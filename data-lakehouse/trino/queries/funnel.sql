-- ============================================================
-- funnel.sql
-- Trino 查询：用户行为转化漏斗分析
-- ============================================================

-- 方法一：基于用户维度的漏斗（同一用户对同一商品的操作序列）
WITH user_item_events AS (
    SELECT
        user_id,
        item_id,
        event_time,
        behavior_type,
        ROW_NUMBER() OVER (
            PARTITION BY user_id, item_id
            ORDER BY event_time
        ) AS step_num
    FROM iceberg_catalog.default.user_behavior_dwd
    WHERE behavior_type IN ('pv', 'cart', 'fav', 'buy')
),
funnel_steps AS (
    SELECT
        user_id,
        item_id,
        MAX(CASE WHEN behavior_type = 'pv'  THEN 1 ELSE 0 END) AS has_pv,
        MAX(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END) AS has_cart,
        MAX(CASE WHEN behavior_type = 'buy'  THEN 1 ELSE 0 END) AS has_buy
    FROM user_item_events
    GROUP BY user_id, item_id
),
funnel_counts AS (
    SELECT
        COUNT(*) AS total,
        SUM(has_pv) AS pv_users,
        SUM(has_cart) AS cart_users,
        SUM(has_buy) AS buy_users
    FROM funnel_steps
)
SELECT
    total                          AS item_interactions,
    pv_users                       AS step1_pv,
    cart_users                     AS step2_cart,
    buy_users                      AS step3_buy,
    ROUND(pv_to_cart_rate, 2)     AS pv_to_cart_pct,
    ROUND(cart_to_buy_rate, 2)     AS cart_to_buy_pct,
    ROUND(pv_to_buy_rate, 2)      AS pv_to_buy_pct
FROM (
    SELECT
        total,
        pv_users,
        cart_users,
        buy_users,
        ROUND(cart_users * 100.0 / NULLIF(pv_users, 0), 2)   AS pv_to_cart_rate,
        ROUND(buy_users  * 100.0 / NULLIF(cart_users, 0), 2)  AS cart_to_buy_rate,
        ROUND(buy_users  * 100.0 / NULLIF(pv_users, 0), 2)   AS pv_to_buy_rate
    FROM funnel_counts
);

-- 方法二：基于时间窗口的天级漏斗
SELECT
    DATE(event_time)                AS dt,
    COUNT(DISTINCT user_id) FILTER (WHERE behavior_type = 'pv')   AS pv_uv,
    COUNT(DISTINCT user_id) FILTER (WHERE behavior_type = 'cart') AS cart_uv,
    COUNT(DISTINCT user_id) FILTER (WHERE behavior_type = 'buy')  AS buy_uv,
    COUNT(DISTINCT user_id) FILTER (WHERE behavior_type = 'fav')  AS fav_uv,
    ROUND(
        COUNT(DISTINCT user_id) FILTER (WHERE behavior_type = 'cart') * 100.0 /
        NULLIF(COUNT(DISTINCT user_id) FILTER (WHERE behavior_type = 'pv'), 0),
        2
    ) AS pv_to_cart_rate,
    ROUND(
        COUNT(DISTINCT user_id) FILTER (WHERE behavior_type = 'buy') * 100.0 /
        NULLIF(COUNT(DISTINCT user_id) FILTER (WHERE behavior_type = 'pv'), 0),
        2
    ) AS pv_to_buy_rate
FROM iceberg_catalog.default.user_behavior_dwd
GROUP BY DATE(event_time)
ORDER BY dt;

-- 收藏转化分析（收藏后是否购买）
WITH fav_actions AS (
    SELECT user_id, item_id, MIN(event_time) AS fav_time
    FROM iceberg_catalog.default.user_behavior_dwd
    WHERE behavior_type = 'fav'
    GROUP BY user_id, item_id
),
buy_actions AS (
    SELECT user_id, item_id, MIN(event_time) AS buy_time
    FROM iceberg_catalog.default.user_behavior_dwd
    WHERE behavior_type = 'buy'
    GROUP BY user_id, item_id
)
SELECT
    COUNT(*)                          AS total_fav,
    COUNT(CASE WHEN b.user_id IS NOT NULL THEN 1 END) AS fav_converted,
    ROUND(
        COUNT(CASE WHEN b.user_id IS NOT NULL THEN 1 END) * 100.0 / COUNT(*),
        2
    ) AS fav_to_buy_rate
FROM fav_actions a
LEFT JOIN buy_actions b
    ON a.user_id = b.user_id
    AND a.item_id = b.item_id
    AND b.buy_time > a.fav_time;
