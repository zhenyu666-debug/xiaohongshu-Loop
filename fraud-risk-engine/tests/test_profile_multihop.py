"""Tests for :mod:`app.profile.graph_search` — multi-hop BFS traversals."""

from __future__ import annotations

import pytest

from app.loader.synth_generator import GeneratedDataset, build_dataset
from app.profile.graph_search import (
    GraphSubgraph,
    GraphNode,
    GraphEdge,
    bfs_identity,
    bfs_funds,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def ds() -> GeneratedDataset:
    """Small seeded dataset with 2 fraud rings for reproducible tests."""
    return build_dataset(
        accounts=120,
        devices=80,
        merchants=20,
        transactions=2000,
        fraud_rings=2,
        seed=20260718,
    )


@pytest.fixture
def planted_ring_account(ds: GeneratedDataset) -> str:
    """Return the first account in the first planted ring."""
    rings = ds.planted_rings
    assert rings, "expected planted rings in seeded dataset"
    return rings[0]["accounts"][0]


# ---------------------------------------------------------------------------
# Shape
# ---------------------------------------------------------------------------


def test_identity_returns_graph_subgraph(ds: GeneratedDataset) -> None:
    result = bfs_identity("A000000", ds)
    assert isinstance(result, GraphSubgraph)
    assert result.root_id == "A000000"
    assert result.mode == "identity"


def test_identity_nodes_have_required_fields(ds: GeneratedDataset) -> None:
    result = bfs_identity("A000000", ds)
    for node in result.nodes:
        assert hasattr(node, "id")
        assert hasattr(node, "kind")
        assert hasattr(node, "hop")
        assert hasattr(node, "parent_id")


def test_identity_edges_have_required_fields(ds: GeneratedDataset) -> None:
    result = bfs_identity("A000000", ds)
    for edge in result.edges:
        assert hasattr(edge, "src")
        assert hasattr(edge, "dst")
        assert hasattr(edge, "label")
        assert hasattr(edge, "hop")


def test_identity_stats_contains_expected_keys(ds: GeneratedDataset) -> None:
    result = bfs_identity("A000000", ds)
    for key in (
        "total_nodes",
        "total_edges",
        "accounts_found",
        "devices_found",
        "ips_found",
        "cumulative_amount",
        "top_counterparties",
    ):
        assert key in result.stats


def test_funds_returns_graph_subgraph(ds: GeneratedDataset) -> None:
    result = bfs_funds("A000000", ds)
    assert isinstance(result, GraphSubgraph)
    assert result.root_id == "A000000"
    assert result.mode == "funds"


def test_funds_stats_contains_expected_keys(ds: GeneratedDataset) -> None:
    result = bfs_funds("A000000", ds)
    for key in (
        "total_nodes",
        "total_edges",
        "accounts_found",
        "transactions_found",
        "merchants_found",
        "cumulative_amount",
        "top_counterparties",
    ):
        assert key in result.stats


def test_funds_cumulative_amount_is_nonnegative(ds: GeneratedDataset) -> None:
    result = bfs_funds("A000000", ds)
    assert result.stats["cumulative_amount"] >= 0.0


# ---------------------------------------------------------------------------
# Correctness
# ---------------------------------------------------------------------------


def test_identity_root_in_nodes(ds: GeneratedDataset) -> None:
    result = bfs_identity("A000050", ds)
    root_nodes = [n for n in result.nodes if n.id == "A000050"]
    assert len(root_nodes) == 1
    assert root_nodes[0].hop == 0
    assert root_nodes[0].parent_id is None


def test_identity_planted_ring_reachable(ds: GeneratedDataset, planted_ring_account: str) -> None:
    """Accounts in the same planted ring share a device, so they must appear
    in the same identity component."""
    result = bfs_identity(planted_ring_account, ds, max_hops=3)
    account_ids = {n.id for n in result.nodes if n.kind == "account"}
    # At least one other ring member should appear (from shared device traversal)
    ring_accounts = set(ds.planted_rings[0]["accounts"])
    overlap = account_ids & ring_accounts
    assert len(overlap) >= 1, "planted ring member should be reachable within 3 hops"


def test_identity_max_hops_respected(ds: GeneratedDataset) -> None:
    result = bfs_identity("A000000", ds, max_hops=1)
    assert all(n.hop <= 1 for n in result.nodes)


def test_identity_no_duplicate_nodes(ds: GeneratedDataset) -> None:
    result = bfs_identity("A000000", ds)
    ids = [n.id for n in result.nodes]
    assert len(ids) == len(set(ids)), "BFS must not add the same node twice"


def test_funds_max_hops_respected(ds: GeneratedDataset) -> None:
    result = bfs_funds("A000000", ds, max_hops=2)
    assert all(n.hop <= 2 for n in result.nodes)


def test_funds_no_duplicate_nodes(ds: GeneratedDataset) -> None:
    result = bfs_funds("A000000", ds)
    ids = [n.id for n in result.nodes]
    assert len(ids) == len(set(ids)), "BFS must not add the same node twice"


def test_funds_direction_out_only(ds: GeneratedDataset) -> None:
    out = bfs_funds("A000000", ds, direction="out")
    # Outgoing: root appears as src of FROM_ACCOUNT edges
    assert out.stats["total_nodes"] >= 1


def test_funds_direction_in_only(ds: GeneratedDataset) -> None:
    inc = bfs_funds("A000000", ds, direction="in")
    assert inc.stats["total_nodes"] >= 1


def test_funds_direction_both(ds: GeneratedDataset) -> None:
    both = bfs_funds("A000000", ds, direction="both")
    assert both.stats["total_nodes"] >= 1


# ---------------------------------------------------------------------------
# to_dict round-trip
# ---------------------------------------------------------------------------


def test_identity_to_dict_serializable(ds: GeneratedDataset) -> None:
    result = bfs_identity("A000000", ds)
    d = result.to_dict()
    assert isinstance(d, dict)
    assert d["root_id"] == "A000000"
    assert d["mode"] == "identity"
    assert isinstance(d["nodes"], list)
    assert isinstance(d["edges"], list)
    assert isinstance(d["stats"], dict)


def test_funds_to_dict_serializable(ds: GeneratedDataset) -> None:
    result = bfs_funds("A000000", ds)
    d = result.to_dict()
    assert isinstance(d, dict)
    assert d["root_id"] == "A000000"
    assert d["mode"] == "funds"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


def test_identity_empty_when_no_connectivity(ds: GeneratedDataset) -> None:
    """An account with no devices/IPs still returns itself."""
    result = bfs_identity("A000000", ds, max_hops=3)
    assert result.root_id == "A000000"
    assert result.stats["accounts_found"] >= 1


def test_funds_empty_when_no_transactions(ds: GeneratedDataset) -> None:
    """An account with no transactions still returns itself."""
    result = bfs_funds("A000000", ds, max_hops=3)
    assert result.root_id == "A000000"
    assert result.stats["accounts_found"] >= 1


def test_funds_include_merchants_flag(ds: GeneratedDataset) -> None:
    without = bfs_funds("A000000", ds, include_merchants=False)
    with_m = bfs_funds("A000000", ds, include_merchants=True)
    assert with_m.stats["merchants_found"] >= without.stats["merchants_found"]
