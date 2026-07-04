import duckdb, os

con = duckdb.connect(database=":memory:")

# Verify each file
files = sorted([
    ("services-2019.csv.gz", 348),
    ("services-2020.csv.gz", 355),
    ("services-2021.csv.gz", 350),
    ("services-2022.csv.gz", 356),
    ("services-2023.csv.gz", 346),
    ("services-2024.csv.gz", 357),
    ("services-2025.csv.gz", 396),
])

base = r"C:\Users\Hasee\.qclaw\workspace\get_jobs\data-lakehouse\duckdb_railway"
total_rows = 0

print("=" * 60)
print("Dutch Railway Dataset Verification")
print("=" * 60)

for fname, expected_mb in files:
    path = os.path.join(base, fname)
    sz = os.path.getsize(path) / 1e6
    pct = sz / expected_mb * 100

    # Count rows
    cnt = con.execute("""
        SELECT count(*) as cnt FROM read_csv_auto(?, compression='gzip', header=true)
    """, [path]).fetchone()[0]

    # Sample data
    sample = con.execute("""
        SELECT * FROM read_csv_auto(?, compression='gzip', header=true) LIMIT 1
    """, [path]).fetchdf()

    status = "OK" if pct > 90 else "WARN"
    print(f"[{status}] {fname:<30} {sz:5.0f}MB ({pct:.0f}%)  rows={cnt:>12,}")
    total_rows += cnt

    if fname == "services-2024.csv.gz":
        print(f"      Columns: {sample.columns.tolist()}")
        print(f"      Sample:\n{sample.to_string()}\n")

print(f"\n{'=' * 60}")
print(f"Total: {total_rows:,} rows  ({sum(os.path.getsize(os.path.join(base,f[0]))/1e9 for f in files):.2f} GB)")

con.close()
