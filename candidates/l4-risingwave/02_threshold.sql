-- ── 02 임계치: 규격표 임시 조인(추가 전용 출력) ──
CREATE SINK IF NOT EXISTS alerts_threshold AS
SELECT t.ts, t.site, t.device, t.tag, t."value",
       CASE WHEN l.usl IS NOT NULL AND t."value" > l.usl THEN 'THRESHOLD_USL' ELSE 'THRESHOLD_LSL' END AS alert_type,
       'CRITICAL' AS severity, 'TIER1_RULE' AS detector,
       t.tag || ' = ' || CAST(ROUND(t."value"::NUMERIC, 3) AS VARCHAR) || ' ' || COALESCE(l.unit, '') ||
       ' / 규격 [' || COALESCE(CAST(l.lsl AS VARCHAR), '-') || ', ' || COALESCE(CAST(l.usl AS VARCHAR), '-') || ']' AS detail
FROM telemetry_raw AS t
JOIN tag_limits FOR SYSTEM_TIME AS OF PROCTIME() AS l ON t.tag = l.tag
WHERE (l.usl IS NOT NULL AND t."value" > l.usl) OR (l.lsl IS NOT NULL AND t."value" < l.lsl)
WITH (connector = 'kafka', properties.bootstrap.server = 'kafka:9092', topic = 'exp.l4.alerts.risingwave')
FORMAT PLAIN ENCODE JSON (force_append_only = 'true');

