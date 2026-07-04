"""
UserBehavior.csv - DuckDB SQL Lakehouse Demo
"""
import duckdb
import pandas as pd

PATH = r"C:\Users\Hasee\.qclaw\workspace\get_jobs\data-lakehouse\data\raw\UserBehavior.csv"

con = duckdb.connect(database=":memory:")

print("Loading data into DuckDB...")
con.execute(f"""
    CREATE TABLE ub AS
    SELECT
        user_id,
        item_id,
        category_id,
        behavior_type,
        to_timestamp(timestamp) AS ts,
        DATE_TRUNC('day', to_timestamp(timestamp))::DATE AS day,
        EXTRACT(HOUR FROM to_timestamp(timestamp))::INT AS hour
    FROM read_csv_auto('{PATH}')
""")
print("Done!\n")

# Helper to print query results
def qry(label, sql):
    print("=" * 60)
    print(label)
    print("=" * 60)
    df = con.execute(sql).fetchdf()
    print(df.to_string(index=False))
    print()

# Q1: 行为漏斗
qry("Q1: 行为漏斗（浏览 → 收藏 → 加购 → 购买）", """
    SELECT
        behavior_type,
        COUNT(*) AS cnt,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
    FROM ub
    GROUP BY behavior_type
    ORDER BY
        CASE behavior_type WHEN 'pv' THEN 1 WHEN 'fav' THEN 2
            WHEN 'cart' THEN 3 WHEN 'buy' THEN 4 END
""")

# Q2: 每日趋势
qry("Q2: 每日行为量趋势", """
    SELECT
        day,
        COUNT(*) AS total,
        COUNT(*) FILTER (WHERE behavior_type = 'buy') AS buy_cnt
    FROM ub
    GROUP BY day
    ORDER BY day
""")

# Q3: 每日漏斗（购买转化率趋势）
qry("Q3: 每日浏览→购买转化率", """
    SELECT
        day,
        COUNT(*) FILTER (WHERE behavior_type = 'pv') AS pv,
        COUNT(*) FILTER (WHERE behavior_type = 'buy') AS buy,
        ROUND(COUNT(*) FILTER (WHERE behavior_type = 'buy') * 100.0 /
              NULLIF(COUNT(*) FILTER (WHERE behavior_type = 'pv'), 0), 2) AS conv_rate
    FROM ub
    GROUP BY day
    ORDER BY day
""")

# Q4: 用户路径分析
qry("Q4: 用户行为路径", """
    WITH uf AS (
        SELECT user_id,
            MAX(CASE WHEN behavior_type = 'pv' THEN 1 END) AS pv,
            MAX(CASE WHEN behavior_type = 'fav' THEN 1 END) AS fav,
            MAX(CASE WHEN behavior_type = 'cart' THEN 1 END) AS cart,
            MAX(CASE WHEN behavior_type = 'buy' THEN 1 END) AS buy
        FROM ub GROUP BY user_id
    )
    SELECT path, cnt,
        ROUND(cnt * 100.0 / SUM(cnt) OVER (), 2) AS pct
    FROM (
        SELECT
            CASE
                WHEN buy=1 AND cart=1 THEN 'pv→cart→buy'
                WHEN buy=1 AND fav=1 AND cart=0 THEN 'pv→fav→buy'
                WHEN buy=1 AND fav=0 AND cart=0 THEN 'pv→buy (direct)'
                WHEN fav=1 THEN 'pv→fav (no buy)'
                WHEN cart=1 THEN 'pv→cart (no buy)'
                ELSE 'pv only'
            END AS path,
            COUNT(*) AS cnt
        FROM uf
        GROUP BY 1
    ) t
    ORDER BY cnt DESC
""")

# Q5: TOP 类别
qry("Q5: 热门购买类别 TOP 10", """
    SELECT category_id, COUNT(*) AS buy_cnt,
           COUNT(DISTINCT user_id) AS buyers
    FROM ub WHERE behavior_type = 'buy'
    GROUP BY category_id
    ORDER BY buy_cnt DESC LIMIT 10
""")

# Q6: 高价值用户
qry("Q6: 高价值用户 TOP 10", """
    SELECT user_id,
        COUNT(*) FILTER (WHERE behavior_type = 'buy') AS buy_cnt,
        COUNT(*) FILTER (WHERE behavior_type = 'pv') AS pv_cnt,
        COUNT(DISTINCT category_id) AS cat_cnt,
        COUNT(DISTINCT item_id) AS item_cnt
    FROM ub
    GROUP BY user_id
    HAVING COUNT(*) FILTER (WHERE behavior_type = 'buy') > 0
    ORDER BY buy_cnt DESC
    LIMIT 10
""")

# Q7: 用户分群（RFM 简化版）
qry("Q7: 用户分群（R=最近活跃, F=购买频次, M=购买商品数）", """
    WITH rfm AS (
        SELECT user_id,
            MAX(day) AS last_day,
            COUNT(*) FILTER (WHERE behavior_type = 'buy') AS frequency,
            COUNT(DISTINCT category_id) FILTER (WHERE behavior_type = 'buy') AS monetary
        FROM ub GROUP BY user_id
    )
    SELECT segment, COUNT(*) AS users,
        ROUND(COUNT(*) * 100.0 / SUM(COUNT(*)) OVER (), 2) AS pct
    FROM (
        SELECT user_id,
            CASE
                WHEN last_day >= '2017-12-02' AND frequency >= 3 THEN 'VIP'
                WHEN last_day >= '2017-12-01' AND frequency >= 2 THEN 'Active'
                WHEN last_day >= '2017-11-30' THEN 'Warm'
                WHEN frequency > 0 THEN 'Buyer'
                ELSE 'Cold'
            END AS segment
        FROM rfm
    ) t
    GROUP BY segment
    ORDER BY
        CASE segment
            WHEN 'VIP' THEN 1 WHEN 'Active' THEN 2
            WHEN 'Warm' THEN 3 WHEN 'Buyer' THEN 4 ELSE 5 END
""")

# Q8: 每小时购买量（峰值分析）
qry("Q8: 每小时购买量（峰值时段）", """
    SELECT hour,
        COUNT(*) FILTER (WHERE behavior_type = 'pv') AS pv,
        COUNT(*) FILTER (WHERE behavior_type = 'buy') AS buy,
        ROUND(COUNT(*) FILTER (WHERE behavior_type = 'buy') * 100.0 /
              NULLIF(COUNT(*) FILTER (WHERE behavior_type = 'pv'), 0), 2) AS conv_pct
    FROM ub
    GROUP BY hour
    ORDER BY hour
""")

con.close()
print("DuckDB SQL Lakehouse Demo 完成！")
