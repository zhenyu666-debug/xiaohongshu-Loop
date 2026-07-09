"""Tests for memory module (SQLite-backed, async)."""
import asyncio
import tempfile
from pathlib import Path

import pytest

from app.ai.memory.db import MemoryDB
from app.ai.memory.short_term import ShortTermMemory
from app.ai.memory.long_term import LongTermMemory
from app.ai.memory.episodic import EpisodicMemory
from app.ai.memory.semantic import SemanticMemory
from app.ai.memory.manager import MemoryManager


@pytest.fixture
async def db():
    with tempfile.TemporaryDirectory() as tmpdir:
        d = MemoryDB(str(Path(tmpdir) / "memory.db"))
        await d.init()
        yield d


@pytest.mark.asyncio
async def test_short_term_add_and_recent(db):
    mem = ShortTermMemory(db, agent_id="a1")
    await mem.add("Hello world", importance=0.5)
    await mem.add("Goodbye world", importance=0.7)
    items = await mem.get_recent(10)
    assert len(items) == 2


@pytest.mark.asyncio
async def test_short_term_pruning(db):
    mem = ShortTermMemory(db, agent_id="a1", max_items=3)
    for i in range(6):
        await mem.add(f"item-{i}")
    items = await mem.get_recent(10)
    assert len(items) <= 3


@pytest.mark.asyncio
async def test_short_term_search(db):
    mem = ShortTermMemory(db, agent_id="a1")
    await mem.add("AI is great")
    await mem.add("Python programming")
    await mem.add("AI tools list")
    results = await mem.search("AI")
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_short_term_consolidate(db):
    mem = ShortTermMemory(db, agent_id="a1")
    await mem.add("Important", importance=0.9)
    await mem.add("Less important", importance=0.3)
    items = await mem.consolidate(threshold=0.7)
    assert len(items) == 1


@pytest.mark.asyncio
async def test_long_term_store_and_recall(db):
    mem = LongTermMemory(db, agent_id="a1")
    item_id = await mem.store("AI is the future", importance=0.8, category="tech")
    assert item_id
    results = await mem.recall("AI")
    assert len(results) > 0


@pytest.mark.asyncio
async def test_long_term_recall_by_category(db):
    mem = LongTermMemory(db, agent_id="a1")
    await mem.store("Test 1", importance=0.5, category="cat1")
    await mem.store("Test 2", importance=0.5, category="cat2")
    results = await mem.recall("Test", category="cat1")
    assert len(results) == 1


@pytest.mark.asyncio
async def test_long_term_delete(db):
    mem = LongTermMemory(db, agent_id="a1")
    item_id = await mem.store("Test", importance=0.5)
    assert await mem.delete(item_id)
    assert await mem.delete(item_id) is False


@pytest.mark.asyncio
async def test_episodic_create(db):
    mem = EpisodicMemory(db, agent_id="a1")
    await mem.start_episode("Test context")
    await mem.add_event({"type": "action", "data": "click"})
    await mem.add_event({"type": "result", "data": "success"})
    episode_id = await mem.end_episode("Test episode summary")
    assert episode_id
    results = await mem.search("summary")
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_episodic_auto_close_on_new_start(db):
    """Regression: previously start_episode discarded in-flight events."""
    mem = EpisodicMemory(db, agent_id="a1")
    await mem.start_episode("first")
    await mem.add_event({"data": "first-event"})
    # Starting a new episode must auto-close the previous one.
    await mem.start_episode("second")
    await mem.end_episode("second summary")
    # Search for "first" should now find the auto-closed episode.
    results = await mem.search("first")
    assert any("first" in r.context for r in results)


@pytest.mark.asyncio
async def test_semantic_store_and_recall(db):
    mem = SemanticMemory(db, agent_id="a1")
    await mem.store("Python is a programming language", source="wikipedia", tags=["programming"])
    results = await mem.recall("Python")
    assert len(results) > 0


@pytest.mark.asyncio
async def test_semantic_recall_by_tags(db):
    mem = SemanticMemory(db, agent_id="a1")
    await mem.store("F1", source="s", tags=["tag1"])
    await mem.store("F2", source="s", tags=["tag2"])
    await mem.store("F3", source="s", tags=["tag1", "tag2"])
    results = await mem.recall("F", tags=["tag1"])
    assert len(results) == 2


@pytest.mark.asyncio
async def test_memory_manager_basic(db):
    mgr = MemoryManager(db, agent_id="agent-x")
    await mgr.add("hello", memory_type="short")
    results = await mgr.recall("hello", memory_types=["short"])
    assert "short_term" in results
    assert len(results["short_term"]) == 1


@pytest.mark.asyncio
async def test_memory_manager_consolidate_summarizes_and_promotes(db):
    mgr = MemoryManager(db, agent_id="agent-x", llm_provider="mock")
    await mgr.add("User prefers bullet lists", importance=0.9, memory_type="short")
    await mgr.add("User dislikes emoji", importance=0.95, memory_type="short")
    await mgr.add("Off-topic", importance=0.3, memory_type="short")
    count = await mgr.consolidate(threshold=0.7)
    assert count == 2
    # Now long-term should have a derived item.
    long_results = await mgr.long_term.recall("User")
    assert len(long_results) >= 1
    derived = long_results[0].metadata.get("derived_from")
    assert derived is not None
    assert len(derived) == 2


@pytest.mark.asyncio
async def test_memory_manager_agent_isolation(db):
    mgr_a = MemoryManager(db, agent_id="A")
    mgr_b = MemoryManager(db, agent_id="B")
    await mgr_a.add("A's secret fact", importance=0.9, memory_type="short")
    await mgr_b.add("B's secret fact", importance=0.9, memory_type="short")
    results_a = await mgr_a.recall("secret")
    results_b = await mgr_b.recall("secret")
    contents_a = [r["content"] for r in results_a["short_term"]]
    contents_b = [r["content"] for r in results_b["short_term"]]
    assert any("A's secret" in c for c in contents_a)
    assert any("B's secret" in c for c in contents_b)
    assert not any("B's secret" in c for c in contents_a)
    assert not any("A's secret" in c for c in contents_b)


@pytest.mark.asyncio
async def test_memory_manager_status(db):
    mgr = MemoryManager(db, agent_id="agent-s")
    await mgr.add("x", memory_type="short")
    s = await mgr.status()
    assert s["items"] >= 1