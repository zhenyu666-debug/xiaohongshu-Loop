-- ============================================================
-- rfm_analysis.sql
-- Trino 查询：用户 RFM 分析（Recency/Frequency/Monetary）
-- 注意：原始数据集不包含金额字段，Monetary 用购买次数代替
-- ============================================================

-- 用户购买行为聚合
WITH user_buy_stats AS (
    SELECT
        user_id,
        MAX(event_time)                                   AS last_buy_time,
        DATE('2017-12-03') - DATE(MAX(event_time))        AS recency_days,
        COUNT(*)                                          AS frequency,
        COUNT(DISTINCT item_id)                           AS unique_items
    FROM iceberg_catalog.default.user_behavior_dwd
    WHERE behavior_type = 'buy'
    GROUP BY user_id
),
-- 计算 RFM 分位数得分
rfm_scores AS (
    SELECT
        user_id,
        recency_days,
        frequency,
        unique_items AS monetary,
        -- Recency: 越小越好（最近购买），分 5 档
        CASE
            WHEN recency_days <= 1  THEN 5
            WHEN recency_days <= 2  THEN 4
            WHEN recency_days <= 3  THEN 3
            WHEN recency_days <= 5  THEN 2
            ELSE 1
        END AS r_score,
        -- Frequency: 越大越好（购买频率），分 5 档
        CASE
            WHEN frequency >= NTILE(5) OVER (ORDER BY frequency DESC) THEN 5
            WHEN frequency >= NTILE(3) OVER (ORDER BY frequency DESC) THEN 4
            WHEN frequency >= NTILE(2) OVER (ORDER BY frequency DESC) THEN 3
            ELSE 2
        END AS f_score,
        -- Monetary: 用购买商品种类数代替，分 5 档
        CASE
            WHEN unique_items >= NTILE(5) OVER (ORDER BY unique_items DESC) THEN 5
            WHEN unique_items >= NTILE(3) OVER (ORDER BY unique_items DESC) THEN 4
            WHEN unique_items >= NTILE(2) OVER (ORDER BY unique_items DESC) THEN 3
            ELSE 2
        END AS m_score
    FROM user_buy_stats
)
SELECT
    user_id,
    recency_days,
    frequency,
    monetary,
    CONCAT(r_score, f_score, m_score) AS rfm_code,
    CASE
        WHEN CONCAT(r_score, f_score, m_score) >= '444' THEN '重要价值用户'
        WHEN r_score >= 4 AND f_score >= 3 THEN '重要发展用户'
        WHEN f_score >= 4 AND r_score <= 2 THEN '重要保持用户'
        WHEN r_score <= 2 AND f_score >= 3 THEN '重要挽回用户'
        WHEN r_score >= 4 THEN '潜力用户'
        WHEN f_score >= 4 THEN '活跃用户'
        WHEN r_score <= 2 THEN '流失风险用户'
        ELSE '一般用户'
    END AS user_segment
FROM rfm_scores
ORDER BY frequency DESC, monetary DESC
LIMIT 100;

-- RFM 用户分群统计
WITH user_buy_stats AS (
    SELECT
        user_id,
        MAX(event_time)                                   AS last_buy_time,
        DATE('2017-12-03') - DATE(MAX(event_time))        AS recency_days,
        COUNT(*)                                          AS frequency,
        COUNT(DISTINCT item_id)                           AS unique_items
    FROM iceberg_catalog.default.user_behavior_dwd
    WHERE behavior_type = 'buy'
    GROUP BY user_id
)
SELECT
    CASE
        WHEN recency_days <= 1 AND frequency >= 3 THEN '高价值活跃'
        WHEN recency_days <= 3 AND frequency >= 2 THEN '高价值新客'
        WHEN recency_days <= 7 AND frequency >= 1 THEN '一般价值'
        WHEN recency_days > 7 THEN '流失用户'
        ELSE '其他'
    END AS segment,
    COUNT(*) AS user_count,
    ROUND(AVG(frequency), 2) AS avg_frequency
FROM user_buy_stats
GROUP BY 1
ORDER BY user_count DESC;
