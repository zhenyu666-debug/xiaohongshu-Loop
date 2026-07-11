"""Unit tests for scheduler runner's ai_mode dispatch (rewrite vs agent)."""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.types import ContentItem, PublishResult
from app.scheduler.runner import run_task_once


def _fake_account():
    return SimpleNamespace(
        id="acct-1",
        enabled=True,
        stage="normal",
        persona=None,
        warmup_until=None,
        last_fail_at=None,
        fail_streak=0,
    )


def _fake_task(use_ai: bool = True, ai_mode: str = "rewrite", persona: str | None = None):
    return SimpleNamespace(
        id=1,
        name="t",
        channel="xiaohongshu",
        account_ids=["acct-1"],
        template_key="demo",
        use_ai=use_ai,
        ai_mode=ai_mode,
        ai_persona=persona,
    )


def _fake_content():
    return ContentItem(
        title="原标题",
        body="原正文",
        images=[],
        topics=["#test"],
        extra={},
    )


@pytest.mark.asyncio
async def test_ai_mode_agent_dispatches_to_agent_rewrite(monkeypatch):
    """When ai_mode='agent', factory.agent_rewrite must be invoked."""
    session = AsyncMock(spec=AsyncSession)
    session.get = AsyncMock(return_value=_fake_account())

    # Patch both the risk module and the channel registry so the runner
    # never tries to talk to a real adapter.
    monkeypatch.setattr("app.scheduler.runner.risk_evaluate", AsyncMock(
        return_value=SimpleNamespace(allowed=True, reason="ok")
    ))
    publish_result = PublishResult(success=True, external_id="ext-1", url="https://x")
    fake_adapter = SimpleNamespace(publish=AsyncMock(return_value=publish_result))
    monkeypatch.setattr("app.scheduler.runner.registry.get", lambda ch: fake_adapter)

    content_after = _fake_content()
    called = {"agent": 0, "maybe": 0}

    async def fake_agent_rewrite(task, content, *, persona=None):
        called["agent"] += 1
        return content_after

    async def fake_maybe_rewrite(content, *, persona=None):
        called["maybe"] += 1
        return content

    monkeypatch.setattr("app.content_factory.factory.agent_rewrite", fake_agent_rewrite)
    monkeypatch.setattr("app.content_factory.factory.maybe_rewrite", fake_maybe_rewrite)
    monkeypatch.setattr("app.content_factory.factory.render", lambda tpl: _fake_content())
    monkeypatch.setattr("app.content_factory.factory.load_template", lambda key: SimpleNamespace(
        key=key, title_prefix="p", body="b", topics=[], images=[], video=None, extra={}
    ))

    task = _fake_task(use_ai=True, ai_mode="agent", persona="温柔学姐")
    await run_task_once(session, task)

    assert called["agent"] == 1, "ai_mode='agent' must invoke factory.agent_rewrite"
    assert called["maybe"] == 0, "ai_mode='agent' must NOT invoke factory.maybe_rewrite"


@pytest.mark.asyncio
async def test_ai_mode_rewrite_dispatches_to_maybe_rewrite(monkeypatch):
    """Default ai_mode='rewrite' must invoke factory.maybe_rewrite."""
    session = AsyncMock(spec=AsyncSession)
    session.get = AsyncMock(return_value=_fake_account())

    monkeypatch.setattr("app.scheduler.runner.risk_evaluate", AsyncMock(
        return_value=SimpleNamespace(allowed=True, reason="ok")
    ))
    publish_result = PublishResult(success=True, external_id="ext-1")
    fake_adapter = SimpleNamespace(publish=AsyncMock(return_value=publish_result))
    monkeypatch.setattr("app.scheduler.runner.registry.get", lambda ch: fake_adapter)

    called = {"agent": 0, "maybe": 0}

    async def fake_agent_rewrite(task, content, *, persona=None):
        called["agent"] += 1
        return content

    async def fake_maybe_rewrite(content, *, persona=None):
        called["maybe"] += 1
        return content

    monkeypatch.setattr("app.content_factory.factory.agent_rewrite", fake_agent_rewrite)
    monkeypatch.setattr("app.content_factory.factory.maybe_rewrite", fake_maybe_rewrite)
    monkeypatch.setattr("app.content_factory.factory.render", lambda tpl: _fake_content())
    monkeypatch.setattr("app.content_factory.factory.load_template", lambda key: SimpleNamespace(
        key=key, title_prefix="p", body="b", topics=[], images=[], video=None, extra={}
    ))

    task = _fake_task(use_ai=True, ai_mode="rewrite", persona="酷飒辣妹")
    await run_task_once(session, task)

    assert called["maybe"] == 1, "ai_mode='rewrite' must invoke factory.maybe_rewrite"
    assert called["agent"] == 0, "ai_mode='rewrite' must NOT invoke factory.agent_rewrite"


@pytest.mark.asyncio
async def test_use_ai_false_skips_both_rewrites(monkeypatch):
    """use_ai=False short-circuits both rewrite paths."""
    session = AsyncMock(spec=AsyncSession)
    session.get = AsyncMock(return_value=_fake_account())

    monkeypatch.setattr("app.scheduler.runner.risk_evaluate", AsyncMock(
        return_value=SimpleNamespace(allowed=True, reason="ok")
    ))
    publish_result = PublishResult(success=True, external_id="ext-1")
    fake_adapter = SimpleNamespace(publish=AsyncMock(return_value=publish_result))
    monkeypatch.setattr("app.scheduler.runner.registry.get", lambda ch: fake_adapter)

    called = {"agent": 0, "maybe": 0}

    async def fake_agent_rewrite(task, content, *, persona=None):
        called["agent"] += 1
        return content

    async def fake_maybe_rewrite(content, *, persona=None):
        called["maybe"] += 1
        return content

    monkeypatch.setattr("app.content_factory.factory.agent_rewrite", fake_agent_rewrite)
    monkeypatch.setattr("app.content_factory.factory.maybe_rewrite", fake_maybe_rewrite)
    monkeypatch.setattr("app.content_factory.factory.render", lambda tpl: _fake_content())
    monkeypatch.setattr("app.content_factory.factory.load_template", lambda key: SimpleNamespace(
        key=key, title_prefix="p", body="b", topics=[], images=[], video=None, extra={}
    ))

    task = _fake_task(use_ai=False, ai_mode="agent")  # even with agent mode
    await run_task_once(session, task)

    assert called["agent"] == 0, "use_ai=False must skip agent_rewrite"
    assert called["maybe"] == 0, "use_ai=False must skip maybe_rewrite"


@pytest.mark.asyncio
async def test_persona_propagates_to_factory_call(monkeypatch):
    """task.ai_persona must reach the factory function as the persona kwarg."""
    session = AsyncMock(spec=AsyncSession)
    session.get = AsyncMock(return_value=_fake_account())

    monkeypatch.setattr("app.scheduler.runner.risk_evaluate", AsyncMock(
        return_value=SimpleNamespace(allowed=True, reason="ok")
    ))
    publish_result = PublishResult(success=True, external_id="ext-1")
    fake_adapter = SimpleNamespace(publish=AsyncMock(return_value=publish_result))
    monkeypatch.setattr("app.scheduler.runner.registry.get", lambda ch: fake_adapter)

    seen = {}

    async def fake_agent_rewrite(task, content, *, persona=None):
        seen["persona"] = persona
        return content

    monkeypatch.setattr("app.content_factory.factory.agent_rewrite", fake_agent_rewrite)
    monkeypatch.setattr("app.content_factory.factory.render", lambda tpl: _fake_content())
    monkeypatch.setattr("app.content_factory.factory.load_template", lambda key: SimpleNamespace(
        key=key, title_prefix="p", body="b", topics=[], images=[], video=None, extra={}
    ))

    task = _fake_task(use_ai=True, ai_mode="agent", persona="学霸学姐，理性冷静")
    await run_task_once(session, task)

    assert seen.get("persona") == "学霸学姐，理性冷静", (
        f"task.ai_persona not propagated to agent_rewrite; got {seen.get('persona')!r}"
    )


@pytest.mark.asyncio
async def test_risk_block_records_skipped_publish_without_rewrite(monkeypatch):
    """When risk blocks the account, no rewrite must be attempted and the
    Publish row must be recorded with status=skipped."""
    session = AsyncMock(spec=AsyncSession)
    session.get = AsyncMock(return_value=_fake_account())

    monkeypatch.setattr("app.scheduler.runner.risk_evaluate", AsyncMock(
        return_value=SimpleNamespace(allowed=False, reason="cooldown")
    ))

    called = {"agent": 0, "maybe": 0, "publish": 0, "add": 0}

    async def fake_agent_rewrite(task, content, *, persona=None):
        called["agent"] += 1
        return content

    async def fake_maybe_rewrite(content, *, persona=None):
        called["maybe"] += 1
        return content

    class FakePublish:
        def __init__(self, **kwargs):
            for k, v in kwargs.items():
                setattr(self, k, v)

    def fake_add(row):
        called["add"] += 1
        # Verify status is SKIPPED
        if hasattr(row, "status"):
            assert row.status == "skipped", f"expected skipped, got {row.status}"

    monkeypatch.setattr("app.content_factory.factory.agent_rewrite", fake_agent_rewrite)
    monkeypatch.setattr("app.content_factory.factory.maybe_rewrite", fake_maybe_rewrite)
    monkeypatch.setattr("app.scheduler.runner.Publish", FakePublish)
    session.add = fake_add
    session.flush = AsyncMock()

    task = _fake_task(use_ai=True, ai_mode="agent")
    await run_task_once(session, task)

    assert called["agent"] == 0, "risk-blocked account must not trigger agent_rewrite"
    assert called["maybe"] == 0, "risk-blocked account must not trigger maybe_rewrite"
    assert called["add"] == 1, "expected exactly one skipped Publish row"