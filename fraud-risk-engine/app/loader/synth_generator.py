"""Deterministic synthetic data generator for the FraudRisk graph.

We synthesise four entity pools and three event pools, plus a configurable
number of planted fraud rings. The generator is *deterministic* — given the
same seed it produces the same dataset, which makes it ideal for
regression tests and reproducible demos.

The generator relies only on stdlib — ``faker`` was avoided on purpose so
the package works in air-gapped CI.
"""

from __future__ import annotations

import json
import random
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterable


# ---------------------------------------------------------------------------
# Tiny embedded wordlists — replace ``faker`` for the names/cities we need.
# ---------------------------------------------------------------------------


_FIRST_NAMES = [
    "Alice", "Brian", "Cathy", "David", "Eva", "Frank", "Grace", "Henry",
    "Iris", "Jack", "Kate", "Liam", "Mia", "Noah", "Olivia", "Peter",
    "Quinn", "Rose", "Sam", "Tina", "Uma", "Victor", "Wendy", "Xander",
    "Yara", "Zoe",
]
_LAST_NAMES = [
    "Aaronson", "Brown", "Chen", "Davis", "Evans", "Foster", "Garcia",
    "Hernandez", "Ito", "Johnson", "Kim", "Lopez", "Martinez", "Nguyen",
    "Obrien", "Patel", "Quintero", "Robinson", "Singh", "Tanaka",
    "Underwood", "Vargas", "Wright", "Xu", "Young", "Zhang",
]
_CITIES = [
    "Shanghai", "Beijing", "Shenzhen", "Hangzhou", "Guangzhou", "Chengdu",
    "Suzhou", "Wuhan", "Tokyo", "Osaka", "Seoul", "Singapore", "Bangkok",
    "Kuala Lumpur", "Jakarta", "Manila", "Hanoi", "Mumbai", "Delhi",
    "Sydney", "Melbourne", "Auckland", "Toronto", "Vancouver", "Seattle",
    "San Francisco", "Los Angeles", "New York", "Boston", "Miami",
    "Berlin", "Munich", "Paris", "London", "Amsterdam", "Madrid", "Rome",
    "Moscow", "Dubai", "Istanbul",
]
_COUNTRIES = ["CHN", "JPN", "KOR", "SGP", "THA", "MYS", "IDN", "PHL",
              "VNM", "IND", "AUS", "NZL", "CAN", "USA", "GBR", "FRA",
              "DEU", "ESP", "ITA", "RUS", "ARE", "TUR", "BRA", "MEX",
              "ARG", "ZAF", "EGY", "NGA", "KEN"]
_COMPANY_PREFIXES = ["Acme", "Globex", "Initech", "Soylent", "Umbrella",
                     "Hooli", "Wonka", "Stark", "Wayne", "Pied Piper",
                     "Cyberdyne", "Massive Dynamic", "Tyrell", "Aperture",
                     "Black Mesa", "Vandelay", "Sirius", "Tycho", "Gringotts",
                     "InGen", "Aether", "OsCorp"]


def _name(rng: random.Random) -> str:
    return f"{rng.choice(_FIRST_NAMES)} {rng.choice(_LAST_NAMES)}"


def _company(rng: random.Random) -> str:
    return f"{rng.choice(_COMPANY_PREFIXES)} {rng.choice(['Holdings', 'Group', 'Ltd', 'LLC', 'Capital', 'Pay', 'Tech', 'Bank', 'Trade'])}"


def _city(rng: random.Random) -> str:
    return rng.choice(_CITIES)


def _country(rng: random.Random) -> str:
    return rng.choice(_COUNTRIES)


def _dob(rng: random.Random) -> str:
    today = datetime.now(timezone.utc).date()
    age = rng.randint(18, 85)
    year = today.year - age
    month = rng.randint(1, 12)
    day = rng.randint(1, 28)
    return f"{year:04d}-{month:02d}-{day:02d}"


def _hashlike(rng: random.Random, n: int = 32) -> str:
    return "".join(rng.choices("0123456789abcdef", k=n))


# ---------------------------------------------------------------------------
# GeneratedDataset container + build_dataset
# ---------------------------------------------------------------------------


@dataclass
class GeneratedDataset:
    """Container for a synthesised fraud graph dataset."""

    customers: list[dict] = field(default_factory=list)
    accounts: list[dict] = field(default_factory=list)
    cards: list[dict] = field(default_factory=list)
    devices: list[dict] = field(default_factory=list)
    ips: list[dict] = field(default_factory=list)
    merchants: list[dict] = field(default_factory=list)
    transactions: list[dict] = field(default_factory=list)

    # Edges
    owns: list[dict] = field(default_factory=list)
    has_card: list[dict] = field(default_factory=list)
    uses_device: list[dict] = field(default_factory=list)
    logged_from: list[dict] = field(default_factory=list)
    paid_to: list[dict] = field(default_factory=list)
    from_account: list[dict] = field(default_factory=list)
    to_account: list[dict] = field(default_factory=list)
    shares_device: list[dict] = field(default_factory=list)
    shares_ip: list[dict] = field(default_factory=list)

    # Planted rings metadata for verification
    planted_rings: list[dict] = field(default_factory=list)

    def counts(self) -> dict[str, int]:
        return {
            "customers": len(self.customers),
            "accounts": len(self.accounts),
            "cards": len(self.cards),
            "devices": len(self.devices),
            "ips": len(self.ips),
            "merchants": len(self.merchants),
            "transactions": len(self.transactions),
            "owns": len(self.owns),
            "has_card": len(self.has_card),
            "uses_device": len(self.uses_device),
            "logged_from": len(self.logged_from),
            "paid_to": len(self.paid_to),
            "from_account": len(self.from_account),
            "to_account": len(self.to_account),
            "shares_device": len(self.shares_device),
            "shares_ip": len(self.shares_ip),
            "planted_rings": len(self.planted_rings),
        }


def _ts(rng: random.Random, base: datetime, max_minutes: int = 60 * 24 * 30) -> str:
    offset = timedelta(minutes=rng.randint(0, max_minutes))
    return (base - offset).isoformat(timespec="seconds")


def _amount(rng: random.Random) -> float:
    # Power-law: lots of small, a few large.
    return round(rng.paretovariate(1.5) * 80.0 + rng.uniform(5.0, 50.0), 2)


def build_dataset(
    *,
    accounts: int = 1200,
    devices: int = 900,
    merchants: int = 300,
    transactions: int = 20000,
    fraud_rings: int = 6,
    seed: int = 20260716,
) -> GeneratedDataset:
    """Build a deterministic synthetic dataset.

    Parameters mirror the ``SYNTH_*`` settings and are passed explicitly so
    the generator remains a pure function (no global state, easy to test).
    """
    rng = random.Random(seed)
    ds = GeneratedDataset()

    # --- Customers ---
    for i in range(accounts):
        cust_id = f"C{i:06d}"
        ds.customers.append(
            {
                "id": cust_id,
                "name": _name(rng),
                "dob": _dob(rng),
                "country": _country(rng),
                "risk_score": round(rng.random(), 4),
            }
        )

    # --- Accounts ---
    account_types = ["checking", "savings", "credit"]
    statuses = ["active", "active", "active", "dormant", "frozen"]
    base = datetime.now(timezone.utc)
    for i in range(accounts):
        acc_id = f"A{i:06d}"
        opened_at = _ts(rng, base, max_minutes=60 * 24 * 365 * 5)
        ds.accounts.append(
            {
                "id": acc_id,
                "account_type": rng.choice(account_types),
                "opened_at": opened_at,
                "balance": round(rng.uniform(0.0, 50000.0), 2),
                "status": rng.choice(statuses),
                "risk_score": round(rng.random(), 4),
            }
        )
        ds.owns.append({"from_id": f"C{i:06d}", "to_id": acc_id, "since": opened_at})

    # --- Cards ---
    card_brands = ["visa", "mastercard", "amex", "unionpay"]
    for i in range(accounts):
        card_id = f"CD{i:06d}"
        issued_at = _ts(rng, base, max_minutes=60 * 24 * 365 * 3)
        ds.cards.append(
            {
                "id": card_id,
                "card_type": rng.choice(["debit", "credit"]),
                "brand": rng.choice(card_brands),
                "issued_at": issued_at,
                "status": rng.choice(["active", "active", "expired", "blocked"]),
            }
        )
        ds.has_card.append({"from_id": f"A{i:06d}", "to_id": card_id, "since": issued_at})

    # --- Devices ---
    device_types = ["mobile", "desktop", "tablet", "pos_terminal"]
    for i in range(devices):
        dev_id = f"D{i:06d}"
        ds.devices.append(
            {
                "id": dev_id,
                "fingerprint": _hashlike(rng, 32),
                "device_type": rng.choice(device_types),
                "os": rng.choice(["Android", "iOS", "Windows", "macOS", "Linux"]),
                "first_seen": _ts(rng, base),
                "last_seen": _ts(rng, base, max_minutes=60 * 24 * 7),
            }
        )

    # --- IPs (one canonical IP per account + extra shared) ---
    for i in range(accounts):
        ip_id = f"IP{i:06d}"
        ds.ips.append(
            {
                "id": ip_id,
                "asn": f"AS{rng.randint(1000, 65000)}",
                "country": _country(rng),
                "city": _city(rng),
                "reputation": round(rng.random(), 4),
            }
        )

    # --- Merchants ---
    mcc_codes = ["5411", "5812", "7011", "5999", "7995", "6051"]
    for i in range(merchants):
        m_id = f"M{i:06d}"
        ds.merchants.append(
            {
                "id": m_id,
                "name": _company(rng),
                "mcc": rng.choice(mcc_codes),
                "country": _country(rng),
                "risk_score": round(rng.random(), 4),
            }
        )

    # --- Account <-> Device / IP edges ---
    for i in range(accounts):
        acc_id = f"A{i:06d}"
        for _ in range(rng.randint(1, 3)):
            dev_id = f"D{rng.randint(0, devices - 1):06d}"
            ds.uses_device.append(
                {
                    "from_id": acc_id,
                    "to_id": dev_id,
                    "first_seen": _ts(rng, base),
                    "last_seen": _ts(rng, base, max_minutes=60 * 24 * 30),
                    "count": rng.randint(1, 25),
                }
            )
        for _ in range(rng.randint(1, 2)):
            ip_id = f"IP{i:06d}" if rng.random() < 0.7 else f"IP{rng.randint(0, accounts - 1):06d}"
            ds.logged_from.append(
                {
                    "from_id": acc_id,
                    "to_id": ip_id,
                    "first_seen": _ts(rng, base),
                    "last_seen": _ts(rng, base, max_minutes=60 * 24 * 30),
                    "count": rng.randint(1, 40),
                }
            )

    # --- Planted fraud rings ---
    for ring_idx in range(fraud_rings):
        ring_len = rng.randint(4, 6)
        ring_accounts = [f"A{rng.randint(0, accounts - 1):06d}" for _ in range(ring_len)]
        seen: set[str] = set()
        ring_accounts = [a for a in ring_accounts if not (a in seen or seen.add(a))]
        if len(ring_accounts) < 3:
            continue

        shared_dev = f"D_SHARED_R{ring_idx:03d}"
        shared_ip = f"IP_SHARED_R{ring_idx:03d}"
        ds.devices.append(
            {
                "id": shared_dev,
                "fingerprint": f"ring-{ring_idx:03d}-device",
                "device_type": "mobile",
                "os": "Android",
                "first_seen": _ts(rng, base),
                "last_seen": _ts(rng, base, max_minutes=60 * 24),
            }
        )
        ds.ips.append(
            {
                "id": shared_ip,
                "asn": f"AS{9000 + ring_idx}",
                "country": "ZZZ",
                "city": f"RingCity{ring_idx}",
                "reputation": 0.05,
            }
        )
        for acc in ring_accounts:
            ds.uses_device.append(
                {
                    "from_id": acc,
                    "to_id": shared_dev,
                    "first_seen": _ts(rng, base),
                    "last_seen": _ts(rng, base, max_minutes=60 * 24),
                    "count": rng.randint(8, 30),
                }
            )
            ds.logged_from.append(
                {
                    "from_id": acc,
                    "to_id": shared_ip,
                    "first_seen": _ts(rng, base),
                    "last_seen": _ts(rng, base, max_minutes=60 * 24),
                    "count": rng.randint(10, 40),
                }
            )
        n = len(ring_accounts)
        for k in range(n):
            src = ring_accounts[k]
            dst = ring_accounts[(k + 1) % n]
            tx_id = f"T_R{ring_idx:03d}_{k:02d}"
            tx_ts = _ts(rng, base, max_minutes=60 * 24 * 7)
            amount = round(rng.uniform(50.0, 950.0), 2)
            ds.transactions.append(
                {
                    "id": tx_id,
                    "ts": tx_ts,
                    "amount": amount,
                    "currency": "USD",
                    "channel": "wire",
                    "status": "completed",
                }
            )
            ds.from_account.append({"from_id": tx_id, "to_id": src, "amount": amount, "ts": tx_ts})
            ds.to_account.append({"from_id": tx_id, "to_id": dst, "amount": amount, "ts": tx_ts})
            ds.paid_to.append(
                {
                    "from_id": tx_id,
                    "to_id": f"M{rng.randint(0, merchants - 1):06d}",
                    "amount": amount,
                }
            )
        ds.planted_rings.append(
            {
                "ring_id": ring_idx,
                "accounts": ring_accounts,
                "shared_device": shared_dev,
                "shared_ip": shared_ip,
            }
        )

    # --- Random noise transactions ---
    remaining = max(transactions - len(ds.transactions), 0)
    for i in range(remaining):
        tx_id = f"T{i:06d}"
        tx_ts = _ts(rng, base)
        amt = _amount(rng)
        ds.transactions.append(
            {
                "id": tx_id,
                "ts": tx_ts,
                "amount": amt,
                "currency": "USD",
                "channel": rng.choice(["ach", "card", "wire", "atm"]),
                "status": rng.choice(["completed", "completed", "completed", "failed"]),
            }
        )
        ds.from_account.append(
            {
                "from_id": tx_id,
                "to_id": f"A{rng.randint(0, accounts - 1):06d}",
                "amount": amt,
                "ts": tx_ts,
            }
        )
        ds.to_account.append(
            {
                "from_id": tx_id,
                "to_id": f"A{rng.randint(0, accounts - 1):06d}",
                "amount": amt,
                "ts": tx_ts,
            }
        )
        ds.paid_to.append(
            {"from_id": tx_id, "to_id": f"M{rng.randint(0, merchants - 1):06d}", "amount": amt}
        )

    # --- SHARES_DEVICE / SHARES_IP computed edges ---
    device_to_accounts: dict[str, list[str]] = defaultdict(list)
    for e in ds.uses_device:
        device_to_accounts[e["to_id"]].append(e["from_id"])
    for dev_id, accs in device_to_accounts.items():
        accs = list(dict.fromkeys(accs))
        for i in range(len(accs)):
            for j in range(i + 1, len(accs)):
                ds.shares_device.append(
                    {"from_id": accs[i], "to_id": accs[j], "device_id": dev_id, "count": 1}
                )
                ds.shares_device.append(
                    {"from_id": accs[j], "to_id": accs[i], "device_id": dev_id, "count": 1}
                )

    ip_to_accounts: dict[str, list[str]] = defaultdict(list)
    for e in ds.logged_from:
        ip_to_accounts[e["to_id"]].append(e["from_id"])
    for ip_id, accs in ip_to_accounts.items():
        accs = list(dict.fromkeys(accs))
        for i in range(len(accs)):
            for j in range(i + 1, len(accs)):
                ds.shares_ip.append(
                    {"from_id": accs[i], "to_id": accs[j], "ip_id": ip_id, "count": 1}
                )
                ds.shares_ip.append(
                    {"from_id": accs[j], "to_id": accs[i], "ip_id": ip_id, "count": 1}
                )

    return ds


# ---------------------------------------------------------------------------
# Serialisation helpers
# ---------------------------------------------------------------------------


import csv  # local import to keep module-level imports clean


def _write_jsonl(path: Path, rows: Iterable[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, ensure_ascii=False) + "\n")
            n += 1
    return n


def _write_csv(path: Path, rows: list[dict]) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return 0
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    return len(rows)


def dataset_to_jsonl_bundles(ds: GeneratedDataset, root: Path) -> dict[str, int]:
    """Serialise the dataset as one JSONL file per vertex / edge type."""
    root.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    counts["customers"] = _write_jsonl(root / "vertex_Customer.jsonl", ds.customers)
    counts["accounts"] = _write_jsonl(root / "vertex_Account.jsonl", ds.accounts)
    counts["cards"] = _write_jsonl(root / "vertex_Card.jsonl", ds.cards)
    counts["devices"] = _write_jsonl(root / "vertex_Device.jsonl", ds.devices)
    counts["ips"] = _write_jsonl(root / "vertex_IP.jsonl", ds.ips)
    counts["merchants"] = _write_jsonl(root / "vertex_Merchant.jsonl", ds.merchants)
    counts["transactions"] = _write_jsonl(root / "vertex_Transaction.jsonl", ds.transactions)
    counts["owns"] = _write_jsonl(root / "edge_OWNS.jsonl", ds.owns)
    counts["has_card"] = _write_jsonl(root / "edge_HAS_CARD.jsonl", ds.has_card)
    counts["uses_device"] = _write_jsonl(root / "edge_USES_DEVICE.jsonl", ds.uses_device)
    counts["logged_from"] = _write_jsonl(root / "edge_LOGGED_FROM.jsonl", ds.logged_from)
    counts["paid_to"] = _write_jsonl(root / "edge_PAID_TO.jsonl", ds.paid_to)
    counts["from_account"] = _write_jsonl(root / "edge_FROM_ACCOUNT.jsonl", ds.from_account)
    counts["to_account"] = _write_jsonl(root / "edge_TO_ACCOUNT.jsonl", ds.to_account)
    counts["shares_device"] = _write_jsonl(root / "edge_SHARES_DEVICE.jsonl", ds.shares_device)
    counts["shares_ip"] = _write_jsonl(root / "edge_SHARES_IP.jsonl", ds.shares_ip)
    return counts


def dataset_to_csv_bundles(ds: GeneratedDataset, root: Path) -> dict[str, int]:
    """Serialise the dataset as flat CSV files. Useful for ``tg_load`` style
    loading jobs or as a sanity-check artefact."""
    root.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {}
    for name, rows in [
        ("Customer", ds.customers),
        ("Account", ds.accounts),
        ("Card", ds.cards),
        ("Device", ds.devices),
        ("IP", ds.ips),
        ("Merchant", ds.merchants),
        ("Transaction", ds.transactions),
        ("OWNS", ds.owns),
        ("HAS_CARD", ds.has_card),
        ("USES_DEVICE", ds.uses_device),
        ("LOGGED_FROM", ds.logged_from),
        ("PAID_TO", ds.paid_to),
        ("FROM_ACCOUNT", ds.from_account),
        ("TO_ACCOUNT", ds.to_account),
        ("SHARES_DEVICE", ds.shares_device),
        ("SHARES_IP", ds.shares_ip),
    ]:
        counts[name] = _write_csv(root / f"{name}.csv", rows)
    return counts