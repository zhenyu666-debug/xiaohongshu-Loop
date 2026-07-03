"""ORM models. A single declarative Base."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, Boolean, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    channel: Mapped[str] = mapped_column(String(32), index=True)   # xiaohongshu / douyin ...
    nickname: Mapped[str] = mapped_column(String(128))
    stage: Mapped[str] = mapped_column(String(16), default="new") # new / warmup / normal / cooling / banned
    proxy: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    cookie_path: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    persona: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON string for AI persona
    warmup_until: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_fail_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    fail_streak: Mapped[int] = mapped_column(Integer, default=0)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    contents: Mapped[list["Content"]] = relationship(back_populates="account")
    publishes: Mapped[list["Publish"]] = relationship(back_populates="account")


class Content(Base):
    __tablename__ = "contents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"))
    template_key: Mapped[str] = mapped_column(String(64))
    title: Mapped[str] = mapped_column(String(256))
    body: Mapped[str] = mapped_column(Text, default="")
    payload: Mapped[dict] = mapped_column(JSON, default=dict)  # topics/images/video/extra
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    account: Mapped[Account] = relationship(back_populates="contents")


class Task(Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(128))
    channel: Mapped[str] = mapped_column(String(32), index=True)
    account_ids: Mapped[list] = mapped_column(JSON, default=list)  # subset of accounts
    template_key: Mapped[str] = mapped_column(String(64))
    kind: Mapped[str] = mapped_column(String(16))  # once / loop / schedule
    status: Mapped[str] = mapped_column(String(16), default="draft")
    cron: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)        # for schedule
    interval_minutes: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)  # for loop
    jitter_minutes: Mapped[int] = mapped_column(Integer, default=15)
    window_start: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)  # "09:00"
    window_end: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)    # "22:00"
    use_ai: Mapped[bool] = mapped_column(Boolean, default=False)
    ai_persona: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Publish(Base):
    __tablename__ = "publishes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    task_id: Mapped[Optional[int]] = mapped_column(ForeignKey("tasks.id"), nullable=True)
    account_id: Mapped[str] = mapped_column(ForeignKey("accounts.id"), index=True)
    channel: Mapped[str] = mapped_column(String(32), index=True)
    status: Mapped[str] = mapped_column(String(16), default="pending")
    external_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    title: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    account: Mapped[Account] = relationship(back_populates="publishes")