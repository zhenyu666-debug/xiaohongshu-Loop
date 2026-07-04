-- Step 2: Streaming INSERT jobs
SET 'execution.checkpointing.interval' = '30 s';
SET 'state.backend' = 'hashmap';

INSERT INTO iceberg_catalog.lake.user_behavior_dwd
SELECT
    user_id,
    item_id,
    category_id,
    behavior_type,
    event_time,
    pt
FROM watermarked;

INSERT INTO iceberg_catalog.lake.user_behavior_pvuv_1m
SELECT
    TUMBLE_START(event_time, INTERVAL '1' MINUTE) AS window_start,
    TUMBLE_END(event_time, INTERVAL '1' MINUTE)   AS window_end,
    COUNT(*)                                       AS pv,
    COUNT(DISTINCT user_id)                        AS uv,
    SUM(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END) AS cart_count,
    SUM(CASE WHEN behavior_type = 'buy'  THEN 1 ELSE 0 END) AS buy_count,
    CAST(DATE_FORMAT(TUMBLE_START(event_time, INTERVAL '1' MINUTE), 'yyyy-MM-dd') AS STRING) AS pt
FROM watermarked
GROUP BY TUMBLE(event_time, INTERVAL '1' MINUTE);

INSERT INTO iceberg_catalog.lake.item_hot_1h
SELECT
    HOP_START(event_time, INTERVAL '5' MINUTE, INTERVAL '1' HOUR) AS window_start,
    HOP_END(event_time, INTERVAL '5' MINUTE, INTERVAL '1' HOUR)   AS window_end,
    item_id,
    COUNT(*) FILTER (WHERE behavior_type = 'pv')   AS pv,
    COUNT(*) FILTER (WHERE behavior_type = 'cart') AS cart_count,
    COUNT(*) FILTER (WHERE behavior_type = 'buy')  AS buy_count,
    category_id,
    CAST(DATE_FORMAT(HOP_START(event_time, INTERVAL '5' MINUTE, INTERVAL '1' HOUR), 'yyyy-MM-dd') AS STRING) AS pt
FROM watermarked
GROUP BY
    HOP(event_time, INTERVAL '5' MINUTE, INTERVAL '1' HOUR),
    item_id,
    category_id;
