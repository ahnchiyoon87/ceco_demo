-- V1 업무 DB 스키마(최종 상태) — ai-layer/knowledge/backend/src/modules/operations/api.py initialize() +
-- consumer.py initialize_inbox() 의 DDL 을 실행 순서대로 옮김(v1-original 코드 기준, 의미 변경 없음).
-- 후보(엔진) 프로파일에서만 초기화 스크립트로 적용한다. V1 프로파일은 V1 워커가 스스로 만든다.
CREATE TABLE IF NOT EXISTS manufacturing_incidents (
    id uuid PRIMARY KEY,
    alarm_key text NOT NULL UNIQUE,
    site text NOT NULL,
    device text NOT NULL,
    status text NOT NULL DEFAULT 'received',
    revision integer NOT NULL DEFAULT 1,
    alarm jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE IF NOT EXISTS manufacturing_events (
    id bigserial PRIMARY KEY,
    incident_id uuid NOT NULL REFERENCES manufacturing_incidents(id),
    kind text NOT NULL,
    payload jsonb NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE manufacturing_incidents ADD COLUMN IF NOT EXISTS correlation_key text;
CREATE INDEX IF NOT EXISTS manufacturing_events_incident_id_idx ON manufacturing_events(incident_id, id DESC);
ALTER TABLE manufacturing_incidents ADD COLUMN IF NOT EXISTS first_ts bigint;
ALTER TABLE manufacturing_incidents ADD COLUMN IF NOT EXISTS last_ts bigint;
ALTER TABLE manufacturing_incidents ADD COLUMN IF NOT EXISTS alarm_count integer NOT NULL DEFAULT 1;
ALTER TABLE manufacturing_incidents ADD COLUMN IF NOT EXISTS review_revision integer;
UPDATE manufacturing_incidents SET review_revision = revision WHERE review_revision IS NULL;
ALTER TABLE manufacturing_incidents ALTER COLUMN review_revision SET DEFAULT 1;
ALTER TABLE manufacturing_incidents ALTER COLUMN review_revision SET NOT NULL;
CREATE TABLE IF NOT EXISTS manufacturing_alarm_links (
    alarm_key text PRIMARY KEY,
    incident_id uuid NOT NULL REFERENCES manufacturing_incidents(id)
);
CREATE TABLE IF NOT EXISTS manufacturing_inbox (
    topic text NOT NULL, partition_id integer NOT NULL, offset_id bigint NOT NULL,
    status text NOT NULL CHECK (status IN ('accepted', 'rejected')),
    incident_id uuid REFERENCES manufacturing_incidents(id),
    raw_payload bytea NOT NULL, error text,
    created_at timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (topic, partition_id, offset_id)
);
