"""Summarization helper used by the consolidation step in MemoryManager."""
from __future__ import annotations

from typing import Optional


async def summarize_text(
    text: str,
    provider: str = "mock",
    model: Optional[str] = None,
) -> str:
    """Summarize a block of short-term items into a single long-term statement."""
    from app.ai.llm import build_default_llm

    if not text.strip():
        return ""

    if provider == "mock":
        # Deterministic compression: take first sentence + count of items.
        first_line = text.split("\n", 1)[0].lstrip("- ").strip()
        item_count = max(text.count("\n"), 1)
        return f"[consolidated from {item_count} items] {first_line}"

    llm = build_default_llm(provider=provider, model=model)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a memory consolidator. Given a list of recent short-term "
                "memory items, produce a single concise long-term fact that "
                "captures the gist. Reply with one sentence, no preamble."
            ),
        },
        {"role": "user", "content": f"Recent items:\n{text}\n\nLong-term fact:"},
    ]
    response = await llm.ainvoke(messages)
    return response.content.strip()