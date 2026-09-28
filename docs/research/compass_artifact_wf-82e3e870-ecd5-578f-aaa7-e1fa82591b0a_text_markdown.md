# IoT/SCADA 프로토타입 V1 구조 검증 보고서: 데이터 경로 미로와 기능 중복 점검, 최소 구성 제안 (2026-09 기준)

**판정: V1은 목적 흐름(수집 → 이상탐지 → 알람 표시 → 이력 조회 → 조사·승인 → 제어 → 운영 감시)은 맞지만, 12태그 단일 머신 규모로 보면 "중계 계층이 미로처럼 꼬였고 기능이 겹친다". 핵심은 세 가지다. 알람이 MQTT→Kafka→Flink→Kafka→Telegraf→MQTT로 되돌아오는 경로, Telegraf 3개와 Kafka·EMQX가 만든 이중 백본, 그리고 알람 상태와 제어 경로에 "주인"이 없다는 점이다. 컴포넌트를 약 30개에서 약 12개로, 알람→화면 전달을 약 8 hop에서 2 hop으로 줄여도 모든 목적 기능을 유지할 수 있다.** 다만 "운전 HMI(FUXA)와 업무·AI UI(Vue)의 분리", "HMI의 설비 직접 폴링", "AI 명령의 별도 승인·재검사·read-back 경로"는 중복이 아니라 현업 원칙에 맞는 분리이므로 유지해야 한다.

## TL;DR

- **미로·중복 판정: 예.** 알람이 화면에 오기까지 약 8 hop 왕복하고, 5개 컴포넌트(EMQX, Telegraf×3, Kafka)가 사실상 같은 "메시지 중계"를 한다. 제어 경로는 3개(FUXA·Vue·Pilot)로 갈려 있고 알람 상태의 단일 관리 지점이 없다. 저장소 3개도 12태그 규모에서는 PostgreSQL 하나로 합칠 수 있다. 여기에 EMQX는 5.9부터 BSL 1.1이고, EMQ 공지에 따르면 5.8 오픈소스판은 2026-02-28에 공식 EOL이 되어 버그 수정·보안 패치가 끊기므로 라이선스 제약 때문에라도 교체가 필요하다.
- **추천 구성(대안 C, MQTT/UNS 단일 백본):** 가상설비 → [FUXA 직접 Modbus(운전)] + [Telegraf 1개(분석용 읽기)] → Mosquitto 2.1.x → Python 탐지기(상·하한/Z-Score/CEP/ONNX) → advisory 토픽 → FUXA·Vue. 저장은 PostgreSQL 하나(선택 시 TimescaleDB Apache 에디션)에 업무·시계열·설비 관계(재귀 CTE)를 모두 둔다. 운영 감시는 Grafana(이력 추세 + 운영 패널 + Grafana Alerting)와 Docker healthcheck로 한다. Kafka·Flink·EdgeX·EMQX·InfluxDB·Neo4j·Prometheus·Alertmanager와 Telegraf 2개를 제거하거나 선택 모듈로 돌린다.
- **유지해야 할 분리:** FUXA(운전 HMI, Purdue L2)와 Vue(업무·AI UI)는 역할을 다시 나눠 화면 중복만 없앤다. 제어는 3경로에서 2경로(운전원 FUXA 직접, 승인된 AI 명령은 Pilot 경유)로 줄이고, 인터록은 PLC 역할(시뮬레이터) 안에 둔다. 알람은 "공정 알람 = FUXA 알람 엔진"과 "분석 advisory = PostgreSQL alarm-core"로 클래스별 소유자를 정한다. 모든 결론은 문헌 기준이며 성능은 실측 전이다. 7장의 실험으로 판정해야 한다.

---

## 1. 핵심 결론 (5줄)

1. **미로:** 맞다. 알람 표시가 MQTT→Kafka→Flink→Kafka→Telegraf#3→MQTT→FUXA로 되돌아오는 것은 12태그 규모에서 얻는 것(재처리·다중 소비자)보다 hop·장애점·설정면이 더 크다.
2. **중복:** 맞다. 메시지 중계 5중(EMQX·Telegraf×3·Kafka), 화면 3중(FUXA·Vue·Grafana), 설비 쓰기 3중(FUXA·Vue·Pilot), 저장 3중이 겹친다. 반면 FUXA/Vue 분리와 HMI 직접 폴링은 "겹침"이 아니라 현업 원칙이다.
3. **강제 교체:** EMQX(5.9+ BSL, EMQ 공지상 5.8 오픈소스판은 2026-02-28 EOL로 보안 패치 중단)는 OSI 조건에 맞지 않는다. InfluxDB 3 Core는 기본 쿼리 파일 한도(432개, 기본 설정에서 최대 72시간)와 Flux 미지원이 있고, FUXA DAQ도 InfluxDB 3을 아직 지원하지 않는다(기능 요청 상태).\[1\] 그래서 이력 저장소로 적합성이 낮다.
4. **추천:** 대안 C(Mosquitto 단일 백본 + Python 탐지기 + PostgreSQL 단일 저장 + FUXA 운전 HMI + Vue 업무 UI + Grafana)는 문헌 기준 17/20점이다. 알람→화면 2 hop, 컨테이너 약 11~12개(추정)다.
5. **검증:** 성능 수치는 측정하지 않았다. 7장 실험(알람→화면 p50/p95, 장애 주입 시 유실·중복, HMI 값과 이력 값의 일관성)으로 확정해야 한다.

---

## 2. 표 1: 기능 중복 매트릭스

범례: **●** = V1에서 실제 담당, **○** = 기능은 있으나 V1에서 쓰지 않음(잠재 대체 수단), 빈칸 = 해당 없음. "겹침" 행은 ●가 2개 이상이거나 ●+○로 대체 가능한 곳이다.

### 표 1a. 수집·중계·처리·저장

| 컴포넌트 | 설비 읽기 | 설비 쓰기 | 메시지 중계 | 데이터 변환 | 이벤트 로그/재처리 | 규칙 탐지 | 패턴 탐지(CEP) | ML 추론 | 시계열 저장 |
|---|---|---|---|---|---|---|---|---|---|
| EdgeX (device-modbus, app-service) | ● | ○ (core-command) | ○ (내부 버스) | ● | | ○ (eKuiper 연동) | | | ○ |
| EMQX | | | ● | ○ (룰 엔진) | | ○ (룰 SQL) | | | |
| Telegraf#1 (MQTT→Kafka) | ○ (inputs.modbus) | | ● | ● | | | | | |
| Telegraf#2 (Kafka→InfluxDB) | | | ● | ● | | | | | |
| Telegraf#3 (Kafka→MQTT) | | | ● | ● | | | | | |
| Kafka | | | ● | | ● | | | | |
| Flink 규칙 작업 | | | | ● (clean) | ○ (체크포인트) | ● | ● | | |
| Flink ONNX 작업 | | | | ○ | | | | ● | |
| InfluxDB | | | | | | | | | ● |
| PostgreSQL | | | | | ○ (outbox 테이블) | | | | ○ (TimescaleDB Apache) |
| Neo4j | | | | | | | | | |
| FUXA | ● | ● | ○ (MQTT 발행) | | | ○ (HH/H/L 알람) | | | ○ (DAQ: SQLite/InfluxDB/TDengine) |
| Vue (+백엔드) | | ● | | | | | | | |
| Grafana | | | | | | | | | |
| Prometheus | | | | | | | | | |
| Alertmanager | | | | | | | | | |
| LiteLLM | | | | | | | | | |
| LangGraph | | | | | | | | | |
| 알람 접수 워커 | | | | ○ | | | | | |
| Pilot | ● (/state, read-back) | ● | | | | | | | |
| **겹침** | **3중(EdgeX·FUXA·Pilot)** | **3중(FUXA·Vue·Pilot)** | **5중 체인** | **5중** | 단일(Kafka) | Flink + FUXA○ | 단일 | 단일 | InfluxDB + FUXA○ + PG○ |

### 표 1b. 화면·알람·운영·업무

| 컴포넌트 | 업무 저장 | 관계 저장 | 실시간 화면 | 추세·이력 화면 | 알람 표시 | 알람 상태 관리 | 운영 지표 수집 | 운영 경보 | 승인 워크플로 |
|---|---|---|---|---|---|---|---|---|---|
| EdgeX | | | | | | | ○ (자체 지표) | | |
| EMQX | | | | | | | ○ (자체 대시보드·지표) | | |
| Telegraf (3개) | | | | | | | ○ (docker 입력) | | |
| Kafka / Flink | | | | | | | ○ (JMX·REST) | | |
| InfluxDB | | | | ○ (Explorer) | | | | | |
| PostgreSQL | ● | ○ (재귀 CTE, Apache AGE) | | | | ○ | | | ○ (체크포인터 저장) |
| Neo4j | | ● | | | | | | | |
| FUXA | | | ● | ○ (DAQ 차트) | ● | ○ (확인·이력) | | | |
| Vue (+백엔드) | | | ● (공정 그림) | ○ | ● | ● (확인 버튼) | | | ● (UI) |
| Grafana | | | ○ | ● | ○ | | | ○ (Grafana Alerting) | |
| Prometheus | | | | | | | ● | ● (규칙 평가) | |
| Alertmanager | | | | | | | | ● (그룹·억제·라우팅) | |
| LiteLLM | | | | | | | | | (LLM 게이트웨이, 해당 기능 없음) |
| LangGraph | ○ | | | | | | | | ● (검토 대기·재개) |
| 알람 접수 워커 | ● (사건) | | | | | ● (등록·결합) | | | |
| Pilot | ● (조치 이력) | | | | | | | | ● (조건 재검사) |
| **겹침** | PG 단일 | Neo4j + PG○ | **FUXA·Vue 2중** | Grafana + FUXA○ | **FUXA·Vue 2중** | **Vue·워커·FUXA○: 주인 없음** | Prometheus + 자체 지표○ | Prom/AM + Grafana○ | 층위 분리(중복 아님) |

**해석**
- 진짜 중복은 **메시지 중계·변환(5중)**, **화면(실시간·알람 2중)**, **설비 쓰기(3중)**, **저장소(3개)**다.
- **승인 워크플로**는 Vue(UI)·LangGraph(상태·재개)·Pilot(실행 전 재검사)가 층위별로 나눠 맡는 구조라 중복이 아니다.
- **알람 상태 관리**는 중복보다 오히려 "공백"이 문제다. 확인(ack)은 Vue에, 사건 등록은 워커에, 공정 한계 알람 능력은 FUXA에 흩어져 있고 ISA-18.2 상태(발생·확인·복귀·셸빙)를 책임지는 곳이 없다.

---

## 3. 표 2: 컴포넌트별 판정

| 컴포넌트 | 하는 일 | 겹치는 대상 | 현업에서 두는 이유 | 판정 | 제거 시 잃는 것 | 대체 방법 | 근거(유형·날짜) |
|---|---|---|---|---|---|---|---|
| EdgeX (device-modbus→MQTT) | Modbus 폴링, 이벤트 변환·발행 | FUXA 폴링, Telegraf inputs.modbus | 이기종 장치 추상화·장치 프로파일(수십~수천 장치) | **제거 가능** | 장치 프로파일 추상화 학습, core-command 경유 쓰기 | Telegraf 1개(inputs.modbus→outputs.mqtt) 또는 FUXA MQTT 발행 | EdgeX 문서(eKuiper 연동, 재단·1차) |\[2\]
| EMQX | MQTT 브로커 | Kafka(중계) | 대규모 연결·클러스터·룰 엔진 | **교체 필수(라이선스)** | 룰 엔진, 대시보드 | Mosquitto 2.1.x(내장 WebSocket), 또는 NATS 2.15(MQTT 3.1.1) | EMQ 발표 2025-05-07(벤더), EMQX 5.8 EOL 공지 2026-02-28(벤더) |\[3\]\[4\]\[5\]
| Telegraf#1 (MQTT→Kafka) | 브로커 간 다리 | Telegraf#2·#3, 브로커 브리지 | 이종 백본 연결 | **제거 가능** | 없음(백본 단일화 시) | 백본 단일화로 불필요 | 구조 분석 |
| Telegraf#2 (Kafka→InfluxDB) | 이력 적재 | Telegraf#1 | 저장 싱크 | **통합 가능** | 없음 | 단일 Telegraf에서 outputs.postgresql 동시 출력(1회 폴링, 2개 싱크) | 구조 분석, [Telegraf 플러그인 문서 본 조사 미재확인] |
| Telegraf#3 (Kafka→MQTT) | 알람 역중계 | 알람 워커 | 없음(순수 다리) | **제거 가능** | 없음 | 탐지기가 MQTT에 직접 발행 | 구조 분석 |
| Kafka 4.2.x | 영속 로그, 재처리, 다중 소비자 | MQTT 브로커 | 재처리·다중 팀 소비·버퍼링·장애 격리 | **조건부**(재처리 교육이 목적이면 유지) | 오프셋 기반 재처리, 소비자별 독립 진도, 대량 버퍼 | ① DB 이력 기반 재생 ② NATS JetStream 스트림 재생 | Apache Kafka 4.2.0 발표 2026-02-17(재단·1차) |\[6\]
| Flink 규칙 작업(2.2.1) | 상·하한, Z-Score, CEP | FUXA 알람(상·하한) | 이벤트타임·워터마크·체크포인트·정확히 한 번 | **조건부 → 대체 권장** | 워터마크·late event 처리 표준화, 체크포인트 복구 | Python 서비스(또는 Quix Streams/eKuiper/Proton) | Flink 2.2.1 발표 2026-05-15(재단·1차) |\[7\]
| Flink ONNX 작업 | Autoencoder 추론 | 규칙 작업(같은 입력) | 대량 병렬 추론 | **통합 가능** | 작업별 독립 확장 | 같은 Python 프로세스에서 onnxruntime 사용 | 구조 분석 |
| InfluxDB | 시계열 저장 | PostgreSQL(+Timescale), FUXA DAQ | 고속 시계열·보존 정책 | **통합 가능** | 시계열 전용 함수, Flux(3에서는 이미 없음) | PostgreSQL(+TimescaleDB Apache: 하이퍼테이블·time_bucket) | InfluxDB 3 Core 문서(벤더·1차): 파일 한도 432, Flux 미지원 |\[8\]\[9\]
| PostgreSQL | 사건·승인·조치 이력 | — | 트랜잭션·감사 | **필수(중심 저장소로 승격)** | — | — | — |
| Neo4j | 설비 지식그래프 | PostgreSQL 관계 테이블 | 대규모 그래프 탐색, Cypher, GDS | **조건부 → 통합 권장** | Cypher 원형, 그래프 시각화, LLM 도구 연동 편의 | 재귀 CTE(설비 6개 규모) 또는 Apache AGE 1.7.0(openCypher, PG 11~18) | Apache AGE 릴리스 노트 2026-01-21(재단·1차) |\[10\]\[11\]
| FUXA 1.3.4 | 운전 HMI, 직접 폴링·조작, 알람 | Vue(화면·조작), Grafana(추세) | Purdue L2 운전 화면은 제어기와 직결 | **필수(운전 HMI 전담)** | — | — | FUXA 릴리스 v1.3.4(2026-08-12, 프로젝트·1차) |\[12\]
| Vue 대시보드 | 공정 그림·조작·알람 확인·AI UI | FUXA | 업무(사건·승인·감사) UI는 운전 화면과 분리 | **통합 가능(역할 축소)** | 공정 그림·기동/정지 중복 제거 | 업무·AI·감사 전용으로 축소, FUXA 화면 링크 | NIST SP 800-82r3(2023-09, 정부·1차) |
| Grafana | 이력 추세 + 운영 지표 | FUXA DAQ 차트 | 엔지니어 분석·임의 기간 비교·운영 대시보드 | **조건부 유지(권장)** | 임의 쿼리 추세, 운영 패널 | FUXA 추세만으로 운전 추세는 가능 | FUXA 위키·이슈(프로젝트·커뮤니티) |
| Prometheus | 운영 지표 수집 | 각 컴포넌트 자체 지표, Docker healthcheck | 지표 이력·PromQL·표준 exporter | **조건부(선택 모듈)** | 지표 장기 이력, PromQL | Docker healthcheck + Mosquitto $SYS + 탐지기 heartbeat → Grafana | 구조 분석 |
| Alertmanager | 운영 경보 그룹·억제 | Grafana Alerting | 다수 경보의 그룹·억제·온콜 라우팅 | **제거 가능** | 억제(inhibition)·그룹 정교함 | Grafana Alerting | 구조 분석 |
| LiteLLM | LLM 게이트웨이 | — | 모델 교체·비용 추적 | **조건부 유지** | 모델 교체 편의 | 단일 모델이면 SDK 직접 호출 | [본 조사 미재확인] |
| LangGraph | 검토 대기·재개 | Vue(승인 UI) | 사람 승인 대기(interrupt)와 상태 보존 | **유지** | 중단·재개 상태 관리 | — | [본 조사 미재확인] |
| 알람 접수 워커 | 사건 등록·중복 결합 | Vue 확인 버튼 | 알람→사건 전환 | **통합(alarm-core로 승격)** | — | 백엔드 API 안의 alarm-core 모듈로 ISA-18.2 상태 소유 | ISA-18.2-2016(표준 요약) |\[13\]
| Pilot | 승인 명령 재검사·실행·read-back | FUXA·Vue 쓰기 | 상위 시스템 쓰기 최소권한 관문 | **필수** | — | — | NIST SP 800-82r3, IEC 62443 개념 |

---

## 4. 표 3: hop별 판정

| 구간 | V1 방식 | 현업 관행 | 판정 | 개선안 | 근거 |
|---|---|---|---|---|---|
| H1 설비→수집 | EdgeX device-modbus 폴링(분석용)과 FUXA 폴링(운전용) **이중 폴링** | HMI/SCADA는 제어기를 직접 읽고 쓰는 것이 일반적이다. NIST SP 800-82r3는 제어 센터가 "중앙 알람, 추세 분석, 리포팅"을 맡는 구조를 설명한다. 히스토리안 수집은 별도 경로(수집 서버·DMZ)로 두는 것이 보통이다 | **이중 폴링 자체는 조건부 허용**(분리 원칙). 단 수집기는 1개로 | 운전: FUXA 직접. 분석: Telegraf 1개(읽기 전용). 대안 B에서는 FUXA가 MQTT로 재발행해 읽기를 일원화 | NIST SP 800-82r3(2023-09-28, 정부·1차) |\[14\]\[15\]
| H2 EdgeX 내부 → MQTT export | device → 메시지 버스 → app-service → 브로커 | 소규모에서는 수집기가 브로커로 직접 발행 | **제거** | Telegraf outputs.mqtt 직접 발행 | 구조 분석 |
| H3 EMQX→Telegraf#1→Kafka raw | 브로커 간 다리 | UMH Classic은 MQTT(HiveMQ)↔Kafka(Redpanda) 브리지를 둔다. 다만 대규모·다중 사이트 전제다 | **제거(단일 백본)** | Mosquitto 단일, 재처리가 필요하면 NATS JetStream | UMH 문서(벤더·1차 사례) |\[16\]
| H4 Kafka raw→Flink×2→Kafka | 규칙·ML 병렬 작업이 각자 Kafka로 되돌림 | 스트림 처리 결과를 토픽으로 되돌리는 것은 대규모 표준 패턴이다 | **통합** | Python 탐지기 1개가 MQTT를 구독하고 결과를 MQTT/DB로 발행 | Flink 2.2.1(재단), Quix(벤더) |
| H5 Kafka→Telegraf#2→InfluxDB | 3개 토픽 적재 | 싱크 커넥터 | **단순화** | 원시 데이터는 Telegraf가 폴링 시 PostgreSQL에 바로 적재. score는 탐지기가 배치로 적재 | 구조 분석 |
| H6 Kafka alerts→Telegraf#3→EMQX→FUXA | 역방향 다리(약 8 hop 왕복) | HMI는 알람 서버·제어기에서 직접 받는다 | **제거(핵심 개선)** | 탐지기 → Mosquitto(`plant/+/advisory/#`, retained) → FUXA/Vue: 2 hop | ISA-18.2-2016, Fermilab ICARUS 사례(arXiv 2509.18392, 2025-09) |\[17\]
| H7 Kafka alerts→워커→PostgreSQL | 사건 등록 | 알람 저널·사건 관리 DB | **유지(소유자 명확화)** | alarm-core가 MQTT advisory를 구독(QoS1 영구 세션)해 PG에 상태 저장 | ISA-18.2 |
| H8 제어 3경로 | FUXA 직접 / Vue 백엔드 / AI→Pilot | 운전원은 HMI에서 직접 조작하고, 상위 시스템 쓰기는 제한된 관문을 거친다. 인터록은 제어기 레벨에 둔다 | **3→2로 축소** | Vue 백엔드 쓰기 제거. Pilot만 허용목록 기반 자동 쓰기 | NIST SP 800-82r3, 벤더 해설(Shieldworkz, 이해관계 있음) |\[18\]
| H9 운영지표 → Prometheus → Alertmanager | 3단 | 대규모 IT 운영 표준 | **축소** | healthcheck + $SYS + heartbeat → Grafana(Alerting) | 구조 분석 |
| H10 사건 → Agent(LiteLLM, Neo4j) → LangGraph → Pilot | AI 조사·승인 | 사람 승인(HITL), AI는 버튼을 누르지 않는다 | **유지(Neo4j만 PG로)** | 지식그래프를 PG 재귀 CTE/AGE로 | Apache AGE(재단) |

**hop 제거 시 잃는 것 vs 얻는 것(요약)**

| 제거 대상 | 잃는 것 | 얻는 것 | 보완책 |
|---|---|---|---|
| Kafka | 오프셋 재처리, 소비자별 독립 진도, 대용량 버퍼, 장애 격리 | 컨테이너·JVM 감소, 설정면 축소, hop 감소 | DB 이력 재생 모드, MQTT QoS1 영구 세션 큐, 또는 NATS JetStream |
| Flink | 워터마크·late event 표준 처리, 체크포인트 복구, 정확히 한 번 | 학습 곡선·메모리 감소, Python 생태계(onnxruntime) 직결 | 이벤트 시각은 payload의 ts·seq로 판정, 시작 시 DB에서 윈도 재구성 |
| Telegraf#1·#3 | 없음 | 장애점 2개 제거 | — |
| EdgeX | 장치 추상화 학습 가치 | 여러 컨테이너(core·레지스트리·DB·device·app 서비스) 제거 | EdgeX는 선택 실습 모듈로 분리 |
| Prometheus+Alertmanager | 지표 장기 이력, 억제·그룹 | 컨테이너 2개 감소 | Grafana Alerting, 필요 시 Prometheus만 재도입 |

---

## 5. 세부 검증

### 5.1 FUXA는 Grafana를 대체할 수 있는가 (최신 1.3.4 기준)

**확인된 기능(1차: 프로젝트 저장소·릴리스·위키)**
- 프로토콜: Modbus RTU/TCP, S7, OPC-UA, BACnet IP, MQTT, EtherNet/IP, ODBC, Redis 등(README). 라이선스는 MIT(npm/Snyk 표기, 2026).\[19\]\[20\] OSI 조건을 만족한다.
- 내장 히스토리안(DAQ): SQLite, InfluxDB(1.8/2.x), TDengine.\[19\] **InfluxDB 3은 미지원**이며 "Support InfluxDB V3 as DAQ database" 기능 요청(#2325)만 열려 있다.\[1\]\[21\] QuestDB는 기능 요청(#2114)이 있고 일부 2차 코드 분석(DeepWiki)은 지원한다고 하지만 **[미검증: 충돌]**이다.\[21\]\[22\] PostgreSQL/TimescaleDB는 DAQ 대상이 아니다. ODBC·Node-RED 연동으로 우회할 수는 있다 [미검증].
- 차트: 히스토리 차트의 점진적 DAQ 스트리밍(uPlot), 테이블 이력 시간 반올림, 15분 리포트 간격(v1.3.1, 2026-04-09).\[12\]\[23\]
- 알람: 태그 하나에 HH/H/L/Message 4개 조건을 둘 수 있다. 활성 알람과 이력 화면이 있고, 알람별 동작(팝업, 태그 값 설정)을 설정할 수 있다(위키 "HowTo setup Alarms").\[24\] v1.3.4에서 알람 텍스트에 태그 값을 넣을 수 있게 되었고,\[12\] v1.3.3(2026-06-21)에서 Node-RED 알람 확인 노드가 갱신되었다.\[12\]
- 보안: CISA ICSA-26-181-02(2026-06-30), CVE-2026-13207. FUXA 1.3.1 이하는 REST API에서 dot-segment 경로 정규화를 우회해 인증 없이 사용자·역할을 열거할 수 있다. CVSS v4 8.7(1차: CISA).\[25\]\[26\] v1.3.4는 Socket.IO 관리 응답 범위 제한, runScript 바인딩, rate limiter 순서 수정 등 추가 보안 수정을 포함한다.\[12\] 위키상 기본 계정이 admin/123456이고 `secureEnabled`로 인증을 켜야 한다.\[27\]

**한계(커뮤니티 이슈, 이해관계 없음이지만 비공식)**
- InfluxDB v2 저장 시 1초 해상도로 떨어진다는 보고가 있다(Discussion #2048).\[28\] 12태그 1 Hz 실습에는 영향이 적다.
- 알람 이력 CSV 내보내기와 기간·그룹별 이력 테이블 요청(Discussion #2053), 알람 이력 검색 요청(#329)이 있다.\[29\]\[30\] 알람 분석(KPI, bad actor)에는 약하다.
- TDengine 사용 시 이력 차트가 뒤섞인다는 버그 보고(#1489)가 있다.\[31\]

**판정:** FUXA 추세는 **운전원 단기 추세**(현재 운전 판단)로 충분하다. 반면 **엔지니어 분석**(전류와 진동의 임의 기간 비교, score 겹쳐 보기, SQL 집계)과 **운영 패널**에는 Grafana가 낫다. 현업에서도 HMI 단기 추세와 플랜트 히스토리안·분석 도구는 따로 둔다. 그래서 Grafana는 "추세 분석 + 운영 감시 + 운영 경보"를 한곳에 모으는 조건으로 유지하는 것을 권장한다. Grafana를 없애는 대안 B도 가능하지만 분석 기능이 줄어든다.

### 5.2 12태그 단일 머신에서 Prometheus+Alertmanager가 필요한가

- Kafka·Flink를 빼면 감시할 대상은 브로커 생존, 탐지기 heartbeat, DB 생존, 수집 지연 정도로 줄어든다.
- 경량 대안: Docker `healthcheck` + `restart` 정책, Mosquitto `$SYS` 토픽(연결 수, 수신·발신 메시지), 탐지기가 `ops/detector/heartbeat`에 last_ts·처리량·지연을 발행하고 Telegraf가 이를 PostgreSQL에 넣으면 Grafana 패널과 Grafana Alerting으로 볼 수 있다. Mosquitto 2.1은 실험적 `http_api` 리스너와 대시보드도 추가했다(Eclipse 릴리스 리뷰, 재단·1차).\[32\]
- **잃는 것:** 지표 장기 이력과 PromQL, 표준 exporter 생태계(cAdvisor 등), Alertmanager의 억제(inhibition)·그룹·온콜 라우팅. "운영 경보는 설비 정지 경로가 아니다"라는 V1 원칙은 그대로 유지된다.
- **판정:** 최소 구성에서는 제거한다. "운영 관측성 교육"이 목표라면 Prometheus 1개(+cAdvisor)를 선택 모듈로 두고 Alertmanager는 Grafana Alerting으로 대체한다.

### 5.3 FUXA와 Vue: 하나로 합칠 수 있는가

- **합칠 수는 있다.** FUXA는 웹 기반이고 스크립트·Node-RED 연동이 있다. 하지만 **합치지 않는 것이 현업 원칙에 맞다.** 이유는 다음과 같다.
  1. 운전 HMI(L2)는 제어기와 직결되어야 하고 업무·IT 계층 장애에 영향받지 않아야 한다. NIST SP 800-82r3는 Purdue/IIoT 분할과 DMZ, 계층 간 통제를 권고한다.\[33\]\[34\]
  2. 업무·AI UI는 LLM·외부 API·사건 DB와 연결되므로 공격면이 넓다. FUXA는 2026년에도 인증 우회 취약점(ICSA-26-181-02)이 있었으므로, 여기에 업무·AI 기능을 얹으면 운전 화면의 위험이 커진다.\[25\]
  3. ISA-18.2 관점에서 운전원 알람 화면에는 합리화(rationalization)를 거친 알람만 있어야 한다. AI 조사·승인 흐름은 다른 사용자(엔지니어·관리자)의 업무다.
- **중복 제거 방법:** Vue에서 공정 그림·기동/정지·설정값을 삭제하고, 사건·advisory 확인·AI 조사·승인·감사 이력만 남긴다. 운전 화면이 필요하면 FUXA 화면 링크로 연결한다.

### 5.4 저장소 3개 → PostgreSQL 하나

- **시계열:** 12태그 × 1 Hz = 하루 1,036,800행(원시값 기준 산술값이며 측정값이 아님)이다. 평범한 PostgreSQL(시간 인덱스 또는 BRIN)로도 다룰 수 있는 규모로 판단하지만 **[미검증: 7장 실험으로 확인]**이다. TimescaleDB를 쓸 경우 OSI 조건 때문에 **Apache 2 에디션만** 쓸 수 있다. 하이퍼테이블·time_bucket은 가능하다. 연속 집계·보존 정책·(자료에 따라) 컬럼 압축은 TSL(Tiger Data License)이라 제외된다. 압축이 Apache 에디션에 포함되는지는 2차 자료끼리 서로 다르므로 **[미검증: 충돌]**이다.\[35\]\[36\]\[37\] 보수적으로 TSL로 간주한다. 보존은 `DELETE`/파티션 드롭을 cron으로 대신한다.
- **관계:** 설비 6개(TK-101, P-101, R-101, M-101, HX-101, CV-101)와 태그 12개, 인과·연결 관계 정도는 `equipment`, `edge` 테이블과 재귀 CTE로 충분하다. openCypher가 교육 목표라면 Apache AGE 1.7.0(2026-01-21, PG 11~18 지원 표기)을 쓴다. 1.8.0은 2026-09-19 RC(PMC 승인 전)다.\[10\]\[11\]\[38\]
- **잃는 것:** Neo4j Browser 시각화, GDS 알고리즘, Neo4j 전용 LLM 도구 연동의 편의, 시계열 전용 DB의 압축·다운샘플링 자동화.
- **InfluxDB를 계속 쓴다면:** InfluxDB 3 Core 설정 문서에 따르면 기본 `--query-file-limit` 432와 기본 gen1-duration 10분 조합에서 쿼리는 "up to a 72 hours of data, but potentially less"까지만 접근할 수 있고, 문서는 "We recommend keeping the default setting and querying smaller time ranges"라고 권고한다. Flux도 지원하지 않는다. 한도를 올리면 성능이 떨어진다고 문서에 경고되어 있다(InfluxData 문서·블로그, 벤더·1차). FUXA DAQ와 함께 쓰려면 InfluxDB OSS 2.x(문서상 2.9.0 존재)가 현실적이다.\[9\]

### 5.5 백본: Kafka vs MQTT 단독 vs NATS JetStream

| 선택 | 라이선스·버전(확인) | 장점 | 한계 |
|---|---|---|---|
| Mosquitto 2.1.x 단독 | EPL-2.0/EDL(OSI) [라이선스 본 조사 미재확인]. Eclipse Mosquitto 블로그 기준 2.1.0 2026-01-29, 2.1.1 2026-02-04, 2.1.2 2026-02-09(버그 수정판) | 내장 WebSocket(Vue·브라우저 직결), SQLite 영속 플러그인, 브리지 옵션, FUXA MQTT와 호환 | 로그 재처리 없음(영구 세션 큐만), 다중 소비자 진도 관리 없음 |
| Kafka 4.2.x(Apache Kafka 블로그 기준 4.3.0 2026-05-22, 4.3.1 2026-06-25 공개) | Apache-2.0. 4.2.0 2026-02-17, KRaft 전용 | 재처리, 다중 소비자, 버퍼, 표준 | FUXA가 직접 구독하지 못해 MQTT 다리가 필요하고 결국 이중 백본이 된다. JVM |
| NATS 2.15 + JetStream + MQTT 게이트웨이 | Apache-2.0. v2.15.0 2026-09-17 | 단일 서버에서 MQTT 수신과 JetStream 스트림 재생을 함께 제공 | **MQTT 3.1.1만 지원(v5 거부)**. NATS 발행 → MQTT 구독은 항상 QoS 0. MQTT 사용에는 JetStream 필수. WebSocket MQTT는 websocket 포트의 `/mqtt` 경로로. 2.15부터 스트림당 기본 소비자 1000 한도 |\[39\]\[40\]\[41\]\[42\]\[43\]\[44\]
| Redpanda(UMH Core 내장) | **BSL(비OSI)** | Kafka 호환·경량 | 제약 조건 위반 → 제외 |\[45\]\[46\]

**판정:** 12태그 교육용에서는 **Mosquitto 단독 + DB 기반 재생**이 가장 단순하다. "재처리·다중 소비자"를 교육 목표로 꼭 남겨야 하면 Kafka를 유지하지 말고 **NATS JetStream 단일 백본(대안 C2)**으로 가는 것이 이중 백본을 피하는 길이다.

### 5.6 Flink 대체 가능성: CEP·Z-Score·ONNX 동등성

| 항목 | Flink 2.2.1 | Python 자체 서비스 | Quix Streams | eKuiper | Timeplus Proton |
|---|---|---|---|---|---|
| 라이선스 | Apache-2.0 | 자체 | Apache-2.0 | Apache-2.0(LF Edge) | Apache-2.0 |\[47\]\[48\]\[49\]
| 브로커 의존 | Kafka 등 | MQTT 직결 가능 | **Kafka 필수** | MQTT·EdgeX 버스 직결 | Kafka/Redpanda 외부 스트림 |\[2\]\[49\]\[50\]
| 상·하한 | ● | ● | ● | ● (SQL) | ● (SQL) |
| Z-Score(슬라이딩) | ● | ● (deque·numpy) | ● (윈도) | ● (윈도 집계) | ● |
| CEP(전류↑ 후 N초 내 진동↑) | ● (CEP 라이브러리) | ● (상태 머신 수십 줄) | ○ (직접 구현) | ○ (윈도·조인으로 근사) [미검증] | ○ (스트림 조인·윈도) [미검증] |
| 이벤트타임·워터마크 | ● (표준) | 직접 구현 | ○ (메시지 타임스탬프 기반 윈도) | [미검증] | ● (워터마크 문서화) |
| late event | ● (허용 지연) | 직접(seq 기반 폐기·보정) | ○ [미검증: grace 설정] | [미검증] | ○ |
| 재시작 복구 | ● (체크포인트) | 직접(DB에서 윈도 재구성) | ● (RocksDB + Kafka changelog, 2차 해설) | [미검증] | ○ |\[51\]
| ONNX 추론 | ○ (Java ONNX Runtime) | ● (onnxruntime) | ● (Python) | ○ (플러그인) [미검증] | ○ (UDF) [미검증] |
| 보안 이력 | — | — | — | 2025년 XSS·경로 조작·파일 쓰기(RCE 가능) 취약점 다수(Go 취약점 DB) | — |\[52\]

**판정:** 단일 수집기 → 단일 브로커 → 단일 소비자 구조에서는 같은 토픽 안의 순서가 MQTT QoS1에서 유지되고, 12태그라서 이벤트타임 문제는 "payload의 ts·seq로 판정하고 역행 샘플은 버리거나 표시하는" 규칙으로 충분하다. 그래서 **Python 서비스 1개**가 가장 적은 구성이다. 이벤트타임·워터마크를 교육 목표로 삼는다면 Flink 1개 작업(규칙+ONNX 통합)이나 Proton을 선택 모듈로 둔다. Proton이 내세우는 "90M EPS, 4 ms" 같은 수치는 벤더 주장이며 이 보고서는 검증하지 않았다.\[53\]

### 5.7 알람 구조 (ISA-18.2 / IEC 62682)

- **표준 요약(1차·요약):** ISA-18.2-2016은 알람 철학 → 식별 → 합리화 → 설계 → 구현 → 운영 → 유지보수 → 모니터링의 수명주기를 정의한다. 알람 상태(정상·활성, 확인·미확인)와 셸빙·설계상 억제·서비스 제외를 규정한다.\[54\]\[55\] exida 백서에 따르면 셸빙한 알람은 정해진 시간이 지나면 다시 나타나야 한다.\[13\]\[56\]
- **현업 사례(1차 공개 사례):** Fermilab ICARUS 극저온 시스템(arXiv 2509.18392, 2025-09)은 "알람 로직은 PLC에 있고, 한계 설정과 확인은 HMI에서" 하며 ISA-18.2의 상태·데드밴드·지연·셸빙을 반영하고, 원격 통지는 별도 오토다이얼러로 한다.\[17\] **알람 상태의 소유자는 제어 시스템(PLC+HMI/SCADA 알람 서버)**이다.
- **분석 알람(advisory):** 예측·이상탐지 신호는 합리화되지 않았다면 운전원 알람 목록에 섞지 않고 advisory로 분리하는 것이 일반적이다. 이 근거는 벤더 해설(iFactory, 이해관계 있음)과 ISA-18.2의 합리화 원칙에서 추론한 것이다.\[57\]
- **V1 권고:** 알람을 두 클래스로 나누고 클래스마다 소유자를 하나씩 둔다.
  - **공정 알람**(TT-101 HH/H, PT-101 고압 등 상·하한): FUXA 알람 엔진이 발생·확인·복귀를 소유한다. 고압 인터록은 시뮬레이터(PLC 역할) 안에 둔다.
  - **분석 advisory**(Z-Score, CEP, AE score): PostgreSQL `alarm` 테이블(상태: active/acked/rtn/shelved, shelve_until, 결합 키)을 alarm-core가 소유한다. 화면은 MQTT retained 토픽으로 FUXA의 advisory 패널과 Vue에 표시한다. 확인·셸빙은 Vue에서 한다.
  - 두 클래스의 이벤트를 모두 `alarm_journal`(PG)에 남기는 것은 선택이다. FUXA 알람 이력 반출 경로는 Node-RED 노드 등으로 가능할 것으로 보지만 [미검증]이다.
- **FUXA 알람으로 충분한가:** 공정 알람의 발생·확인·이력 표시는 충분하다. 셸빙(시간 제한 자동 복귀), 알람 KPI(시간당 알람 수, stale 알람), 이력 검색·내보내기는 부족하다(이슈 #2053, #329).\[29\]\[30\] ISA-18.2 교육 요소는 alarm-core에서 구현하는 편이 낫다.

### 5.8 제어 경로 (인터록, 승인, read-back, IT→OT 쓰기 제한)

- **인터록:** 제어기(PLC) 레벨에 둔다. V1처럼 시뮬레이터 내부 고압 인터록은 옳다. HMI나 AI는 인터록을 우회할 수 없어야 한다.
- **HMI 직접 쓰기:** 운전원 조작은 FUXA → Modbus가 표준이다. FUXA는 인증을 켜고(`secureEnabled`), 역할 권한을 두고, 1.3.2 이상(권장 1.3.4)을 쓰고, 격리된 네트워크에 둔다.\[25\]\[27\]
- **상위 시스템(AI) 명령:** Vue 백엔드 쓰기를 없애고 **Pilot 하나**로 모은다. Pilot의 요건은 다음과 같다.
  1. 쓰기 허용목록(정지 코일, 설정값 범위만)
  2. 승인 토큰(LangGraph 승인 ID, 승인자, 만료)
  3. 실행 직전 조건 재검사(/state seq·운전상태, 인터록 상태)
  4. 쓰기 후 read-back(Modbus 값과 /state seq 증가 확인)
  5. 타임아웃·불일치 시 실패로 기록하고 재시도하지 않음
  6. PostgreSQL 감사 기록(누가·무엇을·언제·전후 값)
- **IT→OT 쓰기 제한:** NIST SP 800-82r3와 IEC 62443의 영역·도관 개념에 따라 L4/L3에서 L2 제어로 직접 연결하지 않고, 통제된 관문 하나만 둔다(벤더 해설 Shieldworkz·Anchor Defense, 이해관계 있음).\[15\]\[18\]

---

## 6. 실제 사례 비교 (2024~2026 공개 자료)

| 사례 | 구성 요소(공개 문서 기준) | hop 구조 | 라이선스(OSI 여부) | V1과의 비교 |
|---|---|---|---|---|
| UMH Core(2025~) | 컨테이너 1개 안에 Agent(Go), Benthos-UMH, Redpanda, S6 | PLC → 브리지 → UNS(Redpanda) → 브리지 → DB/대시보드 | UMH 코드 Apache-2.0, **내장 Redpanda는 BSL(비OSI)** | "브리지만이 유일한 진입점"이라는 단일 백본 원칙은 V1이 본받을 점이다. 그대로 도입하면 라이선스 제약을 위반한다 |\[45\]\[58\]\[59\]
| UMH Classic(레거시 표기, 2025-09) | Kubernetes Helm: HiveMQ(MQTT), Redpanda(Kafka), data-bridge, TimescaleDB, Grafana, Node-RED, Prometheus | MQTT↔Kafka 브리지 → 히스토리안(TimescaleDB) → Grafana | 혼합(Redpanda BSL, TimescaleDB TSL 기능 포함 가능) | V1과 비슷한 이중 백본이지만 **다중 사이트·대규모 전제**다. UMH도 새 버전(Core)에서 단일 컨테이너로 단순화했다 |\[16\]\[60\]
| EdgeX + eKuiper | device 서비스 → 메시지 버스 → eKuiper(SQL 규칙) → 싱크·Command | 엣지 내부 버스 | Apache-2.0 | EdgeX를 쓴다면 Flink 대신 eKuiper가 원래 짝이다. 12태그에는 둘 다 과하다 |\[2\]
| Fermilab ICARUS 극저온(2025) | PLC(알람 로직) + HMI(한계 설정·확인) + 원격 통지 | PLC → HMI → 통지 | 상용 제품 혼재(참고용) | 알람 소유권이 제어 계층에 있다는 근거다 |\[17\]
| Mosquitto 2.1 + Sparkplug | 브로커 + Sparkplug-aware 플러그인(Cedalo 발표) | 장치 → 브로커 → 소비자 | EPL-2.0 [미재확인] | UNS 단일 백본의 경량 형태다. Sparkplug 플러그인 설명은 벤더 블로그라 [부분 검증]이다 |\[5\]
| FUXA 단독·Node-RED 소규모 | FUXA(+Node-RED 통합, v1.2.x~1.3.x) | 장치 → FUXA → DAQ/알람 | MIT / Apache-2.0 | 대안 B의 근거다. 공개된 "공장 규모 구축 사례"는 이번 조사에서 찾지 못했다 **[미검증]** |

---

## 7. 표 4: 단순화 대안 비교 (문헌 기준, 실측 전)

점수 기준(각 5점, 합계 20점, 실측 전 문헌 기준): 현업 정합성(Purdue·ISA-18.2·NIST 분리 원칙 부합) / 단순성(컨테이너·hop) / 기능 보존(V1 목적 기능) / 도입 속도(V1 코드 재사용).

| 대안 | 흐름 한 줄 | 컨테이너 수(추정) | 알람→화면 hop | 제거 컴포넌트 | 잃는 기능 | 현업 정합성 | 교육 가치 | 난이도 | 추천 점수 |
|---|---|---|---|---|---|---|---|---|---|
| V1(기준) | 설비→EdgeX→EMQX→T#1→Kafka→Flink×2→Kafka→T#2/T#3→Influx/EMQX→FUXA | 약 27~33 | 약 8 | — | — | 대규모에 맞춘 과설계 | 도구 폭 넓음 | 높음 | — |
| **A 보수적 최소 수정** | 설비→Telegraf(modbus→Kafka)→Kafka→Flink(규칙+ONNX 1작업)→Kafka alerts→alarm-core→Mosquitto→FUXA | 약 18~20 | 3 | EdgeX, EMQX→Mosquitto, Telegraf#1·#3, Alertmanager | 없음에 가까움(Alertmanager 억제만) | 4 | Kafka·Flink 유지 | 낮음 | 4+2+5+5 = **16** |
| **B FUXA 중심 최소** | 설비→FUXA(폴링·알람·DAQ→InfluxDB 2.x)→FUXA MQTT 발행→Mosquitto→Python 탐지기→Mosquitto→FUXA | 약 9~10 | 2 | EdgeX, EMQX, Telegraf×3, Kafka, Flink, Grafana, Prometheus, Alertmanager, Neo4j | 재처리, 임의 분석 추세, 운영 지표. 분석 경로가 HMI에 종속 | 3 | HMI 중심 실습 | 중간 | 3+5+3+4 = **15** |
| **C MQTT/UNS 단일 백본(추천)** | 설비→[FUXA 직접(운전)] + [Telegraf 1(분석 읽기)→Mosquitto]→Python 탐지기→Mosquitto(advisory)→FUXA·Vue, 이력·업무는 PostgreSQL, Grafana | 약 11~12 | 2 | EdgeX, EMQX, Telegraf#2·#3, Kafka, Flink×2, InfluxDB, Neo4j, Prometheus, Alertmanager | 로그 재처리(→DB 재생), 워터마크 표준 | 5 | UNS·ISA-18.2·HITL 제어 | 중간 | 5+4+4+4 = **17** |
| C2 NATS 변형 | C와 같되 브로커를 NATS 2.15(MQTT 게이트웨이 + JetStream 스트림) | 약 11~12 | 2 | C와 같음 | MQTT v5 불가, NATS→MQTT는 QoS0 | 3 | 재처리 교육 유지 | 중상 | 3+4+5+3 = **15** |
| D PostgreSQL 중심 경량 | 설비→Telegraf→PostgreSQL→탐지기(LISTEN/NOTIFY)→PG alarm→Vue, FUXA 직접 | 약 8~9 | 2~3(DB 경유) | 브로커 포함 대부분 | 이벤트 스트림 개념, FUXA의 MQTT advisory 수신(폴링으로 대체) | 2 | DB 중심 | 중간 | 2+5+3+3 = **13** |

컨테이너 수는 공식 compose 파일을 세어 본 값이 아니라 추정이다. 특히 EdgeX는 core·레지스트리·DB·device·app 서비스를 포함해 여러 개로 추정 **[미검증]**한다.

---

## 8. 추천 최종 구성과 흐름도 (대안 C)

**컨테이너(11~12개, 모두 OSI 라이선스):** sim(가상설비), fuxa(1.3.4+), telegraf(1개), mosquitto(2.1.x), detector(Python: 규칙+Z+CEP+onnxruntime), backend(API + alarm-core, Vue 정적 파일 서빙 가능), postgres(+TimescaleDB Apache 선택), grafana, agent(LangGraph), litellm, pilot. 선택 모듈: prometheus(+cAdvisor), kafka 또는 NATS(재처리 실습), flink(이벤트타임 실습), edgex(장치 추상화 실습).

```
[가상설비 sim] Modbus TCP(코일·레지스터·온도×10) + HTTP /state(seq·운전상태) + 고압 인터록(PLC 역할) + 이상 주입
   │
   ├─(L2 운전 경로) Modbus 폴링/쓰기 ─────────────▶ FUXA  : 공정 그림, 기동/정지, 설정값,
   │                                                         공정 알람(HH/H/L, 확인), 단기 추세(DAQ=SQLite)
   │                                                         + advisory 패널(MQTT 구독)
   │
   └─(분석 경로, 읽기 전용) Modbus 폴링 ──▶ Telegraf(1개)
                                              ├─ outputs.mqtt ─▶ Mosquitto: plant/<area>/<equip>/<tag>
                                              └─ outputs.postgresql ─▶ PostgreSQL.raw (1회 폴링, 2개 싱크)

Mosquitto ──▶ detector(Python): 상·하한 / Z-Score / CEP(IT-102↑ 후 N초 내 VT-101↑) / ONNX AE
               ├─ plant/<equip>/advisory/<rule> (QoS1, retained) ─▶ FUXA advisory 패널, Vue(WebSocket)
               ├─ score·clean 배치 적재 ─▶ PostgreSQL
               └─ ops/detector/heartbeat ─▶ (Telegraf) ─▶ PostgreSQL.ops

backend/alarm-core: advisory 구독(영구 세션) → alarm 테이블(ISA-18.2 상태·결합·셸빙 만료) → 사건 등록
Vue(업무·AI UI): 사건 목록 → "분석 시작" → agent(LangGraph + LiteLLM, 설비관계=PG 재귀 CTE/AGE)
               → 검토 대기(interrupt) → 승인/반려
               → pilot: 허용목록 → 조건 재검사(/state seq·인터록) → Modbus 쓰기 → read-back(Modbus + /state) → PG 감사
Grafana: PostgreSQL 이력 추세(전류·진동·score 비교) + 운영 패널($SYS·heartbeat·healthcheck) + Grafana Alerting(운영 경보)
```

**설계 원칙 요약**
- **읽기:** 운전 경로와 분석 경로를 분리하되 수집기는 경로마다 하나씩만 둔다. 분석 경로는 1회 폴링 결과를 MQTT와 DB에 동시에 써서 "브로커 값과 이력 값의 불일치"를 없앤다.
- **알람:** 공정 알람은 FUXA가, advisory는 alarm-core(PG)가 소유한다. 화면까지는 2 hop이다.
- **쓰기:** 운전원은 FUXA, 자동·승인 명령은 Pilot만 쓴다. Vue는 쓰지 않는다. 인터록은 sim(PLC) 안에 둔다.
- **저장:** PostgreSQL 하나(업무 + 시계열 + 관계 + 알람 + 감사)와 FUXA 로컬 DAQ(운전 단기 추세)만 둔다.

---

## 9. 직접 실험(PoC) 목록 (측정값 칸은 비움)

| ID | 목적 | 비교 구성 | 방법·장애 주입 | 측정 지표 | 판정 기준(사전 합의) | 측정값 V1 | 측정값 C |
|---|---|---|---|---|---|---|---|
| E1 | 알람→화면 지연 | V1 vs A vs C | 이상 주입 시각(sim 로그)부터 FUXA·Vue 표시 시각까지, 100회 | p50/p95/최대 지연(ms) | C의 p95가 V1 이하이고 운전 판단에 충분(예: p95 < 1 s, 기준은 팀이 확정) | | |
| E2 | hop·구성 복잡도 | V1 vs C | compose와 트레이스 분석 | 알람 경로 hop 수, 컨테이너 수, 설정 파일 수 | C가 hop 50% 이상 감소 | | |
| E3 | 자원 | V1 vs C | 1시간 정상 운전 | 총 메모리·CPU(docker stats), 기동 시간 | C가 V1보다 뚜렷이 감소 | | |
| E4 | 브로커 장애 | V1(EMQX/Kafka) vs C(Mosquitto) | 브로커 30 s 정지 후 재기동 | 유실·중복 메시지 수, 복구 시간, FUXA 운전 화면 영향 | 운전 HMI 영향 0, 유실은 허용 정책 이내 | | |
| E5 | 탐지기 장애 | Flink vs Python | 탐지기 강제 종료 후 재기동 | 재기동 뒤 첫 판정까지 시간, Z 윈도 복구 여부, 누락 advisory | 재기동 뒤 윈도가 DB로 복구되고 누락 advisory는 재판정 | | |
| E6 | 재처리 | Kafka 오프셋 재생 vs DB 재생 vs JetStream | 과거 1시간 구간 재생 후 결과 비교 | 재생 가능 여부, 결과 동일성, 소요 시간 | 동일한 advisory 집합 재현 | | |
| E7 | HMI 값과 이력 값의 일관성 | 이중 폴링(V1) vs 1회 폴링·2싱크(C) | 동시각 FUXA 값과 PG/Influx 값 비교, 10,000 샘플 | 불일치 비율, 시간차 분포 | 설정 허용오차 이내 99% 이상 | | |
| E8 | CEP 정확도 | Flink CEP vs Python 상태 머신 | 전류↑→진동↑ 시나리오 50회 + 순서 역전·지연 주입 | 탐지율, 오탐, 지연 이벤트 처리 결과 | 두 구현의 판정 일치 95% 이상 | | |
| E9 | 제어 안전성 | Pilot 경로 | 승인 후 조건 변화(인터록 작동) 주입, read-back 불일치 주입 | 차단된 부적합 명령 수, 감사 기록 완결성 | 부적합 명령 실행 0건, 감사 누락 0건 | | |
| E10 | 알람 수명주기 | alarm-core | 발생→확인→복귀, 셸빙 만료 자동 복귀, 중복 결합 | 상태 전이 정확도, 셸빙 만료 복귀 여부 | ISA-18.2 상태도와 100% 일치 | | |
| E11 | 운영 감시 대체 | Prometheus+AM vs healthcheck+Grafana | 컨테이너 kill, 탐지기 hang(heartbeat 정지) | 경보 발생까지 시간, 누락 | 두 방식 모두 탐지(시간 차이 기록) | | |
| E12 | 보안 기본선 | FUXA 1.3.1 vs 1.3.4 | `/api/./users` 등 dot-segment 요청(격리 환경) | 인증 우회 여부 | 1.3.4에서 차단 | | |

**기능 보존 체크리스트(각 대안 공통, 통과/실패 기록)**

| 항목 | V1 | A | B | C | D |
|---|---|---|---|---|---|
| 12태그 수집(1 Hz) | | | | | |
| 상·하한 / Z-Score / CEP / AE 탐지 | | | | | |
| 공정 알람 표시·확인 | | | | | |
| advisory 표시·확인·셸빙 | | | | | |
| 이력 조회(전류·진동 비교, 72시간 초과 구간 포함) | | | | | |
| 사건 등록·중복 결합 | | | | | |
| AI 조사(지식그래프 질의) | | | | | |
| 승인/반려 → Pilot 재검사 → 정지 → read-back | | | | | |
| 조작 이력·감사 | | | | | |
| 운영 감시·운영 경보 | | | | | |
| 재처리 | | | | | |

---

## 10. 논쟁점과 반론

1. **"HMI도 브로커를 구독하면 읽기가 완전히 하나가 된다."** 반론: 그러면 운전 화면이 IT 계층(브로커·수집기) 장애에 종속된다. NIST SP 800-82r3의 계층 분리 취지와, 현업에서 HMI/SCADA가 제어기를 직접 읽는 관행에 비춰 보면 운전 경로는 직접 폴링이 더 안전하다. 12태그 Modbus TCP에서 이중 폴링의 부하는 미미하다고 보지만 [미검증]이며, E7로 일관성 비용을 측정한다.
2. **"Kafka를 빼면 재처리를 잃는다."** 맞다. 하지만 12태그 원시 데이터는 전부 PG에 있으므로 "DB 재생"으로 같은 입력을 다시 흘릴 수 있다. 소비자별 독립 오프셋이 교육 목표라면 Kafka+MQTT 이중 백본보다 NATS JetStream 단일 백본이 hop이 적다. 단 MQTT 3.1.1만 지원한다.
3. **"Flink는 이벤트타임 교육 가치가 크다."** 동의한다. 다만 본선 경로에서 빼고 선택 모듈(E5·E8의 비교 대상)로 두는 것이 "목적 흐름은 그대로, 스택만 축소"라는 요구에 맞다.
4. **"FUXA 하나로 다 하면 가장 단순하다(대안 B)."** 가장 단순한 것은 맞다. 그러나 FUXA는 2026년에 CISA 권고(인증 우회)가 있었다. 알람 이력 검색·내보내기가 약하고 InfluxDB 3·PostgreSQL DAQ도 지원하지 않는다. 분석·업무·AI를 HMI에 몰면 공격면과 장애 영향이 운전 화면으로 모인다.
5. **"알람 상태는 반드시 한 곳이어야 한다."** ISA-18.2는 알람 시스템의 관리 책임을 요구하지만 물리적 저장소 하나를 요구하지는 않는다. 현업에서는 공정 알람은 제어 시스템이, 분석 advisory는 별도 시스템이 소유하는 경우가 많다. 이 보고서는 "클래스별 단일 소유자 + 공통 저널(선택)"을 제안한다. 반대로 alarm-core가 모든 알람을 소유하고 FUXA는 표시만 하는 설계도 가능하다. 이 경우 FUXA의 확인 기능은 쓰지 않는다.
6. **"Neo4j가 LLM 지식그래프 도구 연동에 유리하다."** 사실이다. 그러나 설비 6개 규모에서는 재귀 CTE로 질의가 충분하고, openCypher가 필요하면 Apache AGE를 쓴다. 대규모 그래프 알고리즘(GDS)이 필요해지면 그때 재도입한다.
7. **"TimescaleDB를 쓰면 되지 않나."** OSI 조건에서는 Apache 에디션만 쓸 수 있고, 연속 집계·보존 정책(그리고 자료에 따라 압축)은 TSL이다. 12태그에서는 평범한 PostgreSQL로도 시작할 수 있다고 보며 E3·E7로 확인한다.
8. **"EdgeX는 산업 표준 엣지 프레임워크다."** 장치 수가 많고 이기종일 때 가치가 크다. 가상설비 1대·12태그에서는 추상화 비용이 더 크므로 선택 실습 모듈로 분리한다.

---

## 11. 근거 등급 구분 (1차 vs 이해관계 있음)

| 근거 | 유형 | 날짜 | 이 보고서에서의 용도 |
|---|---|---|---|
| NIST SP 800-82 Rev.3 | 정부·1차 | 2023-09-28 | 계층 분리, 제어 센터 기능(중앙 알람·추세·리포트), DMZ |
| CISA ICSA-26-181-02 / CVE-2026-13207 | 정부·1차 | 2026-06-30 | FUXA ≤1.3.1 인증 우회, CVSS v4 8.7 |
| ANSI/ISA-18.2-2016 요약(ANSI 블로그, ISA 페이지, exida 백서) | 표준 요약 | 2016 표준 / 요약 날짜 다양 | 알람 수명주기·상태·셸빙 |
| Fermilab ICARUS 극저온 시스템 논문(arXiv 2509.18392) | 실제 시설 사례·1차 | 2025-09 | PLC 알람 로직 + HMI 확인 |
| Apache Kafka 4.2.0 발표 | 재단·1차 | 2026-02-17 | KRaft, 버전 |
| Apache Flink 2.2.1 발표 | 재단·1차 | 2026-05-15 | 버전 |
| Apache AGE 릴리스 노트·README | 재단·1차 | 1.7.0: 2026-01-21, 1.8.0 RC: 2026-09-19 | PG 그래프 대체 |
| NATS 서버 릴리스·문서 | 프로젝트·1차(Synadia 관여) | v2.15.0: 2026-09-17 | MQTT 3.1.1, JetStream 요건 |
| Eclipse Mosquitto 2.1 릴리스 리뷰·블로그 | 재단·1차 | 2.1.0: 2026-01-29, 2.1.1: 2026-02-04, 2.1.2: 2026-02-09 | 내장 WebSocket, http_api, SQLite 영속 |
| FUXA 저장소·릴리스·위키 | 프로젝트·1차 | v1.3.4: 2026-08-12, v1.3.3: 2026-06-21, v1.3.1: 2026-04-09 | 기능·알람·DAQ |
| FUXA 이슈·토론(#2048, #2053, #2114, #2325, #1489, #329) | 커뮤니티 | 2022~2026 | 한계 |
| EMQX BSL 발표·EOL 공지·FAQ | 벤더(이해관계 있음) | 2025-05-07, EOL 2026-02-28 | 라이선스 판정 |
| InfluxDB 3 Core 문서·블로그 | 벤더·1차 문서 | 문서 현행, 블로그 2025-01 | 432 파일 한도, Flux 미지원 |
| Tiger Data(TimescaleDB) 에디션 문서 | 벤더·1차 문서 | 현행 | Apache vs TSL |
| GridDB·Basekick·Gold Lapel·QuestDB의 TimescaleDB/InfluxDB 비교 | 경쟁 벤더(이해관계 있음) | 2025~2026 | 참고만(압축 포함 여부 충돌) |
| UMH 문서·README | 벤더·1차 사례 | 2025 | 아키텍처 비교 |
| Redpanda 라이선스 문서 | 벤더·1차 | 현행 | BSL 판정 |
| eKuiper 문서, Go 취약점 DB | 재단 / 1차 취약점 DB | 2024~2025 | 경량 규칙 엔진, 취약점 이력 |
| Quix Streams(PyPI·README), Timeplus Proton 문서 | 벤더(이해관계 있음) | 현행 | 라이선스·기능. 성능 주장은 미검증 |
| Shieldworkz, Anchor Defense, iFactory 해설 | 벤더 블로그(이해관계 있음) | 2025~2026 | 관행 설명 보조 |

---

## 12. 주의사항 (Caveats)

- **성능 수치 없음:** 이 보고서의 지연·메모리·처리량 판단은 모두 구조 분석과 문헌에 기반한다. 벤더가 제시한 수치(Proton의 EPS·지연, eKuiper의 메모리 수치 등)는 검증하지 않은 주장이다.
- **[미검증] 항목:** FUXA의 QuestDB DAQ 지원 여부(자료 충돌), FUXA의 외부 알람 확인 연동 방식, eKuiper·Proton의 CEP·late event·복구 세부, Telegraf outputs.postgresql 세부, Mosquitto·Grafana·Prometheus·Telegraf·LiteLLM·LangGraph·Neo4j Community의 현행 라이선스 문구(일반적으로 OSI 라이선스로 알려져 있으나 이번 조사에서 원문 미확인), EdgeX compose 컨테이너 수, Apache AGE LICENSE 원문(ASF 최상위 프로젝트이므로 Apache-2.0일 가능성 높음).
- **버전 주의:** 사용자가 제시한 "Kafka 4.2.x"와 달리 Apache Kafka 블로그에는 4.2.1과 함께 4.3.0(2026-05-22, 4.2.0 이후 25개 KIP)과 4.3.1(2026-06-25, Kafka Streams RocksDB 네이티브 메모리 누수 수정) 발표가 있다. FUXA 1.3.4는 ICSA-26-181-02의 영향 범위(≤1.3.1) 밖이다.
- **라이선스 경계:** EMQX License FAQ에 따르면 BSL 1.1에서 v5.9.0+는 개발·테스트·비프로덕션 용도로 자유롭게 쓸 수 있고, 프로덕션에서는 "Additional Use Grant"로 단일 노드 인스턴스만 무료로 운영할 수 있다(이전 Apache 2.0 버전은 Apache 2.0으로 남는다). 그러나 이는 BSL의 추가 사용 허가일 뿐 OSI 라이선스가 아니다. OpenQTT(EMQX 5.8.9의 Apache-2.0 포크)는 커뮤니티 이슈 단계로 확인되었을 뿐 유지보수 성숙도는 [미검증]이다. UMH Core는 코드가 Apache-2.0이어도 내장 Redpanda가 BSL이라 제약에 맞지 않는다.
- **교육용 전제:** 여기서 제안한 단순화는 단일 머신·가상 공정·12태그 전제다. 실제 플랜트(수천 태그, 다중 사이트, SIS 존재)에서는 Kafka·전용 히스토리안·알람 관리 소프트웨어를 두는 판단이 달라질 수 있다.
- 각 주장에 대응하는 URL 링크는 별도 인용 처리 단계에서 붙는다. 이 문서 본문에는 근거 이름과 날짜만 적었다.

## 출처

1. [\[FEATURE\] Support InfluxDB V3 as DAQ database · Issue #2325 · frangoteam/FUXA](https://github.com/frangoteam/FUXA/issues/2325)
2. [eKuiper Rules Engine - EdgeX Foundry Documentation](https://docs.edgexfoundry.org/2.4/microservices/support/eKuiper/Ch-eKuiper/)
3. [A Notice on the EMQX 5.8 Open Source Version End-of-Life and Future Product Strategy | EMQ](https://www.emqx.com/en/news/a-notice-on-the-emqx-5-8-open-source-version)
4. [EMQX Adopts Business Source License to Accelerate MQTT + AI Innovation | EMQ](https://www.emqx.com/en/news/emqx-adopts-business-source-license)
5. [Introducing Eclipse Mosquitto 2.1 | Cedalo](https://www.cedalo.com/blog/introducing-eclipse-mosquitto-2-1)
6. [Apache Kafka 4.2.0 Release Announcement | Apache Kafka](https://kafka.apache.org/blog/2026/02/17/apache-kafka-4.2.0-release-announcement/)
7. [Apache Flink 2.2.1 Release Announcement | Apache Flink](https://flink.apache.org/2026/05/15/apache-flink-2.2.1-release-announcement/)
8. [Query data | Get started with InfluxDB 3 Core | InfluxDB 3 Core Documentation](https://docs.influxdata.com/influxdb3/core/get-started/query/)
9. [InfluxDB 3 Core configuration options | InfluxDB 3 Core Documentation](https://docs.influxdata.com/influxdb3/core/reference/config-options/)
10. [GitHub - apache/age: Graph database optimized for fast analysis and real-time data processing. It is provided as an extension to PostgreSQL. · GitHub](https://github.com/apache/age)
11. [Apache AGE, Graph database optimized for fast analysis and real-time data processing. It is provided as an extension to PostgreSQL.](https://age.apache.org/release-notes/)
12. [Releases · frangoteam/FUXA](https://github.com/frangoteam/FUXA/releases)
13. [What Is ISA-18.2? Alarm Lifecycle Guide](https://www.merobix.com/blog/what-is-isa-18-2)
14. [SP 800-82 Rev.2 DRAFT Guide to Industrial Control Systems ...](https://csrc.nist.gov/files/pubs/sp/800/82/r2/final/docs/sp800_82_r2_draft.pdf)
15. [NIST SP 800-82 Rev. 3 OT Network Segmentation: What Federal Organizations Should Implement - Anchor Defense](https://anchor-defense.com/articles/nist-800-82-ot-network-segmentation/)
16. [Unified Namespace | United Manufacturing Hub](https://umh.docs.umh.app/docs/architecture/data-infrastructure/unified-namespace/)
17. [Cryogenics and purification systems of the ICARUS T600 detector installation at Fermilab](https://arxiv.org/pdf/2509.18392)
18. [Using the IEC 62443 framework to comply with NIST SP 800-82: A CISO's guide](https://shieldworkz.com/blogs/using-the-iec-62443-framework-to-comply-with-nist-sp-800-82-a-ciso-s-guide)
19. [GitHub - frangoteam/FUXA: Web-based Process Visualization (SCADA/HMI/Dashboard) software · GitHub](https://github.com/frangoteam/FUXA)
20. [@frangoteam/fuxa | Snyk](https://snyk.io/advisor/npm-package/@frangoteam/fuxa)
21. [\[FEATURE\] Support QuestDB as a DAQ database backend · Issue #2114 · frangoteam/FUXA](https://github.com/frangoteam/FUXA/issues/2114)
22. [codebreaker-la/target-ecvebench-fuxa-001-19c2471833e4 | DeepWiki](https://deepwiki.com/codebreaker-la/target-ecvebench-fuxa-001-19c2471833e4)
23. [Release v1.3.1 · frangoteam/FUXA](https://github.com/frangoteam/FUXA/releases/tag/v1.3.1)
24. [HowTo setup Alarms · frangoteam/FUXA Wiki · GitHub](https://github.com/frangoteam/FUXA/wiki/HowTo-setup-Alarms)
25. [Frangoteam FUXA SCADA/HMI | CISA](https://www.cisa.gov/news-events/ics-advisories/icsa-26-181-02)
26. [CVE-2026-13207 - Vulnerability Details - OpenCVE](https://app.opencve.io/cve/CVE-2026-13207)
27. [Settings · frangoteam/FUXA Wiki · GitHub](https://github.com/frangoteam/FUXA/wiki/Settings)
28. [Storage to InfluxDB V2 seemingly limited to 1 Hz · frangoteam/FUXA · Discussion #2048](https://github.com/frangoteam/FUXA/discussions/2048)
29. [Better Historical Alarms · frangoteam/FUXA · Discussion #2053](https://github.com/frangoteam/FUXA/discussions/2053)
30. [Alarms settings with authorization (operator) · Issue #329 · frangoteam/FUXA](https://github.com/frangoteam/FUXA/issues/329)
31. [\[BUG\] TDengine historian results in unordered points, also data structure in TDengine is poor · Issue #1489 · frangoteam/FUXA](https://github.com/frangoteam/FUXA/issues/1489)
32. [Eclipse Mosquitto 2.1 Release Review | projects.eclipse.org](https://projects.eclipse.org/projects/iot.mosquitto/reviews/eclipse-mosquittotm-2.1-release-review)
33. [NIST Special Publication NIST SP 800-82r3 Guide to Operational Technology](https://nvlpubs.nist.gov/nistpubs/SpecialPublications/NIST.SP.800-82r3.pdf)
34. [NIST SP 800-82 Explained: 12 Questions and Answers About OT Security](https://www.securityscientist.net/blog/12-questions-and-answers-about-nist-sp-800-82/)
35. [Comparing GridDB and TimescaleDB | GridDB: Open Source Time Series Database for IoT](https://www.griddb.net/en/blog/griddb-vs-timescaledb)
36. [TimescaleDB: Time-Series Optimizations for PostgreSQL | Gold Lapel](https://goldlapel.com/glossary/postgres-extensions/timescaledb)
37. [5 TimescaleDB Alternatives in 2026: An Honest Comparison | Basekick Labs](https://basekick.net/blog/timescaledb-alternatives-2026)
38. [Releases · apache/age](https://github.com/apache/age/releases)
39. [Connect MQTT devices to NATS | NATS Documentation](https://docs.nats.io/learn/mqtt/)
40. [MQTT | NATS Docs](https://docs.nats.io/running-a-nats-service/configuration/mqtt)
41. [Your first MQTT client | NATS Documentation](https://docs.nats.io/learn/mqtt/your-first-mqtt-client)
42. [NATS.io – Cloud Native, Open Source, High-performance Messaging](https://nats.io/download/)
43. [M11-14: nats-server 2.15 caps streams at 1000 consumers by default — NUTS (one consumer per SSE client) returns terminal 503s from the 1001st client · Issue #110 · ideaconnect/nuts](https://github.com/ideaconnect/nuts/issues/110)
44. [nats-server/server/README-MQTT.md at main · nats-io/nats-server](https://github.com/nats-io/nats-server/blob/main/server/README-MQTT.md)
45. [Redpanda Licensing](https://docs.redpanda.com/streaming/23.3/get-started/licenses.md)
46. [Redpanda vs. Apache Kafka: A Deep Dive into Modern Event Streaming Platforms | AutoMQ Blog](https://www.automq.com/blog/redpanda-vs-apache-kafka-event-streaming)
47. [eKuiper: Lightweight data stream processing engine for IoT edge](https://ekuiper.org/)
48. [Timeplus Proton | Timeplus](https://docs.timeplus.com/proton)
49. [quix-streams/README.md at main · quixio/quix-streams](https://github.com/quixio/quix-streams/blob/main/README.md)
50. [GitHub - SteveYurongSu/proton: A streaming SQL engine, a fast and lightweight alternative to ksqlDB and Apache Flink, 🚀 powered by ClickHouse.](https://github.com/SteveYurongSu/proton/)
51. [The Past and Present of Stream Processing (Part 23): Python-Native Ultra-Fast Streaming with Quix Streams | by Gang Tao | Medium](https://taogang.medium.com/the-past-and-present-of-stream-processing-part-23-python-native-ultra-fast-streaming-with-quix-8fdc83946ab8)
52. [ekuiper module - github.com/lf-edge/ekuiper - Go Packages](https://pkg.go.dev/github.com/lf-edge/ekuiper)
53. [Timeplus Proton: Open Source](https://www.timeplus.com/proton)
54. [ANSI/ISA 18.2-2016, Alarm Systems for the Process Industries - The ANSI Blog](https://blog.ansi.org/ansi/ansi-isa-18-2-alarm-systems-process-industries/)
55. [ISA-18 Series of Standards](https://www.isa.org/standards-and-publications/isa-standards/isa-18-series-of-standards)
56. [Alarm Management and ISA-18 – A Journey, Not a Destination White Paper exida](https://www.exida.com/articles/ALARM-MANAGEMENT-AND-ISA-18-A-JOURNEY-NOT-A-DESTINATION.pdf)
57. [Alarm Management in SCADA: ISA-18.2 Implementation Guide](https://ifactoryapp.com/blog/alarm-management-scada-isa-18-2)
58. [GitHub - united-manufacturing-hub/united-manufacturing-hub: The data platform for manufacturing · GitHub](https://github.com/united-manufacturing-hub/united-manufacturing-hub)
59. [Introduction | UMH Docs](https://docs.umh.app/)
60. [Architecture | United Manufacturing Hub](https://umh.docs.umh.app/docs/architecture/)
