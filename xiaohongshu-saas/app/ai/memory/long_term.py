"""Long-term memory for persistent storage."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class LongTermMemoryItem:
    """A long-term memory item."""
    id: str
    content: str
    importance: float
    category: str = "general"
    created_at: datetime = field(default_factory=datetime.now)
    accessed_at: datetime = field(default_factory=datetime.now)
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


class LongTermMemory:
    """Long-term memory with persistent storage."""

    def __init__(
        self,
        storage_path: str = "data/memory",
        max_items: int = 1000,
        auto_save: bool = True,
        save_batch_size: int = 100
    ):
        self.storage_path = Path(storage_path)
        self.max_items = max_items
        self.auto_save = auto_save
        self.save_batch_size = save_batch_size
        self._pending_saves = {}
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self._items = {}
        self._word_index: Dict[str, Set[str]] = {}
        self._load()

    def _get_storage_file(self, category: str = "default") -> Path:
        """Get storage file path for a category."""
        return self.storage_path / f"{category}.json"

    def _load(self) -> None:
        """Load memories from disk."""
        for file_path in self.storage_path.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    for item_data in data.get("items", []):
                        item = LongTermMemoryItem(**item_data)
                        self._items[item.id] = item
                        self._index_item(item)
            except Exception:
                pass

    def _index_item(self, item) -> None:
        """Add item to inverted index."""
        for word in set(item.content.lower().split()):
            if len(word) > 2:
                if word not in self._word_index:
                    self._word_index[word] = set()
                self._word_index[word].add(item.id)

    def flush(self):
        """Force save all pending writes to disk."""
        for category in list(self._pending_saves.keys()):
            if self._pending_saves.get(category, 0) > 0:
                self._save(category)
                self._pending_saves[category] = 0

    def _save(self, category: str = "default") -> None:
        """Save memories to disk."""
        items = [item for item in self._items.values() if item.category == category]
        file_path = self._get_storage_file(category)
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump({
                "items": [
                    {
                        "id": item.id,
                        "content": item.content,
                        "importance": item.importance,
                        "category": item.category,
                        "created_at": item.created_at.isoformat(),
                        "accessed_at": item.accessed_at.isoformat(),
                        "access_count": item.access_count,
                        "metadata": item.metadata
                    }
                    for item in items
                ]
            }, f, ensure_ascii=False, indent=2)

    def store(
        self,
        content: str,
        importance: float,
        category: str = "general",
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """Store a memory."""
        import hashlib
        item_id = hashlib.md5(f"{content}{datetime.now().isoformat()}".encode()).hexdigest()[:16]
        
        item = LongTermMemoryItem(
            id=item_id,
            content=content,
            importance=importance,
            category=category,
            metadata=metadata or {}
        )
        
        # Cache content for fast similarity
        item._content_words = set(item.content.lower().split())
        item._content_lower = item.content.lower()
        self._items[item_id] = item
        self._index_item(item)

        if self.auto_save:

            self._pending_saves[category] = self._pending_saves.get(category, 0) + 1

            if self._pending_saves[category] >= self.save_batch_size:

                self._save(category)

                self._pending_saves[category] = 0

        else:

            self._save(category)



        return item_id

    def recall(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5,
        track_access: bool = True
    ) -> List[LongTermMemoryItem]:
        """Recall relevant memories using inverted index with cached word sets."""
        if not query or not query.strip():
            return []

        query_lower = query.lower()
        query_words = set()
        for w in query_lower.split():
            if len(w) > 2:
                query_words.add(w)

        if not query_words:
            # Fallback: treat short query as substring search
            query_words = set(query_lower.split())

        # Use inverted index for fast lookup
        candidate_ids = set()
        for word in query_words:
            if word in self._word_index:
                candidate_ids.update(self._word_index[word])

        # If no candidates from index, fall back to full scan
        if not candidate_ids:
            candidate_ids = set(self._items.keys())

        results = []
        for item_id in candidate_ids:
            item = self._items.get(item_id)
            if item is None:
                continue
            if category and item.category != category:
                continue

            if track_access:
                item.access_count += 1
                item.accessed_at = datetime.now()

            content_words = item._content_words
            if not content_words:
                continue
            overlap = len(query_words & content_words)
            if overlap == 0:
                continue
            score = overlap
            if len(query_lower) <= 20:
                content_lower = getattr(item, "_content_lower", None) or item.content.lower()
                if query_lower in content_lower:
                    score += 5
            results.append((item.importance * (1 + score), item))

        results.sort(key=lambda x: x[0], reverse=True)
        return [item for _, item in results[:limit]]

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple similarity."""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0

    def get(self, item_id: str) -> Optional[LongTermMemoryItem]:
        """Get a memory by ID."""
        return self._items.get(item_id)

    def delete(self, item_id: str) -> bool:
        """Delete a memory."""
        if item_id in self._items:
            item = self._items[item_id]
            category = item.category
            del self._items[item_id]
            self._save(category)
            return True
        return False

    def get_by_category(self, category: str) -> List[LongTermMemoryItem]:
        """Get all memories in a category."""
        return [item for item in self._items.values() if item.category == category]

    def get_recent(self, limit: int = 10) -> List[LongTermMemoryItem]:
        """Get recently accessed memories."""
        sorted_items = sorted(
            self._items.values(),
            key=lambda x: x.accessed_at,
            reverse=True
        )
        return sorted_items[:limit]

    @property
    def size(self) -> int:
        """Get total memory size."""
        return len(self._items)
