"""Multi-hop BFS graph traversals over a :class:`GeneratedDataset`.

Provides two search modes:

**Identity graph** (``bfs_identity``)
    Walks the identity layer: Account → USES_DEVICE → Device → USES_DEVICE →
    Account → LOGGED_FROM → IP → LOGGED_FROM → Account.
    Use this to find accounts that share devices or IPs with the seed account —
    the classic "same person" signal.

**Funds-flow graph** (``bfs_funds``)
    Follows the transaction graph: Account → FROM_ACCOUNT → Transaction →
    TO_ACCOUNT → Account (outgoing), and the reverse direction (incoming).
    Use this to trace money movement through the fraud network.

Both traversals are breadth-first, bounded by ``max_hops`` and ``max_nodes``.
They return a :class:`GraphSubgraph` that can be serialised to JSON for the API
or to SVG for the frontend.
"""

from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Any, Literal

if TYPE_CHECKING:
    from ..loader.synth_generator import GeneratedDataset


# ---------------------------------------------------------------------------
# Result container
# ---------------------------------------------------------------------------


@dataclass
class GraphNode:
    """A single node in the result subgraph."""

    id: str
    kind: Literal[
        "account", "device", "ip", "transaction", "merchant", "customer"
    ]
    hop: int
    parent_id: str | None
    properties: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GraphEdge:
    """A single edge in the result subgraph."""

    src: str
    dst: str
    label: str  # e.g. "USES_DEVICE", "FROM_ACCOUNT"
    amount: float | None = None  # only for transaction edges
    hop: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class GraphSubgraph:
    """Result of a multi-hop BFS traversal."""

    root_id: str
    mode: str  # "identity" or "funds"
    nodes: list[GraphNode] = field(default_factory=list)
    edges: list[GraphEdge] = field(default_factory=list)
    stats: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_id": self.root_id,
            "mode": self.mode,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "stats": self.stats,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_uses_device_map(ds: "GeneratedDataset") -> dict[str, list[str]]:
    acc_to_devs: dict[str, list[str]] = {}
    for e in ds.uses_device:
        acc_to_devs.setdefault(e["from_id"], []).append(e["to_id"])
    return acc_to_devs


def _build_device_to_accounts_map(ds: "GeneratedDataset") -> dict[str, list[str]]:
    dev_to_accs: dict[str, list[str]] = {}
    for e in ds.uses_device:
        dev_to_accs.setdefault(e["to_id"], []).append(e["from_id"])
    return dev_to_accs


def _build_logged_from_map(ds: "GeneratedDataset") -> dict[str, list[str]]:
    acc_to_ips: dict[str, list[str]] = {}
    for e in ds.logged_from:
        acc_to_ips.setdefault(e["from_id"], []).append(e["to_id"])
    return acc_to_ips


def _build_ip_to_accounts_map(ds: "GeneratedDataset") -> dict[str, list[str]]:
    ip_to_accs: dict[str, list[str]] = {}
    for e in ds.logged_from:
        ip_to_accs.setdefault(e["to_id"], []).append(e["from_id"])
    return ip_to_accs


def _build_transaction_pairs(
    ds: "GeneratedDataset",
) -> tuple[
    dict[str, list[tuple[str, str, float]]],
    dict[str, list[tuple[str, str, float]]],
]:
    """Return (from_acc_outgoing, to_acc_incoming) where the tuple is
    (tx_id, counterpart_id, amount)."""
    tx_from: dict[str, list[tuple[str, str, float]]] = {}
    tx_to: dict[str, list[tuple[str, str, float]]] = {}
    for fa in ds.from_account:
        tx_from.setdefault(fa["to_id"], []).append(
            (fa["from_id"], fa.get("to_id", ""), fa.get("amount", 0.0))
        )
    for ta in ds.to_account:
        tx_to.setdefault(ta["to_id"], []).append(
            (ta["from_id"], ta.get("to_id", ""), ta.get("amount", 0.0))
        )
    return tx_from, tx_to


def _build_paid_to_map(
    ds: "GeneratedDataset",
) -> dict[str, list[tuple[str, float]]]:
    acc_to_merch: dict[str, list[tuple[str, float]]] = {}
    for e in ds.paid_to:
        acc_to_merch.setdefault(e["from_id"], []).append(
            (e["to_id"], e.get("amount", 0.0))
        )
    return acc_to_merch


def _node_properties(
    ds: "GeneratedDataset", node_id: str
) -> dict[str, Any]:
    """Return a minimal properties dict for the given node id."""
    for acc in ds.accounts:
        if acc["id"] == node_id:
            return {"type": acc.get("account_type", ""), "status": acc.get("status", "")}
    for dev in ds.devices:
        if dev["id"] == node_id:
            return {
                "device_type": dev.get("device_type", ""),
                "os": dev.get("os", ""),
            }
    for ip in ds.ips:
        if ip["id"] == node_id:
            return {"country": ip.get("country", ""), "city": ip.get("city", "")}
    for tx in ds.transactions:
        if tx["id"] == node_id:
            return {
                "amount": tx.get("amount", 0.0),
                "currency": tx.get("currency", ""),
                "channel": tx.get("channel", ""),
                "status": tx.get("status", ""),
            }
    for m in ds.merchants:
        if m["id"] == node_id:
            return {"name": m.get("name", ""), "mcc": m.get("mcc", "")}
    return {}


def _node_kind(node_id: str) -> str:
    if node_id.startswith("A"):
        return "account"
    if node_id.startswith("D"):
        return "device"
    if node_id.startswith("IP") and "SHARED" not in node_id:
        return "ip"
    if node_id.startswith("T"):
        return "transaction"
    if node_id.startswith("M"):
        return "merchant"
    if node_id.startswith("C"):
        return "customer"
    return "unknown"


def _qualify_id(ds: "GeneratedDataset", node_id: str) -> str:
    """Return the normalised id from the dataset, or node_id unchanged."""
    for acc in ds.accounts:
        if acc["id"] == node_id:
            return node_id
    return node_id


# ---------------------------------------------------------------------------
# Identity BFS
# ---------------------------------------------------------------------------


def bfs_identity(
    account_id: str,
    ds: "GeneratedDataset",
    *,
    max_hops: int = 3,
    max_nodes: int = 500,
) -> GraphSubgraph:
    """Walk the identity graph starting from ``account_id``.

    Traverses: Account → USES_DEVICE → Device → USES_DEVICE → Account →
    LOGGED_FROM → IP → LOGGED_FROM → Account.

    Returns accounts that share devices or IPs with the seed account, up to
    ``max_hops`` hops away. The result includes all visited accounts, devices,
    and IPs along with the connecting edges.

    Parameters
    ----------
    account_id:
        Seed account (format ``A{digits}``).
    ds:
        The loaded dataset.
    max_hops:
        Maximum BFS depth (default 3). Each identity step counts as one hop.
    max_nodes:
        Hard cap on total nodes to avoid runaway traversal on dense graphs.

    Returns
    -------
    GraphSubgraph
        ``mode="identity"``. ``stats`` includes:

        - ``total_nodes`` — count of nodes in subgraph
        - ``total_edges`` — count of edges
        - ``accounts_found`` — number of distinct accounts (including root)
        - ``devices_found`` — number of distinct devices
        - ``ips_found`` — number of distinct IPs
        - ``cumulative_amount`` — not applicable for identity mode (0.0)
        - ``top_counterparties`` — accounts sorted by shared-device/IP count
    """
    acc_to_devs = _build_uses_device_map(ds)
    dev_to_accs = _build_device_to_accounts_map(ds)
    acc_to_ips = _build_logged_from_map(ds)
    ip_to_accs = _build_ip_to_accounts_map(ds)

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    seen_accounts: dict[str, bool] = {}
    seen_devices: dict[str, bool] = {}
    seen_ips: dict[str, bool] = {}
    device_shared_by: dict[str, int] = {}
    ip_shared_by: dict[str, int] = {}

    # BFS queue: (current_id, kind, hop, parent_id, edge_label, properties_hint)
    queue: deque[tuple[str, str, int, str | None, str | None, dict[str, Any]]] = deque()
    queue.append(
        (
            account_id,
            "account",
            0,
            None,
            None,
            _node_properties(ds, account_id),
        )
    )
    seen_accounts[account_id] = True

    while queue and (len(nodes) < max_nodes):
        current_id, kind, hop, parent_id, edge_label, props = queue.popleft()

        nodes.append(
            GraphNode(
                id=current_id,
                kind=kind,  # type: ignore[arg-type]
                hop=hop,
                parent_id=parent_id,
                properties=props,
            )
        )

        if hop >= max_hops:
            continue

        # Account -> Device
        if kind == "account" and current_id in acc_to_devs:
            for dev_id in acc_to_devs[current_id]:
                if dev_id not in seen_devices:
                    seen_devices[dev_id] = True
                    device_shared_by[dev_id] = device_shared_by.get(dev_id, 0)
                    queue.append(
                        (
                            dev_id,
                            "device",
                            hop + 1,
                            current_id,
                            "USES_DEVICE",
                            _node_properties(ds, dev_id),
                        )
                    )
                    edges.append(
                        GraphEdge(
                            src=current_id,
                            dst=dev_id,
                            label="USES_DEVICE",
                            hop=hop,
                        )
                    )

        # Device -> Account
        elif kind == "device" and current_id in dev_to_accs:
            for acc_id in dev_to_accs[current_id]:
                if acc_id not in seen_accounts:
                    seen_accounts[acc_id] = True
                    device_shared_by[current_id] = device_shared_by.get(current_id, 0) + 1
                    queue.append(
                        (
                            acc_id,
                            "account",
                            hop + 1,
                            current_id,
                            "USES_DEVICE",
                            _node_properties(ds, acc_id),
                        )
                    )
                    edges.append(
                        GraphEdge(
                            src=current_id,
                            dst=acc_id,
                            label="USES_DEVICE",
                            hop=hop,
                        )
                    )

        # Account -> IP
        elif kind == "account" and current_id in acc_to_ips:
            for ip_id in acc_to_ips[current_id]:
                if ip_id not in seen_ips:
                    seen_ips[ip_id] = True
                    ip_shared_by[ip_id] = ip_shared_by.get(ip_id, 0)
                    queue.append(
                        (
                            ip_id,
                            "ip",
                            hop + 1,
                            current_id,
                            "LOGGED_FROM",
                            _node_properties(ds, ip_id),
                        )
                    )
                    edges.append(
                        GraphEdge(
                            src=current_id,
                            dst=ip_id,
                            label="LOGGED_FROM",
                            hop=hop,
                        )
                    )

        # IP -> Account
        elif kind == "ip" and current_id in ip_to_accs:
            for acc_id in ip_to_accs[current_id]:
                if acc_id not in seen_accounts:
                    seen_accounts[acc_id] = True
                    ip_shared_by[current_id] = ip_shared_by.get(current_id, 0) + 1
                    queue.append(
                        (
                            acc_id,
                            "account",
                            hop + 1,
                            current_id,
                            "LOGGED_FROM",
                            _node_properties(ds, acc_id),
                        )
                    )
                    edges.append(
                        GraphEdge(
                            src=current_id,
                            dst=acc_id,
                            label="LOGGED_FROM",
                            hop=hop,
                        )
                    )

    # Stats
    top_counterparties = sorted(
        seen_accounts.keys(),
        key=lambda a: (
            device_shared_by.get(a, 0)
            + sum(ip_shared_by.get(ip, 0) for ip in acc_to_ips.get(a, []))
        ),
        reverse=True,
    )[:10]

    stats = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "accounts_found": len(seen_accounts),
        "devices_found": len(seen_devices),
        "ips_found": len(seen_ips),
        "cumulative_amount": 0.0,
        "top_counterparties": top_counterparties,
    }

    return GraphSubgraph(
        root_id=account_id,
        mode="identity",
        nodes=nodes,
        edges=edges,
        stats=stats,
    )


# ---------------------------------------------------------------------------
# Funds-flow BFS
# ---------------------------------------------------------------------------


def bfs_funds(
    account_id: str,
    ds: "GeneratedDataset",
    *,
    max_hops: int = 4,
    max_nodes: int = 500,
    direction: Literal["out", "in", "both"] = "both",
    include_merchants: bool = False,
) -> GraphSubgraph:
    """Walk the funds-flow graph starting from ``account_id``.

    Traverses: Account → FROM_ACCOUNT → Transaction → TO_ACCOUNT → Account.

    Follows the money trail — outgoing (``out``), incoming (``in``), or both
    (``both``). Transactions are included as intermediate nodes so the dollar
    amounts are visible on the edges. Optionally extends through ``PAID_TO``
    to include merchants.

    Parameters
    ----------
    account_id:
        Seed account (format ``A{digits}``).
    ds:
        The loaded dataset.
    max_hops:
        Maximum BFS depth (default 4). Each hop traverses one FROM_ACCOUNT or
        TO_ACCOUNT edge; a full Account→Transaction→Account round-trip costs
        two hops.
    max_nodes:
        Hard cap on total nodes.
    direction:
        ``out`` = only senders (money leaving the seed account),
        ``in`` = only receivers (money arriving), ``both`` = both.
    include_merchants:
        If True, follow PAID_TO edges from transactions to merchants.
        Merchants are added as terminal nodes; no further traversal from them.

    Returns
    -------
    GraphSubgraph
        ``mode="funds"``. ``stats`` includes:

        - ``total_nodes``, ``total_edges``, ``accounts_found``,
          ``devices_found``, ``ips_found``, ``transactions_found``,
          ``merchants_found``
        - ``cumulative_amount`` — sum of all transaction amounts in the subgraph
        - ``top_counterparties`` — accounts sorted by cumulative amount
    """
    tx_from, tx_to = _build_transaction_pairs(ds)
    paid_to_map = _build_paid_to_map(ds)

    nodes: list[GraphNode] = []
    edges: list[GraphEdge] = []
    seen_accounts: dict[str, bool] = {}
    seen_transactions: dict[str, bool] = {}
    seen_merchants: dict[str, bool] = {}
    cumulative_amount = 0.0
    acc_totals: dict[str, float] = {}

    # BFS queue: (current_id, kind, hop, parent_id, edge_label, amount, tx_src_id)
    # tx_src_id is used to avoid showing duplicate tx→acc edges when both
    # from_account and to_account of the same tx are traversed.
    queue: deque[
        tuple[str, str, int, str | None, str | None, float | None, str | None]
    ] = deque()
    queue.append(
        (account_id, "account", 0, None, None, None, None)
    )
    seen_accounts[account_id] = True
    acc_totals[account_id] = 0.0

    while queue and (len(nodes) < max_nodes):
        current_id, kind, hop, parent_id, edge_label, amount, tx_src_id = (
            queue.popleft()
        )

        props = _node_properties(ds, current_id) if kind == "transaction" else {}
        nodes.append(
            GraphNode(
                id=current_id,
                kind=kind,  # type: ignore[arg-type]
                hop=hop,
                parent_id=parent_id,
                properties=props,
            )
        )

        if hop >= max_hops:
            continue

        # Account -> Transaction (outgoing)
        if kind == "account" and current_id in tx_from and direction in ("out", "both"):
            for src, dst, amt in tx_from[current_id]:
                if src not in seen_transactions:
                    seen_transactions[src] = True
                    cumulative_amount += amt
                    queue.append(
                        (src, "transaction", hop + 1, current_id, "FROM_ACCOUNT", amt, src)
                    )
                    edges.append(
                        GraphEdge(
                            src=current_id,
                            dst=src,
                            label="FROM_ACCOUNT",
                            amount=amt,
                            hop=hop,
                        )
                    )

        # Account -> Transaction (incoming)
        if kind == "account" and current_id in tx_to and direction in ("in", "both"):
            for src, dst, amt in tx_to[current_id]:
                if src not in seen_transactions:
                    seen_transactions[src] = True
                    cumulative_amount += amt
                    queue.append(
                        (src, "transaction", hop + 1, current_id, "TO_ACCOUNT", amt, src)
                    )
                    edges.append(
                        GraphEdge(
                            src=src,
                            dst=current_id,
                            label="TO_ACCOUNT",
                            amount=amt,
                            hop=hop,
                        )
                    )

        # Transaction -> Account
        elif kind == "transaction":
            # Outgoing: the tx source account
            if tx_src_id in tx_from:
                for src2, dst2, amt2 in tx_from[tx_src_id]:
                    if src2 not in seen_accounts:
                        seen_accounts[src2] = True
                        acc_totals[src2] = acc_totals.get(src2, 0.0)
                        queue.append(
                            (src2, "account", hop + 1, current_id, "FROM_ACCOUNT", None, None)
                        )
                        edges.append(
                            GraphEdge(
                                src=current_id,
                                dst=src2,
                                label="FROM_ACCOUNT",
                                amount=amt2,
                                hop=hop,
                            )
                        )
            # Incoming: the tx destination account
            if tx_src_id in tx_to:
                for src2, dst2, amt2 in tx_to[tx_src_id]:
                    if dst2 not in seen_accounts:
                        seen_accounts[dst2] = True
                        acc_totals[dst2] = acc_totals.get(dst2, 0.0) + amt2
                        queue.append(
                            (dst2, "account", hop + 1, current_id, "TO_ACCOUNT", amt2, None)
                        )
                        edges.append(
                            GraphEdge(
                                src=current_id,
                                dst=dst2,
                                label="TO_ACCOUNT",
                                amount=amt2,
                                hop=hop,
                            )
                        )

            # Optionally extend to merchants
            if include_merchants and tx_src_id in paid_to_map:
                for merch_id, merch_amt in paid_to_map[tx_src_id]:
                    if merch_id not in seen_merchants:
                        seen_merchants[merch_id] = True
                        queue.append(
                            (
                                merch_id,
                                "merchant",
                                hop + 1,
                                current_id,
                                "PAID_TO",
                                merch_amt,
                                None,
                            )
                        )
                        edges.append(
                            GraphEdge(
                                src=current_id,
                                dst=merch_id,
                                label="PAID_TO",
                                amount=merch_amt,
                                hop=hop,
                            )
                        )

    top_counterparties = sorted(
        acc_totals.keys(), key=lambda a: acc_totals.get(a, 0.0), reverse=True
    )[:10]

    stats = {
        "total_nodes": len(nodes),
        "total_edges": len(edges),
        "accounts_found": len(seen_accounts),
        "devices_found": 0,
        "ips_found": 0,
        "transactions_found": len(seen_transactions),
        "merchants_found": len(seen_merchants),
        "cumulative_amount": round(cumulative_amount, 2),
        "top_counterparties": top_counterparties,
    }

    return GraphSubgraph(
        root_id=account_id,
        mode="funds",
        nodes=nodes,
        edges=edges,
        stats=stats,
    )
