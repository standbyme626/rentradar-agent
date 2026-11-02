from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import require_admin
from app.core.db import get_db
from app.schemas import TaskCreate, TaskOut, TaskUpdate
from app.services import task_service

router = APIRouter(prefix="/api/tasks", tags=["tasks"], dependencies=[Depends(require_admin)])


@router.get("", response_model=list[TaskOut])
async def list_tasks(db: AsyncSession = Depends(get_db)) -> list[TaskOut]:
    return [TaskOut(**item) for item in await task_service.list_tasks(db)]


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(payload: TaskCreate, db: AsyncSession = Depends(get_db)) -> TaskOut:
    try:
        task = await task_service.create_task(db, payload.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TaskOut(**task)


@router.patch("/{task_id}", response_model=TaskOut)
async def update_task(
    task_id: int, payload: TaskUpdate, db: AsyncSession = Depends(get_db)
) -> TaskOut:
    task = await task_service.update_task(db, task_id, payload.model_dump(exclude_unset=True))
    if task is None:
        raise HTTPException(status_code=404, detail="task not found")
    return TaskOut(**task)


@router.post("/{task_id}/run")
async def run_task(task_id: int, db: AsyncSession = Depends(get_db)) -> dict:
    job_id = await task_service.run_task_now(db, task_id)
    if job_id is None:
        raise HTTPException(status_code=404, detail="task not found")
    return {"ok": True, "job_id": job_id}
