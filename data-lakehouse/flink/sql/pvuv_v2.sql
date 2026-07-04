SET execution.runtime-mode = streaming;
SET parallelism.default = 1;
CREATE TABLE IF NOT EXISTS default_catalog.default_database.k_user_behavior_raw3 (
  user_id BIGINT,
  item_id BIGINT,
  category_id BIGINT,
  behavior_type STRING,
  ts BIGINT,
  event_time TIMESTAMP(3),
  WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
) WITH (
  'connector' = 'kafka',
  'topic' = 'user-behavior',
  'properties.bootstrap.servers' = 'kafka:29092',
  'properties.group.id' = 'flink-consumer-pvuv-v2',
  'format' = 'json',
  'json.ignore-parse-errors' = 'true',
  'scan.startup.mode' = 'earliest-offset'
);
CREATE CATALOG iceberg_catalog WITH (
  'type' = 'iceberg',
  'catalog-type' = 'rest',
  'uri' = 'http://iceberg-rest:8181'
);
USE CATALOG iceberg_catalog;
INSERT INTO `default`.user_behavior_pvuv_1m
SELECT
  TUMBLE_START(event_time, INTERVAL '1' MINUTE) AS window_start,
  TUMBLE_END(event_time, INTERVAL '1' MINUTE) AS window_end,
  COUNT(*) AS pv,
  COUNT(DISTINCT user_id) AS uv,
  COUNT(DISTINCT CASE WHEN behavior_type = 'cart' THEN user_id END) AS cart_count,
  COUNT(DISTINCT CASE WHEN behavior_type = 'buy' THEN user_id END) AS buy_count,
  DATE_FORMAT(TUMBLE_START(event_time, INTERVAL '1' MINUTE), 'yyyy-MM-dd HH:mm') AS pt
FROM default_catalog.default_database.k_user_behavior_raw3
WHERE event_time IS NOT NULL
GROUP BY TUMBLE(event_time, INTERVAL '1' MINUTE);
