# Tests for the BankFraud xlsx loader.

from app.loader.bankfraud_loader import build_api_response, build_graph, compute_stats


def _fixture_rows(n_total=60, fraud_count=30):
    rows=[]
    for i in range(n_total):
        rows.append(dict(id=f"R{i+1}", is_fraud=1 if i< fraud_count else 0, features=[float(i%7)/7.0]*7))
    return rows


def test_build_graph_default_fraud_ratio_is_respected():
    rows = _fixture_rows(n_total=60, fraud_count=30)
    graph = build_graph(rows, sample_size=30, fraud_ratio=0.5, seed=7)
    fraud_nodes = [n for n in graph["nodes"] if n["is_fraud"] == 1]
    assert len(fraud_nodes) == 15


def test_build_graph_n_fraud_overrides_ratio():
    rows = _fixture_rows(n_total=60, fraud_count=30)
    graph = build_graph(rows, sample_size=10, fraud_ratio=0.5, n_fraud=8, seed=7)
    fraud_nodes = [n for n in graph["nodes"] if n["is_fraud"] == 1]
    normal_nodes = [n for n in graph["nodes"] if n["is_fraud"] == 0]
    assert len(fraud_nodes) == 8
    assert len(normal_nodes) == 2


def test_build_graph_n_fraud_clamps_to_available():
    rows = _fixture_rows(n_total=10, fraud_count=3)
    graph = build_graph(rows, sample_size=100, fraud_ratio=0.5, n_fraud=50, seed=1)
    fraud_nodes = [n for n in graph["nodes"] if n["is_fraud"] == 1]
    assert len(fraud_nodes) == 3


def test_build_graph_n_fraud_zero_means_no_fraud():
    rows = _fixture_rows(n_total=20, fraud_count=10)
    graph = build_graph(rows, sample_size=10, fraud_ratio=0.5, n_fraud=0, seed=1)
    fraud_nodes = [n for n in graph["nodes"] if n["is_fraud"] == 1]
    assert len(fraud_nodes) == 0
    assert len(graph["nodes"]) == 10


def test_build_api_response_threads_n_fraud_through():
    rows = _fixture_rows(n_total=80, fraud_count=40)
    resp = build_api_response(rows=rows, sample_size=40, fraud_ratio=0.5, n_fraud=12)
    assert resp["ok"] is True
    fraud_nodes = [n for n in resp["nodes"] if n["is_fraud"] == 1]
    assert len(fraud_nodes) == 12
    # stats report the source pool, not the sampled graph
    assert resp["stats"]["fraud_count"] == 40
    assert resp["total_rows"] == 80


def test_compute_stats_is_independent_of_n_fraud():
    rows = _fixture_rows(n_total=80, fraud_count=40)
    stats = compute_stats(rows)
    assert stats["fraud_count"] == 40
    assert stats["normal_count"] == 40
    assert stats["total_count"] == 80
    assert stats["fraud_rate"] == 50.0


def test_build_graph_n_fraud_negative_falls_back_to_ratio():
    rows = _fixture_rows(n_total=40, fraud_count=20)
    graph = build_graph(rows, sample_size=10, fraud_ratio=0.5, n_fraud=-3, seed=2)
    fraud_nodes = [n for n in graph["nodes"] if n["is_fraud"] == 1]
    assert len(fraud_nodes) == 5
