"""Short-term memory for current session."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class MemoryItem:
    """A memory item."""
    id: str = ""
    content: str = ""
    importance: float = 0.5
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self):
        if not self.id:
            import uuid
            self.id = uuid.uuid4().hex


class ShortTermMemory:
    """Short-term memory for the current session."""

    def __init__(self, max_items: int = 50):
        self.max_items = max_items
        self.items: List[MemoryItem] = []
        self._word_index: Dict[str, set] = {}

    def add(
        self,
        content: str,
        importance: float = 0.5,
        metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Add an item to short-term memory."""
        item = MemoryItem(
            content=content,
            importance=importance,
            metadata=metadata or {}
        )
        item._content_lower = content.lower()
        self.items.append(item)
        self._index_item(item)
        # Clean stale entries from index (item.id is permanent)
        
        # Maintain max size
        if len(self.items) > self.max_items:
            # Remove oldest or lowest importance item
            self._prune()

    def _prune(self) -> None:
        """Remove items to maintain max size and clean index."""
        if len(self.items) <= self.max_items:
            return

        # Remove oldest items first
        removed = self.items[:-self.max_items]
        self.items = self.items[-self.max_items:]
        # Clean index entries for removed items
        for item in removed:
            for word in set(item.content.lower().split()):
                if word in self._word_index:
                    self._word_index[word].discard(item.id)
                    if not self._word_index[word]:
                        del self._word_index[word]

    def get_recent(self, n: int = 10) -> List[MemoryItem]:
        """Get recent memory items."""
        return self.items[-n:] if self.items else []

    def get_all(self) -> List[MemoryItem]:
        """Get all memory items."""
        return self.items.copy()

    def _index_item(self, item) -> None:
        for word in set(item.content.lower().split()):
            if len(word) > 2:
                if word not in self._word_index:
                    self._word_index[word] = set()
                self._word_index[word].add(item.id)

    def search(self, query: str, threshold: float = 0.3) -> List[MemoryItem]:
        """Search memory items using inverted index for speed."""
        if not query or not query.strip():
            return self.get_recent(100)

        query_lower = query.lower()
        query_words = [w for w in query_lower.split() if len(w) > 2]

        # Collect candidate IDs from inverted index
        candidate_ids = set()
        for word in query_words:
            if word in self._word_index:
                candidate_ids.update(self._word_index[word])

        # Build item map for O(1) lookup
        item_map = {item.id: item for item in self.items}
        if not candidate_ids:
            candidates = self.items
        else:
            candidates = [item_map[iid] for iid in candidate_ids if iid in item_map]

        results = []
        for item in candidates:
            content_lower = getattr(item, "_content_lower", None) or item.content.lower()
            if query_lower in content_lower:
                results.append(item)
            elif self._calculate_similarity(query_lower, content_lower) > threshold:
                results.append(item)

        return results

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple similarity."""
        words1 = set(text1.split())
        words2 = set(text2.split())
        
        if not words1 or not words2:
            return 0.0
        
        intersection = len(words1 & words2)
        union = len(words1 | words2)
        
        return intersection / union if union > 0 else 0.0

    def get_context(self, limit: int = 10) -> str:
        """Get memory context as a string."""
        recent = self.get_recent(limit)
        if not recent:
            return ""
        
        parts = []
        for item in recent:
            parts.append(f"[{item.timestamp.strftime('%H:%M:%S')}] {item.content}")
        
        return "\n".join(parts)

    def clear(self) -> None:
        """Clear all memory."""
        self.items.clear()

    def consolidate(self, threshold: float = 0.7) -> List[MemoryItem]:
        """Get items that should be consolidated to long-term memory."""
        return [item for item in self.items if item.importance >= threshold]

    @property
    def size(self) -> int:
        """Get current memory size."""
        return len(self.items)
