SET execution.runtime-mode = streaming;
SET parallelism.default = 1;
CREATE CATALOG iceberg_catalog WITH (
  'type' = 'iceberg',
  'catalog-type' = 'rest',
  'uri' = 'http://iceberg-rest:8181',
  'warehouse' = 's3a://warehouse/',
  'io-impl' = 'org.apache.iceberg.hadoop.HadoopFileIO'
);
USE CATALOG iceberg_catalog;
CREATE DATABASE IF NOT EXISTS lake;
CREATE TABLE IF NOT EXISTS lake.user_behavior_dwd (
  user_id BIGINT,
  item_id BIGINT,
  category_id BIGINT,
  behavior_type STRING,
  event_time TIMESTAMP(3),
  pt STRING
);
CREATE TABLE IF NOT EXISTS lake.user_behavior_pvuv_1m (
  window_start TIMESTAMP(3),
  window_end TIMESTAMP(3),
  pv BIGINT,
  uv BIGINT,
  cart_count BIGINT,
  buy_count BIGINT,
  pt STRING
);
CREATE TABLE IF NOT EXISTS lake.item_hot_1h (
  window_start TIMESTAMP(3),
  window_end TIMESTAMP(3),
  item_id BIGINT,
  pv BIGINT,
  cart_count BIGINT,
  buy_count BIGINT,
  category_id BIGINT,
  pt STRING
);
