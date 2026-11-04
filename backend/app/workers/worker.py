import argparse
import asyncio
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.core.logging import configure_logging, get_logger
from app.models import Job, JobStatus, Listing, ListingStatus, Task
from app.services import monitor_service
from app.services.crawl_service import run_task
from app.services.digest_service import send_digest
from app.services.enrich_service import (
    enrich_communities,
    enrich_task,
    rescore_listings,
    rescore_task,
)
from app.services.settings_service import get_admin_settings

configure_logging()
log = get_logger("worker")


async def claim_job():
    async with SessionLocal() as db:
        job = await db.scalar(
            select(Job)
            .where(Job.status == JobStatus.queued, Job.run_after <= func.now())
            .order_by(Job.run_after)
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        if job is None:
            return None
        job.status = JobStatus.running
        job.locked_by = "rentradar-worker"
        job.locked_at = datetime.now(UTC)
        job.attempts += 1
        await db.commit()
        await db.refresh(job)
        return (
            job.id,
            job.task_id,
            dict(job.payload or {}),
            job.attempts,
            job.max_attempts,
            job.type,
        )


async def process_once() -> bool:
    claimed = await claim_job()
    if claimed is None:
        return False
    job_id, task_id, payload, attempts, max_attempts, job_type = claimed
    log.info("job_started", job_id=job_id, task_id=task_id, type=job_type, attempts=attempts)

    if job_type in {"digest", "monitor_match"}:
        async with SessionLocal() as db:
            try:
                if job_type == "digest":
                    result = await send_digest(db)
                else:
                    result = await monitor_service.process_monitors(db)
                job = await db.get(Job, job_id)
                job.status = JobStatus.done
                job.locked_at = None
                job.payload = {**payload, "result": result}
                await db.commit()
                log.info(f"{job_type}_done", job_id=job_id, result=result)
            except Exception as exc:
                await db.rollback()
                job = await db.get(Job, job_id)
                if job is not None:
                    job.status = JobStatus.failed
                    job.locked_at = None
                    await db.commit()
                log.error(f"{job_type}_failed", job_id=job_id, error=str(exc)[:400])
        return True

    async with SessionLocal() as db:
        task = await db.get(Task, task_id) if task_id else None
        if task is None:
            job = await db.get(Job, job_id)
            job.status = JobStatus.failed
            job.locked_at = None
            await db.commit()
            log.error("job_task_missing", job_id=job_id, task_id=task_id)
            return True

        try:
            filters = task.filters or {}
            if job_type == "enrich":
                enrich = await enrich_task(db, task, limit=int(payload.get("limit", 200)))
                rescore = await rescore_task(db, task)
                result = {"enrich": enrich, "rescore": rescore}
            elif job_type == "analysis":
                listing_ids = [int(item) for item in payload.get("listing_ids") or []]
                rescore = (
                    await rescore_listings(db, task, listing_ids)
                    if listing_ids
                    else await rescore_task(db, task)
                )
                result = {
                    "analysis": rescore,
                    "note": "Phase 2: local rescore only; detail/images/AI pending",
                }
            elif job_type == "geocode":
                settings = await get_admin_settings(db)
                cap = max(1, int(settings.get("batchCap") or 10))
                community_ids = [
                    int(item) for item in (payload.get("community_ids") or [])[:cap]
                ]
                enrich = await enrich_communities(db, community_ids)
                rescore = await rescore_task(db, task)
                result = {"geocode": enrich, "rescore": rescore}
            elif job_type == "sampling":
                settings = await get_admin_settings(db)
                cap = max(1, int(settings.get("batchCap") or 10))
                count = max(1, min(int(payload.get("count") or 10), cap))
                buckets = [str(item) for item in payload.get("buckets") or [] if str(item)]
                modes = [str(item) for item in payload.get("modes") or [] if str(item)]
                community_ids = (
                    await db.execute(
                        select(Listing.community_id)
                        .where(
                            Listing.status == ListingStatus.active,
                            Listing.community_id.is_not(None),
                        )
                        .group_by(Listing.community_id)
                        .order_by(func.count().desc())
                        .limit(count)
                    )
                ).scalars().all()
                enrich = await enrich_communities(
                    db, list(community_ids), buckets=buckets or None
                )
                rescore = await rescore_task(db, task)
                result = {
                    "sampling": enrich,
                    "rescore": rescore,
                    "buckets": buckets or [],
                    "modes": modes or ["公交/地铁"],
                    "note": (
                        "SZMC 为时刻表最短耗时，不含实时拥堵；"
                        "同一 OD 的 4 个时段结果相同。"
                        if "公交/地铁" in (modes or ["公交/地铁"])
                        else "仅支持公交/地铁（SZMC）；其他方式未采样。"
                    ),
                }
            else:
                result = await run_task(
                    db,
                    task,
                    pages=int(payload.get("pages", 1)),
                    sort=str(payload.get("sort") or filters.get("sort") or "newest"),
                    district=str(payload.get("district") or filters.get("district") or ""),
                    line=str(payload.get("line") or filters.get("line") or ""),
                    notify=bool(payload.get("notify", False)),
                    full_scan=bool(payload.get("full_scan", False)),
                )
            if job_type.startswith("crawl") and (
                int(result.get("new") or 0) or int(result.get("price_changes") or 0)
            ):
                active = await db.scalar(
                    select(func.count())
                    .select_from(Job)
                    .where(
                        Job.type == "monitor_match",
                        Job.status.in_([JobStatus.queued, JobStatus.running]),
                    )
                )
                if not active:
                    db.add(Job(task_id=None, type="monitor_match", payload={}))
            job = await db.get(Job, job_id)
            job.status = JobStatus.done
            job.locked_at = None
            job.payload = {**payload, "result": result}
            await db.commit()
            log.info("job_done", job_id=job_id, result=result)
        except Exception as exc:
            await db.rollback()
            job = await db.get(Job, job_id)
            if job is not None:
                if attempts < max_attempts:
                    job.status = JobStatus.queued
                    job.locked_at = None
                    job.run_after = datetime.now(UTC) + timedelta(minutes=5)
                else:
                    job.status = JobStatus.failed
                    job.locked_at = None
                await db.commit()
            log.error("job_failed", job_id=job_id, error=str(exc)[:400])
    return True


async def worker_loop(interval: int = 5) -> None:
    while True:
        try:
            worked = await process_once()
        except Exception as exc:
            log.error("worker_loop_error", error=str(exc)[:400])
            worked = False
        if not worked:
            await asyncio.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(prog="rentradar-worker")
    parser.add_argument("--once", action="store_true", help="process at most one job and exit")
    parser.add_argument("--interval", type=int, default=5)
    args = parser.parse_args()
    if args.once:
        asyncio.run(process_once())
    else:
        asyncio.run(worker_loop(args.interval))


if __name__ == "__main__":
    main()
