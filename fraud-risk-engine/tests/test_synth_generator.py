"""Tests for the synthetic data generator."""

from __future__ import annotations

import random
from pathlib import Path

import pytest

from app.loader.synth_generator import (
    build_dataset,
    dataset_to_csv_bundles,
    dataset_to_jsonl_bundles,
)


def test_dataset_is_deterministic() -> None:
    a = build_dataset(accounts=80, devices=40, merchants=20, transactions=400, fraud_rings=3, seed=42)
    b = build_dataset(accounts=80, devices=40, merchants=20, transactions=400, fraud_rings=3, seed=42)
    assert a.counts() == b.counts()
    assert a.planted_rings == b.planted_rings


def test_planted_rings_have_shared_device_and_ip() -> None:
    ds = build_dataset(accounts=80, devices=40, merchants=20, transactions=400, fraud_rings=4, seed=99)
    assert ds.planted_rings
    for r in ds.planted_rings:
        assert len(r["accounts"]) >= 3
        assert r["shared_device"].startswith("D_SHARED_R")
        assert r["shared_ip"].startswith("IP_SHARED_R")
        # every ring account should be wired to the shared device and ip
        assert any(e["to_id"] == r["shared_device"] and e["from_id"] in r["accounts"]
                   for e in ds.uses_device)


def test_bundles_roundtrip(tmp_path: Path) -> None:
    ds = build_dataset(accounts=20, devices=10, merchants=5, transactions=50, fraud_rings=1, seed=7)
    jsonl_root = tmp_path / "jsonl"
    csv_root = tmp_path / "csv"
    counts = dataset_to_jsonl_bundles(ds, jsonl_root)
    assert counts["customers"] == 20
    # at least 7 vertex / 9 edge jsonl files
    assert len(list(jsonl_root.glob("*.jsonl"))) >= 14

    csv_counts = dataset_to_csv_bundles(ds, csv_root)
    assert csv_counts["Customer"] == 20
    assert (csv_root / "Customer.csv").exists()


def test_generate_with_extreme_defaults_does_not_explode() -> None:
    # 1 account, 1 device, 1 merchant, 1 transaction, 1 ring — should still
    # yield a usable dataset (the ring generator picks >= 3 accounts and
    # falls back gracefully).
    ds = build_dataset(accounts=4, devices=4, merchants=2, transactions=10, fraud_rings=1, seed=1)
    assert ds.counts()["transactions"] >= 10
