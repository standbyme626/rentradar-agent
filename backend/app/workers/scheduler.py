import argparse
import asyncio
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import func, select

from app.core.db import SessionLocal
from app.core.logging import configure_logging, get_logger
from app.models import AgentMonitor, Job, JobStatus, Run, Task
from app.services.settings_service import get_admin_settings

configure_logging()
log = get_logger("scheduler")
TZ = ZoneInfo("Asia/Shanghai")


async def _enqueue(db, task: Task, job_type: str, interval_minutes: int, payload: dict):
    latest = await db.scalar(
        select(func.max(Job.created_at)).where(Job.task_id == task.id, Job.type == job_type)
    )
    if latest is not None:
        if latest.tzinfo is None:
            latest = latest.replace(tzinfo=UTC)
        if datetime.now(UTC) - latest < timedelta(minutes=max(1, interval_minutes)):
            return None
    active = await db.scalar(
        select(func.count())
        .select_from(Job)
        .where(
            Job.task_id == task.id,
            Job.type == job_type,
            Job.status.in_([JobStatus.queued, JobStatus.running]),
        )
    )
    if active:
        return None
    job = Job(task_id=task.id, type=job_type, payload=payload, status=JobStatus.queued)
    db.add(job)
    await db.flush()
    return job.id


async def _recent_failures(db, task: Task) -> bool:
    statuses = (
        (
            await db.execute(
                select(Run.status)
                .where(Run.task_id == task.id)
                .order_by(Run.started_at.desc())
                .limit(3)
            )
        )
        .scalars()
        .all()
    )
    return len(statuses) == 3 and all(item == "failed" for item in statuses)


async def tick() -> dict:
    created: dict[str, int] = {}
    async with SessionLocal() as db:
        admin_settings = await get_admin_settings(db)
        tasks = (
            (await db.execute(select(Task).where(Task.enabled.is_(True)).order_by(Task.id)))
            .scalars()
            .all()
        )
        for task in tasks:
            if await _recent_failures(db, task):
                log.warning("task_circuit_open", task_id=task.id)
                continue
            filters = task.filters or {}
            schedule = task.schedule or {}
            fast = int(schedule.get("fast_minutes", 10))
            slow = int(schedule.get("slow_minutes", 180))
            district = str(filters.get("district") or "")
            line = str(filters.get("line") or "")
            fast_pages = int(filters.get("fast_pages", 1))
            slow_pages = int(filters.get("slow_pages", 6))
            fast_id = await _enqueue(
                db,
                task,
                "crawl_fast",
                fast,
                {
                    "pages": fast_pages,
                    "sort": "newest",
                    "district": district,
                    "line": line,
                    "full_scan": False,
                    "notify": True,
                },
            )
            slow_id = await _enqueue(
                db,
                task,
                "crawl_slow",
                slow,
                {
                    "pages": slow_pages,
                    "sort": "newest",
                    "district": district,
                    "line": line,
                    "full_scan": True,
                    "notify": False,
                },
            )
            if fast_id:
                created[f"fast_{task.id}"] = fast_id
            if slow_id:
                created[f"slow_{task.id}"] = slow_id

        now = datetime.now(TZ)
        if admin_settings.get("digest", True) and 9 <= now.hour < 10:
            day_start = now.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(UTC)
            existing = await db.scalar(
                select(func.count())
                .select_from(Job)
                .where(Job.type == "digest", Job.created_at >= day_start)
            )
            if not existing:
                job = Job(
                    task_id=None,
                    type="digest",
                    payload={"date": now.date().isoformat()},
                    status=JobStatus.queued,
                )
                db.add(job)
                await db.flush()
                created["digest"] = job.id

        monitor_count = int(
            await db.scalar(select(func.count()).select_from(AgentMonitor)) or 0
        )
        if admin_settings.get("monitorPush", True) and monitor_count:
            active = await db.scalar(
                select(func.count())
                .select_from(Job)
                .where(
                    Job.type == "monitor_match",
                    Job.status.in_([JobStatus.queued, JobStatus.running]),
                )
            )
            latest = await db.scalar(
                select(func.max(Job.created_at)).where(Job.type == "monitor_match")
            )
            due = latest is None
            if latest is not None:
                if latest.tzinfo is None:
                    latest = latest.replace(tzinfo=UTC)
                due = datetime.now(UTC) - latest >= timedelta(minutes=5)
            if not active and due:
                job = Job(task_id=None, type="monitor_match", payload={})
                db.add(job)
                await db.flush()
                created["monitor_match"] = job.id
        await db.commit()
    if created:
        log.info("scheduler_enqueued", **created)
    return created


async def loop(interval: int = 60) -> None:
    while True:
        try:
            await tick()
        except Exception as exc:
            log.error("scheduler_error", error=str(exc)[:400])
        await asyncio.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(prog="rentradar-scheduler")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--interval", type=int, default=60)
    args = parser.parse_args()
    if args.once:
        asyncio.run(tick())
    else:
        asyncio.run(loop(args.interval))


if __name__ == "__main__":
    main()
