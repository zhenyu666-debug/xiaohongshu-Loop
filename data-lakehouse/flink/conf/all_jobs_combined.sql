-- ============================================================
-- 全部 3 个 streaming 作业 (DWD, PVUV, item_hot)
-- Flink SQL Client (streaming mode)
-- ============================================================

SET 'execution.runtime-mode' = 'streaming';
SET 'execution.checkpointing.interval' = '30 s';
SET 'execution.checkpointing.min-pause' = '10 s';
SET 'state.backend' = 'rocksdb';

-- ── Catalog ───────────────────────────────────────────────
CREATE CATALOG iceberg_catalog WITH (
    'type'                 = 'iceberg',
    'catalog-type'         = 'rest',
    'uri'                  = 'http://iceberg-rest:8181',
    'warehouse'            = 's3a://warehouse/',
    'io-impl'              = 'org.apache.iceberg.hadoop.HadoopFileIO',
    'fs.s3a.endpoint'      = 'http://minio:9000',
    'fs.s3a.access.key'    = 'admin',
    'fs.s3a.secret.key'    = 'password',
    'fs.s3a.path.style.access' = 'true',
    'fs.s3a.impl'          = 'org.apache.hadoop.fs.s3a.S3AFileSystem'
);

USE CATALOG iceberg_catalog;
CREATE DATABASE IF NOT EXISTS lake;
USE lake;

-- ── Tables (idempotent) ──────────────────────────────────
CREATE TABLE IF NOT EXISTS lake.user_behavior_dwd (
    user_id       BIGINT,
    item_id       BIGINT,
    category_id   BIGINT,
    behavior_type STRING,
    event_time    TIMESTAMP(3),
    pt            STRING
) PARTITIONED BY (pt)
WITH (
    'format' = 'parquet',
    'write.format.default' = 'parquet',
    'write.parquet.compression-codec' = 'zstd',
    'format-version' = '2'
);

CREATE TABLE IF NOT EXISTS lake.user_behavior_pvuv_1m (
    window_start  TIMESTAMP(3),
    window_end    TIMESTAMP(3),
    pv            BIGINT,
    uv            BIGINT,
    cart_count    BIGINT,
    buy_count     BIGINT,
    pt            STRING
) PARTITIONED BY (pt)
WITH (
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
) PARTITIONED BY (pt)
WITH (
    'format' = 'parquet',
    'write.format.default' = 'parquet',
    'write.parquet.compression-codec' = 'zstd',
    'format-version' = '2'
);

-- ── Kafka Source ─────────────────────────────────────────
CREATE TABLE default_catalog.default_database.kafka_user_behavior (
    user_id       BIGINT,
    item_id       BIGINT,
    category_id   BIGINT,
    behavior_type STRING,
    ts            BIGINT,
    event_time    TIMESTAMP(3),
    WATERMARK FOR event_time AS event_time - INTERVAL '5' MINUTE
) WITH (
    'connector'                   = 'kafka',
    'topic'                       = 'user-behavior',
    'properties.bootstrap.servers' = 'kafka:29092',
    'properties.group.id'         = 'flink-lakehouse-consumer',
    'format'                      = 'json',
    'json.ignore-parse-errors'    = 'true',
    'scan.startup.mode'           = 'earliest-offset'
);

-- ── 清洗 + Watermark ─────────────────────────────────────
CREATE TEMPORARY VIEW watermarked AS
SELECT
    user_id,
    item_id,
    category_id,
    behavior_type,
    ts,
    event_time,
    CAST(DATE_FORMAT(event_time, 'yyyy-MM-dd') AS STRING) AS pt
FROM default_catalog.default_database.kafka_user_behavior
WHERE
    behavior_type IN ('pv', 'buy', 'cart', 'fav')
    AND user_id > 0
    AND item_id > 0
    AND category_id > 0
    AND ts > 0;

-- ── Job 1: DWD 明细 ─────────────────────────────────────
INSERT INTO lake.user_behavior_dwd
SELECT
    user_id,
    item_id,
    category_id,
    behavior_type,
    event_time,
    pt
FROM watermarked;

-- ── Job 2: PV/UV 1m 聚合 ────────────────────────────────
INSERT INTO lake.user_behavior_pvuv_1m
SELECT
    TUMBLE_START(event_time, INTERVAL '1' MINUTE) AS window_start,
    TUMBLE_END(event_time, INTERVAL '1' MINUTE)   AS window_end,
    COUNT(*)                                       AS pv,
    COUNT(DISTINCT user_id)                        AS uv,
    SUM(CASE WHEN behavior_type = 'cart' THEN 1 ELSE 0 END) AS cart_count,
    SUM(CASE WHEN behavior_type = 'buy'  THEN 1 ELSE 0 END) AS buy_count,
    CAST(DATE_FORMAT(
        TUMBLE_START(event_time, INTERVAL '1' MINUTE),
        'yyyy-MM-dd'
    ) AS STRING) AS pt
FROM watermarked
GROUP BY TUMBLE(event_time, INTERVAL '1' MINUTE);

-- ── Job 3: item_hot 1h 聚合 (hopping window 1h slide 5m) ─
INSERT INTO lake.item_hot_1h
SELECT
    HOP_START(event_time, INTERVAL '5' MINUTE, INTERVAL '1' HOUR) AS window_start,
    HOP_END(event_time, INTERVAL '5' MINUTE, INTERVAL '1' HOUR)   AS window_end,
    item_id,
    COUNT(*) FILTER (WHERE behavior_type = 'pv')   AS pv,
    COUNT(*) FILTER (WHERE behavior_type = 'cart')  AS cart_count,
    COUNT(*) FILTER (WHERE behavior_type = 'buy')   AS buy_count,
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
