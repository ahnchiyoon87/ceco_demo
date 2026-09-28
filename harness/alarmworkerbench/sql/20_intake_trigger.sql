-- 엔진 후보용 접수 로직: V1 consumer.py persist_message() + api.py Alarm 검증·correlation_key()·ingest() 를 PL/pgSQL 로 옮김.
-- 엔진(Bento·Redpanda Connect·eKuiper·Kafka Connect JDBC)은 Kafka 메시지를 (topic, partition, offset, 원문 바이트) 한 행으로
-- alarm_intake 에 넣기만 하고(엔진 기능: 소비·커밋·재시도·DB 쓰기), 업무 판단은 이 트리거가 한다.
-- 분류(QUESTIONS §1): 업무 로직(알람 수명주기) = V1 도 직접 짠 범위 → 허용. ④ "떠안는 코드량"에 이 파일을 기록한다.
-- 동등성은 벤치가 V1 결과와 대조해 판정한다(check_alw.py). 알려진 차이:
--   · alarm_key: V1 = sha256(Python json.dumps(sort_keys) 문자열), 여기 = sha256(jsonb 정규 문자열). 값은 다르지만 "같은 내용 = 같은 키" 성질은 같다.
--   · error 문구: V1 = pydantic 오류 JSON, 여기 = 짧은 사유. 상태(accepted/rejected)만 비교한다.
--   · pydantic lax 변환(숫자 문자열 → int/float, 정수값 float → int, bool → 숫자)을 흉내 냈다 — 경계 사례는 벤치 입력에 포함.
CREATE TABLE IF NOT EXISTS alarm_intake (
    id bigserial PRIMARY KEY,
    topic text,
    partition_id integer,
    offset_id bigint,
    raw_payload bytea,
    received_at timestamptz NOT NULL DEFAULT now()
);

CREATE OR REPLACE FUNCTION alw_num(v jsonb, want_int boolean) RETURNS numeric
LANGUAGE plpgsql IMMUTABLE AS $$
DECLARE t text := jsonb_typeof(v); n numeric;
BEGIN
  IF t = 'number' THEN n := v::text::numeric;
  ELSIF t = 'boolean' THEN n := CASE WHEN v::text = 'true' THEN 1 ELSE 0 END;
  ELSIF t = 'string' THEN
    IF want_int AND (v #>> '{}') ~ '^\s*[+-]?[0-9]+\s*$' THEN n := trim(v #>> '{}')::numeric;
    ELSIF NOT want_int AND (v #>> '{}') ~ '^\s*[+-]?([0-9]+\.?[0-9]*|\.[0-9]+)([eE][+-]?[0-9]+)?\s*$' THEN n := trim(v #>> '{}')::numeric;
    ELSE RETURN NULL; END IF;
  ELSE RETURN NULL; END IF;
  IF want_int AND n <> trunc(n) THEN RETURN NULL; END IF;
  RETURN n;
END $$;

CREATE OR REPLACE FUNCTION alw_validate(raw bytea, OUT alarm jsonb, OUT err text)
LANGUAGE plpgsql AS $$
DECLARE d jsonb; k text; ts numeric; val double precision;
  req text[] := ARRAY['ts','site','device','tag','value','alert_type','severity','detector','detail'];
  lim jsonb := '{"site":[1,100],"device":[1,100],"tag":[1,100],"alert_type":[1,100],"severity":[1,50],"detector":[1,100],"detail":[0,10000]}';
BEGIN
  BEGIN
    d := convert_from(raw, 'UTF8')::jsonb;
  EXCEPTION WHEN others THEN
    err := 'json_invalid'; RETURN;
  END;
  IF jsonb_typeof(d) <> 'object' THEN err := 'model_type'; RETURN; END IF;
  FOR k IN SELECT jsonb_object_keys(d) LOOP
    IF NOT k = ANY(req) THEN err := 'extra_forbidden:' || k; RETURN; END IF;
  END LOOP;
  FOREACH k IN ARRAY req LOOP
    IF NOT d ? k THEN err := 'missing:' || k; RETURN; END IF;
  END LOOP;
  ts := alw_num(d->'ts', true);
  IF ts IS NULL OR ts <= 0 OR ts > 9223372036854775807 THEN err := 'ts'; RETURN; END IF;
  BEGIN
    val := alw_num(d->'value', false)::double precision;
  EXCEPTION WHEN others THEN
    err := 'value_overflow'; RETURN;
  END;
  IF val IS NULL OR val = 'Infinity'::float8 OR val = '-Infinity'::float8 THEN err := 'value'; RETURN; END IF;
  FOR k IN SELECT jsonb_object_keys(lim) LOOP
    IF jsonb_typeof(d->k) <> 'string' THEN err := 'string_type:' || k; RETURN; END IF;
    IF char_length(d->>k) < (lim->k->>0)::int OR char_length(d->>k) > (lim->k->>1)::int THEN
      err := 'string_length:' || k; RETURN;
    END IF;
  END LOOP;
  alarm := jsonb_build_object('ts', ts::bigint, 'site', d->>'site', 'device', d->>'device', 'tag', d->>'tag',
                              'value', val, 'alert_type', d->>'alert_type', 'severity', d->>'severity',
                              'detector', d->>'detector', 'detail', d->>'detail');
END $$;

-- V1 correlation_key(): 교육용 AR-100 명시 매핑. json.dumps([site, device, group], separators=(",",":")) 와 같은 문자열
-- (ensure_ascii 기본 True: 비 ASCII 는 \uXXXX — 벤치 입력은 ASCII 만 쓴다).
CREATE OR REPLACE FUNCTION alw_correlation_key(a jsonb) RETURNS text
LANGUAGE sql IMMUTABLE AS $$
  SELECT '[' || to_jsonb(a->>'site')::text || ',' || to_jsonb(a->>'device')::text || ',' || to_jsonb(
    CASE WHEN a->>'site' = 'AR-100' AND a->>'device' = 'reactor-line-01'
          AND a->>'tag' IN ('IT-102', 'VT-101') AND a->>'alert_type' IN ('CEP_BEARING', 'THRESHOLD_USL', 'ZSCORE')
         THEN 'mixer-current-vibration-v1' ELSE (a->>'tag') || ':' || (a->>'alert_type') END)::text || ']'
$$;

CREATE OR REPLACE FUNCTION alw_ingest(a jsonb) RETURNS uuid
LANGUAGE plpgsql AS $$
DECLARE k text := encode(sha256(convert_to(a::text, 'UTF8')), 'hex');
  grp text := alw_correlation_key(a); gap bigint := 30000000000; ts bigint := (a->>'ts')::bigint;
  r manufacturing_incidents%ROWTYPE; correlated boolean; known boolean; review_change boolean; inc uuid;
BEGIN
  PERFORM pg_advisory_xact_lock(hashtextextended(grp, 0));
  SELECT l.incident_id INTO inc FROM manufacturing_alarm_links l WHERE l.alarm_key = k;
  IF FOUND THEN RETURN inc; END IF;                                      -- 중복(같은 내용): 사건 그대로
  SELECT * INTO r FROM manufacturing_incidents
   WHERE correlation_key = grp AND status NOT IN ('closed', 'rejected')
     AND first_ts <= ts + gap AND last_ts >= ts - gap
   ORDER BY last_ts DESC LIMIT 1 FOR UPDATE;
  correlated := FOUND;
  IF correlated THEN
    SELECT EXISTS (SELECT 1 FROM manufacturing_events WHERE incident_id = r.id AND kind IN ('alarm_received', 'alarm_correlated')
                   AND payload->>'tag' = a->>'tag' AND payload->>'alert_type' = a->>'alert_type'
                   AND payload->>'detector' = a->>'detector' AND payload->>'severity' = a->>'severity') INTO known;
    review_change := NOT known OR ts < r.first_ts;
    UPDATE manufacturing_incidents SET first_ts = LEAST(first_ts, ts), last_ts = GREATEST(last_ts, ts),
           alarm_count = alarm_count + 1, revision = revision + 1, review_revision = review_revision + review_change::int
     WHERE id = r.id;
    inc := r.id;
  ELSE
    inc := gen_random_uuid();
    INSERT INTO manufacturing_incidents(id, alarm_key, site, device, alarm, correlation_key, first_ts, last_ts)
    VALUES (inc, k, a->>'site', a->>'device', a, grp, ts, ts);
  END IF;
  INSERT INTO manufacturing_alarm_links(alarm_key, incident_id) VALUES (k, inc);
  INSERT INTO manufacturing_events(incident_id, kind, payload)
  VALUES (inc, CASE WHEN correlated THEN 'alarm_correlated' ELSE 'alarm_received' END, a);
  RETURN inc;
END $$;

CREATE OR REPLACE FUNCTION alw_intake() RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE v record; inc uuid;
BEGIN
  SELECT * INTO v FROM alw_validate(coalesce(NEW.raw_payload, ''::bytea));
  IF v.err IS NULL THEN inc := alw_ingest(v.alarm); END IF;
  -- 오프셋을 모르는 엔진은 partition -1, offset = 접수 행 id → 재전달 멱등성은 사건 쪽(링크)만 남는다(벤치가 기록)
  INSERT INTO manufacturing_inbox(topic, partition_id, offset_id, status, incident_id, raw_payload, error)
  VALUES (coalesce(NEW.topic, 'sensor.alerts'), coalesce(NEW.partition_id, -1), coalesce(NEW.offset_id, NEW.id),
          CASE WHEN v.err IS NULL THEN 'accepted' ELSE 'rejected' END, inc, coalesce(NEW.raw_payload, ''::bytea), v.err)
  ON CONFLICT (topic, partition_id, offset_id) DO NOTHING;
  RETURN NULL;
END $$;

DROP TRIGGER IF EXISTS alw_intake_trg ON alarm_intake;
CREATE TRIGGER alw_intake_trg AFTER INSERT ON alarm_intake FOR EACH ROW EXECUTE FUNCTION alw_intake();
