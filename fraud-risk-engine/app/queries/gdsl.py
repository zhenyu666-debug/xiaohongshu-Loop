"""Auto-generated GDSL query strings from TigerGraph GSQL Graph Algorithm Library.

Source: gsql-graph-algorithms-tg_4.4.0_dev.zip (https://github.com/tigergraph/gsql-graph-algorithms)
Date: 2026-07-19

This file is auto-generated. To regenerate:
    python gen_gdsl.py

Total: 69 GSQL queries across 8 categories:
    Centrality (14), Classification (8), Community (14),
    GraphML (4), Path (17), Patterns (2), Similarity (4),
    Topological Link Prediction (6)
"""

from __future__ import annotations

import pathlib

# Resolve gdsl/ directory relative to this file
_GDSL_DIR = pathlib.Path(__file__).parent / "gdsl"


def _load(name: str) -> str:
    """Load a GSQL query file and strip trailing whitespace."""
    p = _GDSL_DIR / name
    return p.read_text(encoding="utf-8", errors="replace").rstrip()


# ─────────────────────────────────────────────────────────────────────────────
# Centrality (14 queries)
# ─────────────────────────────────────────────────────────────────────────────

CENTRALITY_ARTICLE_RANK = _load("Centrality/article_rank/tg_article_rank.gsql")
CENTRALITY_BETWEENNESS_CENT = _load("Centrality/betweenness/tg_betweenness_cent.gsql")
CENTRALITY_CLOSENESS_CENT = _load("Centrality/closeness/exact/tg_closeness_cent.gsql")
CENTRALITY_CLOSENESS_CENT_APPROX = _load("Centrality/closeness/approximate/tg_closeness_cent_approx.gsql")
CENTRALITY_DEGREE_CENT = _load("Centrality/degree/unweighted/tg_degree_cent.gsql")
CENTRALITY_WEIGHTED_DEGREE_CENT = _load("Centrality/degree/weighted/tg_weighted_degree_cent.gsql")
CENTRALITY_EIGENVECTOR_CENT = _load("Centrality/eigenvector/tg_eigenvector_cent.gsql")
CENTRALITY_HARMONIC_CENT = _load("Centrality/harmonic/tg_harmonic_cent.gsql")
CENTRALITY_INFLUENCE_MAXIMIZATION_CELF = _load("Centrality/influence_maximization/CELF/tg_influence_maximization_CELF.gsql")
CENTRALITY_INFLUENCE_MAXIMIZATION_GREEDY = _load("Centrality/influence_maximization/greedy/tg_influence_maximization_greedy.gsql")
CENTRALITY_PAGERANK = _load("Centrality/pagerank/global/unweighted/tg_pagerank.gsql")
CENTRALITY_PAGERANK_PERS = _load("Centrality/pagerank/personalized/multi_source/tg_pagerank_pers.gsql")
CENTRALITY_PAGERANK_PERS_AP_BATCH = _load("Centrality/pagerank/personalized/all_pairs/tg_pagerank_pers_ap_batch.gsql")
CENTRALITY_PAGERANK_WT = _load("Centrality/pagerank/global/weighted/tg_pagerank_wt.gsql")

# ─────────────────────────────────────────────────────────────────────────────
# Classification (8 queries)
# ─────────────────────────────────────────────────────────────────────────────

CLASSIFICATION_GREEDY_GRAPH_COLORING = _load("Classification/greedy_graph_coloring/tg_greedy_graph_coloring.gsql")
CLASSIFICATION_KNN_COSINE_ALL = _load("Classification/k_nearest_neighbors/all_pairs/tg_knn_cosine_all.gsql")
CLASSIFICATION_KNN_COSINE_ALL_SUB = _load("Classification/k_nearest_neighbors/all_pairs/tg_knn_cosine_all_sub.gsql")
CLASSIFICATION_KNN_COSINE_CV = _load("Classification/k_nearest_neighbors/cross_validation/tg_knn_cosine_cv.gsql")
CLASSIFICATION_KNN_COSINE_CV_SUB = _load("Classification/k_nearest_neighbors/cross_validation/tg_knn_cosine_cv_sub.gsql")
CLASSIFICATION_KNN_COSINE_SS = _load("Classification/k_nearest_neighbors/single_source/tg_knn_cosine_ss.gsql")
CLASSIFICATION_MAXIMAL_INDEP_SET = _load("Classification/maximal_independent_set/deterministic/tg_maximal_indep_set.gsql")
CLASSIFICATION_MAXIMAL_INDEP_SET_RANDOM = _load("Classification/maximal_independent_set/random/tg_maximal_indep_set_random.gsql")

# ─────────────────────────────────────────────────────────────────────────────
# Community (14 queries)
# ─────────────────────────────────────────────────────────────────────────────

COMMUNITY_SCC = _load("Community/connected_components/strongly_connected_components/standard/tg_scc.gsql")
COMMUNITY_SCC_SMALL_WORLD = _load("Community/connected_components/strongly_connected_components/small_world/tg_scc_small_world.gsql")
COMMUNITY_WCC = _load("Community/connected_components/weakly_connected_components/standard/tg_wcc.gsql")
COMMUNITY_WCC_SMALL_WORLD = _load("Community/connected_components/weakly_connected_components/small_world/tg_wcc_small_world.gsql")
COMMUNITY_KCORE = _load("Community/k_core/tg_kcore.gsql")
COMMUNITY_KMEANS = _load("Community/k_means/tg_kmeans.gsql")
COMMUNITY_KMEANS_SUB = _load("Community/k_means/tg_kmeans_sub.gsql")
COMMUNITY_LABEL_PROP = _load("Community/label_propagation/tg_label_prop.gsql")
COMMUNITY_LCC = _load("Community/local_clustering_coefficient/tg_lcc.gsql")
COMMUNITY_LOUVAIN = _load("Community/louvain/tg_louvain.gsql")
COMMUNITY_MAP_EQUATION = _load("Community/map_equation/tg_map_equation.gsql")
COMMUNITY_SLPA = _load("Community/speaker-listener_label_propagation/tg_slpa.gsql")
COMMUNITY_TRI_COUNT = _load("Community/triangle_counting/standard/tg_tri_count.gsql")
COMMUNITY_TRI_COUNT_FAST = _load("Community/triangle_counting/fast/tg_tri_count_fast.gsql")

# ─────────────────────────────────────────────────────────────────────────────
# GraphML Embeddings (4 queries)
# ─────────────────────────────────────────────────────────────────────────────

GRAPHML_EMBEDDING_COSINE_SIM = _load("GraphML/Embeddings/EmbeddingSimilarity/single_source/tg_embedding_cosine_sim.gsql")
GRAPHML_EMBEDDING_PAIRWISE_COSINE_SIM = _load("GraphML/Embeddings/EmbeddingSimilarity/pairwise/tg_embedding_pairwise_cosine_sim.gsql")
GRAPHML_FASTRP = _load("GraphML/Embeddings/FastRP/tg_fastRP.gsql")
GRAPHML_WEISFEILER_LEHMAN = _load("GraphML/Embeddings/weisfeiler_lehman/tg_weisfeiler_lehman.gsql")

# ─────────────────────────────────────────────────────────────────────────────
# Path (17 queries)
# ─────────────────────────────────────────────────────────────────────────────

PATH_ASTAR = _load("Path/astar_shortest_path/tg_astar.gsql")
PATH_BFS = _load("Path/bfs/tg_bfs.gsql")
PATH_CYCLE_COMPONENT = _load("Path/cycle_component/tg_cycle_component.gsql")
PATH_CYCLE_DETECTION = _load("Path/cycle_detection/full_result/standard/tg_cycle_detection.gsql")
PATH_CYCLE_DETECTION_BATCH = _load("Path/cycle_detection/full_result/batch/tg_cycle_detection_batch.gsql")
PATH_CYCLE_DETECTION_COUNT = _load("Path/cycle_detection/count/tg_cycle_detection_count.gsql")
PATH_ESTIMATE_DIAMETER = _load("Path/estimated_diameter/approximate/tg_estimate_diameter.gsql")
PATH_MAX_BFS_DEPTH = _load("Path/estimated_diameter/max_bfs/tg_max_BFS_depth.gsql")
PATH_MAXFLOW = _load("Path/maxflow/tg_maxflow.gsql")
PATH_MSF = _load("Path/minimum_spanning_forest/tg_msf.gsql")
PATH_MST = _load("Path/minimum_spanning_tree/tg_mst.gsql")
PATH_ALL_PATH = _load("Path/path_between_two_vertices/one_direction/tg_all_path.gsql")
PATH_ALL_PATH_BIDIRECTION = _load("Path/path_between_two_vertices/bidirection/tg_all_path_bidirection.gsql")
PATH_SHORTEST_SS_ANY_WT = _load("Path/shortest_path/weighted/any_sign/tg_shortest_ss_any_wt.gsql")
PATH_SHORTEST_SS_NO_WT = _load("Path/shortest_path/unweighted/tg_shortest_ss_no_wt.gsql")
PATH_SHORTEST_SS_POS_WT = _load("Path/shortest_path/weighted/positive/summary/tg_shortest_ss_pos_wt.gsql")
PATH_SHORTEST_SS_POS_WT_TB = _load("Path/shortest_path/weighted/positive/traceback/tg_shortest_ss_pos_wt_tb.gsql")

# ─────────────────────────────────────────────────────────────────────────────
# Patterns (2 queries)
# ─────────────────────────────────────────────────────────────────────────────

PATTERNS_FPM = _load("Patterns/frequent_pattern_mining/tg_fpm.gsql")
PATTERNS_FPM_PRE = _load("Patterns/frequent_pattern_mining/tg_fpm_pre.gsql")

# ─────────────────────────────────────────────────────────────────────────────
# Similarity (4 queries)
# ─────────────────────────────────────────────────────────────────────────────

SIMILARITY_COSINE_NBOR_AP_BATCH = _load("Similarity/cosine/all_pairs/tg_cosine_nbor_ap_batch.gsql")
SIMILARITY_COSINE_NBOR_SS = _load("Similarity/cosine/single_source/tg_cosine_nbor_ss.gsql")
SIMILARITY_JACCARD_NBOR_AP_BATCH = _load("Similarity/jaccard/all_pairs/tg_jaccard_nbor_ap_batch.gsql")
SIMILARITY_JACCARD_NBOR_SS = _load("Similarity/jaccard/single_source/tg_jaccard_nbor_ss.gsql")

# ─────────────────────────────────────────────────────────────────────────────
# Topological Link Prediction (6 queries)
# ─────────────────────────────────────────────────────────────────────────────

TLP_ADAMIC_ADAR = _load("Topological Link Prediction/adamic_adar/tg_adamic_adar.gsql")
TLP_COMMON_NEIGHBORS = _load("Topological Link Prediction/common_neighbors/tg_common_neighbors.gsql")
TLP_PREFERENTIAL_ATTACHMENT = _load("Topological Link Prediction/preferential_attachment/tg_preferential_attachment.gsql")
TLP_RESOURCE_ALLOCATION = _load("Topological Link Prediction/resource_allocation/tg_resource_allocation.gsql")
TLP_SAME_COMMUNITY = _load("Topological Link Prediction/same_community/tg_same_community.gsql")
TLP_TOTAL_NEIGHBORS = _load("Topological Link Prediction/total_neighbors/tg_total_neighbors.gsql")

# ─────────────────────────────────────────────────────────────────────────────
# All queries grouped by category (convenience dict)
# ─────────────────────────────────────────────────────────────────────────────

CENTRALITY = {
    "tg_article_rank": CENTRALITY_ARTICLE_RANK,
    "tg_betweenness_cent": CENTRALITY_BETWEENNESS_CENT,
    "tg_closeness_cent": CENTRALITY_CLOSENESS_CENT,
    "tg_closeness_cent_approx": CENTRALITY_CLOSENESS_CENT_APPROX,
    "tg_degree_cent": CENTRALITY_DEGREE_CENT,
    "tg_weighted_degree_cent": CENTRALITY_WEIGHTED_DEGREE_CENT,
    "tg_eigenvector_cent": CENTRALITY_EIGENVECTOR_CENT,
    "tg_harmonic_cent": CENTRALITY_HARMONIC_CENT,
    "tg_influence_maximization_CELF": CENTRALITY_INFLUENCE_MAXIMIZATION_CELF,
    "tg_influence_maximization_greedy": CENTRALITY_INFLUENCE_MAXIMIZATION_GREEDY,
    "tg_pagerank": CENTRALITY_PAGERANK,
    "tg_pagerank_pers": CENTRALITY_PAGERANK_PERS,
    "tg_pagerank_pers_ap_batch": CENTRALITY_PAGERANK_PERS_AP_BATCH,
    "tg_pagerank_wt": CENTRALITY_PAGERANK_WT,
}

CLASSIFICATION = {
    "tg_greedy_graph_coloring": CLASSIFICATION_GREEDY_GRAPH_COLORING,
    "tg_knn_cosine_all": CLASSIFICATION_KNN_COSINE_ALL,
    "tg_knn_cosine_all_sub": CLASSIFICATION_KNN_COSINE_ALL_SUB,
    "tg_knn_cosine_cv": CLASSIFICATION_KNN_COSINE_CV,
    "tg_knn_cosine_cv_sub": CLASSIFICATION_KNN_COSINE_CV_SUB,
    "tg_knn_cosine_ss": CLASSIFICATION_KNN_COSINE_SS,
    "tg_maximal_indep_set": CLASSIFICATION_MAXIMAL_INDEP_SET,
    "tg_maximal_indep_set_random": CLASSIFICATION_MAXIMAL_INDEP_SET_RANDOM,
}

COMMUNITY = {
    "tg_scc": COMMUNITY_SCC,
    "tg_scc_small_world": COMMUNITY_SCC_SMALL_WORLD,
    "tg_wcc": COMMUNITY_WCC,
    "tg_wcc_small_world": COMMUNITY_WCC_SMALL_WORLD,
    "tg_kcore": COMMUNITY_KCORE,
    "tg_kmeans": COMMUNITY_KMEANS,
    "tg_kmeans_sub": COMMUNITY_KMEANS_SUB,
    "tg_label_prop": COMMUNITY_LABEL_PROP,
    "tg_lcc": COMMUNITY_LCC,
    "tg_louvain": COMMUNITY_LOUVAIN,
    "tg_map_equation": COMMUNITY_MAP_EQUATION,
    "tg_slpa": COMMUNITY_SLPA,
    "tg_tri_count": COMMUNITY_TRI_COUNT,
    "tg_tri_count_fast": COMMUNITY_TRI_COUNT_FAST,
}

GRAPHML = {
    "tg_embedding_cosine_sim": GRAPHML_EMBEDDING_COSINE_SIM,
    "tg_embedding_pairwise_cosine_sim": GRAPHML_EMBEDDING_PAIRWISE_COSINE_SIM,
    "tg_fastRP": GRAPHML_FASTRP,
    "tg_weisfeiler_lehman": GRAPHML_WEISFEILER_LEHMAN,
}

PATH = {
    "tg_astar": PATH_ASTAR,
    "tg_bfs": PATH_BFS,
    "tg_cycle_component": PATH_CYCLE_COMPONENT,
    "tg_cycle_detection": PATH_CYCLE_DETECTION,
    "tg_cycle_detection_batch": PATH_CYCLE_DETECTION_BATCH,
    "tg_cycle_detection_count": PATH_CYCLE_DETECTION_COUNT,
    "tg_estimate_diameter": PATH_ESTIMATE_DIAMETER,
    "tg_max_BFS_depth": PATH_MAX_BFS_DEPTH,
    "tg_maxflow": PATH_MAXFLOW,
    "tg_msf": PATH_MSF,
    "tg_mst": PATH_MST,
    "tg_all_path": PATH_ALL_PATH,
    "tg_all_path_bidirection": PATH_ALL_PATH_BIDIRECTION,
    "tg_shortest_ss_any_wt": PATH_SHORTEST_SS_ANY_WT,
    "tg_shortest_ss_no_wt": PATH_SHORTEST_SS_NO_WT,
    "tg_shortest_ss_pos_wt": PATH_SHORTEST_SS_POS_WT,
    "tg_shortest_ss_pos_wt_tb": PATH_SHORTEST_SS_POS_WT_TB,
}

PATTERNS = {
    "tg_fpm": PATTERNS_FPM,
    "tg_fpm_pre": PATTERNS_FPM_PRE,
}

SIMILARITY = {
    "tg_cosine_nbor_ap_batch": SIMILARITY_COSINE_NBOR_AP_BATCH,
    "tg_cosine_nbor_ss": SIMILARITY_COSINE_NBOR_SS,
    "tg_jaccard_nbor_ap_batch": SIMILARITY_JACCARD_NBOR_AP_BATCH,
    "tg_jaccard_nbor_ss": SIMILARITY_JACCARD_NBOR_SS,
}

TLP = {
    "tg_adamic_adar": TLP_ADAMIC_ADAR,
    "tg_common_neighbors": TLP_COMMON_NEIGHBORS,
    "tg_preferential_attachment": TLP_PREFERENTIAL_ATTACHMENT,
    "tg_resource_allocation": TLP_RESOURCE_ALLOCATION,
    "tg_same_community": TLP_SAME_COMMUNITY,
    "tg_total_neighbors": TLP_TOTAL_NEIGHBORS,
}

# All queries flat dict (name -> GSQL string)
ALL_QUERIES: dict[str, str] = {}
for cat in [CENTRALITY, CLASSIFICATION, COMMUNITY, GRAPHML, PATH, PATTERNS, SIMILARITY, TLP]:
    ALL_QUERIES.update(cat)

# Category labels
CATEGORIES = {
    "centrality": "Centrality",
    "classification": "Classification",
    "community": "Community",
    "graphml": "GraphML / Embeddings",
    "path": "Path",
    "patterns": "Patterns",
    "similarity": "Similarity",
    "tlp": "Topological Link Prediction",
}
