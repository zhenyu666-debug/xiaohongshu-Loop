"""Redis-backed token bucket rate limiter.

This is a drop-in replacement for the in-process ``TokenBucket`` from
:mod:`app.ai.tools.rate_limit`, sharing the same public API
(``acquire`` / ``acquire_or_wait`` / ``retry_after`` / ``tokens``).

The bucket state lives in a single Redis hash per tool::

    rl:tool:{name} -> {tokens: float, last_refill: float (unix time)}

Refill + decrement run as one ``EVAL`` Lua script so that concurrent
uvicorn workers (or any other Redis client) cannot race. When
``rate_per_minute <= 0`` the bucket is "disabled" and ``acquire`` always
returns True without touching Redis.

Use :func:`build_redis_rate_limiter` to construct a registry; pair it
with :class:`app.ai.tools.registry.ToolRegistry` exactly like the
in-process limiter:

    from app.ai.tools.rate_limit import build_redis_rate_limiter
    from app.ai.tools.registry import ToolRegistry

    limiter = build_redis_rate_limiter(redis_url="redis://localhost:6379/0")
    registry = ToolRegistry(rate_limiter=limiter)
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Dict, Optional

# Lua script: refill + decrement atomically. Returns:
#   {granted (0|1), tokens_remaining, retry_after_seconds}
# KEYS[1] = bucket hash key
# ARGV[1] = now (float seconds, e.g. time.time())
# ARGV[2] = rate_per_minute (float)
# ARGV[3] = capacity (float)
# ARGV[4] = bucket key prefix length (we read via HGET/HSET directly)
_LUA_ACQUIRE = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local rate_per_minute = tonumber(ARGV[2])
local capacity = tonumber(ARGV[3])

if rate_per_minute <= 0 then
    return {tostring(1), tostring(capacity), tostring(0.0)}
end

local tokens = tonumber(redis.call('HGET', key, 'tokens'))
local last_refill = tonumber(redis.call('HGET', key, 'last_refill'))
if tokens == nil then
    tokens = capacity
    last_refill = now
end

local elapsed = now - last_refill
if elapsed > 0 then
    local refill = (rate_per_minute / 60.0) * elapsed
    tokens = math.min(capacity, tokens + refill)
    last_refill = now
end

if tokens >= 1.0 then
    tokens = tokens - 1.0
    redis.call('HSET', key, 'tokens', tokens, 'last_refill', last_refill)
    return {tostring(1), tostring(tokens), tostring(0.0)}
end

redis.call('HSET', key, 'tokens', tokens, 'last_refill', last_refill)
local deficit = 1.0 - tokens
local retry_after = deficit / (rate_per_minute / 60.0)
return {tostring(0), tostring(tokens), tostring(retry_after)}
"""

# Lua script: read-only token count (no mutation). Used by .tokens /
# .retry_after so introspection doesn't perturb the bucket.
_LUA_INSPECT = """
local key = KEYS[1]
local now = tonumber(ARGV[1])
local rate_per_minute = tonumber(ARGV[2])
local capacity = tonumber(ARGV[3])

if rate_per_minute <= 0 then
    return {tostring(capacity), tostring(0.0)}
end

local tokens = tonumber(redis.call('HGET', key, 'tokens'))
local last_refill = tonumber(redis.call('HGET', key, 'last_refill'))
if tokens == nil then
    return {tostring(capacity), tostring(0.0)}
end

local elapsed = now - last_refill
if elapsed > 0 then
    local refill = (rate_per_minute / 60.0) * elapsed
    tokens = math.min(capacity, tokens + refill)
end
local deficit = math.max(0.0, 1.0 - tokens)
local retry_after = 0.0
if deficit > 0 then
    retry_after = deficit / (rate_per_minute / 60.0)
end
return {tostring(tokens), tostring(retry_after)}
"""


def _bucket_key(tool_name: str) -> str:
    return f"rl:tool:{tool_name}"


@dataclass
class RedisTokenBucket:
    """Async-safe token bucket whose state lives in Redis.

    Same public surface as :class:`app.ai.tools.rate_limit.TokenBucket`
    so ``RateLimiterRegistry`` can swap one for the other.
    """

    name: str
    client: object  # redis.asyncio.Redis
    rate_per_minute: float = 60.0
    capacity: float = 10.0
    _acquire_sha: Optional[str] = None
    _inspect_sha: Optional[str] = None

    async def _ensure_scripts(self) -> None:
        """Lazy-load the Lua scripts; cache their SHAs for EVALSHA."""
        if self._acquire_sha is None:
            self._acquire_sha = await self.client.script_load(_LUA_ACQUIRE)
        if self._inspect_sha is None:
            self._inspect_sha = await self.client.script_load(_LUA_INSPECT)

    async def acquire(self) -> bool:
        """Try to consume one token atomically. Returns False if empty."""
        if self.rate_per_minute <= 0:
            return True
        await self._ensure_scripts()
        now = time.time()
        try:
            res = await self.client.evalsha(
                self._acquire_sha,
                1,
                _bucket_key(self.name),
                str(now),
                str(self.rate_per_minute),
                str(self.capacity),
            )
        except Exception as exc:
            # If the script was flushed (NOSCRIPT), reload and retry once.
            msg = str(exc).upper()
            if "NOSCRIPT" in msg:
                self._acquire_sha = await self.client.script_load(_LUA_ACQUIRE)
                res = await self.client.evalsha(
                    self._acquire_sha,
                    1,
                    _bucket_key(self.name),
                    str(now),
                    str(self.rate_per_minute),
                    str(self.capacity),
                )
            else:
                raise
        return bool(int(res[0]))

    async def acquire_or_wait(self, max_wait: float = 30.0) -> bool:
        """Block (asyncio.sleep loop) until a token is available or timeout."""
        if self.rate_per_minute <= 0:
            return True
        deadline = time.time() + max_wait
        while True:
            if await self.acquire():
                return True
            remaining = deadline - time.time()
            if remaining <= 0:
                return False
            # Sleep just long enough to accrue one token, capped at remaining.
            if self.rate_per_minute > 0:
                wait = min(1.0 / (self.rate_per_minute / 60.0), remaining)
            else:
                wait = remaining
            await asyncio.sleep(max(wait, 0.001))

    async def retry_after(self) -> float:
        """Seconds until the next token is available, given current state."""
        if self.rate_per_minute <= 0:
            return 0.0
        await self._ensure_scripts()
        now = time.time()
        try:
            res = await self.client.evalsha(
                self._inspect_sha,
                1,
                _bucket_key(self.name),
                str(now),
                str(self.rate_per_minute),
                str(self.capacity),
            )
        except Exception as exc:
            if "NOSCRIPT" in str(exc).upper():
                self._inspect_sha = await self.client.script_load(_LUA_INSPECT)
                res = await self.client.evalsha(
                    self._inspect_sha,
                    1,
                    _bucket_key(self.name),
                    str(now),
                    str(self.rate_per_minute),
                    str(self.capacity),
                )
            else:
                raise
        return float(res[1])

    async def tokens(self) -> float:
        """Current token count (after virtual refill, no mutation)."""
        if self.rate_per_minute <= 0:
            return self.capacity
        await self._ensure_scripts()
        now = time.time()
        try:
            res = await self.client.evalsha(
                self._inspect_sha,
                1,
                _bucket_key(self.name),
                str(now),
                str(self.rate_per_minute),
                str(self.capacity),
            )
        except Exception as exc:
            if "NOSCRIPT" in str(exc).upper():
                self._inspect_sha = await self.client.script_load(_LUA_INSPECT)
                res = await self.client.evalsha(
                    self._inspect_sha,
                    1,
                    _bucket_key(self.name),
                    str(now),
                    str(self.rate_per_minute),
                    str(self.capacity),
                )
            else:
                raise
        return float(res[0])

    async def reset(self) -> None:
        """Drop the bucket state. Next acquire() will start with a full bucket."""
        await self.client.delete(_bucket_key(self.name))


# We import the in-process RateLimiterRegistry at module level to keep the
# same registry shape, but its ``get()`` returns TokenBucket. We instead
# subclass here so the same registry works with RedisTokenBucket.
from app.ai.tools.rate_limit import RateLimiterRegistry as _InProcessRegistry  # noqa: E402


class RedisRateLimiterRegistry(_InProcessRegistry):
    """RateLimiterRegistry whose buckets are RedisTokenBucket instances.

    Same constructor signature as the in-process registry. Internally it
    stores :class:`RedisTokenBucket` instances keyed by tool name. The
    registry is safe to share across processes - all state lives in
    Redis.
    """

    def __init__(
        self,
        client,
        default_rate_per_minute: float = 60.0,
        default_capacity: float = 10.0,
    ):
        super().__init__(
            default_rate_per_minute=default_rate_per_minute,
            default_capacity=default_capacity,
        )
        self.client = client

    def configure(
        self,
        tool_name: str,
        rate_per_minute: Optional[float] = None,
        capacity: Optional[float] = None,
    ) -> "RedisTokenBucket":
        bucket = RedisTokenBucket(
            name=tool_name,
            client=self.client,
            rate_per_minute=(
                rate_per_minute
                if rate_per_minute is not None
                else self.default_rate_per_minute
            ),
            capacity=(
                capacity if capacity is not None else self.default_capacity
            ),
        )
        self._buckets[tool_name] = bucket
        return bucket

    def get(self, tool_name: str) -> "RedisTokenBucket":
        existing = self._buckets.get(tool_name)
        if existing is not None:
            return existing
        bucket = RedisTokenBucket(
            name=tool_name,
            client=self.client,
            rate_per_minute=self.default_rate_per_minute,
            capacity=self.default_capacity,
        )
        self._buckets[tool_name] = bucket
        return bucket

    def all_buckets(self) -> Dict[str, "RedisTokenBucket"]:
        return dict(self._buckets)


def build_redis_rate_limiter(redis_url: Optional[str] = None, client=None):
    """Construct a :class:`RedisRateLimiterRegistry`.

    Pass either an explicit ``redis.asyncio.Redis`` ``client`` or a
    ``redis_url`` to construct one. Without either, raises ``ValueError``.

    Returns a registry that is safe to share across uvicorn workers -
    all bucket state lives in Redis.
    """
    if client is None and not redis_url:
        raise ValueError("build_redis_rate_limiter requires redis_url= or client=")
    if client is None:
        try:
            from redis.asyncio import from_url  # type: ignore
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError(
                "redis package is required; install with `pip install redis`"
            ) from exc
        client = from_url(redis_url, decode_responses=True)
    return RedisRateLimiterRegistry(client=client)