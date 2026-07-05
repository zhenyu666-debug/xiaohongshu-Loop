"""Task management + manual trigger.

All endpoints are tenant-scoped.
"""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import Principal, current_principal, record_audit
from app.db.session import get_session, session_scope
from app.models import Account, Task
from app.scheduler import reload_all_tasks
from app.scheduler.runner import run_task_once
from app.schemas import TaskCreate, TaskOut

router = APIRouter(prefix="/api/tasks", tags=["tasks"])


async def _ensure_accounts_in_tenant(session: AsyncSession, tenant_id: str, account_ids: list[str]) -> None:
    if not account_ids:
        return
    rows = (
        await session.execute(
            select(Account).where(Account.id.in_(account_ids), Account.tenant_id == tenant_id)
        )
    ).scalars().all()
    found = {a.id for a in rows}
    missing = [a for a in account_ids if a not in found]
    if missing:
        raise HTTPException(400, f"accounts not in tenant: {missing}")


@router.get("", response_model=list[TaskOut])
async def list_tasks(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[Task]:
    res = await session.execute(
        select(Task).where(Task.tenant_id == principal.tenant.id).order_by(Task.created_at.desc())
    )
    return list(res.scalars())


@router.post("", response_model=TaskOut, status_code=201)
async def create_task(
    payload: TaskCreate,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> Task:
    await _ensure_accounts_in_tenant(session, principal.tenant.id, payload.account_ids)
    task = Task(tenant_id=principal.tenant.id, **payload.model_dump())
    session.add(task)
    await record_audit(session, principal, action="task.create", resource="task", resource_id=None,
                      payload={"name": payload.name})
    await session.commit()
    await session.refresh(task)
    await reload_all_tasks()
    return task


@router.delete("/{task_id}", status_code=204)
async def delete_task(
    task_id: int,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> None:
    task = await session.get(Task, task_id)
    if not task or task.tenant_id != principal.tenant.id:
        raise HTTPException(404, "not found")
    await session.delete(task)
    await record_audit(session, principal, action="task.delete", resource="task", resource_id=str(task_id))
    await session.commit()
    await reload_all_tasks()


@router.post("/{task_id}/run")
async def run_now(
    task_id: int,
    principal: Principal = Depends(current_principal),
    background: BackgroundTasks = BackgroundTasks(),
) -> dict:
    async def _go() -> None:
        async with session_scope() as session:
            task = await session.get(Task, task_id)
            if task and task.tenant_id == principal.tenant.id:
                await run_task_once(session, task)

    background.add_task(_go)
    return {"status": "queued", "task_id": task_id}


@router.post("/{task_id}/activate")
async def activate(
    task_id: int,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    task = await session.get(Task, task_id)
    if not task or task.tenant_id != principal.tenant.id:
        raise HTTPException(404, "not found")
    task.status = "active"
    task.next_run_at = datetime.utcnow()
    await record_audit(session, principal, action="task.activate", resource="task", resource_id=str(task_id))
    await session.commit()
    await reload_all_tasks()
    return {"status": "active", "task_id": task_id}


@router.post("/{task_id}/pause")
async def pause(
    task_id: int,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> dict:
    task = await session.get(Task, task_id)
    if not task or task.tenant_id != principal.tenant.id:
        raise HTTPException(404, "not found")
    task.status = "paused"
    await record_audit(session, principal, action="task.pause", resource="task", resource_id=str(task_id))
    await session.commit()
    await reload_all_tasks()
    return {"status": "paused", "task_id": task_id}