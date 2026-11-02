from datetime import datetime

from pydantic import BaseModel, Field


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: int
    username: str
    role: str
    isActive: bool = True
    lastLoginAt: datetime | None = None

    @classmethod
    def from_user(cls, user) -> "UserOut":
        return cls(
            id=user.id,
            username=user.username,
            role=user.role,
            isActive=bool(user.is_active),
            lastLoginAt=user.last_login_at,
        )


class ChangePasswordRequest(BaseModel):
    oldPassword: str = Field(min_length=1, max_length=128)
    newPassword: str = Field(min_length=8, max_length=128)


class AuditLogOut(BaseModel):
    id: int
    username: str | None
    action: str
    target: str | None
    detail: dict
    ip: str | None
    createdAt: datetime
