"""Pure-Python fallback for the three funds-flow detectors.

These mirror the GSQL implementations in :mod:`app.queries.funds_queries`
without the TigerGraph runtime — they walk
``ds.from_account`` / ``ds.to_account`` (the bipartite transaction
hyper-edge list) directly. They are the workhorse for:

- Unit tests (no TigerGraph, no docker)
- The "demo-without-graph" frontend mode
- The funds-monitor scheduler (see :mod:`app.scheduler.funds_monitor`)

Algorithmic notes:

- **Path trace** — bounded DFS / BFS over the funds-flow graph. Records each
  visited path with its summed amount and the chain of vertex ids.
- **Circular funds** — walks 3- / 4- / 5- / 6-cycles from every source
  account. Requires the source / last vertex to match and intermediate
  vertices to be distinct.
- **Burst amount** — per-source account average outgoing amount vs every
  edge; flags when ``r.amount > burst_factor × avg``.
"""

from __future__ import annotations

from collections import defaultdict

from ..loader.synth_generator import GeneratedDataset


# ---------------------------------------------------------------------------
# Adjacency helper — shared by all 3 detectors
# ---------------------------------------------------------------------------


def _tx_adjacency(ds: GeneratedDataset) -> tuple[
    dict[str, list[tuple[str, float, str]]], list[float]
]:
    """Build forward adjacency ``src -> [(tx_id, dst, amount, ts), ...]``.

    Returns (forward adjacency, all amounts). Source code in the repo pairs
    ``from_account`` / ``to_account`` by ``from_id == tx_id``; both halves
    always carry the same ``amount`` and ``ts`` on the matched row.
    """
    fwd: dict[str, list[tuple[str, float, str]]] = defaultdict(list)
    amts: list[float] = []
    pair: dict[str, dict[str, str]] = {}
    for fa in ds.from_account:
        m = pair.setdefault(fa["from_id"], {})
        m["src"] = fa["to_id"]
        m.setdefault("amount", str(fa.get("amount", 0.0)))
        m.setdefault("ts", str(fa.get("ts", "")))
    for ta in ds.to_account:
        m = pair.setdefault(ta["from_id"], {})
        m["dst"] = ta["to_id"]
        m.setdefault("amount", str(ta.get("amount", 0.0)))
        m.setdefault("ts", str(ta.get("ts", "")))
    for tx_id, m in pair.items():
        if "src" in m and "dst" in m and m["src"] != m["dst"]:
            try:
                amt = float(m["amount"])
            except (TypeError, ValueError):
                continue
            ts = m.get("ts", "")
            fwd[m["src"]].append((tx_id, m["dst"], amt, ts))
            amts.append(amt)
    return fwd, amts


# ---------------------------------------------------------------------------
# 1. Multi-hop funds path trace
# ---------------------------------------------------------------------------


def trace_funds_paths(
    ds: GeneratedDataset,
    *,
    start_id: str = "",
    start_ts: str = "",
    max_hops: int = 5,
    max_paths: int = 200,
) -> dict:
    """Trace all funds-flow paths from ``start_id`` within 1..max_hops.

    Returns a dict shaped to match the GSQL PRINT payload so the same
    factory on both backends works:
        {
            "results": [{
                "paths": [{"source": ..., "target": ..., "pathNodes": [...], "totalAmount": ...}],
                "path_count": int,
                "max_amount": float,
                "max_hops": int,
            }]
        }
    """
    fwd, _ = _tx_adjacency(ds)
    paths: list[dict] = []

    def _walk(src: str, target: str, hops: int, amount: float, trail: list[str]) -> None:
        if len(paths) >= max_paths:
            return
        if hops > 0:
            for tx_id, nxt, amt, ts in fwd.get(src, []):
                if ts and start_ts and ts < start_ts:
                    continue
                paths.append(
                    {
                        "source": target,  # original start
                        "target": nxt,
                        "pathNodes": trail + [nxt],
                        "totalAmount": amount + amt,
                        "edge_count": len(trail) - 1 + 1,
                    }
                )
                if hops > 1:
                    _walk(nxt, target, hops - 1, amount + amt, trail + [nxt])
        # base case is handled above when hops == max_hops initially

    if start_id:
        for tx_id, nxt, amt, ts in fwd.get(start_id, []):
            if ts and start_ts and ts < start_ts:
                continue
            paths.append(
                {
                    "source": start_id,
                    "target": nxt,
                    "pathNodes": [start_id, nxt],
                    "totalAmount": amt,
                    "edge_count": 1,
                }
            )
            _walk(nxt, start_id, max_hops - 1, amt, [start_id, nxt])

    max_amt = max((p["totalAmount"] for p in paths), default=0.0)
    return {
        "results": [
            {
                "paths": paths,
                "path_count": len(paths),
                "max_amount": max_amt,
                "max_hops": max_hops,
                "seed_id": start_id,
                "start_ts": start_ts,
            }
        ]
    }


# ---------------------------------------------------------------------------
# 2. Circular funds detection (3..6 hops)
# ---------------------------------------------------------------------------


def find_circular_funds(
    ds: GeneratedDataset,
    *,
    min_total: float = 50000.0,
    max_hops: int = 6,
    min_hops: int = 3,
) -> dict:
    """Account-centric 3..6 hop circular paths (laundering ring signature).

    Returns a dict shaped to match the GSQL PRINT payload.
        {
            "results": [{
                "totalAmount": float,
                "ringCount": int,
                "accountIds": [...],
                "byAccount": {account: {ring_len: int, totalAmount: float}},
            }]
        }
    """
    fwd, _ = _tx_adjacency(ds)
    rings_total: float = 0.0
    ring_count: int = 0
    involved: set[str] = set()
    by_account: dict[str, dict[str, float | int]] = defaultdict(
        lambda: {"ring_len_count": 0, "totalAmount": 0.0}
    )

    # n-hop cycles: walk src -> ... -> back to src with n steps (n edges, n-1 distinct
    # intermediate accounts). We allow 3..max_hops cycles.
    def _n_cycles(n: int) -> list[list[str]]:
        out: list[list[str]] = []
        for src in list(fwd.keys())[:1000]:  # safety cap for large graphs
            # DFS up to depth n; we only commit cycles that close
            def _dfs(path: list[str], path_amount: float, depth: int) -> None:
                if len(out) >= 200:
                    return
                if depth == n:
                    # check closure
                    return
                last = path[-1]
                for tx_id, nxt, amt, ts in fwd.get(last, []):
                    if depth + 1 == n and nxt != src:
                        continue
                    if depth + 1 < n and nxt in path:
                        continue
                    if nxt == src and depth + 1 == n and len(set(path)) >= min_hops:
                        out.append(path + [src])
                        return
                    if depth + 1 == n:
                        continue
                    _dfs(path + [nxt], path_amount + amt, depth + 1)

            _dfs([src], 0.0, 0)
        return out

    for n in range(min_hops, max_hops + 1):
        cycles = _n_cycles(n)
        for cyc in cycles:
            # Sum amount along the cycle edges
            total = 0.0
            for i in range(len(cyc) - 1):
                src = cyc[i]
                dst = cyc[i + 1]
                # pick first edge between src and dst
                for tx_id, nxt, amt, ts in fwd.get(src, []):
                    if nxt == dst:
                        total += amt
                        break
            if total >= min_total:
                ring_count += 1
                rings_total += total
                for a in cyc:
                    involved.add(a)
                by_account[cyc[0]]["ring_len_count"] = int(by_account[cyc[0]]["ring_len_count"]) + 1
                by_account[cyc[0]]["totalAmount"] = float(by_account[cyc[0]]["totalAmount"]) + total

    return {
        "results": [
            {
                "totalAmount": rings_total,
                "ringCount": ring_count,
                "accountIds": sorted(involved),
                "byAccount": {k: dict(v) for k, v in by_account.items()},
                "min_total": min_total,
                "max_hops": max_hops,
                "min_hops": min_hops,
            }
        ]
    }


# ---------------------------------------------------------------------------
# 3. Burst amount detection (5x historical average)
# ---------------------------------------------------------------------------


def find_burst_amount(
    ds: GeneratedDataset,
    *,
    burst_factor: float = 5.0,
    start_ts: str = "",
) -> dict:
    """Flag every edge whose amount > burst_factor × avg-of-same-source.

    Returns a dict shaped to match the GSQL PRINT payload, plus a flat
    ``suspicious`` list with per-edge evidence.
    """
    pair: dict[str, dict[str, str]] = {}
    for fa in ds.from_account:
        m = pair.setdefault(fa["from_id"], {})
        m["src"] = fa["to_id"]
        m.setdefault("amount", str(fa.get("amount", 0.0)))
        m.setdefault("ts", str(fa.get("ts", "")))
    for ta in ds.to_account:
        m = pair.setdefault(ta["from_id"], {})
        m["dst"] = ta["to_id"]
        m.setdefault("amount", str(ta.get("amount", 0.0)))
        m.setdefault("ts", str(ta.get("ts", "")))

    by_src: dict[str, list[float]] = defaultdict(list)
    edges: list[dict] = []
    for tx_id, m in pair.items():
        if "src" not in m or "dst" not in m or m["src"] == m["dst"]:
            continue
        try:
            amt = float(m["amount"])
        except (TypeError, ValueError):
            continue
        ts = m.get("ts", "")
        if start_ts and ts and ts < start_ts:
            continue
        by_src[m["src"]].append(amt)
        edges.append({"tx_id": tx_id, "src": m["src"], "dst": m["dst"], "amount": amt, "ts": ts})

    suspicious: list[dict] = []
    for e in edges:
        samples = by_src.get(e["src"], [])
        if not samples:
            continue
        avg = sum(samples) / len(samples)
        if avg > 0 and e["amount"] > burst_factor * avg:
            suspicious.append(
                {
                    "suspiciousSource": e["src"],
                    "suspiciousTarget": e["dst"],
                    "transferAmount": e["amount"],
                    "historicalAverage": round(avg, 4),
                    "ratio": round(e["amount"] / avg, 4) if avg else 0.0,
                    "ts": e["ts"],
                    "tx_id": e["tx_id"],
                }
            )

    suspicious.sort(key=lambda r: r["ratio"], reverse=True)
    return {
        "results": [
            {
                "suspicious": suspicious[:200],
                "flagged_count": len(suspicious),
                "burst_factor": burst_factor,
                "start_ts": start_ts,
            }
        ]
    }
