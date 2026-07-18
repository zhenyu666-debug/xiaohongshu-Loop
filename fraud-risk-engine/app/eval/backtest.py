"""Backtest harness for the fraud-detection layer.

Goal: take a :class:`GeneratedDataset` (which carries planted rings as
ground truth) and the local detector's :class:`RiskAlert` output, then
produce precision / recall / F1 numbers across a threshold sweep.

We deliberately avoid scikit-learn — everything is stdlib-friendly so
the harness runs in air-gapped CI.

Key concepts
------------

- **Ground truth**: a "guilty" account is one that appears in *any*
  planted ring in ``ds.planted_rings``. The set is deduped.
- **Predicted positives**: union of ``alerts[i].involved`` across all
  alerts whose ``score >= threshold``. Optionally we restrict by
  ``alert_kind`` so the sweep can target a single algorithm.
- **Per-threshold metrics**: precision = tp / (tp + fp),
  recall = tp / (tp + fn), F1 = 2 * p * r / (p + r). We also count
  total true positives at the alert-level (a ring fully covered counts
  once).

The HTML report is intentionally tiny (a few hundred lines) — no CDN,
no external assets — so the file is portable and CI-friendly.
"""

from __future__ import annotations

import html as html_lib
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence

from ..detection.models import RiskAlert
from ..loader.synth_generator import GeneratedDataset


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


@dataclass
class ThresholdRow:
    """One row in a threshold-sweep table."""

    threshold: float
    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int
    flagged_accounts: int

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class BacktestResult:
    """Full backtest report for a single dataset / alert pair."""

    run_id: str
    started_at: str
    ended_at: str
    seed: int
    planted_ring_count: int
    ground_truth_size: int
    thresholds: list[ThresholdRow]
    best_threshold: float
    best_f1: float
    detail: str = ""
    metrics: dict[str, float] = field(default_factory=dict)

    def to_dict(self) -> dict:
        out = asdict(self)
        out["thresholds"] = [r.to_dict() for r in self.thresholds]
        return out


# ---------------------------------------------------------------------------
# Core metric helpers
# ---------------------------------------------------------------------------


def _ground_truth_accounts(ds: GeneratedDataset) -> set[str]:
    """All accounts that appear in any planted ring."""
    guilty: set[str] = set()
    for ring in ds.planted_rings:
        for acct in ring.get("accounts", []):
            guilty.add(str(acct))
    return guilty


def _predicted_accounts(
    alerts: Sequence[RiskAlert],
    *,
    threshold: float,
    kinds: set[str] | None = None,
) -> set[str]:
    """Union of involved accounts across alerts whose score >= threshold.

    If ``kinds`` is given, only alerts whose ``kind`` is in the set count.
    """
    flagged: set[str] = set()
    for a in alerts:
        if a.score < threshold:
            continue
        if kinds is not None and a.kind not in kinds:
            continue
        for acct in a.involved:
            flagged.add(str(acct))
    return flagged


def _confusion(predicted: set[str], truth: set[str]) -> tuple[int, int, int]:
    """Return (tp, fp, fn)."""
    tp = len(predicted & truth)
    fp = len(predicted - truth)
    fn = len(truth - predicted)
    return tp, fp, fn


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if den else 0.0


def _metrics_for_threshold(
    alerts: Sequence[RiskAlert],
    truth: set[str],
    threshold: float,
    kinds: set[str] | None,
) -> ThresholdRow:
    pred = _predicted_accounts(alerts, threshold=threshold, kinds=kinds)
    tp, fp, fn = _confusion(pred, truth)
    precision = _safe_div(tp, tp + fp)
    recall = _safe_div(tp, tp + fn)
    f1 = _safe_div(2 * precision * recall, precision + recall)
    return ThresholdRow(
        threshold=round(threshold, 4),
        precision=round(precision, 4),
        recall=round(recall, 4),
        f1=round(f1, 4),
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        flagged_accounts=len(pred),
    )


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def default_threshold_grid() -> list[float]:
    """Reasonable default thresholds for sweeps.

    Includes the lower-bound 0.0 (catch-all) and upper-bound 1.0
    (catch-nothing) so the table anchors correctly.
    """
    return [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]


def backtest_run(
    alerts: Sequence[RiskAlert],
    ds: GeneratedDataset,
    *,
    seed: int,
    thresholds: Iterable[float] | None = None,
    kinds: set[str] | None = None,
) -> BacktestResult:
    """Score ``alerts`` against ``ds.planted_rings`` over a threshold grid.

    Parameters
    ----------
    alerts:
        Output of the local detector (or any compatible source).
    ds:
        The synthetic dataset that produced ``alerts``. Its planted
        rings are the ground truth.
    seed:
        Echoed back into the report for reproducibility.
    thresholds:
        Optional custom grid. Defaults to :func:`default_threshold_grid`.
    kinds:
        Optional alert-kind whitelist. ``None`` means "all alerts".
    """
    started = datetime.now(timezone.utc).isoformat(timespec="seconds")
    t0 = time.perf_counter()

    truth = _ground_truth_accounts(ds)
    grid = list(thresholds) if thresholds is not None else default_threshold_grid()

    rows = [_metrics_for_threshold(alerts, truth, t, kinds) for t in grid]

    best = max(rows, key=lambda r: r.f1) if rows else None
    best_threshold = best.threshold if best else 0.0
    best_f1 = best.f1 if best else 0.0

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    ended = datetime.now(timezone.utc).isoformat(timespec="seconds")

    # Per-kind recall @ best threshold is a nice summary line.
    per_kind: dict[str, float] = {}
    if best is not None:
        for k in {a.kind for a in alerts}:
            row = _metrics_for_threshold(alerts, truth, best.threshold, {k})
            per_kind[k] = row.recall

    metrics = {
        "elapsed_ms": float(elapsed_ms),
        "alerts_total": float(len(alerts)),
        "kinds_total": float(len({a.kind for a in alerts})),
        "truth_coverage_at_best": float(best.recall) if best else 0.0,
        "per_kind_recall_at_best": per_kind,
    }

    return BacktestResult(
        run_id=str(uuid.uuid4()),
        started_at=started,
        ended_at=ended,
        seed=seed,
        planted_ring_count=len(ds.planted_rings),
        ground_truth_size=len(truth),
        thresholds=rows,
        best_threshold=best_threshold,
        best_f1=best_f1,
        detail=f"Backtest over {len(alerts)} alerts against {len(truth)} ground-truth accounts",
        metrics=metrics,
    )


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------


def _row_html(row: ThresholdRow, best_t: float) -> str:
    cls = "best" if abs(row.threshold - best_t) < 1e-9 else ""
    return (
        f"<tr class='{cls}'>"
        f"<td>{row.threshold:.2f}</td>"
        f"<td>{row.precision:.3f}</td>"
        f"<td>{row.recall:.3f}</td>"
        f"<td>{row.f1:.3f}</td>"
        f"<td>{row.true_positives}</td>"
        f"<td>{row.false_positives}</td>"
        f"<td>{row.false_negatives}</td>"
        f"<td>{row.flagged_accounts}</td>"
        "</tr>"
    )


def render_backtest_html(result: BacktestResult) -> str:
    """Render the backtest result as a self-contained HTML document."""
    rows_html = "\n".join(_row_html(r, result.best_threshold) for r in result.thresholds)
    per_kind = result.metrics.get("per_kind_recall_at_best", {}) or {}
    per_kind_rows = "\n".join(
        f"<tr><td>{html_lib.escape(str(k))}</td><td>{float(v):.3f}</td></tr>"
        for k, v in sorted(per_kind.items())
    )
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>fraud-risk-engine · backtest {html_lib.escape(result.run_id[:8])}</title>
<style>
  body {{ font-family: ui-sans-serif, system-ui, sans-serif; margin: 2rem; color: #0f172a; }}
  h1 {{ margin-bottom: 0.25rem; }}
  .meta {{ color: #475569; font-size: 0.9rem; margin-bottom: 1.5rem; }}
  table {{ border-collapse: collapse; width: 100%; max-width: 880px; }}
  th, td {{ border: 1px solid #e2e8f0; padding: 0.4rem 0.6rem; text-align: right; }}
  th:first-child, td:first-child {{ text-align: left; }}
  th {{ background: #f1f5f9; }}
  tr.best {{ background: #ecfdf5; font-weight: 600; }}
  .grid {{ display: grid; grid-template-columns: 1fr 1fr; gap: 2rem; max-width: 880px; }}
  .card {{ border: 1px solid #e2e8f0; border-radius: 8px; padding: 1rem 1.25rem; }}
  .kv {{ display: flex; justify-content: space-between; padding: 0.2rem 0; }}
  .kv span:first-child {{ color: #475569; }}
</style>
</head>
<body>
  <h1>Backtest report</h1>
  <div class="meta">
    run <code>{html_lib.escape(result.run_id)}</code> ·
    seed {result.seed} ·
    planted_rings {result.planted_ring_count} ·
    ground truth {result.ground_truth_size} accounts
  </div>
  <div class="grid">
    <div class="card">
      <h2 style="margin-top:0">Best</h2>
      <div class="kv"><span>threshold</span><span>{result.best_threshold:.2f}</span></div>
      <div class="kv"><span>F1</span><span>{result.best_f1:.3f}</span></div>
      <div class="kv"><span>elapsed</span><span>{result.metrics.get("elapsed_ms", 0):.0f} ms</span></div>
      <div class="kv"><span>alerts</span><span>{int(result.metrics.get("alerts_total", 0))}</span></div>
    </div>
    <div class="card">
      <h2 style="margin-top:0">Per-kind recall @ best</h2>
      <table>
        <thead><tr><th>kind</th><th>recall</th></tr></thead>
        <tbody>
          {per_kind_rows or "<tr><td colspan=2><em>no alerts</em></td></tr>"}
        </tbody>
      </table>
    </div>
  </div>
  <h2>Threshold sweep</h2>
  <table>
    <thead>
      <tr>
        <th>threshold</th><th>precision</th><th>recall</th><th>F1</th>
        <th>TP</th><th>FP</th><th>FN</th><th>flagged</th>
      </tr>
    </thead>
    <tbody>
      {rows_html}
    </tbody>
  </table>
  <p class="meta">{html_lib.escape(result.detail)}</p>
</body>
</html>
"""


def write_backtest_html(result: BacktestResult, path: str | Path) -> Path:
    """Write the HTML report to ``path`` and return the resolved Path."""
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(render_backtest_html(result), encoding="utf-8")
    return p


__all__ = [
    "BacktestResult",
    "ThresholdRow",
    "backtest_run",
    "default_threshold_grid",
    "render_backtest_html",
    "write_backtest_html",
]
