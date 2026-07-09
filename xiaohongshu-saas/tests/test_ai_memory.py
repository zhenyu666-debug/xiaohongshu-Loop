"""Tests for memory module."""
import pytest
import tempfile
from pathlib import Path
from app.ai.memory.short_term import ShortTermMemory
from app.ai.memory.long_term import LongTermMemory
from app.ai.memory.episodic import EpisodicMemory
from app.ai.memory.semantic import SemanticMemory
from app.ai.memory.manager import MemoryManager


def test_short_term_memory_add():
    memory = ShortTermMemory(max_items=10)
    memory.add("Hello world", importance=0.5)
    assert memory.size == 1


def test_short_term_memory_get_recent():
    memory = ShortTermMemory()
    for i in range(5):
        memory.add(f"Item {i}")
    recent = memory.get_recent(3)
    assert len(recent) == 3


def test_short_term_memory_pruning():
    memory = ShortTermMemory(max_items=3)
    for i in range(5):
        memory.add(f"Item {i}")
    assert memory.size == 3


def test_short_term_memory_search():
    memory = ShortTermMemory()
    memory.add("AI is great")
    memory.add("Python programming")
    memory.add("AI tools")
    results = memory.search("AI")
    assert len(results) == 2


def test_short_term_memory_context():
    memory = ShortTermMemory()
    memory.add("First item")
    memory.add("Second item")
    context = memory.get_context()
    assert "First item" in context


def test_short_term_memory_consolidate():
    memory = ShortTermMemory()
    memory.add("Important", importance=0.9)
    memory.add("Less important", importance=0.3)
    important_items = memory.consolidate(threshold=0.7)
    assert len(important_items) == 1


def test_short_term_memory_clear():
    memory = ShortTermMemory()
    memory.add("Test")
    memory.clear()
    assert memory.size == 0


def test_long_term_memory_store_and_recall(tmp_path):
    memory = LongTermMemory(storage_path=str(tmp_path))
    item_id = memory.store("AI is the future", importance=0.8, category="tech")
    assert item_id is not None
    results = memory.recall("AI")
    assert len(results) > 0


def test_long_term_memory_get_by_category(tmp_path):
    memory = LongTermMemory(storage_path=str(tmp_path))
    memory.store("Test 1", importance=0.5, category="cat1")
    memory.store("Test 2", importance=0.5, category="cat2")
    cat1_items = memory.get_by_category("cat1")
    assert len(cat1_items) == 1


def test_long_term_memory_delete(tmp_path):
    memory = LongTermMemory(storage_path=str(tmp_path))
    item_id = memory.store("Test", importance=0.5)
    assert memory.delete(item_id)
    assert memory.get(item_id) is None


def test_long_term_memory_get_recent(tmp_path):
    memory = LongTermMemory(storage_path=str(tmp_path))
    for i in range(3):
        memory.store(f"Item {i}", importance=0.5)
    recent = memory.get_recent(2)
    assert len(recent) == 2


def test_episodic_memory_create_episode(tmp_path):
    memory = EpisodicMemory(storage_path=str(tmp_path))
    memory.start_episode("Test context")
    memory.add_event({"type": "action", "data": "click"})
    memory.add_event({"type": "result", "data": "success"})
    episode_id = memory.end_episode("Test episode summary")
    assert episode_id != ""
    episode = memory.get_episode(episode_id)
    assert episode is not None


def test_episodic_memory_get_recent(tmp_path):
    memory = EpisodicMemory(storage_path=str(tmp_path))
    for i in range(3):
        memory.start_episode()
        memory.add_event({"data": f"event {i}"})
        memory.end_episode(f"Episode {i}")
    recent = memory.get_recent_episodes(2)
    assert len(recent) == 2


def test_episodic_memory_search(tmp_path):
    memory = EpisodicMemory(storage_path=str(tmp_path))
    memory.start_episode()
    memory.add_event({"data": "test"})
    memory.end_episode("Python tutorial")
    memory.start_episode()
    memory.add_event({"data": "test"})
    memory.end_episode("JavaScript guide")
    results = memory.search_episodes("Python")
    assert len(results) == 1


def test_semantic_memory_store_and_recall(tmp_path):
    memory = SemanticMemory(storage_path=str(tmp_path))
    fact_id = memory.store("Python is a programming language", source="wikipedia", tags=["programming"])
    assert fact_id is not None
    results = memory.recall("Python")
    assert len(results) > 0


def test_semantic_memory_by_tags(tmp_path):
    memory = SemanticMemory(storage_path=str(tmp_path))
    memory.store("F1", source="s", tags=["tag1"])
    memory.store("F2", source="s", tags=["tag2"])
    memory.store("F3", source="s", tags=["tag1", "tag2"])
    results = memory.get_by_tags(["tag1"])
    assert len(results) == 2


def test_semantic_memory_update_confidence(tmp_path):
    memory = SemanticMemory(storage_path=str(tmp_path))
    fact_id = memory.store("Test", source="test")
    memory.update_confidence(fact_id, 0.5)
    fact = memory._facts.get(fact_id)
    assert fact is not None
    assert fact.confidence == 0.5


def test_semantic_memory_delete(tmp_path):
    memory = SemanticMemory(storage_path=str(tmp_path))
    fact_id = memory.store("Test", source="test")
    assert memory.delete(fact_id)
    assert fact_id not in memory._facts


def test_semantic_memory_all_tags(tmp_path):
    memory = SemanticMemory(storage_path=str(tmp_path))
    memory.store("F1", source="s", tags=["tag1", "tag2"])
    memory.store("F2", source="s", tags=["tag2", "tag3"])
    tags = memory.get_all_tags()
    assert set(tags) == {"tag1", "tag2", "tag3"}


@pytest.mark.asyncio
async def test_memory_manager_add_short():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MemoryManager(
            long_term_path=str(Path(tmpdir) / "long"),
            episodic_path=str(Path(tmpdir) / "episodic"),
            semantic_path=str(Path(tmpdir) / "semantic")
        )
        await manager.add("Hello", memory_type="short")
        assert manager.short_term.size == 1


@pytest.mark.asyncio
async def test_memory_manager_add_long():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MemoryManager(
            long_term_path=str(Path(tmpdir) / "long"),
            episodic_path=str(Path(tmpdir) / "episodic"),
            semantic_path=str(Path(tmpdir) / "semantic")
        )
        item_id = await manager.add("Important fact", importance=0.9, memory_type="long", category="facts")
        assert item_id is not None


@pytest.mark.asyncio
async def test_memory_manager_recall():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MemoryManager(
            long_term_path=str(Path(tmpdir) / "long"),
            episodic_path=str(Path(tmpdir) / "episodic"),
            semantic_path=str(Path(tmpdir) / "semantic")
        )
        await manager.add("Python is great", memory_type="short")
        results = await manager.recall("Python", memory_types=["short"])
        assert "short_term" in results


@pytest.mark.asyncio
async def test_memory_manager_consolidate():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MemoryManager(
            long_term_path=str(Path(tmpdir) / "long"),
            episodic_path=str(Path(tmpdir) / "episodic"),
            semantic_path=str(Path(tmpdir) / "semantic")
        )
        await manager.add("Important", importance=0.9, memory_type="short")
        await manager.add("Less important", importance=0.3, memory_type="short")
        count = await manager.consolidate(threshold=0.7)
        assert count == 1


def test_memory_manager_status():
    with tempfile.TemporaryDirectory() as tmpdir:
        manager = MemoryManager(
            long_term_path=str(Path(tmpdir) / "long"),
            episodic_path=str(Path(tmpdir) / "episodic"),
            semantic_path=str(Path(tmpdir) / "semantic")
        )
        status = manager.status
        assert "short_term_size" in status
        assert "long_term_size" in status
        assert "episodes_count" in status
        assert "facts_count" in status
