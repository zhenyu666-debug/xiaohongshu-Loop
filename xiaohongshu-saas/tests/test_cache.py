"""Tests for the in-process TTL cache."""
from __future__ import annotations

import time

from app.core.cache import TTLCache


def test_set_get_within_ttl():
    c: TTLCache[int] = TTLCache(ttl_seconds=0.5, max_size=4)
    assert c.get("k") is None
    c.set("k", 42)
    assert c.get("k") == 42


def test_expires_after_ttl():
    c: TTLCache[int] = TTLCache(ttl_seconds=0.05, max_size=4)
    c.set("k", 1)
    assert c.get("k") == 1
    time.sleep(0.1)
    assert c.get("k") is None


def test_evicts_oldest_at_max():
    c: TTLCache[int] = TTLCache(ttl_seconds=60.0, max_size=2)
    c.set("a", 1)
    c.set("b", 2)
    c.set("c", 3)
    assert c.size() == 2
    # 'a' should have been evicted as the oldest
    assert c.get("a") is None
    assert c.get("b") == 2
    assert c.get("c") == 3


def test_invalidate():
    c: TTLCache[int] = TTLCache(ttl_seconds=60.0, max_size=4)
    c.set("a", 1)
    c.set("b", 2)
    c.invalidate("a")
    assert c.get("a") is None
    assert c.get("b") == 2
    c.invalidate()
    assert c.get("b") is None