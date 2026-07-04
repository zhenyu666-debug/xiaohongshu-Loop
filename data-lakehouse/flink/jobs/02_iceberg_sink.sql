-- ============================================================
-- 02_iceberg_sink.sql
-- 创建 Iceberg Sink 表（清洗后数据）
-- ============================================================

CREATE CATALOG IF NOT EXISTS iceberg_catalog WITH (
    'type'                 = 'iceberg',
    'catalog-type'         = 'rest',
    'uri'                  = 'http://iceberg-rest:8181',
    'warehouse'            = 's3://warehouse/',
    'io-impl'              = 'org.apache.iceberg.aws.s3.S3FileIO',
    's3.endpoint'          = 'http://minio:9000',
    's3.access-key-id'     = 'admin',
    's3.secret-access-key' = 'password',
    's3.path-style-access' = 'true'
);

USE CATALOG iceberg_catalog;

-- 实时明细表（按天分区）
CREATE TABLE IF NOT EXISTS iceberg_catalog.default.user_behavior_dwd (
    user_id       BIGINT,
    item_id        BIGINT,
    category_id    BIGINT,
    behavior_type  STRING,
    event_time     TIMESTAMP(3),
    pt             STRING  -- 分区字段：天级 2017-11-25
) WITH (
    'format'                 = 'parquet',
    'write.parquet.compression-codec' = 'zstd',
    'write.distribution-mode' = 'hash',
    'write.metadata.delete-after-commit.enabled' = 'true',
    'write.metadata.previous-versions-max' = '100',
    'partitioning'           = 'pt'
);

-- 分钟级 PV/UV 聚合表
CREATE TABLE IF NOT EXISTS iceberg_catalog.default.user_behavior_pvuv_1m (
    window_start   TIMESTAMP(3),
    window_end     TIMESTAMP(3),
    pv             BIGINT,
    uv             BIGINT,
    cart_count     BIGINT,
    buy_count      BIGINT,
    pt             STRING
) WITH (
    'format'                 = 'parquet',
    'write.parquet.compression-codec' = 'zstd',
    'write.distribution-mode' = 'hash',
    'partitioning'           = 'pt'
);

-- 商品热度实时聚合表
CREATE TABLE IF NOT EXISTS iceberg_catalog.default.item_hot_1h (
    window_start   TIMESTAMP(3),
    window_end     TIMESTAMP(3),
    item_id        BIGINT,
    pv             BIGINT,
    cart_count     BIGINT,
    buy_count      BIGINT,
    category_id    BIGINT,
    pt             STRING
) WITH (
    'format'                 = 'parquet',
    'write.parquet.compression-codec' = 'zstd',
    'write.distribution-mode' = 'hash',
    'partitioning'           = 'pt'
);
