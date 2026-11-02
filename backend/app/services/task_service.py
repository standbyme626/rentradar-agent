from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import City, Job, JobStatus, Run, Source, Task


def _task_dict(task: Task, city_code: str, source_code: str, last_run) -> dict:
    return {
        "id": task.id,
        "name": task.name,
        "city_code": city_code,
        "source_code": source_code,
        "enabled": task.enabled,
        "filters": task.filters or {},
        "schedule": task.schedule or {},
        "account_strategy": task.account_strategy,
        "proxy_strategy": task.proxy_strategy,
        "created_at": task.created_at,
        "last_run_status": last_run[0] if last_run else None,
        "last_run_at": last_run[1] if last_run else None,
    }


async def _last_run(db: AsyncSession, task_id: int):
    return (
        await db.execute(
            select(Run.status, Run.started_at)
            .where(Run.task_id == task_id)
            .order_by(Run.started_at.desc())
            .limit(1)
        )
    ).first()


async def list_tasks(db: AsyncSession) -> list[dict]:
    rows = (
        await db.execute(
            select(Task, City.code, Source.code)
            .join(City, Task.city_id == City.id)
            .join(Source, Task.source_id == Source.id)
            .order_by(Task.id.asc())
        )
    ).all()
    result = []
    for task, city_code, source_code in rows:
        result.append(_task_dict(task, city_code, source_code, await _last_run(db, task.id)))
    return result


async def create_task(db: AsyncSession, payload: dict) -> dict:
    city = await db.scalar(select(City).where(City.code == payload["city_code"]))
    source = await db.scalar(select(Source).where(Source.code == payload["source_code"]))
    if city is None:
        raise ValueError(f"unknown city: {payload['city_code']}")
    if source is None:
        raise ValueError(f"unknown source: {payload['source_code']}")
    task = Task(
        name=payload["name"],
        city_id=city.id,
        source_id=source.id,
        filters=payload.get("filters") or {},
        schedule=payload.get("schedule") or {"fast_minutes": 10, "slow_minutes": 180},
        account_strategy=payload.get("account_strategy") or "auto",
        proxy_strategy=payload.get("proxy_strategy") or "direct",
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    return _task_dict(task, city.code, source.code, None)


async def update_task(db: AsyncSession, task_id: int, payload: dict) -> dict | None:
    task = await db.get(Task, task_id)
    if task is None:
        return None
    for field in ("name", "enabled", "filters", "schedule", "account_strategy", "proxy_strategy"):
        value = payload.get(field)
        if value is not None:
            setattr(task, field, value)
    await db.commit()
    await db.refresh(task)
    city = await db.get(City, task.city_id)
    source = await db.get(Source, task.source_id)
    return _task_dict(task, city.code, source.code, await _last_run(db, task.id))


async def run_task_now(db: AsyncSession, task_id: int) -> int | None:
    task = await db.get(Task, task_id)
    if task is None:
        return None
    job = Job(
        task_id=task.id,
        type="crawl_list",
        payload={"mode": "manual", "task_id": task.id},
        status=JobStatus.queued,
    )
    db.add(job)
    await db.commit()
    await db.refresh(job)
    return job.id
