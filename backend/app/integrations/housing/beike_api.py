import time

from app.integrations.base import (
    BaseProvider,
    Capability,
    ProviderDomain,
    ProviderMeta,
    ProviderTestResult,
    QuotaPolicy,
)
from app.sources.beike_api import BeikeAPIFetcher


class BeikeApiProvider(BaseProvider):
    meta = ProviderMeta(
        code="beike_api",
        name="贝壳 App 列表",
        domain=ProviderDomain.housing,
        capabilities=frozenset({Capability.listing_search}),
        auth="none",
        coord_system="GCJ02",
        description="免登录列表 API，返回坐标、调价、上架时间和标签",
        docs_url="",
        quota=QuotaPolicy(period="day", limit=0),
        priority=10,
    )

    async def test(self) -> ProviderTestResult:
        started = time.monotonic()
        fetcher = BeikeAPIFetcher()
        try:
            drafts, total = await fetcher.fetch_page(
                1, line="li110460696", sort="newest", limit=1
            )
        finally:
            await fetcher.close()
        latency = int((time.monotonic() - started) * 1000)
        return ProviderTestResult(
            ok=bool(drafts),
            message=f"返回 {len(drafts)} 条，5 号线 total={total}",
            latency_ms=latency,
        )
