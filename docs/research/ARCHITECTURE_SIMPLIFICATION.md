# V1 구조 단순화 검토서 — 경로 미로·기능 중복 점검과 최소 구성안

> 이 문서만 읽어도 이해하고 실행할 수 있게 썼다. 다른 문서를 참조하지 않는다.
> 기준일은 2026-09-28이다. 버전·라이선스는 작업 당일 공식 릴리스 페이지와 LICENSE 파일로 다시 확인한다.
> 모든 판단은 문헌과 구조 분석에 근거한다. **성능 수치는 측정하지 않았다.** 확정은 §9 실험으로 한다.

---

## 0. 결론 요약

| 질문 | 답 |
|---|---|
| 목적 흐름이 맞는가 | 맞다. 수집 → 이상탐지 → 알람 표시 → 이력 조회 → 조사·승인 → 제어 → 운영 감시 |
| 경로가 미로인가 | **그렇다.** 알람이 MQTT → Kafka → Flink → Kafka → Telegraf → MQTT → FUXA로 되돌아온다. 화면까지 약 8 hop이다 |
| 기능이 중복되는가 | **그렇다.** 메시지 중계가 5중(EMQX·Telegraf×3·Kafka)이고, 화면·설비 쓰기·저장소가 각각 2~3중이다 |
| 비어 있는 곳은 | 알람 상태(발생·확인·해제·셸빙)를 책임지는 곳이 없다 |
| 강제 교체 | EMQX. 5.9+는 BSL(비 OSI)이고, 5.8 오픈소스판은 2026-02-28에 지원이 끝났다 |
| 유지해야 할 분리 | 운전 HMI(FUXA)와 업무·AI UI(Vue)의 분리, HMI의 설비 직접 폴링, AI 명령의 승인·재검사·read-back 경로. 이것들은 중복이 아니라 현업 원칙이다 |
| 추천 | **대안 C: MQTT 단일 백본.** 컨테이너 약 30개 → 약 12개, 알람→화면 약 8 hop → 2 hop. 목적 기능은 모두 유지한다 |

---

## 1. 전제와 제약

- **규모**: 교육·실습용 가상 공정, 단일 머신 Docker Compose, 계측 태그 12개.
- **라이선스**: IoT·SCADA 소프트웨어는 OSI 승인 오픈소스여야 하고 비용이 0원이어야 한다. BSL·SSPL·TSL·RCL 같은 조건부 무료, 체험판, 비상업 전용, 상용은 제외한다. 예외는 LLM API 비용 하나다.
- **비중**: IoT·SCADA(L1~L6)가 중심이고, AI(L7~L9)는 유지 위주로 가볍게 다룬다.

---

## 2. V1 현재 흐름

```
[수집]   가상설비 ─Modbus─▶ EdgeX ─▶ EMQX ─▶ Telegraf#1 ─▶ Kafka raw
[처리]   Kafka raw ─▶ Flink 규칙(상·하한, Z-Score, CEP) ─┐
                    └▶ Flink ONNX(Autoencoder) ───────┴▶ Kafka clean / score / alerts
[저장]   Kafka raw·clean·score ─▶ Telegraf#2 ─▶ InfluxDB ─▶ Grafana
[알람]   Kafka alerts ─▶ Telegraf#3 ─▶ EMQX ─▶ FUXA "최근 알람"          ← 약 8 hop 왕복
         Kafka alerts ─▶ 알람 워커 ─▶ PostgreSQL(사건) ─▶ AI 조사 ─▶ 승인 ─▶ Pilot
[화면]   FUXA ─Modbus 직접 폴링·조작─▶ 가상설비                            ← EdgeX와 이중 폴링
         Vue ─백엔드 API─▶ Modbus 쓰기                                    ← 쓰기 경로 3개
[운영]   Prometheus(EMQX·Kafka·Flink 지표) ─▶ Alertmanager, Grafana
[저장소] InfluxDB + PostgreSQL + Neo4j (3개)
```

---

## 3. 기능 중복 한눈에 보기

| 기능 | V1에서 담당하는 곳 | 상태 |
|---|---|---|
| 설비 읽기 | EdgeX, FUXA, Pilot(/state) | 3중. 운전용·분석용 분리 자체는 원칙에 맞지만 수집기가 과함 |
| 설비 쓰기 | FUXA, Vue 백엔드, Pilot | **3중 → 2개로 축소 필요** |
| 메시지 중계·변환 | EMQX, Telegraf#1·#2·#3, Kafka | **5중 → 과잉** |
| 이상탐지 | Flink 규칙, Flink ONNX | 2개 작업. 한 프로세스로 합칠 수 있음 |
| 시계열 저장 | InfluxDB | PostgreSQL로 합칠 수 있음 |
| 관계 저장 | Neo4j | 설비 6개 규모에서는 PostgreSQL로 충분 |
| 실시간 화면·알람 표시 | FUXA, Vue | 2중. 역할을 다시 나누면 해소됨 |
| 추세·이력 화면 | Grafana (FUXA도 일부 가능) | 역할이 다르므로 유지 권장 |
| 운영 지표·경보 | Prometheus, Alertmanager (Grafana도 가능) | 12태그 규모에서는 과함 |
| 알람 상태 관리 | 없음(Vue 확인 버튼, 워커, FUXA에 흩어짐) | **공백. 소유자 지정 필요** |
| 승인 워크플로 | Vue(UI), LangGraph(대기·재개), Pilot(실행) | 층위가 달라 중복 아님 |

---

## 4. 컴포넌트별 판정

| 컴포넌트 | 판정 | 이유 | 제거 시 잃는 것 | 대체 |
|---|---|---|---|---|
| EdgeX | **제거** | 12태그·설비 1대에는 장치 추상화 비용이 더 큼 | 장치 프로파일 추상화 학습 | Telegraf 1개(inputs.modbus) |
| EMQX | **교체(필수)** | BSL, 5.8 지원 종료 | 룰 엔진, 대시보드 | Mosquitto 2.1.x (내장 WebSocket) |
| Telegraf#1 (MQTT→Kafka) | **제거** | 백본을 하나로 하면 필요 없음 | 없음 | — |
| Telegraf#2 (Kafka→InfluxDB) | **통합** | 수집 Telegraf가 저장까지 동시에 가능 | 없음 | 1회 폴링 → MQTT + PostgreSQL 두 곳에 출력 |
| Telegraf#3 (Kafka→MQTT) | **제거** | 순수 되돌림 다리 | 없음 | 탐지기가 MQTT에 직접 발행 |
| Kafka | **조건부 제거** | 12태그에서는 얻는 것보다 hop이 큼 | 오프셋 재처리, 소비자별 독립 진도, 대량 버퍼 | PostgreSQL 이력 재생, 또는 NATS JetStream |
| Flink (2개 작업) | **대체 권장** | 규모 대비 무거움 | 워터마크·late event 표준 처리, 체크포인트 | Python 탐지기 1개(규칙 + Z-Score + CEP + onnxruntime) |
| InfluxDB | **통합** | InfluxDB 3 Core는 쿼리 파일 한도(기본 약 72시간)가 있고 Flux를 지원하지 않음. FUXA는 InfluxDB 3을 지원하지 않음 | 시계열 전용 함수 | PostgreSQL (+TimescaleDB Apache 에디션 선택) |
| PostgreSQL | **중심 저장소로 승격** | 업무·시계열·관계·알람·감사를 한곳에 | — | — |
| Neo4j | **통합 권장** | 설비 6개 관계는 재귀 CTE로 충분 | Cypher, 그래프 시각화 | 재귀 CTE, 또는 Apache AGE(openCypher) |
| FUXA 1.3.4 | **유지(운전 HMI 전담)** | 운전 화면은 제어기에 직결해야 함 | — | 보안 버전 필수, 인증 활성화 |
| Vue | **유지(역할 축소)** | 업무·AI UI는 운전 화면과 분리가 원칙 | 공정 그림·기동/정지 중복 | 사건·advisory·AI·승인·감사만 담당 |
| Grafana | **유지(권장)** | 엔지니어 분석 추세와 운영 패널, 운영 경보를 한곳에 | — | FUXA 추세는 운전원 단기 추세용 |
| Prometheus | **선택 모듈** | 감시 대상이 크게 줄어듦 | 지표 장기 이력, PromQL | Docker healthcheck + Mosquitto $SYS + 탐지기 heartbeat → Grafana |
| Alertmanager | **제거** | 억제·그룹 기능이 이 규모에서 불필요 | 억제·그룹 정교함 | Grafana Alerting |
| 알람 워커 | **alarm-core로 승격** | 알람 상태의 소유자가 필요 | — | 백엔드 안의 alarm-core 모듈 |
| Pilot | **유지(필수)** | 상위 시스템 쓰기의 유일한 관문 | — | — |
| LangGraph | 유지 | 사람 승인 대기·재개 | — | — |
| LiteLLM | 조건부 유지 | 모델이 하나면 SDK 직접 호출도 가능 | 모델 교체 편의 | 공급자 SDK |

---

## 5. 구간(hop)별 판정

| 구간 | V1 | 현업 관행 | 판정 | 개선안 |
|---|---|---|---|---|
| 설비 → 수집 | EdgeX와 FUXA가 이중 폴링 | HMI는 제어기를 직접 읽는다. 분석 수집은 별도 경로로 둔다 | 분리는 유지, 수집기는 1개로 | 운전: FUXA 직접. 분석: Telegraf 1개(읽기 전용) |
| EdgeX 내부 → MQTT | 장치 → 버스 → 앱 서비스 → 브로커 | 소규모에서는 수집기가 브로커로 직접 발행 | 제거 | Telegraf가 MQTT로 직접 발행 |
| MQTT → Kafka | Telegraf#1 다리 | 이중 백본은 대규모·다중 사이트 전제 | 제거 | 단일 백본 |
| Kafka → Flink×2 → Kafka | 작업마다 결과를 되돌림 | 대규모 표준 패턴 | 통합 | Python 탐지기 1개가 MQTT 구독 → MQTT·DB 발행 |
| Kafka → InfluxDB | 별도 적재 | 싱크 커넥터 | 단순화 | 수집 시점에 PostgreSQL로 바로 적재 |
| **알람 → FUXA** | Kafka → Telegraf#3 → EMQX → FUXA | HMI는 알람을 직접 받는다 | **제거(핵심 개선)** | 탐지기 → Mosquitto(advisory, retained) → FUXA·Vue: **2 hop** |
| 알람 → 사건 | 워커 → PostgreSQL | 알람 저널·사건 DB | 유지 | alarm-core가 advisory 구독 → 상태 저장 → 사건 등록 |
| 제어 경로 | FUXA / Vue / Pilot 3개 | 운전원은 HMI에서 직접 조작하고, 상위 시스템은 통제된 관문 하나만 거친다 | 3 → 2 | Vue 쓰기 제거. Pilot만 자동·승인 명령 |
| 운영 감시 | Prometheus → Alertmanager | 대규모 IT 운영 표준 | 축소 | healthcheck·$SYS·heartbeat → Grafana Alerting |

---

## 6. 단순화 대안 비교

점수는 20점 만점이다. 현업 정합성, 단순성, 기능 보존, 도입 속도를 각 5점으로 매겼다. 실측 전 문헌 기준이다.

| 대안 | 흐름 요약 | 컨테이너(추정) | 알람→화면 | 잃는 기능 | 점수 |
|---|---|---|---|---|---|
| V1 (기준) | 이중 백본 + Flink + 저장소 3개 | 약 27~33 | 약 8 hop | — | — |
| A 보수적 최소 수정 | Telegraf → Kafka → Flink(1작업) → alarm-core → Mosquitto → FUXA | 약 18~20 | 3 hop | 거의 없음 | 16 |
| B FUXA 중심 | FUXA가 폴링·알람·저장 + Python 탐지기 | 약 9~10 | 2 hop | 재처리, 분석 추세, 운영 지표. 분석이 HMI에 종속됨 | 15 |
| **C MQTT 단일 백본 (추천)** | FUXA 직접(운전) + Telegraf → Mosquitto → Python 탐지기 → advisory → FUXA·Vue, 저장은 PostgreSQL 하나 | 약 11~12 | **2 hop** | 로그 재처리(DB 재생으로 대체), 워터마크 표준 | **17** |
| C2 NATS 변형 | C에서 브로커만 NATS(MQTT + JetStream) | 약 11~12 | 2 hop | MQTT v5 불가, NATS→MQTT는 QoS 0 | 15 |
| D PostgreSQL 중심 | 브로커 없이 DB 알림(LISTEN/NOTIFY) | 약 8~9 | 2~3 hop | 이벤트 스트림 개념, FUXA의 MQTT 수신 | 13 |

---

## 7. 추천 구성 (대안 C)

### 7.1 컨테이너 (모두 OSI 오픈소스)
| 필수 (11~12개) | 선택 모듈 (실습용) |
|---|---|
| sim(가상설비), fuxa, telegraf, mosquitto, detector(Python), backend(API + alarm-core + Vue), postgres, grafana, agent(LangGraph), litellm, pilot | prometheus(+cAdvisor), NATS 또는 Kafka(재처리 실습), flink(이벤트타임 실습), edgex(장치 추상화 실습) |

### 7.2 흐름도
```
[가상설비] Modbus + HTTP /state + 고압 인터록(PLC 역할) + 이상 주입
   │
   ├─ 운전 경로 ── Modbus 직접 폴링·쓰기 ──▶ FUXA
   │                                        (공정 그림, 기동/정지, 설정값, 공정 알람, 단기 추세, advisory 패널)
   │
   └─ 분석 경로(읽기 전용) ──▶ Telegraf 1개
                                ├─▶ Mosquitto  plant/<구역>/<설비>/<태그>
                                └─▶ PostgreSQL raw        (1회 폴링, 2곳 출력 → 값 불일치 없음)

Mosquitto ──▶ Python 탐지기 (상·하한 / Z-Score / CEP / ONNX)
               ├─▶ plant/<설비>/advisory/<규칙>  (QoS1, retained) ──▶ FUXA advisory 패널, Vue
               ├─▶ score·clean ──▶ PostgreSQL
               └─▶ heartbeat ──▶ PostgreSQL(운영)

alarm-core ── advisory 구독 ──▶ PostgreSQL alarm(상태·결합·셸빙) ──▶ 사건 등록
Vue(업무·AI UI) ──▶ 사건 → 분석 시작 → Agent(LangGraph + LiteLLM, 설비 관계=PostgreSQL) → 승인/반려
                  ──▶ Pilot: 허용목록 → 조건 재검사 → Modbus 쓰기 → read-back → 감사 기록
Grafana ── PostgreSQL 이력 추세 + 운영 패널 + 운영 경보
```

### 7.3 설계 원칙
| 영역 | 원칙 |
|---|---|
| 읽기 | 운전 경로와 분석 경로는 분리하되, 경로마다 수집기는 하나만 둔다. 분석 경로는 한 번 읽어 두 곳에 쓴다 |
| 알람 | 공정 알람(상·하한, 고압)은 FUXA가 소유한다. 분석 advisory(Z-Score, CEP, AE)는 alarm-core(PostgreSQL)가 소유한다 |
| 쓰기 | 운전원은 FUXA, 승인된 자동 명령은 Pilot만 쓴다. Vue와 AI는 직접 쓰지 않는다. 인터록은 가상설비(PLC 역할) 안에 둔다 |
| 저장 | PostgreSQL 하나에 업무·시계열·관계·알람·감사를 둔다. FUXA 로컬 저장은 운전 단기 추세용이다 |

---

## 8. 알람·제어 권장 원칙

### 8.1 알람 (ISA-18.2 방식)
| 항목 | 공정 알람 | 분석 advisory |
|---|---|---|
| 예 | TT-101 고온, PT-101 고압 | Z-Score 이탈, 전류↑ 후 진동↑(CEP), 모델 점수 |
| 소유자 | FUXA 알람 엔진 | alarm-core (PostgreSQL) |
| 상태 | 발생 → 확인 → 복귀 | 발생 → 확인 → 복귀 + 셸빙(만료 시 자동 복귀) |
| 표시 | FUXA 알람 화면 | FUXA advisory 패널, Vue |
| 확인 | FUXA | Vue |
| 원칙 | 합리화된 알람만 운전원 목록에 | 운전원 알람과 섞지 않고 별도로 표시 |

FUXA 알람은 발생·확인·이력 표시에는 충분하다. 셸빙, 알람 KPI(시간당 건수, 채터링), 이력 검색·내보내기는 약하므로 alarm-core에서 구현한다.

### 8.2 제어
| 원칙 | 내용 |
|---|---|
| 인터록 위치 | 제어기(가상설비) 안. HMI와 AI는 우회할 수 없다 |
| 운전원 조작 | FUXA → Modbus 직접. 인증 활성화, 역할 권한, 1.3.4 이상, 격리 네트워크 |
| 상위 시스템 명령 | Pilot 하나로만. ① 쓰기 허용목록 ② 승인 토큰(승인 ID·승인자·만료) ③ 실행 직전 조건 재검사(/state seq, 인터록) ④ 쓰기 후 read-back ⑤ 불일치 시 실패로 기록하고 재시도하지 않음 ⑥ 감사 기록 |
| IT → OT | 업무·AI 계층에서 제어로 직접 연결하지 않고 통제된 관문 하나만 둔다 |

---

## 9. 검증 실험 (측정값 칸은 비움)

| ID | 확인할 것 | 비교 | 방법 | 지표 | 판정 기준 | V1 | C |
|---|---|---|---|---|---|---|---|
| E1 | 알람→화면 지연 | V1 / A / C | 이상 주입 → FUXA·Vue 표시, 100회 | p50/p95/최대 | C의 p95 ≤ V1 (허용치는 팀이 확정) | | |
| E2 | 구성 복잡도 | V1 / C | compose와 경로 분석 | hop 수, 컨테이너 수, 설정 파일 수 | hop 50% 이상 감소 | | |
| E3 | 자원 | V1 / C | 1시간 정상 운전 | 메모리·CPU 합계, 기동 시간 | 뚜렷한 감소 | | |
| E4 | 브로커 장애 | V1 / C | 브로커 30초 정지 후 재기동 | 유실·중복, 복구 시간, 운전 화면 영향 | 운전 화면 영향 0 | | |
| E5 | 탐지기 장애 | Flink / Python | 강제 종료 후 재기동 | 첫 판정까지 시간, 윈도 복구, 누락 advisory | 윈도가 DB로 복구됨 | | |
| E6 | 재처리 | Kafka / DB 재생 / JetStream | 과거 1시간 재생 | 결과 동일성, 소요 시간 | 같은 advisory 집합 재현 | | |
| E7 | 화면 값 = 이력 값 | 이중 폴링 / 1회 폴링·2곳 출력 | 동시각 값 비교, 10,000 샘플 | 불일치 비율, 시간차 | 허용오차 이내 99% 이상 | | |
| E8 | CEP 정확도 | Flink CEP / Python 상태 머신 | 시나리오 50회 + 순서 역전·지연 | 탐지율, 오탐, 지연 이벤트 처리 | 판정 일치 95% 이상 | | |
| E9 | 제어 안전성 | Pilot | 승인 후 조건 변화, read-back 불일치 주입 | 부적합 명령 실행 수, 감사 누락 | 둘 다 0건 | | |
| E10 | 알람 수명주기 | alarm-core | 발생→확인→복귀, 셸빙 만료, 중복 결합 | 상태 전이 정확도 | 상태도와 100% 일치 | | |
| E11 | 운영 감시 대체 | Prometheus+AM / healthcheck+Grafana | 컨테이너 kill, 탐지기 정지 | 경보까지 시간, 누락 | 둘 다 탐지 | | |
| E12 | 보안 기본선 | FUXA 1.3.1 / 1.3.4 | 격리 환경에서 인증 우회 요청 | 우회 여부 | 1.3.4에서 차단 | | |

### 기능 보존 체크리스트 (모든 대안 공통)
| 항목 | V1 | A | B | C | D |
|---|---|---|---|---|---|
| 12태그 수집 | | | | | |
| 상·하한 / Z-Score / CEP / 모델 탐지 | | | | | |
| 공정 알람 표시·확인 | | | | | |
| advisory 표시·확인·셸빙 | | | | | |
| 이력 조회 (72시간 초과 구간 포함) | | | | | |
| 사건 등록·중복 결합 | | | | | |
| AI 조사 (설비 관계 질의) | | | | | |
| 승인 → 재검사 → 정지 → read-back | | | | | |
| 조작 이력·감사 | | | | | |
| 운영 감시·경보 | | | | | |
| 재처리 | | | | | |

---

## 10. 에이전트 실행 순서

한 번에 한 가지만 바꾸고, 바꿀 때마다 §9 체크리스트와 안전 실험(E9)을 다시 돌린다.

| 순서 | 작업 | 확인 실험 | 되돌릴 조건 |
|---|---|---|---|
| 1 | FUXA 1.3.4 적용, 모든 이미지 버전 고정 | E12 | FUXA 동작 이상 |
| 2 | EMQX → Mosquitto 교체 (토픽 그대로) | E1, E4 | 알람·수집 누락 |
| 3 | 알람 되돌림 제거: advisory를 MQTT로 직접 발행 → FUXA·Vue 구독 | E1, E2 | 알람 표시 누락 |
| 4 | alarm-core 도입 (알람 상태 소유) | E10 | 사건 등록 누락 |
| 5 | 제어 경로 3 → 2 (Vue 쓰기 제거, Pilot만) | E9 | 운전원 조작 불가 |
| 6 | EdgeX → Telegraf 1개 (1회 폴링·2곳 출력) | E7 | 태그 누락 |
| 7 | Flink → Python 탐지기 (Flink는 선택 모듈로) | E5, E8 | 판정 일치 95% 미만 |
| 8 | Kafka 제거 (재처리는 DB 재생) | E6 | 재처리 결과 불일치 |
| 9 | InfluxDB → PostgreSQL, Grafana 쿼리 이식 | 체크리스트 이력 항목 | 72시간 초과 조회 실패 |
| 10 | Neo4j → PostgreSQL 관계 (재귀 CTE 또는 Apache AGE) | AI 조사 질의 결과 동일성 | 답변 가능 질문 감소 |
| 11 | Prometheus·Alertmanager → healthcheck + Grafana Alerting | E11 | 장애 미탐지 |
| 12 | 최종 회귀 | E1~E12 + 체크리스트 전체 | 하나라도 실패 |

각 단계는 git tag를 남기고 결과를 표에 채운다. 실패도 지우지 않고 기록한다.

---

## 11. 논쟁점

| 주장 | 반론·판단 |
|---|---|
| HMI도 브로커를 구독하면 읽기가 완전히 하나가 된다 | 운전 화면이 IT 계층 장애에 종속된다. 운전 경로는 직접 폴링을 유지하고, 일관성 비용은 E7로 측정한다 |
| Kafka를 빼면 재처리를 잃는다 | 맞다. 12태그 원시 데이터는 모두 PostgreSQL에 있으므로 DB 재생으로 대체한다. 소비자별 독립 오프셋이 교육 목표라면 이중 백본보다 NATS JetStream 단일 백본이 낫다 |
| Flink는 이벤트타임 교육 가치가 크다 | 동의한다. 본선에서 빼고 선택 모듈로 둔다 |
| FUXA 하나로 다 하면 가장 단순하다 | FUXA는 2026년에 인증 우회 보안 권고가 있었고, 알람 이력 검색이 약하며 PostgreSQL·InfluxDB 3 저장을 지원하지 않는다. 분석·AI까지 몰면 운전 화면의 위험이 커진다 |
| 알람 상태는 반드시 한 곳이어야 한다 | 표준이 요구하는 것은 관리 책임이지 물리적 저장소 하나가 아니다. 클래스별 단일 소유자로 충분하다 |
| Neo4j가 AI 연동에 유리하다 | 사실이다. 다만 설비 6개 규모에서는 PostgreSQL로 충분하고, Cypher가 필요하면 Apache AGE를 쓴다 |
| EdgeX는 산업 표준이다 | 이기종 장치가 많을 때 가치가 크다. 가상설비 1대에는 선택 실습 모듈로 둔다 |

---

## 12. 확인된 사실과 미확인 사항

### 12.1 판단에 쓴 사실 (2026-09 기준)
| 항목 | 내용 |
|---|---|
| EMQX | 5.9부터 BSL 1.1. 5.8 오픈소스판은 2026-02-28 지원 종료 |
| Mosquitto | 2.1.x (2.1.2, 2026-02). 내장 WebSocket, SQLite 영속 |
| FUXA | 1.3.4 (2026-08). 1.3.1 이하는 인증 우회 보안 권고 대상(2026-06). 저장소로 SQLite·InfluxDB 1.8/2.x·TDengine을 지원하고, InfluxDB 3·PostgreSQL은 지원하지 않음. 기본 계정 변경과 인증 활성화 필요 |
| InfluxDB 3 Core | 기본 설정에서 쿼리 접근 범위가 약 72시간, Flux 미지원 |
| TimescaleDB | Apache 에디션만 허용(하이퍼테이블·time_bucket). 연속 집계·보존 정책 등은 TSL이라 제외 |
| Kafka | 4.2.0 (2026-02, KRaft 전용). 4.3.x도 공개됨 |
| Flink | 2.2.1 (2026-05) |
| NATS | 2.15 (2026-09). MQTT는 3.1.1만 지원, JetStream 필수 |
| Apache AGE | 1.7.0 (2026-01), PostgreSQL 그래프 확장 |
| 현업 근거 | 운전 HMI는 제어기에 직결하고, 알람 로직은 제어 계층에 있으며 확인은 HMI에서 한다. 상위 시스템의 제어 쓰기는 통제된 관문으로 제한한다 |

### 12.2 미확인 (작업 전 확인 필요)
- FUXA의 QuestDB 저장 지원 여부 (자료가 서로 다름)
- Telegraf의 PostgreSQL 출력 세부 동작
- 경량 스트림 엔진(eKuiper, Timeplus Proton)의 CEP·late event·복구 동작
- Mosquitto·Grafana·Prometheus·Telegraf·LiteLLM·LangGraph·Neo4j Community의 현행 LICENSE 원문
- EdgeX compose의 실제 컨테이너 수

### 12.3 적용 범위
이 단순화는 단일 머신·가상 공정·12태그를 전제로 한다. 수천 태그, 다중 사이트, 별도 안전계장시스템이 있는 실제 플랜트에서는 Kafka·전용 히스토리안·알람 관리 소프트웨어를 둘지 다시 판단해야 한다.
