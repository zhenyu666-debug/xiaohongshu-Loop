"""PaySim-statistically-faithful data generator (no external dependencies).

Replicates the statistical fingerprints of the Kaggle PaySim dataset
(https://www.kaggle.com/datasets/varshithkumaranand/banking-fruad-detection-dataset-with-99-accuracy)
so the Graph Studio demo shows real-world-looking fraud patterns without needing
a CSV download.

Key PaySim statistics reproduced
--------------------------------
- 6 transaction types: CASH_IN / CASH_OUT / DEBIT / PAYMENT / TRANSFER
  Distribution (approximate): CASH_OUT 35%, PAYMENT 34%, CASH_IN 22%,
                              TRANSFER 8%, DEBIT <1%
- Amount: heavy-tailed (power-law, median ~75k, max ~10M)
- Fraud rate: 0.13% of all transactions (8,213 / 6.36M)
- Fraud ONLY in: TRANSFER and CASH_OUT (zero fraud in PAYMENT/CASH_IN/DEBIT)
- Fraud flag (isFlaggedFraud): rare, only for amounts > 200k in TRANSFER

API
---
gen_paysim_sample(n=500) -> PaySimSample
    Returns dict with nodes/edges/trends/paymentTypeBreakdown/fraudStats.
    Compatible with the Graph Studio ExploreGraph renderer.

CLI
---
    python -m app.loader.paysim_data          # print summary
    python -m app.loader.paysim_data --n 200 # custom size
"""

from __future__ import annotations

import random
import sys
import math
from dataclasses import dataclass, field
from typing import Callable


# ---------------------------------------------------------------------------
# Global PaySim statistics (from the dataset analysis papers)
# ---------------------------------------------------------------------------

# Transaction type distribution — (type, fraction)
_TYPE_DISTRIBUTION: list[tuple[str, float]] = [
    ("CASH_OUT", 0.352),
    ("PAYMENT",  0.338),
    ("CASH_IN",  0.220),
    ("TRANSFER", 0.084),
    ("DEBIT",    0.006),
]

# Fraud rate by type — fraction of rows that are fraud for each type
_FRAUD_RATE_BY_TYPE: dict[str, float] = {
    "TRANSFER": 0.0056,   # 0.56% of all TRANSFER are fraud
    "CASH_OUT": 0.0020,   # 0.20% of all CASH_OUT are fraud
    "PAYMENT":  0.0,
    "CASH_IN":   0.0,
    "DEBIT":     0.0,
}

# isFlaggedFraud: only when type==TRANSFER and amount > 200_000
_FLAG_THRESHOLD = 200_000.0

# Power-law parameters for amount (fitted to PaySim)
_AMOUNT_ALPHA = 1.16   # Pareto tail index
_AMOUNT_SCALE = 75_000.0
_AMOUNT_MIN   = 0.01
_AMOUNT_MAX   = 10_000_000.0


def _sample_amount(rng: random.Random) -> float:
    """Sample from a truncated Pareto (power-law) distribution."""
    raw = rng.paretovariate(_AMOUNT_ALPHA) * _AMOUNT_SCALE
    return round(min(max(raw, _AMOUNT_MIN), _AMOUNT_MAX), 2)


def _pick_type(rng: random.Random) -> str:
    r = rng.random()
    cumulative = 0.0
    for typ, frac in _TYPE_DISTRIBUTION:
        cumulative += frac
        if r < cumulative:
            return typ
    return "TRANSFER"


@dataclass
class PaySimTransaction:
    id: str
    step: int
    type: str
    amount: float
    name_orig: str
    oldbalance_org: float
    newbalance_org: float
    name_dest: str
    oldbalance_dest: float
    newbalance_dest: float
    is_fraud: int
    is_flagged_fraud: int


@dataclass
class PaySimGraphNode:
    id: str
    label: str
    node_type: str   # "customer" | "transaction"
    # For customers
    balance: float | None = None
    # For transactions
    amount: float | None = None
    tx_type: str | None = None
    is_fraud: bool = False
    step: int | None = None


@dataclass
class PaySimGraphEdge:
    source: str
    target: str
    edge_type: str   # "FROM" | "TO" | "FLAGGED"
    amount: float | None = None


@dataclass
class PaySimSample:
    """All graph data for the PaySim demo."""
    transactions: list[PaySimTransaction] = field(default_factory=list)

    # Nodes for graph view
    nodes: list[PaySimGraphNode] = field(default_factory=list)
    # Edges for graph view
    edges: list[PaySimGraphEdge] = field(default_factory=list)

    # Stats for cards
    total_amount: float = 0.0
    fraud_amount: float = 0.0
    fraud_count: int = 0
    transaction_count: int = 0

    def summary(self) -> dict:
        type_counts: dict[str, int] = {}
        type_amounts: dict[str, float] = {}
        for t in self.transactions:
            type_counts[t.type] = type_counts.get(t.type, 0) + 1
            type_amounts[t.type] = type_amounts.get(t.type, 0.0) + t.amount

        fraud_by_type: dict[str, int] = {}
        for t in self.transactions:
            if t.is_fraud:
                fraud_by_type[t.type] = fraud_by_type.get(t.type, 0) + 1

        return {
            "transaction_count": self.transaction_count,
            "fraud_count": self.fraud_count,
            "fraud_rate": round(self.fraud_count / max(1, self.transaction_count) * 100, 3),
            "total_amount": self.total_amount,
            "fraud_amount": self.fraud_amount,
            "type_counts": type_counts,
            "type_amounts": type_amounts,
            "fraud_by_type": fraud_by_type,
        }


def _rng_balance(rng: random.Random, amount: float, is_fraud: bool) -> tuple[float, float]:
    """Return (oldbalance_org, newbalance_org) that are consistent with amount.

    For fraud: balances are inconsistent (amount "disappears").
    For normal: new = old - amount (or old + amount for receiving side).
    """
    if is_fraud:
        # Fraudulent transactions have balance inconsistencies:
        # oldbalanceOrg + amount - newbalanceOrg ≈ amount (theft)
        old = amount + rng.uniform(0, amount * 0.1)
        new = rng.uniform(0, old * 0.05)
    else:
        # Normal: money flows out of sender
        old = amount + rng.uniform(0, amount * 2)
        new = old - amount
    return round(old, 2), round(max(0, new), 2)


def gen_paysim_sample(
    n: int = 500,
    *,
    fraud_rate_override: float | None = None,
    seed: int = 42,
) -> PaySimSample:
    """Generate ``n`` PaySim-statistically-faithful transactions.

    Parameters
    ----------
    n:
        Total number of transactions (including fraud).
    fraud_rate_override:
        Override the global fraud rate (e.g. 0.013 for 1.3%). Defaults to 0.0013.
    seed:
        RNG seed for reproducibility.

    Returns
    -------
    PaySimSample with raw transactions + graph-ready nodes/edges.
    """
    rng = random.Random(seed)

    txns: list[PaySimTransaction] = []
    fraud_count = 0

    for i in range(n):
        tx_type = _pick_type(rng)
        amount = _sample_amount(rng)
        step = rng.randint(1, 743)   # PaySim has 743 steps (31 days × 24h - 1h)

        # Decide fraud
        base_rate = _FRAUD_RATE_BY_TYPE.get(tx_type, 0.0)
        is_fraud = 1 if rng.random() < base_rate else 0

        # Override fraud rate globally (useful for demo — more visible)
        if fraud_rate_override is not None:
            is_fraud = 1 if rng.random() < fraud_rate_override else 0

        if is_fraud:
            fraud_count += 1

        is_flagged = 1 if (is_fraud and tx_type == "TRANSFER" and amount > _FLAG_THRESHOLD) else 0

        # Balances
        old_o, new_o = _rng_balance(rng, amount, bool(is_fraud))
        old_d = rng.uniform(0, amount * 3)
        new_d = old_d + amount

        name_orig = f"C{rng.randint(1_000_000, 9_999_999):07d}"
        name_dest = f"C{rng.randint(1_000_000, 9_999_999):07d}"

        txns.append(PaySimTransaction(
            id=f"TX{i:06d}",
            step=step,
            type=tx_type,
            amount=amount,
            name_orig=name_orig,
            oldbalance_org=old_o,
            newbalance_org=new_o,
            name_dest=name_dest,
            oldbalance_dest=round(old_d, 2),
            newbalance_dest=round(new_d, 2),
            is_fraud=is_fraud,
            is_flagged_fraud=is_flagged,
        ))

    # Build graph nodes + edges
    nodes: list[PaySimGraphNode] = []
    edges: list[PaySimGraphEdge] = []

    # Normalize to a manageable graph: cap at 120 nodes + 80 edges for display
    MAX_NODES = 120
    MAX_EDGES = 80

    # Count unique accounts
    seen_accounts: dict[str, PaySimGraphNode] = {}
    txn_count = 0
    edge_count = 0

    for tx in txns:
        if txn_count >= MAX_NODES // 2:
            break

        orig = tx.name_orig
        dest = tx.name_dest

        # Add customer nodes (senders + receivers)
        for cid, balance, role in [
            (orig, tx.oldbalance_org, "sender"),
            (dest, tx.oldbalance_dest, "receiver"),
        ]:
            if cid not in seen_accounts and len(seen_accounts) < MAX_NODES:
                seen_accounts[cid] = PaySimGraphNode(
                    id=cid,
                    label=cid,
                    node_type="customer",
                    balance=round(balance, 2),
                )
                nodes.append(seen_accounts[cid])

        if orig not in seen_accounts or dest not in seen_accounts:
            continue

        # Add transaction node
        tx_node = PaySimGraphNode(
            id=tx.id,
            label=f"{tx.type[:3]} ${tx.amount / 1000:.0f}k",
            node_type="transaction",
            amount=tx.amount,
            tx_type=tx.type,
            is_fraud=bool(tx.is_fraud),
            step=tx.step,
        )
        nodes.append(tx_node)

        # Edges: TX → sender (from_account)
        if edge_count < MAX_EDGES:
            edges.append(PaySimGraphEdge(
                source=tx.id, target=orig,
                edge_type="FROM",
                amount=tx.amount,
            ))
            edge_count += 1

        # Edges: TX → receiver (to_account)
        if edge_count < MAX_EDGES:
            edges.append(PaySimGraphEdge(
                source=tx.id, target=dest,
                edge_type="TO",
                amount=tx.amount,
            ))
            edge_count += 1

        # Flagged fraud edge
        if tx.is_flagged_fraud and edge_count < MAX_EDGES:
            edges.append(PaySimGraphEdge(
                source=tx.id, target=f"FLAGGED_{tx.id}",
                edge_type="FLAGGED",
                amount=tx.amount,
            ))
            edge_count += 1

        txn_count += 1

    sample = PaySimSample(
        transactions=txns,
        nodes=nodes,
        edges=edges,
        total_amount=sum(t.amount for t in txns),
        fraud_amount=sum(t.amount for t in txns if t.is_fraud),
        fraud_count=sum(1 for t in txns if t.is_fraud),
        transaction_count=len(txns),
    )
    return sample


def sample_as_api_dict(sample: PaySimSample) -> dict:
    """Serialize a PaySimSample into the JSON shape expected by the frontend."""

    # Node colours for the graph renderer
    def node_color(n: PaySimGraphNode) -> str:
        if n.node_type == "transaction":
            if n.is_fraud:
                return "#ff5d6c"    # red — fraud transaction
            if n.tx_type == "TRANSFER":
                return "#6ad1ff"   # blue
            if n.tx_type == "CASH_OUT":
                return "#ffd866"   # yellow
            if n.tx_type == "CASH_IN":
                return "#6affb0"   # green
            return "#a08fff"      # purple
        return "#6ad1ff"          # customer = blue

    def node_radius(n: PaySimGraphNode) -> float:
        if n.node_type == "transaction":
            if n.is_fraud:
                return 9.0
            return 6.0
        return 7.0

    nodes_out = [
        {
            "id": n.id,
            "label": n.label,
            "type": n.node_type,
            "is_fraud": n.is_fraud,
            "color": node_color(n),
            "radius": node_radius(n),
            "tx_type": n.tx_type,
            "step": n.step,
            "amount": n.amount,
        }
        for n in sample.nodes
    ]

    def edge_color(e: PaySimGraphEdge) -> str:
        if e.edge_type == "FLAGGED":
            return "#ff5d6c"
        if e.source.startswith("TX") and any(
            n["id"] == e.source and n["is_fraud"] for n in nodes_out
        ):
            return "#ff5d6c"
        return "#3a3f4f"

    edges_out = [
        {
            "source": e.source,
            "target": e.target,
            "type": e.edge_type,
            "amount": e.amount,
            "color": edge_color(e),
        }
        for e in sample.edges
    ]

    # Payment type breakdown for a bar chart card
    summary = sample.summary()
    type_counts = summary["type_counts"]
    type_amounts = summary["type_amounts"]
    type_list = ["CASH_OUT", "PAYMENT", "CASH_IN", "TRANSFER", "DEBIT"]
    payment_breakdown = {
        "labels": type_list,
        "counts": [type_counts.get(t, 0) for t in type_list],
        "amounts": [round(type_amounts.get(t, 0) / 1_000_000, 3) for t in type_list],
    }

    # Fraud stats
    fraud_stats = {
        "fraud_count": sample.fraud_count,
        "fraud_rate": summary["fraud_rate"],
        "fraud_amount": round(sample.fraud_amount / 1_000_000, 3),
        "fraud_by_type": summary["fraud_by_type"],
        "flagged_count": sum(1 for t in sample.transactions if t.is_flagged_fraud),
    }

    # Timeline (step → aggregated amount) for the step/time chart
    step_buckets: dict[int, float] = {}
    for t in sample.transactions:
        step_buckets[t.step] = step_buckets.get(t.step, 0) + t.amount
    timeline_labels = sorted(step_buckets.keys())
    timeline_amounts = [round(step_buckets[s] / 1_000_000, 4) for s in timeline_labels]

    return {
        "ok": True,
        "sample_size": len(sample.transactions),
        "nodes": nodes_out,
        "edges": edges_out,
        "payment_breakdown": payment_breakdown,
        "fraud_stats": fraud_stats,
        "timeline": {
            "labels": timeline_labels,
            "amounts": timeline_amounts,
        },
        "total_amount": round(sample.total_amount / 1_000_000, 3),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(description="PaySim-statistically-faithful generator")
    parser.add_argument("-n", "--size", type=int, default=500,
                        help="Number of transactions (default: 500)")
    parser.add_argument("--fraud-rate", type=float, default=None,
                        help="Override global fraud rate (e.g. 0.05 for 5%%)")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    sample = gen_paysim_sample(
        args.size,
        fraud_rate_override=args.fraud_rate,
        seed=args.seed,
    )
    summary = sample.summary()
    print("=== PaySim Sample Summary ===")
    print(f"  Transactions  : {summary['transaction_count']}")
    print(f"  Fraud        : {summary['fraud_count']} ({summary['fraud_rate']}%)")
    print(f"  Total amount : {summary['total_amount']:,.0f}")
    print(f"  Fraud amount : {summary['fraud_amount']:,.0f}")
    print()
    print("  By type:")
    for t in ["CASH_OUT", "PAYMENT", "CASH_IN", "TRANSFER", "DEBIT"]:
        cnt = summary["type_counts"].get(t, 0)
        amt = summary["type_amounts"].get(t, 0)
        fc = summary["fraud_by_type"].get(t, 0)
        print(f"    {t:<10} {cnt:6} tx  ${amt:>15,.0f}  fraud: {fc}")
    print()
    api = sample_as_api_dict(sample)
    print(f"  Graph nodes  : {len(api['nodes'])}")
    print(f"  Graph edges  : {len(api['edges'])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
