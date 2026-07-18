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
    WCC = "connected_component"
    LPCC = "community"
    JACCARD = "jaccard_similarity"
    BETWEENNESS = "betweenness"
    CLOSENESS = "closeness"


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


def wcc_alert_from_gsql(result: dict) -> RiskAlert | None:
    """Build a connected-component alert from ``tg_wcc`` output.

    WCC groups accounts that are transitively connected via shared-device /
    shared-IP edges. Large components indicate potential identity clusters.
    """
    components = _gsql_value(result, "components", {}) or {}
    if not components:
        return None
    # components is a MapAccum: {comp_id -> {comp_id: comp_id}}
    # Count distinct component ids (not vertex ids)
    seen_comp_ids: dict[str, int] = {}
    for comp_id, entry in components.items():
        if isinstance(entry, dict):
            cid = entry.get("comp_id", comp_id)
        else:
            cid = str(entry) if entry else comp_id
        seen_comp_ids[cid] = seen_comp_ids.get(cid, 0) + 1
    distinct_comps = len(seen_comp_ids)
    total_vertices = _gsql_value(result, "vertexCount", 0)
    if total_vertices == 0:
        total_vertices = len(components)
    max_size = max(seen_comp_ids.values()) if seen_comp_ids else 0
    large_component_count = sum(1 for s in seen_comp_ids.values() if s >= 3)
    severity = (
        AlertSeverity.CRITICAL.value
        if large_component_count >= 5
        else AlertSeverity.HIGH.value
        if large_component_count >= 3
        else AlertSeverity.MEDIUM.value
    )
    return RiskAlert(
        kind=AlertKind.WCC.value,
        severity=severity,
        score=round(min(1.0, 0.3 + 0.05 * large_component_count), 4),
        title="Connected components (identity clusters)",
        description=(
            f"{distinct_comps} connected component(s) found; largest has "
            f"{max_size} accounts. Components of size ≥ 3 are flagged as "
            "potential fraud-identity clusters."
        ),
        involved=list(seen_comp_ids.keys())[:20],
        evidence={
            "distinct_components": distinct_comps,
            "total_vertices": total_vertices,
            "largest_size": max_size,
            "large_component_count": large_component_count,
            "component_sizes": dict(list(seen_comp_ids.items())[:20]),
        },
    )


def lpcc_alert_from_gsql(result: dict) -> RiskAlert | None:
    """Build a community-detection alert from ``tg_lpcc`` output.

    Label Propagation finds naturally forming communities without pre-specifying K.
    Tight fraud rings often show up as unusually dense communities.
    """
    top_comms = _gsql_value(result, "topCommunities", []) or []
    community_count = _gsql_value(result, "communityCount", 0)
    vertex_count = _gsql_value(result, "vertexCount", 0)
    if not top_comms and community_count == 0:
        return None
    # top_comms is a list of {"cnt": int, "label": str}
    top_labels = [c.get("label", "") for c in top_comms if isinstance(c, dict)]
    top_sizes = [c.get("cnt", 0) for c in top_comms if isinstance(c, dict)]
    large_communities = [l for l, s in zip(top_labels, top_sizes) if s >= 5]
    severity = (
        AlertSeverity.HIGH.value
        if len(large_communities) >= 3
        else AlertSeverity.MEDIUM.value
        if large_communities
        else AlertSeverity.LOW.value
    )
    return RiskAlert(
        kind=AlertKind.LPCC.value,
        severity=severity,
        score=round(min(1.0, 0.3 + 0.05 * len(top_labels)), 4),
        title="Community clusters (Label Propagation)",
        description=(
            f"{community_count} community/ies found among {vertex_count} accounts. "
            f"Top community has {top_sizes[0] if top_sizes else 0} members. "
            "Unusually dense communities are a fraud ring signal."
        ),
        involved=top_labels[:20],
        evidence={
            "community_count": community_count,
            "vertex_count": vertex_count,
            "top_communities": top_comms[:10],
            "large_community_labels": large_communities,
        },
    )


def jaccard_alert_from_gsql(result: dict) -> RiskAlert | None:
    """Build a Jaccard similarity alert from ``tg_jaccard`` output.

    High Jaccard similarity between two accounts means they share many
    of the same neighbors (devices, IPs) — a strong identity-link signal.
    """
    jaccard = _gsql_value(result, "source_target_jaccard", 0.0)
    top_similar = _gsql_value(result, "topSimilarAccounts", []) or []
    intersection_size = _gsql_value(result, "intersectionSize", 0)
    union_size = _gsql_value(result, "unionSize", 0)
    if jaccard == 0 and not top_similar:
        return None
    threshold_high = 0.5
    threshold_medium = 0.3
    if isinstance(jaccard, dict):
        jaccard = jaccard.get("source_target_jaccard", 0.0)
    severity = (
        AlertSeverity.CRITICAL.value
        if float(jaccard or 0) >= threshold_high
        else AlertSeverity.HIGH.value
        if float(jaccard or 0) >= threshold_medium
        else AlertSeverity.MEDIUM.value
    )
    return RiskAlert(
        kind=AlertKind.JACCARD.value,
        severity=severity,
        score=round(float(jaccard or 0), 4),
        title="Jaccard similarity (identity-link score)",
        description=(
            f"Source-target Jaccard similarity: {jaccard:.4f} "
            f"(intersection={intersection_size}, union={union_size}). "
            f"{len(top_similar)} similar account(s) identified."
        ),
        involved=top_similar[:20],
        evidence={
            "source_target_jaccard": float(jaccard or 0),
            "intersection_size": intersection_size,
            "union_size": union_size,
            "top_similar_accounts": top_similar[:10],
        },
    )


def betweenness_alert_from_gsql(result: dict) -> RiskAlert | None:
    """Build a betweenness centrality alert from ``tg_betweenness`` output.

    High betweenness = account sits on many shortest paths = potential
    mule / broker in the fraud network.
    """
    top_bt = _gsql_value(result, "topBetweennessAccounts", []) or []
    total_bt = _gsql_value(result, "totalBetweenness", 0)
    processed = _gsql_value(result, "verticesProcessed", 0)
    if not top_bt:
        return None
    # top_bt is a list of {"score": float, "v_id": string}
    top_ids = [b.get("v_id", "") for b in top_bt if isinstance(b, dict)]
    top_scores = [b.get("score", 0.0) for b in top_bt if isinstance(b, dict)]
    max_score = top_scores[0] if top_scores else 0.0
    severity = (
        AlertSeverity.HIGH.value
        if max_score >= 10.0
        else AlertSeverity.MEDIUM.value
        if max_score >= 5.0
        else AlertSeverity.LOW.value
    )
    return RiskAlert(
        kind=AlertKind.BETWEENNESS.value,
        severity=severity,
        score=round(min(1.0, 0.3 + 0.005 * max_score), 4),
        title="Betweenness centrality (broker / mule detection)",
        description=(
            f"{processed} vertices processed; betweenness total = {total_bt:.2f}. "
            f"Top account has score {max_score:.2f} — potential intermediary "
            "in multiple fraud paths."
        ),
        involved=top_ids[:20],
        evidence={
            "total_betweenness": float(total_bt or 0),
            "vertices_processed": processed,
            "top_betweenness": top_bt[:10],
        },
    )


def closeness_alert_from_gsql(result: dict) -> RiskAlert | None:
    """Build a closeness centrality alert from ``tg_closeness`` output.

    High closeness = account is "close" to many others = good hub or
    core node in the fraud network.
    """
    top_cl = _gsql_value(result, "topClosenessAccounts", []) or []
    vertex_count = _gsql_value(result, "vertexCount", 0)
    if not top_cl:
        return None
    top_ids = [c.get("v_id", "") for c in top_cl if isinstance(c, dict)]
    top_scores = [c.get("score", 0.0) for c in top_cl if isinstance(c, dict)]
    max_score = top_scores[0] if top_scores else 0.0
    severity = AlertSeverity.MEDIUM.value
    return RiskAlert(
        kind=AlertKind.CLOSENESS.value,
        severity=severity,
        score=round(min(1.0, 0.3 + 0.01 * max_score), 4),
        title="Closeness centrality (network hub accounts)",
        description=(
            f"{vertex_count} accounts analysed. Top closeness score = {max_score:.4f}. "
            "High-closeness accounts are well-connected hubs — high-value for "
            "fraud investigation even if not directly flagged."
        ),
        involved=top_ids[:20],
        evidence={
            "vertex_count": vertex_count,
            "top_closeness": top_cl[:10],
        },
    )


def empty_snapshot() -> GraphSnapshot:
    return GraphSnapshot()