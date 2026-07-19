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
    # ── GDSL categories (69 queries from gsql-graph-algorithms library) ──
    CENTRALITY = "centrality"
    CENTRALITY_ARTICLE_RANK = "centrality_article_rank"
    CENTRALITY_EIGENVECTOR = "centrality_eigenvector"
    CENTRALITY_HARMONIC = "centrality_harmonic"
    CENTRALITY_DEGREE = "centrality_degree"
    CENTRALITY_PAGERANK_EXTENDED = "centrality_pagerank_extended"
    CENTRALITY_PAGERANK_PERS = "centrality_pagerank_personalized"
    CENTRALITY_INFLUENCE = "centrality_influence_maximization"
    CLASSIFICATION = "classification"
    CLASSIFICATION_KNN = "classification_knn"
    CLASSIFICATION_COLORING = "classification_coloring"
    CLASSIFICATION_MIS = "classification_mis"
    COMMUNITY = "community"
    COMMUNITY_SCC = "community_scc"
    COMMUNITY_KCORE = "community_kcore"
    COMMUNITY_KMEANS = "community_kmeans"
    COMMUNITY_LCC = "community_local_clustering"
    COMMUNITY_LOUVAIN = "community_louvain"
    COMMUNITY_MAP_EQ = "community_map_equation"
    COMMUNITY_SLPA = "community_slpa"
    COMMUNITY_TRI_COUNT = "community_triangle_counting"
    GRAPHML_EMBEDDINGS = "graphml_embeddings"
    GRAPHML_EMBEDDING_SIMILARITY = "graphml_embedding_similarity"
    PATH = "path"
    PATH_ASTAR = "path_astar"
    PATH_SHORTEST_PATH = "path_shortest_path"
    PATH_CYCLE = "path_cycle"
    PATH_MAXFLOW = "path_maxflow"
    PATH_MST = "path_minimum_spanning"
    PATH_DIAMETER = "path_diameter"
    PATTERNS = "patterns"
    PATTERNS_FPM = "patterns_frequent_pattern"
    SIMILARITY = "similarity"
    SIMILARITY_JACCARD_EXT = "similarity_jaccard_extended"
    SIMILARITY_COSINE = "similarity_cosine"
    TLP = "topological_link_prediction"
    TLP_ADAMIC_ADAR = "tlp_adamic_adar"
    TLP_COMMON_NEIGHBORS = "tlp_common_neighbors"
    TLP_PREFERENTIAL = "tlp_preferential_attachment"
    TLP_RESOURCE_ALLOC = "tlp_resource_allocation"
    TLP_SAME_COMMUNITY = "tlp_same_community"
    TLP_TOTAL_NEIGHBORS = "tlp_total_neighbors"


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


def _gdsl_generic_alert(
    result: dict,
    kind: str,
    severity: AlertSeverity,
    score: float,
    title: str,
    description: str,
    top_k: int = 20,
) -> RiskAlert | None:
    """Generic factory for GDSL queries that return a top_scores heap.

    Expected GSQL output shape (Centrality / Community / Similarity / TLP):
        {"results": [{"top_scores": [{"Vertex_ID": "...", "score": 0.5}, ...]}]}
    or:
        {"results": [{"sizes": {"compId": count, ...}}]}
    """
    # Try top_scores heap first
    raw = _gsql_value(result, "top_scores", None)
    if raw is None:
        # Try sizes map (WCC / LPCC community output)
        raw = _gsql_value(result, "sizes", None)
    if raw is None:
        raw = _gsql_value(result, "top_scores", None)
    if not raw:
        return None

    involved: list[str] = []
    if isinstance(raw, dict):
        # sizes map: keys are vertex IDs, values are counts
        sorted_items = sorted(raw.items(), key=lambda x: x[1], reverse=True)[:top_k]
        involved = [str(k) for k, _ in sorted_items]
        evidence = dict(sorted_items)
    elif isinstance(raw, list):
        # heap: each item has Vertex_ID (or v_id) and score
        for item in raw[:top_k]:
            if isinstance(item, dict):
                vid = item.get("Vertex_ID") or item.get("v_id") or item.get("score", "unknown")
                involved.append(str(vid))
        evidence = {"top_scores": raw[:top_k]}

    return RiskAlert(
        kind=kind,
        severity=severity.value,
        score=round(min(1.0, score), 4),
        title=title,
        description=description,
        involved=involved[:top_k],
        evidence=evidence if isinstance(raw, dict) else {"items": raw[:top_k]},
    )


def article_rank_alert_from_gsql(result: dict) -> RiskAlert | None:
    return _gdsl_generic_alert(
        result,
        AlertKind.CENTRALITY_ARTICLE_RANK.value,
        AlertSeverity.MEDIUM,
        0.35,
        "Article Rank centrality",
        "Article Rank scores for vertices — similar to PageRank but considers incoming links as citations.",
    )


def eigenvector_alert_from_gsql(result: dict) -> RiskAlert | None:
    return _gdsl_generic_alert(
        result,
        AlertKind.CENTRALITY_EIGENVECTOR.value,
        AlertSeverity.MEDIUM,
        0.35,
        "Eigenvector centrality",
        "Eigenvector centrality — a vertex is important if its neighbors are important.",
    )


def harmonic_alert_from_gsql(result: dict) -> RiskAlert | None:
    return _gdsl_generic_alert(
        result,
        AlertKind.CENTRALITY_HARMONIC.value,
        AlertSeverity.MEDIUM,
        0.35,
        "Harmonic centrality",
        "Harmonic centrality — sum of 1/distance to all reachable vertices.",
    )


def degree_cent_alert_from_gsql(result: dict) -> RiskAlert | None:
    return _gdsl_generic_alert(
        result,
        AlertKind.CENTRALITY_DEGREE.value,
        AlertSeverity.LOW,
        0.25,
        "Degree centrality (unweighted)",
        "Unweighted degree centrality — raw count of incident edges per vertex.",
    )


def weighted_degree_cent_alert_from_gsql(result: dict) -> RiskAlert | None:
    return _gdsl_generic_alert(
        result,
        AlertKind.CENTRALITY_DEGREE.value,
        AlertSeverity.LOW,
        0.25,
        "Degree centrality (weighted)",
        "Weighted degree centrality — sum of edge weights per vertex.",
    )


def pagerank_extended_alert_from_gsql(result: dict) -> RiskAlert | None:
    return _gdsl_generic_alert(
        result,
        AlertKind.CENTRALITY_PAGERANK_EXTENDED.value,
        AlertSeverity.MEDIUM,
        0.40,
        "PageRank (GDSL library — global)",
        "PageRank global centrality — damping=0.85, iterates until convergence.",
    )


def pagerank_personalized_alert_from_gsql(result: dict) -> RiskAlert | None:
    return _gdsl_generic_alert(
        result,
        AlertKind.CENTRALITY_PAGERANK_PERS.value,
        AlertSeverity.MEDIUM,
        0.40,
        "PageRank (personalized / multi-source)",
        "Personalized PageRank seeded from specific source vertices.",
    )


def influence_max_alert_from_gsql(result: dict) -> RiskAlert | None:
    return _gdsl_generic_alert(
        result,
        AlertKind.CENTRALITY_INFLUENCE.value,
        AlertSeverity.HIGH,
        0.45,
        "Influence Maximization (CELF / Greedy)",
        "Influence Maximization — greedy / CELF seed selection for maximum cascade spread.",
    )


def knn_alert_from_gsql(result: dict) -> RiskAlert | None:
    """KNN cosine similarity classification result."""
    raw = _gsql_value(result, "Results", None) or _gsql_value(result, "top_scores", None)
    if not raw:
        return None
    involved = []
    if isinstance(raw, list):
        for item in raw[:20]:
            if isinstance(item, dict):
                involved.append(str(item.get("src_id", item.get("v_type", "unknown"))))
    return RiskAlert(
        kind=AlertKind.CLASSIFICATION_KNN.value,
        severity=AlertSeverity.MEDIUM.value,
        score=0.40,
        title="K-Nearest Neighbors (Cosine similarity)",
        description="KNN cosine similarity classification — assigns labels based on nearest neighbors.",
        involved=involved[:20],
        evidence={"results": raw[:20] if isinstance(raw, list) else raw},
    )


def greedy_coloring_alert_from_gsql(result: dict) -> RiskAlert | None:
    raw = _gsql_value(result, "colors", None)
    if not raw:
        raw = _gsql_value(result, "color_count", None)
    count = raw.get("color_count", 0) if isinstance(raw, dict) else 0
    return RiskAlert(
        kind=AlertKind.CLASSIFICATION_COLORING.value,
        severity=AlertSeverity.LOW.value,
        score=round(min(1.0, 0.1 * count), 4),
        title="Greedy Graph Coloring",
        description=f"Greedy graph coloring — {count} color(s) used to properly color the graph.",
        involved=[],
        evidence={"color_count": count, "colors": raw if isinstance(raw, dict) else {}},
    )


def mis_alert_from_gsql(result: dict) -> RiskAlert | None:
    raw = _gsql_value(result, "Maximal_Independent_Set", None)
    if not raw:
        raw = _gsql_value(result, "mis", None)
    vertices = raw if isinstance(raw, list) else []
    if not vertices:
        return None
    return RiskAlert(
        kind=AlertKind.CLASSIFICATION_MIS.value,
        severity=AlertSeverity.LOW.value,
        score=0.30,
        title="Maximal Independent Set",
        description=f"Maximal Independent Set — {len(vertices)} vertices form an independent set.",
        involved=[str(v) for v in vertices[:20]],
        evidence={"mis_vertices": vertices[:20]},
    )


def scc_alert_from_gsql(result: dict) -> RiskAlert | None:
    """Strongly Connected Components alert."""
    raw = _gsql_value(result, "sizes", None) or _gsql_value(result, "top_scores", None)
    if not raw:
        return None
    if isinstance(raw, dict):
        sorted_items = sorted(raw.items(), key=lambda x: x[1], reverse=True)[:20]
        involved = [str(k) for k, _ in sorted_items]
        total = sum(raw.values())
        largest = max(raw.values()) if raw else 0
    else:
        involved = []
        total = largest = 0
        sorted_items = {}
    severity = (
        AlertSeverity.HIGH if largest >= 10 else AlertSeverity.MEDIUM if largest >= 5 else AlertSeverity.LOW
    )
    return RiskAlert(
        kind=AlertKind.COMMUNITY_SCC.value,
        severity=severity.value,
        score=round(min(1.0, 0.3 + 0.01 * total), 4),
        title="Strongly Connected Components",
        description=f"SCC: {len(raw) if isinstance(raw, dict) else 0} component(s), largest={largest}, total vertices={total}.",
        involved=involved[:20],
        evidence=dict(sorted_items) if isinstance(raw, dict) else {"items": raw[:20]},
    )


def kcore_alert_from_gsql(result: dict) -> RiskAlert | None:
    raw = _gsql_value(result, "kcore", None) or _gsql_value(result, "core_number", None)
    if not raw:
        return None
    kcore = raw.get("k", 0) if isinstance(raw, dict) else 0
    vertices = raw.get("vertices", []) if isinstance(raw, dict) else raw
    return RiskAlert(
        kind=AlertKind.COMMUNITY_KCORE.value,
        severity=AlertSeverity.HIGH.value if kcore >= 5 else AlertSeverity.MEDIUM.value,
        score=round(min(1.0, 0.3 + 0.05 * kcore), 4),
        title=f"K-Core decomposition (k={kcore})",
        description=f"{kcore}-core contains {len(vertices) if isinstance(vertices, list) else '?'} vertices.",
        involved=[str(v) for v in (vertices[:20] if isinstance(vertices, list) else [])],
        evidence={"k": kcore, "vertices": vertices[:20] if isinstance(vertices, list) else vertices},
    )


def kmeans_alert_from_gsql(result: dict) -> RiskAlert | None:
    raw = _gsql_value(result, "Clusters", None) or _gsql_value(result, "centroids", None)
    if not raw:
        return None
    clusters = raw if isinstance(raw, list) else []
    return RiskAlert(
        kind=AlertKind.COMMUNITY_KMEANS.value,
        severity=AlertSeverity.MEDIUM.value,
        score=0.35,
        title="K-Means clustering",
        description=f"K-Means: {len(clusters)} cluster(s) identified.",
        involved=[f"cluster_{i}" for i in range(min(len(clusters), 20))],
        evidence={"clusters": clusters[:10]},
    )


def lcc_alert_from_gsql(result: dict) -> RiskAlert | None:
    raw = _gsql_value(result, "Coefficients", None) or _gsql_value(result, "lcc", None)
    if not raw:
        return None
    if isinstance(raw, dict):
        sorted_items = sorted(raw.items(), key=lambda x: x[1], reverse=True)[:20]
        involved = [str(k) for k, _ in sorted_items]
        avg_coef = sum(raw.values()) / len(raw) if raw else 0
    else:
        sorted_items = []
        involved = []
        avg_coef = 0
    return RiskAlert(
        kind=AlertKind.COMMUNITY_LCC.value,
        severity=AlertSeverity.MEDIUM.value,
        score=round(min(1.0, avg_coef), 4),
        title="Local Clustering Coefficient",
        description=f"Avg clustering coefficient: {avg_coef:.4f}",
        involved=involved[:20],
        evidence=dict(sorted_items) if isinstance(raw, dict) else {"items": raw[:20]},
    )


def louvain_alert_from_gsql(result: dict) -> RiskAlert | None:
    raw = _gsql_value(result, "Clusters", None) or _gsql_value(result, "modularity", None)
    if not raw:
        return None
    if isinstance(raw, dict):
        communities = raw.get("communities", list(raw.keys())[:20])
        modularity = raw.get("modularity", 0.0)
    else:
        communities = raw if isinstance(raw, list) else []
        modularity = 0.0
    return RiskAlert(
        kind=AlertKind.COMMUNITY_LOUVAIN.value,
        severity=AlertSeverity.HIGH.value,
        score=round(min(1.0, 0.5 + modularity), 4),
        title="Louvain community detection",
        description=f"Louvain: {len(communities)} community/ies, modularity={modularity:.4f}.",
        involved=[str(c) for c in communities[:20]],
        evidence={"modularity": modularity, "communities": communities[:20]},
    )


def map_eq_alert_from_gsql(result: dict) -> RiskAlert | None:
    raw = _gsql_value(result, "modules", None) or _gsql_value(result, "map_equation", None)
    if not raw:
        return None
    modules = raw if isinstance(raw, list) else []
    return RiskAlert(
        kind=AlertKind.COMMUNITY_MAP_EQ.value,
        severity=AlertSeverity.HIGH.value,
        score=0.45,
        title="Map Equation community detection",
        description=f"Map Equation: {len(modules)} module(s) identified.",
        involved=[str(m) for m in modules[:20]] if isinstance(modules, list) else [],
        evidence={"modules": modules[:20] if isinstance(modules, list) else modules},
    )


def slpa_alert_from_gsql(result: dict) -> RiskAlert | None:
    raw = _gsql_value(result, "communities", None) or _gsql_value(result, "SLPA", None)
    if not raw:
        return None
    communities = raw if isinstance(raw, list) else []
    return RiskAlert(
        kind=AlertKind.COMMUNITY_SLPA.value,
        severity=AlertSeverity.MEDIUM.value,
        score=0.40,
        title="Speaker-Listener Label Propagation (SLPA)",
        description=f"SLPA: {len(communities)} community/ies detected.",
        involved=[str(c) for c in communities[:20]] if isinstance(communities, list) else [],
        evidence={"communities": communities[:20] if isinstance(communities, list) else communities},
    )


def tri_count_alert_from_gsql(result: dict) -> RiskAlert | None:
    raw = _gsql_value(result, "triangle_count", None) or _gsql_value(result, "tri_count", None)
    count = raw if isinstance(raw, int) else (raw.get("count", 0) if isinstance(raw, dict) else 0)
    return RiskAlert(
        kind=AlertKind.COMMUNITY_TRI_COUNT.value,
        severity=AlertSeverity.MEDIUM.value,
        score=round(min(1.0, 0.2 + 0.001 * count), 4),
        title="Triangle Counting",
        description=f"Total triangles in graph: {count}",
        involved=[],
        evidence={"triangle_count": count},
    )


def embedding_alert_from_gsql(result: dict) -> RiskAlert | None:
    raw = _gsql_value(result, "embeddings", None) or _gsql_value(result, "embedding", None)
    if not raw:
        return None
    count = len(raw) if isinstance(raw, list) else len(raw.get("vectors", {})) if isinstance(raw, dict) else 0
    return RiskAlert(
        kind=AlertKind.GRAPHML_EMBEDDINGS.value,
        severity=AlertSeverity.LOW.value,
        score=0.25,
        title="Graph Embeddings (FastRP / Weisfeiler-Lehman)",
        description=f"Graph embeddings computed for {count} vertex/vertices.",
        involved=[],
        evidence={"vertex_count": count, "embedding_type": "FastRP/WL"},
    )


def path_alert_from_gsql(result: dict, kind_str: str, title: str) -> RiskAlert | None:
    raw = _gsql_value(result, "path", None) or _gsql_value(result, "paths", None)
    if not raw:
        return None
    paths = raw if isinstance(raw, list) else [raw]
    total_length = sum(len(p) for p in paths if isinstance(p, list))
    return RiskAlert(
        kind=kind_str,
        severity=AlertSeverity.MEDIUM.value,
        score=round(min(1.0, 0.3 + 0.01 * total_length), 4),
        title=title,
        description=f"{len(paths)} path(s) found, total length={total_length}.",
        involved=paths[0][:10] if paths and isinstance(paths[0], list) else [],
        evidence={"path_count": len(paths), "total_length": total_length, "paths": paths[:5]},
    )


def bfs_alert_from_gsql(result: dict) -> RiskAlert | None:
    return path_alert_from_gsql(result, AlertKind.PATH.value, "BFS traversal")


def astar_alert_from_gsql(result: dict) -> RiskAlert | None:
    return path_alert_from_gsql(result, AlertKind.PATH_ASTAR.value, "A* shortest path")


def shortest_path_alert_from_gsql(result: dict) -> RiskAlert | None:
    return path_alert_from_gsql(result, AlertKind.PATH_SHORTEST_PATH.value, "Shortest path (unweighted / weighted)")


def cycle_alert_from_gsql(result: dict) -> RiskAlert | None:
    raw = _gsql_value(result, "cycles", None) or _gsql_value(result, "cycle_count", None)
    count = raw if isinstance(raw, int) else (raw.get("count", 0) if isinstance(raw, dict) else 0)
    return RiskAlert(
        kind=AlertKind.PATH_CYCLE.value,
        severity=AlertSeverity.HIGH.value if count > 0 else AlertSeverity.LOW.value,
        score=round(min(1.0, 0.4 + 0.05 * count), 4),
        title="Cycle detection",
        description=f"{count} cycle(s) detected in the graph.",
        involved=[],
        evidence={"cycle_count": count},
    )


def maxflow_alert_from_gsql(result: dict) -> RiskAlert | None:
    raw = _gsql_value(result, "max_flow", None) or _gsql_value(result, "flow", None)
    flow = raw if isinstance(raw, (int, float)) else (raw.get("value", 0) if isinstance(raw, dict) else 0)
    return RiskAlert(
        kind=AlertKind.PATH_MAXFLOW.value,
        severity=AlertSeverity.MEDIUM.value,
        score=round(min(1.0, 0.3 + 0.001 * float(flow)), 4),
        title="Maximum flow",
        description=f"Maximum flow value: {flow}",
        involved=[],
        evidence={"max_flow": flow},
    )


def mst_alert_from_gsql(result: dict) -> RiskAlert | None:
    raw = _gsql_value(result, "mst", None) or _gsql_value(result, "edges", None)
    edges = raw if isinstance(raw, list) else []
    return RiskAlert(
        kind=AlertKind.PATH_MST.value,
        severity=AlertSeverity.LOW.value,
        score=0.20,
        title="Minimum Spanning Tree / Forest",
        description=f"MST / MSF: {len(edges)} edge(s) in the spanning tree.",
        involved=[],
        evidence={"edges": edges[:20]},
    )


def diameter_alert_from_gsql(result: dict) -> RiskAlert | None:
    raw = _gsql_value(result, "diameter", None) or _gsql_value(result, "estimated_diameter", None)
    diameter = raw if isinstance(raw, (int, float)) else (raw.get("diameter", 0) if isinstance(raw, dict) else 0)
    return RiskAlert(
        kind=AlertKind.PATH_DIAMETER.value,
        severity=AlertSeverity.LOW.value,
        score=round(min(1.0, 0.1 + 0.05 * float(diameter)), 4),
        title="Graph diameter (estimated)",
        description=f"Estimated graph diameter: {diameter}",
        involved=[],
        evidence={"diameter": diameter},
    )


def fpm_alert_from_gsql(result: dict) -> RiskAlert | None:
    raw = _gsql_value(result, "frequent_patterns", None) or _gsql_value(result, "patterns", None)
    if not raw:
        return None
    patterns = raw if isinstance(raw, list) else []
    return RiskAlert(
        kind=AlertKind.PATTERNS_FPM.value,
        severity=AlertSeverity.MEDIUM.value,
        score=0.35,
        title="Frequent Pattern Mining",
        description=f"Frequent Pattern Mining: {len(patterns)} pattern(s) found.",
        involved=patterns[:20] if isinstance(patterns, list) else [],
        evidence={"patterns": patterns[:20]},
    )


def cosine_sim_alert_from_gsql(result: dict) -> RiskAlert | None:
    return _gdsl_generic_alert(
        result,
        AlertKind.SIMILARITY_COSINE.value,
        AlertSeverity.MEDIUM,
        0.40,
        "Cosine similarity (all-pairs / single-source)",
        "Cosine similarity between vertex embeddings or neighbor sets.",
    )


def jaccard_ext_alert_from_gsql(result: dict) -> RiskAlert | None:
    return _gdsl_generic_alert(
        result,
        AlertKind.SIMILARITY_JACCARD_EXT.value,
        AlertSeverity.MEDIUM,
        0.40,
        "Jaccard similarity (all-pairs / single-source — GDSL library)",
        "Jaccard similarity between vertex neighbor sets.",
    )


def tlp_score_alert_from_gsql(
    result: dict, kind_str: str, title: str, description: str
) -> RiskAlert | None:
    return _gdsl_generic_alert(
        result,
        kind_str,
        AlertSeverity.MEDIUM,
        0.35,
        title,
        description,
    )


def adamic_adar_alert_from_gsql(result: dict) -> RiskAlert | None:
    return tlp_score_alert_from_gsql(
        result,
        AlertKind.TLP_ADAMIC_ADAR.value,
        "Adamic-Adar index (link prediction)",
        "Adamic-Adar: sums 1/log(degree) over common neighbors — predicts missing links.",
    )


def common_neighbors_alert_from_gsql(result: dict) -> RiskAlert | None:
    return tlp_score_alert_from_gsql(
        result,
        AlertKind.TLP_COMMON_NEIGHBORS.value,
        "Common Neighbors (link prediction)",
        "Common Neighbors: count of shared neighbors — simple link prediction metric.",
    )


def preferential_alert_from_gsql(result: dict) -> RiskAlert | None:
    return tlp_score_alert_from_gsql(
        result,
        AlertKind.TLP_PREFERENTIAL.value,
        "Preferential Attachment (link prediction)",
        "Preferential Attachment: degree(u) × degree(v) — rich-get-richer link formation.",
    )


def resource_alloc_alert_from_gsql(result: dict) -> RiskAlert | None:
    return tlp_score_alert_from_gsql(
        result,
        AlertKind.TLP_RESOURCE_ALLOC.value,
        "Resource Allocation (link prediction)",
        "Resource Allocation: sum of 1/degree over common neighbors.",
    )


def same_community_alert_from_gsql(result: dict) -> RiskAlert | None:
    return tlp_score_alert_from_gsql(
        result,
        AlertKind.TLP_SAME_COMMUNITY.value,
        "Same Community (link prediction)",
        "Same Community: two vertices in the same community are more likely to link.",
    )


def total_neighbors_alert_from_gsql(result: dict) -> RiskAlert | None:
    return tlp_score_alert_from_gsql(
        result,
        AlertKind.TLP_TOTAL_NEIGHBORS.value,
        "Total Neighbors (link prediction)",
        "Total Neighbors: |N(u) ∪ N(v)| — union of neighbor sets.",
    )


def empty_snapshot() -> GraphSnapshot:
    return GraphSnapshot()