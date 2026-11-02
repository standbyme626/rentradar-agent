from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import request_ip, require_admin
from app.core.db import get_db
from app.models import User
from app.schemas.admin import (
    AdminSettings,
    AnalysisRequest,
    AnnotateRequest,
    GeocodeRequest,
    JobOut,
    SamplingRequest,
)
from app.services import admin_service, agent_service, auth_service

router = APIRouter(
    prefix="/api/admin",
    tags=["admin"],
    dependencies=[Depends(require_admin)],
)


@router.get("/overview")
async def overview(db: AsyncSession = Depends(get_db)) -> dict:
    return await admin_service.overview(db)


@router.get("/candidates")
async def candidates(db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await admin_service.candidates(db)


@router.get("/coverage")
async def coverage(db: AsyncSession = Depends(get_db)) -> dict:
    return await admin_service.coverage(db)


@router.get("/quality")
async def quality(db: AsyncSession = Depends(get_db)) -> dict:
    return await admin_service.quality(db)


@router.get("/agent/sessions")
async def agent_sessions(db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await admin_service.agent_sessions(db)


@router.post("/agent/sessions/{session_id}/annotate")
async def annotate_session(
    session_id: str,
    payload: AnnotateRequest,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    if not await agent_service.annotate_session(db, session_id, payload.label):
        raise HTTPException(status_code=404, detail="session not found")
    await auth_service.audit(
        db,
        user=user,
        action="agent.session_annotate",
        target=session_id,
        detail={"label": payload.label},
        ip=request_ip(request),
    )
    return {"ok": True, "session_id": session_id, "label": payload.label}


@router.get("/runs")
async def runs(db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await admin_service.list_runs(db)


@router.get("/tasks")
async def tasks(db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await admin_service.list_tasks(db)


@router.post("/tasks/{task_id}/run")
async def run_task(
    task_id: int,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    job_id = await admin_service.run_task_now(db, task_id)
    if job_id is None:
        raise HTTPException(status_code=404, detail="task not found")
    await auth_service.audit(
        db,
        user=user,
        action="task.run",
        target=str(task_id),
        detail={"job_id": job_id},
        ip=request_ip(request),
    )
    return {"ok": True, "job_id": job_id}


@router.get("/settings", response_model=AdminSettings)
async def get_settings(db: AsyncSession = Depends(get_db)) -> dict:
    return await admin_service.get_admin_settings(db)


@router.put("/settings", response_model=AdminSettings)
async def update_settings(
    payload: AdminSettings,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    current = await admin_service.get_admin_settings(db)
    value = await admin_service.update_admin_settings(
        db, {**current, **payload.model_dump(exclude_unset=True)}
    )
    await auth_service.audit(
        db,
        user=user,
        action="settings.update",
        target="admin_settings",
        detail=value,
        ip=request_ip(request),
    )
    return value


@router.get("/audit")
async def audit_logs(limit: int = 100, db: AsyncSession = Depends(get_db)) -> list[dict]:
    return await auth_service.list_audit(db, limit)


@router.post("/jobs/analysis", response_model=JobOut)
async def enqueue_analysis(
    payload: AnalysisRequest,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    job = await admin_service.enqueue_analysis(db, payload.listingIds)
    if job is None:
        raise HTTPException(status_code=400, detail="no task available")
    await auth_service.audit(
        db,
        user=user,
        action="job.analysis",
        target=job["id"],
        detail={"listing_ids": payload.listingIds},
        ip=request_ip(request),
    )
    return job


@router.post("/jobs/sampling", response_model=JobOut)
async def enqueue_sampling(
    payload: SamplingRequest,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    job = await admin_service.enqueue_sampling(
        db,
        origin=payload.origin,
        count=payload.count,
        buckets=payload.buckets,
        modes=payload.modes,
    )
    if job is None:
        raise HTTPException(status_code=400, detail="no task available")
    await auth_service.audit(
        db,
        user=user,
        action="job.sampling",
        target=job["id"],
        detail={"count": payload.count, "buckets": payload.buckets},
        ip=request_ip(request),
    )
    return job


@router.post("/jobs/geocode", response_model=JobOut)
async def enqueue_geocode(
    payload: GeocodeRequest,
    request: Request,
    user: User = Depends(require_admin),
    db: AsyncSession = Depends(get_db),
) -> dict:
    job = await admin_service.enqueue_geocode(db, payload.communityIds)
    if job is None:
        raise HTTPException(status_code=400, detail="no task available")
    await auth_service.audit(
        db,
        user=user,
        action="job.geocode",
        target=job["id"],
        detail={"community_ids": payload.communityIds},
        ip=request_ip(request),
    )
    return job
