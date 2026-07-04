SET execution.runtime-mode = streaming;

INSERT INTO iceberg_catalog.`default`.user_behavior_pvuv_1m
SELECT
    TUMBLE_START(event_time, INTERVAL '1' MINUTE) AS window_start,
    TUMBLE_END(event_time, INTERVAL '1' MINUTE) AS window_end,
    COUNT(*) AS pv,
    COUNT(DISTINCT user_id) AS uv,
    COUNT(DISTINCT CASE WHEN behavior_type = 'cart' THEN user_id END) AS cart_count,
    COUNT(DISTINCT CASE WHEN behavior_type = 'buy' THEN user_id END) AS buy_count,
    DATE_FORMAT(TUMBLE_START(event_time, INTERVAL '1' MINUTE), 'yyyy-MM-dd HH:mm') AS pt
FROM k_user_behavior_raw
WHERE event_time IS NOT NULL
GROUP BY TUMBLE(event_time, INTERVAL '1' MINUTE);
