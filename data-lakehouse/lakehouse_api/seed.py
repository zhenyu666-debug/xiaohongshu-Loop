"""Deterministic seed data for lakehouse-api fallback.

When Trino is unreachable (likely in local dev), these functions return
synthetic but representative data so the GUI has something to render.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta


def kpis() -> dict:
    pv_today = 12453
    uv_today = 3124
    conversions_today = 487
    return {
        "pv_today": pv_today,
        "uv_today": uv_today,
        "pv_uv_ratio": round(pv_today / uv_today, 2),
        "conversions_today": conversions_today,
        "funnel": funnel(),
    }


def funnel() -> list[dict[str, int | str]]:
    return [
        {"stage": "visit", "count": 31200},
        {"stage": "view", "count": 18900},
        {"stage": "click", "count": 6540},
        {"stage": "conversion", "count": 1380},
    ]


def series(name: str, days: int = 14) -> dict:
    """Synthesize a smooth wavy series per metric for `days` days back."""
    base = {"pv": 9000, "uv": 2200, "conversions": 350}.get(name, 1000)
    amp = base * 0.25
    period = 3.0
    today = datetime(2026, 7, 4)
    points: list[dict[str, int]] = []
    for i in range(days - 1, -1, -1):
        d = today - timedelta(days=i)
        noise = (math.sin(i * 0.7) + math.cos(i * 0.31)) * 0.15
        v = round(base + amp * math.sin(i / period) + amp * 0.2 * noise)
        points.append({"ts": d.date().isoformat(), "value": max(0, v)})
    return {"name": name, "points": points}


def top_items(metric: str = "pv", limit: int = 10) -> list[dict]:
    base = {"pv": 800, "uv": 180, "conversions": 28}.get(metric, 100)
    out: list[dict] = []
    for i in range(1, limit + 1):
        out.append({"item": f"item_{i:03d}", "count": round(base - i * (base * 0.06))})
    return out