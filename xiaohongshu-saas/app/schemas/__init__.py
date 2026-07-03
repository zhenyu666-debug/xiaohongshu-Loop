"""Pydantic schemas for API I/O."""
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.core.types import AccountStage, PublishStatus, TaskKind, TaskStatus


# ---- Account ----

class AccountCreate(BaseModel):
    id: str
    channel: str = "xiaohongshu"
    nickname: str
    proxy: Optional[str] = None
    persona: Optional[str] = None
    enabled: bool = True


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    channel: str
    nickname: str
    stage: AccountStage
    proxy: Optional[str]
    cookie_path: Optional[str]
    persona: Optional[str]
    warmup_until: Optional[datetime]
    last_fail_at: Optional[datetime]
    fail_streak: int
    enabled: bool
    created_at: datetime


# ---- Content / Template ----

class TemplateSpec(BaseModel):
    key: str
    title_prefix: str
    body: str = ""
    topics: List[str] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)
    video: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


# ---- Task ----

class TaskCreate(BaseModel):
    name: str
    channel: str = "xiaohongshu"
    account_ids: List[str] = Field(default_factory=list)
    template_key: str
    kind: TaskKind = TaskKind.LOOP
    status: TaskStatus = TaskStatus.DRAFT
    cron: Optional[str] = None
    interval_minutes: Optional[int] = 60
    jitter_minutes: int = 15
    window_start: Optional[str] = "09:00"
    window_end: Optional[str] = "22:00"
    use_ai: bool = False
    ai_persona: Optional[str] = None


class TaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    channel: str
    account_ids: List[str]
    template_key: str
    kind: TaskKind
    status: TaskStatus
    cron: Optional[str]
    interval_minutes: Optional[int]
    jitter_minutes: int
    window_start: Optional[str]
    window_end: Optional[str]
    use_ai: bool
    ai_persona: Optional[str]
    next_run_at: Optional[datetime]
    last_run_at: Optional[datetime]
    created_at: datetime


# ---- Publish ----

class PublishOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_id: Optional[int]
    account_id: str
    channel: str
    status: PublishStatus
    external_id: Optional[str]
    url: Optional[str]
    title: Optional[str]
    error: Optional[str]
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    created_at: datetime


# ---- Dashboard ----

class DashboardSummary(BaseModel):
    accounts_total: int
    accounts_active: int
    tasks_active: int
    published_today: int
    failed_today: int
    skipped_today: int