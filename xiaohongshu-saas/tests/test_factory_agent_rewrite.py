"""Unit tests for factory.agent_rewrite covering the persona-injection and
analysis-only-fallback fixes.
"""
from __future__ import annotations

from unittest.mock import patch

import pytest

from app.content_factory import factory
from app.core.types import ContentItem
from app.models.orm import Task


def _make_task(ai_mode: str = "agent", persona: str | None = None) -> Task:
    return Task(
        id=1,
        name="t",
        channel="xiaohongshu",
        account_ids=["acct-1"],
        template_key="demo",
        kind="once",
        use_ai=True,
        ai_mode=ai_mode,
        ai_persona=persona,
    )


def _make_content() -> ContentItem:
    return ContentItem(
        title="秋日穿搭",
        body="分享三套日常通勤穿搭，简单干净。",
        images=[],
        topics=["#穿搭"],
        extra={"template": "demo"},
    )


def test_agent_rewrite_no_api_key_returns_content_unchanged(monkeypatch):
    """Without an API key the function must short-circuit and return the input."""
    monkeypatch.setattr(factory.settings, "openai_api_key", "")
    content = _make_content()
    out = factory.agent_rewrite(_make_task(), content, persona="温柔学姐")
    # Plain return, not a coroutine in the no-key branch
    import asyncio
    result = asyncio.run(out) if hasattr(out, "__await__") else out
    assert result.title == content.title
    assert result.body == content.body
    assert result.extra == content.extra


@pytest.mark.asyncio
async def test_agent_rewrite_injects_persona_into_prompt(monkeypatch):
    """Bug #1: persona must be propagated to the CoordinatorAgent task string."""
    monkeypatch.setattr(factory.settings, "openai_api_key", "test-key")

    captured = {}

    class FakeCoordinator:
        def __init__(self, *args, **kwargs):
            pass

        async def coordinate_task(self, *, task, account_id):
            captured["task"] = task
            captured["account_id"] = account_id
            return {"draft": {"title": "新", "body": "新文"}}

    from app.ai.agents import coordinator as coord_module
    with patch.object(coord_module, "CoordinatorAgent", FakeCoordinator):
        content = _make_content()
        result = await factory.agent_rewrite(
            _make_task(), content, persona="温柔学姐，喜欢日系穿搭"
        )

    assert "温柔学姐" in captured["task"], (
        f"persona not injected into coordinator task; got: {captured.get('task')!r}"
    )
    assert result.title == "新"
    assert result.body == "新文"


@pytest.mark.asyncio
async def test_agent_rewrite_uses_default_persona_when_none(monkeypatch):
    """When persona is None the default 人设 must still appear in the prompt."""
    monkeypatch.setattr(factory.settings, "openai_api_key", "test-key")

    captured = {}

    class FakeCoordinator:
        def __init__(self, *args, **kwargs):
            pass

        async def coordinate_task(self, *, task, account_id):
            captured["task"] = task
            return {"draft": {"title": "t", "body": "b"}}

    from app.ai.agents import coordinator as coord_module
    with patch.object(coord_module, "CoordinatorAgent", FakeCoordinator):
        content = _make_content()
        await factory.agent_rewrite(_make_task(persona=None), content)

    assert "人设" in captured["task"], (
        f"default persona marker missing from task: {captured.get('task')!r}"
    )


@pytest.mark.asyncio
async def test_agent_rewrite_falls_back_to_analysis_when_no_draft(monkeypatch):
    """Bug #2: when coordinator returns analysis-only, it must be preserved in
    ``extra['agent_analysis']`` instead of being silently dropped."""
    monkeypatch.setattr(factory.settings, "openai_api_key", "test-key")

    fake_analysis = {"score": 80, "recommendations": ["Add Q&A content"]}

    class FakeCoordinator:
        def __init__(self, *args, **kwargs):
            pass

        async def coordinate_task(self, *, task, account_id):
            return {"analysis": fake_analysis}

    from app.ai.agents import coordinator as coord_module
    with patch.object(coord_module, "CoordinatorAgent", FakeCoordinator):
        content = _make_content()
        result = await factory.agent_rewrite(_make_task(), content)

    # Original content preserved
    assert result.title == content.title
    assert result.body == content.body
    # Analysis surfaced via extra
    assert result.extra.get("agent_analysis") == fake_analysis
    # Original extra keys preserved
    assert result.extra.get("template") == "demo"


@pytest.mark.asyncio
async def test_agent_rewrite_returns_input_when_coordinator_returns_nothing(monkeypatch):
    """Coordinator returns an empty dict (no draft, no analysis): passthrough."""
    monkeypatch.setattr(factory.settings, "openai_api_key", "test-key")

    class FakeCoordinator:
        def __init__(self, *args, **kwargs):
            pass

        async def coordinate_task(self, *, task, account_id):
            return {}

    from app.ai.agents import coordinator as coord_module
    with patch.object(coord_module, "CoordinatorAgent", FakeCoordinator):
        content = _make_content()
        result = await factory.agent_rewrite(_make_task(), content)

    assert result.title == content.title
    assert result.body == content.body
    assert result.extra == content.extra


@pytest.mark.asyncio
async def test_agent_rewrite_swallows_coordinator_exception(monkeypatch):
    """A raising coordinator must not break the pipeline; input is returned."""
    monkeypatch.setattr(factory.settings, "openai_api_key", "test-key")

    class BrokenCoordinator:
        def __init__(self, *args, **kwargs):
            pass

        async def coordinate_task(self, *, task, account_id):
            raise RuntimeError("boom")

    from app.ai.agents import coordinator as coord_module
    with patch.object(coord_module, "CoordinatorAgent", BrokenCoordinator):
        content = _make_content()
        result = await factory.agent_rewrite(_make_task(), content)

    assert result.title == content.title
    assert result.body == content.body