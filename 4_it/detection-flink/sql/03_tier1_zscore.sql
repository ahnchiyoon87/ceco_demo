SET 'pipeline.name' = 'AR100-Tier1-ZScore';

-- ── ② 동적 롤링 Z-Score (PDF p.8) ────────────────────────────────────────
-- 센서별 슬라이딩 윈도우 60샘플의 평균·표준편차를 실시간 산출하고
-- 현재 계측치의 이탈 정도 |z| 를 판정한다. 규격(USL/LSL) 이탈이 아니어도
-- 잡아내므로 noise 시나리오의 탐지 주체가 된다.
--
-- ⚠ 지속성(persistence) 조건이 필요한 이유:
--    설정치 램프 구간에서는 공정값이 단조 이동하므로 이동평균이 뒤처지고
--    순간적으로 |z| 가 3 을 넘는다. 실측에서 정상 운전 중 z=3.02~3.09 오탐이
--    확인되었다. 산업 현장의 표준 대응대로 "최근 5샘플 중 3샘플 이상 위반"
--    이라는 지속성 요건을 걸어 램프에 의한 순간 위반을 걸러낸다.

INSERT INTO alerts
SELECT ts, site, device, `tag`, `value`,
       'ZSCORE'       AS alert_type,
       'WARNING'      AS severity,
       'TIER1_ZSCORE' AS detector,
       CONCAT(`tag`, ' z=', CAST(ROUND(z, 2) AS STRING),
              ' (μ=', CAST(ROUND(mu, 3) AS STRING),
              ', σ=', CAST(ROUND(sd, 4) AS STRING),
              ', 최근5중 ', CAST(viol_run AS STRING), '회 위반)') AS detail
FROM (
    SELECT ts, site, device, `tag`, `value`, mu, sd, z,
           SUM(viol) OVER (
               PARTITION BY `tag` ORDER BY event_time
               ROWS BETWEEN 4 PRECEDING AND CURRENT ROW
           ) AS viol_run
    FROM (
        SELECT ts, site, device, `tag`, `value`, event_time, mu, sd, z,
               CASE WHEN z > 3.5 THEN 1 ELSE 0 END AS viol
        FROM (
            SELECT ts, site, device, `tag`, `value`, event_time, mu, sd, n,
                   CASE WHEN sd > 1e-9 THEN ABS(`value` - mu) / sd ELSE 0.0 END AS z
            FROM (
                SELECT ts, site, device, `tag`, `value`, event_time,
                       AVG(`value`) OVER w AS mu,
                       STDDEV_SAMP(`value`) OVER w AS sd,
                       COUNT(*) OVER w AS n
                FROM telemetry_raw
                WINDOW w AS (
                    PARTITION BY `tag`
                    ORDER BY event_time
                    ROWS BETWEEN 59 PRECEDING AND CURRENT ROW
                )
            )
            -- 윈도우가 충분히 차기 전의 불안정한 통계는 판정에서 제외
            WHERE n >= 30
        )
    )
)
WHERE viol_run >= 3;
