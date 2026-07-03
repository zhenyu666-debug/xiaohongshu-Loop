"""In-process TTL cache for upstream proxy responses."""
from __future__ import annotations

import threading
import time
from typing import Any, Generic, TypeVar

T = TypeVar("T")


class TTLCache(Generic[T]):
    """Thread-safe TTL cache. Keyed by str. Stores typed value."""

    def __init__(self, ttl_seconds: float = 10.0, max_size: int = 256) -> None:
        self._ttl = ttl_seconds
        self._max = max_size
        self._data: dict[str, tuple[float, T]] = {}
        self._lock = threading.RLock()

    def get(self, key: str) -> T | None:
        with self._lock:
            entry = self._data.get(key)
            if entry is None:
                return None
            ts, value = entry
            if time.monotonic() - ts > self._ttl:
                self._data.pop(key, None)
                return None
            return value

    def set(self, key: str, value: T) -> None:
        with self._lock:
            # naive eviction by oldest if exceeded
            if len(self._data) >= self._max:
                oldest = min(self._data, key=lambda k: self._data[k][0])
                self._data.pop(oldest, None)
            self._data[key] = (time.monotonic(), value)

    def invalidate(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._data.clear()
            else:
                self._data.pop(key, None)

    def size(self) -> int:
        with self._lock:
            return len(self._data)


health_cache: TTLCache[dict] = TTLCache(ttl_seconds=3.0, max_size=32)
kpis_cache: TTLCache[dict] = TTLCache(ttl_seconds=10.0, max_size=32)
top_items_cache: TTLCache[list] = TTLCache(ttl_seconds=10.0, max_size=64)