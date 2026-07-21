#!/usr/bin/env python3
"""Test DuckDB SF10 connectivity and query speed."""
import duckdb
import time

print("DuckDB version:", duckdb.__version__)

# Test 1: Try loading ducklake extension
print("\n[Test 1] Load ducklake extension...")
try:
    con = duckdb.connect()
    t0 = time.time()
    con.execute("LOAD ducklake")
    print(f"  OK in {time.time()-t0:.1f}s")
except Exception as e:
    print(f"  FAILED: {e}")

# Test 2: Try attaching via https (CSV reading)
print("\n[Test 2] Try remote CSV read via https...")
SF10_PERSON_CSV = "https://datasets.ldbcouncil.org/snb-interactive-v1/social_network-sf10-CsvBasic-LongDateFormatter/csv/composite-merged-fk/person_0_0.csv"
try:
    con2 = duckdb.connect()
    t0 = time.time()
    result = con2.execute(f"SELECT COUNT(*) FROM read_csv_auto('{SF10_PERSON_CSV}')").fetchone()
    print(f"  OK: {result[0]} rows in {time.time()-t0:.1f}s")
except Exception as e:
    print(f"  FAILED: {e}")

# Test 3: Try DuckLake remote attach with migration
print("\n[Test 3] Try DuckLake remote attach with migration...")
try:
    con3 = duckdb.connect()
    t0 = time.time()
    con3.execute(
        "ATTACH 'ducklake:https://datasets.ldbcouncil.org/snb-interactive-v1-ducklake/sf10.ducklake' "
        "AS snb (AUTOMATIC_MIGRATION TRUE)"
    )
    tables = con3.execute("SHOW TABLES FROM snb").fetchall()
    print(f"  OK in {time.time()-t0:.1f}s: {len(tables)} tables")
    for t in tables[:5]:
        print(f"    - {t[0]}")
    # Quick query
    count = con3.execute("SELECT COUNT(*) FROM snb.person").fetchone()
    print(f"  person table: {count[0]} rows")
except Exception as e:
    print(f"  FAILED: {e}")
