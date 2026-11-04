from typing import Literal

from pydantic import BaseModel, Field


class ImageAnalyzeRequest(BaseModel):
    listingIds: list[int] = Field(default_factory=list, max_length=200)
    limit: int = Field(default=30, ge=1, le=200)


class ReputationMentionCreate(BaseModel):
    communityId: int = Field(ge=1)
    source: str = Field(default="manual", max_length=32)
    url: str | None = Field(default=None, max_length=512)
    title: str | None = Field(default=None, max_length=255)
    excerpt: str = Field(min_length=4, max_length=2000)
    issueType: str | None = Field(default=None, max_length=32)
    severity: Literal["low", "medium", "high"] = "low"
    confidence: float = Field(default=0.5, ge=0.05, le=1)
    matchStatus: Literal["verified", "uncertain", "rejected"] = "verified"
    publishedAt: str | None = None


class ReputationStatusUpdate(BaseModel):
    matchStatus: Literal["verified", "uncertain", "rejected"]


class ReputationExtractRequest(BaseModel):
    communityId: int = Field(ge=1)
    text: str = Field(min_length=10, max_length=8000)


class AgentEvalRunRequest(BaseModel):
    mode: Literal["rules"] = "rules"
