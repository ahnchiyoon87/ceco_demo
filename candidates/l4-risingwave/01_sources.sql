-- L4 후보 RisingWave v3.1.0: V1 규칙(flink/sql/01~03)을 RisingWave 스트리밍 SQL 로 옮긴 것.
-- deploy.sh 가 tag_limits.csv 를 INSERT 로 넣은 뒤 이 파일을 psql 로 실행한다(psql -v ON_ERROR_STOP=1).
-- 엔진 기능: Kafka 소스·워터마크·임시(temporal) 조인·ROWS 프레임 OVER 창·EMIT ON WINDOW CLOSE·Kafka 싱크.
-- 기능 불가(문헌, STAGE2.md): L4-03/04 CEP(MATCH_RECOGNIZE 없음), L4-12 ONNX(내장 Python UDF 는 서드파티 모듈 불가,
--   V1 의 1초 처리시각 표본도 표현 불가).

-- ── 01 소스 ──
-- 임계치용: 워터마크 없음. V1 임계치 쿼리는 워터마크와 무관하게 늦은 레코드에도 알람을 낸다.
--   (RisingWave 소스 워터마크는 늦은 행을 걸러낼 수 있어 규칙별로 소스를 나눈다 — ②에서 확인)
CREATE SOURCE IF NOT EXISTS telemetry_raw (
    ts BIGINT, site VARCHAR, device VARCHAR, tag VARCHAR, "value" DOUBLE PRECISION, quality VARCHAR
) WITH (
    connector = 'kafka', topic = 'exp.l4.raw', properties.bootstrap.server = 'kafka:9092',
    scan.startup.mode = 'latest'
) FORMAT PLAIN ENCODE JSON;

-- Z-Score 용: V1 과 같은 이벤트 시각(ts ns → 밀리초 정밀도)과 워터마크 5초
CREATE SOURCE IF NOT EXISTS telemetry_wm (
    ts BIGINT, site VARCHAR, device VARCHAR, tag VARCHAR, "value" DOUBLE PRECISION, quality VARCHAR,
    event_time TIMESTAMPTZ AS to_timestamp((ts / 1000000) / 1000.0),
    WATERMARK FOR event_time AS event_time - INTERVAL '5' SECOND
) WITH (
    connector = 'kafka', topic = 'exp.l4.raw', properties.bootstrap.server = 'kafka:9092',
    scan.startup.mode = 'latest'
) FORMAT PLAIN ENCODE JSON;

