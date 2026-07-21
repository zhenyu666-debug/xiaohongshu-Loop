"""Tests for the LDBC SNB loader."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from app.loader.ldbc_snb_loader import (
    GeneratedLDBCSNB,
    build_ldbc_snb_dataset,
    dataset_to_csv_bundles,
    dataset_to_jsonl_bundles,
)

# SF=0.001 produces ~4 persons, ~500 posts, ~2 500 comments, ~10 forums.
# This is fast enough for CI while still exercising every code path.
_TEST_SF = 0.001


# ---------------------------------------------------------------------------
# Determinism
# ---------------------------------------------------------------------------

def test_dataset_is_deterministic() -> None:
    """Two calls with the same seed must produce bit-identical counts."""
    a = build_ldbc_snb_dataset(sf=_TEST_SF, seed=42)
    b = build_ldbc_snb_dataset(sf=_TEST_SF, seed=42)
    assert a.counts() == b.counts()


def test_different_seed_produces_different_dataset() -> None:
    a = build_ldbc_snb_dataset(sf=_TEST_SF, seed=1)
    b = build_ldbc_snb_dataset(sf=_TEST_SF, seed=2)
    assert a.counts() != b.counts()


# ---------------------------------------------------------------------------
# Vertex / edge shape at SF=0.001
# ---------------------------------------------------------------------------

def test_vertex_counts_at_tiny_sf() -> None:
    """Verify exact counts at _TEST_SF scale (SF=0.001)."""
    ds = build_ldbc_snb_dataset(sf=_TEST_SF, seed=7)
    c = ds.counts()

    # Exact from formula: round(3904 * 0.001) = 4
    assert c["person"] == 4

    # round(499_968 * 0.001) = 500
    assert c["post"] == 500

    # round(2_498_528 * 0.001) = 2499
    assert c["comment"] == 2499

    # round(9_985 * 0.001) = 10
    assert c["forum"] == 10

    # round(16_088 * 0.001) = 16
    assert c["tag"] == 16

    # TagClasses: fixed 10
    assert c["tagclass"] == 10

    # round(3_996 * 0.001) = 4
    assert c["city"] == 4

    # round(1_490 * 0.001) = 1
    assert c["company"] == 1

    # round(3_478 * 0.001) = 3
    assert c["university"] == 3

    # Place = Continent + Country + City
    assert c["place"] == c["continent"] + c["country"] + c["city"]
    # Continent = 7 (fixed), Country = 30 (fixed, capped at n_countries=30)
    assert c["continent"] == 7
    assert c["country"] == 30


def test_edge_counts_at_tiny_sf() -> None:
    ds = build_ldbc_snb_dataset(sf=_TEST_SF, seed=7)
    c = ds.counts()

    # HAS_CREATOR edges must equal their source vertex counts
    assert c["has_creator_post"] == c["post"]
    assert c["has_creator_comment"] == c["comment"]

    # IS_LOCATED edges
    assert c["is_located_person"] == c["person"]
    assert c["is_located_comment"] == c["comment"]
    assert c["is_located_post"] == c["post"]
    assert c["is_located_org"] == c["company"] + c["university"]

    # IS_PART_OF: City→Country + Country→Continent
    assert c["is_part_of"] == c["city"] + c["country"]

    # KNOWS: at least one edge per person
    assert c["knows"] >= c["person"]

    # STUDY_AT / WORK_AT ≤ person count
    assert c["study_at"] <= c["person"]
    assert c["work_at"] <= c["person"]


# ---------------------------------------------------------------------------
# Vertex attribute shape
# ---------------------------------------------------------------------------

def test_person_has_required_fields() -> None:
    ds = build_ldbc_snb_dataset(sf=_TEST_SF, seed=7)
    assert ds.persons
    p = ds.persons[0]
    for field in ("id", "firstName", "lastName", "gender", "birthday",
                  "creationDate", "locationIP", "browserUsed", "cityId"):
        assert field in p, f"Missing field: {field}"
    # birthday is YYYYMMDD int
    assert isinstance(p["birthday"], int)
    assert 1900_0000 < p["birthday"] < 2020_0000


def test_comment_fields() -> None:
    ds = build_ldbc_snb_dataset(sf=_TEST_SF, seed=7)
    assert ds.comments
    c = ds.comments[0]
    for field in ("id", "creationDate", "locationIP", "browserUsed"):
        assert field in c
    assert "content" in c
    assert "length" in c


def test_post_fields() -> None:
    ds = build_ldbc_snb_dataset(sf=_TEST_SF, seed=7)
    assert ds.posts
    p = ds.posts[0]
    for field in ("id", "creationDate", "locationIP", "browserUsed",
                  "content", "length", "language", "imageFile"):
        assert field in p


# ---------------------------------------------------------------------------
# JSONL round-trip
# ---------------------------------------------------------------------------

def test_jsonl_bundles_roundtrip(tmp_path: Path) -> None:
    ds = build_ldbc_snb_dataset(sf=_TEST_SF, seed=99)
    root = tmp_path / "jsonl"
    counts = dataset_to_jsonl_bundles(ds, root)

    assert counts["person"] == len(ds.persons)
    assert counts["comment"] == len(ds.comments)
    assert counts["post"] == len(ds.posts)

    # Re-read Person JSONL and verify first record
    person_file = root / "vertex_Person.jsonl"
    assert person_file.exists()
    with person_file.open(encoding="utf-8") as fh:
        recovered = [json.loads(line) for line in fh]
    assert len(recovered) == len(ds.persons)
    assert recovered[0]["id"] == ds.persons[0]["id"]

    # Re-read KNOWS edge
    knows_file = root / "edge_KNOWS.jsonl"
    assert knows_file.exists()
    with knows_file.open(encoding="utf-8") as fh:
        recovered_edges = [json.loads(line) for line in fh]
    assert len(recovered_edges) == len(ds.knows)


def test_jsonl_bundles_creates_expected_files(tmp_path: Path) -> None:
    ds = build_ldbc_snb_dataset(sf=_TEST_SF, seed=7)
    root = tmp_path / "jsonl"
    dataset_to_jsonl_bundles(ds, root)

    for vertex in ("Person", "Comment", "Post", "Forum", "Tag"):
        assert (root / f"vertex_{vertex}.jsonl").exists()

    for edge in ("KNOWS", "LIKES", "HAS_CREATOR_Comment", "REPLY_OF_Comment",
                 "CONTAINER_OF", "HAS_MEMBER", "IS_LOCATED_IN_Person",
                 "IS_PART_OF", "STUDY_AT", "WORK_AT"):
        assert (root / f"edge_{edge}.jsonl").exists()


# ---------------------------------------------------------------------------
# CSV round-trip
# ---------------------------------------------------------------------------

def test_csv_bundles_roundtrip(tmp_path: Path) -> None:
    ds = build_ldbc_snb_dataset(sf=_TEST_SF, seed=55)
    root = tmp_path / "csv"
    counts = dataset_to_csv_bundles(ds, root)

    assert counts["Person"] == len(ds.persons)
    assert counts["Comment"] == len(ds.comments)
    assert counts["Post"] == len(ds.posts)

    person_csv = root / "Person.csv"
    assert person_csv.exists()
    with person_csv.open(encoding="utf-8", newline="") as fh:
        reader = list(csv.DictReader(fh))
    assert len(reader) == len(ds.persons)

    knows_csv = root / "KNOWS.csv"
    assert knows_csv.exists()
    with knows_csv.open(encoding="utf-8", newline="") as fh:
        knows_rows = list(csv.DictReader(fh))
    assert len(knows_rows) == len(ds.knows)


# ---------------------------------------------------------------------------
# GeneratedLDBCSNB container
# ---------------------------------------------------------------------------

def test_counts_method() -> None:
    ds = build_ldbc_snb_dataset(sf=_TEST_SF, seed=7)
    c = ds.counts()
    assert isinstance(c, dict)
    assert "person" in c
    assert "knows" in c
    assert c["person"] == len(ds.persons)


def test_all_fields_present_in_counts() -> None:
    ds = build_ldbc_snb_dataset(sf=_TEST_SF, seed=7)
    c = ds.counts()
    expected_keys = {
        "person", "comment", "post", "forum", "tag", "tagclass",
        "place", "country", "city", "continent", "organisation",
        "company", "university",
        "knows", "likes", "likes_post",
        "has_creator_comment", "has_creator_post",
        "reply_of_comment", "reply_of_post",
        "container_of", "has_member",
        "has_tag_forum", "has_tag_comment", "has_tag_post",
        "has_interest",
        "is_located_person", "is_located_comment", "is_located_post", "is_located_org",
        "is_part_of", "study_at", "work_at",
    }
    assert set(c.keys()) == expected_keys
