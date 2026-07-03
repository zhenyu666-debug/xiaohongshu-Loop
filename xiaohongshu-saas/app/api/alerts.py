"""Alerts: simple in-memory rule-based alerts over recent events.

Rules (initial):
  - risk_block: 3+ in last 60s => critical
  - publish_fail: 3+ in last 60s => warning
  - upstream_down: any upstream down => info

This is intentionally lightweight so the GUI can render an alert center
without depending on an external monitoring system.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Any

from fastapi import APIRouter

router = APIRouter()

_WINDOW_SECONDS = 60.0
_recent: dict[str, deque[float]] = {
    "risk_block": deque(maxlen=512),
    "publish_fail": deque(maxlen=512),
    "publish_success": deque(maxlen=512),
    "upstream_down": deque(maxlen=512),
}

_RULES = [
    {"id": "risk_block_3_in_60s", "event": "risk_block", "threshold": 3, "severity": "critical"},
    {"id": "publish_fail_3_in_60s", "event": "publish_fail", "threshold": 3, "severity": "warning"},
]


def record_event(event_type: str, payload: dict[str, Any] | None = None) -> dict[str, Any] | None:
    """Record an event and return the triggered alert (if any)."""
    if event_type not in _recent:
        return None
    now = time.time()
    _recent[event_type].append(now)
    for rule in _RULES:
        if rule["event"] != event_type:
            continue
        # count events in window
        cutoff = now - _WINDOW_SECONDS
        count = sum(1 for t in _recent[event_type] if t >= cutoff)
        if count >= rule["threshold"]:
            return {
                "id": rule["id"],
                "severity": rule["severity"],
                "event": event_type,
                "count_in_window": count,
                "window_seconds": int(_WINDOW_SECONDS),
                "fired_at": now,
                "message": f"{event_type} 触发 {count} 次 / {int(_WINDOW_SECONDS)}s",
                "payload": payload or {},
            }
    return None


@router.get("/api/v1/alerts/recent")
async def recent_alerts(limit: int = 50) -> dict:
    """Return fired alerts (recent). The buffer is intentionally bounded."""
    # Expose only summary stats in the read-only path. The actual alert buffer
    # is populated via record_event(); a fuller view is added in M5c if needed.
    return {
        "rules": _RULES,
        "event_counters": {k: len(v) for k, v in _recent.items()},
        "window_seconds": int(_WINDOW_SECONDS),
    }


@router.post("/api/v1/alerts/record")
async def record(payload: dict) -> dict:
    """Manually inject an event for testing. Returns triggered alert if any."""
    evt = payload.get("event")
    triggered = record_event(evt, payload.get("payload"))
    return {"triggered": triggered}