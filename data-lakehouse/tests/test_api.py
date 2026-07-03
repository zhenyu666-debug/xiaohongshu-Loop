"""Pytest smoke test for lakehouse-api (no real Trino - relies on seed fallback)."""
from fastapi.testclient import TestClient

from lakehouse_api.main import app

client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "lakehouse-api"


def test_kpis_shape():
    r = client.get("/api/kpis")
    assert r.status_code == 200
    body = r.json()
    for k in ("pv_today", "uv_today", "pv_uv_ratio", "conversions_today", "funnel", "source"):
        assert k in body
    assert isinstance(body["funnel"], list)
    assert 2 <= len(body["funnel"]) <= 4
    assert body["pv_today"] > 0
    assert body["uv_today"] > 0


def test_series_pv_uv_conversions():
    for name in ("pv", "uv", "conversions"):
        r = client.get(f"/api/series/{name}?days=14")
        assert r.status_code == 200
        body = r.json()
        assert body["name"] == name
        assert len(body["points"]) == 14
        for p in body["points"]:
            assert "ts" in p
            assert "value" in p
            assert isinstance(p["value"], int)


def test_series_unknown_metric_422():
    r = client.get("/api/series/not_a_metric")
    assert r.status_code == 422


def test_top_items():
    r = client.get("/api/top-items?metric=pv&limit=5")
    assert r.status_code == 200
    body = r.json()
    assert body["metric"] == "pv"
    assert len(body["items"]) == 5
    counts = [it["count"] for it in body["items"]]
    assert counts == sorted(counts, reverse=True)