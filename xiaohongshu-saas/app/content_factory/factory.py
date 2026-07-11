"""Content factory: build a ContentItem from a template + optional AI rewrite."""
from __future__ import annotations

import json
import random
from pathlib import Path
from typing import List, Optional

from app.core.config import settings
from app.core.logging import logger
from app.core.types import ContentItem
from app.schemas import TemplateSpec


_TEMPLATE_DIR = Path("data/templates")


def load_template(key: str) -> TemplateSpec:
    path = _TEMPLATE_DIR / f"{key}.json"
    if not path.exists():
        # Fallback to a minimal built-in template
        return TemplateSpec(key=key, title_prefix=key.replace("_", " ").title())
    return TemplateSpec(**json.loads(path.read_text(encoding="utf-8")))


def list_templates() -> List[str]:
    if not _TEMPLATE_DIR.exists():
        return []
    return [p.stem for p in _TEMPLATE_DIR.glob("*.json")]


def render(template: TemplateSpec, *, rng: Optional[random.Random] = None) -> ContentItem:
    """Deterministically render a template into a concrete ContentItem.

    Supports placeholders: {n} for selection, {emoji} for random emoji, {hour} for hour-of-day.
    """
    rng = rng or random.Random()
    emojis = ["🌿", "✨", "💫", "🌸", "🍃", "☁️", "🪴", "🫧"]
    body = (
        template.body
        .replace("{emoji}", rng.choice(emojis))
        .replace("{hour}", str(rng.randint(9, 22)))
    )

    title = f"{template.title_prefix} · {rng.choice(emojis)} #{rng.randint(1000, 9999)}"

    return ContentItem(
        title=title,
        body=body,
        images=list(template.images),
        video=template.video,
        topics=list(template.topics),
        extra=dict(template.extra),
    )


async def agent_rewrite(task: Task, content: ContentItem, *, persona: Optional[str] = None) -> ContentItem:
    """Multi-step agent rewrite via CoordinatorAgent.

    Uses the Coordinator to fan-out ContentAgent (and optionally AnalysisAgent),
    producing a richer structured output than the single-prompt rewrite path.
    Falls back to the template-rendered content when no API key is configured.

    When the coordinator returns only analysis (no draft), the analysis payload
    is preserved in ``content.extra["agent_analysis"]`` so it surfaces in audit
    logs instead of being silently dropped.
    """
    if not settings.openai_api_key:
        return content

    try:
        from app.ai.agents.coordinator import CoordinatorAgent
    except ImportError:
        logger.warning("ai agents not installed; skipping agent rewrite")
        return content

    persona_line = f"人设：{persona}" if persona else "人设：亲和、真诚、不夸张"
    try:
        coordinator = CoordinatorAgent()
        topic = content.title
        body = content.body[:200]
        prompt_task = (
            f"{persona_line}\n"
            f"任务：写一篇关于 {topic} 的小红书笔记。内容：{body}"
        )
        result = await coordinator.coordinate_task(
            task=prompt_task,
            account_id=task.account_ids[0] if task.account_ids else "default",
        )
        draft = result.get("draft") or {}
        if draft:
            return ContentItem(
                title=draft.get("title", content.title),
                body=draft.get("body", content.body),
                images=content.images,
                video=content.video,
                topics=content.topics,
                mentions=content.mentions,
                location=content.location,
                extra=content.extra,
            )
        analysis = result.get("analysis")
        if analysis:
            new_extra = dict(content.extra)
            new_extra["agent_analysis"] = analysis
            logger.info("agent_rewrite: no draft, attaching analysis-only fallback")
            return ContentItem(
                title=content.title,
                body=content.body,
                images=content.images,
                video=content.video,
                topics=content.topics,
                mentions=content.mentions,
                location=content.location,
                extra=new_extra,
            )
        return content
    except Exception:
        logger.exception("Agent rewrite failed, falling back to raw content")
        return content


async def maybe_rewrite(content: ContentItem, *, persona: Optional[str] = None) -> ContentItem:
    """Optional AI rewrite. If `openai` is installed and key configured, rewrite text;
    otherwise return as-is.
    """
    if not settings.openai_api_key:
        return content
    try:
        from openai import AsyncOpenAI  # type: ignore
    except ImportError:
        logger.warning("openai package not installed; skipping AI rewrite")
        return content

    client = AsyncOpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    persona_line = f"人设：{persona}" if persona else "人设：亲和、真诚、不夸张"

    prompt = (
        f"{persona_line}\n"
        "请在保留原意的前提下，把下面的小红书笔记改写成更口语化、更有节奏感、更像真人发的版本，"
        "不要使用夸张营销词，不要超过原文字数的 1.2 倍。\n\n"
        f"标题：{content.title}\n正文：{content.body}\n"
        "返回 JSON：{\"title\": str, \"body\": str}"
    )
    try:
        resp = await client.chat.completions.create(
            model=settings.openai_model,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.8,
            response_format={"type": "json_object"},
        )
        data = json.loads(resp.choices[0].message.content)
        return ContentItem(
            title=data.get("title", content.title),
            body=data.get("body", content.body),
            images=content.images,
            video=content.video,
            topics=content.topics,
            mentions=content.mentions,
            location=content.location,
            extra=content.extra,
        )
    except Exception:
        logger.exception("AI rewrite failed, falling back to raw template")
        return content