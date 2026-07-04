import duckdb, time

BASE = r"C:/Users/Hasee/.qclaw/workspace/get_jobs/data-lakehouse/duckdb_railway"
con = duckdb.connect(database=":memory:")

# 用 CTE + UNION ALL 构造全量数据
union_sql = "\nUNION ALL\n".join([
    f"SELECT * FROM read_csv_auto('{BASE}/services-{y}.csv.gz', compression='gzip', header=true)"
    for y in range(2019, 2026)
])
railway_sql = f"WITH r AS ({union_sql})"

print("Testing row count...")
t0 = time.time()
cnt = con.execute(f"{union_sql}\nSELECT count(*) AS total FROM t", aliases={"t": union_sql}).fetchone()[0]
print(f"Total: {cnt:,}  ({time.time()-t0:.1f}s)")

con.close()
