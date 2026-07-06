"""Trino client wrapper + fallback generator.

Real Trino query is optional; if `TRINO_HOST` is unset or unreachable, the
service falls back to `seed.py` so the GUI always has data.
"""
from __future__ import annotations

import os
import socket
from typing import Any, Iterable

from lakehouse_api import seed

_TRINO_HOST = os.environ.get("TRINO_HOST", "")
_TRINO_PORT = int(os.environ.get("TRINO_PORT", "8080"))
_TRINO_USER = os.environ.get("TRINO_USER", "xhs-saas")
_TIMEOUT = 2.0  # seconds — short so we fall back quickly when offline


def trino_reachable() -> bool:
    if not _TRINO_HOST:
        return False
    try:
        with socket.create_connection((_TRINO_HOST, _TRINO_PORT), timeout=_TIMEOUT):
            return True
    except OSError:
        return False


def run_trino(sql: str) -> list[dict[str, Any]]:
    """Execute SQL against Trino via httpx and return rows as list[dict].

    Raises httpx.HTTPError on transport failure or returns [] if upstream
    returns nothing parseable. Caller is responsible for handling the case
    where Trino is offline by checking `trino_reachable()` first.
    """
    import httpx

    url = f"http://{_TRINO_HOST}:{_TRINO_PORT}/v1/statement"
    headers = {"X-Trino-User": _TRINO_USER}
    payload = {"query": sql}
    with httpx.Client(timeout=10.0) as client:
        # Trino REST API is multi-stage, this minimal implementation
        # submits, polls X-Trino-Stage, and returns the final data rows.
        cur = client.post(url, headers=headers, json=payload)
        cur.raise_for_status()
        node = cur.json()
        while True:
            next_url = node.get("nextUri")
            if not next_url:
                return node.get("data", [])
            cur = client.get(next_url, headers=headers)
            cur.raise_for_status()
            node = cur.json()
            if "data" in node and node.get("columns"):
                # attach column names for result assembly
                cols = [c["name"] for c in node["columns"]]
                return [dict(zip(cols, row)) for row in node["data"]]


def kpis() -> dict:
    """Top-level KPIs: PV, UV, conversions, PV/UV ratio."""
    if trino_reachable():
        try:
            sql = (
                "SELECT "
                "  sum(if(event='pv', 1, 0)) AS pv, "
                "  count(DISTINCT if(event='pv', user_id, NULL)) AS uv, "
                "  sum(if(event='conversion', 1, 0)) AS conversions "
                "FROM iceberg.dwd.events "
                "WHERE dt = current_date"
            )
            rows = run_trino(sql)
            if rows:
                row = rows[0]
                pv = int(row.get("pv", 0) or 0)
                uv = int(row.get("uv", 0) or 0)
                conversions = int(row.get("conversions", 0) or 0)
                return {
                    "pv_today": pv,
                    "uv_today": uv,
                    "pv_uv_ratio": round(pv / uv, 2) if uv else None,
                    "conversions_today": conversions,
                    "funnel": funnel(),
                    "source": "trino",
                }
        except Exception:
            pass
    return {**seed.kpis(), "source": "seed"}


def funnel() -> list[dict[str, int | str]]:
    """4-stage conversion funnel: visit -> view -> click -> conversion."""
    if trino_reachable():
        try:
            sql = (
                "SELECT stage, count(*) AS cnt FROM ("
                "  SELECT 'visit' AS stage FROM iceberg.dwd.events WHERE event='visit' AND dt=current_date "
                "  UNION ALL "
                "  SELECT 'view' FROM iceberg.dwd.events WHERE event='view' AND dt=current_date "
                "  UNION ALL "
                "  SELECT 'click' FROM iceberg.dwd.events WHERE event='click' AND dt=current_date "
                "  UNION ALL "
                "  SELECT 'conversion' FROM iceberg.dwd.events WHERE event='conversion' AND dt=current_date "
                ") GROUP BY stage"
            )
            rows = run_trino(sql)
            if rows:
                return [{"stage": r["stage"], "count": int(r["cnt"])} for r in rows]
        except Exception:
            pass
    return seed.funnel()


def series(name: str, days: int = 14) -> dict:
    """Time-series for a named metric. Supported: pv, uv, conversions."""
    if name not in {"pv", "uv", "conversions"}:
        return {"name": name, "points": [], "source": "seed"}
    if trino_reachable():
        try:
            sql = (
                f"SELECT dt AS ts, count(*) AS v FROM iceberg.dwd.events "
                f"WHERE event='{name}' AND dt >= current_date - interval '{days}' day "
                f"GROUP BY dt ORDER BY dt"
            )
            rows = run_trino(sql)
            if rows:
                return {"name": name, "points": [{"ts": str(r["ts"]), "value": int(r["v"])} for r in rows], "source": "trino"}
        except Exception:
            pass
    return {**seed.series(name, days), "source": "seed"}


def top_items(metric: str = "pv", limit: int = 10) -> list[dict]:
    """Top-N items for a given metric. Items are bucketed items like 'item_42'."""
    if trino_reachable():
        try:
            sql = (
                f"SELECT item_id, count(*) AS cnt FROM iceberg.dwd.events "
                f"WHERE event='{metric}' AND dt=current_date "
                f"GROUP BY item_id ORDER BY cnt DESC LIMIT {int(limit)}"
            )
            rows = run_trino(sql)
            if rows:
                return [{"item": str(r["item_id"]), "count": int(r["cnt"])} for r in rows]
        except Exception:
            pass
    return seed.top_items(metric, limit)