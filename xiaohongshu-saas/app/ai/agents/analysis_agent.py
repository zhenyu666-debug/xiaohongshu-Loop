"""Analysis agent for account performance and content analytics."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.ai.agents.base import AgentConfig, AgentMessage, AgentRole, BaseAgent


class AnalysisAgent(BaseAgent):
    """Agent specialized in analyzing Xiaohongshu performance data."""

    SYSTEM_PROMPT = """You are a data analysis expert focused on Xiaohongshu account operations.

Analysis dimensions:
1. Account health (follower growth, engagement rate, retention)
2. Content performance (viral rate, watch time, conversion)
3. Competitor comparison (differentiation strategy)
4. Optimization recommendations (specific actionable items)

Output format:
```json
{
  "score": 85,
  "strengths": ["strength1", "strength2"],
  "weaknesses": ["weakness1", "weakness2"],
  "recommendations": [
    {"action": "specific action", "expected_impact": "expected effect"}
  ]
}
```"""

    def __init__(self):
        super().__init__(AgentConfig(
            name="data_analyst",
            role=AgentRole.REVIEWER,
            system_prompt=self.SYSTEM_PROMPT
        ))

    async def think(self, context: List[AgentMessage]) -> str:
        """Analyze the data and identify patterns."""
        last_message = context[-1].content if context else ""
        return f"Analyzing data: {last_message[:100]}..."

    async def act(self, thought: str) -> List[AgentMessage]:
        """Generate analysis report."""
        response_content = json.dumps({
            "score": 72,
            "strengths": ["Accurate topic selection", "Regular posting schedule"],
            "weaknesses": ["Low engagement rate", "Missing series content"],
            "recommendations": [
                {"action": "Add Q&A style content", "expected_impact": "Expected 15% engagement increase"}
            ]
        }, ensure_ascii=False)

        return [AgentMessage(
            role="assistant",
            content=response_content,
            sender=self.name
        )]

    async def analyze_account(self, account_id: str, period: str = "7d") -> Dict[str, Any]:
        """Analyze account performance."""
        prompt = f"Analyze account {account_id} for period {period}."
        msg = AgentMessage(role="user", content=prompt, sender="analysis")
        result = await self.run(msg)
        
        try:
            return json.loads(result.content)
        except json.JSONDecodeError:
            return {"error": "Failed to parse analysis result"}

    async def compare_content(self, post_ids: List[str]) -> Dict[str, Any]:
        """Compare performance of multiple posts."""
        prompt = f"Compare posts: {', '.join(post_ids)}"
        msg = AgentMessage(role="user", content=prompt, sender="analysis")
        result = await self.run(msg)
        
        try:
            return json.loads(result.content)
        except json.JSONDecodeError:
            return {"error": "Failed to parse comparison result"}
