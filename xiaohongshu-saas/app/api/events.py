"""Server-Sent Events (SSE) endpoint streaming publish / risk events.

The unified console subscribes here for live updates so the GUI
does not need to poll the task list on every change.
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import Any

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

router = APIRouter()

# Module-level ring buffer for recent events
_BUFFER_MAX = 200
_buffer: list[dict[str, Any]] = []
_buffer_lock = asyncio.Lock()


async def publish_event(evt: dict[str, Any]) -> None:
    """Called from other parts of the app to push a publish / risk event."""
    async with _buffer_lock:
        _buffer.append({**evt, "ts": time.time()})
        if len(_buffer) > _BUFFER_MAX:
            del _buffer[: len(_buffer) - _BUFFER_MAX]


async def _stream():
    last_idx = len(_buffer)
    last_keepalive = time.monotonic()
    while True:
        async with _buffer_lock:
            current = list(_buffer)
        if current and last_idx < len(current):
            for evt in current[last_idx:]:
                yield f"data: {json.dumps(evt, default=str)}\n\n"
            last_idx = len(current)
        # keepalive every 15s
        now = time.monotonic()
        if now - last_keepalive > 15:
            yield ": keepalive\n\n"
            last_keepalive = now
        await asyncio.sleep(0.5)


@router.get("/api/v1/events/stream")
async def stream_events(topic: str = Query("publish")) -> StreamingResponse:
    """SSE endpoint. Filters by topic (publish|risk|all)."""
    queue: asyncio.Queue = asyncio.Queue(maxsize=128)

    async def producer():
        last_idx = 0
        while True:
            async with _buffer_lock:
                if last_idx < len(_buffer):
                    for evt in _buffer[last_idx:]:
                        if topic == "all" or evt.get("topic") == topic:
                            try:
                                queue.put_nowait(json.dumps(evt, default=str))
                            except asyncio.QueueFull:
                                pass
                    last_idx = len(_buffer)
            await asyncio.sleep(0.3)

    async def event_gen():
        task = asyncio.create_task(producer())
        try:
            while True:
                data = await queue.get()
                yield f"data: {data}\n\n"
        finally:
            task.cancel()

    return StreamingResponse(event_gen(), media_type="text/event-stream")


@router.get("/api/v1/events/recent")
async def recent_events(limit: int = Query(50, ge=1, le=200)) -> dict:
    """Return recent events from the ring buffer (no streaming)."""
    async with _buffer_lock:
        items = _buffer[-limit:][::-1]
    return {"items": items, "total": len(_buffer)}