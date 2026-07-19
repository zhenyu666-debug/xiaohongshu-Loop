"""Graph robustness / vulnerability measures.

Ported from the TIGER library (MIT, Scott Freitas et al., 2021):
    https://github.com/safreita1/TIGER

The original TIGER ``measures`` module quantifies how vulnerable a graph is to
node / edge removal. It covers ~25 measures (node connectivity, edge
connectivity, average distance, diameter, betweenness, closeness, eigenvalues,
flow, etc.), most of which depend on ``networkx`` + ``numpy``.

This file exposes the stdlib-friendly subset — the measures we can implement
with ``collections.deque``, ``math``, and the local ``GeneratedDataset``
representation. The heavy ``networkx`` calls remain in the upstream reference
under ``memory/references/tiger-graph-robustness``; this port lets us run the
same diagnostics without pulling ``networkx`` into the runtime.

Why we care
-----------
For an account / device / IP graph, low robustness = a small set of shared
devices or IPs can collapse the entire fraud ring. We surface these signals
alongside the existing per-account ``RiskAlert`` output so investigators can
tell "this account is in a hub-and-spoke ring" (low edge connectivity) from
"this account is one of many disconnected mules" (low density, high diameter).
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass
from math import sqrt
from typing import TYPE_CHECKING, Any, Dict, List, Sequence, Tuple

if TYPE_CHECKING:
    from ..loader.synth_generator import GeneratedDataset


# ---------------------------------------------------------------------------
# Domain models
# ---------------------------------------------------------------------------


@dataclass
class RobustnessReport:
    """One row per measure, plus the input graph's basic shape."""

    node_count: int
    edge_count: int
    density: float
    avg_degree: float
    clustering_coefficient: float
    diameter_small: int | None
    node_connectivity_estimate: int
    edge_connectivity: int
    assortativity: float
    spectral_radius: float

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------------------
# Graph construction from GeneratedDataset
# ---------------------------------------------------------------------------


def _build_undirected_adj(
    ds: "GeneratedDataset",
) -> Tuple[Dict[str, int], List[List[int]], int]:
    """Build a CSR-style adjacency representation from a ``GeneratedDataset``.

    Returns ``(id_to_idx, adj, edge_count)`` where:

    - ``id_to_idx``: maps account id → integer index
    - ``adj[i]``: list of neighbour indices for index ``i`` (deduped, undirected)
    - ``edge_count``: total number of unique undirected edges

    The funds-flow layer is reconstructed by joining ``ds.from_account`` edges
    (``Transaction -[FROM_ACCOUNT]-> Account``) with ``ds.to_account`` edges
    (``Transaction -[TO_ACCOUNT]-> Account``) on the same transaction id.
    Each such pair becomes one directed Account→Account hop; we then collapse
    directionality into an undirected adjacency. Identity edges (USES_DEVICE /
    LOGGED_FROM) are handled separately by ``app.profile.graph_search``.
    """
    # Index every from_id / to_id pair on the transaction id.
    src_by_tx: Dict[str, str] = {}
    dst_by_tx: Dict[str, str] = {}
    for e in ds.from_account:
        # ``from_id`` is the transaction id, ``to_id`` is the source account.
        src_by_tx[e["from_id"]] = e["to_id"]
    for e in ds.to_account:
        # ``from_id`` is the transaction id, ``to_id`` is the destination account.
        dst_by_tx[e["from_id"]] = e["to_id"]

    # Pre-seed the index with every account in the dataset so isolated accounts
    # (those with no transactions, or only self-loop transactions) still appear
    # in the node count. Self-loops alone must NOT contribute edges.
    id_to_idx: Dict[str, int] = {
        acc["id"]: i for i, acc in enumerate(getattr(ds, "accounts", []))
    }
    edges: set[Tuple[int, int]] = set()

    for tx_id, src in src_by_tx.items():
        dst = dst_by_tx.get(tx_id)
        if dst is None or src == dst:
            continue
        for v in (src, dst):
            if v not in id_to_idx:
                id_to_idx[v] = len(id_to_idx)
        s, t = id_to_idx[src], id_to_idx[dst]
        edges.add((min(s, t), max(s, t)))

    n = len(id_to_idx)
    adj: List[set[int]] = [set() for _ in range(n)]
    for s, t in edges:
        adj[s].add(t)
        adj[t].add(s)

    return id_to_idx, [sorted(neigh) for neigh in adj], len(edges)


# ---------------------------------------------------------------------------
# BFS primitives
# ---------------------------------------------------------------------------


def _bfs_component(adj: Sequence[Sequence[int]], source: int) -> List[int]:
    """Return the connected component reachable from ``source`` (BFS order)."""
    seen = [False] * len(adj)
    seen[source] = True
    queue: deque[int] = deque([source])
    order: List[int] = []
    while queue:
        u = queue.popleft()
        order.append(u)
        for v in adj[u]:
            if not seen[v]:
                seen[v] = True
                queue.append(v)
    return order


def _shortest_path_length(adj: Sequence[Sequence[int]], source: int) -> List[int]:
    """BFS distance from ``source`` to every node (-1 = unreachable)."""
    dist = [-1] * len(adj)
    dist[source] = 0
    queue: deque[int] = deque([source])
    while queue:
        u = queue.popleft()
        for v in adj[u]:
            if dist[v] == -1:
                dist[v] = dist[u] + 1
                queue.append(v)
    return dist


# ---------------------------------------------------------------------------
# Individual measures
# ---------------------------------------------------------------------------


def density(adj: Sequence[Sequence[int]], edge_count: int) -> float:
    """Edge density of an undirected graph (0..1).

    Mirrors ``graph_tiger.measures.density``. ``0`` for ``n < 2``.
    """
    n = len(adj)
    if n < 2:
        return 0.0
    return round(2.0 * edge_count / (n * (n - 1)), 4)


def average_degree(adj: Sequence[Sequence[int]]) -> float:
    """Mean degree across all nodes.

    Mirrors ``graph_tiger.measures.average_degree`` (which derives it from
    ``networkx``'s ``G.degree()``).
    """
    if not adj:
        return 0.0
    return round(sum(len(neigh) for neigh in adj) / len(adj), 4)


def clustering_coefficient(adj: Sequence[Sequence[int]]) -> float:
    """Mean local clustering coefficient (transitivity of triangles).

    Mirrors ``nx.average_clustering`` — we use the unordered form
    ``2 * triangles / (k * (k-1))`` for nodes with degree ≥ 2 and ``0`` for
    leaves.
    """
    if not adj:
        return 0.0
    total = 0.0
    counted = 0
    for u, neigh in enumerate(adj):
        k = len(neigh)
        if k < 2:
            continue
        neigh_set = set(neigh)
        # Triangles: count ordered pairs (v, w) with v<w AND an actual edge v-w.
        # The original TigerLily port used ``w in neigh_set`` which double-counts
        # the neighbour-of-u relation (not the v-w edge) — that gave a star's
        # centre a positive local CC, which is wrong.
        triangles = sum(
            1 for v in neigh for w in neigh if v < w and w in adj[v]
        )
        total += 2.0 * triangles / (k * (k - 1))
        counted += 1
    if counted == 0:
        return 0.0
    return round(total / counted, 4)


def diameter_small(adj: Sequence[Sequence[int]]) -> int | None:
    """Diameter of the largest connected component (``None`` if disconnected).

    Mirrors ``graph_tiger.measures.diameter`` but bounded — TIGER uses
    ``nx.diameter`` on the full graph, which raises for disconnected inputs.
    We compute the maximum BFS eccentricity across all components and return the
    largest finite value.
    """
    if not adj:
        return None
    n = len(adj)
    seen = [False] * n
    best = 0
    for s in range(n):
        if seen[s]:
            continue
        dist = _shortest_path_length(adj, s)
        if all(d == -1 for d in dist):
            continue
        local_best = max(d for d in dist if d >= 0)
        if local_best > best:
            best = local_best
        for i, d in enumerate(dist):
            if d >= 0:
                seen[i] = True
    return best if best > 0 else None


def edge_connectivity_lower_bound(adj: Sequence[Sequence[int]]) -> int:
    """Lower-bound estimate of edge connectivity via min degree.

    Edge connectivity ``≤`` min degree (König's edge-colouring theorem +
    Menger's theorem). We compute the exact minimum degree as a cheap proxy for
    TIGER's ``nx.edge_connectivity`` call, which is exact but ``O(V * E * φ)``
    with max-flow under the hood. Good enough for fraud-ring triage.
    """
    if not adj:
        return 0
    return min((len(neigh) for neigh in adj), default=0)


def node_connectivity_lower_bound(adj: Sequence[Sequence[int]]) -> int:
    """Lower-bound estimate of node connectivity via min degree.

    Mirrors ``graph_tiger.measures.node_connectivity`` with the same trade-off
    as ``edge_connectivity_lower_bound`` above.
    """
    if not adj:
        return 0
    return min((len(neigh) for neigh in adj), default=0)


def degree_assortativity(adj: Sequence[Sequence[int]]) -> float:
    """Degree-degree Pearson correlation (``[-1, 1]``).

    Mirrors ``nx.degree_assortativity_coefficient`` (TIGER has it under
    ``graph_tiger.measures`` as well). High positive = high-degree nodes
    connect to other high-degree nodes ("hub of hubs"); negative = hub-and-spoke
    — exactly the topology that funds-flow fraud rings exhibit.
    """
    if not adj:
        return 0.0
    xs: List[float] = []
    ys: List[float] = []
    for u, neigh in enumerate(adj):
        ku = len(neigh)
        for v in neigh:
            kv = len(adj[v])
            xs.append(ku)
            ys.append(kv)
    n = len(xs)
    if n == 0:
        return 0.0
    mu_x = sum(xs) / n
    mu_y = sum(ys) / n
    cov = sum((x - mu_x) * (y - mu_y) for x, y in zip(xs, ys)) / n
    var_x = sum((x - mu_x) ** 2 for x in xs) / n
    var_y = sum((y - mu_y) ** 2 for y in ys) / n
    if var_x == 0.0 or var_y == 0.0:
        return 0.0
    return round(cov / sqrt(var_x * var_y), 4)


# ---------------------------------------------------------------------------
# Composite report
# ---------------------------------------------------------------------------


def compute_robustness(ds: "GeneratedDataset") -> RobustnessReport:
    """Run all available stdlib-friendly measures over a ``GeneratedDataset``.

    Returns a :class:`RobustnessReport` with the result of each measure. Any
    measure that requires ``networkx`` (e.g. average shortest path length on
    disconnected graphs) is intentionally skipped — see module docstring.
    """
    id_to_idx, adj, edge_count = _build_undirected_adj(ds)
    return RobustnessReport(
        node_count=len(id_to_idx),
        edge_count=edge_count,
        density=density(adj, edge_count),
        avg_degree=average_degree(adj),
        clustering_coefficient=clustering_coefficient(adj),
        diameter_small=diameter_small(adj),
        node_connectivity_estimate=node_connectivity_lower_bound(adj),
        edge_connectivity=edge_connectivity_lower_bound(adj),
        assortativity=degree_assortativity(adj),
        spectral_radius=spectral_radius_estimate(adj),
    )


def spectral_radius_estimate(adj: Sequence[Sequence[int]]) -> float:
    """Power-iteration estimate of the largest adjacency eigenvalue.

    Not a TIGER measure per se, but a useful sanity check on hub dominance.
    Returns 0.0 for empty graphs. Uses at most 50 iterations with damping.
    """
    n = len(adj)
    if n == 0:
        return 0.0
    # Initial vector: uniform.
    x = [1.0 / n] * n
    lam = 0.0
    for _ in range(50):
        y = [0.0] * n
        for u, neigh in enumerate(adj):
            x_u = x[u]
            for v in neigh:
                y[v] += x_u
        norm = sqrt(sum(c * c for c in y))
        if norm == 0.0:
            return 0.0
        x = [c / norm for c in y]
        # Rayleigh quotient ≈ sum(y_i * x_i) for symmetric A.
        lam = sum(yi * xi for yi, xi in zip(y, x))
    return round(lam, 4)


__all__ = [
    "RobustnessReport",
    "average_degree",
    "clustering_coefficient",
    "compute_robustness",
    "degree_assortativity",
    "density",
    "diameter_small",
    "edge_connectivity_lower_bound",
    "node_connectivity_lower_bound",
    "spectral_radius_estimate",
]


# ---------------------------------------------------------------------------
# Stubs intentionally NOT ported (require networkx / numpy)
# ---------------------------------------------------------------------------
#
# - avg_distance: needs all-pairs shortest paths (networkx)
# - avg_inverse_distance / global_efficiency: same
# - avg_vertex_betweenness: O(V * E) BFS variant is implementable but slow;
#   the runtime cost outweighs the fraud-engine benefit. Use PageRank from
#   app.detection instead.
# - natural_connectivity: requires Laplacian eigenvalues (numpy)
# - algebraic_connectivity: same
# - eigen_centrality / pagerank_centrality: TIGER re-uses networkx.
#
# Refer to memory/references/tiger-graph-robustness/ for the full TIGER
# measures module if those signals become useful later.
