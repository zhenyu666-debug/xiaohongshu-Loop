"""Tests for the upstream service gateway router."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import httpx
import pytest
from httpx import ASGITransport, AsyncClient

from app.api import v1_gateway
from app.main import app


@pytest.mark.asyncio
async def test_health_all_returns_self_when_no_upstreams():
    """Even if pbp/lakehouse are unreachable, /health/all still returns 200 with all services marked down."""
    transport = ASGITransport(app=app)

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

    async def fake_probe(client, name, base, health_path):
        return {"name": name, "status": "up", "latency_ms": 12.3}

    with patch.object(v1_gateway, "_probe_one", side_effect=fake_probe):
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.get("/api/v1/health/all")

    assert r.status_code == 200
    assert r.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_unknown_upstream_404():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/nope/healthz")
    assert r.status_code == 404