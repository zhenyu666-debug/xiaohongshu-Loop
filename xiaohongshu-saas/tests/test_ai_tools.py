"""Tests for tools module."""
import pytest
from app.ai.tools.base import ToolDefinition, ToolResult
from app.ai.tools.registry import ToolRegistry
from app.ai.tools.content_tools import (
    GenerateTitleTool, GenerateBodyTool, SuggestHashtagsTool,
)
from app.ai.tools.search_tools import (
    SearchTrendingTool, SearchContentIdeasTool,
)
from app.ai.tools.scheduler_tools import (
    SchedulePostTool, GetAccountStatsTool, AnalyzeEngagementTool,
)


def test_tool_definition_creation():
    defn = ToolDefinition(name="test_tool", description="Test", parameters={})
    assert defn.name == "test_tool"


def test_tool_definition_openai_format():
    defn = ToolDefinition(name="t", description="d", parameters={"properties": {}, "required": []})
    schema = defn.to_openai_format()
    assert schema["type"] == "function"


@pytest.mark.asyncio
async def test_generate_title_tool():
    tool = GenerateTitleTool()
    result = await tool.execute(topic="AI")
    assert result.success
    assert "titles" in result.data


@pytest.mark.asyncio
async def test_generate_body_tool():
    tool = GenerateBodyTool()
    result = await tool.execute(topic="AI", style="casual", length="short")
    assert result.success
    assert "body" in result.data


@pytest.mark.asyncio
async def test_suggest_hashtags_tool():
    tool = SuggestHashtagsTool()
    result = await tool.execute(content="AI content", topic="AI")
    assert result.success
    assert "hashtags" in result.data


@pytest.mark.asyncio
async def test_search_trending_tool():
    tool = SearchTrendingTool()
    result = await tool.execute(category="general")
    assert result.success


@pytest.mark.asyncio
async def test_search_content_ideas_tool():
    tool = SearchContentIdeasTool()
    result = await tool.execute(topic="AI")
    assert result.success


@pytest.mark.asyncio
async def test_schedule_post_tool():
    tool = SchedulePostTool()
    result = await tool.execute(
        account_id="acc1", content={"title": "Test"}, scheduled_time="2024-12-31T10:00:00"
    )
    assert result.success


@pytest.mark.asyncio
async def test_get_account_stats_tool():
    tool = GetAccountStatsTool()
    result = await tool.execute(account_id="acc1")
    assert result.success
    assert result.data["account_id"] == "acc1"


@pytest.mark.asyncio
async def test_analyze_engagement_tool():
    tool = AnalyzeEngagementTool()
    result = await tool.execute(post_id="post1")
    assert result.success
    assert "engagement_score" in result.data


def test_tool_registry_register():
    registry = ToolRegistry()
    registry.register(GenerateTitleTool())
    assert registry.get("generate_title") is not None


@pytest.mark.asyncio
async def test_tool_registry_execute():
    registry = ToolRegistry()
    registry.register(GenerateTitleTool())
    result = await registry.execute("generate_title", topic="AI")
    assert result.success


@pytest.mark.asyncio
async def test_tool_registry_execute_unknown():
    registry = ToolRegistry()
    result = await registry.execute("unknown_tool")
    assert not result.success


def test_tool_registry_list():
    registry = ToolRegistry()
    registry.register(GenerateTitleTool())
    registry.register(GenerateBodyTool())
    tools = registry.list_tools()
    assert len(tools) == 2


def test_register_function():
    registry = ToolRegistry()
    def double(x):
        return x * 2
    registry.register_function("double", double, "Double a number")
    assert registry.get_function("double") is double


@pytest.mark.asyncio
async def test_execute_function():
    registry = ToolRegistry()
    def double(x):
        return x * 2
    registry.register_function("double", double, "Double a number")
    result = await registry.execute("double", x=5)
    assert result.success
    assert result.data == 10


@pytest.mark.asyncio
async def test_schedule_post_tool_returns_task_id():
    """The tool must always return a task_id, even when APScheduler is unreachable."""
    tool = SchedulePostTool()
    result = await tool.execute(
        account_id="acc1",
        content={"title": "T"},
        scheduled_time="2099-01-01T00:00:00",
    )
    assert result.success
    assert "task_id" in result.data
    assert result.data["status"] == "scheduled"


@pytest.mark.asyncio
async def test_search_trending_tool_returns_static_by_default():
    tool = SearchTrendingTool()
    result = await tool.execute(category="general", count=3)
    assert result.success
    assert len(result.data["trending"]) == 3
    assert result.metadata["backend"] == "static"


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rate_limit_burst_then_throttle():
    """Calling a tool faster than the rate limit should produce rate_limited results."""
    registry = ToolRegistry(default_rate_per_minute=60.0, default_capacity=3.0)
    registry.register(GenerateTitleTool())
    # Capacity is 3, so 4th call in the same second should be throttled.
    results = []
    for _ in range(4):
        results.append(await registry.execute("generate_title", topic="AI"))
    successes = sum(1 for r in results if r.success)
    rate_limited = sum(1 for r in results if not r.success and r.metadata.get("reason") == "rate_limited")
    assert successes == 3
    assert rate_limited == 1
    # And the metadata carries retry_after and limit_per_minute
    throttled = next(r for r in results if not r.success)
    assert "retry_after" in throttled.metadata
    assert throttled.metadata["limit_per_minute"] == 60.0


@pytest.mark.asyncio
async def test_rate_limit_disabled_when_rate_zero():
    """Setting rate_per_minute=0 disables limiting for the tool."""
    registry = ToolRegistry()
    registry.register(GenerateTitleTool())
    registry.configure_rate_limit("generate_title", rate_per_minute=0)
    for _ in range(20):
        result = await registry.execute("generate_title", topic="AI")
        assert result.success


@pytest.mark.asyncio
async def test_rate_limit_refills_over_time():
    """After waiting for refill, more calls succeed."""
    import asyncio as _asyncio
    registry = ToolRegistry(default_rate_per_minute=600.0, default_capacity=2.0)
    registry.register(GenerateTitleTool())
    # Drain the bucket
    assert (await registry.execute("generate_title", topic="AI")).success
    assert (await registry.execute("generate_title", topic="AI")).success
    # Third should be rate-limited (within the same instant, refill is 10/s = 100ms/token)
    r3 = await registry.execute("generate_title", topic="AI")
    assert not r3.success
    assert r3.metadata["reason"] == "rate_limited"
    # Wait for a refill; capacity=2, rate=10/s -> 1 token back in 100ms
    await _asyncio.sleep(0.15)
    assert (await registry.execute("generate_title", topic="AI")).success


@pytest.mark.asyncio
async def test_disabled_tool_returns_error():
    registry = ToolRegistry()
    registry.register(GenerateTitleTool())
    registry.disable_tool("generate_title")
    result = await registry.execute("generate_title", topic="AI")
    assert not result.success
    assert result.metadata["reason"] == "disabled"
    # Re-enable
    registry.enable_tool("generate_title")
    result = await registry.execute("generate_title", topic="AI")
    assert result.success


@pytest.mark.asyncio
async def test_per_tool_rate_limits_are_isolated():
    """Limiting tool A must not affect tool B."""
    registry = ToolRegistry(default_rate_per_minute=60.0, default_capacity=1.0)
    registry.register(GenerateTitleTool())
    registry.register(GenerateBodyTool())
    # Drain title's bucket
    assert (await registry.execute("generate_title", topic="AI")).success
    r = await registry.execute("generate_title", topic="AI")
    assert r.metadata.get("reason") == "rate_limited"
    # body still has a fresh bucket
    assert (await registry.execute("generate_body", topic="AI", style="casual", length="short")).success


def test_rate_limit_exposed_on_registry():
    registry = ToolRegistry()
    assert registry.rate_limiter is not None
    registry.register(GenerateTitleTool())
    buckets = registry.rate_limiter.all_buckets()
    assert "generate_title" in buckets
