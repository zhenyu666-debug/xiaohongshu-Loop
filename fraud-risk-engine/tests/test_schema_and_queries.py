"""Tests for the GSQL schema and detection queries.

We do not need a TigerGraph runtime — these tests verify the strings are
well-formed GSQL and contain the expected query names.
"""

from __future__ import annotations

from app.queries.fraud_queries import (
    GSQL_BURST_TRANSACTIONS,
    GSQL_PAGERANK_ACCOUNTS,
    GSQL_SHARED_DEVICE_RINGS,
    GSQL_TRANSACTION_RINGS,
)
from app.schema import EDGE_TYPES, GSQL_SCHEMA, VERTEX_TYPES


def test_schema_contains_expected_vertices() -> None:
    expected = {"Customer", "Account", "Card", "Device", "IP", "Merchant", "Transaction"}
    assert set(VERTEX_TYPES.keys()) == expected
    body = GSQL_SCHEMA
    for v in expected:
        assert f"CREATE VERTEX {v}" in body


def test_schema_contains_expected_edges() -> None:
    expected = {
        "OWNS",
        "HAS_CARD",
        "USES_DEVICE",
        "LOGGED_FROM",
        "PAID_TO",
        "FROM_ACCOUNT",
        "TO_ACCOUNT",
        "SHARES_DEVICE",
        "SHARES_IP",
    }
    assert set(EDGE_TYPES.keys()) == expected
    for e in expected:
        assert f"CREATE { 'UNDIRECTED' if e in {'SHARES_DEVICE','SHARES_IP'} else 'DIRECTED' } EDGE {e}" in GSQL_SCHEMA


def test_each_query_has_create_query_and_print() -> None:
    for q in (
        GSQL_TRANSACTION_RINGS,
        GSQL_SHARED_DEVICE_RINGS,
        GSQL_BURST_TRANSACTIONS,
        GSQL_PAGERANK_ACCOUNTS,
    ):
        assert q.startswith("CREATE QUERY")
        assert "FOR GRAPH FraudRisk" in q
        assert "PRINT" in q


def test_query_names_unique() -> None:
    names = []
    for src in (GSQL_TRANSACTION_RINGS, GSQL_SHARED_DEVICE_RINGS,
                GSQL_BURST_TRANSACTIONS, GSQL_PAGERANK_ACCOUNTS):
        first_line = src.splitlines()[0]
        # `CREATE QUERY foo( ...`
        assert "CREATE QUERY" in first_line
        names.append(first_line.split("QUERY", 1)[1].split("(", 1)[0].strip())
    assert len(set(names)) == 4
