-- ═══════════════════════════════════════════════════════════════════════════
-- 공용 업무 DB(PostgreSQL 18.6, DATABASE plant): 스키마 4개(HANDOFF §2-2 저장, 17번 H1)
--   registry  설비 등록부(shared/registry/generate.py 가 내용을 만든다 → 20_registry.sql)
--   workflow  작업 요청·승인·응답의 정본(추가 전용). 현재 상태는 뷰로 계산한다
--   alert     분석 alert(Flink) 기록과 ISA-18.2 상태(억제·Out of Service), 사건 묶음
--   audit     감사 기록(추가 전용, UPDATE·DELETE 거부 — IEC 62443 SR 3.9 취지)
-- ═══════════════════════════════════════════════════════════════════════════
CREATE SCHEMA registry;
CREATE SCHEMA workflow;
CREATE SCHEMA alert;
CREATE SCHEMA audit;

-- 추가 전용 표: 누구든 UPDATE·DELETE 하면 거부한다(권한 회수에 더해 트리거로 막는다)
CREATE FUNCTION audit.append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  RAISE EXCEPTION '추가 전용 표(%.%)는 % 할 수 없다', TG_TABLE_SCHEMA, TG_TABLE_NAME, TG_OP USING ERRCODE = 'insufficient_privilege';
END $$;

-- ── registry ──
CREATE TABLE registry.equipment (
  id text PRIMARY KEY, type text NOT NULL, name text NOT NULL, site text NOT NULL, area text NOT NULL, line text NOT NULL);
CREATE TABLE registry.signal (
  tag text PRIMARY KEY, equipment_id text NOT NULL REFERENCES registry.equipment(id), class text NOT NULL, unit text,
  lsl double precision, usl double precision, deadband double precision NOT NULL, scan_s double precision NOT NULL,
  max_interval_s double precision NOT NULL, topic text NOT NULL);
CREATE TABLE registry.work_master (
  id text PRIMARY KEY, equipment_id text NOT NULL REFERENCES registry.equipment(id), parameters jsonb NOT NULL, description text);

-- ── workflow: 작업 요청(OPC UA ISA-95 Job Control 필드 흉내)과 그 뒤의 모든 사건 ──
CREATE TABLE workflow.request (
  job_order_id text PRIMARY KEY,
  work_master_id text NOT NULL REFERENCES registry.work_master(id),
  equipment_id text NOT NULL REFERENCES registry.equipment(id),
  job_order_parameters jsonb NOT NULL DEFAULT '[]',
  requester text NOT NULL,
  approver text NOT NULL,
  context jsonb,
  incident_id uuid,
  proposal_id uuid,
  created_at timestamptz NOT NULL DEFAULT now());
-- 사건 종류: approved · dispatched · gateway_accepted/gateway_rejected(ⓐ) · receipt(ⓑ) · operator(ⓒ-1) · plc(ⓒ-2)
--           ack_timeout(결과 모름) · expired_unconfirmed · unconfirmed · observed(재관측 일치) · command_disagree
CREATE TABLE workflow.request_event (
  id bigserial PRIMARY KEY,
  job_order_id text NOT NULL REFERENCES workflow.request(job_order_id),
  kind text NOT NULL,
  status text,
  reason text,
  detail jsonb,
  source text NOT NULL,
  at timestamptz NOT NULL DEFAULT now());
CREATE INDEX ON workflow.request_event (job_order_id, at);
-- 변경 관리 기록(MOC 흉내): 운전 범위를 넘는 설정·허용 범위 변경 승인(요청 길로 보내지 않는다, 17번 E37)
CREATE TABLE workflow.moc_record (
  id bigserial PRIMARY KEY, subject text NOT NULL, change jsonb NOT NULL, requester text NOT NULL,
  approver text NOT NULL, reason text, at timestamptz NOT NULL DEFAULT now());
CREATE TRIGGER request_append_only BEFORE UPDATE OR DELETE ON workflow.request FOR EACH ROW EXECUTE FUNCTION audit.append_only();
CREATE TRIGGER request_event_append_only BEFORE UPDATE OR DELETE ON workflow.request_event FOR EACH ROW EXECUTE FUNCTION audit.append_only();
CREATE TRIGGER moc_append_only BEFORE UPDATE OR DELETE ON workflow.moc_record FOR EACH ROW EXECUTE FUNCTION audit.append_only();
-- 현재 상태 = 마지막 사건(표는 고치지 않는다)
CREATE VIEW workflow.request_status AS
  SELECT r.*, e.kind AS last_kind, e.status AS last_status, e.reason AS last_reason, e.at AS last_at
  FROM workflow.request r
  LEFT JOIN LATERAL (SELECT kind, status, reason, at FROM workflow.request_event x
                     WHERE x.job_order_id = r.job_order_id ORDER BY x.at DESC, x.id DESC LIMIT 1) e ON true;

-- ── alert: 분석 alert(ISA-18.2 "alert", 알람과 따로) ──
CREATE TABLE alert.alert_event (
  id bigserial PRIMARY KEY,
  ts timestamptz NOT NULL, asset_id text, rule_id text NOT NULL, tag text, value double precision,
  severity text, detector text, detail text,
  display_state text NOT NULL,          -- DISPLAYED · SUPPRESSED_BY_DESIGN · OUT_OF_SERVICE
  group_id bigint,
  at timestamptz NOT NULL DEFAULT now());
CREATE TRIGGER alert_event_append_only BEFORE UPDATE OR DELETE ON alert.alert_event FOR EACH ROW EXECUTE FUNCTION audit.append_only();
-- 사건 묶음(사건 키 asset_id + rule_id): 열린 묶음이 있으면 건수·마지막 시각만 올린다(17번 F4)
CREATE TABLE alert.alert_group (
  id bigserial PRIMARY KEY,
  asset_id text, rule_id text NOT NULL,
  state text NOT NULL DEFAULT 'ACTIVE',  -- ACTIVE · CLEARED
  count integer NOT NULL DEFAULT 1,
  first_ts timestamptz NOT NULL, last_ts timestamptz NOT NULL,
  suppressed_by text,                   -- NULL · DESIGN(설비 정지) · OUT_OF_SERVICE(정비 모드)
  maint_operator integer);
CREATE UNIQUE INDEX alert_group_open ON alert.alert_group (asset_id, rule_id) WHERE state = 'ACTIVE';

-- ── audit: 같은 요청 ID 로 요청→승인→경계 검사→OT 수용/거부→결과. 주체 = 사람/시스템/AI(AI 는 별도 ID) ──
CREATE TABLE audit.log (
  id bigserial PRIMARY KEY,
  at timestamptz NOT NULL DEFAULT now(),
  actor_type text NOT NULL CHECK (actor_type IN ('human', 'system', 'ai')),
  actor_id text NOT NULL,
  action text NOT NULL,
  job_order_id text,
  subject text,
  detail jsonb);
CREATE INDEX ON audit.log (job_order_id, at);
CREATE TRIGGER audit_append_only BEFORE UPDATE OR DELETE ON audit.log FOR EACH ROW EXECUTE FUNCTION audit.append_only();

-- ── 권한(최소 권한): UPDATE·DELETE 는 누구에게도 주지 않는다(alert_group 상태만 업무 서비스가 고친다) ──
GRANT USAGE ON SCHEMA registry, workflow, alert, audit TO ops, dispatcher, ai_app, reader;
GRANT SELECT ON ALL TABLES IN SCHEMA registry TO ops, dispatcher, ai_app, reader;
GRANT SELECT, INSERT ON workflow.request, workflow.request_event, workflow.moc_record TO ops, ai_app;
GRANT SELECT ON workflow.request, workflow.request_status TO dispatcher, ai_app, ops, reader;
GRANT SELECT, INSERT ON workflow.request_event TO dispatcher;
GRANT SELECT ON workflow.request_event, workflow.moc_record TO reader;
GRANT SELECT, INSERT ON alert.alert_event TO ops;
GRANT SELECT, INSERT, UPDATE ON alert.alert_group TO ops;
GRANT SELECT ON alert.alert_event, alert.alert_group TO ai_app, reader;
GRANT INSERT, SELECT ON audit.log TO ops, dispatcher, ai_app;
GRANT SELECT ON audit.log TO reader;
GRANT USAGE ON ALL SEQUENCES IN SCHEMA workflow, alert, audit TO ops, dispatcher, ai_app;
REVOKE UPDATE, DELETE, TRUNCATE ON audit.log, workflow.request, workflow.request_event, workflow.moc_record, alert.alert_event
  FROM PUBLIC, ops, dispatcher, ai_app, reader;
