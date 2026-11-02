import time

import httpx

from app.core.config import settings
from app.integrations.base import (
    BaseProvider,
    Capability,
    ProviderDomain,
    ProviderMeta,
    ProviderTestResult,
    QuotaPolicy,
)


class BeikeCdpProvider(BaseProvider):
    meta = ProviderMeta(
        code="beike_cdp",
        name="贝壳 CDP",
        domain=ProviderDomain.housing,
        capabilities=frozenset({Capability.listing_search}),
        auth="account",
        coord_system="GCJ02",
        description="受控 Chrome 兜底通道，需要人工通过人机验证",
        quota=QuotaPolicy(period="day", limit=0),
        priority=20,
    )

    async def test(self) -> ProviderTestResult:
        started = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                response = await client.get(f"{settings.cdp_url.rstrip('/')}/json/version")
        except httpx.HTTPError as exc:
            return ProviderTestResult(
                ok=False,
                message=f"CDP 不可达：{type(exc).__name__}",
                latency_ms=int((time.monotonic() - started) * 1000),
            )
        latency = int((time.monotonic() - started) * 1000)
        if response.status_code != 200:
            return ProviderTestResult(
                ok=False,
                message=f"CDP HTTP {response.status_code}",
                latency_ms=latency,
            )
        return ProviderTestResult(ok=True, message="CDP 隧道可连接", latency_ms=latency)
