-- ============================================================
-- 04_analytics.sql
-- 实时窗口聚合作业：PV/UV + 商品 TopN + 转化漏斗
-- ============================================================

-- 启用 Checkpoint
SET 'execution.checkpointing.interval' = '30 s';
SET 'state.backend' = 'rocksdb';

-- ── 1. 分钟级 PV/UV 实时聚合 ────────────────────────────────
CREATE TEMPORARY VIEW pvuv_1m AS
SELECT
    TUMBLE_START(event_time, INTERVAL '1' MINUTE) AS window_start,
    TUMBLE_END(event_time, INTERVAL '1' MINUTE)   AS window_end,
    COUNT(*)                                       AS pv,
    COUNT(DISTINCT user_id)                       AS uv,
    SUM(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END) AS cart_count,
    SUM(CASE WHEN behavior_type = 'buy'  THEN 1 ELSE 0 END) AS buy_count,
    CAST(DATE_FORMAT(
        TUMBLE_START(event_time, INTERVAL '1' MINUTE),
        'yyyy-MM-dd'
    ) AS STRING) AS pt
FROM watermarked
GROUP BY
    TUMBLE(event_time, INTERVAL '1' MINUTE);

-- 写入 Iceberg PV/UV 表
INSERT INTO user_behavior_pvuv_1m
SELECT * FROM pvuv_1m;

-- ── 2. 小时级商品热度 TopN ─────────────────────────────────
CREATE TEMPORARY VIEW item_hot_raw AS
SELECT
    HOP_START(event_time, INTERVAL '5' MINUTE, INTERVAL '1' HOUR) AS window_start,
    HOP_END(event_time, INTERVAL '5' MINUTE, INTERVAL '1' HOUR)   AS window_end,
    item_id,
    COUNT(*) FILTER (WHERE behavior_type = 'pv')   AS pv,
    COUNT(*) FILTER (WHERE behavior_type = 'cart')  AS cart_count,
    COUNT(*) FILTER (WHERE behavior_type = 'buy')  AS buy_count,
    category_id,
    CAST(DATE_FORMAT(
        HOP_START(event_time, INTERVAL '5' MINUTE, INTERVAL '1' HOUR),
        'yyyy-MM-dd'
    ) AS STRING) AS pt
FROM watermarked
GROUP BY
    HOP(event_time, INTERVAL '5' MINUTE, INTERVAL '1' HOUR),
    item_id,
    category_id;

INSERT INTO item_hot_1h
SELECT * FROM item_hot_raw;

-- ── 3. SESSION 窗口：用户行为序列 + 转化漏斗 ────────────────
-- 漏斗定义：用户从 pv -> cart -> buy 的转化路径
CREATE TEMPORARY VIEW funnel_session AS
SELECT
    user_id,
    SESSION_START(event_time, INTERVAL '30' MINUTE) AS session_start,
    SESSION_END(event_time, INTERVAL '30' MINUTE)   AS session_end,
    COUNT(*) FILTER (WHERE behavior_type = 'pv')   AS pv_cnt,
    COUNT(*) FILTER (WHERE behavior_type = 'cart') AS cart_cnt,
    COUNT(*) FILTER (WHERE behavior_type = 'buy')  AS buy_cnt,
    MAX(CAST(behavior_type = 'pv'   AND ROW_NUMBER() OVER (
        PARTITION BY user_id ORDER BY event_time ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    ) = 1 AS INT))  AS has_pv,
    MAX(CAST(behavior_type = 'cart' AND ROW_NUMBER() OVER (
        PARTITION BY user_id ORDER BY event_time ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    ) = 1 AS INT))  AS has_cart,
    MAX(CAST(behavior_type = 'buy'  AND ROW_NUMBER() OVER (
        PARTITION BY user_id ORDER BY event_time ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    ) = 1 AS INT))  AS has_buy
FROM watermarked
WHERE behavior_type IN ('pv', 'cart', 'buy')
GROUP BY
    user_id,
    SESSION(event_time, INTERVAL '30' MINUTE);

-- 输出转化漏斗统计（每 5 分钟输出一次）
CREATE TEMPORARY VIEW funnel_stats AS
SELECT
    TUMBLE_START(session_start, INTERVAL '5' MINUTE) AS window_start,
    COUNT(*) AS total_sessions,
    SUM(CASE WHEN pv_cnt   > 0 THEN 1 ELSE 0 END) AS pv_sessions,
    SUM(CASE WHEN cart_cnt > 0 THEN 1 ELSE 0 END) AS cart_sessions,
    SUM(CASE WHEN buy_cnt  > 0 THEN 1 ELSE 0 END) AS buy_sessions,
    ROUND(SUM(CASE WHEN cart_cnt > 0 THEN 1 ELSE 0 END) * 100.0 /
          NULLIF(SUM(CASE WHEN pv_cnt > 0 THEN 1 ELSE 0 END), 0), 2) AS pv_to_cart_rate,
    ROUND(SUM(CASE WHEN buy_cnt > 0 THEN 1 ELSE 0 END) * 100.0 /
          NULLIF(SUM(CASE WHEN cart_cnt > 0 THEN 1 ELSE 0 END), 0), 2) AS cart_to_buy_rate,
    ROUND(SUM(CASE WHEN buy_cnt > 0 THEN 1 ELSE 0 END) * 100.0 /
          NULLIF(SUM(CASE WHEN pv_cnt > 0 THEN 1 ELSE 0 END), 0), 2) AS pv_to_buy_rate
FROM funnel_session
GROUP BY
    TUMBLE(session_start, INTERVAL '5' MINUTE);

SELECT * FROM funnel_stats;

-- ── 4. 实时 DAU 统计 ────────────────────────────────────────
CREATE TEMPORARY VIEW dau_stats AS
SELECT
    CAST(DATE_FORMAT(event_time, 'yyyy-MM-dd') AS STRING) AS pt,
    COUNT(DISTINCT user_id) AS dau
FROM watermarked
GROUP BY
    CAST(DATE_FORMAT(event_time, 'yyyy-MM-dd') AS STRING);

SELECT * FROM dau_stats;
