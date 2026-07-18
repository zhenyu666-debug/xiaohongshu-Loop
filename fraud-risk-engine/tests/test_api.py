"""Tests for the FastAPI surface.

We use the FastAPI ``TestClient`` which is bundled with FastAPI >= 0.21,
so no extra pytest plugins required.
"""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import app, STATE
from app.config import get_settings


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
    # Patch DATA_SEED_DIR to a tmp path so we don't pollute the repo.
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

    monkeypatch.setattr(api_module, "DATA_SEED_DIR", tmp_path_factory())  # type: ignore[name-defined]
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


# Local helper (pyfixture-free).
def tmp_path_factory():
    import tempfile
    return tempfile.mkdtemp()
