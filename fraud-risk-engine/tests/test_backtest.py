"""Tests for :mod:`app.eval.backtest` — PR sweep + HTML report."""

from __future__ import annotations

import json

from app.detection.local_detector import run_local_detector
from app.eval.backtest import (
    BacktestResult,
    ThresholdRow,
    backtest_run,
    default_threshold_grid,
    render_backtest_html,
    write_backtest_html,
)
from app.loader.synth_generator import build_dataset


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_alerts(*, fraud_rings: int, seed: int = 20260716):
    ds = build_dataset(
        accounts=120,
        devices=80,
        merchants=20,
        transactions=2000,
        fraud_rings=fraud_rings,
        seed=seed,
    )
    run = run_local_detector(
        ds, ring_min_len=3, shared_device_min=3, burst_min_count=10, top_k=20,
    )
    return ds, run.alerts


# ---------------------------------------------------------------------------
# Smoke / shape
# ---------------------------------------------------------------------------


def test_backtest_run_returns_shape() -> None:
    ds, alerts = _build_alerts(fraud_rings=4)
    result = backtest_run(alerts, ds, seed=20260716)
    assert isinstance(result, BacktestResult)
    assert result.run_id
    assert result.planted_ring_count == 4
    assert result.ground_truth_size > 0
    assert result.thresholds, "threshold grid must not be empty"
    assert 0.0 <= result.best_f1 <= 1.0


def test_threshold_grid_default_has_endpoints() -> None:
    grid = default_threshold_grid()
    assert grid[0] == 0.0
    assert grid[-1] == 1.0
    assert len(grid) >= 5


def test_threshold_row_to_dict_round_trip() -> None:
    ds, alerts = _build_alerts(fraud_rings=3)
    result = backtest_run(alerts, ds, seed=20260716)
    sample = result.thresholds[0]
    assert isinstance(sample, ThresholdRow)
    d = sample.to_dict()
    for k in ("threshold", "precision", "recall", "f1", "true_positives",
              "false_positives", "false_negatives", "flagged_accounts"):
        assert k in d


# ---------------------------------------------------------------------------
# Metric semantics
# ---------------------------------------------------------------------------


def test_threshold_zero_recalls_everything() -> None:
    """At threshold 0.0 every alert counts, so recall must be ≥ any higher threshold."""
    ds, alerts = _build_alerts(fraud_rings=4)
    result = backtest_run(alerts, ds, seed=20260716)
    rows_by_t = {r.threshold: r for r in result.thresholds}
    assert rows_by_t[0.0].recall >= rows_by_t[0.5].recall


def test_threshold_one_recalls_nothing_or_only_high_score() -> None:
    """At threshold 1.0 only alerts with score == 1.0 count → recall is ≤ any lower threshold."""
    ds, alerts = _build_alerts(fraud_rings=4)
    result = backtest_run(alerts, ds, seed=20260716)
    rows_by_t = {r.threshold: r for r in result.thresholds}
    if rows_by_t[1.0].flagged_accounts == 0:
        assert rows_by_t[1.0].recall == 0.0
    else:
        # If any alert reaches a perfect 1.0 score, recall is still bounded
        # above by the recall at threshold 0.0.
        assert rows_by_t[1.0].recall <= rows_by_t[0.0].recall


def test_kinds_filter_only_counts_selected_alert_kinds() -> None:
    ds, alerts = _build_alerts(fraud_rings=4)
    unfiltered = backtest_run(alerts, ds, seed=20260716)
    only_rings = backtest_run(
        alerts, ds, seed=20260716, kinds={"transaction_ring"}
    )
    # Filtering to a single kind must produce a flagged set no larger than the union.
    unflagged_total = unfiltered.thresholds[-1].flagged_accounts
    filtered_total = only_rings.thresholds[-1].flagged_accounts
    assert filtered_total <= unflagged_total


def test_precision_recall_bounded_between_zero_and_one() -> None:
    ds, alerts = _build_alerts(fraud_rings=5)
    result = backtest_run(alerts, ds, seed=20260716)
    for r in result.thresholds:
        assert 0.0 <= r.precision <= 1.0
        assert 0.0 <= r.recall <= 1.0
        assert 0.0 <= r.f1 <= 1.0


# ---------------------------------------------------------------------------
# HTML report
# ---------------------------------------------------------------------------


def test_html_report_renders() -> None:
    ds, alerts = _build_alerts(fraud_rings=3)
    result = backtest_run(alerts, ds, seed=20260716)
    html = render_backtest_html(result)
    assert html.startswith("<!doctype html>")
    assert "Backtest report" in html
    assert f"{result.best_threshold:.2f}" in html
    assert "<table>" in html
    # Best row is highlighted
    assert "class='best'" in html


def test_html_report_to_dict_is_json_serializable(tmp_path) -> None:
    """The full report round-trips through JSON for archival."""
    ds, alerts = _build_alerts(fraud_rings=3)
    result = backtest_run(alerts, ds, seed=20260716)
    payload = result.to_dict()
    json.dumps(payload)  # must not raise
    out = write_backtest_html(result, tmp_path / "report.html")
    assert out.exists()
    assert out.stat().st_size > 1000


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_empty_alerts_produces_zero_metrics() -> None:
    """No alerts → no TP/FP, recall == 0, precision stays 0 by convention."""
    ds, alerts = _build_alerts(fraud_rings=2)
    result = backtest_run([], ds, seed=20260716)
    for r in result.thresholds:
        assert r.true_positives == 0
        assert r.false_positives == 0
        assert r.f1 == 0.0
    assert result.best_f1 == 0.0


def test_no_planted_rings_produces_all_zero_recall() -> None:
    """If the dataset has no planted rings, recall is 0 everywhere by definition."""
    ds, alerts = _build_alerts(fraud_rings=0)
    result = backtest_run(alerts, ds, seed=20260716)
    assert result.planted_ring_count == 0
    assert result.ground_truth_size == 0
    for r in result.thresholds:
        assert r.recall == 0.0
        assert r.f1 == 0.0
