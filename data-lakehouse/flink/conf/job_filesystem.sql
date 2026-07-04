-- Use Flink Filesystem connector to read MinIO CSV directly (bypass Kafka issue)
-- Then write to Iceberg
SET 'execution.runtime-mode' = 'batch';
SET 'state.backend' = 'hashmap';
SET 'parallelism.default' = '4';
SET 'execution.restart-strategy' = 'none';

-- Create MinIO/S3 catalog for reading CSV
CREATE CATALOG minio_catalog WITH (
    'type' = 'filesystem',
    'filesystem' = 's3',
    's3.endpoint' = 'http://minio:9000',
    's3.access-key' = 'admin',
    's3.secret-key' = 'password',
    's3.path.style.access' = 'true'
);

-- Iceberg catalog for writing
CREATE CATALOG iceberg_catalog WITH (
    'type'                 = 'iceberg',
    'catalog-type'         = 'rest',
    'uri'                  = 'http://iceberg-rest:8181',
    'warehouse'            = 's3a://warehouse/',
    'io-impl'             = 'org.apache.iceberg.hadoop.HadoopFileIO',
    'fs.s3a.endpoint'      = 'http://minio:9000',
    'fs.s3a.access.key'    = 'admin',
    'fs.s3a.secret.key'    = 'password',
    'fs.s3a.path.style.access' = 'true',
    'fs.s3a.impl'          = 'org.apache.hadoop.fs.s3a.S3AFileSystem'
);

-- Source: read CSV from MinIO
CREATE TABLE IF NOT EXISTS csv_source (
    user_id       BIGINT,
    item_id       BIGINT,
    category_id   BIGINT,
    behavior_type STRING,
    timestamp     BIGINT
) WITH (
    'connector' = 'filesystem',
    'path' = 's3://warehouse/UserBehavior.csv',
    'format' = 'csv',
    'csv.field-delimiter' = ',',
    'csv.ignore-parse-errors' = 'false',
    'csv.skip-records' = '1'
);

USE CATALOG iceberg_catalog;
CREATE DATABASE IF NOT EXISTS lake;
USE lake;

-- Create sink table
CREATE TABLE IF NOT EXISTS lake.user_behavior_dwd (
    user_id       BIGINT,
    item_id       BIGINT,
    category_id   BIGINT,
    behavior_type STRING,
    event_time    TIMESTAMP(3),
    pt            STRING
) PARTITIONED BY (pt) WITH (
    'format' = 'parquet',
    'write.format.default' = 'parquet',
    'write.parquet.compression-codec' = 'zstd',
    'format-version' = '2'
);

-- Create aggregated tables
CREATE TABLE IF NOT EXISTS lake.user_behavior_pvuv_1m (
    window_start  TIMESTAMP(3),
    window_end    TIMESTAMP(3),
    pv            BIGINT,
    uv            BIGINT,
    cart_count    BIGINT,
    buy_count     BIGINT,
    pt            STRING
) PARTITIONED BY (pt) WITH (
    'format' = 'parquet',
    'write.format.default' = 'parquet',
    'write.parquet.compression-codec' = 'zstd',
    'format-version' = '2'
);

CREATE TABLE IF NOT EXISTS lake.item_hot_1h (
    window_start  TIMESTAMP(3),
    window_end    TIMESTAMP(3),
    item_id       BIGINT,
    pv            BIGINT,
    cart_count    BIGINT,
    buy_count     BIGINT,
    category_id   BIGINT,
    pt            STRING
) PARTITIONED BY (pt) WITH (
    'format' = 'parquet',
    'write.format.default' = 'parquet',
    'write.parquet.compression-codec' = 'zstd',
    'format-version' = '2'
);

-- Insert DWD: raw detail table
INSERT INTO lake.user_behavior_dwd
SELECT
    user_id,
    item_id,
    category_id,
    behavior_type,
    TO_TIMESTAMP(FROM_UNIXTIME(timestamp)) AS event_time,
    CAST(DATE_FORMAT(TO_TIMESTAMP(FROM_UNIXTIME(timestamp)), 'yyyy-MM-dd') AS STRING) AS pt
FROM minio_catalog.default_database.csv_source
WHERE
    behavior_type IN ('pv', 'buy', 'cart', 'fav')
    AND user_id > 0 AND item_id > 0 AND category_id > 0 AND timestamp > 0;
