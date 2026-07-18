"""Profile sub-system — multi-hop BFS graph traversals.

Exports:
- :func:`bfs_identity` — account identity graph (devices / IPs / shared accounts)
- :func:`bfs_funds` — funds-flow graph (money trail through transactions)
- :class:`GraphSubgraph` — serialisable result container
"""

from .graph_search import GraphSubgraph, bfs_identity, bfs_funds

__all__ = ["GraphSubgraph", "bfs_identity", "bfs_funds"]
