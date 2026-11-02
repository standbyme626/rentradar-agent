import enum
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
    text,
)
from sqlalchemy import (
    Enum as SAEnum,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class ListingStatus(enum.StrEnum):
    active = "active"
    gone = "gone"
    suspect = "suspect"
    relisted = "relisted"


class EventType(enum.StrEnum):
    new = "new"
    price_drop = "price_drop"
    price_up = "price_up"
    gone = "gone"
    relisted = "relisted"
    suspect = "suspect"


class JobStatus(enum.StrEnum):
    queued = "queued"
    running = "running"
    done = "done"
    failed = "failed"
    canceled = "canceled"


class City(Base):
    __tablename__ = "cities"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    domain_template: Mapped[str] = mapped_column(String(255))
    center_lng: Mapped[float | None] = mapped_column(Numeric(10, 6))
    center_lat: Mapped[float | None] = mapped_column(Numeric(10, 6))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)

    communities: Mapped[list["Community"]] = relationship(back_populates="city")
    tasks: Mapped[list["Task"]] = relationship(back_populates="city")
    listings: Mapped[list["Listing"]] = relationship(back_populates="city")


class Source(Base):
    __tablename__ = "sources"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(32), default="html")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    rate_limit: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )

    tasks: Mapped[list["Task"]] = relationship(back_populates="source")
    listings: Mapped[list["Listing"]] = relationship(back_populates="source")


class Community(Base):
    __tablename__ = "communities"
    __table_args__ = (UniqueConstraint("city_id", "name", name="uq_community_city_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"), index=True)
    name: Mapped[str] = mapped_column(String(128))
    district: Mapped[str | None] = mapped_column(String(64))
    lng: Mapped[float | None] = mapped_column(Numeric(10, 6))
    lat: Mapped[float | None] = mapped_column(Numeric(10, 6))
    coord_system: Mapped[str] = mapped_column(String(16), default="GCJ02")
    adcode: Mapped[str | None] = mapped_column(String(16))
    geocode_confidence: Mapped[float | None] = mapped_column(Numeric(4, 2))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    city: Mapped[City] = relationship(back_populates="communities")
    listings: Mapped[list["Listing"]] = relationship(back_populates="community")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    filters: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    schedule: Mapped[dict] = mapped_column(
        JSONB,
        default=dict,
        server_default=text("'{}'::jsonb"),
    )
    account_strategy: Mapped[str] = mapped_column(String(16), default="auto")
    proxy_strategy: Mapped[str] = mapped_column(String(16), default="direct")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    city: Mapped[City] = relationship(back_populates="tasks")
    source: Mapped[Source] = relationship(back_populates="tasks")
    jobs: Mapped[list["Job"]] = relationship(back_populates="task")
    runs: Mapped[list["Run"]] = relationship(back_populates="task")


class Job(Base):
    __tablename__ = "jobs"
    __table_args__ = (Index("jobs_claim_idx", "status", "run_after"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id", ondelete="CASCADE"))
    type: Mapped[str] = mapped_column(String(32))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus, name="job_status"), default=JobStatus.queued
    )
    run_after: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    attempts: Mapped[int] = mapped_column(Integer, default=0)
    max_attempts: Mapped[int] = mapped_column(Integer, default=3)
    locked_by: Mapped[str | None] = mapped_column(String(64))
    locked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    task: Mapped[Task | None] = relationship(back_populates="jobs")
    runs: Mapped[list["Run"]] = relationship(back_populates="job")


class Run(Base):
    __tablename__ = "runs"

    id: Mapped[int] = mapped_column(primary_key=True)
    task_id: Mapped[int | None] = mapped_column(ForeignKey("tasks.id"))
    job_id: Mapped[int | None] = mapped_column(ForeignKey("jobs.id"))
    status: Mapped[str] = mapped_column(String(16), default="running")
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    stats: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    error: Mapped[str | None] = mapped_column(Text)

    task: Mapped[Task | None] = relationship(back_populates="runs")
    job: Mapped[Job | None] = relationship(back_populates="runs")


class Listing(Base):
    __tablename__ = "listings"
    __table_args__ = (
        UniqueConstraint("source_id", "source_listing_id", name="uq_listing_source"),
        Index("listings_city_status_score_idx", "city_id", "status", "score"),
        Index("listings_community_idx", "community_id"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    source_id: Mapped[int] = mapped_column(ForeignKey("sources.id"))
    city_id: Mapped[int] = mapped_column(ForeignKey("cities.id"))
    community_id: Mapped[int | None] = mapped_column(ForeignKey("communities.id"))
    source_listing_id: Mapped[str] = mapped_column(String(64))
    url: Mapped[str] = mapped_column(String(512))
    title: Mapped[str | None] = mapped_column(String(255))
    community_name: Mapped[str | None] = mapped_column(String(128))
    district: Mapped[str | None] = mapped_column(String(64))
    layout: Mapped[str | None] = mapped_column(String(32))
    area: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    orientation: Mapped[str | None] = mapped_column(String(32))
    floor: Mapped[str | None] = mapped_column(String(32))
    rent: Mapped[int | None] = mapped_column(Integer)
    tags: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    image_url: Mapped[str | None] = mapped_column(String(512))
    agent_type: Mapped[str | None] = mapped_column(String(16))
    raw: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    raw_hash: Mapped[str | None] = mapped_column(String(64))
    score: Mapped[int | None] = mapped_column(Integer)
    score_reasons: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    status: Mapped[ListingStatus] = mapped_column(
        SAEnum(ListingStatus, name="listing_status"), default=ListingStatus.active
    )
    cluster_id: Mapped[int | None] = mapped_column(Integer)
    miss_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    first_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    source: Mapped[Source] = relationship(back_populates="listings")
    city: Mapped[City] = relationship(back_populates="listings")
    community: Mapped[Community | None] = relationship(back_populates="listings")
    snapshots: Mapped[list["Snapshot"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )
    events: Mapped[list["Event"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )
    watchlist_entries: Mapped[list["Watchlist"]] = relationship(
        back_populates="listing", cascade="all, delete-orphan"
    )


class Snapshot(Base):
    __tablename__ = "snapshots"
    __table_args__ = (Index("snapshots_listing_time_idx", "listing_id", "seen_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    rent: Mapped[int] = mapped_column(Integer)
    seen_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    image_hash: Mapped[str | None] = mapped_column(String(64))

    listing: Mapped[Listing] = relationship(back_populates="snapshots")


class Event(Base):
    __tablename__ = "events"
    __table_args__ = (Index("events_notified_idx", "notified", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int | None] = mapped_column(ForeignKey("listings.id", ondelete="CASCADE"))
    cluster_id: Mapped[int | None] = mapped_column(Integer)
    type: Mapped[EventType] = mapped_column(SAEnum(EventType, name="event_type"))
    payload: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    notified: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    listing: Mapped[Listing | None] = relationship(back_populates="events")


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), default="disabled")
    role: Mapped[str] = mapped_column(String(16), default="admin")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    watchlist_entries: Mapped[list["Watchlist"]] = relationship(back_populates="user")


class AuthSession(Base):
    __tablename__ = "auth_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), index=True
    )
    refresh_hash: Mapped[str] = mapped_column(String(128), unique=True)
    user_agent: Mapped[str | None] = mapped_column(String(255))
    ip: Mapped[str | None] = mapped_column(String(64))
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("audit_log_created_idx", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="SET NULL"))
    username: Mapped[str | None] = mapped_column(String(64))
    action: Mapped[str] = mapped_column(String(64), index=True)
    target: Mapped[str | None] = mapped_column(String(128))
    detail: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    ip: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Watchlist(Base):
    __tablename__ = "watchlist"

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True
    )
    state: Mapped[str] = mapped_column(String(16), default="new")
    note: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    user: Mapped[User] = relationship(back_populates="watchlist_entries")
    listing: Mapped[Listing] = relationship(back_populates="watchlist_entries")


class AppSetting(Base):
    __tablename__ = "app_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class PoiCache(Base):
    __tablename__ = "poi_cache"

    community_id: Mapped[int] = mapped_column(
        ForeignKey("communities.id", ondelete="CASCADE"), primary_key=True
    )
    dining_count: Mapped[int] = mapped_column(Integer, default=0)
    daily_count: Mapped[int] = mapped_column(Integer, default=0)
    nightlife_count: Mapped[int] = mapped_column(Integer, default=0)
    raw: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class CommuteSample(Base):
    __tablename__ = "commute_samples"
    __table_args__ = (
        Index("commute_community_dest_idx", "community_id", "destination_key", "fetched_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("communities.id", ondelete="CASCADE"))
    destination_key: Mapped[str] = mapped_column(String(64))
    mode: Mapped[str] = mapped_column(String(16), default="transit")
    duration_s: Mapped[int] = mapped_column(Integer)
    distance_m: Mapped[int | None] = mapped_column(Integer)
    transfers: Mapped[int | None] = mapped_column(Integer)
    provider: Mapped[str] = mapped_column(String(16), default="amap")
    fetched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    raw: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))


class Inspection(Base):
    __tablename__ = "inspections"

    listing_id: Mapped[int] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    data: Mapped[dict] = mapped_column(JSONB, default=dict, server_default=text("'{}'::jsonb"))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class DeliveryProbe(Base):
    __tablename__ = "delivery_probes"
    __table_args__ = (Index("delivery_community_time_idx", "community_id", "probe_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    community_id: Mapped[int] = mapped_column(ForeignKey("communities.id", ondelete="CASCADE"))
    platform: Mapped[str] = mapped_column(String(16), default="meituan")
    probe_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    meal_period: Mapped[str | None] = mapped_column(String(16))
    address_label: Mapped[str | None] = mapped_column(String(128))
    eta_min_low: Mapped[int | None] = mapped_column(Integer)
    eta_min_high: Mapped[int | None] = mapped_column(Integer)
    fee: Mapped[float | None] = mapped_column(Numeric(6, 2))
    merchant_count: Mapped[int | None] = mapped_column(Integer)
    raw_text: Mapped[str | None] = mapped_column(Text)
    screenshot_paths: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    confidence: Mapped[float | None] = mapped_column(Numeric(4, 2))
    device_id: Mapped[str | None] = mapped_column(String(64))


class ProviderSetting(Base):
    __tablename__ = "provider_settings"

    provider: Mapped[str] = mapped_column(String(64), primary_key=True)
    domain: Mapped[str] = mapped_column(String(32), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    priority: Mapped[int] = mapped_column(Integer, default=100, server_default="100")
    config: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProviderUsage(Base):
    __tablename__ = "provider_usage"

    provider: Mapped[str] = mapped_column(String(64), primary_key=True)
    period: Mapped[str] = mapped_column(String(16), primary_key=True)
    used: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    limit_value: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProviderHealth(Base):
    __tablename__ = "provider_health"

    provider: Mapped[str] = mapped_column(String(64), primary_key=True)
    status: Mapped[str] = mapped_column(String(16), default="unknown", server_default="unknown")
    consecutive_failures: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    circuit_open_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_ok_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_error: Mapped[str | None] = mapped_column(Text)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ProviderCall(Base):
    __tablename__ = "provider_calls"
    __table_args__ = (Index("provider_calls_provider_time_idx", "provider", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), index=True)
    capability: Mapped[str] = mapped_column(String(32), default="health_check")
    status: Mapped[str] = mapped_column(String(16))
    latency_ms: Mapped[int | None] = mapped_column(Integer)
    quota_units: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cached: Mapped[bool] = mapped_column(Boolean, default=False, server_default=text("false"))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_message: Mapped[str | None] = mapped_column(Text)
    request_id: Mapped[str | None] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )


class AgentSession(Base):
    __tablename__ = "agent_sessions"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    title: Mapped[str] = mapped_column(String(128))
    prompt: Mapped[str] = mapped_column(Text)
    conditions: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    status: Mapped[str] = mapped_column(String(16), default="running", server_default="running")
    stage: Mapped[str] = mapped_column(String(128), default="", server_default="")
    candidates: Mapped[str] = mapped_column(String(64), default="", server_default="")
    tools_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    amap_count: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    latency_ms: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    model: Mapped[str] = mapped_column(String(128), default="", server_default="")
    prompt_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    completion_tokens: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    cost: Mapped[float] = mapped_column(Numeric(10, 6), default=0, server_default="0")
    llm_fallback: Mapped[bool] = mapped_column(
        Boolean, default=True, server_default=text("true")
    )
    plan: Mapped[list] = mapped_column(JSONB, default=list, server_default=text("'[]'::jsonb"))
    tools_list: Mapped[list] = mapped_column(
        JSONB, default=list, server_default=text("'[]'::jsonb")
    )
    result: Mapped[str | None] = mapped_column(Text)
    label: Mapped[str | None] = mapped_column(String(32))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AgentMonitor(Base):
    __tablename__ = "agent_monitors"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True
    )
    name: Mapped[str] = mapped_column(String(128))
    conditions: Mapped[dict] = mapped_column(
        JSONB, default=dict, server_default=text("'{}'::jsonb")
    )
    new_matches: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, server_default=text("true"))
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class AgentMonitorMatch(Base):
    __tablename__ = "agent_monitor_matches"
    __table_args__ = (
        UniqueConstraint("monitor_id", "match_key", name="uq_monitor_match_key"),
        Index("agent_monitor_matches_pending_idx", "notified_at", "created_at"),
        Index("agent_monitor_matches_monitor_idx", "monitor_id", "created_at"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    monitor_id: Mapped[str] = mapped_column(
        ForeignKey("agent_monitors.id", ondelete="CASCADE")
    )
    listing_id: Mapped[int | None] = mapped_column(
        ForeignKey("listings.id", ondelete="CASCADE")
    )
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("events.id", ondelete="SET NULL")
    )
    match_key: Mapped[str] = mapped_column(String(64))
    type: Mapped[str] = mapped_column(String(32))
    score: Mapped[int | None] = mapped_column(Integer)
    rent: Mapped[int | None] = mapped_column(Integer)
    title: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    notified_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
