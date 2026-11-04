import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, request_ip
from app.core.db import SessionLocal, get_db
from app.models import Listing, ListingStatus, User
from app.schemas.agent import AgentRequest, ChatSessionOut, MonitorCreate, SavedMonitorOut
from app.services import agent_service, auth_service
from app.services.settings_service import get_commute_destination

router = APIRouter(
    prefix="/api/agent",
    tags=["agent"],
    dependencies=[Depends(get_current_user)],
)


@router.get("/settings")
async def agent_settings(db: AsyncSession = Depends(get_db)) -> dict:
    return {"commute_destination": await get_commute_destination(db)}


@router.post("/messages/stream")
async def stream_messages(
    payload: AgentRequest, user: User = Depends(get_current_user)
) -> StreamingResponse:
    async def event_stream():
        async with SessionLocal() as db:
            try:
                async for event in agent_service.stream(
                    db, payload.sessionId, payload.message, user_id=user.id
                ):
                    yield f"data: {json.dumps(event, ensure_ascii=False, default=str)}\n\n"
            except Exception as exc:
                error = {"type": "error", "message": f"{type(exc).__name__}: {exc}"[:200]}
                yield f"data: {json.dumps(error, ensure_ascii=False)}\n\n"
                yield 'data: {"type":"done"}\n\n'

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.get("/sessions", response_model=list[ChatSessionOut])
async def list_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await agent_service.list_chat_sessions(db, user.id)


@router.get("/stats")
async def stats(db: AsyncSession = Depends(get_db)) -> dict:
    listings = int(await db.scalar(select(func.count()).select_from(Listing)) or 0)
    active = int(
        await db.scalar(
            select(func.count())
            .select_from(Listing)
            .where(Listing.status == ListingStatus.active)
        )
        or 0
    )
    scored = int(
        await db.scalar(
            select(func.count()).select_from(Listing).where(Listing.score.is_not(None))
        )
        or 0
    )
    return {"listings": listings, "active": active, "scored": scored}


@router.get("/monitors", response_model=list[SavedMonitorOut])
async def list_monitors(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    return await agent_service.list_monitors(db, user.id)


@router.post("/monitors", response_model=SavedMonitorOut, status_code=201)
async def create_monitor(
    payload: MonitorCreate,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    monitor = await agent_service.create_monitor(
        db, payload.name, payload.conditions, user_id=user.id
    )
    await auth_service.audit(
        db,
        user=user,
        action="monitor.create",
        target=monitor["id"],
        detail={"name": payload.name, "conditions": payload.conditions},
        ip=request_ip(request),
    )
    return monitor


@router.delete("/monitors/{monitor_id}", status_code=204)
async def delete_monitor(
    monitor_id: str,
    request: Request,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    if not await agent_service.delete_monitor(
        db, monitor_id, user_id=user.id, is_admin=user.role == "admin"
    ):
        raise HTTPException(status_code=404, detail="monitor not found")
    await auth_service.audit(
        db,
        user=user,
        action="monitor.delete",
        target=monitor_id,
        ip=request_ip(request),
    )
