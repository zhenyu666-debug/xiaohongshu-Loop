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
