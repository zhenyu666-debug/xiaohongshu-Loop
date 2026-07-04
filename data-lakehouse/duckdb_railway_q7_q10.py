"""
Dutch Railway - Remaining Queries (Q7-Q10)
"""
import duckdb, time

BASE = r"C:/Users/Hasee/.qclaw/workspace/get_jobs/data-lakehouse/duckdb_railway"

con = duckdb.connect(":memory:")

common_cols = [
    "Service:RDT-ID", "Service:Date", "Service:Type", "Service:Company",
    "Service:Train number", "Service:Completely cancelled", "Service:Partly cancelled",
    "Service:Maximum delay", "Stop:RDT-ID", "Stop:Station code", "Stop:Station name",
    "Stop:Arrival time", "Stop:Arrival delay", "Stop:Arrival cancelled",
    "Stop:Departure time", "Stop:Departure delay", "Stop:Departure cancelled",
]
select_common = "SELECT " + ", ".join([f'"{c}"' for c in common_cols])

for y in range(2019, 2026):
    con.execute(f"CREATE VIEW v{y} AS {select_common} FROM read_csv_auto('{BASE}/services-{y}.csv.gz', compression='gzip', header=true)")

UNION_VIEW = " UNION ALL ".join([f"SELECT * FROM v{y}" for y in range(2019, 2026)])

def run(label, sql):
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    t0 = time.time()
    df = con.execute(sql).fetchdf()
    print(df.to_string(index=False))
    print(f"[{time.time()-t0:.1f}s]")

# Q7: 延误最严重日期
run("Q7: TOP 10 延误最严重的日期", f"""
    WITH all_data AS ({UNION_VIEW})
    SELECT
        "Service:Date" AS date,
        CASE CAST(strftime('%w', "Service:Date") AS INT)
            WHEN 0 THEN 'Sunday' WHEN 1 THEN 'Monday' WHEN 2 THEN 'Tuesday'
            WHEN 3 THEN 'Wednesday' WHEN 4 THEN 'Thursday' WHEN 5 THEN 'Friday'
            WHEN 6 THEN 'Saturday' END AS weekday,
        COUNT(*) AS total_stops,
        ROUND(AVG("Stop:Arrival delay"), 2) AS avg_delay,
        MAX("Service:Maximum delay") AS max_service_delay,
        COUNT(*) FILTER (WHERE "Stop:Arrival delay" > 30) AS delay_over_30min
    FROM all_data
    WHERE "Stop:Arrival delay" IS NOT NULL
    GROUP BY 1
    ORDER BY avg_delay DESC
    LIMIT 10
""")

# Q8: 时段分析
run("Q8: 高峰 vs 低谷时段延误", f"""
    WITH all_data AS ({UNION_VIEW})
    SELECT
        CASE
            WHEN EXTRACT(HOUR FROM "Stop:Arrival time") BETWEEN 7 AND 9 THEN 'Morning Peak (7-9)'
            WHEN EXTRACT(HOUR FROM "Stop:Arrival time") BETWEEN 17 AND 19 THEN 'Evening Peak (17-19)'
            WHEN EXTRACT(HOUR FROM "Stop:Arrival time") BETWEEN 0 AND 5 THEN 'Night (0-5)'
            ELSE 'Off-Peak'
        END AS time_period,
        COUNT(*) AS stops,
        ROUND(AVG("Stop:Arrival delay"), 2) AS avg_delay_min,
        MAX("Stop:Arrival delay") AS max_delay_min,
        ROUND(COUNT(*) FILTER (WHERE "Stop:Arrival delay" > 10) * 100.0 / COUNT(*), 2) AS delay_rate_pct
    FROM all_data
    WHERE "Stop:Arrival delay" IS NOT NULL
    GROUP BY 1 ORDER BY avg_delay_min DESC
""")

# Q9: 月度趋势
run("Q9: 月度平均延误趋势", f"""
    WITH all_data AS ({UNION_VIEW})
    SELECT
        strftime('%Y-%m', "Service:Date") AS month,
        COUNT(*) AS stops,
        ROUND(AVG("Stop:Arrival delay"), 2) AS avg_delay,
        ROUND(COUNT(*) FILTER (WHERE "Stop:Arrival delay" > 15) * 100.0 / COUNT(*), 2) AS severe_delay_pct
    FROM all_data
    WHERE "Stop:Arrival delay" IS NOT NULL
    GROUP BY 1 ORDER BY 1
""")

# Q10: 工作日 vs 周末
run("Q10: 工作日 vs 周末延误对比", f"""
    WITH all_data AS ({UNION_VIEW})
    SELECT
        CASE CAST(strftime('%w', "Service:Date") AS INT)
            WHEN 0 THEN 'Sunday' WHEN 6 THEN 'Saturday' ELSE 'Weekday' END AS day_type,
        COUNT(*) AS total_stops,
        ROUND(AVG("Stop:Arrival delay"), 2) AS avg_delay_min,
        ROUND(COUNT(*) FILTER (WHERE "Stop:Arrival delay" > 10) * 100.0 / COUNT(*), 2) AS delay_rate_pct
    FROM all_data
    WHERE "Stop:Arrival delay" IS NOT NULL
    GROUP BY 1
    ORDER BY
        CASE day_type WHEN 'Weekday' THEN 1 WHEN 'Saturday' THEN 2 ELSE 3 END
""")

con.close()
print("\n" + "=" * 60)
print("COMPLETE!")
print("=" * 60)
