"""Content-related tools for Xiaohongshu posts."""
from __future__ import annotations

import json
from typing import Any, Dict, List

from app.ai.tools.base import BaseTool, ToolDefinition, ToolResult


class GenerateTitleTool(BaseTool):
    """Generate titles for Xiaohongshu posts."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="generate_title",
            description="Generate engaging titles for Xiaohongshu posts",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "The topic of the post"},
                    "keywords": {"type": "array", "items": {"type": "string"}, "description": "Keywords to include"},
                    "style": {"type": "string", "enum": ["casual", "professional", "humorous"], "description": "Title style"}
                },
                "required": ["topic"]
            }
        )

    async def execute(self, topic: str, keywords: List[str] = None, style: str = "casual") -> ToolResult:
        """Generate a title."""
        try:
            keywords = keywords or []
            # Mock generation
            titles = [
                f"{topic} Revealed: What You Need to Know",
                f"The Ultimate {topic} Guide for 2024",
                f"Why Everyone is Talking About {topic}"
            ]
            return ToolResult(
                success=True,
                data={"titles": titles, "selected": titles[0]},
                metadata={"topic": topic, "style": style}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class GenerateBodyTool(BaseTool):
    """Generate body content for Xiaohongshu posts."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="generate_body",
            description="Generate body content for Xiaohongshu posts",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "The topic of the post"},
                    "style": {"type": "string", "enum": ["casual", "professional", "story"], "description": "Writing style"},
                    "length": {"type": "string", "enum": ["short", "medium", "long"], "description": "Content length"}
                },
                "required": ["topic"]
            }
        )

    async def execute(self, topic: str, style: str = "casual", length: str = "medium") -> ToolResult:
        """Generate body content."""
        try:
            length_map = {"short": 100, "medium": 200, "long": 400}
            target_length = length_map.get(length, 200)
            
            body = f"""I've been exploring {topic} lately and wanted to share my thoughts...

This is a {style} style post about {topic}. 
The content would be approximately {target_length} characters in length.

Key points to cover:
- Introduction to the topic
- Personal experience
- Tips and recommendations
- Call to action"""

            return ToolResult(
                success=True,
                data={"body": body, "word_count": len(body.split())},
                metadata={"topic": topic, "style": style, "length": length}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class SuggestHashtagsTool(BaseTool):
    """Suggest hashtags for Xiaohongshu posts."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="suggest_hashtags",
            description="Suggest relevant hashtags for Xiaohongshu posts",
            parameters={
                "type": "object",
                "properties": {
                    "content": {"type": "string", "description": "The post content"},
                    "topic": {"type": "string", "description": "Main topic"},
                    "count": {"type": "integer", "description": "Number of hashtags to suggest", "default": 5}
                },
                "required": ["content"]
            }
        )

    async def execute(self, content: str, topic: str = None, count: int = 5) -> ToolResult:
        """Suggest hashtags."""
        try:
            # Mock hashtag suggestions
            hashtags = [
                "#小红书运营",
                "#内容创作",
                "#AI工具",
                "#效率提升",
                "#笔记分享",
                "#涨粉攻略",
                "#爆款笔记"
            ][:count]
            
            return ToolResult(
                success=True,
                data={"hashtags": hashtags, "count": len(hashtags)},
                metadata={"topic": topic, "content_length": len(content)}
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


# Register tools
def register_content_tools():
    """Register all content-related tools."""
    from app.ai.tools.registry import tool_registry
    
    tool_registry.register(GenerateTitleTool())
    tool_registry.register(GenerateBodyTool())
    tool_registry.register(SuggestHashtagsTool())
