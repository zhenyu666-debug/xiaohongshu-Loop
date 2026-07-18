"""GSQL detection queries package.

Each query is exposed as a string so the loader can ``INSTALL QUERY`` it
after the schema is created. The functions below are pure strings — they do
no I/O and are easy to test.
"""

from .fraud_queries import (
    GSQL_BURST_TRANSACTIONS,
    GSQL_PAGERANK_ACCOUNTS,
    GSQL_SHARED_DEVICE_RINGS,
    GSQL_TRANSACTION_RINGS,
)

__all__ = [
    "GSQL_BURST_TRANSACTIONS",
    "GSQL_PAGERANK_ACCOUNTS",
    "GSQL_SHARED_DEVICE_RINGS",
    "GSQL_TRANSACTION_RINGS",
]