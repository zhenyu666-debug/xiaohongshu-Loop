"""Pydantic DTOs / shared value objects."""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AccountStage(str, Enum):
    NEW = "new"             # Just onboarded, needs warm-up
    WARMUP = "warmup"       # Posting only safe / low-risk content
    NORMAL = "normal"       # Full capability
    COOLING = "cooling"     # Recently failed, on cooldown
    BANNED = "banned"       # Disabled


class TaskKind(str, Enum):
    ONCE = "once"
    LOOP = "loop"
    SCHEDULE = "schedule"


class TaskStatus(str, Enum):
    DRAFT = "draft"
    ACTIVE = "active"
    PAUSED = "paused"
    DONE = "done"
    FAILED = "failed"


class PublishStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    SKIPPED = "skipped"     # skipped by risk control
    COOLDOWN = "cooldown"   # waiting for cooldown window


# ---- DTOs ----

class ContentItem(BaseModel):
    """A piece of content to be published."""
    title: str
    body: str = ""
    images: List[str] = Field(default_factory=list)
    video: Optional[str] = None
    topics: List[str] = Field(default_factory=list)
    mentions: List[str] = Field(default_factory=list)
    location: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class PublishResult(BaseModel):
    success: bool
    external_id: Optional[str] = None
    url: Optional[str] = None
    error: Optional[str] = None
    raw: Dict[str, Any] = Field(default_factory=dict)
    published_at: Optional[datetime] = None


class AccountHealth(BaseModel):
    ok: bool
    cookies_valid: bool
    message: str = ""