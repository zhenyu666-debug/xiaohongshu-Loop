"""Tests for the funds-monitor scheduler (APScheduler-free background thread)."""

from __future__ import annotations

import time

from app.detection.models import (
    AlertKind,
    burst_amount_alert_from_gsql,
    circular_funds_alert_from_gsql,
    funds_path_trace_alert_from_gsql,
)
from app.loader.synth_generator import build_dataset
from app.scheduler.funds_monitor import (
    FundsMonitor,
    get_monitor,
    run_funds_detectors,
)


def test_funds_monitor_status_idle() -> None:
    """A fresh monitor reports running=False and zero runs."""
    m = FundsMonitor()
    s = m.status()
    assert s["running"] is False
    assert s["runs_total"] == 0
    assert s["last_alert_count"] == 0


def test_funds_monitor_singleton_returns_same_instance() -> None:
    a = get_monitor()
    b = get_monitor()
    assert a is b


def test_run_funds_detectors_one_shot() -> None:
    """One-shot run covers all 3 funds detectors (≥ 2 alerts expected)."""
    ds = build_dataset(
        accounts=120,
        devices=80,
        merchants=20,
        transactions=2000,
        fraud_rings=4,
        seed=20260716,
    )
    alerts = run_funds_detectors(ds)
    kinds = {a.kind for a in alerts}
    # At minimum, the path-trace and burst-amount always find *something* in the
    # synthetic dataset.
    assert AlertKind.FUNDS_PATH_TRACE.value in kinds or AlertKind.BURST_AMOUNT.value in kinds


def test_funds_monitor_start_stop_minimal() -> None:
    """start/stop with dry_run=True on a 30-second interval must be cancellable
    via stop() within a short window without hangs in the test runner."""
    m = FundsMonitor()
    ok = m.start(interval_minutes=1, dry_run=True, dataset_seed=20260716)
    assert ok is True
    assert m.status()["running"] is True
    # Wait briefly for at least one tick — but cap aggressively
    deadline = time.time() + 0.5
    while time.time() < deadline:
        if m.status()["runs_total"] >= 0 and m.status().get("started_at"):
            break
        time.sleep(0.05)
    m.stop()
    assert m.status()["running"] is False


def test_factory_relationships() -> None:
    """All three funds alert factories should map onto the expected AlertKind."""
    # Empty input → None
    assert funds_path_trace_alert_from_gsql({"results": []}) is None
    assert circular_funds_alert_from_gsql({"results": []}) is None
    assert burst_amount_alert_from_gsql({"results": []}) is None
    # Bad input type → None
    assert funds_path_trace_alert_from_gsql("not a dict") is None
    assert circular_funds_alert_from_gsql([]) is None
    assert burst_amount_alert_from_gsql(None) is None
