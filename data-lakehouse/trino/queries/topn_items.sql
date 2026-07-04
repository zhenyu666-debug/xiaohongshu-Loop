-- ============================================================
-- topn_items.sql
-- Trino 查询：商品/类目 Top N 分析
-- ============================================================

-- 商品点击 Top 20
SELECT
    item_id,
    category_id,
    COUNT(*) FILTER (WHERE behavior_type = 'pv')   AS pv,
    COUNT(*) FILTER (WHERE behavior_type = 'cart') AS cart,
    COUNT(*) FILTER (WHERE behavior_type = 'buy')  AS buy,
    COUNT(DISTINCT user_id) FILTER (WHERE behavior_type = 'pv') AS uv,
    ROUND(COUNT(*) FILTER (WHERE behavior_type = 'buy') * 100.0 /
          NULLIF(COUNT(*) FILTER (WHERE behavior_type = 'pv'), 0), 2) AS buy_rate
FROM iceberg_catalog.default.user_behavior_dwd
WHERE behavior_type IN ('pv', 'cart', 'buy')
GROUP BY item_id, category_id
ORDER BY pv DESC
LIMIT 20;

-- 商品购买 Top 20
SELECT
    item_id,
    category_id,
    COUNT(*) FILTER (WHERE behavior_type = 'buy') AS buy_count,
    COUNT(DISTINCT user_id) FILTER (WHERE behavior_type = 'buy') AS buyer_count,
    COUNT(DISTINCT user_id) FILTER (WHERE behavior_type = 'pv') AS pv_uv
FROM iceberg_catalog.default.user_behavior_dwd
GROUP BY item_id, category_id
HAVING COUNT(*) FILTER (WHERE behavior_type = 'buy') > 0
ORDER BY buy_count DESC
LIMIT 20;

-- 类目成交 Top 20
SELECT
    category_id,
    COUNT(*) FILTER (WHERE behavior_type = 'buy') AS buy_count,
    COUNT(DISTINCT user_id) FILTER (WHERE behavior_type = 'buy') AS buyer_count,
    COUNT(DISTINCT item_id) FILTER (WHERE behavior_type = 'pv')  AS item_count,
    COUNT(*) FILTER (WHERE behavior_type = 'pv') AS pv
FROM iceberg_catalog.default.user_behavior_dwd
GROUP BY category_id
HAVING COUNT(*) FILTER (WHERE behavior_type = 'buy') > 0
ORDER BY buy_count DESC
LIMIT 20;

-- 加购未购买商品（潜在流失分析）
WITH cart_items AS (
    SELECT user_id, item_id, MAX(event_time) AS cart_time
    FROM iceberg_catalog.default.user_behavior_dwd
    WHERE behavior_type = 'cart'
    GROUP BY user_id, item_id
),
buy_items AS (
    SELECT user_id, item_id, MIN(event_time) AS buy_time
    FROM iceberg_catalog.default.user_behavior_dwd
    WHERE behavior_type = 'buy'
    GROUP BY user_id, item_id
)
SELECT
    c.item_id,
    COUNT(DISTINCT c.user_id) AS cart_users,
    COUNT(DISTINCT b.user_id) AS buy_users,
    ROUND(COUNT(DISTINCT b.user_id) * 100.0 / NULLIF(COUNT(DISTINCT c.user_id), 0), 2) AS cart_to_buy_rate
FROM cart_items c
LEFT JOIN buy_items b
    ON c.user_id = b.user_id
    AND c.item_id = b.item_id
GROUP BY c.item_id
HAVING COUNT(DISTINCT b.user_id) > 0
ORDER BY cart_users DESC
LIMIT 20;
