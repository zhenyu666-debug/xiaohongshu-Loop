"""Tests for the alerts engine."""
from __future__ import annotations

from app.api.alerts import record_event, _recent


def setup_function(_):
    _recent["risk_block"].clear()
    _recent["publish_fail"].clear()


def test_no_alert_below_threshold():
    assert record_event("risk_block", {"x": 1}) is None
    assert record_event("risk_block", {"x": 2}) is None


def test_critical_alert_on_3rd_risk_block():
    a1 = record_event("risk_block", {"i": 1})
    a2 = record_event("risk_block", {"i": 2})
    a3 = record_event("risk_block", {"i": 3})
    assert a1 is None and a2 is None
    assert a3 is not None
    assert a3["severity"] == "critical"
    assert a3["count_in_window"] == 3


def test_warning_alert_on_3rd_publish_fail():
    for i in range(3):
        record_event("publish_fail", {"i": i})
    out = record_event("publish_fail", {"i": 3})
    assert out is not None
    assert out["severity"] == "warning"


def test_unknown_event_silently_ignored():
    assert record_event("totally_unknown", {}) is None