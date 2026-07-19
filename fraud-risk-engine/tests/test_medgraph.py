"""Tests for the Synthea MedGraph synthetic data generator + API endpoint."""

from __future__ import annotations

from fastapi.testclient import TestClient

from app.api import app


def _client() -> TestClient:
    return TestClient(app)


def test_medgraph_sample_basic() -> None:
    c = _client()
    r = c.get("/api/medgraph/sample?n_patients=20&seed=42")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["source"] == "Synthea MedGraph (synthetic)"
    assert body["seed"] == 42
    assert body["stats"]["patient_count"] == 20
    assert body["stats"]["encounter_count"] > 0
    assert body["stats"]["condition_count"] > 0
    assert body["stats"]["provider_count"] == 10  # fixed pool of 10 providers
    assert body["stats"]["payer_count"] == 7  # fixed pool of 7 payers


def test_medgraph_graph_structure() -> None:
    c = _client()
    r = c.get("/api/medgraph/sample?n_patients=30&seed=123")
    assert r.status_code == 200
    body = r.json()

    nodes = body["nodes"]
    edges = body["edges"]
    node_kinds = {n["kind"] for n in nodes}
    edge_kinds = {e["kind"] for e in edges}

    # Verify all node kinds present
    for kind in ["patient", "encounter", "condition", "medication", "provider", "payer"]:
        assert kind in node_kinds, f"missing node kind: {kind}"

    # Verify edges connect existing nodes
    node_ids = {n["id"] for n in nodes}
    for e in edges:
        assert e["source"] in node_ids
        assert e["target"] in node_ids


def test_medgraph_patient_detail() -> None:
    c = _client()
    # Generate a sample first to get a valid patient id
    r = c.get("/api/medgraph/sample?n_patients=10&seed=42")
    assert r.status_code == 200
    body = r.json()
    first_patient_id = body["patients"][0]["id"]

    # Fetch detail for that patient
    r2 = c.get(f"/api/medgraph/patient/{first_patient_id}")
    assert r2.status_code == 200
    detail = r2.json()
    assert detail["patient"]["id"] == first_patient_id
    assert "name" in detail["patient"]
    assert "encounters" in detail
    assert "conditions" in detail
    assert "medications" in detail


def test_medgraph_patient_not_found() -> None:
    c = _client()
    r = c.get("/api/medgraph/patient/NONEXISTENT-PAT-XXXXX")
    assert r.status_code == 404


def test_medgraph_deterministic_seed() -> None:
    c = _client()
    r1 = c.get("/api/medgraph/sample?n_patients=15&seed=999")
    r2 = c.get("/api/medgraph/sample?n_patients=15&seed=999")
    assert r1.json() == r2.json(), "same seed must produce same graph"


def test_medgraph_schema_files_present() -> None:
    """GSQL schema files should be on disk under app/queries/medgraph/."""
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "app" / "queries" / "medgraph"
    schema = base / "medgraph_schema.gsql"
    assert schema.exists(), f"missing schema file: {schema}"

    content = schema.read_text(encoding="utf-8")
    assert "CREATE VERTEX Patient" in content
    assert "CREATE VERTEX Encounter" in content
    assert "CREATE VERTEX Conditions" in content
    assert "CREATE VERTEX Medication" in content
    assert "CREATE GRAPH MedGraph" in content


def test_medgraph_query_files_present() -> None:
    """All MedGraph query files should be on disk."""
    from pathlib import Path

    base = Path(__file__).resolve().parents[1] / "app" / "queries" / "medgraph"
    expected = [
        "get_patient_conditions.gsql",
        "get_patient_codes.gsql",
        "get_code_cost.gsql",
        "get_cost_outliers.gsql",
        "check_distance.gsql",
        "cosine_patient_demographics.gsql",
    ]
    for fn in expected:
        assert (base / fn).exists(), f"missing query: {fn}"
