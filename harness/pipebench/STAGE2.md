# 중계 파이프 벤치 (EXP-PIPE) — 준비 상태와 실행법

작성 2026-09-29. **준비만 했고 띄우지 않았다**(무거운 측정 중 기동 금지). 검증된 것: `docker compose config -q` 통과(기본 Kafka 3.9.0·`KAFKA_IMAGE=apache/kafka:4.3.1` 둘 다), 검사기 분석부(`analyze_relay1`·`analyze_relay3`·`fault_windows`) 합성 시험 — 정상·ts float 화·여분 키·유실·필터 누출(①), 정상·모양 불일치·중복(③), 사건 구간 유실(④)에서 기대대로 판정. 이미지 로컬 보유(빌드 이미지 제외). 후보 설정의 동작은 전부 **미검증**.

기준: `QUESTIONS.md` §1, `CANDIDATES.md` §4·§11(P-C·P-D·P-E), `ROBUSTNESS.md` R01·R03·R06·R08(`stage4.sh`, §4-1). 알람 워커는 별도 벤치 `harness/alarmworkerbench/`.

## 1. V1 이 하던 일(정답은 V1 설정 파일에서 도출)

| 중계 | V1 부품 | 입력 → 출력 | 보장해야 할 것 |
|---|---|---|---|
| ① | Telegraf#1 1.33 `telegraf/bridge-edgex.conf` | MQTT `edgex/telemetry`(EdgeX Event v3, QoS1, 영속 세션) → Kafka `sensor.telemetry.raw` | reading 마다 1건, 계측 12태그만, 센티널(≤ -999998) 제외, 레코드 `{ts(ns, reading origin), site:"AR-100", device, tag, value(float), quality:"GOOD"}`, key = tag, lz4, acks=all |
| ② | Telegraf#2 1.33 `telegraf/sink.conf` | Kafka clean·raw·anomaly.score·alerts(newest) → InfluxDB `process`·`process_raw`·`anomaly`·`alerts` | 측정별 태그·필드 이름·타입(sink.conf json_v2), ts=레코드 ts(ns) |
| ③ | Telegraf#3 1.33 `telegraf/alert-republish.conf` | Kafka `sensor.alerts` → MQTT `scada/alerts/{tag}` + `scada/hmi/latest-alert` | ① Telegraf JSON `{"fields":{"detail","value"},"name":"alert","tags":{alert_type,detector,device,severity,site,tag},"timestamp":ns}` ② 텍스트 `MM-DD HH:MM:SS UTC \| severity \| tag \| alert_type`(FUXA 최근 알람) |

`ai-alarm-worker` 는 Kafka `sensor.alerts` 를 직접 소비한다(`ai-layer/.../operations/consumer.py`, 영속 저장 뒤 커밋). V1 에서도 직접 짠 업무 로직이라 이 벤치의 대체 대상이 아니다(§6).

## 2. 벤치 구조

- 고정 상수: EMQX 5.8.6(V1 `emqx/emqx.conf`, hostname `emqx`) · Kafka `${KAFKA_IMAGE}`(기본 V1 `apache/kafka:3.9.0`, 토픽은 V1 `kafka/create-topics.sh`) · InfluxDB 2.7(org `bench`, bucket `process`, 벤치 전용 토큰). 호스트명이 V1 과 같아 **V1 Telegraf 설정 3개를 한 글자도 안 바꾸고** 마운트한다.
- 발생기+검사기 `check_pipe.py`(한 컨테이너): 입력 A = EdgeX Event 1 Hz(12 계측 + 5건마다 비계측 1개 + 10건마다 TT-101 센티널) 또는 `lite`(V1 `sim.py` 직발행 모양), 입력 B = Kafka 에 clean 12/s·anomaly 1/s·alerts `ALERT_RATE`/s(고유 detail). raw 는 시작 시점 끝 오프셋부터 전 파티션 소비, 중계 ③ 은 MQTT 구독, 중계 ② 는 InfluxDB Flux 로 1초 폴링(지연)·종료 후 개수·태그 키 조회.
- 가드: `rot-iiot`/`rot-ai` 가 떠 있으면 거부(`FORCE=1`).

## 3. 후보 → 프로파일

| 후보(우선순위) | 프로파일 | 이미지(정확한 태그) | 재현 방법 | 알려진 차이·위험 |
|---|---|---|---|---|
| V1 기준 Telegraf 1.33 ×3 | `v1` | `telegraf:1.33-alpine` | V1 설정 3개 그대로 | 강제 교체 대상(1.33 지원 종료). **이 프로파일 결과가 비교 기준**(검사기의 이상적 기대와 다르면 V1 값을 기준으로 삼는다 — 예: ts 가 float 로 나가는지) |
| Telegraf 1.40.1 ×3 (P1, 같은 제품 최신) | `telegraf140x3` | `telegraf:1.40.1-alpine` | V1 설정 3개 그대로, 이미지만 교체 | Kafka 4.x 소비(#17570) → `KAFKA_IMAGE=apache/kafka:4.3.1` 로 한 번 더 |
| Telegraf 1.40.1 한 대 (P1, P-E) | `telegraf140x1` | `telegraf:1.40.1-alpine` | `telegraf/single.conf` = V1 설정 3개를 기계적으로 합치고 출력마다 `namepass` 로 경로 분리, Telegraf#2 배치·버퍼·flush 는 출력별 설정으로 이전 | 한 프로세스라 재시작·OOM 이 세 중계를 함께 멈춤(장애 격리 → 4단계) |
| Bento 1.21.2 (P2) | `bento` | `ghcr.io/warpstreamlabs/bento:1.21.2` | streams 모드 `benthos/relay1~3.yaml`: ① mqtt→unarchive→mapping→kafka_franz(key=tag) ② kafka_franz→Bloblang 라인 프로토콜→http_client(/api/v2/write) ③ kafka_franz→broker fan_out mqtt ×2 | 파티셔너 murmur2(Telegraf 와 태그→파티션 배정 다름, 태그 단위 순서는 같음). Influx 전용 출력이 없어 http_client |
| Redpanda Connect 4.111.0 Apache 컴포넌트만 (P2) | `rpconnect` | `docker.redpanda.com/redpandadata/connect:4.111.0` | Bento 와 같은 스트림 파일(mqtt·kafka_franz·http_client·mapping — 모두 Apache) | RCL 엔터프라이즈 커넥터 미사용(① 관문). 같은 파일 호환 [미검증] |
| benthos-umh v0.16.0 (P2) | `benthos-umh` | `ghcr.io/united-manufacturing-hub/benthos-umh:0.16.0` | 같은 스트림 파일 | 수집(§2)과 한 도구로 묶을 수 있는지의 근거 |
| LF Edge eKuiper 2.4.2 (P1) | `ekuiper` | `lfedge/ekuiper:2.4.2` | REST `ekuiper/setup.py`: ① `unnest(readings)`→memory→필터 규칙→kafka 싱크(key `{{.tag}}`) ② 토픽별 kafka 스트림→influx2 싱크 ③ kafka 스트림→mqtt 싱크 ×2(dataTemplate) | JSON 숫자 float64 처리로 ts(ns) 끝자리 손실 위험(검사기 `ts_not_exact_ns` 로 드러남). 싱크 속성 이름 [미검증] |
| Vector 0.58.0 (P3) | `vector` | `timberio/vector:0.58.0-alpine` (이미지 이름 유지 확인) | `vector/vector.yaml`: mqtt 소스→remap(배열 루트=이벤트 분할)→kafka(key_field tag) / kafka→route→influxdb_logs ×4 / kafka→mqtt ×2 | MQTT 소스 beta·ack 미지원(재시작 유실 가능). influxdb_logs 는 태그 외 모든 키를 필드로 쓴다 |
| Apache NiFi 2.12.0 (P3) | `nifi` | `apache/nifi:2.12.0` | `nifi/setup.py apply` 가 REST 로 프로세서 21개·연결·Kafka 컨트롤러 서비스를 만들고 시작(09-29: 재현 가능 설정만 인정). ① ConsumeMQTT→SplitJson→JoltTransformJSON→EvaluateJsonPath→RouteOnAttribute→PublishKafka(key=${tag}) ② ConsumeKafka→EvaluateJsonPath→RouteOnAttribute→ReplaceText(라인)×4→MergeContent→InvokeHTTP ③ ConsumeKafka→EvaluateJsonPath→ReplaceText×2→PublishMQTT×2 | 프로세서 속성 이름 [미검증] — 틀리면 UI 로 고친 뒤 `setup.py export` → `nifi/exported-flow.json` 이 정본(업로드 API 로 재적용). ④ 부담: 흐름 21개 프로세서 |
| Kafka Connect + Stream Reactor 12.1.2 MQTT source (P2, P-D) | `kconnect` | 빌드 `pipebench-kconnect:4.3.1-sr12.1.2`(FROM `apache/kafka:4.3.1` + 릴리스 zip `kafka-connect-mqtt-12.1.2.zip`) + ②③ 은 `telegraf:1.40.1-alpine` `relay23.conf` | 중계 ① 만 대체: `connect-standalone` + KCQL `INSERT INTO sensor.telemetry.raw SELECT * FROM edgex/telemetry` | **V1 중계 ① 을 재현할 수 없음(예상)**: 메시지 1건=레코드 1건, 배열 펼치기·필터 SMT 없음 → raw 에 EdgeX Event 통째. Kafka ≥ 4.0 필요(자동으로 4.3.1). 12.x 에 InfluxDB 커넥터 없음(중계 ② 불가) |
| RMQTT 0.24.0 브로커 내장 Kafka 출력 (P1, P-C) | `rmqtt-pc` | `rmqtt/rmqtt:0.24.0` + `telegraf:1.40.1-alpine`(relay23) | 발행기가 V1 lite 모양(`iiot/AR-100/reactor-line-01/<tag>`, 레코드 1건)을 RMQTT 로, `rmqtt-bridge-egress-kafka` 가 `iiot/#` → `sensor.telemetry.raw`. ③ 은 relay23 이 RMQTT 로 재발행 | **key 지정 불가**(0.24.0 설정에 `remote.partition` 고정만) → key=tag 불일치·태그 순서 역전 가능. lite 페이로드의 `seq` 가 그대로 들어가 스키마 여분 키. EdgeX 모양 입력은 펼칠 수 없어 수집기가 태그별 최종 스키마로 내야 성립 |
| TBMQ 2.4.0 Integration Executor (P2, P-C) | `tbmq-pc` | `thingsboard/tbmq:2.4.0`, `thingsboard/tbmq-integration-executor:2.4.0`, `postgres:17`, `valkey/valkey:8.0.11-alpine` + relay23 | lite 모양 → TBMQ → Kafka 통합(`tbmq/setup.py apply` 가 REST `/api/integration` 로 생성) | 통합 모델 필드 [미검증] → 틀리면 UI 1회 + export. 컨테이너 +4. 벤치 Kafka 를 TBMQ 내부 저장에도 공유. 영속 메시지 한도 1만 → 10만 맞춤 |

제외(① 관문): Confluent MQTT Source(상용), Redpanda Connect 엔터프라이즈 커넥터(RCL).
목록에 있으나 이 벤치에 프로파일이 없는 것: Kapacitor·Node-RED(알람 흐름, P3)·Fluent Bit(MQTT 입력이 서버 모드)·RisingWave(구조 대안) — §6.

## 4. 명령

레포 루트(Git Bash)에서, 한 번에 하나.

```bash
harness/pipebench/stage2.sh v1                                   # 기준 먼저(Kafka 3.9.0)
harness/pipebench/stage2.sh telegraf140x3
KAFKA_IMAGE=apache/kafka:4.3.1 harness/pipebench/stage2.sh telegraf140x3   # #17570 확인
harness/pipebench/stage2.sh telegraf140x1
harness/pipebench/stage2.sh bento
harness/pipebench/stage2.sh ekuiper
harness/pipebench/stage2.sh kconnect                             # 자동으로 Kafka 4.3.1
harness/pipebench/stage2.sh rmqtt-pc
RUN=r2 harness/pipebench/stage2.sh telegraf140x1                 # 반복(3회 중앙값)
```

결과: `experiments/EXP-PIPE/stage2_<profile>[_k<kafka>][_<RUN>].json`, 원자료 `experiments/EXP-PIPE/raw/`(stats·images·logs).
JSON: `relay1_mqtt_to_kafka_raw`(기대·고유·유실·중복·여분·필터 누출·스키마/값 불일치·key≠tag·ts 비정수·태그 순서 역전·지연), `relay2_kafka_to_influx`(측정별 필드 개수·태그 키, 알람 detail 유실·태그 불일치, 1초 폴링 지연), `relay3_kafka_to_mqtt`(알람당 1건·중복·모양·토픽·HMI 텍스트 일치·지연), `resources`.

## 5. 판정에 쓸 때 주의

- InfluxDB 는 같은 series+시각을 덮어써서 중계 ② 의 중복은 보이지 않는다(유실만 판정).
- 중계 ② 지연은 1초 폴링 해상도.
- P-C·P-D 프로파일의 `resources` 는 후보 컨테이너 합(보조 relay23 포함). 브로커를 대체하는 P-C 는 EMQX 가 빠지는 이득을 브로커 층 결과와 합쳐 계산할 것.

## 4-1. 4단계(비정상) — `stage4.sh` (09-29 지시)

기준 `v1` 을 같은 스크립트로 먼저 잰다. 한 번에 하나, `rot-*` 가 떠 있으면 거부.

| 시험 | 대응 | 주입 | 잴 것(결과 `fault` + 전체 relay 절) |
|---|---|---|---|
| `r01` | R01 | 60 s 지점에 브로커 `docker stop` → 30 s → `start`(P-C 프로파일은 RMQTT/TBMQ). 발생 240 s | 구간 입력의 ①③ 유실·중복, 복구 후 첫 전달까지 초, 최대 공백. 입력 A 발행기는 paho 내부 큐로 보관(= 수집기 저장 후 전달 대역) |
| `r03` | R03 | 60 s 지점 Kafka `docker restart`. 발생 240 s | ①②③ 유실·중복, 소비자 재개 |
| `r06` | R06 | 60 s 지점 InfluxDB `docker stop` → 300 s → `start`. 발생 480 s | 다운 중 알람이 복구 후 적재됐는가(쓰기 버퍼 = `relay2.lost_in_window`), ①③ 이 영향받지 않는가(통합안의 장애 격리) |
| `r08` | R08 | 입력 A 10배(EdgeX 이벤트 10/s = reading 120/s) 600 s | 알람 지연 p95(②③), 유실, 적체 해소(`first_*_after_end_s`) |

```bash
harness/pipebench/stage4.sh r01 v1
harness/pipebench/stage4.sh r01 telegraf140x1
harness/pipebench/stage4.sh r06 telegraf140x1
SETTLE=300 harness/pipebench/stage4.sh r08 bento
```
결과: `experiments/EXP-PIPE/stage4_<test>_<profile>[...].json`(+ raw/fault_·stats_·logs_). 검사기 MQTT 구독자도 R01 에서 끊긴다 — 재구독 전 발행분은 검사기 쪽 공백(FUXA 구독과 같은 조건)이라 V1 과 같은 방법으로 비교한다.

## 6. 남은 것

- 알람 워커 대체는 `harness/alarmworkerbench/STAGE2.md`.
- Kapacitor·Node-RED(알람 흐름, P3)·Fluent Bit(MQTT 입력이 서버 모드)·RisingWave(구조 대안)는 프로파일 없음(우선순위 P3, 요청 시 추가).
