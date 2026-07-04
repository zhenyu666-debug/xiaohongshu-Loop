-- ============================================================
-- 01_raw_to_kafka.sql
-- 在 Flink SQL Client 中执行：SET 'execution.runtime-mode' = 'streaming';
-- 然后分批执行本文件中的语句
-- ============================================================

-- 1. 创建 Kafka Source 表（原始数据，来自 Data Replay Producer）
CREATE TABLE IF NOT EXISTS k_user_behavior_raw (
    user_id    BIGINT,
    item_id     BIGINT,
    category_id BIGINT,
    behavior_type STRING,
    ts          BIGINT,
    event_time  TIMESTAMP(3) -- 派生列：从 ts 转换
) WITH (
    'connector'                   = 'kafka',
    'topic'                      = 'user-behavior',
    'properties.bootstrap.servers' = 'kafka:29092',
    'properties.group.id'        = 'flink-consumer',
    'format'                     = 'json',
    'json.fail-on-missing-field'  = 'false',
    'json.ignore-parse-errors'    = 'true',
    'scan.startup.mode'           = 'earliest-offset'
);

-- 验证数据源（查询前 10 条，确认数据流入）
SELECT * FROM k_user_behavior_raw LIMIT 10;
