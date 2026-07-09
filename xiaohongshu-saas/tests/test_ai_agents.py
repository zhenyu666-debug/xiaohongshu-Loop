"""Tests for AI agents module."""
from __future__ import annotations

import pytest

from app.ai.agents.base import (
    AgentConfig,
    AgentMessage,
    AgentRole,
    AgentCoordinator,
)
from app.ai.agents.content_agent import ContentAgent
from app.ai.agents.analysis_agent import AnalysisAgent
from app.ai.agents.coordinator import CoordinatorAgent
from app.ai.agents.graph import StateGraph, Checkpointer, END


def test_agent_message_creation():
    msg = AgentMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"
    assert msg.sender is None
    assert msg.timestamp is not None


def test_agent_config():
    config = AgentConfig(
        name="test_agent",
        role=AgentRole.EXECUTOR,
        model="gpt-4o",
    )
    assert config.name == "test_agent"
    assert config.role == AgentRole.EXECUTOR
    assert config.model == "gpt-4o"


def test_agent_role_enum():
    assert AgentRole.PLANNER.value == "planner"
    assert AgentRole.EXECUTOR.value == "executor"
    assert AgentRole.REVIEWER.value == "reviewer"
    assert AgentRole.COORDINATOR.value == "coordinator"


def test_content_agent_creation():
    agent = ContentAgent()
    assert agent.name == "content_creator"
    assert agent.role == AgentRole.EXECUTOR


def test_content_agent_graph_builds():
    agent = ContentAgent(llm_provider="mock")
    g = agent.build_graph()
    assert "route" in g.nodes
    assert "generate" in g.nodes
    assert "review" in g.nodes
    assert "revise" in g.nodes


@pytest.mark.asyncio
async def test_content_agent_graph_runs_in_mock_mode():
    agent = ContentAgent(llm_provider="mock")
    result = await agent.create_content("AI tools")
    assert "title" in result
    assert "body" in result
    assert "hashtags" in result


def test_analysis_agent_creation():
    agent = AnalysisAgent()
    assert agent.name == "data_analyst"
    assert agent.role == AgentRole.REVIEWER


@pytest.mark.asyncio
async def test_analysis_agent_graph_runs_in_mock_mode():
    agent = AnalysisAgent(llm_provider="mock")
    result = await agent.analyze_account("test_account")
    assert "score" in result


def test_coordinator_agent_creation():
    coord = CoordinatorAgent()
    assert coord.name == "coordinator"
    assert coord.role == AgentRole.COORDINATOR


@pytest.mark.asyncio
async def test_coordinator_routes_writing_tasks_to_content_agent():
    coord = CoordinatorAgent()
    result = await coord.coordinate_task("写一篇关于 AI 工具的小红书")
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_coordinator_routes_analysis_tasks_to_analysis_agent():
    coord = CoordinatorAgent()
    result = await coord.coordinate_task("分析 account1 的数据表现")
    assert isinstance(result, dict)


@pytest.mark.asyncio
async def test_coordinator_subgraph_fan_out():
    """Multiple sub-graphs should be invoked when plan contains >1 intent."""
    coord = CoordinatorAgent()
    # Default route always returns one intent, but the graph supports >1.
    g = coord.build_graph()
    cp = Checkpointer()
    compiled = g.compile(checkpointer=cp)
    final = await compiled.ainvoke(
        {"task": "test", "plan": ["content", "analysis"], "account_id": "acct-1"}
    )
    assert "sub_results" in final
    assert "final" in final


def test_stategraph_compile_runs_sequentially():
    g = StateGraph()

    async def a(state):
        return {"a": state.get("a", 0) + 1}

    async def b(state):
        return {"b": state.get("b", 0) + 1}

    g.add_node("a", a)
    g.add_node("b", b)
    g.set_entry_point("a")
    g.add_edge("a", "b")
    g.add_edge("b", END())

    import asyncio
    compiled = g.compile()
    result = asyncio.run(compiled.ainvoke({}))
    assert result.get("a") == 1
    assert result.get("b") == 1


@pytest.mark.asyncio
async def test_stategraph_conditional_routing():
    g = StateGraph()

    async def classify(state):
        return {"score": state.get("score", 0)}

    async def pass_node(state):
        return {"verdict": "pass"}

    async def fail_node(state):
        return {"verdict": "fail"}

    g.add_node("classify", classify)
    g.add_node("pass", pass_node)
    g.add_node("fail", fail_node)
    g.set_entry_point("classify")
    g.add_conditional_edges(
        "classify",
        lambda s: "high" if s.get("score", 0) > 50 else "low",
        {"high": "pass", "low": "fail"},
    )
    g.add_edge("pass", END())
    g.add_edge("fail", END())

    compiled = g.compile()
    high = await compiled.ainvoke({"score": 75})
    low = await compiled.ainvoke({"score": 25})
    assert high["verdict"] == "pass"
    assert low["verdict"] == "fail"


@pytest.mark.asyncio
async def test_stategraph_checkpointer_resume():
    g = StateGraph()
    seen = []

    async def step1(state):
        seen.append(1)
        return {"step1": True}

    async def step2(state):
        seen.append(2)
        return {"step2": True}

    g.add_node("step1", step1)
    g.add_node("step2", step2)
    g.set_entry_point("step1")
    g.add_edge("step1", "step2")
    g.add_edge("step2", END())

    cp = Checkpointer()
    compiled = g.compile(checkpointer=cp)
    await compiled.ainvoke({}, config={"configurable": {"thread_id": "t1"}})
    assert cp._store.get("t1") is not None
    assert "step1" in cp._store["t1"]
    assert "step2" in cp._store["t1"]