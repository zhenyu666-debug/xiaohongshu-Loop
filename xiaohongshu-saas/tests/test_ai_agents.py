"""Tests for AI agents module."""
from __future__ import annotations

import pytest

from app.ai.agents.base import (
    AgentConfig,
    AgentMessage,
    AgentRole,
    AgentCoordinator,
)
from app.ai.agents.coordinator import CoordinatorAgent
from app.ai.agents.content_agent import ContentAgent
from app.ai.agents.analysis_agent import AnalysisAgent


def test_agent_message_creation():
    """Test AgentMessage creation."""
    msg = AgentMessage(role="user", content="Hello")
    assert msg.role == "user"
    assert msg.content == "Hello"
    assert msg.sender is None
    assert msg.timestamp is not None


def test_agent_config():
    """Test AgentConfig creation."""
    config = AgentConfig(
        name="test_agent",
        role=AgentRole.EXECUTOR,
        model="gpt-4o"
    )
    assert config.name == "test_agent"
    assert config.role == AgentRole.EXECUTOR
    assert config.model == "gpt-4o"


def test_agent_role_enum():
    """Test AgentRole enum."""
    assert AgentRole.PLANNER.value == "planner"
    assert AgentRole.EXECUTOR.value == "executor"
    assert AgentRole.REVIEWER.value == "reviewer"
    assert AgentRole.COORDINATOR.value == "coordinator"


def test_content_agent_creation():
    """Test ContentAgent creation."""
    agent = ContentAgent()
    assert agent.name == "content_creator"
    assert agent.role == AgentRole.EXECUTOR


@pytest.mark.asyncio
async def test_content_agent_think():
    """Test ContentAgent thinking."""
    agent = ContentAgent()
    context = [AgentMessage(role="user", content="AI tools")]
    thought = await agent.think(context)
    assert thought is not None


@pytest.mark.asyncio
async def test_content_agent_act():
    """Test ContentAgent action."""
    agent = ContentAgent()
    responses = await agent.act("test thought")
    assert len(responses) == 1
    assert responses[0].role == "assistant"


@pytest.mark.asyncio
async def test_content_agent_create_content():
    """Test creating content."""
    agent = ContentAgent()
    result = await agent.create_content("AI Tools", style="casual", length="short")
    assert "title" in result
    assert "body" in result
    assert "hashtags" in result


def test_analysis_agent_creation():
    """Test AnalysisAgent creation."""
    agent = AnalysisAgent()
    assert agent.name == "data_analyst"
    assert agent.role == AgentRole.REVIEWER


@pytest.mark.asyncio
async def test_analysis_agent_analyze():
    """Test analysis."""
    agent = AnalysisAgent()
    result = await agent.analyze_account("test_account")
    assert "score" in result
    assert "strengths" in result
    assert "weaknesses" in result
    assert "recommendations" in result


def test_coordinator_agent_creation():
    """Test CoordinatorAgent creation."""
    coord = CoordinatorAgent()
    assert coord.name == "coordinator"
    assert coord.role == AgentRole.COORDINATOR
    assert coord.agent_coordinator is not None


def test_coordinator_register_sub_agent():
    """Test registering sub-agents."""
    coord = CoordinatorAgent()
    content = ContentAgent()
    coord.register_sub_agent(content)

    assert coord.agent_coordinator.get_agent("content_creator") is content


@pytest.mark.asyncio
async def test_coordinate_task():
    """Test task coordination."""
    coord = CoordinatorAgent()
    content = ContentAgent()
    coord.register_sub_agent(content)

    results = await coord.coordinate_task("Test task", ["content_creator"])
    assert "content_creator" in results


def test_agent_coordinator_register():
    """Test AgentCoordinator register."""
    coordinator = AgentCoordinator()
    agent = ContentAgent()
    coordinator.register(agent)

    assert coordinator.get_agent("content_creator") is agent


def test_agent_coordinator_broadcast():
    """Test message broadcasting."""
    coordinator = AgentCoordinator()
    agent = ContentAgent()
    coordinator.register(agent)

    msg = AgentMessage(role="system", content="Important update")
    coordinator.broadcast(msg)

    assert len(coordinator.shared_memory) == 1
    assert len(agent.memory) == 1


def test_agent_add_message():
    """Test adding messages to agent memory."""
    agent = ContentAgent()
    msg = AgentMessage(role="user", content="test")
    agent.add_message(msg)

    assert len(agent.memory) == 1
    assert agent.memory[0].content == "test"


def test_agent_clear_memory():
    """Test clearing agent memory."""
    agent = ContentAgent()
    agent.add_message(AgentMessage(role="user", content="test"))
    agent.clear_memory()
    assert len(agent.memory) == 0