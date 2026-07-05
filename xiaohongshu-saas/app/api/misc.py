"""Templates + publishes + dashboard read endpoints (tenant-scoped)."""
from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.content_factory import factory
from app.core.auth import Principal, current_principal
from app.core.types import PublishStatus
from app.db.session import get_session
from app.models import Account, Publish, Task
from app.schemas import DashboardSummary, PublishOut

router = APIRouter(prefix="/api", tags=["misc"])


@router.get("/templates")
async def list_templates() -> dict:
    return {"templates": factory.list_templates()}


@router.get("/publishes", response_model=list[PublishOut])
async def list_publishes(
    limit: int = 50,
    account_id: str | None = None,
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> list[Publish]:
    stmt = (
        select(Publish)
        .where(Publish.tenant_id == principal.tenant.id)
        .order_by(Publish.id.desc())
        .limit(min(limit, 200))
    )
    if account_id:
        stmt = stmt.where(Publish.account_id == account_id)
    return list((await session.execute(stmt)).scalars())


@router.get("/dashboard/summary", response_model=DashboardSummary)
async def dashboard_summary(
    principal: Principal = Depends(current_principal),
    session: AsyncSession = Depends(get_session),
) -> DashboardSummary:
    today_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
    tid = principal.tenant.id

    accounts_total = await session.scalar(
        select(func.count(Account.id)).where(Account.tenant_id == tid)
    ) or 0
    accounts_active = await session.scalar(
        select(func.count(Account.id)).where(
            Account.tenant_id == tid,
            Account.enabled.is_(True),
            Account.stage != "banned",
        )
    ) or 0
    tasks_active = await session.scalar(
        select(func.count(Task.id)).where(Task.tenant_id == tid, Task.status == "active")
    ) or 0

    published_today = await session.scalar(
        select(func.count(Publish.id)).where(
            Publish.tenant_id == tid,
            Publish.status == PublishStatus.SUCCESS.value,
            Publish.created_at >= today_start,
        )
    ) or 0
    failed_today = await session.scalar(
        select(func.count(Publish.id)).where(
            Publish.tenant_id == tid,
            Publish.status == PublishStatus.FAILED.value,
            Publish.created_at >= today_start,
        )
    ) or 0
    skipped_today = await session.scalar(
        select(func.count(Publish.id)).where(
            Publish.tenant_id == tid,
            Publish.status == PublishStatus.SKIPPED.value,
            Publish.created_at >= today_start,
        )
    ) or 0

    return DashboardSummary(
        accounts_total=accounts_total,
        accounts_active=accounts_active,
        tasks_active=tasks_active,
        published_today=published_today,
        failed_today=failed_today,
        skipped_today=skipped_today,
    )


@router.get("/healthz")
async def api_healthz() -> dict:
    return {"status": "ok"}