# 인터페이스 계약 (V1 실측 기준)

모든 후보는 이 계약을 지킨다. 형식이 다른 후보는 후보 쪽에 어댑터를 둔다.
근거: 2026-09-28 원본 V1 Kafka 메시지 실측 + Telegraf·Flink 설정 + 업무 DB `\d` 조회.

## 1. L1 가상설비

- Modbus TCP (slave 1): 계측 HR 0~22 float32(2워드, 태그 12개), 코일 0 펌프 · 1 교반기 · 2 히터 · 3 냉각기 · 10 알람 확인 · 20 인터록(읽기 전용), HR 100 펌프 속도 % · 101 밸브 개도 % · 102 온도 SP ×10, HR 200 seq(UINT32)
- HTTP: `GET /state` (seq·commands·interlock·readings·active_faults·status·site·device), `POST /fault {"scenario","duration_s"}`, `POST /fault/clear`
- 스캔 주기 1000 ms

## 2. MQTT

| 토픽 | 생산 | 소비 | 페이로드 |
|---|---|---|---|
| `edgex/telemetry` | EdgeX app-mqtt-export | Telegraf#1 (QoS1, 영속 세션) | EdgeX Event `{deviceName, origin(ns), readings:[{resourceName, value(문자열), ...}]}` |
| `iiot/+/+/+` | 시뮬레이터 직발행(`make lite`만) | Telegraf lite | lite 경로 전용 |
| `scada/alerts/{tag}` | Telegraf#3 | FUXA | Telegraf JSON (tags: site·device·tag·alert_type·severity·detector, fields: value·detail, timestamp ns) |
| `scada/hmi/latest-alert` | Telegraf#3 | FUXA 최근 알람 | 문자열 `MM-DD HH:MM:SS UTC \| {severity} \| {tag} \| {alert_type}` |

## 3. Kafka

| 토픽 | 파티션·보존 | 생산 | 소비 | 파티션 키 |
|---|---|---|---|---|
| `sensor.telemetry.raw` | 6 · 24h | Telegraf#1 | Flink 규칙·ONNX, Telegraf#2 | tag |
| `sensor.telemetry.clean` | 6 · 24h | Flink | Telegraf#2 | — |
| `sensor.anomaly.score` | 3 · 24h | Flink ONNX | Telegraf#2 | — |
| `sensor.alerts` | 3 · 7일 | Flink 규칙·ZScore·CEP·ONNX | Telegraf#3 (`offset=newest`), 알람 워커 | — |

레코드 (실측 예):

```json
// raw / clean  — ts = 나노초 (Flink: TO_TIMESTAMP_LTZ(ts/1000000, 3))
{"ts":1790581601213181400,"site":"AR-100","device":"reactor-line-01","tag":"LT-102","value":53.6462,"quality":"GOOD"}

// score
{"ts":1790558359422000000,"site":"AR-100","device":"reactor-line-01","reconstruction_error":0.0126,"threshold":0.0351,
 "is_anomaly":false,"top_contributors":"CT-101(44%), pH-101(24%), IT-102(19%)","inference_ms":0.45}

// alerts
{"ts":1789956258948738800,"site":"AR-100","device":"reactor-line-01","tag":"IT-102","value":9.613946,
 "alert_type":"THRESHOLD_USL","severity":"CRITICAL","detector":"TIER1_RULE","detail":"IT-102 = 9.614 A / 규격 [-, 9.6]"}
```

- `alert_type`: `THRESHOLD_USL | THRESHOLD_LSL | ZSCORE | CEP_BEARING | ML_AUTOENCODER`
- `detector`: `TIER1_RULE | TIER1_ZSCORE | TIER1_CEP | TIER2_ML`
- raw의 `quality`는 Telegraf#1이 항상 `"GOOD"`으로 채운다(불량값 `<= -999998`은 버림). 결측은 레코드 부재로만 드러난다.

## 4. 측정용 추가 필드 (하니스가 붙인다)

raw에 `trace_id`·발행 시각이 없다. 기존 소비자를 바꾸지 않기 위해 **추가 필드로만** 붙인다.

- 리플레이(2순위 주입) 레코드: `trace_id`(uuid), `emit_ns`(하니스 발행 시각, ns). Flink JSON 소스는 모르는 필드를 무시한다(`json.ignore-parse-errors`와 무관하게 스키마 밖 필드는 무시됨 → 실측으로 확인 필요).
- 가상설비 경로(1순위 주입): 레코드를 바꿀 수 없으므로 `POST /fault` 호출 시각과 해당 태그의 alerts 레코드 `ts`·Kafka `CreateTime`을 대조해 지연을 계산한다.
- 후보의 alerts 출력은 위 alerts 스키마를 그대로 따른다. 후보가 `trigger_trace_ids`를 추가로 실을 수 있으면 싣는다(선택).

## 5. 업무 DB (ar100_work, PostgreSQL 17)

| 테이블 | 역할 |
|---|---|
| `manufacturing_incidents` | 사건. `alarm_key` UNIQUE, `correlation_key`로 중복 관측 결합, `revision`·`review_revision` |
| `manufacturing_alarm_links`, `manufacturing_inbox` | 알람↔사건 연결, 접수함 |
| `manufacturing_analysis_runs` | AI 분석 실행 |
| `manufacturing_proposals` | 대응안. `status`, `expires_at`(생성+5분), `state_fingerprint`, `decision`, `result` |
| `manufacturing_events` | 감사 기록(append). `kind`: proposal_created · action_authorized · action_dispatch_started · action_acknowledged · action_observed · action_result · proposal_rejected · execution_recovered … |
| `manufacturing_operator_commands` | C2 직접 조작. `id` = 요청 ID(PK), request·result |
| `manufacturing_knowledge_builds` | 지식 구축 |
| `checkpoints`, `checkpoint_blobs`, `checkpoint_writes`, `checkpoint_migrations` | LangGraph PostgresSaver |

## 6. 재시작 동작 (계약에 포함되는 현재 동작)

| 구성 | 재시작 시 동작 | 근거 |
|---|---|---|
| Telegraf#1 수집 | MQTT QoS1 + 영속 세션 → 단절 구간 보존 | `bridge-edgex.conf` |
| Flink 잡 | 세션 클러스터·HA 없음 → JobManager 재시작 시 잡 소멸, 재제출 필요. 소스 `latest-offset` → 중단 구간 건너뜀 | `01_sources.sql`, 2026-09-28 관측(V1_FACTS §5) |
| Telegraf#3 알람 중계 | `offset=newest` → 중단 구간 알람을 FUXA에 보내지 않음 | `alert-republish.conf` |
