"""Static (decision / architecture) markdown memory.

Stored as a single checked-in Markdown file at
``docs/MEMORY-STATIC.md``. The static memory is curated — it captures
long-lived facts that the agent should be able to recall even if the
runtime is cold.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
STATIC_PATH = ROOT / "docs" / "MEMORY-STATIC.md"


STATIC_TEMPLATE = """# Static Memory — fraud-risk-engine

## Identity

- **Project:** fraud-risk-engine
- **Goal:** TigerGraph-backed financial fraud risk detection engine with
  multi-view visualization (Multi-view + Dashboard + Investigation).
- **Sponsor:** single-developer workspace at
  ``c:\\\\Users\\\\Hasee\\\\.qclaw\\\\workspace\\\\get_jobs\\\\fraud-risk-engine``.

## Long-lived decisions

1. **Deployment topology.** TigerGraph runs locally as a Docker container
   on top of WSL2 / Docker Desktop. The Windows host talks to the
   container via ``http://localhost:14240`` (RESTPP) using ``httpx``.
2. **Data sources.** Synthetic data generator only. No live feed, no
   third-party data, no real PII.
3. **Detection backend.** Both TigerGraph (GSQL) and a fully
   backend-equivalent local in-memory implementation are first-class.
   The frontend hits ``/api/detector/run`` with ``backend=auto`` so the
   API transparently falls back when the runtime is not reachable.
4. **Multi-view visualisation.** Three surfaces:
   - **Multi-view panel** — high-density scatter + sankey overview
   - **Dashboard** — KPI cards + time-series + alert timeline
   - **Investigation** — node focus panel with evidence chain
5. **Memory layer.** Dual Markdown memory:
   - ``docs/MEMORY-STATIC.md`` (this file) — curated, checked-in
   - ``data/output/MEMORY-DYNAMIC.md`` — regenerated on every detector
     run, captures the most recent graph snapshot + alerts

## Invariants

- The package depends only on ``fastapi``, ``uvicorn``, ``pydantic``,
  ``httpx`` and the Python standard library. The visual stack
  (Streamlit / Plotly / pandas) is optional and not required for tests.
- All RNG / sampling uses an explicit ``seed`` so the synthetic dataset
  is reproducible.
- TigerGraph connection failures **never** raise — every loader /
  detector returns a structured ``LoaderResult`` / ``DetectionRun``
  with ``status`` set to ``degraded`` or ``unreachable``.
"""


def ensure_static_memory() -> Path:
    """Create the static memory file on first run (idempotent)."""
    STATIC_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not STATIC_PATH.exists():
        STATIC_PATH.write_text(STATIC_TEMPLATE, encoding="utf-8")
    return STATIC_PATH


def load_static_memory() -> dict[str, Any]:
    """Return the static memory as a structured object for the API."""
    path = ensure_static_memory()
    text = path.read_text(encoding="utf-8")
    return {
        "ok": True,
        "path": str(path.relative_to(ROOT)),
        "title": "Static Memory — fraud-risk-engine",
        "markdown": text,
        "char_count": len(text),
        "loaded_at": _now_iso(),
    }


def _now_iso() -> str:
    from datetime import datetime, timezone

    return datetime.now(timezone.utc).isoformat(timespec="seconds")