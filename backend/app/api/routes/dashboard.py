from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.core.db import get_db
from app.models import (
    Event,
    EventType,
    Job,
    JobStatus,
    Listing,
    ListingStatus,
    Run,
    Source,
    Task,
)
from app.schemas import DashboardOut, EventOut, SourceHealth

router = APIRouter(prefix="/api", tags=["dashboard"], dependencies=[Depends(get_current_user)])


@router.get("/dashboard", response_model=DashboardOut)
async def dashboard(db: AsyncSession = Depends(get_db)) -> DashboardOut:
    day_start = func.date_trunc("day", func.now())

    active_listings = await db.scalar(
        select(func.count()).select_from(Listing).where(Listing.status == ListingStatus.active)
    )
    new_today = await db.scalar(
        select(func.count()).select_from(Listing).where(Listing.first_seen_at >= day_start)
    )
    price_drops_today = await db.scalar(
        select(func.count())
        .select_from(Event)
        .where(Event.type == EventType.price_drop, Event.created_at >= day_start)
    )
    gone_today = await db.scalar(
        select(func.count())
        .select_from(Event)
        .where(Event.type == EventType.gone, Event.created_at >= day_start)
    )
    queued_jobs = await db.scalar(
        select(func.count()).select_from(Job).where(Job.status == JobStatus.queued)
    )

    sources = (await db.execute(select(Source).order_by(Source.id))).scalars().all()
    source_rows: list[SourceHealth] = []
    for source in sources:
        source_active = await db.scalar(
            select(func.count())
            .select_from(Listing)
            .where(Listing.source_id == source.id, Listing.status == ListingStatus.active)
        )
        source_queued = await db.scalar(
            select(func.count())
            .select_from(Job)
            .join(Task, Job.task_id == Task.id)
            .where(Task.source_id == source.id, Job.status == JobStatus.queued)
        )
        last_run = (
            await db.execute(
                select(Run.status, Run.started_at)
                .join(Task, Run.task_id == Task.id)
                .where(Task.source_id == source.id)
                .order_by(Run.started_at.desc())
                .limit(1)
            )
        ).first()
        source_rows.append(
            SourceHealth(
                id=source.id,
                code=source.code,
                name=source.name,
                enabled=source.enabled,
                active_listings=int(source_active or 0),
                queued_jobs=int(source_queued or 0),
                last_run_status=last_run[0] if last_run else None,
                last_run_at=last_run[1] if last_run else None,
            )
        )

    recent = (
        await db.execute(
            select(Event, Listing.title)
            .join(Listing, Event.listing_id == Listing.id, isouter=True)
            .order_by(Event.created_at.desc())
            .limit(8)
        )
    ).all()
    recent_events = [
        EventOut(
            id=event.id,
            type=event.type.value,
            listing_id=event.listing_id,
            listing_title=title,
            payload=event.payload,
            notified=event.notified,
            created_at=event.created_at,
        )
        for event, title in recent
    ]

    return DashboardOut(
        active_listings=int(active_listings or 0),
        new_today=int(new_today or 0),
        price_drops_today=int(price_drops_today or 0),
        gone_today=int(gone_today or 0),
        queued_jobs=int(queued_jobs or 0),
        sources=source_rows,
        recent_events=recent_events,
    )
