SET 'execution.savepoint.path' = 'file:/opt/flink/checkpoints/booth-threshold-ttl/savepoint-9f1d68-7adee5509409';
SET 'execution.savepoint.ignore-unclaimed-state' = 'false';
SET 'execution.savepoint-restore-mode' = 'NO_CLAIM';
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
    'topic' = 'sensor.telemetry.raw',
    'properties.bootstrap.servers' = 'kafka:9092',
    'properties.group.id' = 'flink-tier1',
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
    'topic' = 'sensor.alerts',
    'properties.bootstrap.servers' = 'kafka:9092',
    'format' = 'json'
);

SET 'pipeline.name' = 'AR100-Tier1-Threshold';

-- ═══════════════════════════════════════════════════════════════════════════
-- Tier 3-B · 1계층 이상 탐지 (PDF p.8) — 전부 선언형 SQL
--
--   ① 엔지니어링 규격 USL/LSL 이탈
--   ② 동적 롤링 Z-Score  |z| > 3.0
--   ③ CEP: 전류 초과 후 10초 내 진동 초과 (MATCH_RECOGNIZE)
--
-- PDF 결론 2 — Esper/EQL 을 Flink CEP 로 대체 — 를 SQL 한 문장으로 실증합니다.
-- ═══════════════════════════════════════════════════════════════════════════

-- ── ① 엔지니어링 임계치(USL/LSL) 감지 ────────────────────────────────────
INSERT INTO alerts
-- 규격표는 한 번 읽는 고정 CSV다. 이미 판정한 과거 센서 행은 다시
-- 결합할 필요가 없으므로 센서 쪽만 60초 후 정리한다. 규격표 쪽은
-- 만료시키지 않는다(전역 TTL을 설정하면 고정 규격표까지 사라진다).
-- https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/dev/table/sql/queries/hints/#state-ttl-hints
SELECT /*+ STATE_TTL('t' = '60s') */
    t.ts, t.site, t.device, t.`tag`, t.`value`,
    CASE WHEN l.usl IS NOT NULL AND t.`value` > l.usl THEN 'THRESHOLD_USL'
         ELSE 'THRESHOLD_LSL' END                                   AS alert_type,
    'CRITICAL'                                                      AS severity,
    'TIER1_RULE'                                                    AS detector,
    CONCAT(t.`tag`, ' = ', CAST(ROUND(t.`value`, 3) AS STRING), ' ', COALESCE(l.unit, ''),
           ' / 규격 [',
           COALESCE(CAST(l.lsl AS STRING), '-'), ', ',
           COALESCE(CAST(l.usl AS STRING), '-'), ']')               AS detail
FROM telemetry_raw AS t
JOIN tag_limits AS l ON t.`tag` = l.`tag`
WHERE (l.usl IS NOT NULL AND t.`value` > l.usl)
   OR (l.lsl IS NOT NULL AND t.`value` < l.lsl);

