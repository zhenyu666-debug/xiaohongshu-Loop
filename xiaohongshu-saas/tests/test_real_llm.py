"""Smoke tests for real LLM providers (SiliconFlow / OpenAI-compatible).

These tests are SKIPPED when no API key is set, so they never block the
CI pipeline. To run them locally, set OPENAI_API_KEY and OPENAI_BASE_URL
in your .env file.

SiliconFlow free tier: 1M tokens/month, no credit card required.
Sign up at https://siliconflow.cn

Example .env values:
    OPENAI_API_KEY=<your SiliconFlow key>
    OPENAI_BASE_URL=https://api.siliconflow.cn/v1
    OPENAI_MODEL=Qwen/Qwen2.5-72B-Instruct
"""
from __future__ import annotations

from pathlib import Path

import pytest

# Re-load AISettings so OPENAI_BASE_URL is picked up from the caller.s .env
# (AISettings uses validation_alias=OPENAI_BASE_URL).
from app.ai.config import AISettings
from app.ai.llm import LLMClient, build_default_llm


def _has_real_key() -> bool:
    env_path = Path("xiaohongshu-saas") / ".env"
    if not env_path.exists():
        env_path = Path(".env")
    if not env_path.exists():
        return False
    try:
        ai_settings = AISettings(_env_file=str(env_path))
        return bool(ai_settings.openai_api_key)
    except Exception:
        return False


requires_real_key = pytest.mark.skipif(
    not _has_real_key(),
    reason="OPENAI_API_KEY not set in .env",
)


@requires_real_key
@pytest.mark.asyncio
async def test_llm_ainvoke():
    """Basic ainvoke via the configured OpenAI-compatible endpoint."""
    llm = build_default_llm()
    resp = await llm.ainvoke([
        {"role": "user", "content": "Reply with exactly one word: hello"},
    ])
    assert isinstance(resp.content, str)
    assert len(resp.content.strip()) > 0
    assert resp.model


@requires_real_key
@pytest.mark.asyncio
async def test_llm_stream():
    """Stream tokens and verify we get at least one chunk."""
    llm = build_default_llm()
    chunks = []
    async for chunk in llm.astream([
        {"role": "user", "content": "Count from 1 to 3 in words, separated by spaces: one two three"},
    ]):
        chunks.append(chunk)
    assert len(chunks) >= 1, f"expected at least 1 chunk, got {len(chunks)}"
    full = "".join(chunks)
    assert len(full) > 0


@requires_real_key
@pytest.mark.asyncio
async def test_content_agent_create_content():
    """End-to-end ContentAgent via the real LLM provider."""
    from app.ai.agents.content_agent import ContentAgent

    agent = ContentAgent()
    result = await agent.create_content(
        topic="周末露营攻略",
        style="casual",
        length="short",
    )
    assert "title" in result
    assert "body" in result
    assert len(result["body"]) > 10


@requires_real_key
@pytest.mark.asyncio
async def test_coordinator_smoke():
    """Smoke test: CoordinatorAgent.coordinate_task via the real LLM."""
    from app.ai.agents.coordinator import CoordinatorAgent

    coord = CoordinatorAgent()
    result = await coord.coordinate_task(
        task="写一篇关于夏天喝冷饮的小红书笔记",
        account_id="test",
    )
    assert isinstance(result, dict), f"expected dict, got {type(result)}"


@requires_real_key
@pytest.mark.asyncio
async def test_llm_client_respects_base_url():
    """Verify base_url from AISettings is passed through to ChatOpenAI."""
    env_path = Path("xiaohongshu-saas") / ".env"
    if not env_path.exists():
        env_path = Path(".env")
    ai_settings = AISettings(_env_file=str(env_path) if env_path.exists() else None)

    llm = LLMClient(provider="openai", api_key=ai_settings.openai_api_key)
    if ai_settings.openai_base_url != "https://api.openai.com/v1":
        assert llm.base_url == ai_settings.openai_base_url


@requires_real_key
@pytest.mark.asyncio
async def test_factory_agent_rewrite_smoke():
    """factory.agent_rewrite() calls CoordinatorAgent and returns a ContentItem."""
    from app.content_factory import factory
    from app.core.types import ContentItem
    from app.models.orm import Task

    content = ContentItem(
        title="测试标题",
        body="这是测试正文内容，用于验证 agent rewrite 功能是否正常工作。",
        images=[],
        topics=["测试"],
        extra={},
    )
    task = Task(
        id=999,
        name="test-task",
        channel="xiaohongshu",
        account_ids=["test-account"],
        template_key="demo",
        kind="once",
        use_ai=True,
        ai_mode="agent",
    )

    result = await factory.agent_rewrite(task, content)

    assert isinstance(result, ContentItem)
    assert result.title
    assert result.body