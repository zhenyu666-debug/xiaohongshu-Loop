"""Base agent classes for multi-agent collaboration.

These classes still exist for backwards compatibility with the public API used
elsewhere in the codebase, but new graphs should be built with
``app.ai.agents.graph.StateGraph`` and ``app.ai.agents.graph.Checkpointer``.
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AgentRole(str, Enum):
    PLANNER = "planner"
    EXECUTOR = "executor"
    REVIEWER = "reviewer"
    COORDINATOR = "coordinator"


class AgentMessage(BaseModel):
    role: str
    content: str
    sender: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


@dataclass
class AgentConfig:
    name: str
    role: AgentRole
    model: str = "gpt-4o"
    temperature: float = 0.7
    max_tokens: int = 2000
    system_prompt: Optional[str] = None
    tools: List[str] = field(default_factory=list)


class BaseAgent(ABC):
    def __init__(self, config: AgentConfig):
        self.config = config
        self.name = config.name
        self.role = config.role
        self.memory: List[AgentMessage] = []
        self.tools: Dict[str, Any] = {}

    @abstractmethod
    async def think(self, context: List[AgentMessage]) -> str: ...

    @abstractmethod
    async def act(self, thought: str) -> List[AgentMessage]: ...

    def add_message(self, message: AgentMessage) -> None:
        self.memory.append(message)

    def get_context(self, limit: int = 10) -> List[AgentMessage]:
        return self.memory[-limit:]

    def register_tool(self, name: str, tool: Any) -> None:
        self.tools[name] = tool

    def clear_memory(self) -> None:
        self.memory.clear()

    @property
    def system_prompt(self) -> str:
        if self.config.system_prompt:
            return self.config.system_prompt
        return f"You are {self.name}, a {self.role.value} agent."

    async def run(self, input_message: AgentMessage) -> AgentMessage:
        self.add_message(input_message)
        context = self.get_context()
        thought = await self.think(context)
        responses = await self.act(thought)
        for msg in responses:
            self.add_message(msg)
        return responses[-1] if responses else AgentMessage(
            role="assistant",
            content="No response generated.",
            sender=self.name,
        )


class AgentCoordinator:
    def __init__(self):
        self.agents: Dict[str, BaseAgent] = {}
        self.shared_memory: List[AgentMessage] = []

    def register(self, agent: BaseAgent) -> None:
        self.agents[agent.name] = agent

    def unregister(self, name: str) -> None:
        if name in self.agents:
            del self.agents[name]

    def get_agent(self, name: str) -> Optional[BaseAgent]:
        return self.agents.get(name)

    def broadcast(self, message: AgentMessage) -> None:
        self.shared_memory.append(message)
        for agent in self.agents.values():
            agent.add_message(message)

    async def run_pipeline(
        self,
        task: str,
        pipeline: List[str],
        initial_context: Optional[List[AgentMessage]] = None,
    ) -> AgentMessage:
        context = initial_context or []
        current_content = task
        for agent_name in pipeline:
            agent = self.agents.get(agent_name)
            if not agent:
                continue
            msg = AgentMessage(role="user", content=current_content, sender="pipeline")
            response = await agent.run(msg)
            current_content = response.content
        return AgentMessage(
            role="assistant",
            content=current_content,
            sender=pipeline[-1] if pipeline else "pipeline",
        )