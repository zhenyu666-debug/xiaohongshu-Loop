"""Per-tool async token-bucket rate limiter.

Usage:
    limiter = TokenBucket(rate_per_minute=60, capacity=10)
    if not await limiter.acquire():
        raise RateLimitExceeded(...)
    # ... run tool ...

The bucket refills at ``rate_per_minute / 60`` tokens per second, up to
``capacity`` tokens. The acquire is non-blocking: it either consumes a
token immediately or returns False. Use ``acquire_or_wait()`` to await
the next available token instead.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, Optional


class RateLimitExceeded(Exception):
    """Raised when a tool's rate limit is exceeded and the caller did not wait."""

    def __init__(self, tool_name: str, retry_after: float):
        super().__init__(
            f"Rate limit exceeded for tool '{tool_name}'; retry in {retry_after:.2f}s"
        )
        self.tool_name = tool_name
        self.retry_after = retry_after


@dataclass
class TokenBucket:
    """Async-safe token bucket.

    ``rate_per_minute`` is the steady-state refill rate. ``capacity`` is the
    maximum bucket depth (burst size). When ``rate_per_minute=0`` the bucket
    is disabled and acquire() always returns True.
    """

    rate_per_minute: float = 60.0
    capacity: float = 10.0
    _tokens: float = 0.0
    _last_refill: float = 0.0
    _lock: asyncio.Lock = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        if self._last_refill == 0.0:
            self._last_refill = time.monotonic()
        if self._lock is None:
            self._lock = asyncio.Lock()
        # Start the bucket full so a freshly constructed limiter allows a burst.
        self._tokens = min(self._tokens or self.capacity, self.capacity)

    def _refill(self) -> None:
        now = time.monotonic()
        elapsed = now - self._last_refill
        if elapsed <= 0:
            return
        refill = (self.rate_per_minute / 60.0) * elapsed
        self._tokens = min(self.capacity, self._tokens + refill)
        self._last_refill = now

    async def acquire(self) -> bool:
        """Try to consume one token. Returns False if the bucket is empty."""
        if self.rate_per_minute <= 0:
            return True
        async with self._lock:
            self._refill()
            if self._tokens >= 1.0:
                self._tokens -= 1.0
                return True
            return False

    async def acquire_or_wait(self, max_wait: float = 30.0) -> bool:
        """Block (sleep loop) until a token is available, or timeout."""
        if self.rate_per_minute <= 0:
            return True
        deadline = time.monotonic() + max_wait
        while True:
            ok = await self.acquire()
            if ok:
                return True
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                return False
            async with self._lock:
                self._refill()
                tokens = self._tokens
            # Sleep just long enough to accrue one token, capped at remaining.
            if self.rate_per_minute > 0:
                wait = min(1.0 / (self.rate_per_minute / 60.0), remaining)
            else:
                wait = remaining
            await asyncio.sleep(max(wait, 0.001))

    def retry_after(self) -> float:
        """Seconds until the next token is available, given current state."""
        if self.rate_per_minute <= 0:
            return 0.0
        with _LocklessView(self) as view:
            view._refill()
            if view._tokens >= 1.0:
                return 0.0
            deficit = 1.0 - view._tokens
            return deficit / (self.rate_per_minute / 60.0)

    @property
    def tokens(self) -> float:
        with _LocklessView(self) as view:
            view._refill()
            return view._tokens


class _LocklessView:
    """Read-only view that releases the lock for non-mutating introspection."""

    def __init__(self, bucket: TokenBucket) -> None:
        self._bucket = bucket

    def __enter__(self) -> TokenBucket:
        return self._bucket

    def __exit__(self, *args: object) -> None:
        return None


class RateLimiterRegistry:
    """Maps tool name -> TokenBucket. Created once per ToolRegistry."""

    def __init__(self, default_rate_per_minute: float = 60.0, default_capacity: float = 10.0):
        self.default_rate_per_minute = default_rate_per_minute
        self.default_capacity = default_capacity
        self._buckets: Dict[str, TokenBucket] = {}

    def configure(
        self,
        tool_name: str,
        rate_per_minute: Optional[float] = None,
        capacity: Optional[float] = None,
    ) -> TokenBucket:
        bucket = TokenBucket(
            rate_per_minute=rate_per_minute
            if rate_per_minute is not None
            else self.default_rate_per_minute,
            capacity=capacity if capacity is not None else self.default_capacity,
        )
        self._buckets[tool_name] = bucket
        return bucket

    def get(self, tool_name: str) -> TokenBucket:
        return self._buckets.setdefault(
            tool_name,
            TokenBucket(
                rate_per_minute=self.default_rate_per_minute,
                capacity=self.default_capacity,
            ),
        )

    def all_buckets(self) -> Dict[str, TokenBucket]:
        return dict(self._buckets)
