"""Pytest smoke test for pbp-api (no real DB, just exercises demo dataset)."""
from fastapi.testclient import TestClient

from pbp_api.main import app

client = TestClient(app)


def test_healthz():
    r = client.get("/healthz")
    assert r.status_code == 200
    body = r.json()
    assert body["status"] == "ok"
    assert body["service"] == "pbp-api"


def test_top20_shape():
    r = client.get("/api/candidates/top20")
    assert r.status_code == 200
    body = r.json()
    assert "items" in body
    assert len(body["items"]) == 20
    first = body["items"][0]
    assert "id" in first
    assert "score" in first
    assert "rank" in first
    assert first["rank"] == 1
    # scores should be descending
    scores = [c["score"] for c in body["items"]]
    assert scores == sorted(scores, reverse=True)


def test_distribution_buckets():
    r = client.get("/api/candidates/distribution?buckets=5")
    assert r.status_code == 200
    body = r.json()
    assert body["buckets"] == 5
    assert len(body["items"]) == 5
    assert sum(b["count"] for b in body["items"]) > 0


def test_filter_score_range():
    r = client.get("/api/candidates?score_min=0.9&limit=50")
    assert r.status_code == 200
    body = r.json()
    for c in body["items"]:
        assert c["score"] >= 0.9


def test_404_on_missing():
    r = client.get("/api/candidates/99999")
    assert r.status_code == 404