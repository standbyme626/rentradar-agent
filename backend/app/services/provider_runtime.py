from datetime import UTC, datetime, timedelta
from time import monotonic

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.db import SessionLocal
from app.core.logging import get_logger
from app.integrations.base import (
    BaseProvider,
    Capability,
    ProviderDomain,
    ProviderError,
    ProviderQuotaExceeded,
    ProviderUnavailable,
)
from app.integrations.registry import load_default_providers, registry
from app.models import ProviderCall, ProviderHealth, ProviderSetting, ProviderUsage
from app.services.settings_service import get_admin_settings

log = get_logger("provider_runtime")
CIRCUIT_FAILURE_THRESHOLD = 3
CIRCUIT_OPEN_MINUTES = 5


class ProviderDisabled(ProviderError):
    pass


class ProviderCircuitOpen(ProviderError):
    pass


async def _settings_map(db: AsyncSession) -> dict[str, ProviderSetting]:
    rows = (
        await db.execute(
            select(ProviderSetting).execution_options(populate_existing=True)
        )
    ).scalars().all()
    return {row.provider: row for row in rows}


def _effective_limit(
    provider: BaseProvider,
    *,
    usage: ProviderUsage | None,
    admin_settings: dict,
    cap_key: str | None,
) -> int | None:
    meta_limit = int(provider.meta.quota.limit or 0)
    limit: int | None = meta_limit or (int(usage.limit_value) if usage else 0) or None
    if cap_key is not None:
        cap = int(admin_settings.get(cap_key) or 0)
        if cap <= 0:
            return 0
        limit = min(limit, cap) if limit else cap
    return limit


async def usage_snapshot(
    db: AsyncSession,
    provider: BaseProvider,
    *,
    admin_settings: dict | None = None,
    cap_key: str | None = None,
) -> tuple[int, int | None, str]:
    admin_settings = admin_settings or await get_admin_settings(db)
    period = provider.meta.quota.period_key()
    usage = await db.get(
        ProviderUsage, (provider.meta.code, period), populate_existing=True
    )
    used = int(usage.used or 0) if usage else 0
    limit = _effective_limit(
        provider, usage=usage, admin_settings=admin_settings, cap_key=cap_key
    )
    return used, limit, period


async def quota_snapshot(
    db: AsyncSession, code: str, *, cap_key: str | None = None
) -> tuple[int, int | None]:
    load_default_providers()
    provider = registry.get(code)
    if provider is None:
        raise ProviderUnavailable(f"unknown provider {code}")
    used, limit, _ = await usage_snapshot(db, provider, cap_key=cap_key)
    return used, limit


async def preflight(
    db: AsyncSession,
    provider: BaseProvider,
    *,
    units: int = 1,
    cap_key: str | None = None,
    admin_settings: dict | None = None,
    settings_map: dict[str, ProviderSetting] | None = None,
) -> int | None:
    code = provider.meta.code
    setting = (settings_map or await _settings_map(db)).get(code)
    enabled = setting.enabled if setting else provider.meta.enabled
    if not enabled:
        raise ProviderDisabled(f"{code} 已在 Provider 管理中停用")
    if not getattr(provider, "configured", True):
        raise ProviderDisabled(f"{code} 未配置凭据")
    health = await db.get(ProviderHealth, code, populate_existing=True)
    now = datetime.now(UTC)
    if health and health.circuit_open_until:
        open_until = health.circuit_open_until
        if open_until.tzinfo is None:
            open_until = open_until.replace(tzinfo=UTC)
        if open_until > now:
            raise ProviderCircuitOpen(f"{code} 熔断中，恢复时间 {open_until.isoformat()}")
    used, limit, _ = await usage_snapshot(
        db,
        provider,
        admin_settings=admin_settings,
        cap_key=cap_key,
    )
    if limit is not None and used + max(0, units) > limit:
        raise ProviderQuotaExceeded(
            f"{code} 额度不足：已用 {used}/{limit}，本次需要 {units}"
        )
    return limit


async def record_call(
    provider: BaseProvider,
    *,
    capability: str,
    status: str,
    latency_ms: int | None = None,
    units: int = 0,
    error: str | None = None,
    request_id: str | None = None,
    limit: int | None = None,
) -> None:
    code = provider.meta.code
    now = datetime.now(UTC)
    async with SessionLocal() as db:
        db.add(
            ProviderCall(
                provider=code,
                capability=capability,
                status=status,
                latency_ms=latency_ms,
                quota_units=max(0, units),
                error_code=status if status != "ok" else None,
                error_message=(error or None) if status != "ok" else None,
                request_id=(request_id or "")[:64] or None,
            )
        )
        health = await db.get(ProviderHealth, code, populate_existing=True)
        if health is None:
            health = ProviderHealth(provider=code, consecutive_failures=0)
            db.add(health)
        if status == "ok":
            health.status = "ok"
            health.consecutive_failures = 0
            health.last_ok_at = now
            health.last_error = None
            health.circuit_open_until = None
        else:
            health.status = "error"
            health.consecutive_failures = int(health.consecutive_failures or 0) + 1
            health.last_error = (error or "provider call failed")[:500]
            if health.consecutive_failures >= CIRCUIT_FAILURE_THRESHOLD:
                health.circuit_open_until = now + timedelta(minutes=CIRCUIT_OPEN_MINUTES)
        if units > 0:
            period = provider.meta.quota.period_key()
            usage = await db.get(ProviderUsage, (code, period))
            if usage is None:
                usage = ProviderUsage(
                    provider=code,
                    period=period,
                    used=0,
                    limit_value=int(limit or 0),
                )
                db.add(usage)
            usage.used = int(usage.used or 0) + units
            if limit is not None:
                usage.limit_value = int(limit)
        await db.commit()


async def record_external_call(
    code: str,
    *,
    capability: str,
    status: str,
    latency_ms: int | None = None,
    units: int = 0,
    error: str | None = None,
    request_id: str | None = None,
) -> None:
    load_default_providers()
    provider = registry.get(code)
    if provider is None:
        return
    await record_call(
        provider,
        capability=capability,
        status=status,
        latency_ms=latency_ms,
        units=units,
        error=error,
        request_id=request_id,
    )


async def ensure_enabled(db: AsyncSession, code: str) -> BaseProvider:
    load_default_providers()
    provider = registry.get(code)
    if provider is None:
        raise ProviderUnavailable(f"unknown provider {code}")
    await preflight(db, provider, units=0)
    return provider


async def _ordered_providers(
    db: AsyncSession, capability: Capability
) -> list[BaseProvider]:
    load_default_providers()
    settings_map = await _settings_map(db)
    providers = [
        provider
        for provider in registry.providers_for(capability)
        if provider.meta.implemented
    ]
    providers.sort(
        key=lambda provider: (
            settings_map[provider.meta.code].priority
            if provider.meta.code in settings_map
            else provider.meta.priority,
            provider.meta.code,
        )
    )
    return providers


async def invoke(
    db: AsyncSession,
    capability: Capability,
    operation: str,
    *args,
    units: int = 1,
    cap_key: str | None = None,
    **kwargs,
):
    admin_settings = await get_admin_settings(db)
    settings_map = await _settings_map(db)
    last_error: Exception | None = None
    for provider in await _ordered_providers(db, capability):
        if not hasattr(provider, operation):
            continue
        provider_cap_key = cap_key
        if cap_key == "amapMonthlyCap" and provider.meta.code != "amap":
            provider_cap_key = None
        if cap_key == "aiDailyCap" and provider.meta.domain != ProviderDomain.ai:
            provider_cap_key = None
        try:
            limit = await preflight(
                db,
                provider,
                units=units,
                cap_key=provider_cap_key,
                admin_settings=admin_settings,
                settings_map=settings_map,
            )
        except ProviderError as exc:
            last_error = exc
            continue
        started = monotonic()
        try:
            result = await getattr(provider, operation)(*args, **kwargs)
        except Exception as exc:
            latency = int((monotonic() - started) * 1000)
            await record_call(
                provider,
                capability=capability.value,
                status="error",
                latency_ms=latency,
                units=units,
                error=f"{type(exc).__name__}: {exc}"[:500],
                limit=limit,
            )
            last_error = exc
            log.warning(
                "provider_call_failed",
                provider=provider.meta.code,
                capability=capability.value,
                error=str(exc)[:200],
            )
            continue
        latency = int((monotonic() - started) * 1000)
        await record_call(
            provider,
            capability=capability.value,
            status="ok",
            latency_ms=latency,
            units=units,
            limit=limit,
        )
        return result
    if isinstance(last_error, (ProviderQuotaExceeded, ProviderDisabled, ProviderCircuitOpen)):
        raise last_error
    if last_error is not None:
        raise ProviderUnavailable(str(last_error)) from last_error
    raise ProviderUnavailable(f"没有可用的 {capability.value}/{operation} Provider")


async def invoke_chat(
    db: AsyncSession,
    messages: list[dict],
    *,
    max_tokens: int,
    temperature: float,
    tools: list[dict] | None = None,
    tool_choice: str | dict | None = None,
) -> dict:
    admin_settings = await get_admin_settings(db)
    settings_map = await _settings_map(db)
    last_error: Exception | None = None
    for provider in await _ordered_providers(db, Capability.chat):
        if not hasattr(provider, "chat"):
            continue
        try:
            limit = await preflight(
                db,
                provider,
                units=1,
                cap_key="aiDailyCap",
                admin_settings=admin_settings,
                settings_map=settings_map,
            )
        except ProviderError as exc:
            last_error = exc
            continue
        started = monotonic()
        try:
            kwargs: dict = {"max_tokens": max_tokens, "temperature": temperature}
            if tools and getattr(provider, "supports_tools", False):
                kwargs["tools"] = tools
                kwargs["tool_choice"] = tool_choice
            result = await provider.chat(messages, **kwargs)
        except Exception as exc:
            latency = int((monotonic() - started) * 1000)
            await record_call(
                provider,
                capability=Capability.chat.value,
                status="error",
                latency_ms=latency,
                units=1,
                error=f"{type(exc).__name__}: {exc}"[:500],
                limit=limit,
            )
            last_error = exc
            continue
        latency = int((monotonic() - started) * 1000)
        await record_call(
            provider,
            capability=Capability.chat.value,
            status="ok",
            latency_ms=latency,
            units=1,
            limit=limit,
            request_id=(
                f"tokens:{int(result.get('prompt_tokens') or 0)}/"
                f"{int(result.get('completion_tokens') or 0)}"
            ),
        )
        return result
    if isinstance(last_error, (ProviderQuotaExceeded, ProviderDisabled, ProviderCircuitOpen)):
        raise last_error
    if last_error is not None:
        raise ProviderUnavailable(str(last_error)) from last_error
    raise ProviderUnavailable("没有可用的 chat Provider")
