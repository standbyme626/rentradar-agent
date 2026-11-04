from datetime import UTC, datetime, timedelta
from time import monotonic

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.integrations.base import BaseProvider, ProviderDomain, ProviderError
from app.integrations.registry import load_default_providers, registry
from app.models import ProviderCall, ProviderHealth, ProviderSetting, ProviderUsage
from app.services import provider_runtime
from app.services.settings_service import get_admin_settings


def _cap_key(provider: BaseProvider) -> str | None:
    """Map provider to the runtime hard cap that governs it."""
    if provider.meta.domain == ProviderDomain.ai:
        return "aiDailyCap"
    if provider.meta.code == "amap":
        return "amapMonthlyCap"
    return None


def _health_dict(health: ProviderHealth | None) -> dict:
    if health is None:
        return {
            "status": "unknown",
            "consecutive_failures": 0,
            "circuit_open_until": None,
            "last_ok_at": None,
            "last_error": None,
        }
    return {
        "status": health.status,
        "consecutive_failures": health.consecutive_failures,
        "circuit_open_until": health.circuit_open_until,
        "last_ok_at": health.last_ok_at,
        "last_error": health.last_error,
    }


def _call_dict(call: ProviderCall | None) -> dict | None:
    if call is None:
        return None
    return {
        "id": call.id,
        "provider": call.provider,
        "capability": call.capability,
        "status": call.status,
        "latency_ms": call.latency_ms,
        "quota_units": call.quota_units,
        "cached": call.cached,
        "error_code": call.error_code,
        "error_message": call.error_message,
        "request_id": call.request_id,
        "created_at": call.created_at,
    }


async def _provider_payload(
    db: AsyncSession, provider: BaseProvider
) -> dict:
    code = provider.meta.code
    setting = await db.get(ProviderSetting, code)
    health = await db.get(ProviderHealth, code)
    admin_settings = await get_admin_settings(db)
    cap_key = _cap_key(provider)
    used, limit, period = await provider_runtime.usage_snapshot(
        db, provider, admin_settings=admin_settings, cap_key=cap_key
    )
    last_call = await db.scalar(
        select(ProviderCall)
        .where(ProviderCall.provider == code)
        .order_by(ProviderCall.created_at.desc(), ProviderCall.id.desc())
        .limit(1)
    )
    return {
        "code": code,
        "name": provider.meta.name,
        "domain": provider.meta.domain.value,
        "capabilities": sorted(item.value for item in provider.meta.capabilities),
        "auth": provider.meta.auth,
        "coord_system": provider.meta.coord_system,
        "description": provider.meta.description,
        "docs_url": provider.meta.docs_url,
        "proxy": provider.meta.proxy,
        "priority": setting.priority if setting else provider.meta.priority,
        "enabled": setting.enabled if setting else provider.meta.enabled,
        "configured": provider.configured,
        "implemented": provider.meta.implemented,
        "quota": {
            "period": provider.meta.quota.period,
            "limit": int(limit or 0),
            "used": used,
            "remaining": max(0, limit - used) if limit else None,
            "unit": provider.meta.quota.unit,
        },
        "health": _health_dict(health),
        "last_call": _call_dict(last_call),
        "test_note": getattr(provider, "test_note", None),
    }


async def list_providers(db: AsyncSession, domain: str | None = None) -> list[dict]:
    load_default_providers()
    return [await _provider_payload(db, provider) for provider in registry.by_domain(domain)]


async def get_provider(db: AsyncSession, code: str) -> dict | None:
    load_default_providers()
    provider = registry.get(code)
    if provider is None:
        return None
    return await _provider_payload(db, provider)


async def test_provider(db: AsyncSession, code: str) -> dict | None:
    load_default_providers()
    provider = registry.get(code)
    if provider is None:
        return None

    started = monotonic()
    ok = False
    message = "测试失败"
    quota_units = 0
    try:
        result = await provider.test()
        ok = result.ok
        message = result.message
        quota_units = result.quota_units
    except ProviderError as exc:
        message = str(exc)[:500]
    except Exception as exc:
        message = f"{type(exc).__name__}: {exc}"[:500]
    latency_ms = int((monotonic() - started) * 1000)
    now = datetime.now(UTC)

    db.add(
        ProviderCall(
            provider=code,
            capability="health_check",
            status="ok" if ok else "error",
            latency_ms=latency_ms,
            quota_units=quota_units,
            error_message=None if ok else message,
        )
    )

    health = await db.get(ProviderHealth, code)
    if health is None:
        health = ProviderHealth(provider=code, consecutive_failures=0)
        db.add(health)
    if ok:
        health.status = "ok"
        health.consecutive_failures = 0
        health.last_ok_at = now
        health.last_error = None
        health.circuit_open_until = None
    else:
        health.status = "error"
        health.consecutive_failures = int(health.consecutive_failures or 0) + 1
        health.last_error = message[:500]
        if health.consecutive_failures >= 3:
            health.circuit_open_until = now + timedelta(minutes=5)

    if quota_units:
        admin_settings = await get_admin_settings(db)
        cap_key = _cap_key(provider)
        _, effective_limit, period = await provider_runtime.usage_snapshot(
            db, provider, admin_settings=admin_settings, cap_key=cap_key
        )
        usage = await db.get(ProviderUsage, (code, period), populate_existing=True)
        if usage is None:
            usage = ProviderUsage(
                provider=code,
                period=period,
                used=0,
                limit_value=int(effective_limit or 0),
            )
            db.add(usage)
        usage.used = int(usage.used or 0) + quota_units
        usage.limit_value = int(effective_limit or 0)

    await db.commit()
    await db.refresh(health)
    return {
        "provider": code,
        "ok": ok,
        "message": message,
        "latency_ms": latency_ms,
        "quota_units": quota_units,
        "health": _health_dict(health),
    }


async def list_calls(
    db: AsyncSession,
    *,
    provider: str | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[dict]:
    stmt = select(ProviderCall).order_by(ProviderCall.created_at.desc(), ProviderCall.id.desc())
    if provider:
        stmt = stmt.where(ProviderCall.provider == provider)
    if status:
        stmt = stmt.where(ProviderCall.status == status)
    rows = (await db.execute(stmt.limit(max(1, min(limit, 200))))).scalars().all()
    return [_call_dict(item) for item in rows]


async def list_usage(db: AsyncSession, code: str) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(ProviderUsage)
                .where(ProviderUsage.provider == code)
                .order_by(ProviderUsage.period.desc())
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "provider": item.provider,
            "period": item.period,
            "used": item.used,
            "limit": item.limit_value,
            "updated_at": item.updated_at,
        }
        for item in rows
    ]


async def update_provider_setting(
    db: AsyncSession,
    code: str,
    *,
    enabled: bool | None = None,
    priority: int | None = None,
) -> dict | None:
    load_default_providers()
    provider = registry.get(code)
    if provider is None:
        return None
    setting = await db.get(ProviderSetting, code)
    if setting is None:
        setting = ProviderSetting(
            provider=code,
            domain=provider.meta.domain.value,
            enabled=provider.meta.enabled,
            priority=provider.meta.priority,
        )
        db.add(setting)
    if enabled is not None:
        setting.enabled = enabled
    if priority is not None:
        setting.priority = priority
    await db.commit()
    return await get_provider(db, code)
