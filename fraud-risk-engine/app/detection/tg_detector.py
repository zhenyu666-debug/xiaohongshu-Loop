"""TigerGraph-backed detector — runs the GSQL queries via RESTPP and
post-processes results into :class:`RiskAlert` records.

If the runtime is unreachable the detector returns a :class:`DetectionRun`
with ``status="degraded"`` instead of raising. The frontend in
"demo-without-graph" mode keeps working against :class:`LocalDetector`.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone
from typing import Any

import httpx

from ..config import Settings, get_settings
from ..queries import gdsl as _gdsl
from ..queries.funds_queries import (
    GSQL_BURST_AMOUNT,
    GSQL_CIRCULAR_FUNDS,
    GSQL_FUNDS_PATH_TRACE,
)
from .local_detector import snapshot_from_dataset
from .funds_local import (
    find_burst_amount,
    find_circular_funds,
    trace_funds_paths,
)
from .models import (
    DetectionRun,
    GraphSnapshot,
    RiskAlert,
    burst_amount_alert_from_gsql,
    circular_funds_alert_from_gsql,
    funds_path_trace_alert_from_gsql,
    adamic_adar_alert_from_gsql,
    article_rank_alert_from_gsql,
    astar_alert_from_gsql,
    betweenness_alert_from_gsql,
    bfs_alert_from_gsql,
    burst_alert_from_gsql,
    closeness_alert_from_gsql,
    common_neighbors_alert_from_gsql,
    cosine_sim_alert_from_gsql,
    cycle_alert_from_gsql,
    degree_cent_alert_from_gsql,
    diameter_alert_from_gsql,
    embedding_alert_from_gsql,
    eigenvector_alert_from_gsql,
    fpm_alert_from_gsql,
    greedy_coloring_alert_from_gsql,
    harmonic_alert_from_gsql,
    influence_max_alert_from_gsql,
    jaccard_alert_from_gsql,
    kcore_alert_from_gsql,
    kmeans_alert_from_gsql,
    knn_alert_from_gsql,
    lcc_alert_from_gsql,
    louvain_alert_from_gsql,
    lpcc_alert_from_gsql,
    map_eq_alert_from_gsql,
    maxflow_alert_from_gsql,
    mis_alert_from_gsql,
    mst_alert_from_gsql,
    pagerank_alert_from_gsql,
    pagerank_extended_alert_from_gsql,
    pagerank_personalized_alert_from_gsql,
    path_alert_from_gsql,
    preferential_alert_from_gsql,
    resource_alloc_alert_from_gsql,
    ring_alert_from_gsql,
    same_community_alert_from_gsql,
    scc_alert_from_gsql,
    shared_device_alert_from_gsql,
    shortest_path_alert_from_gsql,
    slpa_alert_from_gsql,
    total_neighbors_alert_from_gsql,
    tri_count_alert_from_gsql,
    wcc_alert_from_gsql,
    weighted_degree_cent_alert_from_gsql,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _post_query(
    client: httpx.Client,
    settings: Settings,
    name: str,
    params: dict[str, Any] | None = None,
) -> dict:
    body = {"graph": settings.tg_graph_name, "params": params or {}}
    r = client.post(f"{settings.restpp_url}/query/{name}", json=body, timeout=30.0)
    r.raise_for_status()
    try:
        return r.json()
    except json.JSONDecodeError:
        return {"results": [], "_raw": r.text}


class TigerGraphDetector:
    """Run every detection query and produce a structured
    :class:`DetectionRun`."""

    def __init__(self, settings: Settings | None = None) -> None:
        self.settings = settings or get_settings()

    def ping(self) -> bool:
        try:
            with httpx.Client() as c:
                r = c.get(f"{self.settings.restpp_url}/echo", timeout=5.0)
                return r.status_code == 200
        except httpx.HTTPError:
            return False

    def run(self, *, top_k: int = 50) -> DetectionRun:
        started = _now()
        t0 = time.perf_counter()
        alerts: list[RiskAlert] = []
        status = "ok"
        detail_parts: list[str] = []

        try:
            with httpx.Client() as client:
                if not self.ping():
                    raise RuntimeError("TigerGraph RESTPP not reachable")

                # 1) Transaction rings
                try:
                    res = _post_query(
                        client,
                        self.settings,
                        "transactionRings",
                        {"minLen": self.settings.thresh_ring_min_len, "maxLen": 6, "limitPerRing": 50},
                    )
                    a = ring_alert_from_gsql(res)
                    if a:
                        alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"transactionRings={exc}")

                # 2) Shared devices
                try:
                    res = _post_query(
                        client,
                        self.settings,
                        "sharedDeviceRings",
                        {"minShared": self.settings.thresh_shared_device_min, "limitAccounts": 200},
                    )
                    a = shared_device_alert_from_gsql(res)
                    if a:
                        alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"sharedDeviceRings={exc}")

                # 3) Burst transactions
                try:
                    res = _post_query(
                        client,
                        self.settings,
                        "burstTransactions",
                        {
                            "windowMin": self.settings.thresh_burst_tx_window_min,
                            "minCount": self.settings.thresh_burst_tx_count,
                            "limitAccounts": 200,
                        },
                    )
                    a = burst_alert_from_gsql(res)
                    if a:
                        alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"burstTransactions={exc}")

                # 4) Top-K centrality
                try:
                    res = _post_query(
                        client,
                        self.settings,
                        "pageRankAccounts",
                        {"damping": 0.85, "iterations": 25, "topK": top_k},
                    )
                    a = pagerank_alert_from_gsql(res, top_k=top_k)
                    if a:
                        alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"pageRankAccounts={exc}")

                # 5) Weakly Connected Components (entity-resolution helper)
                try:
                    res = _post_query(
                        client,
                        self.settings,
                        "tg_wcc",
                        {
                            "v_type": "Account",
                            "e_type": "SHARES_DEVICE",
                            "max_iter": 10,
                            "print_limit": 100,
                        },
                    )
                    a = wcc_alert_from_gsql(res)
                    if a:
                        alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_wcc={exc}")

                # 6) Community Detection (Label Propagation)
                try:
                    res = _post_query(
                        client,
                        self.settings,
                        "tg_lpcc",
                        {
                            "v_type": "Account",
                            "e_type": "SHARES_DEVICE",
                            "max_iter": 20,
                            "seed": 42,
                            "print_limit": 100,
                        },
                    )
                    a = lpcc_alert_from_gsql(res)
                    if a:
                        alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_lpcc={exc}")

                # 7) Jaccard Similarity (identity-link scoring)
                try:
                    res = _post_query(
                        client,
                        self.settings,
                        "tg_jaccard",
                        {
                            "source_id": "A0",
                            "target_id": "A1",
                            "v_type": "Account",
                            "e_type": "USES_DEVICE",
                            "top_k": top_k,
                        },
                    )
                    a = jaccard_alert_from_gsql(res)
                    if a:
                        alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_jaccard={exc}")

                # 8) Betweenness Centrality (broker / mule detection)
                try:
                    res = _post_query(
                        client,
                        self.settings,
                        "tg_betweenness",
                        {
                            "v_type": "Account",
                            "e_type": "SHARES_DEVICE",
                            "sample_size": 0,
                            "top_k": top_k,
                        },
                    )
                    a = betweenness_alert_from_gsql(res)
                    if a:
                        alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_betweenness={exc}")

                # 9) Closeness Centrality (hub detection)
                try:
                    res = _post_query(
                        client,
                        self.settings,
                        "tg_closeness",
                        {
                            "v_type": "Account",
                            "e_type": "SHARES_DEVICE",
                            "top_k": top_k,
                        },
                    )
                    a = closeness_alert_from_gsql(res)
                    if a:
                        alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_closeness={exc}")

                # ── GDSL library queries (69 total) ─────────────────────────────────
                # Centrality
                def _gdsl(
                    client,
                    name: str,
                    params: dict[str, Any] | None = None,
                ) -> dict:
                    return _post_query(client, self.settings, name, params)

                # 10) Article Rank
                try:
                    res = _gdsl(client, "tg_article_rank", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "reverse_e_type": ["SHARES_DEVICE"], "top_k": top_k})
                    a = article_rank_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_article_rank={exc}")

                # 11) Eigenvector Cent
                try:
                    res = _gdsl(client, "tg_eigenvector_cent", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "reverse_e_type": ["SHARES_DEVICE"], "top_k": top_k})
                    a = eigenvector_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_eigenvector_cent={exc}")

                # 12) Harmonic Cent
                try:
                    res = _gdsl(client, "tg_harmonic_cent", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "reverse_e_type": ["SHARES_DEVICE"], "top_k": top_k})
                    a = harmonic_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_harmonic_cent={exc}")

                # 13) Degree Cent (unweighted)
                try:
                    res = _gdsl(client, "tg_degree_cent", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "reverse_e_type": ["SHARES_DEVICE"], "top_k": top_k})
                    a = degree_cent_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_degree_cent={exc}")

                # 14) Weighted Degree Cent
                try:
                    res = _gdsl(client, "tg_weighted_degree_cent", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "reverse_e_type": ["SHARES_DEVICE"], "top_k": top_k})
                    a = weighted_degree_cent_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_weighted_degree_cent={exc}")

                # 15) PageRank (global unweighted)
                try:
                    res = _gdsl(client, "tg_pagerank", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "reverse_e_type": ["SHARES_DEVICE"], "top_k": top_k})
                    a = pagerank_extended_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_pagerank={exc}")

                # 16) PageRank (global weighted)
                try:
                    res = _gdsl(client, "tg_pagerank_wt", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "reverse_e_type": ["SHARES_DEVICE"], "top_k": top_k})
                    a = pagerank_extended_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_pagerank_wt={exc}")

                # 17) PageRank (personalized)
                try:
                    res = _gdsl(client, "tg_pagerank_pers", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "reverse_e_type": ["SHARES_DEVICE"], "top_k": top_k})
                    a = pagerank_personalized_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_pagerank_pers={exc}")

                # 18) Influence Maximization (CELF)
                try:
                    res = _gdsl(client, "tg_influence_maximization_CELF", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "k": 10})
                    a = influence_max_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_influence_maximization_CELF={exc}")

                # Community: SCC
                try:
                    res = _gdsl(client, "tg_scc", {"v_type_set": ["Account"], "e_type_set": ["FROM_ACCOUNT"], "print_limit": top_k})
                    a = scc_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_scc={exc}")

                # Community: k-core
                try:
                    res = _gdsl(client, "tg_kcore", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "k": 3, "print_limit": top_k})
                    a = kcore_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_kcore={exc}")

                # Community: Louvain
                try:
                    res = _gdsl(client, "tg_louvain", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "print_limit": top_k})
                    a = louvain_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_louvain={exc}")

                # Community: Local Clustering Coefficient
                try:
                    res = _gdsl(client, "tg_lcc", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "print_limit": top_k})
                    a = lcc_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_lcc={exc}")

                # Community: Map Equation
                try:
                    res = _gdsl(client, "tg_map_equation", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "print_limit": top_k})
                    a = map_eq_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_map_equation={exc}")

                # Community: SLPA
                try:
                    res = _gdsl(client, "tg_slpa", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "maximum_iteration": 20, "print_limit": top_k})
                    a = slpa_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_slpa={exc}")

                # Community: Triangle Counting (fast)
                try:
                    res = _gdsl(client, "tg_tri_count_fast", {"v_type_set": ["Account"], "e_type_set": ["FROM_ACCOUNT"]})
                    a = tri_count_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_tri_count_fast={exc}")

                # Classification: KNN (single source)
                try:
                    res = _gdsl(client, "tg_knn_cosine_ss", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "k": 5, "max_top_k": top_k})
                    a = knn_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_knn_cosine_ss={exc}")

                # Classification: Greedy Graph Coloring
                try:
                    res = _gdsl(client, "tg_greedy_graph_coloring", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"]})
                    a = greedy_coloring_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_greedy_graph_coloring={exc}")

                # Classification: Maximal Independent Set
                try:
                    res = _gdsl(client, "tg_maximal_indep_set", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"]})
                    a = mis_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_maximal_indep_set={exc}")

                # Path: BFS
                try:
                    res = _gdsl(client, "tg_bfs", {"v_start": "Account", "e_type_set": ["SHARES_DEVICE"], "max_hops": 5, "target": ""})
                    a = bfs_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_bfs={exc}")

                # Path: Shortest path (no weight)
                try:
                    res = _gdsl(client, "tg_shortest_ss_no_wt", {"v_start": "", "v_target": "", "e_type": "SHARES_DEVICE", "max_hops": 10})
                    a = shortest_path_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_shortest_ss_no_wt={exc}")

                # Path: Shortest path (weighted positive)
                try:
                    res = _gdsl(client, "tg_shortest_ss_pos_wt", {"v_start": "", "v_target": "", "e_type": "SHARES_DEVICE", "weight_attr": "amount", "max_hops": 10})
                    a = shortest_path_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_shortest_ss_pos_wt={exc}")

                # Path: Cycle Detection (count)
                try:
                    res = _gdsl(client, "tg_cycle_detection_count", {"v_type_set": ["Account"], "e_type_set": ["FROM_ACCOUNT"]})
                    a = cycle_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_cycle_detection_count={exc}")

                # Path: Max Flow
                try:
                    res = _gdsl(client, "tg_maxflow", {"v_source": "", "v_target": "", "e_type_set": ["FROM_ACCOUNT"], "reverse_e_type_set": ["TO_ACCOUNT"]})
                    a = maxflow_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_maxflow={exc}")

                # Path: MST
                try:
                    res = _gdsl(client, "tg_msf", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "reverse_e_type_set": ["SHARES_DEVICE"]})
                    a = mst_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_msf={exc}")

                # Path: Estimated Diameter
                try:
                    res = _gdsl(client, "tg_estimate_diameter", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "reverse_e_type_set": ["SHARES_DEVICE"]})
                    a = diameter_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_estimate_diameter={exc}")

                # Similarity: Jaccard (all-pairs)
                try:
                    res = _gdsl(client, "tg_jaccard_nbor_ap_batch", {"e_type": "SHARES_DEVICE", "top_k": top_k})
                    a = jaccard_ext_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_jaccard_nbor_ap_batch={exc}")

                # Similarity: Cosine (single-source)
                try:
                    res = _gdsl(client, "tg_cosine_nbor_ss", {"src": "", "e_type": "SHARES_DEVICE", "top_k": top_k})
                    a = cosine_sim_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_cosine_nbor_ss={exc}")

                # Topological Link Prediction: all 6
                try:
                    res = _gdsl(client, "tg_adamic_adar", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "reverse_e_type_set": ["SHARES_DEVICE"], "top_k": top_k})
                    a = adamic_adar_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_adamic_adar={exc}")

                try:
                    res = _gdsl(client, "tg_common_neighbors", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "reverse_e_type_set": ["SHARES_DEVICE"], "top_k": top_k})
                    a = common_neighbors_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_common_neighbors={exc}")

                try:
                    res = _gdsl(client, "tg_preferential_attachment", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "reverse_e_type_set": ["SHARES_DEVICE"], "top_k": top_k})
                    a = preferential_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_preferential_attachment={exc}")

                try:
                    res = _gdsl(client, "tg_resource_allocation", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "reverse_e_type_set": ["SHARES_DEVICE"], "top_k": top_k})
                    a = resource_alloc_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_resource_allocation={exc}")

                try:
                    res = _gdsl(client, "tg_same_community", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "reverse_e_type_set": ["SHARES_DEVICE"], "top_k": top_k})
                    a = same_community_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_same_community={exc}")

                try:
                    res = _gdsl(client, "tg_total_neighbors", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "reverse_e_type_set": ["SHARES_DEVICE"], "top_k": top_k})
                    a = total_neighbors_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_total_neighbors={exc}")

                # Patterns: Frequent Pattern Mining
                try:
                    res = _gdsl(client, "tg_fpm", {"v_type_set": ["Account"], "e_type_set": ["FROM_ACCOUNT"], "min_support": 0.01, "min_pattern_size": 2, "max_pattern_size": 5})
                    a = fpm_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_fpm={exc}")

                # GraphML: FastRP embeddings
                try:
                    res = _gdsl(client, "tg_fastRP", {"v_type_set": ["Account"], "e_type_set": ["SHARES_DEVICE"], "embedding_size": 64, "num_iterations": 3})
                    a = embedding_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"tg_fastRP={exc}")

                # ── Funds-flow detectors (Cypher → GSQL port) ─────────────
                # The TG-side runs the GSQL strings in `app.queries.funds_queries`;
                # the local fallback (see run_local_detector + funds_local) uses the
                # pure-Python equivalent so the demo-without-graph mode keeps working
                # when TigerGraph is unreachable.
                try:
                    res = _gdsl(
                        client,
                        "circularFunds",
                        {"min_total": 50000.0, "max_hops": 6},
                    )
                    a = circular_funds_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"circularFunds={exc}")

                try:
                    res = _gdsl(
                        client,
                        "burstAmount",
                        {"start_ts": "1970-01-01T00:00:00Z", "burst_factor": 5.0, "edge_limit": 5000},
                    )
                    a = burst_amount_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"burstAmount={exc}")

                # Path trace needs a seed account. Pass empty string → GSQL falls
                # through and returns an empty result without trashing the run.
                try:
                    res = _gdsl(
                        client,
                        "fundsPathTrace",
                        {"start_id": "", "start_ts": "1970-01-01T00:00:00Z", "max_hops": 5, "path_limit": 200},
                    )
                    a = funds_path_trace_alert_from_gsql(res)
                    if a: alerts.append(a)
                except httpx.HTTPError as exc:
                    detail_parts.append(f"fundsPathTrace={exc}")

        except Exception as exc:
            status = "degraded" if alerts else "unreachable"
            detail_parts.append(str(exc))

        elapsed_ms = int((time.perf_counter() - t0) * 1000)
        ended = _now()
        metrics = {
            "alerts_total": len(alerts),
            "elapsed_ms": elapsed_ms,
        }
        return DetectionRun(
            run_id=str(uuid.uuid4()),
            started_at=started,
            ended_at=ended,
            backend="tigergraph",
            status=status,
            detail="; ".join(detail_parts) or "ok",
            alerts=alerts,
            snapshot=GraphSnapshot(),
            metrics=metrics,
        )


def run_remote_detector(
    fallback_dataset=None, settings: Settings | None = None
) -> DetectionRun:
    """Convenience that returns a TigerGraph result if reachable, otherwise
    falls back to :func:`run_local_detector` over ``fallback_dataset``.
    """
    det = TigerGraphDetector(settings=settings)
    res = det.run()
    if res.status in ("ok", "partial") and res.alerts:
        return res
    if fallback_dataset is not None:
        from .local_detector import run_local_detector

        local = run_local_detector(fallback_dataset)
        # Surface the fallback explicitly
        from dataclasses import replace

        return replace(
            local,
            backend=f"{local.backend}+fallback",
            detail=(
                f"TigerGraph unreachable; served local fallback. {local.detail}"
            ),
        )
    return res