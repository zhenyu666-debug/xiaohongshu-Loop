"""Content-related tools for Xiaohongshu posts (LLM-backed)."""
from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from app.ai.llm import build_default_llm
from app.ai.tools.base import BaseTool, ToolDefinition, ToolResult


class GenerateTitleTool(BaseTool):
    """Generate titles using the configured LLM (falls back to deterministic mock)."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="generate_title",
            description="Generate engaging titles for Xiaohongshu posts",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {"type": "string", "description": "The topic of the post"},
                    "keywords": {"type": "array", "items": {"type": "string"}},
                    "style": {"type": "string", "enum": ["casual", "professional", "humorous"]},
                },
                "required": ["topic"],
            },
        )

    async def execute(self, topic: str, keywords: Optional[List[str]] = None, style: str = "casual") -> ToolResult:
        try:
            keywords = keywords or []
            llm = build_default_llm()
            if llm.provider == "mock":
                titles = [
                    f"{topic} Revealed: What You Need to Know",
                    f"The Ultimate {topic} Guide for 2024",
                    f"Why Everyone is Talking About {topic}",
                ]
            else:
                prompt = (
                    f"Generate 3 Xiaohongshu titles (each under 20 characters, {style} tone) "
                    f"about: {topic}. Keywords: {', '.join(keywords)}. Return as a JSON array."
                )
                resp = await llm.ainvoke([{"role": "user", "content": prompt}])
                try:
                    titles = json.loads(resp.content.strip().strip("```"))
                    if not isinstance(titles, list):
                        titles = [resp.content]
                except Exception:
                    titles = [resp.content]
            return ToolResult(
                success=True,
                data={"titles": titles, "selected": titles[0]},
                metadata={"topic": topic, "style": style},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class GenerateBodyTool(BaseTool):
    """Generate body content using the configured LLM."""

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="generate_body",
            description="Generate body content for Xiaohongshu posts",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "style": {"type": "string", "enum": ["casual", "professional", "story"]},
                    "length": {"type": "string", "enum": ["short", "medium", "long"]},
                },
                "required": ["topic"],
            },
        )

    async def execute(self, topic: str, style: str = "casual", length: str = "medium") -> ToolResult:
        try:
            llm = build_default_llm()
            if llm.provider == "mock":
                length_map = {"short": 100, "medium": 200, "long": 400}
                body = (
                    f"I've been exploring {topic} lately and wanted to share my thoughts.\n\n"
                    f"This is a {style} style post about {topic}.\n\n"
                    f"Key points:\n- Introduction to the topic\n- Personal experience\n- Tips"
                )
                word_count = len(body.split())
            else:
                target_chars = {"short": 200, "medium": 500, "long": 1000}.get(length, 500)
                prompt = (
                    f"Write a {style} Xiaohongshu post body about: {topic}. "
                    f"Length: ~{target_chars} characters. Use conversational tone, "
                    f"emoji, and 2-3 sentences per paragraph."
                )
                resp = await llm.ainvoke([{"role": "user", "content": prompt}])
                body = resp.content
                word_count = len(body.split())
            return ToolResult(
                success=True,
                data={"body": body, "word_count": word_count},
                metadata={"topic": topic, "style": style, "length": length},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


class SuggestHashtagsTool(BaseTool):
    """Suggest hashtags using LLM, with a static fallback list."""

    DEFAULT_HASHTAGS = [
        "#小红书运营", "#内容创作", "#AI工具", "#效率提升",
        "#笔记分享", "#涨粉攻略", "#爆款笔记",
    ]

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="suggest_hashtags",
            description="Suggest relevant hashtags for Xiaohongshu posts",
            parameters={
                "type": "object",
                "properties": {
                    "content": {"type": "string"},
                    "topic": {"type": "string"},
                    "count": {"type": "integer", "default": 5},
                },
                "required": ["content"],
            },
        )

    async def execute(self, content: str, topic: Optional[str] = None, count: int = 5) -> ToolResult:
        try:
            llm = build_default_llm()
            if llm.provider == "mock":
                hashtags = self.DEFAULT_HASHTAGS[:count]
            else:
                prompt = (
                    f"Suggest {count} relevant Xiaohongshu hashtags for this content.\n"
                    f"Topic: {topic or 'general'}\n"
                    f"Content: {content[:500]}\n"
                    f"Return as a JSON array of strings starting with '#'."
                )
                resp = await llm.ainvoke([{"role": "user", "content": prompt}])
                try:
                    hashtags = json.loads(resp.content.strip().strip("```"))
                    if not isinstance(hashtags, list):
                        hashtags = self.DEFAULT_HASHTAGS[:count]
                except Exception:
                    hashtags = self.DEFAULT_HASHTAGS[:count]
            return ToolResult(
                success=True,
                data={"hashtags": hashtags, "count": len(hashtags)},
                metadata={"topic": topic, "content_length": len(content)},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


def register_content_tools():
    """Register all content-related tools."""
    from app.ai.tools.registry import tool_registry
    tool_registry.register(GenerateTitleTool())
    tool_registry.register(GenerateBodyTool())
    tool_registry.register(SuggestHashtagsTool())