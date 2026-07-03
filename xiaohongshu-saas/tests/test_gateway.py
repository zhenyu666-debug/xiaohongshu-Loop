"""Tests for the upstream service gateway router."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.api import v1_gateway
from app.core.cache import health_cache
from app.main import app


@pytest.mark.asyncio
async def test_health_all_returns_self_when_no_upstreams():
    """Even if pbp/lakehouse are unreachable, /health/all still returns 200 with all services marked down."""
    transport = ASGITransport(app=app)
    health_cache.invalidate()

    async def fake_probe(client, name, base, health_path):
        return {"name": name, "status": "down", "latency_ms": None}

    with patch.object(v1_gateway, "_probe_one", side_effect=fake_probe):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v1/health/all")

    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "down"
    names = {s["name"] for s in body["services"]}
    assert "xhs-saas" in names
    assert "pbp" in names
    assert "lakehouse" in names


@pytest.mark.asyncio
async def test_health_all_ok_when_all_probes_succeed():
    transport = ASGITransport(app=app)
    health_cache.invalidate()

    async def fake_probe(client, name, base, health_path):
        return {"name": name, "status": "up", "latency_ms": 12.3}

    with patch.object(v1_gateway, "_probe_one", side_effect=fake_probe):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v1/health/all")

    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_health_all_cached_on_second_call():
    transport = ASGITransport(app=app)
    health_cache.invalidate()
    call_count = {"n": 0}

    async def fake_probe(client, name, base, health_path):
        call_count["n"] += 1
        return {"name": name, "status": "up", "latency_ms": 5.0}

    with patch.object(v1_gateway, "_probe_one", side_effect=fake_probe):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r1 = await client.get("/api/v1/health/all")
            r2 = await client.get("/api/v1/health/all")

    assert r1.json()["cache_hit"] is False
    assert r2.json()["cache_hit"] is True
    assert call_count["n"] == 3


@pytest.mark.asyncio
async def test_unknown_upstream_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/nope/healthz")
    assert r.status_code == 404


@pytest.mark.asyncio
async def test_cache_clear_endpoint():
    transport = ASGITransport(app=app)
    health_cache.set("manual", {"x": 1})
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.post("/api/v1/cache/clear")
    assert r.status_code == 200
    assert r.json()["cleared"] is True


@pytest.mark.asyncio
async def test_cache_stats_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/cache/stats")
    assert r.status_code == 200
    body = r.json()
    assert "health_cache_size" in body
    assert "health_cache_ttl_seconds" in body