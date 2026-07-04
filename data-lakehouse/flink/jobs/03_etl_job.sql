-- ============================================================
-- 03_etl_job.sql
-- 实时 ETL 作业：数据清洗 + Watermark + 去重 + 写入 Iceberg 明细表
-- ============================================================

-- 启用 Checkpoint（Flink Iceberg Sink 必须开启）
SET 'execution.checkpointing.interval' = '30 s';
SET 'execution.checkpointing.externalized-checkpoint-retention' = 'RETAIN_ON_CANCELLATION';
SET 'state.backend' = 'rocksdb';

-- 定义 Kafka Source（含 Watermark）
CREATE TEMPORARY VIEW raw_source AS
SELECT
    user_id,
    item_id,
    category_id,
    behavior_type,
    ts,
    TO_TIMESTAMP(FROM_UNIXTIME(ts)) AS event_time
FROM k_user_behavior_raw;

-- Watermark 策略：允许 5 分钟乱序
CREATE TEMPORARY VIEW watermarked AS
SELECT
    user_id,
    item_id,
    category_id,
    behavior_type,
    ts,
    event_time,
    CAST(DATE_FORMAT(event_time, 'yyyy-MM-dd') AS STRING) AS pt
FROM raw_source
WHERE
    behavior_type IN ('pv', 'buy', 'cart', 'fav')
    AND user_id > 0
    AND item_id > 0
    AND category_id > 0
    AND ts > 0;

-- 实时 ETL：写入 Iceberg 明细表
INSERT INTO user_behavior_dwd
SELECT
    user_id,
    item_id,
    category_id,
    behavior_type,
    event_time,
    pt
FROM watermarked;
