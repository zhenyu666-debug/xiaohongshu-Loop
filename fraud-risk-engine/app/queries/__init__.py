"""GSQL detection queries package.

Each query is exposed as a string so the loader can ``INSTALL QUERY`` it
after the schema is created. The functions below are pure strings — they do
no I/O and are easy to test.
"""

from .fraud_queries import (
    GSQL_BETWEENNESS,
    GSQL_BURST_TRANSACTIONS,
    GSQL_CLOSENESS,
    GSQL_JACCARD,
    GSQL_LPCC,
    GSQL_PAGERANK_ACCOUNTS,
    GSQL_SHARED_DEVICE_RINGS,
    GSQL_TRANSACTION_RINGS,
    GSQL_WCC,
)
from .funds_queries import (
    GSQL_BURST_AMOUNT,
    GSQL_CIRCULAR_FUNDS,
    GSQL_FUNDS_PATH_TRACE,
)
from . import edge_features
from . import gdsl

__all__ = [
    "GSQL_BETWEENNESS",
    "GSQL_BURST_TRANSACTIONS",
    "GSQL_CLOSENESS",
    "GSQL_JACCARD",
    "GSQL_LPCC",
    "GSQL_PAGERANK_ACCOUNTS",
    "GSQL_SHARED_DEVICE_RINGS",
    "GSQL_TRANSACTION_RINGS",
    "GSQL_WCC",
    "GSQL_BURST_AMOUNT",
    "GSQL_CIRCULAR_FUNDS",
    "GSQL_FUNDS_PATH_TRACE",
    "edge_features",
    "gdsl",
]      