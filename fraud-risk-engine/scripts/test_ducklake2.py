#!/usr/bin/env python3
"""Test DuckLake remote attach with read-only mode."""
import duckdb, time

con = duckdb.connect()
print("Testing DuckLake remote attach...")

# Try with custom options
t0 = time.time()
try:
    con.execute(
        "ATTACH 'ducklake:https://datasets.ldbcouncil.org/snb-interactive-v1-ducklake/sf10.ducklake' "
        "AS snb (READ_ONLY TRUE)"
    )
    tables = con.execute("SHOW TABLES FROM snb").fetchall()
    print(f"OK in {time.time()-t0:.1f}s: {len(tables)} tables")
    for t in tables:
        print(f"  - {t[0]}")
    count = con.execute("SELECT COUNT(*) FROM snb.person").fetchone()
    print(f"  person: {count[0]:,} rows")
except Exception as e:
    print(f"FAILED: {e}")
