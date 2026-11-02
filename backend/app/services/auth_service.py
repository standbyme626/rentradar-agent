from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    TokenError,
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    new_session_id,
    verify_password,
)
from app.models import AuditLog, AuthSession, User


async def authenticate(db: AsyncSession, username: str, password: str) -> User | None:
    user = await db.scalar(select(User).where(User.username == username))
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user


async def create_session(
    db: AsyncSession,
    user: User,
    *,
    ip: str | None = None,
    user_agent: str | None = None,
) -> tuple[str, str, AuthSession]:
    session_id = new_session_id()
    refresh_token = new_refresh_token()
    now = datetime.now(UTC)
    session = AuthSession(
        id=session_id,
        user_id=user.id,
        refresh_hash=hash_refresh_token(refresh_token),
        user_agent=(user_agent or "")[:255] or None,
        ip=(ip or "")[:64] or None,
        expires_at=now + timedelta(days=max(1, settings.refresh_token_days)),
        last_seen_at=now,
    )
    db.add(session)
    user.last_login_at = now
    await db.commit()
    await db.refresh(session)
    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        session_id=session.id,
    )
    return access_token, refresh_token, session


async def rotate_refresh_token(
    db: AsyncSession, refresh_token: str
) -> tuple[User, str, str, AuthSession] | None:
    refresh_hash = hash_refresh_token(refresh_token)
    session = await db.scalar(
        select(AuthSession).where(AuthSession.refresh_hash == refresh_hash)
    )
    if session is None or session.revoked_at is not None:
        return None
    now = datetime.now(UTC)
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now:
        return None
    user = await db.get(User, session.user_id)
    if user is None or not user.is_active:
        return None
    new_token = new_refresh_token()
    session.refresh_hash = hash_refresh_token(new_token)
    session.expires_at = now + timedelta(days=max(1, settings.refresh_token_days))
    session.last_seen_at = now
    await db.commit()
    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role,
        session_id=session.id,
    )
    return user, access_token, new_token, session


async def resolve_access_token(db: AsyncSession, token: str) -> User | None:
    try:
        payload = decode_access_token(token)
    except TokenError:
        return None
    session = await db.get(AuthSession, str(payload["sid"]))
    if session is None or session.revoked_at is not None:
        return None
    now = datetime.now(UTC)
    expires_at = session.expires_at
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=UTC)
    if expires_at <= now:
        return None
    user = await db.get(User, int(payload["sub"]))
    if user is None or not user.is_active:
        return None
    last_seen = session.last_seen_at
    if last_seen.tzinfo is None:
        last_seen = last_seen.replace(tzinfo=UTC)
    if (now - last_seen).total_seconds() > 300:
        session.last_seen_at = now
        await db.commit()
    return user


async def revoke_session(db: AsyncSession, session_id: str) -> None:
    await db.execute(
        update(AuthSession)
        .where(AuthSession.id == session_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await db.commit()


async def revoke_user_sessions(db: AsyncSession, user_id: int) -> None:
    await db.execute(
        update(AuthSession)
        .where(AuthSession.user_id == user_id, AuthSession.revoked_at.is_(None))
        .values(revoked_at=datetime.now(UTC))
    )
    await db.commit()


async def change_password(
    db: AsyncSession, user: User, old_password: str, new_password: str
) -> bool:
    if not verify_password(old_password, user.password_hash):
        return False
    user.password_hash = hash_password(new_password)
    await revoke_user_sessions(db, user.id)
    await db.commit()
    return True


async def audit(
    db: AsyncSession,
    *,
    user: User | None,
    action: str,
    target: str | None = None,
    detail: dict | None = None,
    ip: str | None = None,
    username: str | None = None,
) -> None:
    db.add(
        AuditLog(
            user_id=user.id if user else None,
            username=(user.username if user else username),
            action=action[:64],
            target=(target or "")[:128] or None,
            detail=detail or {},
            ip=(ip or "")[:64] or None,
        )
    )
    await db.commit()


async def list_audit(db: AsyncSession, limit: int = 100) -> list[dict]:
    rows = (
        (
            await db.execute(
                select(AuditLog)
                .order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
                .limit(max(1, min(limit, 500)))
            )
        )
        .scalars()
        .all()
    )
    return [
        {
            "id": item.id,
            "username": item.username,
            "action": item.action,
            "target": item.target,
            "detail": item.detail or {},
            "ip": item.ip,
            "createdAt": item.created_at,
        }
        for item in rows
    ]


async def purge_expired_sessions(db: AsyncSession, days: int = 30) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=max(1, days))
    result = await db.execute(
        delete(AuthSession).where(AuthSession.expires_at < cutoff)
    )
    await db.commit()
    return int(result.rowcount or 0)
