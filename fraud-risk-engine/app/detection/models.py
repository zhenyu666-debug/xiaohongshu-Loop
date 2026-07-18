"""Detection domain models and GSQL → alert post-processors.

The detection results are:

- :class:`RiskAlert` — one suspicion worth surfacing
- :class:`AlertSeverity` — low/medium/high/critical
- :class:`AlertKind` — discriminator (ring / shared_device / burst / pagerank)
- :class:`GraphSnapshot` — serialisable picture of the current graph state
- :class:`DetectionRun` — a batched run containing many alerts + a snapshot

The four ``*_alert_from_gsql`` factory functions translate the raw GSQL
``PRINT`` output (a list of strings / string-sets / maps) into structured
:class:`RiskAlert` instances. They are pure functions — easy to unit test.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class AlertSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class AlertKind(str, Enum):
    RING = "transaction_ring"
    SHARED_DEVICE = "shared_device"
    SHARED_IP = "shared_ip"
    BURST = "burst_transactions"
    PAGERANK = "pagerank"


@dataclass
class RiskAlert:
    """A single fraud suspicion record."""

    kind: str
    severity: str
    score: float
    title: str
    description: str
    involved: list[str] = field(default_factory=list)
    evidence: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GraphSnapshot:
    """Point-in-time snapshot of the FraudRisk graph."""

    vertices: dict[str, int] = field(default_factory=dict)
    edges: dict[str, int] = field(default_factory=dict)
    planted_rings: list[dict[str, Any]] = field(default_factory=list)
    topk_accounts: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DetectionRun:
    """A complete fraud-detection run."""

    run_id: str
    started_at: str
    ended_at: str
    backend: str  # "tigergraph" or "local"
    status: str  # "ok" / "degraded" / "unreachable"
    detail: str = ""
    alerts: list[RiskAlert] = field(default_factory=list)
    snapshot: GraphSnapshot = field(default_factory=GraphSnapshot)
    metrics: dict[str, int] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "run_id": self.run_id,
            "started_at": self.started_at,
            "ended_at": self.ended_at,
            "backend": self.backend,
            "status": self.status,
            "detail": self.detail,
            "alerts": [a.to_dict() for a in self.alerts],
            "snapshot": self.snapshot.to_dict(),
            "metrics": self.metrics,
        }


# ---------------------------------------------------------------------------
# GSQL PRINT helpers — TigerGraph returns JSON like:
#   {"results": [{"ringCount": 12, "accountIds": {"A001","A017", ...}}]}
# These factories normalise that shape into RiskAlert records.
# ---------------------------------------------------------------------------


def _gsql_value(result: dict, name: str, default=None):
    """Pull a key from ``{"results":[ ... ]}`` or from raw payload."""
    if not result:
        return default
    if "results" in result and isinstance(result["results"], list) and result["results"]:
        first = result["results"][0]
        return first.get(name, default)
    return result.get(name, default)


def ring_alert_from_gsql(result: dict) -> RiskAlert | None:
    """Build a ring alert from ``transactionRings`` output."""
    ring_count = _gsql_value(result, "ringCount", 0)
    if not ring_count or ring_count <= 0:
        return None
    score = min(1.0, 0.4 + 0.05 * int(ring_count))
    return RiskAlert(
        kind=AlertKind.RING.value,
        severity=AlertSeverity.CRITICAL.value if ring_count >= 5 else AlertSeverity.HIGH.value,
        score=round(score, 4),
        title="Short-cycle transaction ring detected",
        description=(
            f"Detected {ring_count} 3-hop cyclic transaction(s) on Account "
            "vertices — money loops back to the originating account."
        ),
        involved=_gsql_value(result, "accountIds", []) or [],
        evidence={"ring_count": ring_count},
    )


def shared_device_alert_from_gsql(result: dict) -> RiskAlert | None:
    """Build a shared-device alert from ``sharedDeviceRings`` output."""
    shared_ids = _gsql_value(result, "sharedDeviceIds", []) or []
    accounts_by_device = _gsql_value(result, "accountsByDevice", {}) or {}
    affected = sum(len(v) for v in accounts_by_device.values() if len(v) >= 3)
    if not shared_ids or affected < 3:
        return None
    severity = (
        AlertSeverity.CRITICAL.value
        if affected >= 9
        else AlertSeverity.HIGH.value
        if affected >= 5
        else AlertSeverity.MEDIUM.value
    )
    return RiskAlert(
        kind=AlertKind.SHARED_DEVICE.value,
        severity=severity,
        score=round(min(1.0, 0.3 + 0.05 * len(shared_ids)), 4),
        title="Multiple accounts sharing the same device",
        description=(
            f"{len(shared_ids)} device(s) are linked to ≥3 distinct accounts — "
            "a classic account-takeover / mule-pool signature."
        ),
        involved=list(shared_ids),
        evidence={"affected_accounts": affected, "by_device": accounts_by_device},
    )


def burst_alert_from_gsql(result: dict) -> RiskAlert | None:
    """Build a burst alert from ``burstTransactions`` output."""
    counts = _gsql_value(result, "txCountByAccount", {}) or {}
    flagged = {acc: c for acc, c in counts.items() if int(c) >= 12}
    if not flagged:
        return None
    affected = len(flagged)
    severity = (
        AlertSeverity.CRITICAL.value
        if affected >= 10
        else AlertSeverity.HIGH.value
        if affected >= 5
        else AlertSeverity.MEDIUM.value
    )
    return RiskAlert(
        kind=AlertKind.BURST.value,
        severity=severity,
        score=round(min(1.0, 0.4 + 0.05 * affected), 4),
        title="Transaction velocity burst",
        description=(
            f"{affected} account(s) emitted more than 12 outgoing transactions "
            "inside the rolling window — classic velocity fraud pattern."
        ),
        involved=list(flagged.keys()),
        evidence={
            "tx_count_by_account": {k: int(v) for k, v in flagged.items()},
            "first_ts": _gsql_value(result, "firstTsByAccount", {}) or {},
            "last_ts": _gsql_value(result, "lastTsByAccount", {}) or {},
        },
    )


def pagerank_alert_from_gsql(result: dict, top_k: int = 50) -> RiskAlert | None:
    """Build a pagerank alert from ``pageRankAccounts`` output."""
    top = _gsql_value(result, "topAccounts", []) or []
    if not top:
        return None
    sample_score = _gsql_value(result, "sampleScore", 0)
    return RiskAlert(
        kind=AlertKind.PAGERANK.value,
        severity=AlertSeverity.MEDIUM.value,
        score=round(min(1.0, 0.3 + 0.005 * len(top)), 4),
        title=f"Top-{top_k} centrality accounts (PageRank-like)",
        description=(
            f"Top-K central accounts ranked by out-degree. These accounts are "
            "good first-pass candidates for human review when combined with "
            "ring / shared-device alerts."
        ),
        involved=list(top)[:top_k],
        evidence={"topK": len(top), "sample_score": sample_score},
    )


def empty_snapshot() -> GraphSnapshot:
    return GraphSnapshot()