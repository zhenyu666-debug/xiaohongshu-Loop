"""
Dutch Railway - DuckDB Lakehouse Analysis
将 CSV.gz 导入 DuckDB 表（Parquet 格式），加速后续查询
"""
import duckdb, time, os

BASE = r"C:/Users/Hasee/.qclaw/workspace/get_jobs/data-lakehouse/duckdb_railway"
DB = r"C:/Users/Hasee/.qclaw/workspace/get_jobs/data-lakehouse/railway.db"

con = duckdb.connect(DB)

# 创建表（如果不存在）
con.execute("""
    CREATE TABLE IF NOT EXISTS railway (
        "Service:RDT-ID" BIGINT,
        "Service:Date" DATE,
        "Service:Type" VARCHAR,
        "Service:Company" VARCHAR,
        "Service:Train number" INTEGER,
        "Service:Completely cancelled" BOOLEAN,
        "Service:Partly cancelled" BOOLEAN,
        "Service:Maximum delay" INTEGER,
        "Stop:RDT-ID" BIGINT,
        "Stop:Station code" VARCHAR,
        "Stop:Station name" VARCHAR,
        "Stop:Arrival time" TIMESTAMP,
        "Stop:Arrival delay" INTEGER,
        "Stop:Arrival cancelled" BOOLEAN,
        "Stop:Departure time" TIMESTAMP,
        "Stop:Departure delay" INTEGER,
        "Stop:Departure cancelled" BOOLEAN
    )
""")

# 导入每年数据（COPY FROM SELECT）
years = list(range(2019, 2026))
for y in years:
    path = f"{BASE}/services-{y}.csv.gz"
    t0 = time.time()
    cnt = con.execute(f"""
        COPY (
            SELECT * FROM read_csv_auto('{path}', compression='gzip', header=true)
        ) TO '{BASE}/services-{y}.parquet' (FORMAT PARQUET)
    """).fetchone()[0]
    elapsed = time.time() - t0
    print(f"[{y}] parquet created: {cnt:,} rows in {elapsed:.1f}s")

con.close()
print("\nDone! Parquet files ready for fast queries.")
