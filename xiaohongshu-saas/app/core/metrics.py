"""Minimal metrics facade.

Avoids making ``prometheus_client`` a hard dependency. If it's installed we
expose proper Prometheus text; otherwise we fall back to a tiny in-process
counter store that renders a compatible text payload.

Use:

    from app.core import metrics
    metrics.inc("publishes_total", status="success")
    payload = metrics.render()
"""
from __future__ import annotations

from threading import Lock
from typing import Dict, Tuple

try:
    from prometheus_client import CONTENT_TYPE_LATEST, Counter, generate_latest  # type: ignore

    _HAS_PROM = True
except Exception:  # noqa: BLE001
    _HAS_PROM = False
    CONTENT_TYPE_LATEST = "text/plain; version=0.0.4; charset=utf-8"
    generate_latest = None  # type: ignore

    class Counter:  # type: ignore[no-redef]
        def __init__(self, name: str, doc: str, labelnames: tuple = ()):
            self.name = name
            self.labelnames = labelnames
            self._lock = Lock()
            self._values: Dict[Tuple[Tuple[str, str], ...], float] = {}

        def labels(self, **labels):
            key = tuple(sorted(labels.items()))
            return _Labeled(self, key)

        def _inc(self, key: Tuple[Tuple[str, str], ...], value: float) -> None:
            with self._lock:
                self._values[key] = self._values.get(key, 0.0) + value

    class _Labeled:
        def __init__(self, owner: Counter, key: Tuple[Tuple[str, str], ...]) -> None:
            self._owner = owner
            self._key = key

        def inc(self, amount: float = 1.0) -> None:
            self._owner._inc(self._key, amount)


# ---- Module-level counters ----

publishes_total = Counter(
    "publishes_total",
    "Total publish attempts grouped by channel and status.",
    ("channel", "status"),
)

risk_blocks_total = Counter(
    "risk_blocks_total",
    "Total publish attempts blocked by risk-control.",
    ("account_id", "reason"),
)


# ---- Public API ----

def inc(metric_name: str, /, **labels: str) -> None:
    """Increment a module-level counter by name.

    Only counters defined in this module are reachable by name; unknown names
    raise ``KeyError`` so callers don't silently no-op.
    """
    counter = {"publishes_total": publishes_total, "risk_blocks_total": risk_blocks_total}[metric_name]
    counter.labels(**labels).inc()


def render() -> bytes:
    """Return Prometheus text-format payload."""
    if _HAS_PROM and generate_latest is not None:
        return generate_latest()
    # Fallback: render minimal text format for our own counters
    lines: list[str] = []
    for c in (publishes_total, risk_blocks_total):
        if isinstance(c, Counter) and hasattr(c, "_values"):
            for key, value in c._values.items():  # type: ignore[attr-defined]
                labels = ",".join(f'{k}="{v}"' for k, v in key)
                if labels:
                    lines.append(f"{c.name}{{{labels}}} {value}")
                else:
                    lines.append(f"{c.name} {value}")
    return ("\n".join(lines) + "\n").encode("utf-8")


__all__ = ["inc", "render", "publishes_total", "risk_blocks_total", "CONTENT_TYPE_LATEST"]


def install_fastapi_app(app) -> None:
    """Mount a GET /metrics endpoint on the given FastAPI app.

    Imported lazily by ``app.main`` to keep this module import-cost low.
    """
    from fastapi import Response

    @app.get("/metrics", include_in_schema=False)
    async def _metrics() -> Response:
        return Response(content=render(), media_type=CONTENT_TYPE_LATEST)