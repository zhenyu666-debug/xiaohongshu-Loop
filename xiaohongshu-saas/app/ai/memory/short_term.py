"""Short-term memory layer, SQLite-backed with agent_id namespace."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from app.ai.memory.db import MemoryDB


@dataclass
class MemoryItem:
    id: str
    content: str
    importance: float = 0.5
    timestamp: float = field(default_factory=time.time)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            self.id = uuid.uuid4().hex


class ShortTermMemory:
    """Short-term memory for the current session."""

    def __init__(
        self,
        db: MemoryDB,
        agent_id: str = "default",
        tenant_id: str = "default",
        max_items: int = 50,
    ):
        self.db = db
        self.agent_id = agent_id
        self.tenant_id = tenant_id
        self.max_items = max_items

    async def add(
        self,
        content: str,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> str:
        item_id = uuid.uuid4().hex
        await self.db.upsert_item(
            item_id=item_id,
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            layer="short",
            content=content,
            importance=importance,
            metadata=metadata or {},
        )
        await self._prune()
        return item_id

    async def _prune(self) -> None:
        rows = await self.db.query_items(
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            layer="short",
            limit=self.max_items * 4,
            order_by="updated_at DESC",
        )
        if len(rows) > self.max_items:
            for old in rows[self.max_items:]:
                await self.db.delete_item(old["id"], self.agent_id)

    async def get_recent(self, n: int = 10) -> List[MemoryItem]:
        rows = await self.db.query_items(
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            layer="short",
            limit=n,
            order_by="updated_at DESC",
        )
        return [
            MemoryItem(
                id=r["id"],
                content=r["content"],
                importance=r["importance"],
                timestamp=r["updated_at"],
                metadata=r["metadata"],
            )
            for r in rows
        ]

    async def search(self, query: str, limit: int = 10) -> List[MemoryItem]:
        """Keyword-based search across short-term memory."""
        all_rows = await self.db.query_items(
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            layer="short",
            limit=200,
        )
        q_lower = query.lower()
        q_words = {w for w in q_lower.split() if len(w) > 2}
        scored = []
        for r in all_rows:
            content = r["content"].lower()
            if q_lower in content:
                scored.append((1.0 + r["importance"], r))
                continue
            if q_words:
                hits = sum(1 for w in q_words if w in content)
                if hits:
                    scored.append((hits / len(q_words) + r["importance"], r))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [
            MemoryItem(
                id=r["id"],
                content=r["content"],
                importance=r["importance"],
                timestamp=r["updated_at"],
                metadata=r["metadata"],
            )
            for _, r in scored[:limit]
        ]

    async def consolidate(self, threshold: float = 0.7) -> List[MemoryItem]:
        """Return short-term items above an importance threshold (for promotion to long-term)."""
        rows = await self.db.query_items(
            agent_id=self.agent_id,
            tenant_id=self.tenant_id,
            layer="short",
            limit=200,
            order_by="importance DESC",
        )
        return [
            MemoryItem(
                id=r["id"],
                content=r["content"],
                importance=r["importance"],
                timestamp=r["updated_at"],
                metadata=r["metadata"],
            )
            for r in rows
            if r["importance"] >= threshold
        ]

    async def clear(self) -> None:
        rows = await self.db.query_items(
            agent_id=self.agent_id, tenant_id=self.tenant_id, layer="short"
        )
        for r in rows:
            await self.db.delete_item(r["id"], self.agent_id)

    @property
    def size(self) -> int:
        return 0  # sync stub; use get_recent for actual count