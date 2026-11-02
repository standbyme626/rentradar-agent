from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import ACCESS_COOKIE, REFRESH_COOKIE, get_current_user, request_ip
from app.core.config import settings
from app.core.db import get_db
from app.core.rate_limit import (
    clear_login_failures,
    login_blocked,
    record_login_failure,
)
from app.core.security import TokenError, decode_access_token
from app.models import User
from app.schemas.auth import ChangePasswordRequest, LoginRequest, UserOut
from app.services import auth_service

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _set_auth_cookies(response: Response, access_token: str, refresh_token: str) -> None:
    common = {
        "httponly": True,
        "samesite": "lax",
        "secure": settings.cookie_secure,
        "path": "/",
    }
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        max_age=max(1, settings.access_token_minutes) * 60,
        **common,
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        max_age=max(1, settings.refresh_token_days) * 86400,
        **common,
    )


def _clear_auth_cookies(response: Response) -> None:
    response.delete_cookie(ACCESS_COOKIE, path="/")
    response.delete_cookie(REFRESH_COOKIE, path="/")


@router.post("/login", response_model=UserOut)
async def login(
    payload: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
) -> UserOut:
    ip = request_ip(request)
    key = f"{ip}:{payload.username.lower()}"
    if await login_blocked(key):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="登录失败次数过多，请稍后再试",
        )
    user = await auth_service.authenticate(db, payload.username, payload.password)
    if user is None:
        await record_login_failure(key)
        await auth_service.audit(
            db,
            user=None,
            username=payload.username,
            action="auth.login_failed",
            target=payload.username,
            detail={"ip": ip},
            ip=ip,
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
        )
    await clear_login_failures(key)
    access_token, refresh_token, _ = await auth_service.create_session(
        db, user, ip=ip, user_agent=request.headers.get("user-agent")
    )
    _set_auth_cookies(response, access_token, refresh_token)
    await auth_service.audit(
        db,
        user=user,
        action="auth.login",
        target=user.username,
        detail={"role": user.role},
        ip=ip,
    )
    return UserOut.from_user(user)


@router.post("/refresh", response_model=UserOut)
async def refresh(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> UserOut:
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="missing refresh")
    rotated = await auth_service.rotate_refresh_token(db, token)
    if rotated is None:
        _clear_auth_cookies(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="refresh expired")
    user, access_token, next_refresh, _ = rotated
    _set_auth_cookies(response, access_token, next_refresh)
    return UserOut.from_user(user)


@router.post("/logout")
async def logout(
    request: Request, response: Response, db: AsyncSession = Depends(get_db)
) -> dict:
    token = request.cookies.get(ACCESS_COOKIE)
    user: User | None = None
    if token:
        try:
            payload = decode_access_token(token)
            user = await auth_service.resolve_access_token(db, token)
            await auth_service.revoke_session(db, str(payload["sid"]))
        except TokenError:
            user = None
    if user is not None:
        await auth_service.audit(
            db,
            user=user,
            action="auth.logout",
            target=user.username,
            ip=request_ip(request),
        )
    _clear_auth_cookies(response)
    return {"ok": True}


@router.get("/me", response_model=UserOut)
async def me(user: User = Depends(get_current_user)) -> UserOut:
    return UserOut.from_user(user)


@router.post("/change-password")
async def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    response: Response,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    changed = await auth_service.change_password(
        db, user, payload.oldPassword, payload.newPassword
    )
    if not changed:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="原密码不正确")
    await auth_service.audit(
        db,
        user=user,
        action="auth.password_changed",
        target=user.username,
        ip=request_ip(request),
    )
    _clear_auth_cookies(response)
    return {"ok": True, "reLogin": True}
