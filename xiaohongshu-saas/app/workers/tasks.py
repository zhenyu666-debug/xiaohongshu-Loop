"""Celery tasks."""
from __future__ import annotations

from app.core.logging import logger
from app.db.session import SessionLocal
from app.models import Task
from app.scheduler.runner import run_task_once
from app.workers.celery_app import celery_app


@celery_app.task(name="xhs.run_task", acks_late=True)
def run_task(task_id: int) -> dict:
    import asyncio

    async def _go() -> dict:
        async with SessionLocal() as session:
            task = await session.get(Task, task_id)
            if not task:
                logger.warning("celery: task {} missing", task_id)
                return {"task_id": task_id, "ok": False, "error": "not found"}
            publishes = await run_task_once(session, task)
            return {
                "task_id": task_id,
                "ok": True,
                "publishes": [
                    {"id": p.id, "status": p.status, "error": p.error} for p in publishes
                ],
            }

    return asyncio.run(_go())