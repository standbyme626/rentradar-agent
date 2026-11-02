from pydantic import BaseModel, Field


class AdminSettings(BaseModel):
    amapMonthlyCap: int = Field(default=5000, ge=0)
    sessionAmapCap: int = Field(default=15, ge=1)
    batchCap: int = Field(default=10, ge=1)
    aiDailyCap: int = Field(default=500, ge=0)
    notifyBatchCap: int = Field(default=10, ge=1, le=100)
    notifyScoreMin: int = Field(default=75, ge=0, le=100)
    priceDropPct: float = Field(default=8.0, ge=0, le=100)
    quietStart: str = Field(default="23:00", pattern=r"^\d{2}:\d{2}$")
    quietEnd: str = Field(default="08:00", pattern=r"^\d{2}:\d{2}$")
    feishu: bool = True
    digest: bool = True
    quiet: bool = True
    pauseAlert: bool = True
    monitorPush: bool = True


class AnalysisRequest(BaseModel):
    listingIds: list[int] = Field(default_factory=list)


class SamplingRequest(BaseModel):
    origin: str = "深圳会展中心"
    count: int = Field(default=10, ge=1, le=200)
    buckets: list[str] = Field(default_factory=list)
    modes: list[str] = Field(default_factory=list)


class GeocodeRequest(BaseModel):
    communityIds: list[int] = Field(default_factory=list)


class AnnotateRequest(BaseModel):
    label: str


class JobOut(BaseModel):
    id: str
    type: str
    status: str
    calls: int | None = None
    createdAt: str
