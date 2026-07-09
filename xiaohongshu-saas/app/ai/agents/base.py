"""Base agent classes for multi-agent collaboration."""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentRole(str, Enum):
    """Agent roles in the system."""
    PLANNER = "planner"       # Decompose tasks
    EXECUTOR = "executor"     # Execute subtasks
    REVIEWER = "reviewer"     # Validate results
    COORDINATOR = "coordinator"  # Orchestrate agents


class AgentMessage(BaseModel):
    """Message exchanged between agents."""
    role: str
    content: str
    sender: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


@dataclass
class AgentConfig:
    """Configuration for an agent."""
    name: str
    role: AgentRole
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 2000
    system_prompt: Optional[str] = None
    tools: List[str] = field(default_factory=list)


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    def __init__(self, config: AgentConfig):
        self.config = config
        self.name = config.name
        self.role = config.role
        self.memory: List[AgentMessage] = []
        self.tools: Dict[str, Any] = {}

    @abstractmethod
    async def think(self, context: List[AgentMessage]) -> str:
        """Process context and generate thoughts."""
        pass

    @abstractmethod
    async def act(self, thought: str) -> List[AgentMessage]:
        """Execute actions based on thoughts and return messages."""
        pass

    def add_message(self, message: AgentMessage) -> None:
        """Add a message to agent memory."""
        self.memory.append(message)

    def get_context(self, limit: int = 10) -> List[AgentMessage]:
        """Get recent messages from memory."""
        return self.memory[-limit:]

    def register_tool(self, name: str, tool: Any) -> None:
        """Register a tool for this agent."""
        self.tools[name] = tool

    def clear_memory(self) -> None:
        """Clear agent memory."""
        self.memory.clear()

    @property
    def system_prompt(self) -> str:
        """Get system prompt for this agent."""
        if self.config.system_prompt:
            return self.config.system_prompt
        return f"You are {self.name}, a {self.role.value} agent."

    async def run(self, input_message: AgentMessage) -> AgentMessage:
        """Run the agent on an input message."""
        self.add_message(input_message)
        context = self.get_context()
        thought = await self.think(context)
        responses = await self.act(thought)
        for msg in responses:
            self.add_message(msg)
        return responses[-1] if responses else AgentMessage(
            role="assistant",
            content="No response generated.",
            sender=self.name
        )


class AgentCoordinator:
    """Coordinates multiple agents working together."""

    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.shared_memory: List[AgentMessage] = []

    def register(self, agent: BaseAgent) -> None:
        """Register an agent."""
        self.agents[agent.name] = agent

    def unregister(self, name: str) -> None:
        """Unregister an agent."""
        if name in self.agents:
            del self.agents[name]

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        """Get an agent by name."""
        return self.agents.get(name)

    def broadcast(self, message: AgentMessage) -> None:
        """Broadcast message to all agents."""
        self.shared_memory.append(message)
        for agent in self.agents.values():
            agent.add_message(message)

    async def run_pipeline(
        self,
        task: str,
        pipeline: List[str],
        initial_context: Optional[List[AgentMessage]] = None
    ) -> AgentMessage:
        """Run a pipeline of agents in sequence."""
        context = initial_context or []
        current_content = task

        for agent_name in pipeline:
            agent = self.agents.get(agent_name)
            if not agent:
                continue

            msg = AgentMessage(
                role="user",
                content=current_content,
                sender="pipeline"
            )
            response = await agent.run(msg)
            current_content = response.content

        return AgentMessage(
            role="assistant",
            content=current_content,
            sender=pipeline[-1] if pipeline else "pipeline"
        )
