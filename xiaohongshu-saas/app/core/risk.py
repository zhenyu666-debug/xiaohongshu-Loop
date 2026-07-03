"""Risk-control checks: stage, quotas, cooldowns."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Optional

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.core.types import PublishStatus
from app.models import Account, Publish


@dataclass(slots=True)
class RiskVerdict:
    allowed: bool
    reason: str = ""
    cooldown_until: Optional[datetime] = None


async def evaluate(
    session: AsyncSession,
    account: Account,
    *,
    now: Optional[datetime] = None,
) -> RiskVerdict:
    """Run all risk checks for an account before publishing."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)

    if not account.enabled:
        return RiskVerdict(False, "account disabled")
    if account.stage == "banned":
        return RiskVerdict(False, "account is banned")

    # 1) cooldown after recent failure
    if account.last_fail_at and account.fail_streak > 0:
        minutes = settings.cool_down_minutes_after_fail * account.fail_streak
        until = account.last_fail_at + timedelta(minutes=minutes)
        if now < until:
            return RiskVerdict(False, f"cooldown until {until.isoformat()}", cooldown_until=until)

    # 2) warm-up window
    if account.warmup_until and now < account.warmup_until:
        return RiskVerdict(False, f"in warmup until {account.warmup_until.isoformat()}")

    # 3) daily / hourly quotas
    day_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    hour_start = now.replace(minute=0, second=0, microsecond=0)

    success_states: tuple = (PublishStatus.SUCCESS.value,)

    daily = await _count_publishes(session, account.id, day_start, now, success_states)
    if daily >= settings.daily_post_limit_per_account:
        return RiskVerdict(False, f"daily quota reached ({daily}/{settings.daily_post_limit_per_account})")

    hourly = await _count_publishes(session, account.id, hour_start, now, success_states)
    if hourly >= settings.hourly_post_limit_per_account:
        return RiskVerdict(False, f"hourly quota reached ({hourly}/{settings.hourly_post_limit_per_account})")

    return RiskVerdict(True, "ok")


async def _count_publishes(
    session: AsyncSession,
    account_id: str,
    since: datetime,
    until: datetime,
    statuses: Iterable[str],
) -> int:
    stmt = select(func.count(Publish.id)).where(
        and_(
            Publish.account_id == account_id,
            Publish.status.in_(tuple(statuses)),
            Publish.created_at >= since,
            Publish.created_at < until,
        )
    )
    res = await session.execute(stmt)
    return int(res.scalar() or 0)


async def mark_success(session: AsyncSession, account: Account) -> None:
    account.fail_streak = 0
    account.last_fail_at = None
    if account.stage in {"new", "warmup"}:
        account.stage = "normal"
    await session.flush()


async def mark_failure(session: AsyncSession, account: Account, reason: str) -> None:
    account.fail_streak = (account.fail_streak or 0) + 1
    account.last_fail_at = datetime.utcnow()
    if "banned" in reason.lower() or "封号" in reason:
        account.stage = "banned"
        account.enabled = False
    elif account.fail_streak >= 3:
        account.stage = "cooling"
    logger.warning("account {} failed (streak={}): {}", account.id, account.fail_streak, reason)
    await session.flush()