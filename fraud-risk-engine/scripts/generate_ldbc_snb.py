#!/usr/bin/env python3
# =============================================================================
# generate_ldbc_snb.py
#
# Generate synthetic LDBC SNB (Social Network Benchmark) data using the
# deterministic generator from fraud_risk_engine.app.loader.ldbc_snb_loader.
#
# Usage:
#   python generate_ldbc_snb.py --sf 1 --seed 42 --format both
#   python generate_ldbc_snb.py --sf 0.1                    # quick test
#   python generate_ldbc_snb.py --sf 10 --force            # overwrite existing
#   python generate_ldbc_snb.py --sf 1 --validate         # run validation
#
# Output:
#   data/ldbc_snb/sf{sf}/
#     vertex_*.jsonl / vertex_*.csv   (13 vertex types)
#     edge_*.jsonl   / edge_*.csv     (20 edge types)
#
# =============================================================================

from __future__ import annotations

import argparse
import csv
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import TextIO

# Add project root to path for imports
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_PROJECT_ROOT))

from app.loader.ldbc_snb_loader import (
    GeneratedLDBCSNB,
    build_ldbc_snb_dataset,
    dataset_to_csv_bundles,
    dataset_to_jsonl_bundles,
)
from app.schema.ldbc_snb_schema import scale_factor, edge_count_estimates


# =============================================================================
# Constants
# =============================================================================

SUPPORTED_SCALE_FACTORS = [0.1, 0.3, 1, 3, 10, 30]
DEFAULT_SCALE_FACTOR = 0.1
DEFAULT_SEED = 42
DEFAULT_FORMAT = "jsonl"  # jsonl, csv, both

# Expected counts at SF1 (for validation)
SF1_BASELINE = {
    "person": 3904,
    "post": 499_968,
    "comment": 2_498_528,
    "forum": 9_985,
    "tag": 160,  # reduced from 16088 for brevity
}


# =============================================================================
# CLI
# =============================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="generate_ldbc_snb",
        description="Generate synthetic LDBC SNB benchmark data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s --sf 1 --seed 42 --format both
  %(prog)s --sf 0.1              # quick test
  %(prog)s --sf 10 --force       # overwrite existing
  %(prog)s --sf 1 --validate     # run validation checks
        """,
    )

    parser.add_argument(
        "--sf",
        type=float,
        default=DEFAULT_SCALE_FACTOR,
        choices=SUPPORTED_SCALE_FACTORS,
        help=f"Scale factor (default: {DEFAULT_SCALE_FACTOR})",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=DEFAULT_SEED,
        help=f"Random seed for reproducibility (default: {DEFAULT_SEED})",
    )
    parser.add_argument(
        "--format",
        type=str,
        default=DEFAULT_FORMAT,
        choices=["jsonl", "csv", "both"],
        help="Output format (default: jsonl)",
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output directory (default: data/ldbc_snb/sf{sf}/)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing data without prompting",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        help="Validate vertex/edge counts after generation",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress progress output",
    )

    return parser.parse_args()


# =============================================================================
# Progress reporting
# =============================================================================

class ProgressReporter:
    def __init__(self, quiet: bool = False):
        self.quiet = quiet
        self._start_time = time.time()
        self._last_update = 0

    def log(self, msg: str, level: str = "INFO") -> None:
        if not self.quiet:
            elapsed = time.time() - self._start_time
            print(f"[{elapsed:6.2f}s] [{level}] {msg}", flush=True)

    def step(self, msg: str) -> None:
        self.log(msg, "STEP")

    def warn(self, msg: str) -> None:
        self.log(msg, "WARN")

    def error(self, msg: str) -> None:
        self.log(msg, "ERROR")

    def done(self, msg: str) -> None:
        self.log(msg, "DONE")


# =============================================================================
# Output helpers
# =============================================================================

def _write_jsonl(path: Path, rows: list[dict]) -> int:
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


# =============================================================================
# Dataset export
# =============================================================================

def export_dataset(
    ds: GeneratedLDBCSNB,
    root: Path,
    formats: list[str],
    reporter: ProgressReporter,
) -> dict[str, int]:
    """Write dataset to disk in specified format(s)."""
    total_counts: dict[str, int] = {}

    # Vertex types
    vertex_types = [
        ("Person", ds.persons),
        ("Comment", ds.comments),
        ("Post", ds.posts),
        ("Forum", ds.forums),
        ("Tag", ds.tags),
        ("TagClass", ds.tagclasses),
        ("Place", ds.places),
        ("Country", ds.countries),
        ("City", ds.cities),
        ("Continent", ds.continents),
        ("Organisation", ds.organisations),
        ("Company", ds.companies),
        ("University", ds.universities),
    ]

    # Edge types
    edge_types = [
        ("KNOWS", ds.knows),
        ("LIKES", ds.likes),
        ("LIKES_Post", ds.likes_post),
        ("HAS_CREATOR_Comment", ds.has_creator_comment),
        ("HAS_CREATOR_Post", ds.has_creator_post),
        ("REPLY_OF_Comment", ds.reply_of_comment),
        ("REPLY_OF_Post", ds.reply_of_post),
        ("CONTAINER_OF", ds.container_of),
        ("HAS_MEMBER", ds.has_member),
        ("HAS_TAG_Forum", ds.has_tag_forum),
        ("HAS_TAG_Comment", ds.has_tag_comment),
        ("HAS_TAG_Post", ds.has_tag_post),
        ("HAS_INTEREST", ds.has_interest),
        ("IS_LOCATED_IN_Person", ds.is_located_person),
        ("IS_LOCATED_IN_Comment", ds.is_located_comment),
        ("IS_LOCATED_IN_Post", ds.is_located_post),
        ("IS_LOCATED_IN_Org", ds.is_located_org),
        ("IS_PART_OF", ds.is_part_of),
        ("STUDY_AT", ds.study_at),
        ("WORK_AT", ds.work_at),
    ]

    # Export vertices
    reporter.step("Exporting vertices...")
    for name, rows in vertex_types:
        for fmt in formats:
            if fmt == "jsonl":
                count = _write_jsonl(root / f"vertex_{name}.jsonl", rows)
            else:
                count = _write_csv(root / f"vertex_{name}.csv", rows)
            total_counts[f"vertex_{name.lower()}"] = count

    # Export edges
    reporter.step("Exporting edges...")
    for name, rows in edge_types:
        for fmt in formats:
            if fmt == "jsonl":
                count = _write_jsonl(root / f"edge_{name}.jsonl", rows)
            else:
                count = _write_csv(root / f"edge_{name}.csv", rows)
            key = name.lower().replace("_", "_")
            total_counts[f"edge_{key}"] = count

    return total_counts


# =============================================================================
# Validation
# =============================================================================

def validate_counts(
    ds: GeneratedLDBCSNB,
    sf: float,
    reporter: ProgressReporter,
) -> bool:
    """Validate generated dataset against expected counts."""
    reporter.step("Validating vertex/edge counts...")

    counts = ds.counts()
    expected_vertices = scale_factor(sf)
    expected_edges = edge_count_estimates(sf)

    all_ok = True

    # Check vertices
    reporter.log("Vertex validation:")
    for vertex_type, expected in expected_vertices.items():
        actual = counts.get(vertex_type, 0)
        tolerance = 0.1  # 10% tolerance

        if expected == 0:
            continue

        ratio = actual / expected if expected > 0 else 0
        if abs(1 - ratio) > tolerance:
            reporter.warn(
                f"  {vertex_type}: expected ~{expected}, got {actual} "
                f"(ratio: {ratio:.2f})"
            )
            all_ok = False
        else:
            reporter.log(f"  {vertex_type}: {actual} (expected ~{expected})")

    # Summary
    if all_ok:
        reporter.done("Validation passed!")
    else:
        reporter.warn("Validation completed with warnings (counts may vary due to generation randomness)")

    return all_ok


# =============================================================================
# Summary report
# =============================================================================

def print_summary(
    ds: GeneratedLDBCSNB,
    counts: dict[str, int],
    output_dir: Path,
    sf: float,
    formats: list[str],
    elapsed: float,
    reporter: ProgressReporter,
) -> None:
    """Print summary statistics after generation."""

    print()
    print("=" * 70)
    print("  LDBC SNB Data Generation Summary")
    print("=" * 70)
    print(f"  Scale factor : SF{sf}")
    print(f"  Output dir   : {output_dir}")
    print(f"  Format(s)    : {', '.join(formats)}")
    print(f"  Seed         : {args.seed}")
    print(f"  Elapsed time : {elapsed:.2f}s")
    print()
    print("  Vertex counts:")
    print("-" * 70)

    vertices = [
        ("person", "Person"),
        ("post", "Post"),
        ("comment", "Comment"),
        ("forum", "Forum"),
        ("tag", "Tag"),
        ("tagclass", "TagClass"),
        ("country", "Country"),
        ("city", "City"),
        ("continent", "Continent"),
        ("company", "Company"),
        ("university", "University"),
    ]

    for key, label in vertices:
        count = counts.get(f"vertex_{key}", 0)
        print(f"    {label:<15} {count:>12,}")

    print()
    print("  Edge counts:")
    print("-" * 70)

    edges = [
        ("knows", "KNOWS"),
        ("likes", "LIKES (Comment)"),
        ("likes_post", "LIKES (Post)"),
        ("has_creator_comment", "HAS_CREATOR (Comment)"),
        ("has_creator_post", "HAS_CREATOR (Post)"),
        ("reply_of_comment", "REPLY_OF (Comment)"),
        ("reply_of_post", "REPLY_OF (Post)"),
        ("container_of", "CONTAINER_OF"),
        ("has_member", "HAS_MEMBER"),
        ("has_tag_post", "HAS_TAG (Post)"),
        ("has_tag_comment", "HAS_TAG (Comment)"),
        ("has_tag_forum", "HAS_TAG (Forum)"),
        ("has_interest", "HAS_INTEREST"),
        ("is_located_person", "IS_LOCATED_IN (Person)"),
        ("is_located_post", "IS_LOCATED_IN (Post)"),
        ("is_located_comment", "IS_LOCATED_IN (Comment)"),
        ("is_located_org", "IS_LOCATED_IN (Org)"),
        ("is_part_of", "IS_PART_OF"),
        ("study_at", "STUDY_AT"),
        ("work_at", "WORK_AT"),
    ]

    for key, label in edges:
        count = counts.get(f"edge_{key}", 0)
        print(f"    {label:<25} {count:>12,}")

    print()
    print("=" * 70)

    # Calculate total edges
    vertex_total = sum(v for k, v in counts.items() if k.startswith("vertex_"))
    edge_total = sum(v for k, v in counts.items() if k.startswith("edge_"))

    print(f"  Total vertices: {vertex_total:,}")
    print(f"  Total edges   : {edge_total:,}")
    print()
    print("  Next steps:")
    print("    1. Load data into TigerGraph using app/loader/tg_loader.py")
    print("    2. Or use with local detector for fraud detection testing")
    print("    3. Run queries via app/queries/fraud_queries.py")
    print("=" * 70)


# =============================================================================
# Main
# =============================================================================

def main() -> int:
    global args
    args = parse_args()

    reporter = ProgressReporter(quiet=args.quiet)

    # Determine output directory
    if args.output:
        output_dir = Path(args.output).resolve()
    else:
        output_dir = _PROJECT_ROOT / "data" / "ldbc_snb" / f"sf{args.sf}"

    # Check if data already exists
    if output_dir.exists() and any(output_dir.iterdir()):
        if args.force:
            reporter.warn(f"Overwriting existing data in {output_dir}")
        else:
            reporter.warn(f"Data already exists in {output_dir}")
            response = input("Overwrite? [y/N] ").strip().lower()
            if response != "y":
                reporter.log("Aborted.")
                return 0

    reporter.step(f"Generating LDBC SNB data (SF{args.sf}, seed={args.seed})...")

    start_time = time.time()

    # Generate dataset
    try:
        ds = build_ldbc_snb_dataset(sf=args.sf, seed=args.seed)
        reporter.done("Dataset generated successfully")
    except Exception as e:
        reporter.error(f"Failed to generate dataset: {e}")
        return 1

    # Determine formats
    formats = ["both"] if args.format == "both" else [args.format]

    # Export to disk
    reporter.step("Exporting data to disk...")
    try:
        counts = export_dataset(ds, output_dir, formats, reporter)
        reporter.done("Data exported successfully")
    except Exception as e:
        reporter.error(f"Failed to export data: {e}")
        return 1

    # Validate if requested
    if args.validate:
        validate_counts(ds, args.sf, reporter)

    # Print summary
    elapsed = time.time() - start_time
    print_summary(ds, counts, output_dir, args.sf, formats, elapsed, reporter)

    reporter.done("Generation complete!")
    return 0


if __name__ == "__main__":
    sys.exit(main())
