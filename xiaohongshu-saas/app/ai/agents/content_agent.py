"""Content creation agent for Xiaohongshu posts."""
from __future__ import annotations

import json
from typing import List, Optional

from app.ai.agents.base import AgentConfig, AgentMessage, AgentRole, BaseAgent
from app.ai.config import settings
from app.ai.tools.registry import tool_registry


class ContentAgent(BaseAgent):
    """Agent specialized in creating Xiaohongshu content."""

    SYSTEM_PROMPT = """You are an expert Xiaohongshu content creator.

Your abilities:
1. Analyze user needs and generate engaging titles
2. Create posts in Xiaohongshu style (conversational, emoji-rich, rhythmic)
3. Recommend appropriate hashtags
4. Optimize content based on performance data

Writing style:
- Conversational, like chatting with a friend
- 2-3 sentences per paragraph, with blank lines between
- Use emojis appropriately to add vitality
- Avoid exaggerated marketing language
- Titles under 20 characters

Output format:
```json
{
  "title": "Title",
  "body": "Content body",
  "hashtags": ["#topic1", "#topic2"],
  "tips": ["tip1", "tip2"]
}
```"""

    def __init__(self):
        super().__init__(AgentConfig(
            name="content_creator",
            role=AgentRole.EXECUTOR,
            system_prompt=self.SYSTEM_PROMPT
        ))
        self._register_tools()

    def _register_tools(self):
        """Register content-related tools."""
        self.register_tool("search_trending", tool_registry.get("search_trending"))
        self.register_tool("suggest_hashtags", tool_registry.get("suggest_hashtags"))

    async def think(self, context: List[AgentMessage]) -> str:
        """Analyze the request and plan content creation."""
        last_message = context[-1].content if context else ""
        
        # Simple keyword extraction
        keywords = []
        if "AI" in last_message or "ai" in last_message:
            keywords.append("AI")
        if "工具" in last_message:
            keywords.append("工具")
        if "小红书" in last_message:
            keywords.append("小红书")

        return f"Creating content about: {', '.join(keywords) if keywords else 'general topic'}"

    async def act(self, thought: str) -> List[AgentMessage]:
        """Generate content based on thought."""
        # This would normally call the LLM
        response_content = json.dumps({
            "title": "AI Tools Review",
            "body": "Tried several AI writing tools recently...",
            "hashtags": ["#AI", "#效率工具", "#小红书运营"],
            "tips": ["Choose tools based on your needs", "AI is an assistant, not a replacement"]
        }, ensure_ascii=False)

        return [AgentMessage(
            role="assistant",
            content=response_content,
            sender=self.name
        )]

    async def create_content(
        self,
        topic: str,
        style: str = "casual",
        length: str = "medium"
    ) -> dict:
        """Create content based on topic and preferences."""
        prompt = f"""Create a Xiaohongshu post about: {topic}
Style: {style}
Length: {length}
Return JSON with title, body, hashtags."""
        
        msg = AgentMessage(role="user", content=prompt, sender="user")
        result = await self.run(msg)
        
        try:
            return json.loads(result.content)
        except json.JSONDecodeError:
            return {"title": topic, "body": result.content, "hashtags": [], "tips": []}
