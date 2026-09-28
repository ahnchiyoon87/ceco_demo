-- ISA-18.2 알람 수명주기 — PostgreSQL 상태 테이블 + 트랜잭션 함수 (EXP-ALM 후보 pg-isa).
-- 성격: V1 ai-alarm-worker 와 같은 "업무 로직 연결 코드"(QUESTIONS §1 허용 범위). 저장·잠금·감사는 PostgreSQL 이 한다.
-- 참조 설계: Alerta alerta/models/alarms/isa_18_2.py (상태 A~E, 전이 규칙). 차이: 셸빙 만료(shelved_until)를 DB 가 가진다.
-- 상태: NORM(정상) · UNACK(발생·미확인) · ACKED(확인) · RTNUN(복귀·미확인) · SHLVD(셸빙)
-- 모든 전이는 행 잠금(FOR UPDATE) 안에서 alarm_event 에 누가·언제·무엇을·왜를 한 줄씩 남긴다(append-only, CQ15·CQ08 근거).
-- 배치(09-29 결정): 업무 DB(ar100_work, PostgreSQL 17)와 같은 서버의 별도 스키마 isa. 업무 테이블(manufacturing_*)과 이름·권한이 섞이지 않는다.

CREATE SCHEMA IF NOT EXISTS isa;
SET search_path = isa;

CREATE TABLE IF NOT EXISTS alarm (
  alarm_key     text PRIMARY KEY,                 -- site|device|tag|alert_type (V1 alerts 레코드에서 만든다)
  site          text NOT NULL, device text NOT NULL, tag text NOT NULL, alert_type text NOT NULL,
  state         text NOT NULL CHECK (state IN ('NORM','UNACK','ACKED','RTNUN','SHLVD')),
  active        boolean NOT NULL,                 -- 공정 조건이 아직 이상인가(발생 true / 복귀 false)
  severity      text NOT NULL,
  last_value    double precision,
  last_detail   text,
  occurrences   integer NOT NULL DEFAULT 1,
  first_ts      bigint NOT NULL, last_ts bigint NOT NULL,   -- V1 alerts ts(ns)
  shelved_until timestamptz, shelved_by text, shelve_reason text,
  acked_by      text, acked_at timestamptz,
  updated_at    timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS alarm_event (
  id        bigserial PRIMARY KEY,
  alarm_key text NOT NULL REFERENCES alarm(alarm_key),
  at        timestamptz NOT NULL DEFAULT clock_timestamp(),
  actor     text NOT NULL,                        -- 'process'(발생·복귀) | 'system'(만료) | 운전원 ID
  action    text NOT NULL,                        -- raise|duplicate|rtn|ack|ack_rejected|shelve|unshelve_expired|re_alarm
  from_state text, to_state text,
  reason    text,
  payload   jsonb
);
CREATE INDEX IF NOT EXISTS alarm_event_key_idx ON alarm_event(alarm_key, id);

-- 감사 기록은 지우거나 고칠 수 없다(G6 감사)
CREATE OR REPLACE FUNCTION alarm_event_immutable() RETURNS trigger LANGUAGE plpgsql SET search_path = isa AS $$
BEGIN RAISE EXCEPTION 'alarm_event is append-only'; END $$;
DROP TRIGGER IF EXISTS alarm_event_no_change ON alarm_event;
CREATE TRIGGER alarm_event_no_change BEFORE UPDATE OR DELETE ON alarm_event
  FOR EACH ROW EXECUTE FUNCTION alarm_event_immutable();

CREATE OR REPLACE FUNCTION sev_rank(s text) RETURNS int LANGUAGE sql IMMUTABLE AS $$
  SELECT CASE upper(s) WHEN 'CRITICAL' THEN 5 WHEN 'HIGH' THEN 4 WHEN 'WARNING' THEN 3 WHEN 'MEDIUM' THEN 3
                       WHEN 'LOW' THEN 2 WHEN 'ADVISORY' THEN 1 ELSE 0 END $$;

CREATE OR REPLACE FUNCTION alarm_log(k text, actor text, act text, f text, t text, why text, p jsonb)
RETURNS void LANGUAGE sql SET search_path = isa AS $$
  INSERT INTO alarm_event(alarm_key, actor, action, from_state, to_state, reason, payload) VALUES (k, actor, act, f, t, why, p);
  SELECT pg_notify('alarm_state', json_build_object('key', k, 'state', t, 'action', act)::text);
$$;

-- 발생(V1 alerts 레코드 1건)
CREATE OR REPLACE FUNCTION alarm_raise(m jsonb) RETURNS text LANGUAGE plpgsql SET search_path = isa AS $$
DECLARE k text := concat_ws('|', m->>'site', m->>'device', m->>'tag', m->>'alert_type'); r alarm; nxt text; act text;
BEGIN
  SELECT * INTO r FROM alarm WHERE alarm_key = k FOR UPDATE;
  IF NOT FOUND THEN
    INSERT INTO alarm(alarm_key, site, device, tag, alert_type, state, active, severity, last_value, last_detail, first_ts, last_ts)
    VALUES (k, m->>'site', m->>'device', m->>'tag', m->>'alert_type', 'UNACK', true, m->>'severity',
            (m->>'value')::float8, m->>'detail', (m->>'ts')::bigint, (m->>'ts')::bigint);
    PERFORM alarm_log(k, 'process', 'raise', 'NORM', 'UNACK', null, m);
    RETURN 'UNACK';
  END IF;
  nxt := r.state; act := 'duplicate';
  IF r.state = 'SHLVD' THEN act := 'raise_while_shelved';
  ELSIF r.state IN ('NORM', 'RTNUN') THEN nxt := 'UNACK'; act := 'raise';
  ELSIF r.state = 'ACKED' AND sev_rank(m->>'severity') > sev_rank(r.severity) THEN nxt := 'UNACK'; act := 're_alarm';
  ELSIF r.state = 'ACKED' AND NOT r.active THEN nxt := 'UNACK'; act := 'raise';
  END IF;
  UPDATE alarm SET state = nxt, active = true, severity = m->>'severity', last_value = (m->>'value')::float8,
         last_detail = m->>'detail', occurrences = occurrences + 1, last_ts = greatest(last_ts, (m->>'ts')::bigint),
         acked_by = CASE WHEN nxt = 'UNACK' THEN null ELSE acked_by END,
         acked_at = CASE WHEN nxt = 'UNACK' THEN null ELSE acked_at END, updated_at = now()
   WHERE alarm_key = k;
  PERFORM alarm_log(k, 'process', act, r.state, nxt, null, m);
  RETURN nxt;
END $$;

-- 복귀(공정 조건 정상) — V1 에는 복귀 신호가 없다: 연결 코드가 raw 값(한계 이하)에서 만든다
CREATE OR REPLACE FUNCTION alarm_rtn(k text, m jsonb DEFAULT null) RETURNS text LANGUAGE plpgsql SET search_path = isa AS $$
DECLARE r alarm; nxt text;
BEGIN
  SELECT * INTO r FROM alarm WHERE alarm_key = k FOR UPDATE;
  IF NOT FOUND OR NOT r.active THEN RETURN coalesce(r.state, 'NORM'); END IF;
  nxt := CASE r.state WHEN 'UNACK' THEN 'RTNUN' WHEN 'ACKED' THEN 'NORM' ELSE r.state END;
  UPDATE alarm SET state = nxt, active = false, updated_at = now() WHERE alarm_key = k;
  PERFORM alarm_log(k, 'process', 'rtn', r.state, nxt, null, m);
  RETURN nxt;
END $$;

-- 확인(운전원)
CREATE OR REPLACE FUNCTION alarm_ack(k text, who text, why text DEFAULT null) RETURNS text LANGUAGE plpgsql SET search_path = isa AS $$
DECLARE r alarm; nxt text;
BEGIN
  IF who IS NULL OR who = '' THEN RAISE EXCEPTION 'ack requires operator id'; END IF;
  SELECT * INTO r FROM alarm WHERE alarm_key = k FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'unknown alarm %', k; END IF;
  IF r.state = 'UNACK' THEN nxt := 'ACKED';
  ELSIF r.state = 'RTNUN' THEN nxt := 'NORM';
  ELSE PERFORM alarm_log(k, who, 'ack_rejected', r.state, r.state, why, null); RETURN r.state; END IF;
  UPDATE alarm SET state = nxt, acked_by = who, acked_at = clock_timestamp(), updated_at = now() WHERE alarm_key = k;
  PERFORM alarm_log(k, who, 'ack', r.state, nxt, why, null);
  RETURN nxt;
END $$;

-- 셸빙(운전원, 만료 시각 필수·사유 필수)
CREATE OR REPLACE FUNCTION alarm_shelve(k text, who text, seconds int, why text) RETURNS text LANGUAGE plpgsql SET search_path = isa AS $$
DECLARE r alarm;
BEGIN
  IF who IS NULL OR why IS NULL OR seconds IS NULL OR seconds <= 0 THEN RAISE EXCEPTION 'shelve requires operator, reason, expiry'; END IF;
  SELECT * INTO r FROM alarm WHERE alarm_key = k FOR UPDATE;
  IF NOT FOUND THEN RAISE EXCEPTION 'unknown alarm %', k; END IF;
  UPDATE alarm SET state = 'SHLVD', shelved_until = clock_timestamp() + make_interval(secs => seconds),
         shelved_by = who, shelve_reason = why, updated_at = now() WHERE alarm_key = k;
  PERFORM alarm_log(k, who, 'shelve', r.state, 'SHLVD', why, jsonb_build_object('seconds', seconds));
  RETURN 'SHLVD';
END $$;

-- 셸빙 만료(주기 실행: 연결 코드 또는 pg_cron). 조건이 아직 이상이면 UNACK, 아니면 NORM
CREATE OR REPLACE FUNCTION alarm_unshelve_expired() RETURNS int LANGUAGE plpgsql SET search_path = isa AS $$
DECLARE r alarm; n int := 0; nxt text;
BEGIN
  FOR r IN SELECT * FROM alarm WHERE state = 'SHLVD' AND shelved_until <= clock_timestamp() FOR UPDATE SKIP LOCKED LOOP
    nxt := CASE WHEN r.active THEN 'UNACK' ELSE 'NORM' END;
    UPDATE alarm SET state = nxt, shelved_until = null, updated_at = now() WHERE alarm_key = r.alarm_key;
    PERFORM alarm_log(r.alarm_key, 'system', 'unshelve_expired', 'SHLVD', nxt, r.shelve_reason, null);
    n := n + 1;
  END LOOP;
  RETURN n;
END $$;
