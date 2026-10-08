-- ═══════════════════════════════════════════════════════════════════════════
-- 기업 시스템 사실값(가상 MES·ERP·CMMS) — 정비 판단의 손익 계산이 읽는 값
--   enterprise.fact        시스템별 현재 사실(생산 가치·납기·예비품 재고·정비 인력·위험 비용률)
--   enterprise.work_order  CMMS 정비 작업 이력(승인된 정비 계획의 실행 결과 보고서)
-- 숫자는 교육용 가상 기업 데이터다(금액 단위 만원). 온톨로지는 숫자가 아니라 이 키 이름을 가리킨다.
-- 이미 있는 DB 에도 다시 실행할 수 있다(있으면 건너뛴다. 사람이 바꾼 값은 덮어쓰지 않는다).
-- ═══════════════════════════════════════════════════════════════════════════
CREATE SCHEMA IF NOT EXISTS enterprise;

CREATE TABLE IF NOT EXISTS enterprise.fact (
  key text PRIMARY KEY,
  system text NOT NULL CHECK (system IN ('MES', 'ERP', 'CMMS')),
  value double precision NOT NULL,
  unit text NOT NULL,
  description text NOT NULL,
  updated_at timestamptz NOT NULL DEFAULT now());

CREATE TABLE IF NOT EXISTS enterprise.work_order (
  id text PRIMARY KEY,
  incident_id text,
  proposal_id text,
  equipment_id text,
  option_id text NOT NULL,
  status text NOT NULL,
  opened_at timestamptz NOT NULL,
  closed_at timestamptz,
  approver text,
  report jsonb NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now());

INSERT INTO enterprise.fact(key, system, value, unit, description) VALUES
  ('mes_hour_value',          'MES',  85,   '만원/h',   '정상 운전 1시간의 생산 가치(정격 6.2 m3/h × 제품 단가)'),
  ('mes_nominal_rate_m3h',    'MES',  6.2,  'm3/h',     '정격 생산 속도'),
  ('mes_order_remaining_m3',  'MES',  120,  'm3',       '진행 중 수주(SO-2610-031) 남은 수량'),
  ('mes_order_due_h',         'MES',  26,   'h',        '진행 중 수주 납기까지 남은 시간'),
  ('mes_late_penalty_per_h',  'MES',  150,  '만원/h',   '납기 지연 시 고객 라인 정지 보상(시간당)'),
  ('mes_batch_remaining_h',   'MES',  1.5,  'h',        '현재 배치 종료까지 남은 시간'),
  ('mes_batch_scrap_cost',    'MES',  210,  '만원',     '배치 도중 교반 정지 시 배치 폐기 손실'),
  ('mes_offspec_loss_per_h',  'MES',  120,  '만원/h',   '반응기 온도 상한 초과 운전 시 품질 이탈 손실(시간당)'),
  ('erp_spare_bearing_qty',   'ERP',  1,    'ea',       '교반기 베어링 예비품 재고'),
  ('erp_bearing_cost',        'ERP',  180,  '만원',     '교반기 베어링 세트 단가'),
  ('erp_bearing_lead_h',      'ERP',  72,   'h',        '교반기 베어링 긴급 조달 리드타임'),
  ('erp_descale_chem_qty',    'ERP',  1,    'set',      '재킷 화학 세정제 재고'),
  ('erp_descale_cost',        'ERP',  60,   '만원',     '재킷 화학 세정 1회 약품·폐액 처리비'),
  ('erp_strainer_kit_cost',   'ERP',  5,    '만원',     '스트레이너 세척 가스켓·소모품'),
  ('erp_cv_kit_cost',         'ERP',  25,   '만원',     '배출 밸브 패킹·가이드 정비 키트'),
  ('cmms_labor_per_h',        'CMMS', 12,   '만원/h',   '정비팀 1개 조 시간당 인건비'),
  ('cmms_crew_callout_h',     'CMMS', 0,    'h',        '정비팀 현장 도착까지 걸리는 시간(지금 대기 중이면 0)'),
  ('cmms_trip_restart_h',     'CMMS', 0.3,  'h',        '정지·인터록 뒤 재기동·안정화 소요'),
  ('cmms_seizure_risk_per_h', 'CMMS', 90,   '만원/h',   '진동 상한 초과 상태로 운전할 때 축·감속기 손상 기대 손실(시간당, 상한 대비 1배 기준)'),
  ('cmms_overtemp_risk_per_h','CMMS', 60,   '만원/h',   '반응기 온도 상한 초과 운전의 설비·안전 기대 손실(시간당)')
ON CONFLICT (key) DO NOTHING;

GRANT USAGE ON SCHEMA enterprise TO ai_app, ops, reader;
GRANT SELECT ON enterprise.fact TO ai_app, ops, reader;
GRANT SELECT, INSERT ON enterprise.work_order TO ai_app;
GRANT SELECT ON enterprise.work_order TO ops, reader;
