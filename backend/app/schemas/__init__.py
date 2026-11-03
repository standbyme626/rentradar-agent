from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class SnapshotOut(ORMModel):
    rent: int
    seen_at: datetime
    image_hash: str | None = None


class EventOut(ORMModel):
    id: int
    type: str
    listing_id: int | None = None
    listing_title: str | None = None
    payload: dict = Field(default_factory=dict)
    notified: bool = False
    created_at: datetime


class DeliveryProbeOut(ORMModel):
    id: int
    platform: str
    probe_at: datetime
    meal_period: str | None = None
    address_label: str | None = None
    eta_min_low: int | None = None
    eta_min_high: int | None = None
    fee: float | None = None
    merchant_count: int | None = None
    confidence: float | None = None


class ListingOut(ORMModel):
    id: int
    source_code: str
    city_code: str
    source_listing_id: str
    url: str
    title: str | None = None
    community_name: str | None = None
    district: str | None = None
    layout: str | None = None
    area: float | None = None
    orientation: str | None = None
    floor: str | None = None
    rent: int | None = None
    tags: list[str] = Field(default_factory=list)
    image_url: str | None = None
    agent_type: str | None = None
    score: int | None = None
    status: str
    first_seen_at: datetime
    last_seen_at: datetime


class CommuteStatsOut(BaseModel):
    samples: int = 0
    buckets: list[str] = Field(default_factory=list)
    bucket_count: int = 0
    multi_bucket: bool = False
    p50_min: float | None = None
    p90_min: float | None = None
    static: bool = True
    provider: str | None = None
    mode: str | None = None
    direction: str = "community_to_destination"
    direction_label: str = "小区→公司"
    transfers: int | None = None
    walk_min: float | None = None
    fetched_at: datetime | None = None
    destination: str | None = None
    example: bool = False




class InspectionUpdate(BaseModel):
    items: dict[str, bool] = Field(default_factory=dict)
    note: str | None = None
    photos: list[str] = Field(default_factory=list)


class InspectionOut(InspectionUpdate):
    updated_at: datetime | None = None

class ListingDetail(ListingOut):
    score_reasons: dict = Field(default_factory=dict)
    image_analysis: dict | None = None
    reputation: dict | None = None
    snapshots: list[SnapshotOut] = Field(default_factory=list)
    events: list[EventOut] = Field(default_factory=list)
    delivery_probes: list[DeliveryProbeOut] = Field(default_factory=list)
    watch_state: str | None = None
    watch_note: str | None = None
    watch_updated_at: datetime | None = None
    inspection: InspectionOut | None = None
    commute_stats: CommuteStatsOut | None = None


class ListingPage(ORMModel):
    items: list[ListingOut]
    total: int
    page: int
    page_size: int


class SourceHealth(ORMModel):
    id: int
    code: str
    name: str
    enabled: bool
    active_listings: int
    queued_jobs: int
    last_run_status: str | None = None
    last_run_at: datetime | None = None


class DashboardOut(ORMModel):
    active_listings: int
    new_today: int
    price_drops_today: int
    gone_today: int
    queued_jobs: int
    sources: list[SourceHealth]
    recent_events: list[EventOut]


class TaskOut(ORMModel):
    id: int
    name: str
    city_code: str
    source_code: str
    enabled: bool
    filters: dict = Field(default_factory=dict)
    schedule: dict = Field(default_factory=dict)
    account_strategy: str
    proxy_strategy: str
    created_at: datetime
    last_run_status: str | None = None
    last_run_at: datetime | None = None


class TaskCreate(BaseModel):
    name: str
    city_code: str
    source_code: str
    filters: dict = Field(default_factory=dict)
    schedule: dict = Field(default_factory=lambda: {"fast_minutes": 10, "slow_minutes": 180})
    account_strategy: str = "auto"
    proxy_strategy: str = "direct"


class TaskUpdate(BaseModel):
    name: str | None = None
    enabled: bool | None = None
    filters: dict | None = None
    schedule: dict | None = None
    account_strategy: str | None = None
    proxy_strategy: str | None = None


class StateUpdate(BaseModel):
    state: str = Field(pattern="^(new|seen|contacted|viewed|rejected)$")
    note: str | None = None


class SettingsStatus(BaseModel):
    env: str
    api_auth_enabled: bool
    feishu_configured: bool
    amap_configured: bool
    baidu_configured: bool
    baidu_proxy_configured: bool


class CommuteSetting(BaseModel):
    configured: bool = False
    address: str | None = None
    city: str | None = None
    lng: float | None = None
    lat: float | None = None
    level: str | None = None
    example: bool = False


class CommuteUpdate(BaseModel):
    address: str = Field(min_length=2)
    city: str = "深圳"
    example: bool = False


class EnrichResponse(BaseModel):
    jobs: list[int]

