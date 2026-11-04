from typing import Literal

from pydantic import BaseModel, Field


class ShareLinkCreate(BaseModel):
    label: str = Field(default="只读看板", min_length=1, max_length=64)
    expiresDays: int = Field(default=7, ge=1, le=365)


class SourceUpdate(BaseModel):
    enabled: bool


class CityUpdate(BaseModel):
    enabled: bool


class TaskCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    cityCode: str = Field(default="sz", max_length=16)
    sourceCode: str = Field(default="beike", max_length=32)
    filters: dict = Field(default_factory=dict)
    schedule: dict = Field(default_factory=dict)
    enabled: bool = True


class TaskUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    filters: dict | None = None
    schedule: dict | None = None
    enabled: bool | None = None


class ReferenceRentRow(BaseModel):
    communityId: int | None = Field(default=None, ge=1)
    communityName: str | None = Field(default=None, max_length=128)
    district: str | None = Field(default=None, max_length=64)
    layout: str = Field(min_length=1, max_length=32)
    monthlyRent: int = Field(ge=100, le=100000)
    referenceMonth: str = Field(pattern=r"^\d{4}-\d{2}$")
    source: Literal["manual", "housing_bureau", "district_notice"] = "manual"
    url: str | None = Field(default=None, max_length=512)
    confidence: float = Field(default=0.8, ge=0.1, le=1.0)


class ReferenceRentImport(BaseModel):
    cityCode: str = Field(default="sz", max_length=16)
    rows: list[ReferenceRentRow] = Field(min_length=1, max_length=500)
