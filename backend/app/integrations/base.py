from dataclasses import dataclass, field
from enum import StrEnum


class ProviderDomain(StrEnum):
    housing = "housing"
    maps = "maps"
    transit = "transit"
    opendata = "opendata"
    reputation = "reputation"
    ai = "ai"
    notify = "notify"


class Capability(StrEnum):
    listing_search = "listing_search"
    listing_detail = "listing_detail"
    geocode = "geocode"
    reverse_geocode = "reverse_geocode"
    poi_search = "poi_search"
    route_driving = "route_driving"
    route_transit = "route_transit"
    taxi_estimate = "taxi_estimate"
    metro_time = "metro_time"
    rent_reference = "rent_reference"
    reputation = "reputation"
    image_tagging = "image_tagging"
    chat = "chat"


@dataclass(frozen=True, slots=True)
class QuotaPolicy:
    period: str = "month"
    limit: int = 0
    unit: str = "call"

    def period_key(self) -> str:
        from datetime import datetime
        from zoneinfo import ZoneInfo

        now = datetime.now(ZoneInfo("Asia/Shanghai"))
        if self.period == "day":
            return now.strftime("%Y-%m-%d")
        return now.strftime("%Y-%m")


@dataclass(frozen=True, slots=True)
class ProviderMeta:
    code: str
    name: str
    domain: ProviderDomain
    capabilities: frozenset[Capability]
    auth: str = "none"
    coord_system: str = "GCJ02"
    description: str = ""
    docs_url: str = ""
    quota: QuotaPolicy = field(default_factory=QuotaPolicy)
    proxy: str | None = None
    priority: int = 100
    enabled: bool = True
    implemented: bool = True


@dataclass(slots=True)
class ProviderTestResult:
    ok: bool
    message: str
    latency_ms: int = 0
    quota_units: int = 0


class ProviderError(Exception):
    pass


class ProviderAuthError(ProviderError):
    pass


class ProviderRateLimitError(ProviderError):
    pass


class ProviderQuotaExceeded(ProviderError):
    pass


class ProviderUnavailable(ProviderError):
    pass


class BaseProvider:
    meta: ProviderMeta
    configured: bool = True

    async def test(self) -> ProviderTestResult:
        raise NotImplementedError

    async def close(self) -> None:
        return None
