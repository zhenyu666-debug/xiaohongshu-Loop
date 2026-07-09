"""Memory manager coordinating all memory types."""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from app.ai.memory.short_term import ShortTermMemory
from app.ai.memory.long_term import LongTermMemory
from app.ai.memory.episodic import EpisodicMemory
from app.ai.memory.semantic import SemanticMemory


class MemoryManager:
    """Central manager for all memory systems."""

    def __init__(
        self,
        short_term_max: int = 50,
        long_term_path: str = "data/memory",
        episodic_path: str = "data/memory/episodes",
        semantic_path: str = "data/memory/semantic"
    ):
        self.short_term = ShortTermMemory(max_items=short_term_max)
        self.long_term = LongTermMemory(storage_path=long_term_path)
        self.episodic = EpisodicMemory(storage_path=episodic_path)
        self.semantic = SemanticMemory(storage_path=semantic_path)

    async def add(
        self,
        content: str,
        importance: float = 0.5,
        memory_type: str = "short",
        **kwargs
    ) -> Optional[str]:
        """Add to memory based on type."""
        if memory_type == "short":
            self.short_term.add(content, importance, kwargs.get("metadata"))
            return None
        
        elif memory_type == "long":
            return self.long_term.store(
                content=content,
                importance=importance,
                category=kwargs.get("category", "general"),
                metadata=kwargs.get("metadata")
            )
        
        elif memory_type == "episodic":
            self.episodic.add_event({"content": content, **kwargs})
            return None
        
        elif memory_type == "semantic":
            return self.semantic.store(
                statement=content,
                source=kwargs.get("source", "user"),
                tags=kwargs.get("tags", []),
                confidence=kwargs.get("confidence", 1.0),
                metadata=kwargs.get("metadata")
            )
        
        return None

    async def recall(
        self,
        query: str,
        memory_types: Optional[List[str]] = None,
        limit: int = 5,
        **kwargs
    ) -> Dict[str, List[Any]]:
        """Recall from multiple memory types."""
        if memory_types is None:
            memory_types = ["short", "long", "semantic"]
        
        results = {}
        
        if "short" in memory_types:
            short_results = self.short_term.search(query)
            results["short_term"] = [
                {"content": r.content, "importance": r.importance, "timestamp": r.timestamp.isoformat()}
                for r in short_results[:limit]
            ]
        
        if "long" in memory_types:
            long_results = self.long_term.recall(query, limit=limit)
            results["long_term"] = [
                {"id": r.id, "content": r.content, "importance": r.importance, "category": r.category}
                for r in long_results
            ]
        
        if "semantic" in memory_types:
            semantic_results = self.semantic.recall(query, tags=kwargs.get("tags"))
            results["semantic"] = [
                {"id": r.id, "statement": r.statement, "confidence": r.confidence, "tags": r.tags}
                for r in semantic_results[:limit]
            ]
        
        return results

    def get_context(self, limit: int = 10) -> str:
        """Get context from short-term memory."""
        return self.short_term.get_context(limit)

    async def consolidate(self, threshold: float = 0.7) -> int:
        """Move important short-term memories to long-term."""
        items = self.short_term.consolidate(threshold)
        count = 0
        
        for item in items:
            self.long_term.store(
                content=item.content,
                importance=item.importance,
                metadata=item.metadata
            )
            count += 1
        
        return count

    def clear(self, memory_type: Optional[str] = None) -> None:
        """Clear memory."""
        if memory_type is None or memory_type == "short":
            self.short_term.clear()
        # Long-term and semantic are persistent, don't clear

    def start_episode(self, context: str = "") -> None:
        """Start a new episodic memory episode."""
        self.episodic.start_episode(context)

    def end_episode(self, summary: str, **kwargs) -> str:
        """End current episode."""
        return self.episodic.end_episode(summary, kwargs)

    def get_episode_history(self, limit: int = 10) -> List[Dict]:
        """Get episode history."""
        episodes = self.episodic.get_recent_episodes(limit)
        return [
            {
                "id": e.id,
                "summary": e.summary,
                "start_time": e.start_time.isoformat(),
                "end_time": e.end_time.isoformat(),
                "event_count": len(e.events)
            }
            for e in episodes
        ]

    def store_fact(
        self,
        statement: str,
        source: str,
        tags: Optional[List[str]] = None,
        **kwargs
    ) -> str:
        """Store a semantic fact."""
        return self.semantic.store(statement, source, tags, **kwargs)

    def recall_facts(
        self,
        query: str,
        tags: Optional[List[str]] = None
    ) -> List[Dict]:
        """Recall semantic facts."""
        facts = self.semantic.recall(query, tags)
        return [
            {
                "id": f.id,
                "statement": f.statement,
                "source": f.source,
                "confidence": f.confidence,
                "tags": f.tags
            }
            for f in facts
        ]

    @property
    def status(self) -> Dict[str, int]:
        """Get memory system status."""
        return {
            "short_term_size": self.short_term.size,
            "long_term_size": self.long_term.size,
            "episodes_count": self.episodic.episode_count,
            "facts_count": self.semantic.fact_count
        }
