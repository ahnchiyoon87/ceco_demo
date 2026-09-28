-- ═══════════════════════════════════════════════════════════════════════════
-- Tier 3-A · Flink SQL — 소스/싱크 정의
-- 이 계층 전체가 선언형 SQL 입니다. 자바 코드가 없습니다.
-- ═══════════════════════════════════════════════════════════════════════════

SET 'execution.checkpointing.interval' = '10s';
SET 'execution.checkpointing.mode' = 'EXACTLY_ONCE';
SET 'table.exec.source.idle-timeout' = '5s';

-- ── 원본 텔레메트리 (무손실, 보간 없음) ──
CREATE TABLE telemetry_raw (
    ts          BIGINT,
    site        STRING,
    device      STRING,
    `tag`       STRING,
    `value`     DOUBLE,
    quality     STRING,
    event_time  AS TO_TIMESTAMP_LTZ(ts / 1000000, 3),
    -- 센서 클럭 지터와 EdgeX 스캔 편차를 흡수
    WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
) WITH (
    'connector' = 'kafka',
    'topic' = 'exp.l4.raw',
    'properties.bootstrap.servers' = 'kafka:9092',
    'properties.group.id' = 'flinkcep23-tier1',
    'scan.startup.mode' = 'latest-offset',
    'format' = 'json',
    'json.ignore-parse-errors' = 'true'
);

-- ── 태그별 엔지니어링 규격 (USL/LSL). plant.yaml 에서 생성됨 ──
CREATE TABLE tag_limits (
    `tag`     STRING,
    unit      STRING,
    lsl       DOUBLE,
    usl       DOUBLE,
    PRIMARY KEY (`tag`) NOT ENFORCED
) WITH (
    'connector' = 'filesystem',
    'path' = 'file:///opt/flink/sql/tag_limits.csv',
    'format' = 'csv',
    'csv.ignore-parse-errors' = 'true'
);

-- ── 통합 알람 싱크 ──
CREATE TABLE alerts (
    ts            BIGINT,
    site          STRING,
    device        STRING,
    `tag`         STRING,
    `value`       DOUBLE,
    alert_type    STRING,   -- THRESHOLD_USL | THRESHOLD_LSL | ZSCORE | CEP_BEARING | ML_AUTOENCODER
    severity      STRING,   -- CRITICAL | WARNING
    detector      STRING,   -- TIER1_RULE | TIER1_ZSCORE | TIER1_CEP | TIER2_ML
    detail        STRING
) WITH (
    'connector' = 'kafka',
    'topic' = 'exp.l4.alerts.cep',
    'properties.bootstrap.servers' = 'kafka:9092',
    'format' = 'json'
);
