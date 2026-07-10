"""ORM models. A single declarative Base."""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, Boolean, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class Tenant(Base):
    """Workspace / customer boundary.

    Every `Account` / `Task` / `Content` / `Publish` is owned by exactly one
    tenant. The default tenant is seeded by `init_db` as `default` so the
    single-tenant deployment keeps working unchanged.
    """

    __tablename__ = "tenants"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    name: Mapped[str] = mapped_column(String(128))
    plan: Mapped[str] = mapped_column(String(16), default="free")  # free / pro / business
    status: Mapped[str] = mapped_column(String(16), default="active")  # active / suspended
    seat_limit: Mapped[int] = mapped_column(Integer, default=1)
    monthly_post_quota: Mapped[int] = mapped_column(Integer, default=500)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())

    billing: Mapped[Optional["BillingAccount"]] = relationship(back_populates="tenant", uselist=False)


class User(Base):
    """Login identity. A user may belong to multiple tenants via `Membership`."""

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(256), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(256))
    display_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    is_superadmin: Mapped[bool] = mapped_column(Boolean, default=False)
    status: Mapped[str] = mapped_column(String(16), default="active")  # active / disabled
    last_login_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    memberships: Mapped[list["Membership"]] = relationship(back_populates="user", cascade="all, delete-orphan")


class Membership(Base):
    """User <-> tenant link with a role inside that tenant."""

    __tablename__ = "memberships"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"))
    role: Mapped[str] = mapped_column(String(16), default="member")  # owner / admin / member / viewer
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    user: Mapped[User] = relationship(back_populates="memberships")
    tenant: Mapped[Tenant] = relationship()


class ApiToken(Base):
    """Long-lived bearer token used by SDKs / CLI. `prefix` is the searchable part."""

    __tablename__ = "api_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    name: Mapped[str] = mapped_column(String(128))
    prefix: Mapped[str] = mapped_column(String(16), index=True)  # first 8 chars
    token_hash: Mapped[str] = mapped_column(String(256))
    last_used_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    revoked: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())


class BillingAccount(Base):
    """Per-tenant usage counters for the quota system."""

    __tablename__ = "billing_accounts"

    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True)
    posts_this_month: Mapped[int] = mapped_column(Integer, default=0)
    period_start: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    last_reset_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    tenant: Mapped[Tenant] = relationship(back_populates="billing")


class AuditLog(Base):
    """Append-only log of mutating API calls for tenant audit trails."""

    __tablename__ = "audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[Optional[str]] = mapped_column(ForeignKey("tenants.id"), nullable=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    action: Mapped[str] = mapped_column(String(64), index=True)
    resource: Mapped[str] = mapped_column(String(64))
    resource_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), index=True)


class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, default="default")
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
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, default="default")
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
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, default="default")
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
    ai_mode: Mapped[str] = mapped_column(String(32), default="rewrite")  # rewrite | agent
    next_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_run_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now())


class Publish(Base):
    __tablename__ = "publishes"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    tenant_id: Mapped[str] = mapped_column(ForeignKey("tenants.id", ondelete="CASCADE"), index=True, default="default")
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