-- ── 03 Z-Score: 태그별 최근 60행(현재 포함) 평균·표본표준편차, n>=30, 최근 5행 중 3회 이상 |z|>3.5 ──
-- EMIT ON WINDOW CLOSE: 워터마크가 지난 행부터 이벤트 시각 순으로 한 번씩 확정(= V1 Flink OVER 창의 정렬·폐기 의미)
CREATE MATERIALIZED VIEW IF NOT EXISTS z_stats AS
SELECT ts, site, device, tag, "value", event_time,
       AVG("value") OVER (PARTITION BY tag ORDER BY event_time ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS mu,
       STDDEV_SAMP("value") OVER (PARTITION BY tag ORDER BY event_time ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS sd,
       COUNT(*) OVER (PARTITION BY tag ORDER BY event_time ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS n
FROM telemetry_wm
EMIT ON WINDOW CLOSE;

CREATE MATERIALIZED VIEW IF NOT EXISTS z_run AS
SELECT ts, site, device, tag, "value", event_time, mu, sd, z,
       SUM(viol) OVER (PARTITION BY tag ORDER BY event_time ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS viol_run
FROM (
    SELECT *, CASE WHEN z > 3.5 THEN 1 ELSE 0 END AS viol
    FROM (SELECT *, CASE WHEN sd > 1e-9 THEN ABS("value" - mu) / sd ELSE 0.0 END AS z FROM z_stats WHERE n >= 30) a
) b
EMIT ON WINDOW CLOSE;

CREATE SINK IF NOT EXISTS alerts_zscore AS
SELECT ts, site, device, tag, "value", 'ZSCORE' AS alert_type, 'WARNING' AS severity, 'TIER1_ZSCORE' AS detector,
       tag || ' z=' || CAST(ROUND(z::NUMERIC, 2) AS VARCHAR) || ' (최근5중 ' || CAST(viol_run AS VARCHAR) || '회 위반)' AS detail
FROM z_run WHERE viol_run >= 3
WITH (connector = 'kafka', properties.bootstrap.server = 'kafka:9092', topic = 'exp.l4.alerts.risingwave')
FORMAT PLAIN ENCODE JSON (force_append_only = 'true');
