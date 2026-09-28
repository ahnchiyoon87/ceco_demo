# 알람 워커 벤치 (EXP-ALW) — 준비 상태와 실행법

작성 2026-09-29(09-29 지시 3). **준비만 했고 띄우지 않았다**(무거운 측정 중 기동 금지). 검증된 것: `docker compose config -q` 통과, 시나리오 생성(50건: core 46·edge 4, NaN·1e400 치환 확인)과 비교 로직(같음·inbox 상태 차이·사건 여분) 합성 시험, 이미지 로컬 보유(빌드 이미지 제외). **PL/pgSQL 트리거·엔진 설정은 한 번도 실행되지 않았다(미검증).**

`harness/alarmbench/`(ISA-18.2 알람 표시·상태, 다른 작업)와는 다른 벤치다.

## 1. V1 이 하던 일(정답 = V1 코드 실행 결과)

`ai-alarm-worker` = `ai-layer/knowledge/backend/src/modules/operations/consumer.py`(직접 짠 코드, 허용 범위):
- Kafka `sensor.alerts` 소비(그룹 `ar100-ai-incidents-v1`, earliest, 자동 커밋 끔) → 메시지마다 `persist_message()` → **영속 저장 뒤 동기 커밋**.
- 검증: pydantic `Alarm`(extra 금지, inf/nan 금지, 길이 제한, lax 변환). 실패 → `manufacturing_inbox` 에 `rejected` + 원문 바이트(조용한 버림 없음).
- 접수(`api.py ingest()`): 내용 해시 `alarm_key` 로 중복이면 기존 사건 · 아니면 상관 키(`site,device,group`; IT-102/VT-101 의 CEP·USL·ZSCORE 는 `mixer-current-vibration-v1` 로 묶음)와 ±30 s 간격으로 열린 사건을 찾아 갱신(first/last_ts·count·revision·review_revision) 또는 새 사건. `manufacturing_alarm_links`·`manufacturing_events` 기록.
- 재전달 멱등: inbox PK `(topic, partition, offset)` `ON CONFLICT DO NOTHING` + 알람 링크.

## 2. 후보 → 프로파일

엔진 후보는 **"Kafka 소비·커밋·재시도·DB 쓰기"(엔진 기능)** 만 맡고 행 하나를 `alarm_intake(topic, partition_id, offset_id, raw_payload)` 에 넣는다. 업무 판단(검증·상관·inbox)은 `sql/20_intake_trigger.sql`(V1 로직의 PL/pgSQL 이식, AFTER INSERT 트리거)이 한다 — 업무 로직은 V1 도 직접 짠 범위라 허용, ④ "떠안는 코드량"(약 150줄 SQL)으로 기록.

| 후보 | 프로파일 | 이미지 | 엔진 설정 | 알려진 차이·위험 |
|---|---|---|---|---|
| V1 기준 | `v1` | 빌드 `alwbench-v1worker:1.0`(FROM `python:3.12.8-slim` + uv.lock 고정 버전) + V1 코드 읽기 전용 마운트 | V1 모듈 그대로 `python -m backend.src.modules.operations.consumer` | V1 운영 이미지(`latest`, LibreOffice 포함)가 아니라 같은 코드의 가벼운 대역 — 자원 비교는 워커 프로세스 기준 |
| Bento 1.21.2 | `bento` | `ghcr.io/warpstreamlabs/bento:1.21.2` | `engine/bento.yaml`: `kafka_franz`(earliest, `checkpoint_limit: 1` = 파티션마다 한 건씩 커밋) → `sql_insert`(postgres, `max_in_flight 1`, 배치 1) | 출력 성공 뒤 커밋(at-least-once). DB 다운 시 재시도(소비 정지) |
| Redpanda Connect 4.111.0 (Apache 컴포넌트만) | `rpconnect` | `docker.redpanda.com/redpandadata/connect:4.111.0` | 같은 파일(`kafka_franz`·`sql_insert` 는 Apache) | 같은 파일 호환 [미검증] |
| eKuiper 2.4.2 | `ekuiper` | `lfedge/ekuiper:2.4.2` | `ekuiper/setup.py`: kafka 소스(BINARY) → sql 싱크 | `meta(partition/offset)` 제공 [미확인] — 없으면 inbox 키가 `-1/행 id` 라 **재전달 멱등이 inbox 에서 깨짐**(사건은 링크로 보호). sql 싱크 포함 여부·커밋 시점 [미확인] |
| Kafka Connect + Aiven JDBC sink 6.12.0 | `kconnect` | 빌드 `alwbench-kconnect:4.3.1-aivenjdbc6.12.0`(소스 태그 v6.12.0 을 `eclipse-temurin:21.0.8_9-jdk` 로 빌드 → `apache/kafka:4.3.1`) | `kconnect/jdbc-sink.properties`: ByteArray → `HoistField`(raw_payload) → `InsertField`(topic·partition·offset) → insert, 배치 1 | **Confluent JDBC 커넥터는 Confluent Community License(비 OSI) → ① 관문 제외**, Aiven 판(Apache-2.0)은 v6.12.0 바이너리 미배포라 소스 빌드(첫 빌드 네트워크 필요, gradle 태스크 `installDist` [미검증]). Kafka ≥ 4 이미지라 KAFKA_IMAGE 자동 4.3.1 |

## 3. 시험(`stage2.sh` 한 번에 전부)

1. **시나리오 동등**: 결정적 알람 50건을 파티션 0 에 순서대로(상관 결과가 순서에 의존하므로). 단독 12 · 같은 서명 반복 · 30 s 간격 새 사건 · 완전 중복 · 서명 변화 · 교반기 상관(CEP/USL/ZSCORE, 이른 시각 역순 도착) · ML 알람은 묶지 않음 · 순서 의존 다리 사건 · 거부 14종(JSON 아님·빈 값·배열·null·필드 누락·여분·문자 값·ts 소수/음수/0·빈 site·숫자 tag·detail 초과·NaN·1e400) · 수용 경계(detail 1만 자·한글) · edge 4종(pydantic lax: 숫자 문자열 값·ts 문자열·bool 값·정수값 float ts). → `dump1` 을 V1 기준 덤프와 대조(`vs_v1`).
2. **재전달 멱등**: 워커 정지 → 그룹 오프셋 earliest 로 되감기 → 재기동 → LAG 0 → `dump2` 가 `dump1` 과 같아야 함(`redelivery_idempotent`).
3. **부하 + 중단**: 유효 알람 600건 20/s(3파티션, key=tag), 절반 지점에 워커 `docker kill` → 5 s 뒤 시작 → 유실·중복 이벤트·지연 p50/p95(생산 확인 → inbox 커밋).
4. 자원: 워커 + 업무 DB 컨테이너 합(엔진 후보는 판단이 DB 안에서 돌기 때문).

비교 규칙: 사건 식별 = `(correlation_key, first_ts)`. UUID·`alarm_key`(해시)·오류 문구·시각 열은 비교하지 않는다(구현·실행마다 다름). 불일치는 시나리오 label(`core`/`edge`)로 보고한다.

## 4. 명령

```bash
harness/alarmworkerbench/stage2.sh v1          # 기준 먼저(experiments/EXP-ALW/dump1_v1.json 생성)
harness/alarmworkerbench/stage2.sh bento
harness/alarmworkerbench/stage2.sh rpconnect
harness/alarmworkerbench/stage2.sh ekuiper
harness/alarmworkerbench/stage2.sh kconnect
RUN=r2 harness/alarmworkerbench/stage2.sh bento # 반복
```
결과: `experiments/EXP-ALW/stage2_<profile>[_<RUN>].json`(`vs_v1`·`redelivery_idempotent`·`load_with_worker_kill`·`resources`), 원자료 `experiments/EXP-ALW/raw/`(dump1_·dump2_·labels_·load_·reset_·actions_·stats_·logs_).

## 5. 판정에 쓸 때 주의·미검증

- V1 도 두 번 돌려 V1 끼리 같은지 먼저 볼 것(`RUN=r2 ... v1` 후 `check_alw.py compare`) — 기준 자체의 결정성 확인.
- edge 4종에서 V1 과 다르면 "lax 변환 차이"다. 실제 V1 입력(Flink)은 ts 를 정수로만 내므로 core 와 따로 본다. 특히 정수값 float ts(1.79e18.0)는 Python float 정밀도 때문에 V1 이 다른 ts 로 받을 수 있다.
- 한 트랜잭션 안에서 판단하는 트리거라 엔진이 배치로 넣으면(JDBC) 한 행 실패가 배치 전체를 되돌린다 → 재시도로 흡수되는지 로그 확인.
- DB 다운(R07 류) 중 동작은 이 스크립트에 없다(요청 범위: 동등·중복·재전달). 필요하면 부하 단계의 kill 대상을 `work-db` 로 바꾸는 변형으로 추가.
