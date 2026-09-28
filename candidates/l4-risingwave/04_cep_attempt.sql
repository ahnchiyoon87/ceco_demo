-- L4-03/04 시도: V1 04_tier1_cep.sql 의 MATCH_RECOGNIZE 를 그대로 RisingWave 에 낸다.
-- 문서상 미지원(rw-flink-feature-comparison) — 엔진의 실제 오류 메시지를 시도 기록에 남기는 것이 목적.
CREATE SINK alerts_cep AS
SELECT ts, site, device, tag, "value", 'CEP_BEARING' AS alert_type, 'CRITICAL' AS severity, 'TIER1_CEP' AS detector, detail
FROM (SELECT * FROM telemetry_wm WHERE tag IN ('IT-102', 'VT-101'))
MATCH_RECOGNIZE (
    PARTITION BY device
    ORDER BY event_time
    MEASURES
        LAST(VIB.ts) AS ts, LAST(VIB.site) AS site, 'VT-101' AS tag, LAST(VIB."value") AS "value",
        'CEP' AS detail
    ONE ROW PER MATCH
    AFTER MATCH SKIP PAST LAST ROW
    PATTERN (OVERCURRENT OTHER*? VIB) WITHIN INTERVAL '10' SECOND
    DEFINE
        OVERCURRENT AS OVERCURRENT.tag = 'IT-102' AND OVERCURRENT."value" > 9.6,
        VIB AS VIB.tag = 'VT-101' AND VIB."value" > 7.1
)
WITH (connector = 'kafka', properties.bootstrap.server = 'kafka:9092', topic = 'exp.l4.alerts.risingwave')
FORMAT PLAIN ENCODE JSON (force_append_only = 'true');
