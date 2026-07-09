"""Semantic memory: factual knowledge store, SQLite-backed."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.ai.memory.db import MemoryDB


@dataclass
class Fact:
    id: str
    statement: str
    source: str = "user"
    confidence: float = 1.0
    tags: List[str] = field(default_factory=list)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)


class SemanticMemory:
    """Store and recall factual knowledge."""

    def __init__(
        self,
        db: MemoryDB,
        agent_id: str = "default",
        tenant_id: str = "default",
    ):
        self.db = db
        self.agent_id = agent_id
        self.tenant_id = tenant_id

    async def store(
        self,
        statement: str,
        source: str,
        tags: Optional[List[str]] = None,
        confidence: float = 1.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        fact_id = uuid.uuid4().hex
        await self.db.upsert_fact(
            fact_id=fact_id,
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            statement=statement,
            source=source,
            confidence=confidence,
            tags=tags or [],
            metadata=metadata or {},
        )
        return fact_id

    async def recall(self, query: str, tags: Optional[List[str]] = None) -> List[Fact]:
        all_facts = await self.db.query_facts(
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            limit=200,
        )
        q_lower = query.lower()
        q_words = {w for w in q_lower.split() if len(w) > 2}
        scored = []
        for f in all_facts:
            if tags and not (set(tags) & set(f["tags"])):
                continue
            stmt = f["statement"].lower()
            score = f["confidence"]
            if q_lower in stmt:
                score += 1
            if q_words:
                score += sum(0.1 for w in q_words if w in stmt)
            if any(q_lower in t.lower() for t in f["tags"]):
                score += 0.5
            scored.append((score, f))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            Fact(
                id=f["id"],
                statement=f["statement"],
                source=f["source"],
                confidence=f["confidence"],
                tags=f["tags"],
                metadata=f["metadata"],
            )
            for _, f in scored
        ]

    @property
    def fact_count(self) -> int:
        return 0  # sync stub