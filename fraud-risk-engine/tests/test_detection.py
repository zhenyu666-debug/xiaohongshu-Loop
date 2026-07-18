"""Tests for the detection layer."""

from __future__ import annotations

from app.detection import (
    betweenness_alert_from_gsql,
    burst_alert_from_gsql,
    closeness_alert_from_gsql,
    jaccard_alert_from_gsql,
    lpcc_alert_from_gsql,
    pagerank_alert_from_gsql,
    ring_alert_from_gsql,
    run_local_detector,
    shared_device_alert_from_gsql,
    wcc_alert_from_gsql,
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


# ---------------------------------------------------------------------------
# GDSL algorithm alert factories
# ---------------------------------------------------------------------------


def test_wcc_alert_processor() -> None:
    payload = {
        "results": [{
            "components": {
                "A0": {"comp_id": "C0"}, "A1": {"comp_id": "C0"},
                "A2": {"comp_id": "C1"}, "A3": {"comp_id": "C1"},
                "A4": {"comp_id": "C1"}, "A5": {"comp_id": "C2"},
            },
            "vertexCount": 6,
        }]
    }
    a = wcc_alert_from_gsql(payload)
    assert a is not None
    assert a.kind == "connected_component"
    assert a.evidence["distinct_components"] == 3
    assert a.evidence["largest_size"] == 3


def test_wcc_alert_empty() -> None:
    assert wcc_alert_from_gsql({"results": []}) is None
    assert wcc_alert_from_gsql({"results": [{"components": {}, "vertexCount": 0}]}) is None


def test_lpcc_alert_processor() -> None:
    payload = {
        "results": [{
            "topCommunities": [
                {"cnt": 12, "label": "G0"},
                {"cnt": 8, "label": "G1"},
                {"cnt": 3, "label": "G2"},
            ],
            "communityCount": 3,
            "vertexCount": 23,
        }]
    }
    a = lpcc_alert_from_gsql(payload)
    assert a is not None
    assert a.kind == "community"
    assert a.evidence["community_count"] == 3
    assert a.evidence["large_community_labels"] == ["G0", "G1"]


def test_lpcc_alert_empty() -> None:
    assert lpcc_alert_from_gsql({"results": []}) is None
    assert lpcc_alert_from_gsql({"results": [{"topCommunities": [], "communityCount": 0}]}) is None


def test_jaccard_alert_processor() -> None:
    payload = {
        "results": [{
            "source_target_jaccard": 0.65,
            "intersectionSize": 5,
            "unionSize": 8,
            "topSimilarAccounts": ["A2", "A3", "A4"],
        }]
    }
    a = jaccard_alert_from_gsql(payload)
    assert a is not None
    assert a.kind == "jaccard_similarity"
    assert a.evidence["source_target_jaccard"] == 0.65
    assert len(a.evidence["top_similar_accounts"]) == 3
    assert a.severity == "critical"  # >= 0.5 threshold


def test_jaccard_alert_medium() -> None:
    payload = {"results": [{"source_target_jaccard": 0.35, "intersectionSize": 2,
                           "unionSize": 6, "topSimilarAccounts": []}]}
    a = jaccard_alert_from_gsql(payload)
    assert a is not None
    assert a.severity == "high"  # 0.3–0.5


def test_jaccard_alert_empty() -> None:
    assert jaccard_alert_from_gsql({"results": [{"source_target_jaccard": 0, "topSimilarAccounts": []}]}) is None


def test_betweenness_alert_processor() -> None:
    payload = {
        "results": [{
            "topBetweennessAccounts": [
                {"score": 15.3, "v_id": "A0"},
                {"score": 9.1, "v_id": "A2"},
                {"score": 4.0, "v_id": "A5"},
            ],
            "totalBetweenness": 28.4,
            "verticesProcessed": 100,
        }]
    }
    a = betweenness_alert_from_gsql(payload)
    assert a is not None
    assert a.kind == "betweenness"
    assert a.evidence["vertices_processed"] == 100
    assert len(a.evidence["top_betweenness"]) == 3
    assert a.severity == "high"  # max_score >= 10


def test_betweenness_alert_empty() -> None:
    assert betweenness_alert_from_gsql({"results": []}) is None
    assert betweenness_alert_from_gsql({"results": [{"topBetweennessAccounts": []}]}) is None


def test_closeness_alert_processor() -> None:
    payload = {
        "results": [{
            "topClosenessAccounts": [
                {"score": 2.8, "v_id": "A0"},
                {"score": 2.1, "v_id": "A1"},
            ],
            "vertexCount": 120,
        }]
    }
    a = closeness_alert_from_gsql(payload)
    assert a is not None
    assert a.kind == "closeness"
    assert a.evidence["vertex_count"] == 120
    assert len(a.evidence["top_closeness"]) == 2
