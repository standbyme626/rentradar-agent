from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import request_ip, require_admin
from app.core.db import get_db
from app.integrations.base import ProviderError
from app.models import Job, JobStatus, Task, User
from app.schemas import CommuteSetting, CommuteUpdate, EnrichResponse
from app.services import auth_service
from app.services.settings_service import (
    get_admin_settings,
    get_commute_destination,
    set_commute_destination,
)

router = APIRouter(
    prefix="/api/settings", tags=["settings"], dependencies=[Depends(require_admin)]
)


def _to_setting(value: dict | None) -> CommuteSetting:
    if not value:
        return CommuteSetting(configured=False)
    return CommuteSetting(
        configured=True,
        address=value.get("address"),
        city=value.get("city"),
        lng=value.get("lng"),
        lat=value.get("lat"),
        level=value.get("level"),
        example=bool(value.get("example")),
    )


@router.get("/commute", response_model=CommuteSetting)
async def get_commute(db: AsyncSession = Depends(get_db)) -> CommuteSetting:
    return _to_setting(await get_commute_destination(db))


@router.put("/commute", response_model=CommuteSetting)
async def put_commute(
    payload: CommuteUpdate,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> CommuteSetting:
    try:
        value = await set_commute_destination(db, payload.address, payload.city, payload.example)
    except (ValueError, ProviderError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    await auth_service.audit(
        db,
        user=user,
        action="settings.commute_destination",
        target=payload.address,
        detail={"city": payload.city, "example": payload.example},
        ip=request_ip(request),
    )
    return _to_setting(value)


@router.post("/enrich", response_model=EnrichResponse)
async def request_enrich(db: AsyncSession = Depends(get_db)) -> EnrichResponse:
    admin_settings = await get_admin_settings(db)
    limit = max(1, int(admin_settings.get("batchCap") or 10))
    tasks = (await db.execute(select(Task).where(Task.enabled.is_(True)))).scalars().all()
    job_ids: list[int] = []
    for task in tasks:
        existing = await db.scalar(
            select(func.count())
            .select_from(Job)
            .where(
                Job.task_id == task.id,
                Job.type == "enrich",
                Job.status.in_([JobStatus.queued, JobStatus.running]),
            )
        )
        if existing:
            continue
        job = Job(
            task_id=task.id,
            type="enrich",
            payload={"limit": limit},
            status=JobStatus.queued,
        )
        db.add(job)
        await db.flush()
        job_ids.append(job.id)
    await db.commit()
    return EnrichResponse(jobs=job_ids)
