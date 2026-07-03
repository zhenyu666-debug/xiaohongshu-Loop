"""Unit tests for risk control logic."""
from __future__ import annotations

from datetime import datetime, timedelta

import pytest

from app.core.config import settings
from app.core.risk import evaluate
from app.models import Account


pytestmark = pytest.mark.asyncio


class _StubSession:
    """Tiny async-session stub: ``execute(select(...))`` -> scalar integer."""

    def __init__(self, daily: int = 0, hourly: int = 0) -> None:
        self.daily = daily
        self.hourly = hourly
        self.calls = 0

    async def execute(self, stmt):  # pragma: no cover - very minimal
        class _R:
            def __init__(_self, owner):
                _self.owner = owner

            def scalar(_self):
                _self.owner.calls += 1
                return _self.owner.daily if _self.owner.calls == 1 else _self.owner.hourly

        return _R(self)


def _acc(**kw) -> Account:
    base = dict(id="a", channel="xhs", nickname="a", stage="normal", enabled=True)
    base.update(kw)
    return Account(**base)


async def test_allows_when_under_quota():
    acc = _acc()
    v = await evaluate(_StubSession(daily=0, hourly=0), acc)
    assert v.allowed


async def test_blocks_daily_quota():
    acc = _acc()
    v = await evaluate(
        _StubSession(daily=settings.daily_post_limit_per_account, hourly=0),
        acc,
    )
    assert not v.allowed and "daily" in v.reason


async def test_blocks_hourly_quota():
    acc = _acc()
    v = await evaluate(
        _StubSession(daily=0, hourly=settings.hourly_post_limit_per_account),
        acc,
    )
    assert not v.allowed and "hourly" in v.reason


async def test_blocks_warmup():
    acc = _acc(
        stage="warmup",
        warmup_until=datetime.utcnow() + timedelta(hours=12),
    )
    v = await evaluate(_StubSession(), acc)
    assert not v.allowed and "warmup" in v.reason


async def test_blocks_cooldown_after_failure():
    acc = _acc(
        last_fail_at=datetime.utcnow() - timedelta(minutes=5),
        fail_streak=1,
    )
    v = await evaluate(_StubSession(), acc)
    assert not v.allowed and "cooldown" in v.reason


async def test_blocks_disabled():
    acc = _acc(enabled=False)
    v = await evaluate(_StubSession(), acc)
    assert not v.allowed and "disabled" in v.reason


async def test_blocks_banned():
    acc = _acc(stage="banned")
    v = await evaluate(_StubSession(), acc)
    assert not v.allowed and "banned" in v.reason