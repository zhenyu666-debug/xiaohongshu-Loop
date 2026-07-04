SET execution.runtime-mode = streaming;
SET parallelism.default = 1;
-- The actual data is in 'user-behavior' topic with 2M+ messages
DROP TABLE IF EXISTS default_catalog.default_database.k_user_behavior_dwd;
CREATE TABLE default_catalog.default_database.k_user_behavior_dwd (
  user_id BIGINT,
  item_id BIGINT,
  category_id BIGINT,
  behavior_type STRING,
  ts BIGINT,
  event_time TIMESTAMP(3)
) WITH (
  'connector' = 'kafka',
  'topic' = 'user-behavior',
  'properties.bootstrap.servers' = 'kafka:29092',
  'properties.group.id' = 'flink-dwd-2026',
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
INSERT INTO `default`.user_behavior_dwd
SELECT user_id, item_id, category_id, behavior_type, event_time, DATE_FORMAT(event_time, 'yyyy-MM-dd') AS pt
FROM default_catalog.default_database.k_user_behavior_dwd
WHERE event_time IS NOT NULL;
