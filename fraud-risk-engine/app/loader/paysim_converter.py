"""PaySim CSV → TigerGraph-ready JSONL graph bundles.

Converts the Kaggle PaySim synthetic financial dataset into the
graph format used by fraud-risk-engine::

    https://www.kaggle.com/datasets/varshithkumaranand/banking-fruad-detection-dataset-with-99-accuracy

PaySim columns
--------------
step           int   — time unit (1 hour each)
type           str   — TRANSFER | CASH_OUT | PAYMENT | CASH_IN | DEBIT
amount         float — transaction amount
nameOrig       str   — sender customer ID (C...)
oldbalanceOrg  float — sender balance before
newbalanceOrig float — sender balance after
nameDest       str   — receiver customer ID (C...)
oldbalanceDest float — receiver balance before
newbalanceDest float — receiver balance after
isFraud       int   — 1=fraud, 0=normal
isFlaggedFraud int  — system flag (rare)

Graph mapping
------------
Vertex  PaySim entity
────────────────────────────────────────────
Customer  nameOrig / nameDest (normalised to C...)
Account   derived: one per customer (balance snapshots)
Transaction  step + type + amount + isFraud
Merchant    nameDest (when type=TRANSFER/CASH_OUT)

Edges
────────────────────────────────────────────────────
OWNS          Customer → Account
FROM_ACCOUNT  Transaction → Account (sender)
TO_ACCOUNT    Transaction → Account (receiver)
PAID_TO       Transaction → Merchant
IS_FRAUD      Transaction → FraudFlag   (only when isFraud=1)
"""

from __future__ import annotations

import csv
import json
import logging
import math
import sys
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import IO, Iterable, Iterator, TextIO

from .synth_generator import GeneratedDataset

log = logging.getLogger(__name__)

# PaySim transaction types → graph mapping
FRAUD_TYPES = {"TRANSFER", "CASH_OUT"}   # fraud mainly happens here


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class PaySimRecord:
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
class PaySimGraphDataset:
    """Graph representation of a PaySim sample."""
    customers: list[dict] = field(default_factory=list)
    accounts: list[dict] = field(default_factory=list)
    transactions: list[dict] = field(default_factory=list)
    merchants: list[dict] = field(default_factory=list)
    fraud_flags: list[dict] = field(default_factory=list)
    owns: list[dict] = field(default_factory=list)
    from_account: list[dict] = field(default_factory=list)
    to_account: list[dict] = field(default_factory=list)
    paid_to: list[dict] = field(default_factory=list)
    is_fraud: list[dict] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "customers": len(self.customers),
            "accounts": len(self.accounts),
            "transactions": len(self.transactions),
            "merchants": len(self.merchants),
            "fraud_flags": len(self.fraud_flags),
            "owns": len(self.owns),
            "from_account": len(self.from_account),
            "to_account": len(self.to_account),
            "paid_to": len(self.paid_to),
            "is_fraud": len(self.is_fraud),
            "fraud_transactions": sum(1 for t in self.transactions if t.get("is_fraud")),
        }


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def parse_paysim_row(row: dict) -> PaySimRecord:
    return PaySimRecord(
        step=int(row["step"]),
        type=row["type"],
        amount=float(row["amount"]),
        name_orig=row["nameOrig"],
        oldbalance_org=float(row["oldbalanceOrg"]),
        newbalance_org=float(row["newbalanceOrig"]),
        name_dest=row["nameDest"],
        oldbalance_dest=float(row["oldbalanceDest"]),
        newbalance_dest=float(row["newbalanceDest"]),
        is_fraud=int(row["isFraud"]),
        is_flagged_fraud=int(row["isFlaggedFraud"]),
    )


def read_paysim_csv(path: str | Path) -> Iterator[PaySimRecord]:
    with open(path, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            yield parse_paysim_row(row)


def read_paysim_stream(stream: TextIO) -> Iterator[PaySimRecord]:
    reader = csv.DictReader(stream)
    for row in reader:
        yield parse_paysim_row(row)


# ---------------------------------------------------------------------------
# Converter
# ---------------------------------------------------------------------------

def paysim_to_graph(
    records: Iterable[PaySimRecord],
    *,
    sample_size: int | None = None,
    fraud_only: bool = False,
    seed: int = 42,
) -> PaySimGraphDataset:
    """Convert PaySim records into a graph dataset.

    Parameters
    ----------
    records:
        Iterator of PaySimRecord.
    sample_size:
        If set, sample this many records (deterministic).
        Use ``fraud_only=True`` to oversample fraud.
    fraud_only:
        If True, include only fraud transactions (for focused analysis).
    seed:
        RNG seed for reproducibility.
    """
    import random

    ds = PaySimGraphDataset()
    seen_customers: dict[str, bool] = {}
    seen_accounts: dict[str, bool] = {}
    seen_merchants: dict[str, bool] = {}
    seen_tx: dict[str, bool] = {}

    # Two-pass: first collect all, then deduplicate vertices
    all_records: list[PaySimRecord] = []

    for rec in records:
        if fraud_only and rec.is_fraud != 1:
            continue
        all_records.append(rec)

    # Sample if needed
    if sample_size and len(all_records) > sample_size:
        rng = random.Random(seed)
        # Always include all fraud records
        fraud_records = [r for r in all_records if r.is_fraud == 1]
        non_fraud = [r for r in all_records if r.is_fraud == 0]
        remaining = sample_size - len(fraud_records)
        if remaining > 0:
            sampled = rng.sample(non_fraud, min(remaining, len(non_fraud)))
            all_records = fraud_records + sampled
        else:
            all_records = fraud_records[:sample_size]

    # Build vertices and edges
    for rec in all_records:
        orig_id = rec.name_orig
        dest_id = rec.name_dest
        tx_id = f"TX_{rec.step}_{orig_id}_{dest_id}"

        if tx_id in seen_tx:
            continue
        seen_tx[tx_id] = True

        # Customer (sender)
        if orig_id not in seen_customers:
            seen_customers[orig_id] = True
            ds.customers.append({
                "id": orig_id,
                "name": orig_id,
                "country": "PaySim",
                "risk_score": 0.0,
            })

        # Customer (receiver)
        if dest_id not in seen_customers:
            seen_customers[dest_id] = True
            ds.customers.append({
                "id": dest_id,
                "name": dest_id,
                "country": "PaySim",
                "risk_score": 0.0,
            })

        # Account (sender)
        acc_orig = f"ACC_{orig_id}"
        if acc_orig not in seen_accounts:
            seen_accounts[acc_orig] = True
            ds.accounts.append({
                "id": acc_orig,
                "account_type": "checking",
                "opened_at": f"step_{rec.step}",
                "balance": rec.newbalance_org,
                "status": "active",
                "risk_score": 0.0,
            })
            ds.owns.append({
                "from_id": orig_id,
                "to_id": acc_orig,
                "since": f"step_{rec.step}",
            })

        # Account (receiver)
        acc_dest = f"ACC_{dest_id}"
        if acc_dest not in seen_accounts:
            seen_accounts[acc_dest] = True
            ds.accounts.append({
                "id": acc_dest,
                "account_type": "checking",
                "opened_at": f"step_{rec.step}",
                "balance": rec.newbalance_dest,
                "status": "active",
                "risk_score": 0.0,
            })
            ds.owns.append({
                "from_id": dest_id,
                "to_id": acc_dest,
                "since": f"step_{rec.step}",
            })

        # Transaction
        ds.transactions.append({
            "id": tx_id,
            "ts": f"step_{rec.step}",
            "amount": rec.amount,
            "currency": "PaySim",
            "channel": rec.type,
            "status": "posted",
            "is_fraud": rec.is_fraud,
        })

        # FROM_ACCOUNT edge
        ds.from_account.append({
            "from_id": tx_id,
            "to_id": acc_orig,
            "amount": rec.amount,
            "ts": f"step_{rec.step}",
        })

        # TO_ACCOUNT edge
        ds.to_account.append({
            "from_id": tx_id,
            "to_id": acc_dest,
            "amount": rec.amount,
            "ts": f"step_{rec.step}",
        })

        # Merchant (for TRANSFER/CASH_OUT)
        if rec.type in FRAUD_TYPES and dest_id not in seen_merchants:
            seen_merchants[dest_id] = True
            ds.merchants.append({
                "id": dest_id,
                "name": dest_id,
                "mcc": rec.type,
                "country": "PaySim",
                "risk_score": 0.0,
            })
            ds.paid_to.append({
                "from_id": tx_id,
                "to_id": dest_id,
                "amount": rec.amount,
            })

        # Fraud flag
        if rec.is_fraud == 1:
            fraud_flag_id = f"FRAUD_{tx_id}"
            ds.fraud_flags.append({
                "id": fraud_flag_id,
                "step": rec.step,
                "type": rec.type,
                "amount": rec.amount,
            })
            ds.is_fraud.append({
                "from_id": tx_id,
                "to_id": fraud_flag_id,
                "amount": rec.amount,
            })

    return ds


# ---------------------------------------------------------------------------
# I/O helpers
# ---------------------------------------------------------------------------

def paysim_csv_to_jsonl(
    csv_path: str | Path,
    output_dir: str | Path,
    sample_size: int = 5000,
    fraud_only: bool = False,
    seed: int = 42,
) -> dict[str, int]:
    """Convert a PaySim CSV file to JSONL bundles under ``output_dir``."""
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    log.info("Reading %s …", csv_path)
    t0 = time.perf_counter()
    records = list(read_paysim_csv(csv_path))
    log.info("Read %d rows in %.1fs", len(records), time.perf_counter() - t0)

    log.info("Converting to graph (sample=%s, fraud_only=%s) …",
             sample_size, fraud_only)
    t1 = time.perf_counter()
    ds = paysim_to_graph(records, sample_size=sample_size,
                         fraud_only=fraud_only, seed=seed)
    log.info("Graph built in %.1fs: %s", time.perf_counter() - t1, ds.counts())

    counts: dict[str, int] = {}
    for name, items in [
        ("customers", ds.customers),
        ("accounts", ds.accounts),
        ("transactions", ds.transactions),
        ("merchants", ds.merchants),
        ("fraud_flags", ds.fraud_flags),
    ]:
        path = output_dir / f"{name}.jsonl"
        n = _write_jsonl(path, items)
        counts[name] = n

    for name, items in [
        ("owns", ds.owns),
        ("from_account", ds.from_account),
        ("to_account", ds.to_account),
        ("paid_to", ds.paid_to),
        ("is_fraud", ds.is_fraud),
    ]:
        path = output_dir / f"{name}.jsonl"
        n = _write_jsonl(path, items)
        counts[name] = n

    log.info("Wrote %d JSONL files → %s", len(counts), output_dir)
    return counts


def _write_jsonl(path: Path, items: list[dict]) -> int:
    n = 0
    with path.open("w", encoding="utf-8") as f:
        for item in items:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")
            n += 1
    return n


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Convert PaySim CSV to graph JSONL bundles."
    )
    parser.add_argument("csv", help="Path to PaySim CSV file")
    parser.add_argument("-o", "--output", default="data/paysim_graph",
                        help="Output directory (default: data/paysim_graph)")
    parser.add_argument("-n", "--sample-size", type=int, default=5000,
                        help="Max rows to convert (default: 5000)")
    parser.add_argument("--fraud-only", action="store_true",
                        help="Include only fraud transactions")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed (default: 42)")

    args = parser.parse_args(argv)
    counts = paysim_csv_to_jsonl(
        args.csv, args.output,
        sample_size=args.sample_size,
        fraud_only=args.fraud_only,
        seed=args.seed,
    )
    print(json.dumps(counts, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
