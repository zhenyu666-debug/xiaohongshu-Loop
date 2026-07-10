"""Tests for the Redis-backed rate limiter (fakeredis-backed).

Mirrors test_ai_tools.py's rate-limit tests but uses fakeredis to
exercise the Redis-backed ``RedisTokenBucket`` and
``RedisRateLimiterRegistry``. Crucially, two registry instances that
share the same fakeredis client must share bucket state - this is the
whole point of moving the limiter out-of-process so multi-worker
uvicorn deployments see consistent rate limiting.
"""
from __future__ import annotations

import asyncio

import pytest

pytest.importorskip("fakeredis", reason="fakeredis not installed")

import fakeredis.aioredis

from app.ai.tools.redis_rate_limit import (
    RedisTokenBucket,
    RedisRateLimiterRegistry,
    build_redis_rate_limiter,
)
from app.ai.tools.registry import ToolRegistry
from app.ai.tools.content_tools import GenerateTitleTool


# ---------------------------------------------------------------- fixtures

@pytest.fixture
async def redis_client():
    client = fakeredis.aioredis.FakeRedis()
    yield client
    await client.aclose()


@pytest.fixture
async def registry(redis_client):
    return RedisRateLimiterRegistry(
        client=redis_client,
        default_rate_per_minute=60.0,
        default_capacity=3.0,
    )


# ------------------------------------------------------------------- basics

@pytest.mark.asyncio
async def test_redis_bucket_starts_full(redis_client):
    bucket = RedisTokenBucket(name="x", client=redis_client, capacity=5.0, rate_per_minute=60.0)
    # First acquire must succeed without any prior state.
    assert await bucket.acquire() is True
    assert await bucket.tokens() == pytest.approx(4.0, abs=0.01)


@pytest.mark.asyncio
async def test_redis_bucket_throttles_after_burst(redis_client):
    bucket = RedisTokenBucket(name="x", client=redis_client, capacity=3.0, rate_per_minute=60.0)
    assert await bucket.acquire() is True
    assert await bucket.acquire() is True
    assert await bucket.acquire() is True
    # 4th call inside the same instant: 60/min = 1/s, so no refill yet.
    assert await bucket.acquire() is False


@pytest.mark.asyncio
async def test_redis_bucket_disabled_when_rate_zero(redis_client):
    bucket = RedisTokenBucket(name="x", client=redis_client, capacity=1.0, rate_per_minute=0.0)
    # Disabled bucket must allow unlimited calls without touching Redis.
    for _ in range(50):
        assert await bucket.acquire() is True
    # retry_after must always be 0 when disabled.
    assert await bucket.retry_after() == 0.0


@pytest.mark.asyncio
async def test_redis_bucket_refills_over_time(redis_client):
    bucket = RedisTokenBucket(name="x", client=redis_client, capacity=2.0, rate_per_minute=600.0)
    assert await bucket.acquire() is True
    assert await bucket.acquire() is True
    # 600/min = 10/s, so 100ms accrues ~1 token.
    await asyncio.sleep(0.15)
    assert await bucket.acquire() is True


@pytest.mark.asyncio
async def test_redis_bucket_retry_after_when_empty(redis_client):
    bucket = RedisTokenBucket(name="x", client=redis_client, capacity=1.0, rate_per_minute=60.0)
    await bucket.acquire()  # drain
    # 60/min = 1 token per second; just-drained bucket -> ~1s wait.
    ra = await bucket.retry_after()
    assert 0.0 < ra <= 1.5


@pytest.mark.asyncio
async def test_redis_bucket_reset(redis_client):
    bucket = RedisTokenBucket(name="x", client=redis_client, capacity=2.0, rate_per_minute=1.0)
    await bucket.acquire()
    await bucket.acquire()
    assert await bucket.acquire() is False
    await bucket.reset()
    # After reset, full bucket is restored.
    assert await bucket.acquire() is True
    assert await bucket.acquire() is True


# ------------------------------------------------------------------- sharing

@pytest.mark.asyncio
async def test_two_registry_instances_share_state(redis_client):
    """The whole point of Redis-backed rate limiting: two processes
    holding separate registries must still share the same token count
    for a given tool name."""
    reg_a = RedisRateLimiterRegistry(
        client=redis_client,
        default_rate_per_minute=60.0,
        default_capacity=2.0,
    )
    reg_b = RedisRateLimiterRegistry(
        client=redis_client,
        default_rate_per_minute=60.0,
        default_capacity=2.0,
    )

    # Process A drains the shared bucket.
    assert await reg_a.get("web_search").acquire() is True
    assert await reg_a.get("web_search").acquire() is True

    # Process B must observe the empty bucket and get throttled.
    assert await reg_b.get("web_search").acquire() is False


@pytest.mark.asyncio
async def test_two_workers_concurrent_drain_is_atomic(redis_client):
    """20 concurrent acquires across two registries must respect the
    capacity=5 limit (no over-grants) - that's the Lua atomicity test."""
    reg_a = RedisRateLimiterRegistry(
        client=redis_client,
        default_rate_per_minute=1.0,
        default_capacity=5.0,
    )
    reg_b = RedisRateLimiterRegistry(
        client=redis_client,
        default_rate_per_minute=1.0,
        default_capacity=5.0,
    )

    async def attempt(reg):
        return await reg.get("shared").acquire()

    results = await asyncio.gather(
        *(attempt(reg_a) for _ in range(10)),
        *(attempt(reg_b) for _ in range(10)),
    )
    granted = sum(1 for r in results if r)
    # Capacity=5, so exactly 5 grants; the rest are denied.
    assert granted == 5


# ------------------------------------------------------------------- isolation

@pytest.mark.asyncio
async def test_per_tool_buckets_are_isolated(redis_client):
    """Limiting tool A must not affect tool B, even when sharing Redis."""
    reg = RedisRateLimiterRegistry(
        client=redis_client,
        default_rate_per_minute=60.0,
        default_capacity=1.0,
    )
    assert await reg.get("tool_a").acquire() is True
    # tool_a drained
    assert await reg.get("tool_a").acquire() is False
    # tool_b fresh bucket
    assert await reg.get("tool_b").acquire() is True


# ------------------------------------------------------------------- registry surface

@pytest.mark.asyncio
async def test_registry_configure_overrides(redis_client):
    reg = RedisRateLimiterRegistry(
        client=redis_client,
        default_rate_per_minute=60.0,
        default_capacity=10.0,
    )
    bucket = reg.configure("special", rate_per_minute=600.0, capacity=2.0)
    assert bucket.rate_per_minute == 600.0
    assert bucket.capacity == 2.0
    # Bucket returned by get() should be the same configured one.
    assert reg.get("special") is bucket


def test_build_redis_rate_limiter_requires_url_or_client():
    with pytest.raises(ValueError):
        build_redis_rate_limiter()


def test_build_redis_rate_limiter_accepts_client(redis_client):
    reg = build_redis_rate_limiter(client=redis_client)
    assert isinstance(reg, RedisRateLimiterRegistry)


@pytest.mark.asyncio
async def test_build_redis_rate_limiter_from_url(redis_client):
    # We pass a fake url; fakeredis will be monkey-patched via the client
    # arg in tests. Here we just confirm the URL path also constructs.
    # (The async redis client will fail to connect, but the constructor
    # must not raise.)
    reg = build_redis_rate_limiter(redis_url="redis://127.0.0.1:65535/0")
    assert isinstance(reg, RedisRateLimiterRegistry)


# ------------------------------------------------------------------- integration with ToolRegistry

@pytest.mark.asyncio
async def test_tool_registry_uses_redis_limiter(redis_client):
    """A real ToolRegistry wired to a Redis-backed limiter must
    throttle and surface retry_after via ToolResult metadata."""
    limiter = RedisRateLimiterRegistry(
        client=redis_client,
        default_rate_per_minute=60.0,
        default_capacity=3.0,
    )
    registry = ToolRegistry(rate_limiter=limiter)
    registry.register(GenerateTitleTool())
    results = []
    for _ in range(5):
        results.append(await registry.execute("generate_title", topic="AI"))
    successes = sum(1 for r in results if r.success)
    throttled = [r for r in results if not r.success and r.metadata.get("reason") == "rate_limited"]
    assert successes == 3
    assert len(throttled) == 2
    # retry_after must be present and positive on a throttled result.
    assert throttled[0].metadata["retry_after"] > 0
    assert throttled[0].metadata["limit_per_minute"] == 60.0


@pytest.mark.asyncio
async def test_in_process_and_redis_limiters_share_state_via_tool_registry(redis_client):
    """End-to-end: two ToolRegistry instances wired to two separate
    RedisRateLimiterRegistry instances (e.g. two uvicorn workers) but
    sharing the same Redis client must share the tool's token budget.
    """
    reg_a = ToolRegistry(
        rate_limiter=RedisRateLimiterRegistry(
            client=redis_client,
            default_rate_per_minute=60.0,
            default_capacity=2.0,
        )
    )
    reg_b = ToolRegistry(
        rate_limiter=RedisRateLimiterRegistry(
            client=redis_client,
            default_rate_per_minute=60.0,
            default_capacity=2.0,
        )
    )
    reg_a.register(GenerateTitleTool())
    reg_b.register(GenerateTitleTool())

    # Worker A drains the bucket.
    assert (await reg_a.execute("generate_title", topic="AI")).success
    assert (await reg_a.execute("generate_title", topic="AI")).success
    # Worker B must see the bucket drained.
    r = await reg_b.execute("generate_title", topic="AI")
    assert not r.success
    assert r.metadata["reason"] == "rate_limited"