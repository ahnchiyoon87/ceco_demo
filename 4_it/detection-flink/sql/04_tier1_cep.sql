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
