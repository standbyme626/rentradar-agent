import time

from app.core.config import settings
from app.geo import amap
from app.integrations.base import (
    BaseProvider,
    Capability,
    ProviderDomain,
    ProviderMeta,
    ProviderTestResult,
    QuotaPolicy,
)


class AmapProvider(BaseProvider):
    meta = ProviderMeta(
        code="amap",
        name="高德地图",
        domain=ProviderDomain.maps,
        capabilities=frozenset(
            {
                Capability.geocode,
                Capability.poi_search,
                Capability.route_transit,
            }
        ),
        auth="api_key",
        coord_system="GCJ02",
        description="POI、地理编码、公交通勤；个人 Key 每月约 5000 次",
        docs_url="https://lbs.amap.com/api/webservice/summary",
        quota=QuotaPolicy(period="month", limit=5000),
        priority=30,
    )

    def __init__(self) -> None:
        self.configured = bool(settings.amap_web_key)

    async def test(self) -> ProviderTestResult:
        started = time.monotonic()
        latency = int((time.monotonic() - started) * 1000)
        if not self.configured:
            return ProviderTestResult(
                ok=False, message="未配置 AMAP_WEB_KEY", latency_ms=latency
            )
        return ProviderTestResult(
            ok=True,
            message="Key 已配置；为避免消耗额度，未发起真实请求",
            latency_ms=latency,
        )

    async def geocode(self, address: str, city: str = "深圳") -> dict | None:
        return await amap.geocode(address, city)

    async def search_poi(
        self, keywords: str, city: str = "深圳", types: str = "120000"
    ) -> dict | None:
        return await amap.search_poi(keywords, city, types)

    async def around_count(self, location: str, types: str, radius: int = 1000) -> int:
        return await amap.around_count(location, types, radius)

    async def transit(self, origin: str, destination: str, city: str = "0755") -> dict | None:
        return await amap.transit(origin, destination, city)
