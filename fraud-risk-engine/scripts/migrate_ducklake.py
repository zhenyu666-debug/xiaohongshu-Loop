#!/usr/bin/env python3
"""Migrate DuckLake remote catalog to local DuckDB 1.5.4 format.

Creates a local migrated copy of the DuckLake metadata, then queries the remote data.
"""
import duckdb, time, os

LOCAL_DB = "fraud-risk-engine/data/ldbc_snb/sf10_ducklake.duckdb"
REMOTE = "ducklake:https://datasets.ldbcouncil.org/snb-interactive-v1-ducklake/sf10.ducklake"

os.makedirs(os.path.dirname(LOCAL_DB), exist_ok=True)

# Step 1: Create a fresh local DuckDB database and migrate the remote catalog into it
print("[Step 1] Creating local DB and migrating DuckLake catalog...")
t0 = time.time()
con = duckdb.connect(LOCAL_DB)

try:
    con.execute(f"ATTACH '{REMOTE}' AS snb_src (AUTOMATIC_MIGRATION TRUE)")
    print(f"  Migration OK in {time.time()-t0:.1f}s")
except Exception as e:
    print(f"  Migration FAILED: {e}")
    print("  Trying alternative: create local empty ducklake and copy schema...")
    # Alternative: detach and try different approach
    try:
        con.execute("DETACH snb_src")
    except:
        pass
    con.execute(f"CREATE DUCKLAKE '{LOCAL_DB}.dlk'")
    con.execute(f"ATTACH '{REMOTE}' AS snb_src")
    # Copy tables manually
    tables = con.execute("SHOW TABLES FROM snb_src").fetchall()
    print(f"  Found {len(tables)} tables to migrate")
    raise SystemExit(1)

# Step 2: Explore the migrated catalog
print("\n[Step 2] Exploring migrated catalog...")
tables = con.execute("SHOW TABLES FROM snb_src").fetchall()
print(f"  Tables: {len(tables)}")
for t in tables:
    print(f"    - {t[0]}")

# Step 3: Run quick queries
print("\n[Step 3] Quick queries...")
queries = [
    ("SELECT COUNT(*) FROM snb_src.person", "person count"),
    ("SELECT COUNT(*) FROM snb_src.comment", "comment count"),
    ("SELECT COUNT(*) FROM snb_src.post", "post count"),
    ("SELECT COUNT(*) FROM snb_src.forum", "forum count"),
    ("SELECT COUNT(*) FROM snb_src.knows", "knows edges"),
]
for sql, label in queries:
    tq = time.time()
    try:
        r = con.execute(sql).fetchone()
        print(f"  {label}: {r[0]:>12,} rows  ({time.time()-tq:.1f}s)")
    except Exception as e:
        print(f"  {label}: ERROR - {e}")

# Step 4: Join query example (friends of a person)
print("\n[Step 4] Join example: top 5 friends by name...")
tq = time.time()
result = con.execute("""
    SELECT p.p_firstname, p.p_lastname, k.k_creationdate
    FROM snb_src.knows k
    JOIN snb_src.person p ON k.Person2 = p.p_personid
    WHERE k.Person1 = 0
    ORDER BY p.p_lastname, p.p_firstname
    LIMIT 5
""").fetchall()
print(f"  {result}")
print(f"  ({time.time()-tq:.1f}s)")

con.close()
print(f"\nLocal DuckLake DB: {LOCAL_DB}")
print("Done!")
