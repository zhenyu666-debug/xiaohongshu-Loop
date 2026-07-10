"""Redis-backed memory store. Same surface as MemoryDB (SQLite).

Hashes hold record payloads, sorted sets index them by order_by field.
Keys are namespaced mem:item:{id}, mem:fact:{id}, mem:episode:{id} plus
per-agent/tenant/layer ZSETs and SETs for enumeration.
"""
from __future__ import annotations

import json
import time
from typing import Any, Dict, List, Optional


class RedisMemoryDB:
    """Async Redis-backed MemoryDB. Drop-in for the SQLite MemoryDB.

    The layer classes (ShortTermMemory etc.) only call methods on db,
    so swapping the backend is just constructing a different db object
    with the same surface area.
    """

    def __init__(self, client):
        self.client = client

    async def init(self):
        return None

    # ------------------------------------------------------------------ items

    async def upsert_item(self, item_id, agent_id, tenant_id, layer, content, importance, metadata, created_at=None):
        now = created_at or time.time()
        key = "mem:item:" + item_id
        mapping = {
            "id": item_id,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "layer": layer,
            "content": content,
            "importance": importance,
            "metadata": json.dumps(metadata or {}, ensure_ascii=False),
            "created_at": str(now),
            "updated_at": str(now),
            "access_count": "0",
        }
        await self.client.hset(key, mapping=mapping)
        idx_ts = "mem:items_idx:" + agent_id + ":" + tenant_id + ":" + layer
        idx_imp = idx_ts + ":imp"
        idx_set = "mem:items_set:" + agent_id + ":" + tenant_id
        await self.client.zadd(idx_ts, {item_id: now})
        await self.client.zadd(idx_imp, {item_id: importance})
        await self.client.sadd(idx_set, item_id)

    async def query_items(self, agent_id, tenant_id="default", layer=None, limit=50, order_by="importance DESC, updated_at DESC"):
        if layer is None:
            keys = ["mem:items_idx:" + agent_id + ":" + tenant_id + ":" + lyr for lyr in ("short", "long")]
            out = []
            for k in keys:
                out.extend(await self._query_one_layer(k, agent_id, tenant_id, layer_name=k.split(":")[-1], order_by=order_by, limit=limit))
            return out[:limit]
        primary = order_by.split(",")[0].strip().lower()
        if primary.startswith("importance"):
            idx = "mem:items_idx:" + agent_id + ":" + tenant_id + ":" + layer + ":imp"
        else:
            idx = "mem:items_idx:" + agent_id + ":" + tenant_id + ":" + layer
        return await self._query_one_layer(idx, agent_id, tenant_id, layer, order_by, limit)

    async def _query_one_layer(self, idx_key, agent_id, tenant_id, layer_name, order_by, limit):
        ids = await self.client.zrevrange(idx_key, 0, limit - 1)
        ids = [i.decode() if isinstance(i, bytes) else i for i in ids]
        if not ids:
            return []
        out = []
        for item_id in ids:
            raw = await self.client.hgetall("mem:item:" + item_id)
            data = {k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v for k, v in raw.items()}
            if not data:
                await self.client.zrem(idx_key, item_id)
                continue
            out.append(self._decode_item(data, layer_name))
        return out

    @staticmethod
    def _decode_item(data, layer):
        return {
            "id": data["id"],
            "layer": data.get("layer", layer),
            "content": data["content"],
            "importance": float(data.get("importance", 0.5)),
            "metadata": json.loads(data.get("metadata", "{}") or "{}"),
            "created_at": float(data.get("created_at", 0)),
            "updated_at": float(data.get("updated_at", 0)),
            "access_count": int(data.get("access_count", 0)),
        }

    async def delete_item(self, item_id, agent_id):
        raw = await self.client.hgetall("mem:item:" + item_id)
        data = {k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v for k, v in raw.items()}
        if not data:
            return False
        agent_id_actual = data.get("agent_id")
        tenant_id = data.get("tenant_id", "default")
        layer = data.get("layer", "short")
        await self.client.delete("mem:item:" + item_id)
        await self.client.zrem("mem:items_idx:" + agent_id_actual + ":" + tenant_id + ":" + layer, item_id)
        await self.client.zrem("mem:items_idx:" + agent_id_actual + ":" + tenant_id + ":" + layer + ":imp", item_id)
        await self.client.srem("mem:items_set:" + agent_id_actual + ":" + tenant_id, item_id)
        return True

    # ------------------------------------------------------------------ facts

    async def upsert_fact(self, fact_id, agent_id, tenant_id, statement, source, confidence, tags, metadata):
        now = time.time()
        key = "mem:fact:" + fact_id
        mapping = {
            "id": fact_id,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "statement": statement,
            "source": source,
            "confidence": confidence,
            "tags": json.dumps(tags or [], ensure_ascii=False),
            "metadata": json.dumps(metadata or {}, ensure_ascii=False),
            "created_at": str(now),
            "updated_at": str(now),
        }
        await self.client.hset(key, mapping=mapping)
        await self.client.zadd("mem:facts_idx:" + agent_id + ":" + tenant_id, {fact_id: confidence})
        await self.client.sadd("mem:facts_set:" + agent_id + ":" + tenant_id, fact_id)

    async def query_facts(self, agent_id, tenant_id="default", tag=None, limit=50):
        raw_ids = await self.client.zrevrange("mem:facts_idx:" + agent_id + ":" + tenant_id, 0, limit - 1)
        ids = [i.decode() if isinstance(i, bytes) else i for i in raw_ids]
        out = []
        for fid in ids:
            raw = await self.client.hgetall("mem:fact:" + fid)
            data = {k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v for k, v in raw.items()}
            if not data:
                await self.client.zrem("mem:facts_idx:" + agent_id + ":" + tenant_id, fid)
                continue
            tags = json.loads(data.get("tags", "[]") or "[]")
            if tag and tag not in tags:
                continue
            out.append({
                "id": data["id"],
                "statement": data["statement"],
                "source": data["source"],
                "confidence": float(data["confidence"]),
                "tags": tags,
                "metadata": json.loads(data.get("metadata", "{}") or "{}"),
            })
        return out

    # -------------------------------------------------------------- episodes

    async def upsert_episode(self, episode_id, agent_id, tenant_id, summary, context, events, metadata, start_time, end_time):
        key = "mem:episode:" + episode_id
        mapping = {
            "id": episode_id,
            "agent_id": agent_id,
            "tenant_id": tenant_id,
            "summary": summary,
            "context": context,
            "events": json.dumps(events, ensure_ascii=False, default=str),
            "metadata": json.dumps(metadata or {}, ensure_ascii=False),
            "start_time": str(start_time),
            "end_time": str(end_time),
        }
        await self.client.hset(key, mapping=mapping)
        await self.client.zadd("mem:episodes_idx:" + agent_id + ":" + tenant_id, {episode_id: end_time})
        await self.client.sadd("mem:episodes_set:" + agent_id + ":" + tenant_id, episode_id)

    async def query_episodes(self, agent_id, tenant_id="default", limit=10):
        raw_ids = await self.client.zrevrange("mem:episodes_idx:" + agent_id + ":" + tenant_id, 0, limit - 1)
        ids = [i.decode() if isinstance(i, bytes) else i for i in raw_ids]
        out = []
        for eid in ids:
            raw = await self.client.hgetall("mem:episode:" + eid)
            data = {k.decode() if isinstance(k, bytes) else k: v.decode() if isinstance(v, bytes) else v for k, v in raw.items()}
            if not data:
                await self.client.zrem("mem:episodes_idx:" + agent_id + ":" + tenant_id, eid)
                continue
            out.append({
                "id": data["id"],
                "summary": data["summary"],
                "context": data.get("context", ""),
                "events": json.loads(data.get("events", "[]") or "[]"),
                "metadata": json.loads(data.get("metadata", "{}") or "{}"),
                "start_time": float(data.get("start_time", 0)),
                "end_time": float(data.get("end_time", 0)),
            })
        return out

    # ----------------------------------------------------------------- admin

    async def stats(self, agent_id, tenant_id="default"):
        item_ids_raw = await self.client.smembers("mem:items_set:" + agent_id + ":" + tenant_id)
        item_ids = {i.decode() if isinstance(i, bytes) else i for i in item_ids_raw}
        fact_ids_raw = await self.client.smembers("mem:facts_set:" + agent_id + ":" + tenant_id)
        fact_ids = {i.decode() if isinstance(i, bytes) else i for i in fact_ids_raw}
        ep_ids_raw = await self.client.smembers("mem:episodes_set:" + agent_id + ":" + tenant_id)
        ep_ids = {i.decode() if isinstance(i, bytes) else i for i in ep_ids_raw}
        return {"items": len(item_ids), "facts": len(fact_ids), "episodes": len(ep_ids)}

    async def clear(self, agent_id, tenant_id="default"):
        for prefix, idx_prefix, set_key in (
            ("mem:item:", "mem:items_idx:", "mem:items_set:" + agent_id + ":" + tenant_id),
            ("mem:fact:", "mem:facts_idx:", "mem:facts_set:" + agent_id + ":" + tenant_id),
            ("mem:episode:", "mem:episodes_idx:", "mem:episodes_set:" + agent_id + ":" + tenant_id),
        ):
            ids_raw = await self.client.smembers(set_key)
            ids = [i.decode() if isinstance(i, bytes) else i for i in ids_raw]
            if ids:
                await self.client.delete(*[prefix + i for i in ids])
            await self.client.delete(set_key)
            for layer in ("short", "long"):
                await self.client.delete(idx_prefix + agent_id + ":" + tenant_id + ":" + layer)
                await self.client.delete(idx_prefix + agent_id + ":" + tenant_id + ":" + layer + ":imp")
            await self.client.delete(idx_prefix + agent_id + ":" + tenant_id)

# --------------------------------------------------------------------------- #
# Factory
# --------------------------------------------------------------------------- #

def build_redis_memory_db(redis_url=None, client=None):
    """Construct a RedisMemoryDB from a URL or an existing client.

    Pass either `redis_url` (e.g. `redis://localhost:6379/0`) or a
    pre-built `client` (use this for fakeredis in tests). One of them
    must be provided.
    """
    if client is None:
        if redis_url is None:
            raise ValueError("Either redis_url or client must be provided")
        try:
            import redis.asyncio as aioredis
        except ImportError as e:
            raise ImportError(
                "redis is required for the redis backend: pip install redis"
            ) from e
        client = aioredis.from_url(redis_url, decode_responses=False)
    return RedisMemoryDB(client)


def get_memory_db(backend=None, **kwargs):
    """Pick the right backend based on settings (or override).

    Returns an instance with the same async surface (init/upsert/query/etc).
    """
    from app.ai.config import settings
    backend = backend or settings.memory_backend
    if backend == "redis":
        return build_redis_memory_db(
            redis_url=kwargs.get("redis_url") or settings.redis_url,
            client=kwargs.get("client"),
        )
    if backend == "sqlite":
        # Lazy import to avoid circular imports and to keep the optional
        # deps of the redis backend off the SQLite path.
        from app.ai.memory.db import MemoryDB
        return MemoryDB(kwargs.get("db_path", "data/memory/memory.db"))
    if backend == "memory":
        # Process-local in-memory dict store; not implemented here - the
        # default is sqlite.
        from app.ai.memory.db import MemoryDB
        return MemoryDB(":memory:")
    raise ValueError("Unknown memory backend: " + str(backend))
