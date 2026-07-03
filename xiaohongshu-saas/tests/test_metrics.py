"""Unit tests for the metrics facade."""
from __future__ import annotations

from app.core import metrics
from app.core.metrics import publishes_total, risk_blocks_total


def test_inc_publishes_total():
    metrics.inc("publishes_total", channel="xiaohongshu", status="success")
    metrics.inc("publishes_total", channel="xiaohongshu", status="success")
    metrics.inc("publishes_total", channel="xiaohongshu", status="failed")

    payload = metrics.render().decode()
    assert "publishes_total" in payload
    # Each counter line should include the channel label
    assert 'channel="xiaohongshu"' in payload


def test_inc_unknown_metric_raises():
    import pytest

    with pytest.raises(KeyError):
        metrics.inc("does_not_exist_total")


def test_inc_risk_blocks_total():
    metrics.inc("risk_blocks_total", account_id="acc_001", reason="daily")
    payload = metrics.render().decode()
    assert "risk_blocks_total" in payload
    assert 'reason="daily"' in payload


def test_counters_attribute_access():
    # Module-level handles should be available
    assert publishes_total is not None
    assert risk_blocks_total is not None


def test_render_returns_bytes():
    out = metrics.render()
    assert isinstance(out, bytes)
    assert len(out) > 0