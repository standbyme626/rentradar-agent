from fastapi import APIRouter, Depends
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.db import get_db
from app.core.logging import get_logger
from app.models import Job, JobStatus
from app.schemas import SettingsStatus

router = APIRouter(tags=["meta"])
log = get_logger("health")


@router.get("/health")
async def health(db: AsyncSession = Depends(get_db)) -> dict:
    try:
        await db.execute(text("SELECT 1"))
        queued = await db.scalar(
            select(func.count()).select_from(Job).where(Job.status == JobStatus.queued)
        )
        return {
            "status": "ok",
            "db": "ok",
            "queued_jobs": int(queued or 0),
            "version": settings.version,
            "env": settings.env,
        }
    except Exception as exc:  # pragma: no cover - operational guard
        log.error("health_check_failed", error=str(exc))
        return {"status": "degraded", "db": "error", "detail": str(exc)}


@router.get("/api/settings/status", response_model=SettingsStatus)
async def settings_status() -> SettingsStatus:
    return SettingsStatus(
        env=settings.env,
        api_auth_enabled=True,
        feishu_configured=bool(settings.feishu_app_id and settings.feishu_app_secret),
        amap_configured=bool(settings.amap_web_key),
        baidu_configured=bool(settings.baidu_ak),
        baidu_proxy_configured=bool(settings.baidu_proxy),
    )
