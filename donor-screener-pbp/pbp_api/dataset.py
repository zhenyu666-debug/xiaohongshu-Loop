"""CSV-backed candidate dataset loader.

Single source of truth: `data/candidates.csv` at the donor-screener-pbp root.
Schema:
  id          (int)        - molecule id
  smiles      (str)        - SMILES representation
  score       (float)      - composite score (higher = better)
  rank        (int)        - global rank (1-based)
  descriptor_* (float)     - any number of numeric descriptors
"""
from __future__ import annotations

import csv
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Iterable

DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "candidates.csv"


@dataclass(frozen=True)
class Candidate:
    id: int
    smiles: str
    score: float
    rank: int
    descriptors: dict[str, float]

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "smiles": self.smiles,
            "score": self.score,
            "rank": self.rank,
            **self.descriptors,
        }


def _safe_float(v: str) -> float | None:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


@lru_cache(maxsize=1)
def load_all() -> tuple[Candidate, ...]:
    if not DATA_PATH.exists():
        return _seed_demo()
    out: list[Candidate] = []
    with DATA_PATH.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        descriptor_cols = [c for c in (reader.fieldnames or []) if c.startswith("descriptor_")]
        for row in reader:
            desc = {col.removeprefix("descriptor_"): _safe_float(row[col]) for col in descriptor_cols}
            desc = {k: v for k, v in desc.items() if v is not None}
            try:
                cid = int(row["id"])
            except (KeyError, TypeError, ValueError):
                continue
            try:
                score = float(row["score"])
            except (KeyError, TypeError, ValueError):
                continue
            out.append(
                Candidate(
                    id=cid,
                    smiles=row.get("smiles", ""),
                    score=score,
                    rank=0,
                    descriptors=desc,
                )
            )
    out.sort(key=lambda c: c.score, reverse=True)
    ranked = tuple(
        Candidate(c.id, c.smiles, c.score, idx + 1, c.descriptors)
        for idx, c in enumerate(out)
    )
    return ranked


def _seed_demo() -> tuple[Candidate, ...]:
    """Deterministic demo dataset so the GUI has something to render before real pbp runs."""
    import math

    out: list[Candidate] = []
    for i in range(1, 51):
        score = round(0.5 + 0.5 * math.sin(i * 0.7) + 0.01 * i, 4)
        desc = {
            "tpsa": round(60 + (i * 3.7) % 90, 2),
            "logp": round(-1 + (i * 0.31) % 5, 2),
            "dn": round(15 + (i * 1.7) % 25, 2),
            "ew": round(2.5 + (i * 0.13) % 4, 2),
        }
        out.append(Candidate(id=i, smiles=f"C{i}H{(i * 2) + 4}O{(i % 3) + 1}", score=score, rank=0, descriptors=desc))
    out.sort(key=lambda c: c.score, reverse=True)
    return tuple(
        Candidate(c.id, c.smiles, c.score, idx + 1, c.descriptors)
        for idx, c in enumerate(out)
    )


def filter_by_score(score_min: float | None = None, score_max: float | None = None) -> list[Candidate]:
    res: Iterable[Candidate] = load_all()
    if score_min is not None:
        res = [c for c in res if c.score >= score_min]
    if score_max is not None:
        res = [c for c in res if c.score <= score_max]
    return list(res)


def distribution(buckets: int = 10) -> list[dict[str, float | int]]:
    data = load_all()
    if not data:
        return []
    lo = min(c.score for c in data)
    hi = max(c.score for c in data)
    if hi == lo:
        hi = lo + 1.0
    step = (hi - lo) / buckets
    counts = [0] * buckets
    for c in data:
        idx = min(buckets - 1, int((c.score - lo) / step))
        counts[idx] += 1
    return [
        {
            "bucket": f"{lo + i * step:.3f}-{lo + (i + 1) * step:.3f}",
            "count": counts[i],
            "lo": lo + i * step,
            "hi": lo + (i + 1) * step,
        }
        for i in range(buckets)
    ]