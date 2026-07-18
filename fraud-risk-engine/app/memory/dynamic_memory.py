"""Dynamic (volatile state) markdown memory.

The dynamic memory is regenerated on every detection run. It captures:

- the latest graph snapshot (counts)
- the last-N alerts grouped by severity
- the planted-rings metadata (from the generator)
- a "next-step" hint that the API surfaces to the frontend

Stored at ``data/output/MEMORY-DYNAMIC.md``.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
DYNAMIC_PATH = ROOT / "data" / "output" / "MEMORY-DYNAMIC.md"


def build_dynamic_memory(latest_run: dict[str, Any] | None, latest_dataset: Any) -> dict[str, Any]:
    """Build the dynamic memory markdown + return the API payload.

    ``latest_run`` is the dict form of :class:`DetectionRun` (or ``None``
    before the first run). ``latest_dataset`` is the
    :class:`GeneratedDataset` (or ``None``).
    """
    DYNAMIC_PATH.parent.mkdir(parents=True, exist_ok=True)

    parts: list[str] = []
    parts.append("# Dynamic Memory — fraud-risk-engine\n")
    parts.append(f"_Regenerated: {datetime.now(timezone.utc).isoformat(timespec='seconds')}_\n")

    if not latest_run:
        parts.append("\n## Status\n\nNo detection run has been executed yet.\n")
        parts.append("\nNext step: `POST /api/detector/run` to seed the graph and run detection.\n")
    else:
        snap = latest_run.get("snapshot", {})
        verts = snap.get("vertices", {})
        edges = snap.get("edges", {})
        planted = snap.get("planted_rings", [])

        parts.append("\n## Graph snapshot\n")
        parts.append("\n### Vertices\n")
        for v, n in sorted(verts.items()):
            parts.append(f"- **{v}**: {n}\n")
        parts.append("\n### Edges\n")
        for e, n in sorted(edges.items()):
            parts.append(f"- **{e}**: {n}\n")
        if planted:
            parts.append(f"\n### Planted fraud rings: {len(planted)}\n")
            for ring in planted[:5]:
                parts.append(
                    f"- ring_id={ring.get('ring_id')} "
                    f"accounts={len(ring.get('accounts', []))} "
                    f"device={ring.get('shared_device', '-')} "
                    f"ip={ring.get('shared_ip', '-')}\n"
                )

        alerts = latest_run.get("alerts", [])
        if alerts:
            sev_counts = Counter(a.get("severity", "n/a") for a in alerts)
            parts.append("\n## Most recent alerts\n")
            parts.append("\n| severity | kind | score | title |\n|---|---|---|---|\n")
            for a in alerts:
                parts.append(
                    f"| {a.get('severity')} | {a.get('kind')} | {a.get('score')} | {a.get('title')} |\n"
                )
            parts.append(f"\n> Severity mix: {dict(sev_counts)}\n")

        parts.append("\n## Next step\n")
        parts.append(
            f"\nLast run id `{latest_run.get('run_id')}` ended "
            f"at {latest_run.get('ended_at')} (status={latest_run.get('status')}). "
            "Re-run via `POST /api/detector/run` or open the Investigation view "
            "to drill down into the alerts.\n"
        )

    md = "".join(parts)
    DYNAMIC_PATH.write_text(md, encoding="utf-8")

    return {
        "ok": True,
        "path": str(DYNAMIC_PATH.relative_to(ROOT)),
        "title": "Dynamic Memory — fraud-risk-engine",
        "markdown": md,
        "char_count": len(md),
        "regenerated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "alert_count": len((latest_run or {}).get("alerts", [])),
    }