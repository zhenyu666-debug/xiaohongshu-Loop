"""GSQL funds-flow detection queries.

These are ports of three canonical Cypher / Neo4j statements into
TigerGraph's GSQL syntax. They all target the existing ``FraudRisk``
schema (Account / Transaction / FROM_ACCOUNT / TO_ACCOUNT) and emit a
single ``PRINT`` line suitable for the Python alert factory layer.

The local Pure-Python fallbacks are in :mod:`app.detection.funds_local`
so the same logic works in ``local`` and ``tigergraph`` backends
(see ``TigerGraphDetector.run()`` vs ``LocalDetector.run()``).
"""

from __future__ import annotations

from pathlib import Path


_FUNDS_DIR = Path(__file__).parent / "funds"


def _load(name: str) -> str:
    return (_FUNDS_DIR / name).read_text(encoding="utf-8").strip()


# 1. Multi-hop funds trace (smurfing path analysis)
GSQL_FUNDS_PATH_TRACE: str = _load("fundsPathTrace.gsql")

# 2. Circular funds rings (3..6 hops) — extends the existing 3-hop ring query
GSQL_CIRCULAR_FUNDS: str = _load("circularFunds.gsql")

# 3. Burst amount detection (5x historical average)
GSQL_BURST_AMOUNT: str = _load("burstAmount.gsql")


__all__ = [
    "GSQL_FUNDS_PATH_TRACE",
    "GSQL_CIRCULAR_FUNDS",
    "GSQL_BURST_AMOUNT",
]
