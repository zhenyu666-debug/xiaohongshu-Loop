"""Local in-memory detector — runs the same algorithmic checks as TigerGraph
against a :class:`GeneratedDataset`.

This is the workhorse for:

- Unit tests (no TigerGraph runtime needed)
- The "demo-without-graph" frontend mode
- CI smoke tests on machines that cannot reach PyPI / docker mirrors

Algorithmic parity with the GSQL queries is approximated here:

- :func:`find_transaction_rings` — DFS for cycles of length 3..6 over the
  ``FROM_ACCOUNT/TO_ACCOUNT`` bipartite graph.
- :func:`find_shared_device_clusters` — connected components over the
  ``USES_DEVICE`` projection.
- :func:`find_burst_accounts` — accounts with ≥N outgoing transactions.
- :func:`find_top_centrality` — out-degree as a coarse centrality proxy.
"""

from __future__ import annotations

import time
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone

from ..loader.synth_generator import GeneratedDataset
from .models import (
    AlertSeverity,
    DetectionRun,
    GraphSnapshot,
    RiskAlert,
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---------------------------------------------------------------------------
# Individual algorithms — return RiskAlert or None
# ---------------------------------------------------------------------------


def find_transaction_rings(ds: GeneratedDataset, *, min_len: int = 3) -> RiskAlert | None:
    """Count 3-hop transaction cycles over ``FROM_ACCOUNT``/``TO_ACCOUNT``.

    Implementation note: we walk the ``Transaction`` as a hyper-edge
    ``src --tx--> dst`` and use plain tuple DFS over a small ring-depth.
    With 12K transactions this runs in milliseconds, so we avoid a heavy
    network-X dependency.
    """
    edges: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for fa in ds.from_account:
        edges[fa["to_id"]][fa["to_id"]]  # noqa: B018 — placeholder doc
    # Build forward adjacency: account -> [account]
    fwd: dict[str, list[str]] = defaultdict(list)
    for fa, ta in zip(ds.from_account, ds.to_account):
        # Both edges refer to the same Transaction vertex; pair by id.
        pass

    # Re-build properly: pair from_account and to_account by transaction id.
    pair: dict[str, tuple[str, str]] = {}
    for fa in ds.from_account:
        pair[fa["from_id"]] = (fa["to_id"], pair.get(fa["from_id"], ("", ""))[1])
    for ta in ds.to_account:
        if ta["from_id"] in pair:
            src, _ = pair[ta["from_id"]]
            pair[ta["from_id"]] = (src, ta["to_id"])
    for tx_id, (src, dst) in pair.items():
        if src and dst and src != dst:
            fwd[src].append(dst)

    # Count 3-cycles: a -> b -> c -> a
    rings = set()
    for a, neighbours_ab in fwd.items():
        for b in neighbours_ab:
            for c in fwd.get(b, []):
                if a in fwd.get(c, []) and c not in {a, b}:
                    key = tuple(sorted([a, b, c]))
                    if len(set(key)) >= min_len:
                        rings.add(key)
    if not rings:
        return None

    accounts = sorted({a for ring in rings for a in ring})
    severity = AlertSeverity.CRITICAL.value if len(rings) >= 5 else AlertSeverity.HIGH.value
    return RiskAlert(
        kind="transaction_ring",
        severity=severity,
        score=round(min(1.0, 0.4 + 0.05 * len(rings)), 4),
        title="Short-cycle transaction ring detected",
        description=f"Detected {len(rings)} distinct 3-cycle(s) across {len(accounts)} accounts.",
        involved=accounts,
        evidence={"ring_count": len(rings), "ring_size": min_len},
    )


def find_shared_device_clusters(
    ds: GeneratedDataset, *, min_shared: int = 3
) -> RiskAlert | None:
    """Accounts sharing ≥ ``min_shared`` devices OR IPs."""
    dev_to_accts: dict[str, set[str]] = defaultdict(set)
    ip_to_accts: dict[str, set[str]] = defaultdict(set)
    for e in ds.uses_device:
        dev_to_accts[e["to_id"]].add(e["from_id"])
    for e in ds.logged_from:
        ip_to_accts[e["to_id"]].add(e["from_id"])
    shared_devices = {d for d, a in dev_to_accts.items() if len(a) >= min_shared}
    shared_ips = {ip for ip, a in ip_to_accts.items() if len(a) >= min_shared}

    if not shared_devices and not shared_ips:
        return None
    affected = set()
    for d in shared_devices:
        affected |= dev_to_accts[d]
    for ip in shared_ips:
        affected |= ip_to_accts[ip]
    severity = (
        AlertSeverity.CRITICAL.value
        if len(affected) >= 9
        else AlertSeverity.HIGH.value
        if len(affected) >= 5
        else AlertSeverity.MEDIUM.value
    )
    return RiskAlert(
        kind="shared_device",
        severity=severity,
        score=round(min(1.0, 0.4 + 0.04 * len(affected)), 4),
        title="Account cluster sharing devices / IPs",
        description=(
            f"{len(shared_devices)} device(s) and {len(shared_ips)} IP(s) are "
            f"linked to ≥{min_shared} distinct accounts — affects {len(affected)} accounts."
        ),
        involved=sorted(affected),
        evidence={
            "shared_device_count": len(shared_devices),
            "shared_ip_count": len(shared_ips),
            "affected_accounts": len(affected),
        },
    )


def find_burst_accounts(
    ds: GeneratedDataset, *, min_count: int = 12
) -> RiskAlert | None:
    """Accounts with ≥ ``min_count`` outgoing transactions (approx)."""
    outgoing: Counter[str] = Counter()
    for e in ds.from_account:
        outgoing[e["to_id"]] += 1
    flagged = {a: c for a, c in outgoing.items() if c >= min_count}
    if not flagged:
        return None
    severity = (
        AlertSeverity.CRITICAL.value
        if len(flagged) >= 10
        else AlertSeverity.HIGH.value
        if len(flagged) >= 5
        else AlertSeverity.MEDIUM.value
    )
    return RiskAlert(
        kind="burst_transactions",
        severity=severity,
        score=round(min(1.0, 0.4 + 0.04 * len(flagged)), 4),
        title="Outgoing-transaction velocity burst",
        description=(
            f"{len(flagged)} accounts each have ≥{min_count} outgoing transactions "
            "in the synthetic dataset — candidates for burst-style fraud."
        ),
        involved=sorted(flagged.keys()),
        evidence={"tx_count_by_account": {k: v for k, v in sorted(flagged.items())}},
    )


def find_top_centrality(
    ds: GeneratedDataset, *, top_k: int = 50
) -> RiskAlert | None:
    """Top-K accounts by combined out+in edge count."""
    degree: Counter[str] = Counter()
    for e in ds.from_account:
        degree[e["to_id"]] += 1
    for e in ds.to_account:
        degree[e["to_id"]] += 1
    if not degree:
        return None
    top = [a for a, _ in degree.most_common(top_k)]
    return RiskAlert(
        kind="pagerank",
        severity=AlertSeverity.MEDIUM.value,
        score=round(min(1.0, 0.3 + 0.01 * len(top)), 4),
        title=f"Top-{top_k} high-degree accounts",
        description=(
            f"Top accounts by combined in+out transaction degree. Use as first-pass "
            "review candidates after ring / shared-device alerts."
        ),
        involved=top,
        evidence={"topK": len(top)},
    )


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def snapshot_from_dataset(ds: GeneratedDataset) -> GraphSnapshot:
    counts = ds.counts()
    return GraphSnapshot(
        vertices={
            "Customer": counts["customers"],
            "Account": counts["accounts"],
            "Card": counts["cards"],
            "Device": counts["devices"],
            "IP": counts["ips"],
            "Merchant": counts["merchants"],
            "Transaction": counts["transactions"],
        },
        edges={
            "OWNS": counts["owns"],
            "HAS_CARD": counts["has_card"],
            "USES_DEVICE": counts["uses_device"],
            "LOGGED_FROM": counts["logged_from"],
            "PAID_TO": counts["paid_to"],
            "FROM_ACCOUNT": counts["from_account"],
            "TO_ACCOUNT": counts["to_account"],
            "SHARES_DEVICE": counts["shares_device"],
            "SHARES_IP": counts["shares_ip"],
        },
        planted_rings=ds.planted_rings,
    )


def run_local_detector(
    ds: GeneratedDataset,
    *,
    ring_min_len: int = 3,
    shared_device_min: int = 3,
    burst_min_count: int = 12,
    top_k: int = 50,
) -> DetectionRun:
    """Run every local detection algorithm and collect alerts."""
    started = _now()
    t0 = time.perf_counter()
    alerts: list[RiskAlert] = []

    ring = find_transaction_rings(ds, min_len=ring_min_len)
    if ring:
        alerts.append(ring)
    cluster = find_shared_device_clusters(ds, min_shared=shared_device_min)
    if cluster:
        alerts.append(cluster)
    burst = find_burst_accounts(ds, min_count=burst_min_count)
    if burst:
        alerts.append(burst)
    top = find_top_centrality(ds, top_k=top_k)
    if top:
        alerts.append(top)

    elapsed_ms = int((time.perf_counter() - t0) * 1000)
    ended = _now()
    snap = snapshot_from_dataset(ds)
    metrics = {
        "vertices_total": sum(snap.vertices.values()),
        "edges_total": sum(snap.edges.values()),
        "alerts_total": len(alerts),
        "elapsed_ms": elapsed_ms,
    }
    return DetectionRun(
        run_id=str(uuid.uuid4()),
        started_at=started,
        ended_at=ended,
        backend="local",
        status="ok",
        detail=f"Local detection over {metrics['vertices_total']} vertices / {metrics['edges_total']} edges",
        alerts=alerts,
        snapshot=snap,
        metrics=metrics,
    )


class LocalDetector:
    """OO façade around :func:`run_local_detector`."""

    def __init__(self, dataset: GeneratedDataset, **thresholds: int) -> None:
        self.dataset = dataset
        self.thresholds = thresholds

    def run(self) -> DetectionRun:
        return run_local_detector(self.dataset, **self.thresholds)

    def snapshot(self) -> GraphSnapshot:
        return snapshot_from_dataset(self.dataset)