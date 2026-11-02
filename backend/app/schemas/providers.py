from datetime import datetime

from pydantic import BaseModel, Field


class ProviderQuotaOut(BaseModel):
    period: str
    limit: int
    used: int
    remaining: int | None = None
    unit: str = "call"


class ProviderHealthOut(BaseModel):
    status: str = "unknown"
    consecutive_failures: int = 0
    circuit_open_until: datetime | None = None
    last_ok_at: datetime | None = None
    last_error: str | None = None


class ProviderCallOut(BaseModel):
    id: int
    provider: str
    capability: str
    status: str
    latency_ms: int | None = None
    quota_units: int = 0
    cached: bool = False
    error_code: str | None = None
    error_message: str | None = None
    request_id: str | None = None
    created_at: datetime


class ProviderOut(BaseModel):
    code: str
    name: str
    domain: str
    capabilities: list[str]
    auth: str
    coord_system: str
    description: str
    docs_url: str
    proxy: str | None = None
    priority: int
    enabled: bool
    configured: bool
    implemented: bool
    quota: ProviderQuotaOut
    health: ProviderHealthOut
    last_call: ProviderCallOut | None = None
    test_note: str | None = None


class ProviderTestResultOut(BaseModel):
    provider: str
    ok: bool
    message: str
    latency_ms: int
    quota_units: int
    health: ProviderHealthOut


class ProviderUsageOut(BaseModel):
    provider: str
    period: str
    used: int
    limit: int
    updated_at: datetime


class ProviderPatch(BaseModel):
    enabled: bool | None = None
    priority: int | None = Field(default=None, ge=0, le=1000)
