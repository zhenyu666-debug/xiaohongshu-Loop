"""Short-term memory for current session."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional


@dataclass
class MemoryItem:
    """A memory item."""
    content: str
    importance: float = 0.5
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)


class ShortTermMemory:
    """Short-term memory for the current session."""

    def __init__(self, max_items: int = 50):
        self.max_items = max_items
        self.items: List[MemoryItem] = []

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
        self.items.append(item)
        
        # Maintain max size
        if len(self.items) > self.max_items:
            # Remove oldest or lowest importance item
            self._prune()

    def _prune(self) -> None:
        """Remove items to maintain max size."""
        if len(self.items) <= self.max_items:
            return
        
        # Remove oldest items first
        self.items = self.items[-self.max_items:]

    def get_recent(self, n: int = 10) -> List[MemoryItem]:
        """Get recent memory items."""
        return self.items[-n:] if self.items else []

    def get_all(self) -> List[MemoryItem]:
        """Get all memory items."""
        return self.items.copy()

    def search(self, query: str, threshold: float = 0.3) -> List[MemoryItem]:
        """Search memory items by content similarity."""
        query_lower = query.lower()
        results = []
        
        for item in self.items:
            if query_lower in item.content.lower():
                results.append(item)
            elif self._calculate_similarity(query_lower, item.content.lower()) > threshold:
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
