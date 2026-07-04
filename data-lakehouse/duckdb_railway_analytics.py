"""
Dutch Railway - DuckDB Lakehouse Analysis
"""
import duckdb, time

BASE = r"C:/Users/Hasee/.qclaw/workspace/get_jobs/data-lakehouse/duckdb_railway"

con = duckdb.connect(":memory:")

# 创建各年份视图（统一列名）
common_cols = [
    "Service:RDT-ID", "Service:Date", "Service:Type", "Service:Company",
    "Service:Train number", "Service:Completely cancelled", "Service:Partly cancelled",
    "Service:Maximum delay", "Stop:RDT-ID", "Stop:Station code", "Stop:Station name",
    "Stop:Arrival time", "Stop:Arrival delay", "Stop:Arrival cancelled",
    "Stop:Departure time", "Stop:Departure delay", "Stop:Departure cancelled",
]
quoted = [f'"{c}"' for c in common_cols]
select_common = "SELECT " + ", ".join(quoted)

for y in range(2019, 2026):
    path = f"{BASE}/services-{y}.csv.gz"
    sql = f"CREATE VIEW v{y} AS {select_common} FROM read_csv_auto('{path}', compression='gzip', header=true)"
    con.execute(sql)

# 验证视图行数
t0 = time.time()
total = 0
for y in range(2019, 2026):
    cnt = con.execute(f"SELECT count(*) FROM v{y}").fetchone()[0]
    total += cnt
    print(f"  v{y}: {cnt:,} rows")
print(f"Total: {total:,} rows  (registered in {time.time()-t0:.1f}s)\n")

def run(label, sql):
    print(f"\n{'=' * 60}")
    print(f"  {label}")
    print(f"{'=' * 60}")
    t0 = time.time()
    df = con.execute(sql).fetchdf()
    print(df.to_string(index=False))
    print(f"[{time.time()-t0:.1f}s]")

UNION_VIEW = " UNION all ".join([f"SELECT * FROM v{y}" for y in range(2019, 2026)])

print("=" * 60)
print("Dutch Railway - Lakehouse SQL Analysis")
print("=" * 60)

# Q1: 每年数据量
run("Q1: 每年列车停靠记录", f"""
    WITH all_data AS ({UNION_VIEW})
    SELECT
        strftime('%Y', "Service:Date") AS year,
        COUNT(*) AS total_stops,
        COUNT(DISTINCT "Service:Train number") AS unique_trains,
        ROUND(COUNT(*) * 1.0 / 365, 0) AS avg_daily_stops
    FROM all_data
    GROUP BY 1 ORDER BY 1
""")

# Q2: 延误趋势
run("Q2: 平均延误时间 by 年份", f"""
    WITH all_data AS ({UNION_VIEW})
    SELECT
        strftime('%Y', "Service:Date") AS year,
        COUNT(*) AS total_stops,
        COUNT(*) FILTER (WHERE "Stop:Arrival delay" IS NOT NULL) AS with_delay_data,
        ROUND(AVG("Stop:Arrival delay"), 1) AS avg_arrival_delay_min,
        ROUND(AVG("Stop:Departure delay"), 1) AS avg_departure_delay_min,
        MAX("Stop:Arrival delay") AS max_arrival_delay
    FROM all_data
    WHERE "Stop:Arrival delay" IS NOT NULL
    GROUP BY 1 ORDER BY 1
""")

# Q3: 铁路公司
run("Q3: 各铁路公司延误对比", f"""
    WITH all_data AS ({UNION_VIEW})
    SELECT
        "Service:Company" AS company,
        COUNT(*) AS total_stops,
        ROUND(AVG("Stop:Arrival delay"), 2) AS avg_delay_min,
        ROUND(COUNT(*) FILTER (WHERE "Stop:Arrival delay" > 5) * 100.0 / COUNT(*), 2) AS pct_over_5min,
        ROUND(COUNT(*) FILTER (WHERE "Stop:Arrival delay" > 30) * 100.0 / COUNT(*), 2) AS pct_over_30min
    FROM all_data
    WHERE "Stop:Arrival delay" IS NOT NULL
    GROUP BY 1 ORDER BY total_stops DESC
""")

# Q4: 列车类型
run("Q4: 列车类型延误对比", f"""
    WITH all_data AS ({UNION_VIEW})
    SELECT
        "Service:Type" AS train_type,
        COUNT(*) AS total_stops,
        ROUND(AVG("Stop:Arrival delay"), 2) AS avg_delay_min,
        MAX("Stop:Arrival delay") AS max_delay_min,
        ROUND(COUNT(*) FILTER (WHERE "Stop:Arrival delay" > 10) * 100.0 / COUNT(*), 2) AS delay_rate_pct
    FROM all_data
    WHERE "Stop:Arrival delay" IS NOT NULL
    GROUP BY 1 ORDER BY delay_rate_pct DESC
""")

# Q5: 取消率
run("Q5: 取消率统计（按年）", f"""
    WITH all_data AS ({UNION_VIEW})
    SELECT
        strftime('%Y', "Service:Date") AS year,
        COUNT(*) AS total_stops,
        COUNT(*) FILTER (WHERE "Stop:Arrival cancelled" = TRUE) AS arrivals_cancelled,
        ROUND(COUNT(*) FILTER (WHERE "Stop:Arrival cancelled" = TRUE) * 100.0 / COUNT(*), 3) AS arrival_cancel_pct,
        ROUND(COUNT(*) FILTER (WHERE "Service:Completely cancelled" = TRUE) * 100.0 /
              COUNT(DISTINCT "Service:RDT-ID"), 3) AS service_cancel_pct
    FROM all_data
    GROUP BY 1 ORDER BY 1
""")

# Q6: TOP 延误车站
run("Q6: TOP 20 最延误车站", f"""
    WITH all_data AS ({UNION_VIEW})
    SELECT
        "Stop:Station name" AS station,
        "Stop:Station code" AS code,
        COUNT(*) AS stops,
        ROUND(AVG("Stop:Arrival delay"), 2) AS avg_delay_min,
        MAX("Stop:Arrival delay") AS max_delay_min,
        ROUND(COUNT(*) FILTER (WHERE "Stop:Arrival delay" > 10) * 100.0 / COUNT(*), 1) AS delay_rate_pct
    FROM all_data
    WHERE "Stop:Arrival delay" IS NOT NULL
    GROUP BY 1, 2
    ORDER BY avg_delay_min DESC
    LIMIT 20
""")

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
