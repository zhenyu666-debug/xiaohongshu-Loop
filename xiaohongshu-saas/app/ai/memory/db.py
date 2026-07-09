"""SQLite-backed memory store with agent_id + tenant_id isolation."""
from __future__ import annotations

import json
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional

try:
    import aiosqlite
except ImportError:  # pragma: no cover
    aiosqlite = None  # type: ignore


SCHEMA = """
CREATE TABLE IF NOT EXISTS memory_items (
    id           TEXT PRIMARY KEY,
    agent_id     TEXT NOT NULL,
    tenant_id    TEXT NOT NULL DEFAULT 'default',
    layer        TEXT NOT NULL,
    content      TEXT NOT NULL,
    importance   REAL NOT NULL DEFAULT 0.5,
    metadata     TEXT NOT NULL DEFAULT '{}',
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL,
    access_count INTEGER NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS idx_memory_agent_layer
    ON memory_items(agent_id, layer, importance DESC, updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_memory_tenant_layer
    ON memory_items(tenant_id, layer);

CREATE TABLE IF NOT EXISTS memory_facts (
    id           TEXT PRIMARY KEY,
    agent_id     TEXT NOT NULL,
    tenant_id    TEXT NOT NULL DEFAULT 'default',
    statement    TEXT NOT NULL,
    source       TEXT NOT NULL DEFAULT 'user',
    confidence   REAL NOT NULL DEFAULT 1.0,
    tags         TEXT NOT NULL DEFAULT '[]',
    metadata     TEXT NOT NULL DEFAULT '{}',
    created_at   REAL NOT NULL,
    updated_at   REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_facts_agent ON memory_facts(agent_id, tenant_id);

CREATE TABLE IF NOT EXISTS memory_episodes (
    id           TEXT PRIMARY KEY,
    agent_id     TEXT NOT NULL,
    tenant_id    TEXT NOT NULL DEFAULT 'default',
    summary      TEXT NOT NULL,
    context      TEXT NOT NULL DEFAULT '',
    events       TEXT NOT NULL DEFAULT '[]',
    metadata     TEXT NOT NULL DEFAULT '{}',
    start_time   REAL NOT NULL,
    end_time     REAL NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_episodes_agent
    ON memory_episodes(agent_id, tenant_id, end_time DESC);
"""


class MemoryDB:
    """Async SQLite memory store. One DB file per tenant."""

    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._initialized = False

    async def init(self) -> None:
        if self._initialized:
            return
        if aiosqlite is None:
            raise ImportError("aiosqlite is required for MemoryDB")
        async with aiosqlite.connect(self.db_path) as db:
            await db.executescript(SCHEMA)
            await db.commit()
        self._initialized = True

    @asynccontextmanager
    async def _conn(self):
        await self.init()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("PRAGMA journal_mode=WAL")
            yield db

    async def upsert_item(
        self,
        item_id: str,
        agent_id: str,
        tenant_id: str,
        layer: str,
        content: str,
        importance: float,
        metadata: Dict[str, Any],
        created_at: Optional[float] = None,
    ) -> None:
        now = created_at or time.time()
        async with self._conn() as db:
            await db.execute(
                """
                INSERT INTO memory_items
                  (id, agent_id, tenant_id, layer, content, importance, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  content=excluded.content,
                  importance=excluded.importance,
                  metadata=excluded.metadata,
                  updated_at=excluded.updated_at
                """,
                (item_id, agent_id, tenant_id, layer, content, importance,
                 json.dumps(metadata, ensure_ascii=False), now, now),
            )
            await db.commit()

    async def query_items(
        self,
        agent_id: str,
        tenant_id: str = "default",
        layer: Optional[str] = None,
        limit: int = 50,
        order_by: str = "importance DESC, updated_at DESC",
    ) -> List[Dict[str, Any]]:
        sql = (
            "SELECT id, layer, content, importance, metadata, created_at, updated_at, access_count "
            "FROM memory_items WHERE agent_id = ? AND tenant_id = ?"
        )
        params: List[Any] = [agent_id, tenant_id]
        if layer:
            sql += " AND layer = ?"
            params.append(layer)
        sql += f" ORDER BY {order_by} LIMIT ?"
        params.append(limit)
        async with self._conn() as db:
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
        return [
            {
                "id": r[0],
                "layer": r[1],
                "content": r[2],
                "importance": r[3],
                "metadata": json.loads(r[4] or "{}"),
                "created_at": r[5],
                "updated_at": r[6],
                "access_count": r[7],
            }
            for r in rows
        ]

    async def delete_item(self, item_id: str, agent_id: str) -> bool:
        async with self._conn() as db:
            cursor = await db.execute(
                "DELETE FROM memory_items WHERE id = ? AND agent_id = ?", (item_id, agent_id)
            )
            await db.commit()
            return cursor.rowcount > 0

    async def upsert_fact(
        self,
        fact_id: str,
        agent_id: str,
        tenant_id: str,
        statement: str,
        source: str,
        confidence: float,
        tags: List[str],
        metadata: Dict[str, Any],
    ) -> None:
        now = time.time()
        async with self._conn() as db:
            await db.execute(
                """
                INSERT INTO memory_facts
                  (id, agent_id, tenant_id, statement, source, confidence, tags, metadata, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  statement=excluded.statement,
                  confidence=excluded.confidence,
                  tags=excluded.tags,
                  metadata=excluded.metadata,
                  updated_at=excluded.updated_at
                """,
                (fact_id, agent_id, tenant_id, statement, source, confidence,
                 json.dumps(tags, ensure_ascii=False),
                 json.dumps(metadata, ensure_ascii=False), now, now),
            )
            await db.commit()

    async def query_facts(
        self,
        agent_id: str,
        tenant_id: str = "default",
        tag: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        sql = (
            "SELECT id, statement, source, confidence, tags, metadata "
            "FROM memory_facts WHERE agent_id = ? AND tenant_id = ?"
        )
        params: List[Any] = [agent_id, tenant_id]
        if tag:
            sql += " AND tags LIKE ?"
            params.append(f'%"{tag}"%')
        sql += " ORDER BY confidence DESC, updated_at DESC LIMIT ?"
        params.append(limit)
        async with self._conn() as db:
            cursor = await db.execute(sql, params)
            rows = await cursor.fetchall()
        return [
            {
                "id": r[0],
                "statement": r[1],
                "source": r[2],
                "confidence": r[3],
                "tags": json.loads(r[4] or "[]"),
                "metadata": json.loads(r[5] or "{}"),
            }
            for r in rows
        ]

    async def upsert_episode(
        self,
        episode_id: str,
        agent_id: str,
        tenant_id: str,
        summary: str,
        context: str,
        events: List[Dict[str, Any]],
        metadata: Dict[str, Any],
        start_time: float,
        end_time: float,
    ) -> None:
        async with self._conn() as db:
            await db.execute(
                """
                INSERT INTO memory_episodes
                  (id, agent_id, tenant_id, summary, context, events, metadata, start_time, end_time)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(id) DO UPDATE SET
                  summary=excluded.summary,
                  events=excluded.events,
                  end_time=excluded.end_time,
                  metadata=excluded.metadata
                """,
                (episode_id, agent_id, tenant_id, summary, context,
                 json.dumps(events, ensure_ascii=False, default=str),
                 json.dumps(metadata, ensure_ascii=False), start_time, end_time),
            )
            await db.commit()

    async def query_episodes(
        self,
        agent_id: str,
        tenant_id: str = "default",
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        async with self._conn() as db:
            cursor = await db.execute(
                "SELECT id, summary, context, events, metadata, start_time, end_time "
                "FROM memory_episodes WHERE agent_id = ? AND tenant_id = ? "
                "ORDER BY end_time DESC LIMIT ?",
                (agent_id, tenant_id, limit),
            )
            rows = await cursor.fetchall()
        return [
            {
                "id": r[0],
                "summary": r[1],
                "context": r[2],
                "events": json.loads(r[3] or "[]"),
                "metadata": json.loads(r[4] or "{}"),
                "start_time": r[5],
                "end_time": r[6],
            }
            for r in rows
        ]

    async def stats(self, agent_id: str, tenant_id: str = "default") -> Dict[str, int]:
        async with self._conn() as db:
            item_count = await (await db.execute(
                "SELECT COUNT(*) FROM memory_items WHERE agent_id=? AND tenant_id=?",
                (agent_id, tenant_id),
            )).fetchone()
            fact_count = await (await db.execute(
                "SELECT COUNT(*) FROM memory_facts WHERE agent_id=? AND tenant_id=?",
                (agent_id, tenant_id),
            )).fetchone()
            episode_count = await (await db.execute(
                "SELECT COUNT(*) FROM memory_episodes WHERE agent_id=? AND tenant_id=?",
                (agent_id, tenant_id),
            )).fetchone()
        return {
            "items": item_count[0],
            "facts": fact_count[0],
            "episodes": episode_count[0],
        }

    async def clear(self, agent_id: str, tenant_id: str = "default") -> None:
        async with self._conn() as db:
            for tbl in ("memory_items", "memory_facts", "memory_episodes"):
                await db.execute(
                    f"DELETE FROM {tbl} WHERE agent_id = ? AND tenant_id = ?",
                    (agent_id, tenant_id),
                )
            await db.commit()