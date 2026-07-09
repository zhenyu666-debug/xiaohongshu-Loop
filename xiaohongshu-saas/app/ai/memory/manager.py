"""Memory manager with summarize-then-consolidate and 4-layer SQLite backend."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.ai.memory.db import MemoryDB
from app.ai.memory.short_term import ShortTermMemory
from app.ai.memory.long_term import LongTermMemory
from app.ai.memory.episodic import EpisodicMemory
from app.ai.memory.semantic import SemanticMemory
from app.ai.memory.summarize import summarize_text


class MemoryManager:
    """Central manager. Coordinates 4 layers + summarization on consolidation."""

    def __init__(
        self,
        db: MemoryDB,
        agent_id: str = "default",
        tenant_id: str = "default",
        llm_provider: str = "mock",
        llm_model: Optional[str] = None,
    ):
        self.db = db
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self.llm_provider = llm_provider
        self.llm_model = llm_model
        self.short_term = ShortTermMemory(db, agent_id, tenant_id)
        self.long_term = LongTermMemory(db, agent_id, tenant_id)
        self.episodic = EpisodicMemory(db, agent_id, tenant_id)
        self.semantic = SemanticMemory(db, agent_id, tenant_id)

    async def add(
        self,
        content: str,
        importance: float = 0.5,
        memory_type: str = "short",
        **kwargs,
    ) -> Optional[str]:
        if memory_type == "short":
            return await self.short_term.add(content, importance, kwargs.get("metadata"))
        if memory_type == "long":
            return await self.long_term.store(
                content=content,
                importance=importance,
                category=kwargs.get("category", "general"),
                metadata=kwargs.get("metadata"),
            )
        if memory_type == "semantic":
            return await self.semantic.store(
                statement=content,
                source=kwargs.get("source", "user"),
                tags=kwargs.get("tags", []),
                confidence=kwargs.get("confidence", 1.0),
                metadata=kwargs.get("metadata"),
            )
        if memory_type == "episodic":
            await self.episodic.add_event({"content": content, **kwargs})
            return None
        return None

    async def recall(
        self,
        query: str,
        memory_types: Optional[List[str]] = None,
        limit: int = 5,
        **kwargs,
    ) -> Dict[str, List[Any]]:
        types = memory_types or ["short", "long", "semantic", "episodic"]
        results: Dict[str, List[Any]] = {}

        if "short" in types:
            short_results = await self.short_term.search(query, limit=limit)
            results["short_term"] = [
                {"content": r.content, "importance": r.importance, "timestamp": r.timestamp}
                for r in short_results
            ]
        if "long" in types:
            long_results = await self.long_term.recall(query, limit=limit)
            results["long_term"] = [
                {"id": r.id, "content": r.content, "importance": r.importance, "category": r.category}
                for r in long_results
            ]
        if "semantic" in types:
            sem = await self.semantic.recall(query, tags=kwargs.get("tags"))
            results["semantic"] = [
                {"id": f.id, "statement": f.statement, "confidence": f.confidence, "tags": f.tags}
                for f in sem[:limit]
            ]
        if "episodic" in types:
            eps = await self.episodic.search(query, limit=limit)
            results["episodic"] = [
                {"id": e.id, "summary": e.summary, "event_count": len(e.events)}
                for e in eps
            ]
        return results

    async def consolidate(self, threshold: float = 0.7) -> int:
        """Summarize short-term items >= threshold, then promote to long-term.

        New behavior (vs legacy): the short-term items are summarized via LLM,
        then a single derived-from-tracked long-term item is stored. The source
        items are removed from short-term. This is "context evolution" — the
        short-term chatter becomes a long-term fact.
        """
        items = await self.short_term.consolidate(threshold)
        if not items:
            return 0
        text_blob = "\n".join(f"- {i.content}" for i in items)
        summary = await summarize_text(text_blob, self.llm_provider, self.llm_model)
        derived_from = [i.id for i in items]
        await self.long_term.store(
            content=summary,
            importance=max(i.importance for i in items),
            category="consolidated",
            metadata={"source_item_count": len(items)},
            derived_from=derived_from,
        )
        # Remove the source short-term items now that they are summarized
        for item in items:
            await self.db.delete_item(item.id, self.agent_id)
        return len(items)

    async def start_episode(self, context: str = "") -> None:
        await self.episodic.start_episode(context)

    async def end_episode(self, summary: str, **kwargs) -> str:
        return await self.episodic.end_episode(summary, kwargs)

    async def clear(self) -> None:
        await self.db.clear(self.agent_id, self.tenant_id)

    async def status(self) -> Dict[str, int]:
        return await self.db.stats(self.agent_id, self.tenant_id)