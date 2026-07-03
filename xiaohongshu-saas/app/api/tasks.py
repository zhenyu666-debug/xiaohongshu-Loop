"""Task management + manual trigger."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_session, session_scope
from app.models import Task
from app.scheduler import reload_all_tasks
from app.scheduler.runner import run_task_once
from app.schemas import TaskCreate, TaskOut

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


@router.get("", response_model=list[TaskOut])
async def list_tasks(session: AsyncSession = Depends(get_session)) -> list[Task]:
    res = await session.execute(select(Task).order_by(Task.created_at.desc()))
    return list(res.scalars())


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(
    payload: TaskCreate,
    session: AsyncSession = Depends(get_session),
) -> Task:
    task = Task(**payload.model_dump())
    session.add(task)
    await session.commit()
    await session.refresh(task)
    await reload_all_tasks()
    return task


@router.delete("/{task_id}", status_code=204)
async def delete_task(task_id: int, session: AsyncSession = Depends(get_session)) -> None:
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(404, "not found")
    await session.delete(task)
    await session.commit()
    await reload_all_tasks()


@router.post("/{task_id}/run")
async def run_now(task_id: int, background: BackgroundTasks) -> dict:
    async def _go() -> None:
        async with session_scope() as session:
            task = await session.get(Task, task_id)
            if task:
                await run_task_once(session, task)

    background.add_task(_go)
    return {"status": "queued", "task_id": task_id}


@router.post("/{task_id}/activate")
async def activate(task_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(404, "not found")
    task.status = "active"
    task.next_run_at = datetime.utcnow()
    await session.commit()
    await reload_all_tasks()
    return {"status": "active", "task_id": task_id}


@router.post("/{task_id}/pause")
async def pause(task_id: int, session: AsyncSession = Depends(get_session)) -> dict:
    task = await session.get(Task, task_id)
    if not task:
        raise HTTPException(404, "not found")
    task.status = "paused"
    await session.commit()
    await reload_all_tasks()
    return {"status": "paused", "task_id": task_id}