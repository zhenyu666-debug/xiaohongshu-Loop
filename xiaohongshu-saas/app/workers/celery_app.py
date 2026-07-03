"""Celery app for distributed task execution."""
from __future__ import annotations

from celery import Celery

from app.core.config import settings

celery_app = Celery(
    "xhs_saas",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["app.workers.tasks"],
)

celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    timezone="Asia/Shanghai",
    enable_utc=False,
)