"""Coordinator agent for orchestrating multi-agent workflows."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.ai.agents.base import (
    AgentConfig,
    AgentMessage,
    AgentRole,
    AgentCoordinator,
    BaseAgent,
)


class CoordinatorAgent(BaseAgent):
    """Agent that coordinates other agents for complex tasks."""

    SYSTEM_PROMPT = """You are a project coordinator that orchestrates multiple specialized agents.

Your workflow:
1. Understand the user's request
2. Break down into subtasks
3. Assign to appropriate agents
4. Synthesize results
5. Present final output

Agents available:
- content_creator: Create Xiaohongshu posts
- data_analyst: Analyze performance data
- scheduler: Optimize posting schedules

Always provide clear, actionable responses."""

    def __init__(self, coordinator: Optional[AgentCoordinator] = None):
        super().__init__(AgentConfig(
            name="coordinator",
            role=AgentRole.COORDINATOR,
            system_prompt=self.SYSTEM_PROMPT
        ))
        self.agent_coordinator = coordinator or AgentCoordinator()

    async def think(self, context: List[AgentMessage]) -> str:
        """Analyze request and determine workflow."""
        last_message = context[-1].content if context else ""
        
        # Simple routing logic
        if "分析" in last_message or "数据" in last_message:
            return "route_to:data_analyst"
        elif "写" in last_message or "创作" in last_message:
            return "route_to:content_creator"
        else:
            return "route_to:content_creator"

    async def act(self, thought: str) -> List[AgentMessage]:
        """Execute the coordinated workflow."""
        if thought.startswith("route_to:"):
            agent_name = thought.split(":")[1]
            return [AgentMessage(
                role="assistant",
                content=f"Routed to {agent_name}",
                sender=self.name,
                metadata={"action": "route", "agent": agent_name}
            )]
        
        return [AgentMessage(
            role="assistant",
            content="Task completed",
            sender=self.name
        )]

    async def coordinate_task(
        self,
        task: str,
        agents: List[str],
        parallel: bool = False
    ) -> Dict[str, Any]:
        """Coordinate a task across multiple agents."""
        results = {}
        
        if parallel:
            # Run agents in parallel (simplified)
            for agent_name in agents:
                agent = self.agent_coordinator.get_agent(agent_name)
                if agent:
                    msg = AgentMessage(role="user", content=task, sender="coordinator")
                    result = await agent.run(msg)
                    results[agent_name] = result.content
        else:
            # Run agents in sequence
            current_task = task
            for agent_name in agents:
                agent = self.agent_coordinator.get_agent(agent_name)
                if agent:
                    msg = AgentMessage(role="user", content=current_task, sender="coordinator")
                    result = await agent.run(msg)
                    results[agent_name] = result.content
                    current_task = result.content

        return results

    def register_sub_agent(self, agent: BaseAgent) -> None:
        """Register a sub-agent for coordination."""
        self.agent_coordinator.register(agent)
