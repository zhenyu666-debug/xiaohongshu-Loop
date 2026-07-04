-- DWD only job
SET 'execution.runtime-mode' = 'streaming';
SET 'execution.checkpointing.interval' = '30 s';
SET 'state.backend' = 'hashmap';
SET 'parallelism.default' = '1';
SET 'execution.restart-strategy' = 'none';

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

CREATE TABLE IF NOT EXISTS default_catalog.default_database.kafka_user_behavior (
    user_id       BIGINT,
    item_id       BIGINT,
    category_id   BIGINT,
    behavior_type STRING,
    ts            BIGINT,
    event_time    TIMESTAMP(3),
    WATERMARK FOR event_time AS event_time - INTERVAL '5' MINUTE
) WITH (
    'connector'                      = 'kafka',
    'topic'                          = 'user-behavior',
    'properties.bootstrap.servers'    = 'kafka:29092',
    'properties.group.id'            = 'flink-lakehouse-consumer-v2',
    'format'                         = 'json',
    'json.ignore-parse-errors'       = 'true',
    'scan.startup.mode'              = 'earliest-offset'
);

CREATE TEMPORARY VIEW watermarked AS
SELECT
    user_id, item_id, category_id, behavior_type, ts, event_time,
    CAST(DATE_FORMAT(event_time, 'yyyy-MM-dd') AS STRING) AS pt
FROM default_catalog.default_database.kafka_user_behavior
WHERE
    behavior_type IN ('pv', 'buy', 'cart', 'fav')
    AND user_id > 0 AND item_id > 0 AND category_id > 0 AND ts > 0;

INSERT INTO lake.user_behavior_dwd
SELECT user_id, item_id, category_id, behavior_type, event_time, pt FROM watermarked;
