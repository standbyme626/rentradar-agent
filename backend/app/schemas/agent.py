from datetime import datetime

from pydantic import BaseModel, Field


class AgentRequest(BaseModel):
    sessionId: str | None = None
    message: str = Field(min_length=1, max_length=500)


class ChatSessionOut(BaseModel):
    id: str
    title: str
    prompt: str
    updatedAt: datetime


class MonitorCreate(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    conditions: dict = Field(default_factory=dict)


class SavedMonitorOut(BaseModel):
    id: str
    name: str
    conditions: dict
    createdAt: datetime
    newMatches: int = 0
