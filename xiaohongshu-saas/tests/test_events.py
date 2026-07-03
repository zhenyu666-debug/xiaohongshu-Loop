"""Tests for the SSE events endpoint (recent + stream)."""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.api import events as events_mod
from app.main import app


@pytest.mark.asyncio
async def test_recent_events_empty():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/events/recent?limit=5")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert "total" in body


@pytest.mark.asyncio
async def test_publish_event_appends_to_buffer():
    events_mod._buffer.clear()
    await events_mod.publish_event({"topic": "publish", "task_id": 1, "ok": True})
    await events_mod.publish_event({"topic": "risk", "task_id": 2, "ok": False})
    assert len(events_mod._buffer) == 2
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        r = await client.get("/api/v1/events/recent?limit=10")
    assert r.status_code == 200
    body = r.json()
    assert body["total"] >= 2
    assert len(body["items"]) >= 2


@pytest.mark.asyncio
async def test_recent_caps_at_buffer_max():
    """Bounded by _BUFFER_MAX."""
    events_mod._buffer.clear()
    for i in range(events_mod._BUFFER_MAX + 10):
        await events_mod.publish_event({"topic": "publish", "i": i})
    assert len(events_mod._buffer) == events_mod._BUFFER_MAX