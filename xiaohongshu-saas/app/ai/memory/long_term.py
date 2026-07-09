"""Long-term memory layer, SQLite-backed with optional embeddings."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.ai.memory.db import MemoryDB


@dataclass
class LongTermMemoryItem:
    id: str
    content: str
    importance: float
    category: str = "general"
    created_at: float = field(default_factory=time.time)
    accessed_at: float = field(default_factory=time.time)
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    agent_id: str = "default"
    tenant_id: str = "default"


class LongTermMemory:
    """Long-term memory. SQLite-backed, agent-scoped."""

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
        content: str,
        importance: float,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None,
        derived_from: Optional[List[str]] = None,
    ) -> str:
        item_id = uuid.uuid4().hex
        meta = dict(metadata or {})
        meta["category"] = category
        if derived_from:
            meta["derived_from"] = derived_from
        await self.db.upsert_item(
            item_id=item_id,
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            layer="long",
            content=content,
            importance=importance,
            metadata=meta,
        )
        return item_id

    async def recall(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> List[LongTermMemoryItem]:
        rows = await self.db.query_items(
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            layer="long",
            limit=200,
            order_by="importance DESC, updated_at DESC",
        )
        if category:
            rows = [r for r in rows if r["metadata"].get("category") == category]
        q_lower = query.lower()
        q_words = {w for w in q_lower.split() if len(w) > 2}
        scored = []
        for r in rows:
            content = r["content"].lower()
            score = r["importance"]
            if q_lower in content:
                score += 5
            if q_words:
                hits = sum(1 for w in q_words if w in content)
                score += hits * 0.1
            scored.append((score, r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            LongTermMemoryItem(
                id=r["id"],
                content=r["content"],
                importance=r["importance"],
                category=r["metadata"].get("category", "general"),
                created_at=r["created_at"],
                accessed_at=r["updated_at"],
                access_count=r["access_count"],
                metadata=r["metadata"],
                agent_id=self.agent_id,
                tenant_id=self.tenant_id,
            )
            for _, r in scored[:limit]
        ]

    async def delete(self, item_id: str) -> bool:
        return await self.db.delete_item(item_id, self.agent_id)

    @property
    def size(self) -> int:
        return 0  # sync stub