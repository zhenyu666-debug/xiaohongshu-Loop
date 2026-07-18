"""Tests for the FastAPI surface.

We use the FastAPI ``TestClient`` which is bundled with FastAPI >= 0.21,
so no extra pytest plugins required.
"""

from __future__ import annotations

import tempfile

import pytest
from fastapi.testclient import TestClient

from app.api import app, STATE


@pytest.fixture(autouse=True)
def _reset_state():
    """Isolate each test: clear STATE before and after so no test bleeds into the next."""
    STATE["latest_dataset"] = None
    STATE["latest_run"] = None
    STATE["latest_run_id"] = None
    yield
    STATE["latest_dataset"] = None
    STATE["latest_run"] = None
    STATE["latest_run_id"] = None


def _tmp_seed_dir():
    return tempfile.mkdtemp()


def _client() -> TestClient:
    return TestClient(app)


def test_health_endpoint() -> None:
    with _client() as c:
        r = c.get("/api/health")
        assert r.status_code == 200
        data = r.json()
        assert data["ok"] is True
        assert data["service"] == "fraud-risk-engine"


def test_dataset_build_and_summary_roundtrip(tmp_path, monkeypatch) -> None:
    from app import api as api_module

    monkeypatch.setattr(api_module, "DATA_SEED_DIR", tmp_path / "seed")
    with _client() as c:
        r = c.post("/api/dataset", json={})
        assert r.status_code == 200
        manifest = r.json()["manifest"]
        assert manifest["totals"]["accounts"] >= 100
        r = c.get("/api/dataset")
        assert r.status_code == 200


def test_detector_run_local_backend(monkeypatch) -> None:
    from app import api as api_module

    monkeypatch.setattr(api_module, "DATA_SEED_DIR", _tmp_seed_dir())
    with _client() as c:
        r = c.post("/api/detector/run", json={"backend": "local"})
        assert r.status_code == 200
        run = r.json()
        assert run["status"] == "ok"
        assert run["backend"].startswith("local") or run["backend"].startswith("tigergraph")
        assert len(run["alerts"]) >= 1


def test_memory_static_endpoint() -> None:
    with _client() as c:
        r = c.get("/api/memory/static")
        assert r.status_code == 200
        body = r.json()
        assert body["ok"] is True
        assert "fraud-risk-engine" in body["markdown"]


def test_memory_dynamic_endpoint() -> None:
    with _client() as c:
        c.post("/api/detector/run", json={"backend": "local"})
        r = c.get("/api/memory/dynamic")
        assert r.status_code == 200
        body = r.json()
        assert body["alert_count"] >= 1
        assert "Graph snapshot" in body["markdown"]


# ------------------------------------------------------------------
# Profile / multi-hop BFS
# ------------------------------------------------------------------


def test_profile_bfs_endpoint_requires_dataset(monkeypatch) -> None:
    """Profile endpoint must fail with 400 when no dataset is loaded."""
    from app import api as api_module

    monkeypatch.setattr(api_module, "DATA_SEED_DIR", _tmp_seed_dir())
    STATE["latest_dataset"] = None
    with _client() as c:
        r = c.get("/api/profile/A000000")
        assert r.status_code == 400
        assert "no dataset" in r.json()["detail"]


def test_profile_bfs_endpoint_returns_both_graphs(monkeypatch) -> None:
    """After loading a dataset, /api/profile/{id} returns identity + funds subgraphs."""
    from app import api as api_module
    from app.loader.synth_generator import build_dataset

    monkeypatch.setattr(api_module, "DATA_SEED_DIR", _tmp_seed_dir())
    # Directly seed STATE so profile endpoint finds it (local detector builds
    # a dataset internally but does not persist it to STATE["latest_dataset"]).
    STATE["latest_dataset"] = build_dataset(seed=20260718)
    with _client() as c:
        r = c.get("/api/profile/A000000")
        assert r.status_code == 200, f"got {r.status_code}: {r.text}"
        body = r.json()
        assert "identity" in body
        assert "funds" in body
        assert body["identity"]["root_id"] == "A000000"
        assert body["identity"]["mode"] == "identity"
        assert body["funds"]["mode"] == "funds"
        assert "stats" in body["identity"]
        assert "stats" in body["funds"]


def test_profile_single_graph_identity(monkeypatch) -> None:
    from app import api as api_module
    from app.loader.synth_generator import build_dataset

    monkeypatch.setattr(api_module, "DATA_SEED_DIR", _tmp_seed_dir())
    STATE["latest_dataset"] = build_dataset(seed=20260718)
    with _client() as c:
        r = c.get("/api/profile/A000000/graph/identity")
        assert r.status_code == 200, f"got {r.status_code}: {r.text}"
        body = r.json()
        assert body["mode"] == "identity"
        assert "nodes" in body
        assert "edges" in body


def test_profile_single_graph_funds(monkeypatch) -> None:
    from app import api as api_module
    from app.loader.synth_generator import build_dataset

    monkeypatch.setattr(api_module, "DATA_SEED_DIR", _tmp_seed_dir())
    STATE["latest_dataset"] = build_dataset(seed=20260718)
    with _client() as c:
        r = c.get("/api/profile/A000000/graph/funds?max_hops=3")
        assert r.status_code == 200, f"got {r.status_code}: {r.text}"
        body = r.json()
        assert body["mode"] == "funds"
        assert body["stats"]["cumulative_amount"] >= 0.0
