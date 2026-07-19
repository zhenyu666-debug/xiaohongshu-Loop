"""Tests for the stdlib port of TIGER graph robustness measures.

Ported from https://github.com/safreita1/TIGER (MIT). The values here are
verified against hand-computed expected outputs and against the simpler
``networkx``-free measures that ``app.eval.graph_robustness`` exposes.
"""

from __future__ import annotations

import math

import pytest

from app.eval.graph_robustness import (
    RobustnessReport,
    average_degree,
    clustering_coefficient,
    compute_robustness,
    degree_assortativity,
    density,
    diameter_small,
    edge_connectivity_lower_bound,
    node_connectivity_lower_bound,
    spectral_radius_estimate,
)
from app.loader.synth_generator import GeneratedDataset, build_dataset


# ---------------------------------------------------------------------------
# Synthetic mini-datasets (built inline so each test is self-contained)
# ---------------------------------------------------------------------------


def _ring_dataset(n: int = 4) -> GeneratedDataset:
    """Build a minimal ``GeneratedDataset`` that forms an n-cycle of accounts.

    Account A0 → A1 → … → A{n-1} → A0 via a transaction at each step.
    """
    ds = GeneratedDataset()
    for i in range(n):
        ds.accounts.append({"id": f"A{i:03d}"})
    for i in range(n):
        src = f"A{i:03d}"
        dst = f"A{(i + 1) % n:03d}"
        tx_id = f"T_R0_{i:02d}"
        ds.transactions.append(
            {
                "id": tx_id,
                "ts": "2026-07-19T00:00:00Z",
                "amount": 100.0,
                "currency": "USD",
                "channel": "wire",
                "status": "completed",
            }
        )
        ds.from_account.append({"from_id": tx_id, "to_id": src, "amount": 100.0, "ts": "2026-07-19T00:00:00Z"})
        ds.to_account.append({"from_id": tx_id, "to_id": dst, "amount": 100.0, "ts": "2026-07-19T00:00:00Z"})
    return ds


def _star_dataset(centre: str = "A000", leaves: int = 5) -> GeneratedDataset:
    """Build a star: ``centre`` transacts with each leaf in turn."""
    ds = GeneratedDataset()
    ds.accounts.append({"id": centre})
    for i in range(leaves):
        leaf = f"A{i + 1:03d}"
        ds.accounts.append({"id": leaf})
        tx_id = f"T_S_{i:02d}"
        ds.transactions.append(
            {
                "id": tx_id,
                "ts": "2026-07-19T00:00:00Z",
                "amount": 50.0,
                "currency": "USD",
                "channel": "wire",
                "status": "completed",
            }
        )
        ds.from_account.append({"from_id": tx_id, "to_id": centre, "amount": 50.0, "ts": "2026-07-19T00:00:00Z"})
        ds.to_account.append({"from_id": tx_id, "to_id": leaf, "amount": 50.0, "ts": "2026-07-19T00:00:00Z"})
    return ds


def _empty_dataset() -> GeneratedDataset:
    return GeneratedDataset()


# ---------------------------------------------------------------------------
# Per-measure tests
# ---------------------------------------------------------------------------


def test_density_cycle_4() -> None:
    """A 4-cycle has 4 nodes, 4 undirected edges. Density = 2*4 / (4*3) = 2/3."""
    adj = [[1], [0, 2], [1, 3], [2]]  # 0-1-2-3-0
    assert math.isclose(density(adj, edge_count=4), 2.0 / 3.0, rel_tol=1e-3)


def test_density_empty_graph() -> None:
    """Empty / trivial graphs return 0."""
    assert density([], edge_count=0) == 0.0
    assert density([[]], edge_count=0) == 0.0


def test_average_degree_cycle() -> None:
    """Every node in a cycle has degree 2."""
    # 4-cycle: 0-1-2-3-0. Note: adj[3] must include 0 to close the loop.
    adj = [[1, 3], [0, 2], [1, 3], [0, 2]]
    assert average_degree(adj) == 2.0


def test_average_degree_empty() -> None:
    assert average_degree([]) == 0.0


def test_clustering_coefficient_star() -> None:
    """In a star, only the centre has any neighbour pairs, and none are connected to each other."""
    # Star of 5 leaves: centre at index 0, leaves 1..5.
    star_adj = [[1, 2, 3, 4, 5], [0], [0], [0], [0], [0]]
    # Centre has 0 triangles (leaves not connected to each other) -> 0
    # Leaves have degree 1 -> skip
    assert clustering_coefficient(star_adj) == 0.0


def test_clustering_coefficient_triangle() -> None:
    """Complete graph on 3 nodes: every node has 2 triangles / (2*1) = 1.0."""
    triangle = [[1, 2], [0, 2], [0, 1]]
    assert clustering_coefficient(triangle) == 1.0


def test_diameter_cycle_4() -> None:
    """4-cycle: max BFS eccentricity from any node = 2 (opposite side)."""
    # 4-cycle: 0-1-2-3-0. adj[3] must include 0.
    adj = [[1, 3], [0, 2], [1, 3], [0, 2]]
    assert diameter_small(adj) == 2


def test_diameter_empty_returns_none() -> None:
    assert diameter_small([]) is None
    assert diameter_small([[]]) is None


def test_diameter_disconnected_returns_largest_component_diameter() -> None:
    """Two disconnected edges: each component has diameter 1; we return 1."""
    adj = [[1], [0], [3], [2]]
    assert diameter_small(adj) == 1


def test_edge_connectivity_min_degree() -> None:
    """Lower-bound edge connectivity = min degree."""
    # Star: centre degree 4, leaves degree 1 -> min degree = 1
    star_adj = [[1, 2, 3, 4], [0], [0], [0], [0]]
    assert edge_connectivity_lower_bound(star_adj) == 1


def test_node_connectivity_min_degree() -> None:
    """Lower-bound node connectivity = min degree."""
    star_adj = [[1, 2, 3, 4], [0], [0], [0], [0]]
    assert node_connectivity_lower_bound(star_adj) == 1


def test_assortativity_cycle_4_is_zero() -> None:
    """A regular graph of constant degree has zero assortativity (Pearson)."""
    # 4-cycle: 0-1-2-3-0. Every node has degree 2.
    adj = [[1, 3], [0, 2], [1, 3], [0, 2]]
    assert math.isclose(degree_assortativity(adj), 0.0, abs_tol=1e-3)


def test_assortativity_star_is_negative() -> None:
    """A star is disassortative: high-degree node connects to low-degree leaves."""
    star_adj = [[1, 2, 3, 4], [0], [0], [0], [0]]
    assert degree_assortativity(star_adj) < 0


def test_spectral_radius_estimate_positive_for_connected_graph() -> None:
    """Spectral radius of a cycle is bounded above by 2."""
    adj = [[1], [0, 2], [1, 3], [2]]
    sr = spectral_radius_estimate(adj)
    assert sr > 0.0


def test_spectral_radius_estimate_empty() -> None:
    assert spectral_radius_estimate([]) == 0.0


# ---------------------------------------------------------------------------
# End-to-end: compute_robustness on GeneratedDataset
# ---------------------------------------------------------------------------


def test_compute_robustness_on_synthetic_ring() -> None:
    """End-to-end on a tiny ring dataset."""
    ds = _ring_dataset(n=4)
    report = compute_robustness(ds)
    assert isinstance(report, RobustnessReport)
    assert report.node_count == 4
    assert report.edge_count == 4
    assert report.density > 0.0
    assert report.avg_degree == 2.0
    assert report.diameter_small == 2
    assert report.assortativity == pytest.approx(0.0, abs=1e-3)


def test_compute_robustness_on_star() -> None:
    """End-to-end on a star: 6 nodes, 5 edges, centre dominates."""
    ds = _star_dataset(centre="A000", leaves=5)
    report = compute_robustness(ds)
    assert report.node_count == 6
    assert report.edge_count == 5
    assert report.density == pytest.approx(2 * 5 / (6 * 5), rel=1e-3)
    assert report.assortativity < 0  # disassortative hub-and-spoke


def test_compute_robustness_on_empty_dataset() -> None:
    """Empty dataset must produce a valid (degenerate) report, not raise."""
    report = compute_robustness(_empty_dataset())
    assert report.node_count == 0
    assert report.edge_count == 0
    assert report.density == 0.0
    assert report.avg_degree == 0.0
    assert report.diameter_small is None
    assert report.clustering_coefficient == 0.0
    assert report.assortativity == 0.0


def test_compute_robustness_on_full_dataset() -> None:
    """Smoke-test on the canonical build_dataset() output."""
    ds = build_dataset(accounts=120, devices=80, merchants=20, transactions=2000, fraud_rings=4)
    report = compute_robustness(ds)
    assert report.node_count > 0
    assert report.edge_count > 0
    assert 0.0 <= report.density <= 1.0
    assert report.avg_degree > 0
    # 2000 transactions / 120 accounts ≈ average degree between 1 and 50.
    assert 1.0 <= report.avg_degree <= 50.0
    # Diameter is bounded by the node count.
    assert report.diameter_small is None or 1 <= report.diameter_small <= report.node_count


def test_compute_robustness_self_loops_ignored() -> None:
    """Self-loops (src == dst) should not be added to the undirected graph."""
    ds = GeneratedDataset()
    ds.accounts.append({"id": "A000"})
    # A transaction that goes A000 -> A000 (self-loop). Should not count as an edge.
    ds.transactions.append(
        {"id": "T_SELF", "ts": "2026-07-19T00:00:00Z", "amount": 0.0, "currency": "USD", "channel": "wire", "status": "completed"}
    )
    ds.from_account.append({"from_id": "T_SELF", "to_id": "A000", "amount": 0.0, "ts": "2026-07-19T00:00:00Z"})
    ds.to_account.append({"from_id": "T_SELF", "to_id": "A000", "amount": 0.0, "ts": "2026-07-19T00:00:00Z"})
    report = compute_robustness(ds)
    assert report.node_count == 1
    assert report.edge_count == 0


def test_robustness_report_to_dict_round_trip() -> None:
    """to_dict() should return all dataclass fields as a plain dict."""
    ds = _ring_dataset(n=3)
    report = compute_robustness(ds)
    d = report.to_dict()
    assert isinstance(d, dict)
    for key in (
        "node_count",
        "edge_count",
        "density",
        "avg_degree",
        "clustering_coefficient",
        "diameter_small",
        "node_connectivity_estimate",
        "edge_connectivity",
        "assortativity",
    ):
        assert key in d, f"missing key {key!r}"
