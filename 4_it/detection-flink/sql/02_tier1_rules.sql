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
