"""APScheduler-based local scheduler.

For production / multi-worker deployments swap to Celery beat (see ``app/workers``).
This in-process scheduler is convenient for single-node dev / small fleets.
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, time, timedelta
from typing import Optional

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from sqlalchemy import select

from app.core.logging import logger
from app.db.session import SessionLocal
from app.models import Task
from app.scheduler.runner import run_task_once


_scheduler: Optional[AsyncIOScheduler] = None


def get_scheduler() -> Optional[AsyncIOScheduler]:
    """Return the current global scheduler, or None if not started."""
    return _scheduler


async def _tick_task(task_id: int) -> None:
    async with SessionLocal() as session:
        task = await session.get(Task, task_id)
        if not task:
            logger.warning("scheduler: task {} vanished", task_id)
            return
        if task.status != "active":
            logger.debug("scheduler: task {} not active, skip", task_id)
            return
        logger.info("scheduler: running task {} ({})", task.id, task.name)
        try:
            await run_task_once(session, task)
        except Exception:
            logger.exception("scheduler: task {} failed", task_id)


async def reload_all_tasks() -> None:
    """Re-read tasks from DB and (re)schedule them."""
    assert _scheduler is not None
    async with SessionLocal() as session:
        result = await session.execute(select(Task).where(Task.status == "active"))
        tasks = list(result.scalars())

    # Remove existing jobs and reschedule
    for job in list(_scheduler.get_jobs()):
        _scheduler.remove_job(job.id)

    for task in tasks:
        _scheduler.add_job(
            _tick_task,
            trigger=_trigger_for(task),
            args=[task.id],
            id=f"task-{task.id}",
            jitter=timedelta(minutes=task.jitter_minutes),
            max_instances=1,
            coalesce=True,
            replace_existing=True,
            next_run_time=_initial_run(task),
        )
    logger.info("scheduler: {} active task(s) loaded", len(tasks))


def _trigger_for(task: Task):
    if task.kind == "loop" and task.interval_minutes:
        return IntervalTrigger(minutes=task.interval_minutes)
    if task.kind == "schedule" and task.cron:
        return CronTrigger.from_crontab(task.cron)
    # one-shot
    return IntervalTrigger(minutes=10**9)


def _initial_run(task: Task) -> datetime:
    """Apply window/jitter to compute first run time."""
    now = datetime.now()
    start = _parse_time(task.window_start) if task.window_start else time(0, 0)
    end = _parse_time(task.window_end) if task.window_end else time(23, 59)
    base = now
    if not (start <= base.time() <= end):
        base = base.replace(hour=start.hour, minute=start.minute, second=0, microsecond=0)
        if base <= now:
            base = base + timedelta(days=1)
    jitter = timedelta(minutes=random.randint(0, task.jitter_minutes))
    return base + jitter


def _parse_time(s: str) -> time:
    hh, mm = s.split(":")
    return time(int(hh), int(mm))


def start_scheduler() -> AsyncIOScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    _scheduler = AsyncIOScheduler(timezone="Asia/Shanghai")
    _scheduler.start()
    # fire-and-forget reload
    asyncio.create_task(reload_all_tasks())
    return _scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler:
        _scheduler.shutdown(wait=False)
        _scheduler = None