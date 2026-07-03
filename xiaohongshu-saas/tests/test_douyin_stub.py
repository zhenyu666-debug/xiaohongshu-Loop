"""The douyin adapter is currently a stub; ensure it raises on every call."""
from __future__ import annotations

import pytest

from app.channels.douyin.adapter import DouyinAdapter
from app.core.types import AccountHealth, ContentItem, PublishResult
from app.models import Account


def _stub_account() -> Account:
    return Account(id="acc_dy_001", channel="douyin", nickname="stub")


@pytest.mark.asyncio
async def test_login_raises():
    adapter = DouyinAdapter()
    with pytest.raises(NotImplementedError):
        await adapter.login(_stub_account())


@pytest.mark.asyncio
async def test_publish_raises():
    adapter = DouyinAdapter()
    content = ContentItem(title="t", body="b")
    with pytest.raises(NotImplementedError):
        await adapter.publish(_stub_account(), content)


@pytest.mark.asyncio
async def test_heartbeat_raises():
    adapter = DouyinAdapter()
    with pytest.raises(NotImplementedError):
        await adapter.heartbeat(_stub_account())


def test_cookie_path_helper_returns_under_data_cookies():
    adapter = DouyinAdapter()
    p = adapter.cookie_path_for("acc_dy_001")
    assert p.name == "acc_dy_001.json"
    assert "data/cookies" in str(p).replace("\\", "/")


def test_protocol_compliance():
    """The three required methods exist and are coroutines."""
    adapter = DouyinAdapter()
    assert adapter.name == "douyin"
    import inspect
    for method_name in ("login", "publish", "heartbeat"):
        fn = getattr(adapter, method_name)
        assert inspect.iscoroutinefunction(fn), f"{method_name} must be async"
    _ = PublishResult(success=False, error="probe")
    _ = AccountHealth(ok=False, cookies_valid=False, message="probe")