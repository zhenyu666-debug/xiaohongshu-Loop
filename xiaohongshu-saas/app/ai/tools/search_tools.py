"""Search-related tools."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.ai.tools.base import BaseTool, ToolDefinition, ToolResult


class SearchTrendingTool(BaseTool):
    """Search trending topics.

    Tries a live Playwright scrape when XHS_TRENDING_SCRAPE=1 is set and a
    cookie is available; otherwise returns a curated static list. The static
    list is good enough for demo / CI.
    """

    STATIC_TRENDING = [
        {"topic": "AI Writing Tools", "heat": 98500, "trend": "up"},
        {"topic": "Productivity Hacks", "heat": 87200, "trend": "stable"},
        {"topic": "Work from Home", "heat": 76500, "trend": "up"},
        {"topic": "Side Projects", "heat": 65400, "trend": "down"},
        {"topic": "Morning Routine", "heat": 54300, "trend": "stable"},
    ]

    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_trending",
            description="Search for trending topics on Xiaohongshu",
            parameters={
                "type": "object",
                "properties": {
                    "category": {"type": "string"},
                    "count": {"type": "integer", "default": 10},
                },
            },
        )

    async def execute(self, category: Optional[str] = None, count: int = 10) -> ToolResult:
        try:
            import os
            trending = self.STATIC_TRENDING
            backend = "static"
            if os.environ.get("XHS_TRENDING_SCRAPE") == "1":
                scraped = await _scrape_trending(category)
                if scraped:
                    trending = scraped
                    backend = "playwright"
            return ToolResult(
                success=True,
                data={"trending": trending[:count], "category": category or "general"},
                metadata={"count": min(count, len(trending)), "backend": backend},
            )
        except Exception as e:
            return ToolResult(success=False, error=str(e))


async def _scrape_trending(category: Optional[str]) -> Optional[List[Dict[str, Any]]]:
    """Live scrape via Playwright. Returns None on any failure."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        return None
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            await page.goto("https://www.xiaohongshu.com/explore", timeout=10000)
            await page.wait_for_timeout(2000)
            # Naive parse: pull visible topic text snippets
            topics = await page.eval_on_selector_all(
                "section.note-item .title span",
                "els => els.map(e => e.textContent.trim()).filter(Boolean)",
            )
            await browser.close()
            return [{"topic": t, "heat": 0, "trend": "unknown"} for t in topics[:20]]
    except Exception:
        return None


class SearchContentIdeasTool(BaseTool):
    def get_definition(self) -> ToolDefinition:
        return ToolDefinition(
            name="search_content_ideas",
            description="Search for content ideas based on topic",
            parameters={
                "type": "object",
                "properties": {
                    "topic": {"type": "string"},
                    "count": {"type": "integer", "default": 5},
                },
                "required": ["topic"],
            },
        )

    async def execute(self, topic: str, count: int = 5) -> ToolResult:
        try:
            ideas = [
                f"How to Get Started with {topic}",
                f"{topic}: Tips for Beginners",
                f"My {topic} Journey",
                f"Why {topic} Changed Everything",
                f"The Complete {topic} Guide",
            ][:count]
            return ToolResult(success=True, data={"ideas": ideas, "topic": topic},
                              metadata={"count": len(ideas)})
        except Exception as e:
            return ToolResult(success=False, error=str(e))


def register_search_tools():
    from app.ai.tools.registry import tool_registry
    tool_registry.register(SearchTrendingTool())
    tool_registry.register(SearchContentIdeasTool())