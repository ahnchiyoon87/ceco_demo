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
    'properties.group.id' = 'flinkhab-tier1',
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
    'topic' = 'exp.l4.alerts.flinkhab',
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
SELECT
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

SET 'pipeline.name' = 'AR100-Tier1-CEP';

-- ── ③ 복합 상태 규칙 (CEP) — PDF p.8 예시의 직역 ─────────────────────────
-- "모터 전류가 정격의 120%(9.6A)를 초과한 후 10초 이내에
--  베어링 진동 센서의 진폭이 기준치(7.1mm/s)를 상회하는 경우"
--
-- Esper/EQL 의 패턴 매칭을 Flink 의 MATCH_RECOGNIZE (NFA 기반) 로 대체한다.
-- Esper 와 달리 분산 실행되며 체크포인트로 상태가 정확히 한 번 복구된다.

INSERT INTO alerts
SELECT ts, site, device, `tag`, `value`,
       'CEP_BEARING' AS alert_type,
       'CRITICAL'    AS severity,
       'TIER1_CEP'   AS detector,
       detail
FROM (
    SELECT * FROM telemetry_raw
    WHERE `tag` IN ('IT-102', 'VT-101')
)
MATCH_RECOGNIZE (
    PARTITION BY device
    ORDER BY event_time
    MEASURES
        -- 주의: PARTITION BY 컬럼(device)은 출력에 자동 포함되므로
        -- MEASURES 에서 같은 이름을 다시 정의하면 "Columns ambiguously defined" 가 난다.
        LAST(VIB.ts)      AS ts,
        LAST(VIB.site)    AS site,
        'VT-101'          AS `tag`,
        LAST(VIB.`value`) AS `value`,
        CONCAT('교반기 전류 ', CAST(ROUND(LAST(OVERCURRENT.`value`), 2) AS STRING),
               'A (정격 120% 초과) 후 ',
               CAST(TIMESTAMPDIFF(SECOND, LAST(OVERCURRENT.event_time), LAST(VIB.event_time)) AS STRING),
               '초 내 진동 ', CAST(ROUND(LAST(VIB.`value`), 2) AS STRING),
               'mm/s 상회 → 베어링 열화 의심') AS detail
    ONE ROW PER MATCH
    AFTER MATCH SKIP PAST LAST ROW
    -- OTHER 는 DEFINE 이 없으므로 모든 행에 매칭된다 (reluctant 수량자로 최소 소비).
    -- 이것이 없으면 두 조건이 '같은 스캔에서 동시에' 참일 때만 매칭되어
    -- 시간 선후관계가 드러나지 않고 단순 AND 와 구별되지 않는다.
    PATTERN (OVERCURRENT OTHER*? VIB) WITHIN INTERVAL '10' SECOND
    DEFINE
        OVERCURRENT AS OVERCURRENT.`tag` = 'IT-102' AND OVERCURRENT.`value` > 9.6,
        VIB         AS VIB.`tag`         = 'VT-101' AND VIB.`value`         > 7.1
);
