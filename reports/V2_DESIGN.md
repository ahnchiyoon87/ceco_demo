# V2 설계 — 레이어·길 재설계, 기능 대응표, 스택 조합 선택 (회전 1)

작성 2026-09-29 세션 4. 판정 기준 정본 `QUESTIONS.md` §1(결정 순서 → 기능 보존 → 구조 판정 → ①~④).
근거: 리서치 원문(`docs/research/ARCHITECTURE_SIMPLIFICATION.md`·`AGENT_BRIEF_FINAL.md`·`deep-2026-09-29/01~06`), 층별 실측(`experiments/EXP-*/layer_*.json`, decision-log #101~#119), V1 기준값(`experiments/EXP-001/summary_V1_r2_.json`).
**실측 칸이 "측정 대기"인 항목은 V2 전체 측정(EXP-002)에서 채운다. 채우기 전에는 확정이 아니다.**

## 0. (세션 4 17:50 재설계) 현업 가정 고정 · 통일 구조 — 아래 §1~§8 보다 우선

**전제(사용자 지시, 고정):** 현업 라인 — 설비 다수, 통신 방식 혼재(Modbus·OPC UA 등), 장치 등록·관리와 명령 통제가 필요. 데모 라인(설비 7대·센서 12개를 Modbus 연결 하나로 읽음)은 이 전제의 한 사례로만 쓴다.
세션 4 앞부분은 "데모는 Modbus 하나"를 근거로 EdgeX 를 뺐다 — 현업 전제에서 EdgeX 의 장치 등록부·명령 API·관리 화면·다중 통신 통합은 실제 기능이고 Telegraf 가 대신하지 못하므로, 기능 보존 기준으로 **그 판단은 틀렸다**(사용자 지적). 같은 잣대로 알람 태그별 토픽 제거·감시 선택 모듈화도 다시 본다.

**사용자 지시: 읽기·쓰기·전달 길을 하나로 통일.** 지금(V1·초기 V2) 설비를 읽는 곳이 셋(수집기 Modbus, FUXA Modbus 직접, AI 백엔드 HTTP /state), 쓰는 곳이 셋(EdgeX 명령·FUXA Modbus·AI Modbus)이다(코드 확인: `fuxa/build_project.py` devices, `ai-layer/.../actions.py`·`simulation.py`).

### 0-1. 통일 구조 (현업 UNS 참조 구조 — 리서치 06: HiveMQ "MQTT remains the best choice for building a UNS", Kafka 는 스트림 분석용 뒷단)

```
설비들 ─Modbus/OPC UA…─▶ [장치 계층 하나: EdgeX 4.0.2]  ◀── 명령(권한·인터록·기록 한 창구: EdgeX core-command)
                              │ 읽기 결과
                              ▼
                   [데이터 허브 하나: MQTT(Mosquitto)]  — EdgeX 메시지 버스도 이 브로커(내부 브로커 중복 제거)
                     │            │                 │
          FUXA 화면(구독)   AI 층(현재값)      [Kafka 커넥터 하나: Bento]
                                                 ├─ 허브 → Kafka raw ──▶ Flink(탐지, HA) ──▶ Kafka alerts/clean/score
                                                 ├─ Kafka → InfluxDB(이력) ──▶ Grafana
                                                 └─ Kafka alerts → 허브(알람, 설비·태그별 토픽 + 최근알람)
```

| 층 | 통일 뒤 담당 | V1 | 초기 V2(세션 4 전반) | 바뀌는 이유 |
|---|---|---|---|---|
| 장치(읽기) | EdgeX 하나 | EdgeX + FUXA 직접 + AI /state | Telegraf + FUXA 직접 + AI /state | 읽기 창구 하나(PLC 동시 접속·값 일치·장치 추가를 한곳에서) |
| 장치(쓰기) | EdgeX core-command 하나 | EdgeX 명령 + FUXA + AI | FUXA + AI | 명령 통제 한 창구(권한·인터록·감사) |
| 허브 | Mosquitto 하나 | EdgeX 내부 브로커 + EMQX | Mosquitto(알람·수업용 사본만) | 브로커 중복 제거, UNS 중심 |
| 분석 백본 | Kafka(허브 뒤, 다리 하나) | Kafka | Kafka | Flink 가 Kafka 로만 읽고 씀·재처리 |
| 탐지 | Flink 2.2 + HA | Flink 1.20(HA 없음) | 같음 | 변경 없음 |
| 커넥터 | Bento 하나(3개 흐름) | Telegraf ×3 | Vector 하나(2흐름) | Vector 소비 재개 버그(#22006) |
| 화면 | FUXA 가 허브 구독, 명령은 장치 계층으로 | FUXA Modbus 직접 | 같음(직접) | 통일 |
| 감시 | 기본 켬(현업 전제에서 필요) — 가벼운 설정으로 | 켬 | 선택 모듈 | 전제 재고정 |

### 0-2. 확인해야 할 것(실측 전, 사실 미확인)
1. FUXA 가 허브(MQTT) 구독만으로 12개 이상 태그를 V1 직접 폴링과 같은 주기로 표시하는가, 허브 장애(브로커 재시작 약 10 s) 때 화면 영향.
2. FUXA 명령을 장치 계층으로 보내는 방법 — EdgeX core-command 의 외부 MQTT 명령 요청 또는 REST. FUXA 가 지원하는 방식 확인.
3. EdgeX 메시지 버스를 외부 Mosquitto 로 쓰는 설정(EdgeX 4.0 공식 설정), EdgeX 4.0.2 이미지.
4. EdgeX 4.0 LTS 지원 2027-03 종료 → 다음 장기지원판(2027 봄 예정)으로 따라가는 계획을 관문 약점으로 명시.
5. AI 층의 /state 읽기·Modbus 쓰기는 담당 밖 코드 — 기반 쪽 명령 창구를 준비하고 AI 쪽 전환은 별도 과제로 기록.

## 1. 출발점과 원칙 (한 문단)
V1 의 흐름(설비 → 수집 → 전달 → 탐지 → 저장 → 화면 → AI)과 기능은 현업에서 컨펌받은 것이라 **그대로 둔다**.
바꾸는 것은 "어떻게"뿐이다 — 같은 데이터를 두 번 옮기는 길, 되돌아가는 길, 같은 일을 하는 부품, 지원이 끝났거나 12개월 안에 끝나는 판.
층을 합칠지는 "합치면 무엇을 잃는가"로 따지고, 잃는 것이 없고 실측으로 확인될 때만 합친다. 남기는 층에는 이유를 붙인다.

## 1-1. V1 해부 — 갈래별 필요성 판정 (코드·설정에서 "누가 받아 쓰는가"를 확인, 세션 4)

| # | 갈래(보내는 곳 → 받는 곳) | 실제로 받아 쓰는 곳(근거) | 판정 |
|---|---|---|---|
| 1 | 설비 → EdgeX device-modbus → EdgeX 내부 브로커 → app-mqtt-export → EMQX → Telegraf#1 → Kafka raw | 끝단 Kafka raw 만 씀(Flink `flink/sql/01_sources.sql:23`, 저장). 중간 5단계는 값을 옮기기만 함 | **줄임**: 수집기 → Kafka 1단계 |
| 2 | (lite) 설비 MQTT 직발행 `iiot/+/+/+` → EMQX → Telegraf-lite → Kafka raw | 본 경로와 같은 raw 토픽을 채우는 두 번째 수집 길(`docker-compose.yml` profiles lite, `telegraf/bridge-lite.conf`) | **없앰**(중복 길) |
| 3 | Kafka raw → Flink 잡 4개(임계치·Z-Score·CEP SQL 각 1 + ONNX 1)가 각자 읽음 | 잡마다 다른 판정(`flink/sql/02~04`, `AnomalyJob.java`) | **남김**: 규칙 잡이 서로 따로 재시작·실패(격리), V1 SQL 무수정 70/70(#107). 잡을 합쳐도 줄어드는 컨테이너 없음 |
| 4 | ONNX 잡 → Kafka clean(보간값) → 저장 `process` | Grafana `01-process.json`, verify.py | **남김** |
| 5 | Kafka raw → 저장 `process_raw` | AI 근거 조회 `evidence.py:40`·`pipeline.py`, Grafana 01 패널 8(원본 vs 보간 비교) | **남김** |
| 6 | ONNX 잡 → Kafka score → 저장 `anomaly` | Grafana `02-anomaly.json`, verify.py | **남김** |
| 7 | Kafka alerts → 저장 `alerts` | Grafana `03-alerts.json` | **남김** |
| 8 | Kafka alerts → Telegraf#3 → EMQX `scada/hmi/latest-alert` → FUXA | FUXA 알람 태그(`fuxa/build_project.py:108~117`) | **줄임**: 중계기 1 → 표시 전용 브로커 → FUXA |
| 9 | Kafka alerts → Telegraf#3 → EMQX `scada/alerts/<tag>` | **받는 곳 없음** — FUXA 는 2026-09-23 latest-alert 로 이전(`scripts/apply-fuxa-alert-topic.py`), Vue 는 MQTT 미사용(`ai-web/src` 검색 0) | **없앰**(옛 흔적 갈래) |
| 10 | Kafka alerts → 알람 워커 → PostgreSQL 사건 | AI 층(`consumer.py:55,60`) | **남김**(AI 층 입구) |
| 11 | EdgeX → `edgex/telemetry` MQTT | 수업 안내(`ai-web/public/system-guide.html`), `scripts/reference-style-architecture.py` — 사람이 쓰는 기능 | **남김**: 수집기가 같은 토픽·모양으로 사본 발행 |
| 12 | FUXA → 설비 Modbus 직접 폴링·쓰기(C1) | 운전 화면·조작 | **남김**: 운전 화면은 수집·브로커 장애와 무관해야 함(현업 원칙) |
| 13 | EdgeX core-command → 설비 쓰기 REST | **받는 곳(호출자) 없음**(`docker-compose.edgex.yml` 외 검색 0), 인증 없음 | **없앰**(쓰기 창구 축소) |
| 14 | AI 백엔드 → 설비 /state·Modbus 쓰기(C2·C3) | AI 층 | **남김**(AI 층) |
| 15 | Prometheus ← EMQX 지표(접속 수·끊김) → Grafana 04 패널·EMQXDisconnectSpike 경보 | 운영 화면·경보 | **대체 필요**: 브로커 상태 지표(방식은 리서치 07 결과로 확정) |
| 16 | Prometheus ← kafka-exporter·Flink·InfluxDB·cAdvisor | Grafana 04·경보 5종(`prometheus/rules.yml`) | **남김** + 중계기 지표 추가(V1 E11 에서 중계기 kill·탐지 잡 정지 둘 다 미탐) |

## 2. 길(데이터 경로) — 전과 후

```
V1  설비 ─Modbus─▶ EdgeX device-modbus ─▶ EdgeX 내부 Mosquitto ─▶ app-mqtt-export ─▶ EMQX ─▶ Telegraf#1 ─▶ Kafka raw
    Kafka raw ─▶ Flink(규칙 SQL 3 + ONNX 1, HA 없음) ─▶ Kafka clean/score/alerts
    Kafka ─▶ Telegraf#2 ─▶ InfluxDB 2.7 ─▶ Grafana 11.4
    Kafka alerts ─▶ Telegraf#3 ─▶ EMQX ─▶ FUXA 최근 알람          ← 알람이 수집용 브로커로 되돌아감
    Kafka alerts ─▶ 알람 워커 ─▶ PostgreSQL 사건 ─▶ AI(담당 밖)
    FUXA ─Modbus 직접 폴링·조작─▶ 설비                            ← EdgeX 와 이중 폴링
    (lite 프로필) 설비 ─MQTT 직발행─▶ EMQX ─▶ Telegraf(lite) ─▶ Kafka   ← 본 경로를 건너뛰는 두 번째 수집 길
    Prometheus 3.1 + Alertmanager 0.28 + kafka-exporter(latest) + cAdvisor 0.49

V2  설비 ─Modbus(설비 전용망)─▶ 수집기(Telegraf 1.40) ─▶ Kafka 4.3 raw
                                     └─▶ Mosquitto edgex/telemetry (V1 과 같은 토픽·모양 — 수업 자료용 실시간 계측)
    Kafka raw ─▶ Flink 2.2(규칙 SQL 3 + ONNX 1, V1 SQL 그대로) + ZooKeeper HA ─▶ Kafka clean/score/alerts
    Kafka ─▶ 중계기(Vector 1대) ─┬▶ InfluxDB 2.9 ─▶ Grafana 13.2
                                 └▶ Mosquitto scada/hmi/latest-alert ─▶ FUXA
    Kafka alerts ─▶ 알람 워커 ─▶ PostgreSQL 사건 ─▶ AI(변경 없음)
    FUXA ─Modbus 직접 폴링·조작─▶ 설비   (운전 화면은 IT 층 장애와 무관하게 — 남긴 이유 §4-③)
    Prometheus 3.15 + Alertmanager 0.34 + kafka-exporter 1.10 + cAdvisor 0.60
```

알람 → 화면 경유 단계(`harness/situations/paths.yaml`, 같은 셈법): **V1 12 → V2 8**.
상시 컨테이너(SCADA, 일회성 제외): V1 25 → V2 측정 대기(설계상 15: 설비·수집·브로커·Kafka·ZooKeeper·Flink JM·TM·InfluxDB·중계·FUXA·Grafana·Prometheus·Alertmanager·exporter·cAdvisor). 서비스 수(일회성 포함) V1 SCADA 29 → V2 19.

## 3. 층별 판단 — 합칠 것·뺄 것·남길 것

| 층 | V1 | V2 | 판단(무엇을 잃는가 → 결론) | 근거 |
|---|---|---|---|---|
| 수집 | EdgeX 10컨테이너 + Telegraf#1 | 수집기 1 | EdgeX 4.0 LTS 2027-03 종료(12개월 안), 후속 정식판 없음 → **강제 교체**. 장치 추상화(프로파일·메타데이터·명령 API)는 설비 7대·센서 12개를 Modbus 연결 하나로 읽는 이 라인에서 수집 외 사용처 없음 → 수집기 하나로(PLC·통신 방식이 늘어도 Telegraf 입력 블록 추가로 대응 — modbus 외 opcua 등 입력 있음). ※ 세션 4 에 "설비 1대"로 잘못 적었던 것을 정정(사용자 지적) | 05 §A, #107 |
| 수집 우회(lite) | 설비 MQTT 직발행 → Telegraf(lite) | 없음 | 본 경로가 이미 한 단계(설비→수집기→Kafka)라 가벼운 우회 길이 따로 있을 이유가 없음 → **제거**(중복) | `docker-compose.yml` profiles lite |
| 브로커 | EdgeX 내부 Mosquitto + EMQX | Mosquitto 1 | EMQX 5.8 OSS 2026-02-28 종료·이후 BSL → **강제 교체**. EdgeX 내부 버스는 EdgeX 와 함께 사라짐 → **2 → 1** | #48, 01 §2 |
| MQTT→Kafka 중계 | Telegraf#1 | 없음 | 수집기가 Kafka 에 바로 씀 → 되돌아가는 길 제거 | 구조 |
| 백본 | Kafka 3.9 | Kafka 4.3.1 | 3.9 는 2027-02-19 종료 → 같은 제품 지원판 고정. **MQTT 하나로 합치지 않는 이유**: 재처리(CAP-16)·소비자별 독립 진도가 필요하고, 합치면 Flink 를 직접 짠 탐지기로 바꿔야 함(급진안 C, 폐기 #57·#53) | 02 §0, FINAL §17 |
| 이상탐지 | Flink 1.20 세션(HA 없음) | Flink 2.2.1 + ZooKeeper HA | 다른 제품 6종은 엔진이 CEP·Z-Score 를 거부해 탈락(#109~#113). HA 는 사용자 확정 예외(#94). **ZooKeeper 를 따로 두는 이유**: Flink 공식 HA 는 ZooKeeper·Kubernetes 두 가지뿐(02 §3) | #107 |
| 저장 중계 + 알람 중계 | Telegraf#2·#3 | 중계기 1(Vector) | 두 중계를 한 프로세스로(패턴 P-E). 결과 동일·메모리 V1 3대 710 MiB → 45 MiB(#113) | #113 |
| 시계열 저장 | InfluxDB 2.7 | InfluxDB 2.9.1 | 2.7 지원 밖 → 지원판 고정. **PostgreSQL 로 합치지 않는 이유**: TimescaleDB(Apache 판)·pg_partman·QuestDB 는 질의 정답이나 24시간분 디스크 680~1,100 MB vs InfluxDB 19 MB(압축은 TSL 이라 금지) → ③ 효율 악화 | #117·#118·#119, EXP-TS |
| 업무 DB·그래프 DB | PostgreSQL 17 · Neo4j 5.26 | 그대로 | AI 층(담당 밖), Neo4j 는 사용자 고정 | QUESTIONS §1 AI 고정 |
| 알람 워커 | V1 워커 | 그대로 | 대안(Bento·Redpanda Connect) 결과 동일·효율 이득 미미 → 유지 | #119 |
| HMI | FUXA 1.3.4 | 그대로 | 보안판 이미 충족. 설비 직접 폴링은 남김(§4-③) | 03 §0 |
| 감시 | Prometheus 3.1·AM 0.28·exporter latest·cAdvisor 0.49 | 3.15·0.34.1·1.10.0·0.60.6 | 네 판 모두 지원 밖 → 지원판 고정. 줄일지는 E11(장애 탐지) 결과로 판단 — V1 은 0/2 | 05 §A, EXP-001 E11 |

## 4. 구조 재조립 대상 5개

| # | 대상 | V1 | V2 | 결론 | 실측 확인 |
|---|---|---|---|---|---|
| ① | 알람 되돌림 | Kafka → Telegraf#3 → EMQX(수집용 브로커) → FUXA, 12단계 | Kafka → 중계기 → Mosquitto(표시 전용) → FUXA, 8단계 | 단계 축소. **탐지기가 MQTT 로 바로 쏘지 않는 이유**: Flink 에 유지되는 MQTT 커넥터가 없고(직접 코드 = 금지 범위), 알람은 워커·저장도 Kafka 에서 받아야 함 | E1 p95·E2 — 측정 대기 |
| ② | 중계 5중 | EMQX·Telegraf×3·Kafka (+EdgeX 내부 버스·export) | Kafka·중계기 1·Mosquitto | 5 → 3 | E2·E3 — 측정 대기 |
| ③ | 설비 이중 폴링 | EdgeX·FUXA | 수집기·FUXA | **남김**: 운전 화면은 제어기를 직접 읽는 것이 현업 원칙(구조 분석서 §5·§11) — FUXA 를 MQTT 구독으로 바꾸면 브로커·수집기 장애 때 운전 화면이 멈춤. 일관성 비용은 E7 로 확인 | E7(V1 99.17 %)·R01 중 FUXA 영향 — 측정 대기 |
| ④ | 설비 쓰기 경로 3개 | FUXA(C1)·EdgeX core-command·AI 조치(C3, 운전원 C2 는 같은 백엔드) | FUXA·AI 백엔드 | EdgeX core-command(사용처 없음·인증 없는 쓰기 창구) 제거 → 3 → 2 | E12 접점 수 — 측정 대기 |
| ⑤ | 저장소 3개(+EdgeX DB) | InfluxDB·PostgreSQL·Neo4j·edgex-postgres | InfluxDB·PostgreSQL·Neo4j | edgex-postgres 제거(EdgeX 전용). 나머지 셋은 **남김**: 시계열은 디스크 실측(§3), 업무·그래프는 AI 층 | EXP-TS 디스크 |

## 5. 기능 대응표 (V1 부품 → 하던 기능 → V2 담당 → 확인 방법 → 결과)

| V1 부품 | 하던 기능 | V2 담당 | 확인 방법 | 결과 |
|---|---|---|---|---|
| plant-simulator | 가상설비·Modbus·/state·이상 주입·인터록 | 그대로(배속 600 설비) | 회귀 S14~S22 | 측정 대기 |
| edgex-device-modbus | 12태그 1초 폴링·정규화 | 수집기 inputs.modbus | S01 12태그 저장·raw 600건 표본(중복 0·1초 간격, 세션 4) | 표본 확인됨 · S01 측정 대기 |
| edgex-core-data·metadata·keeper·common-config | 장치 프로파일·메타데이터·설정 레지스트리(EdgeX 내부) | 수집기 설정 파일의 레지스터 지도(`v2/telegraf/ingest.conf`) | 12태그·단위 일치 | 측정 대기 |
| edgex-postgres | EdgeX 내부 저장·Store-and-Forward | 수집기 디스크 버퍼(`buffer_strategy = "disk"`) | R02 단절 10 s 유실 ≤ V1(중앙 120) | 측정 대기 |
| edgex-app-mqtt-export | `edgex/telemetry` MQTT 발행(수업 자료·도구가 구독) | 수집기 outputs.mqtt(같은 토픽·EdgeX Event v3 모양) | 토픽 구독 후 V1 기록(`experiments/REC-V1/mqtt_edgex_telemetry.jsonl`)과 모양 대조 | **확인(세션 4)**: 같은 토픽·장치·프로파일·이벤트당 계측 12개·값 항목(resourceName·value·units·valueType) 동일. 차이 1개: EdgeX 가 붙이던 고유 번호 `id`(이벤트·값) 없음 — 이 토픽을 읽는 코드(`scripts/verify.py`·`reference-style-architecture.py`)와 수업 자료 어디도 `id` 를 읽지 않음 |
| edgex-mqtt-broker | EdgeX 내부 메시지 버스 | 없음(EdgeX 와 함께 불필요) | — | 해당 없음 |
| edgex-core-command | 장치 쓰기 REST(사용처 없음, 인증 없음) | 없음 — 제거가 보안 이득 | E12 접점, G7 | 측정 대기 |
| edgex-ui | EdgeX 장치 화면(장치 목록·현재 값 조회) | 현재 값: FUXA P&ID·Grafana 01 공정 화면. 장치 정의: 수집기 설정(`v2/telegraf/ingest.conf` 레지스터 지도) | verify.py scada·storage 단계 | 측정 대기 |
| emqx | 계측·알람 MQTT 중계, 대시보드(접속 상태), Prometheus 지표 | Mosquitto(계측 사본·최근알람). 접속 상태는 브로커 지표 → Grafana 04 운영 패널·경보(갈래 15) | S23 알람 표시, 토픽 구독, 브로커 정지 시 경보(E11) | 측정 대기 |
| telegraf-bridge(#1) | MQTT → Kafka raw | 없음(수집기가 Kafka 에 바로) | S01·completeness | 측정 대기 |
| telegraf-bridge-lite | EdgeX 우회 경량 수집 | 없음(본 경로가 같은 역할) | — | 해당 없음 |
| kafka·kafka-init | 백본·토픽 4개 | Kafka 4.3.1·같은 토픽 스크립트 | 토픽 목록, R03 | 기동 확인(4토픽 흐름) · R03 측정 대기 |
| flink-jobmanager·taskmanager·submitter·model-trainer | 규칙·Z-Score·CEP·ONNX 탐지 | Flink 2.2.1+HA(+ZooKeeper), V1 SQL·모델 그대로 | S02~S08 70건, R05 자동 복귀 | 벤치 70/70·잡 자동 복귀(#107) · 전체 스택 측정 대기 |
| telegraf-sink(#2) | Kafka 4토픽 → InfluxDB(최소 1회 전달) | 중계기(Vector, 전달 확인 켬) | S01 저장·R06 | 기동 확인(세션 4, 401 오류 수정 뒤) · R06 측정 대기 |
| alert-republisher(#3) | 알람 → MQTT latest-alert(FUXA 구독) + 태그별 토픽(구독처 없음, 갈래 9) | 중계기(Vector)가 latest-alert 를 냄 | S23·E1 | 측정 대기 |
| influxdb | 공정 이력 | InfluxDB 2.9.1 | S01·E7 | 기동 확인 · 측정 대기 |
| fuxa·fuxa-provisioner | 운전 화면·C1 조작·최근 알람 | 그대로(브로커 주소만 mqtt) | S14·S23·verify.py scada | 측정 대기 |
| grafana | 추세·이력 화면 | Grafana 13.2.2 | 대시보드 질의 | 측정 대기 |
| prometheus·alertmanager·kafka-exporter·cadvisor | 운영 지표·경보(E11) | 지원판 4개 | E11 ≥ V1(0/2) | 측정 대기 |
| **사람이 쓰는 기능** | 수업 자료의 `edgex/telemetry` 구독(`ai-web/public/system-guide.html`, `docs/소스코드로_…설명.html`, `docs/journal/07`) | 수집기 MQTT 사본 | 토픽 구독 | 측정 대기 |
| 〃 | `scripts/verify.py`(EdgeX 정규화 확인 포함) | EdgeX 단계는 수집기 확인으로 대체 필요 | verify.py 실행 | 측정 대기 |
| 〃 | 수업 3차시 EdgeX 장치 프로파일(장치를 파일로 정의해 수집) | 수집기 장치 정의(`ingest.conf` 의 레지스터 지도: 태그·주소·자료형·단위) — 같은 개념을 V2 파일로 가르침 | 파일 대조(12태그·단위) | 측정 대기 |

## 6. 스택 조합안 (남는 층에서만)

남는 층 중 제품을 고를 수 있는 곳은 **수집기**와 **중계기** 둘이다(백본·탐지·저장·브로커·HMI·감시는 §3 의 강제 교체·실측 결과로 이미 정해짐).

| 안 | 수집기 | 중계기 | 컨테이너(SCADA 상시) | 이미 있는 증거 | 판단 |
|---|---|---|---|---|---|
| A 보수안 | Telegraf 1.40 | Telegraf 1.40 ×2(저장·알람 따로, V1 설정 그대로) | 16 | V1 중계 3대 710 MiB(#111). 1.40 판 중계 재측정 없음 | 경로 격리는 좋지만 중계 2대 = 중복 |
| **B 효율안(선택)** | Telegraf 1.40 | Vector 0.58 1대 | 15 | Vector 결과 동일·45 MiB·알람 p95 793 → 37 ms(#113). Telegraf 는 V1 이 이미 쓰는 제품(수업 연속성), Modbus·Kafka·MQTT·디스크 버퍼 모두 OSS | 중복 없음, ③ 메모리 15.8배↓ |
| C 수집 교체안 | benthos-umh 0.16 | Vector 0.58 | 15 | 수집 1,356/1,356·p95 1.36 ms(#107). 디스크 버퍼·EdgeX 모양 MQTT 사본 미확인 | 컨테이너 수 같음, B 대비 확인된 이득이 지연뿐(수집 지연은 알람 경로에서 초 단위 대비 ms) → 결정적 이득 없음, 기준 유지 성격으로 B |

선택: **B**. 규칙 근거 — ③ 에서 A 대비 중계 컨테이너 1개·메모리 대폭 절감, C 와는 컨테이너 동수이고 C 의 추가 이득은 결정을 바꿀 크기가 아님(§1 ③ "미묘하면 기준 유지": 수집기는 V1 계열 제품 유지). 이 선택은 V2 전체 측정에서 ② 가 V1 보다 나쁘지 않을 때만 확정한다.

## 7. V2 조립 중 발견해 고친 내부 오류 (STABILITY 로 옮김)
- InfluxDB 2.9.1 초기 설정 반복 실패: `/etc/influxdb2` 가 이름 없는 볼륨이라 같은 이름 컨테이너 재생성 때 V1 컨테이너의 CLI 설정(2026-09-28 15:51 생성, `default` 항목)이 넘어옴 → V2 전용 이름 볼륨 `influx-config-v2`.
- 중계기(Vector 0.58) InfluxDB 401 → 저장 유실: Vector 0.58 은 설정 파일 `${VAR}` 치환이 기본 꺼짐(`--help` 원문), 토큰·org 가 글자 그대로 전송됨(가로챈 요청으로 확인) → `VECTOR_DANGEROUSLY_ALLOW_ENV_VAR_INTERPOLATION=true`. 같은 기회에 전달 확인(acknowledgements)을 켜 V1 Telegraf#2 의 최소 1회 전달 보장과 같게.
- 수집기 디스크 버퍼 경로 권한: `/var/lib/telegraf` 는 이미지에 없어 권한 오류 → `/tmp/telegraf-buffer`(세션 3 말 반영, 세션 4 기동 확인).

## 7-1. 리서치 반영 결정 (06 참조 구조 · 07 감시 경량화 · 08 부품 안정성, 모두 1차 출처)

| 결정 | 근거(리서치 파일) | 반영 |
|---|---|---|
| Alertmanager 유지 | Grafana 내장 알림으로 대체 가능하나, 빼도 줄어드는 것은 작은 컨테이너 1개이고 경보 규칙 이전이 필요 → ③ "미묘하면 기준 유지" | 그대로 |
| VictoriaMetrics+vmalert 로 교체 안 함 | vmalert 도 알림에 Alertmanager 필요, 무료판 장기지원판 없음(07) | — |
| 브로커 감시 = 브로커 생존(cAdvisor) + 수집기·중계기의 브로커 쓰기 오류 | Mosquitto 는 Prometheus 지표 없음(07). $SYS 구독(mqtt_consumer)은 1.40.1 에서도 브로커 정지 때 프로세스 종료 결함 열림(#17564, 08) → 수집기 안에 두지 않음. 전용 exporter 는 2021 이후 릴리스 없음(07) | 규칙 MQTTBrokerDown·MQTTPublishErrors, Grafana 04 패널 교체, 수집기 `inputs.internal`→`:9273` |
| 탐지 잡 정지 감지 | `flink_jobmanager_numRunningJobs` 실측 확인(V2 Prometheus 조회) | 규칙 FlinkJobsNotRunning(V1 E11 미탐 수정) |
| 중계기 정지 감지 | Vector `internal_metrics`+`prometheus_exporter`(07), up==0 | job relay |
| 수집기 기동 순서 | outputs.mqtt 는 기동 때 연결 실패를 재시도하지 않고 종료(08, 코드 확인) | `depends_on: mqtt healthy`, Kafka 출력 `startup_error_behavior = "retry"` |
| Kafka 쓰기 멱등 | `idempotent_writes` 는 클라이언트 재시도 중복만 막음, 배치 재전송 중복은 남음(08, PR #19735) | 켬(대장 S4 방향) — R03 에서 V1 중복 중앙 150 과 비교 |
| MQTT 연결 유지 | outputs.mqtt keep_alive 기본 0, README 가 Mosquitto 에 0 아닌 값 권고(08) | `keep_alive = 30` |
| 중계기 MQTT 알람 전달 보장 | Vector 0.58 MQTT 싱크는 PUBACK 전에 전달 표시(08, 코드 확인) — "받은 뒤에만 넘긴다"는 MQTT 경로에선 성립 안 함 | 주석 정정, R01 에서 화면 알람 영향 실측 |
| Flink 싱크 정확히 1회는 켜지 않음 | 켜면 트랜잭션 시간 한도 조정 필요, Telegraf 소비는 read_committed 설정 불가(08). 재시작 중복 1건은 알람 워커가 내용 해시로 결합(#107) | 최소 1회 유지(기록) |
| ONNX 잡 체크포인트 | 잡 설정 조회 interval=Long.MAX(꺼짐) — SQL 잡만 `SET` 으로 켜져 있었음(V1 도 같음) | V2 제출 설정 `client-config.v2.yaml` 에 10 s, 4잡 모두 체크포인트 완료 확인(대장 S17) |
| 중계기 로그 잡음 | InfluxDB 싱크 `version` 미지정 경고가 재시작마다 반복 | `version: "2"`(검사기 통과 뒤 적용, 경고 0) |
| Flink 지표 이름 충돌 경고(S14) | Flink 2.2.1 에도 미수정(FLINK-35321·37559 열림, 수정 PR 은 master 만, 08) | 대장 S14 "남김(상류 미수정)" — V2 로그에서 건수 실측 |

## 7-2. 땜빵 점검표 (V1 과 달라진 V2 설정·코드 전수, 세션 4 — 작업하며 발견되면 추가)

분류: **근본** = 원인을 없앰 / **땜빵** = 증상만 막음(근본 수정 계획 필수) / **부분** = 원인 일부만.

| # | 위치 | 한 일 | 분류 | 근본 원인 · 근본 수정 | 상태 |
|---|---|---|---|---|---|
| 1 | `docker-compose.v2.yml` influx `influx-config-v2` | 설정 폴더를 V2 전용 이름 볼륨으로 | 근본 | 이름 없는 볼륨이 옛 컨테이너 설정을 물려받음 — 공식 compose 문서 구성(데이터·설정 둘 다 볼륨) | 완료(S15) |
| 2 | `flink/conf/client-config.v2.yaml` | ONNX 잡 체크포인트 10 s | 근본 | 제출 설정에 항목 누락 | 완료(S17) |
| 3 | `v2/vector/vector.yaml` acknowledgements | InfluxDB 싱크 쓰기 성공 뒤 읽은 위치 넘김 | 근본 | V1 최소 1회 전달 보장 복원. MQTT 싱크는 PUBACK 전 표시(Vector 한계, 리서치 08) — R01 에서 화면 영향 실측 | 완료 |
| 4 | `v2/prometheus/*`, 수집기 `inputs.internal`, 중계기 지표 | 탐지 잡 정지·중계기 정지·브로커 상태 감시 | 근본 | 감시 대상·규칙이 없었음(V1 E11 0/2) | 완료, E11 로 확인 |
| 5 | `harness/e2e/baseline.sh` | 이름표를 기본값 뒤에 읽음 | 근본 | 변수 순서 오류(#125) | 완료 |
| 6 | `scripts/verify.py` EdgeX 단계 | 수집 확인 실패를 실패로 셈 | 근본 | V1 은 실패를 "lite 건너뜀 = 통과"로 셈 — V2 확인까지 가리고 있었음(세션 4 발견) | 완료 |
| 7 | 설비 전용망 `plant-field` 별칭 | 수집기가 전용망 이름으로 설비를 읽음 | 근본 | 설비 이름이 백본망 주소로 풀려 R02 때 설비 읽기도 끊김(로그 172.24.0.13 i/o timeout) | 파일 준비, 측정 뒤 적용(S18) |
| 8 | 수집기 `depends_on: mqtt` | 브로커가 먼저 떠야 수집기 기동 | **땜빵** | 수집기가 Kafka+MQTT 두 곳에 씀 → outputs.mqtt 가 기동 때 연결 실패면 종료(리서치 08). 근본: 계측 MQTT 사본을 중계기(브리지)로 옮겨 수집기는 Kafka 만 | V3 #6 |
| 9 | 수집기 `buffer_directory = /tmp/telegraf-buffer` | 권한 오류 회피 | **땜빵** | 컨테이너 쓰기 계층이라 컨테이너 재생성 때 버퍼 소실. 근본: 이미지 사용자(telegraf)가 쓸 수 있는 전용 이름 볼륨 | V2 확정 전 수정 |
| 10 | 중계기 `VECTOR_DANGEROUSLY_ALLOW_ENV_VAR_INTERPOLATION` | 환경변수 치환 켬 | **땜빵에 가까움** | Vector 권장은 비밀값 백엔드. 근본: compose secrets(환경변수에서) → Vector `secret` directory 백엔드 `SECRET[...]` | V2 확정 전 수정 |
| 11 | 수집기 `idempotent_writes` | 클라이언트 재시도 중복 방지 | **부분** | 배치 재전송 중복은 남음(PR #19735 미병합, 리서치 08). R03 중복을 V1(중앙 150)과 비교 | 측정 대기 |
| 12 | Flink HA `storageDir` 를 체크포인트 볼륨 안에 | 별도 볼륨은 root 소유라 못 씀 | 설계 선택 | 같은 수명(체크포인트와 함께)이라 기능상 문제 없음. 분리하려면 이미지에 폴더를 flink 소유로 만들고 볼륨 연결 | 기록 |
| 13 | `fuxa/provision.py` `MQTT_URL` | 브로커 주소 환경변수 | 근본(설정화) | 값이 없으면 V1 과 같음 | 완료 |
| 14 | `v2/telegraf/sink.conf` `kafka_version = "3.0.0"` | Telegraf 소비기의 Kafka 4.x 호환 | 해당 없음 | V2 실행에 안 쓰임(중계 벤치 `harness/pipebench` 만 참조) | 기록 |
| 15 | 중계기 InfluxDB `version: "2"` | 명시 | 근본 | 미지정 경고가 로그를 덮음 | 완료 |

## 8. 측정 계획 (결정을 바꿀 수 있는 것만)
- 전체 측정 `STRUCT=V2 sh harness/e2e/baseline.sh EXP-002 V2`: P1(E3·E7·E12·R09) → P2(E1 3묶음) → P3(R01·R02·R03 각 3회, R06·R07·R08·R11·E11).
- 회귀 `STRUCT=V2 sh harness/e2e/regression.sh EXP-002 V2`(S01~S08·S14~S22·S24·S25). V2 가 전부 통과하면 V1 회귀는 결정을 바꾸지 못하므로 생략, 실패 항목이 있으면 그 항목만 V1 에서 잰다.
- 고장→알람 `fault_onset.py`(배속 600, 10 s 이내).
- E2 복잡도 `e2_complexity.py V2`.
