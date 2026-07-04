-- ============================================================
-- pv_uv.sql
-- Trino 查询：PV/UV/DAU/WAU/MAU 分析
-- ============================================================

-- 每日 PV/UV 统计
SELECT
    DATE(event_time) AS dt,
    COUNT(*)            AS pv,
    COUNT(DISTINCT user_id) AS uv,
    ROUND(COUNT(*) / COUNT(DISTINCT user_id), 2) AS avg_pv_per_user
FROM iceberg_catalog.default.user_behavior_dwd
GROUP BY DATE(event_time)
ORDER BY dt;

-- 每小时 PV 趋势
SELECT
    DATE(event_time)                    AS dt,
    HOUR(event_time)                    AS hour,
    COUNT(*)                            AS pv,
    COUNT(DISTINCT user_id)             AS uv
FROM iceberg_catalog.default.user_behavior_dwd
GROUP BY DATE(event_time), HOUR(event_time)
ORDER BY dt, hour;

-- 5 分钟滚动 PV/UV（接入实时 Flink 聚合表）
SELECT
    window_start,
    window_end,
    pv,
    uv,
    cart_count,
    buy_count,
    ROUND(buy_count * 100.0 / NULLIF(pv, 0), 2) AS buy_rate,
    ROUND(cart_count * 100.0 / NULLIF(pv, 0), 2) AS cart_rate
FROM iceberg_catalog.default.user_behavior_pvuv_1m
WHERE pt = DATE_FORMAT(NOW(), 'yyyy-MM-dd')
ORDER BY window_start;

-- DAU / WAU / MAU
WITH daily_users AS (
    SELECT
        DATE(event_time) AS dt,
        user_id
    FROM iceberg_catalog.default.user_behavior_dwd
    GROUP BY DATE(event_time), user_id
)
SELECT
    (SELECT COUNT(DISTINCT user_id) FROM daily_users
     WHERE dt = CURRENT_DATE - INTERVAL '1' DAY)  AS dau,
    (SELECT COUNT(DISTINCT user_id) FROM daily_users
     WHERE dt >= CURRENT_DATE - INTERVAL '7' DAY)  AS wau,
    (SELECT COUNT(DISTINCT user_id) FROM daily_users
     WHERE dt >= CURRENT_DATE - INTERVAL '30' DAY) AS mau;
