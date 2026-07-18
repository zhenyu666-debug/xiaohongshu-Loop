"""Tests for the detection layer."""

from __future__ import annotations

from app.detection import (
    burst_alert_from_gsql,
    pagerank_alert_from_gsql,
    ring_alert_from_gsql,
    run_local_detector,
    shared_device_alert_from_gsql,
)
from app.loader.synth_generator import build_dataset


def test_local_detector_finds_planted_alerts() -> None:
    ds = build_dataset(
        accounts=120, devices=80, merchants=20, transactions=2000,
        fraud_rings=4, seed=20260716,
    )
    run = run_local_detector(
        ds, ring_min_len=3, shared_device_min=3, burst_min_count=10, top_k=20,
    )
    assert run.status == "ok"
    assert {a.kind for a in run.alerts} >= {
        "transaction_ring",
        "shared_device",
        "burst_transactions",
        "pagerank",
    }
    assert run.snapshot.vertices["Account"] >= 120
    assert run.snapshot.edges["USES_DEVICE"] > 0


def test_ring_alert_post_processor() -> None:
    payload = {"results": [{"ringCount": 6, "accountIds": ["A001", "A017", "A023"]}]}
    a = ring_alert_from_gsql(payload)
    assert a is not None
    assert a.kind == "transaction_ring"
    assert a.evidence["ring_count"] == 6


def test_ring_alert_post_processor_handles_empty() -> None:
    assert ring_alert_from_gsql({"results": [{"ringCount": 0}]}) is None
    assert ring_alert_from_gsql({"results": []}) is None


def test_shared_device_post_processor() -> None:
    payload = {
        "results": [{
            "sharedDeviceIds": ["D01", "D02", "D03"],
            "accountsByDevice": {"D01": ["A1", "A2", "A3"], "D02": ["A4", "A5", "A6", "A7"]},
        }]
    }
    a = shared_device_alert_from_gsql(payload)
    assert a is not None
    assert a.evidence["affected_accounts"] >= 7
    assert a.severity in {"medium", "high", "critical"}


def test_burst_post_processor() -> None:
    payload = {"results": [{"txCountByAccount": {"A1": 30, "A2": 12, "A3": 5}}]}
    a = burst_alert_from_gsql(payload)
    assert a is not None
    # only A1 and A2 satisfy minCount=12
    assert set(a.evidence["tx_count_by_account"].keys()) == {"A1", "A2"}


def test_pagerank_post_processor() -> None:
    payload = {"results": [{"topAccounts": ["A1", "A2", "A3"], "sampleScore": 7}]}
    a = pagerank_alert_from_gsql(payload, top_k=3)
    assert a is not None
    assert len(a.involved) == 3
    assert a.evidence["topK"] == 3
