"""Tests for the Redis memory backend (fakeredis-backed).

These exercise the same surface area as the SQLite tests in test_ai_memory.py
so any divergence between the two backends is caught.
"""
from __future__ import annotations

import pytest

pytest.importorskip("fakeredis", reason="fakeredis not installed")

import fakeredis.aioredis

from app.ai.memory.db import MemoryDB
from app.ai.memory.redis_db import RedisMemoryDB, build_redis_memory_db, get_memory_db
from app.ai.memory.short_term import ShortTermMemory
from app.ai.memory.long_term import LongTermMemory
from app.ai.memory.episodic import EpisodicMemory
from app.ai.memory.semantic import SemanticMemory
from app.ai.memory.manager import MemoryManager


@pytest.fixture
async def redis_db():
    client = fakeredis.aioredis.FakeRedis()
    db = RedisMemoryDB(client)
    yield db
    # cleanup
    await client.aclose()


# ------------------------------------------------------------------- direct

@pytest.mark.asyncio
async def test_redis_upsert_and_query_item(redis_db):
    await redis_db.upsert_item("i1", agent_id="a1", tenant_id="t1", layer="short", content="hi", importance=0.5, metadata={"src": "test"})
    rows = await redis_db.query_items("a1", "t1", layer="short")
    assert len(rows) == 1
    assert rows[0]["content"] == "hi"
    assert rows[0]["metadata"] == {"src": "test"}


@pytest.mark.asyncio
async def test_redis_query_items_order_by_importance(redis_db):
    for i, imp in enumerate([0.3, 0.9, 0.6]):
        await redis_db.upsert_item("i" + str(i), agent_id="a1", tenant_id="t1", layer="short", content="x" + str(i), importance=imp, metadata={})
    rows = await redis_db.query_items("a1", "t1", layer="short", order_by="importance DESC")
    assert [r["importance"] for r in rows] == [0.9, 0.6, 0.3]


@pytest.mark.asyncio
async def test_redis_query_items_order_by_updated_at(redis_db):
    import asyncio
    for i in range(3):
        await redis_db.upsert_item("u" + str(i), agent_id="a1", tenant_id="t1", layer="short", content="x", importance=0.5, metadata={})
        await asyncio.sleep(0.01)
    rows = await redis_db.query_items("a1", "t1", layer="short", order_by="updated_at DESC")
    ids = [r["id"] for r in rows]
    assert ids[0] == "u2"
    assert ids[-1] == "u0"


@pytest.mark.asyncio
async def test_redis_delete_item(redis_db):
    await redis_db.upsert_item("d1", agent_id="a1", tenant_id="t1", layer="short", content="x", importance=0.5, metadata={})
    ok = await redis_db.delete_item("d1", "a1")
    assert ok is True
    rows = await redis_db.query_items("a1", "t1", layer="short")
    assert rows == []
    # Deleting again returns False.
    assert await redis_db.delete_item("d1", "a1") is False


@pytest.mark.asyncio
async def test_redis_facts(redis_db):
    await redis_db.upsert_fact("f1", agent_id="a1", tenant_id="t1", statement="Python is a language", source="wiki", confidence=0.9, tags=["prog"], metadata={})
    facts = await redis_db.query_facts("a1", "t1")
    assert len(facts) == 1
    assert facts[0]["statement"] == "Python is a language"
    assert facts[0]["tags"] == ["prog"]
    # tag filter
    facts2 = await redis_db.query_facts("a1", "t1", tag="prog")
    assert len(facts2) == 1
    facts3 = await redis_db.query_facts("a1", "t1", tag="missing")
    assert len(facts3) == 0


@pytest.mark.asyncio
async def test_redis_episodes(redis_db):
    import time
    await redis_db.upsert_episode(
        "e1", agent_id="a1", tenant_id="t1",
        summary="first session", context="ctx", events=[{"data": "click"}],
        metadata={}, start_time=time.time() - 10, end_time=time.time(),
    )
    eps = await redis_db.query_episodes("a1", "t1")
    assert len(eps) == 1
    assert eps[0]["summary"] == "first session"
    assert eps[0]["events"] == [{"data": "click"}]


@pytest.mark.asyncio
async def test_redis_stats_and_clear(redis_db):
    await redis_db.upsert_item("i1", agent_id="a1", tenant_id="t1", layer="short", content="x", importance=0.5, metadata={})
    await redis_db.upsert_fact("f1", agent_id="a1", tenant_id="t1", statement="x", source="s", confidence=0.5, tags=[], metadata={})
    s = await redis_db.stats("a1", "t1")
    assert s["items"] == 1
    assert s["facts"] == 1
    await redis_db.clear("a1", "t1")
    s2 = await redis_db.stats("a1", "t1")
    assert s2 == {"items": 0, "facts": 0, "episodes": 0}


# ------------------------------------------------------ layer integration

@pytest.mark.asyncio
async def test_short_term_on_redis(redis_db):
    mem = ShortTermMemory(redis_db, agent_id="a1")
    await mem.add("Hello", importance=0.5)
    await mem.add("AI tools", importance=0.9)
    items = await mem.get_recent(10)
    assert len(items) == 2
    res = await mem.search("AI")
    assert any("AI" in r.content for r in res)


@pytest.mark.asyncio
async def test_long_term_on_redis(redis_db):
    mem = LongTermMemory(redis_db, agent_id="a1")
    item_id = await mem.store("AI is the future", importance=0.8, category="tech")
    res = await mem.recall("AI")
    assert any("AI" in r.content for r in res)
    cat = await mem.recall("AI", category="tech")
    assert len(cat) == 1
    cat2 = await mem.recall("AI", category="missing")
    assert len(cat2) == 0
    assert await mem.delete(item_id) is True
    assert await mem.delete(item_id) is False


@pytest.mark.asyncio
async def test_episodic_on_redis(redis_db):
    mem = EpisodicMemory(redis_db, agent_id="a1")
    await mem.start_episode("ctx")
    await mem.add_event({"data": "first-event"})
    await mem.start_episode("second")  # auto-closes the first
    await mem.add_event({"data": "second-event"})
    await mem.end_episode("second summary")
    # The auto-closed episode contains "first" in its event payload.
    res = await mem.search("first")
    assert any(any("first" in str(ev) for ev in r.events) for r in res)


@pytest.mark.asyncio
async def test_semantic_on_redis(redis_db):
    mem = SemanticMemory(redis_db, agent_id="a1")
    await mem.store("F1", source="s", tags=["tag1"])
    await mem.store("F2", source="s", tags=["tag2"])
    await mem.store("F3", source="s", tags=["tag1", "tag2"])
    all_facts = await mem.recall("F")
    assert len(all_facts) == 3
    tag1_facts = await mem.recall("F", tags=["tag1"])
    assert len(tag1_facts) == 2


@pytest.mark.asyncio
async def test_memory_manager_on_redis(redis_db):
    mgr = MemoryManager(redis_db, agent_id="a1", llm_provider="mock")
    await mgr.add("A", importance=0.9, memory_type="short")
    await mgr.add("B", importance=0.95, memory_type="short")
    n = await mgr.consolidate(threshold=0.7)
    assert n == 2
    # Long-term now has a derived item.
    long_results = await mgr.long_term.recall("A")
    assert len(long_results) >= 1
    derived = long_results[0].metadata.get("derived_from")
    assert derived is not None
    assert len(derived) == 2
    # Short-term is empty after consolidate.
    recent = await mgr.short_term.get_recent(10)
    assert recent == []


# ------------------------------------------------- isolation / cross-agent

@pytest.mark.asyncio
async def test_agent_isolation(redis_db):
    mgr_a = MemoryManager(redis_db, agent_id="A", llm_provider="mock")
    mgr_b = MemoryManager(redis_db, agent_id="B", llm_provider="mock")
    await mgr_a.add("A-only fact", importance=0.9, memory_type="short")
    await mgr_b.add("B-only fact", importance=0.9, memory_type="short")
    res_a = await mgr_a.recall("A-only")
    res_b = await mgr_b.recall("B-only")
    assert len(res_a["short_term"]) == 1
    assert len(res_b["short_term"]) == 1
    # Cross-agent must not leak.
    cross_a = await mgr_a.recall("B-only")
    cross_b = await mgr_b.recall("A-only")
    assert len(cross_a["short_term"]) == 0
    assert len(cross_b["short_term"]) == 0


@pytest.mark.asyncio
async def test_tenant_isolation(redis_db):
    mgr_t1 = MemoryManager(redis_db, agent_id="a1", tenant_id="t1", llm_provider="mock")
    mgr_t2 = MemoryManager(redis_db, agent_id="a1", tenant_id="t2", llm_provider="mock")
    await mgr_t1.add("tenant1 item", importance=0.9, memory_type="short")
    await mgr_t2.add("tenant2 item", importance=0.9, memory_type="short")
    r1 = await mgr_t1.recall("tenant1")
    r2 = await mgr_t2.recall("tenant2")
    assert len(r1["short_term"]) == 1
    assert len(r2["short_term"]) == 1
    cross = await mgr_t1.recall("tenant2")
    assert len(cross["short_term"]) == 0


# ------------------------------------------------------------ factory

@pytest.mark.asyncio
async def test_get_memory_db_redis_with_client(redis_db):
    """get_memory_db(backend=redis, client=...) must build a working RedisMemoryDB."""
    db = get_memory_db(backend="redis", client=redis_db.client)
    assert isinstance(db, RedisMemoryDB)
    await db.upsert_item("f1", agent_id="a", tenant_id="t", layer="short", content="x", importance=0.5, metadata={})
    rows = await db.query_items("a", "t", layer="short")
    assert len(rows) == 1


@pytest.mark.asyncio
async def test_get_memory_db_redis_requires_url_or_client():
    with pytest.raises(ValueError, match="redis_url"):
        get_memory_db(backend="redis")


@pytest.mark.asyncio
async def test_get_memory_db_unknown_backend():
    with pytest.raises(ValueError, match="Unknown memory backend"):
        get_memory_db(backend="cassandra")
