# HANDOFF — 경남대 제조 AI 실습용 IIoT·SCADA 베이스 (scada-rotation)

갱신 2026-09-29 · 작성 Claude Code
**이 문서가 유일한 정본이다.** 목표·기준·작업 방식·상태는 여기에만 둔다. 실제 파일·실행 상태·사용자 지시가 이 문서와 다르면 실제가 우선이고, 이 문서를 고친다.

---

## 0. 새 세션이 처음 할 일
1. 이 파일을 끝까지 읽는다.
2. 조사 결과를 끝까지 읽는다(모두 `docs/research/deep-2026-09-29/`). 구조와 스택은 함께 본다.
   - `12-industry-structure.md` — 현업 구조, v3·우리 비교, 권장 베이스 (요지 §2-1)
   - `13-industry-detail.md` — 세부 결정 29줄 (요지 §2-2)
   - `14-industry-stack.md` — 칸별 제품·버전·라이선스·지원 기간·메모리 (요지 §2-3)
   - `15-free-options-compare.md` — soft-PLC·엣지·HMI 무료 후보 비교(의뢰서 §8, 요지 §2-3)
   - 조사를 다시 돌릴 때는 의뢰서의 해당 절(§6·§7·§8)을 쓰고 도커 실행 금지를 명시한다.
3. 구조·세부·스택과 §2-3 결정 세 가지를 합쳐 사용자에게 쉬운 말 한 장으로 보고한다(베이스 구조, 칸별 제품·버전, 지금 구조에서 바꿀 것). 확인을 받으면 §2 단계 2로 간다.
4. 시작 전에 실제 상태를 대조한다: `git status`, `docker ps -a`.

## 1. 목표와 방향
- **무엇:** 국립 경남대 제조 AI 과정 학생이 배우고 실습할 IIoT·SCADA 시스템.
- **배포:** 학생 개인 실습용. 학생마다 같은 패키지를 받아 자기 PC 한 대의 Docker Compose로 띄운다(Windows, Docker 메모리 약 7.6 GB). 비용 0원. 각자 똑같이 받아 잘 돌아가면 된다.
- **기준: 2026년 제조 현업의 주류 구조와 스택.** 현업 가정으로 고정한다(설비 다수, 통신 혼재). "설비가 적으니 이 층은 필요 없다" 같은 데모 전제로 층을 빼지 않는다. "현업 주류"는 "현업에서 주로 쓴다"를 알면 되고 채택률 수치는 필요 없다.
- **큰 순서:**
  1. 베이스: 구조 확정 → 칸별 제품·버전 확정 → 한 번에 조립 → 한 번에 검증
  2. 설비 확장: 종류·대수를 늘리고 통신을 섞는다(OPC UA 등)
  3. 시나리오·온톨로지 보강: 풍부하고 자세하게
  → 베이스는 설비가 늘어도 다시 짜지 않아도 되는 구조여야 한다.
- **확장 요구 — 피지컬 AI:** 이 시스템은 이후 피지컬 AI(AI가 현실 설비·로봇을 보고 판단해 움직이게 하는 것)에 쓰인다. 무엇이 필요한지(로봇 층 ROS 2, 카메라·비전, AI의 설비 조작, 디지털 트윈 등)는 사용자도 아직 정하지 않았다 → 에이전트가 조사로 정한다(§2 단계 1-2). 베이스의 AI 명령 경로(사람 승인 → 검증 통로 → PLC 최종 판단)와 설비 등록부는 이 확장의 받침이다.
- **우선순위:** ① 현업 주류 ② 비용 0·라이선스·도커 적합성·지원 기간(같은 제품 안에서 판을 고르는 기준) ③ 경량화.
- **경량화:** 현업 수준(구조·기능·주류 제품)을 유지하면서 효율적으로 가볍게 한다. 층을 빼거나 비주류 제품으로 바꾸지 않는다. 방법은 네 가지다. 성능·안정성이 V1보다 나빠지면 그 경량화는 쓰지 않는다.
  - 같은 제품 안에서 가벼운 지원 판(alpine 등)을 고른다.
  - 설정을 실제 사용량에 맞춘다(JVM 힙, 보존 기간, 로그, 수집 주기).
  - 현업에서도 선택인 기능은 프로필로 켠다.
  - 같은 역할의 중복을 하나로 합친다.
- **참조:** 참조 설계서 v3(다른 팀이 구축·실행한 구조, 내용은 의뢰서 부록 A)와 우리 구조도(`시스템구성도_풀스택_보강본.pdf`, `시스템구성도_실제통신구조_확인본.pdf`)는 비교 대상이다. 판단은 현업 조사 결과로 한다.
- **AI 층(L7~L9):** 구조 그림에는 포함한다. 베이스 단계에서는 AI 코드를 고치지 않는다. 큰 순서 3에서 적용할 원칙은 이렇다.
  - 그래프 DB 필수, 원인 분석은 온톨로지 그래프 추론, 매뉴얼 검색은 임베딩 + 그래프 연결
  - V1 에이전트(LLM + LangGraph + 가드레일)를 유지하고 도구를 더한다. 새 고장은 코드 0줄로 확장한다.
  - 비교는 같은 LiteLLM 설정으로 시나리오당 3회, 정답은 주입한 고장 사실만(순환 평가 금지)
  - 기존 측정 결과: `experiments/EXP-AI`(`harness/tools/report_ai.py`)

## 2. 진행 순서와 지금 위치
| 단계 | 내용 | 상태 |
|---|---|---|
| 1 | 현업 구조 조사(층·길·망·확장·AI 연결), 세부 조사 | 완료(12·13) |
| 1-2 | 피지컬 AI 조사(의뢰서에 절 추가): 2026 제조 피지컬 AI의 뜻과 주류(로봇·AI 공정 제어·비전·디지털 트윈), 참조 구조, 엣지 칸 후보(EdgeX·Node-RED·ROS 2·Zenoh·OPC UA 로봇 표준 등), 우리 베이스에 더할 것, 학생 PC(도커 7.6 GB, GPU 없음)에서 가능한 범위. 질문 목록은 띄우기 전에 사용자에게 보여 준다 | 대기 |
| 2 | 구조 확정: 우리 베이스의 층과 길 목록을 확정하고 사용자에게 한 장으로 보고 | 대기 |
| 3 | 칸별 제품·버전 확정 | 완료(14·15, 결정 3건 §2-3) |
| 4 | 조립 한 번에: V1 코드에서 출발해 확정 구조·스택으로 바꾸고 기능 대응표(§3-4)를 채운다. 엣지는 먼저 Node-RED·EdgeX를 나란히 재서 정한다(§2-3 결정 ①) | 대기 |
| 5 | 검증 한 번에(§3-5) → 나빠진 곳만 고침 → 태그 | 대기 |
| 6 | 보고서(대표님용 짧은 대조 보고 + 쉬운 설명서) → 작업보고 | 대기 |
| 7 | 설비 확장 → 시나리오·온톨로지 | 이후 |

### 2-1. 현업 구조 (근거는 12번 파일)
- **망:** OT(L0~L3), 산업 DMZ(L3.5), IT(L4~5) 세 구역. IT에서 OT로 바로 가는 길은 없다. OT와 DMZ 사이 연결은 OT 쪽이 연다(CISA Defense in Depth 2016). 이 원칙은 제품 선택이 아니라 배치와 규칙으로 지킨다(13번 A6).
- **층(아래부터):** 현장 장치 → 제어기(PLC: 인터록·운전 모드·명령 수용 최종 판단, SIS는 따로) → SCADA/HMI → 엣지 연결·프로토콜 변환(끊기면 저장 후 전송) → 사이트 브로커(UNS) → 맥락화·설비 모델 → 히스토리언 → DMZ 중계 → Kafka형 장부 → 탐지 → 플랫폼 감시 → AI(OT 밖, 읽기 전용) → MES·CMMS·ERP.
- **확장:** 설비가 늘어도 층은 그대로다. ISA-95 설비 이름, 토픽 규칙, 설비 종류별 모델, 엣지 노드로 흡수한다.
- **명령:** 운전원은 HMI → 제어기. 외부·AI 명령은 사람 승인 → 검증 통로 하나 → 제어기가 최종 판단(NAMUR NE 178). Sparkplug 명령은 QoS 0, retain=false.
- **AI:** 읽고 추천만 한다. AI가 제어기에 직접 쓰기를 권하는 표준은 없다.
- **트렌드:** UNS와 Kafka·NATS 백엔드의 결합, DataOps(데이터 모델링·맥락화), 에이전트형 AI 시연 시작(IoT Analytics 2026-01), AI는 OT 밖 읽기 전용(CISA 등 9개 기관 2025-12), ISA-112 SCADA 표준 발행(2026-02), 제조사 절반가량이 데이터·아키텍처 표준화 진행(Deloitte 2025).
- **V1과 비교:**
  - V1에 없는 것: 망 구분, 제어기(PLC) 층, 하나로 모인 명령 검증 길(V1 쓰기 길 3개), 설비 등록부, 알람 수명주기
  - 현업 근거가 없는 것: AI 코드가 설비에 Modbus로 직접 쓰기, FUXA와 EdgeX의 이중 폴링, 결과 확인을 시뮬레이터 전용 HTTP `/state`로 하기
  - 맞는 것: EdgeX 엣지 층, MQTT→Kafka 분리, 사람 승인과 실행 직전 재확인, 허용 조치 목록
- **권장 베이스로 바꿀 것:** ① 망 3구역 ② soft-PLC 층 ③ 쓰기 길을 수동 하나 + 검증 통로 하나로 ④ 결과 확인을 제어기 ACK·상태 토픽으로 ⑤ 설비 등록부를 정본으로 두고 토픽·Kafka 키·Flink 규칙·온톨로지가 같은 ID를 쓴다.
- **v3:** 망·명령 게이트웨이·경보 분리는 현업과 맞다. OT 이력 저장·설비 모델 층·알람 수명주기는 없다.
- **근거 강도:** 공공 표준 원문 중심(URL 39개). 권장안의 메모리 합계는 재지 않았다.

### 2-2. 세부 결정 (근거는 13번 파일 결정 표 29줄)
- **근거 강도:** URL 90개 중 62곳이 검색 요약만 본 것이다. 채택할 핵심 근거(EEMUA 191, ISO 14224, 전력 원격제어 표준 등)는 원문으로 확인한 뒤 확정한다.
- **데이터:** 주기 샘플링 + 변화 필터(deadband). 값마다 출처 시각과 품질(Good/Uncertain/Bad, 끊기면 STALE). 토픽 `{site}/{area}/{line}/{asset}/{kind}/{tag}`, 단위·설명은 등록부 모델에만. Kafka는 데이터 종류별 토픽 + 자산 ID 키, 최소 1회 전달, 소비자가 중복을 거른다. 상향 복제는 OT 브로커가 DMZ 쪽으로 밀어낸다.
- **명령:** HMI → `cmd` → 엣지 → soft-PLC. 확인은 두 겹(PLC ACK + 바뀐 값 재발행). 게이트웨이와 PLC에서 만료·`cmdId` 중복·모드·범위·인터록 검사(근거는 전력 원격제어 표준 IEC 61850·IEC 104 지침, 제조 표준 문장은 없음). 모드는 MTP식 3상태 + 출처 채널. 시뮬레이터에는 soft-PLC 하나만 붙는다.
- **알람:** Flink 결과는 ISA-18.2 "alert"(분석 경고)로 알람 목록과 따로 표시. 공정 알람 상태는 HMI, alert·사건 상태는 IT 사건 저장소. 반복 alert는 사건 하나로 묶고, 설비 정지 때는 설계된 억제. 10분당 건수로 폭주를 본다(EEMUA 191). 플랫폼 경보는 인프라 역할로만.
- **저장:** 이력 정본은 IT 한 곳, OT에는 HMI 단기 추세만. 명령·승인·감사는 추가만 하고 지우지 않는다.
- **확장:** 등록부 = 설비 종류 모델 표 + 설비 개체 표. 생성 스크립트가 EdgeX 장치·토픽·Kafka 키·Flink 범위·온톨로지 노드를 만든다. 온톨로지 고장 칸은 ISO 14224식(모드/메커니즘/원인/조치). OPC UA는 엣지 서비스 하나만 더한다.
- **AI:** 도구는 읽기 전용. 흐름은 제안 → 정비 요청 → 승인 → 명령 요청 → 게이트웨이 → PLC → ACK → 재관측 → 기록.
- **망·보안:** ot/dmz/it 도커 망 3개, 모든 컨테이너가 붙는 공용 망은 두지 않는다. 서비스별 계정 + 토픽 ACL, `cmd` 발행은 HMI와 게이트웨이만. TLS만 축소한다.
- **감시:** 엣지·PLC·시뮬레이터마다 MQTT Will로 연결 상태 토픽(v3 `status`와 분리).
- **확인 못 한 것:** 메모리 수치, FUXA의 ISA-18.2 셸빙, Windows 도커 망 동작. 찾지 못함으로 확정: 데이터 랩과 보안 랩을 합친 교육 사례, UNS 채택 통계, 명령 만료를 요구하는 제조 표준, 이름 있는 공장의 층 구조.

### 2-3. 스택 (근거·버전·이미지 태그는 14번 파일 맨 앞 표)
| 칸 | 권장 | V1 대비 |
|---|---|---|
| 설비 시뮬레이터 | 기존 Python(pymodbus). OPC UA 단계는 Microsoft OPC PLC 2.15.4 | 유지 |
| soft-PLC | OpenPLC Runtime v4.2.4(MIT). 2안은 자체 Python 제어기 | 추가 |
| 엣지 | Node-RED 5.0.x(+node-red-contrib-modbus 5.60.2, node-red-contrib-opcua 0.2.355) 또는 EdgeX 4.0.2 — 조립 때 나란히 재서 확정 | 결정 ① |
| MQTT 브로커 | Mosquitto 2.1.2 하나 | EMQX 대체 |
| DMZ 중계 | Bento 1.21.2 + 자체 명령 게이트웨이 | Telegraf 3개 대체 |
| 장부 | Kafka 4.3.1 | 버전만 |
| 탐지 | Flink 2.2.1 + ZooKeeper HA(2.3 커넥터 나오면 2.3.x) | 버전만 |
| 이력 | InfluxDB 2.9.1 | 버전만 |
| 화면 | FUXA 1.3.4(UNS 구독 + `cmd` 발행) | 유지, 구성 변경 |
| 대시보드 | Grafana 13.2.3 | 버전만 |
| 감시 | Prometheus 3.13 LTS, cAdvisor 0.60.6, kafka-exporter 1.10.0 | 버전만 |
| 설비 등록부 | 자체(YAML/JSON → PostgreSQL 표·Neo4j 노드) | 추가 |
| AI·지식 | Neo4j 5.26 LTS CE, LangGraph, LiteLLM(1.82.7·1.82.8 금지) | 유지, 도구 읽기 전용 |
| 승인 흐름 | 자체(PostgreSQL). BPMN이 필요하면 Operaton 2.1.5 | 유지 |
| 알람 수명주기 | 공정은 FUXA, 분석 alert는 PostgreSQL ISA-18.2 상태표 | 추가 |
| 공용 DB | PostgreSQL 18.6(2030-11 지원) | 공통 |

- **현업 주류와의 관계:** MQTT·Kafka·Flink·Grafana·Prometheus·Neo4j·PostgreSQL은 현업 1위와 같은 오픈소스 본체다. PLC·HMI·히스토리언·엣지는 현업 주류가 상용(CODESYS·벤더 PLC, WinCC·FactoryTalk·Ignition, 상용 히스토리언, Kepware 등)이라 무료 제품으로 대신하고, 학생에게 "현업은 보통 상용"이라고 설명한다.
- **무료 대체품 선택 근거(15번 파일):**
  - **PLC — OpenPLC Runtime v4.2.4.** 후보(OpenPLC·4diac·Beremiz) 중 공식 도커 이미지가 있는 유일한 제품이다. IEC 61131-3 다섯 언어, Modbus·OPC UA 플러그인이 있다. 논문 138편(4diac 88편), Western Carolina 대학 PLC 과목에서 쓴다. 약점: 근거 대부분이 v3 계보이고, v4(2025-08 새 저장소)는 한 회사 개발자 9명뿐이다. 2안(설명용)은 Eclipse 4diac(IEC 61499, 대학 교육 근거가 가장 강함, 도커 이미지 없음).
  - **엣지 — Node-RED 5.0.x(결정 ①).** 산업 논문 486편(EdgeX 33, Telegraf 11, Kura 9, PLC4X 5), OpenJS 재단, Opto 22 산업 제어기 기본 탑재. Modbus 읽기·쓰기, OPC UA, MQTT 모두 무료. 끊김 시 저장·장치 등록부·명령 API는 없어 등록부 생성 흐름과 조립 뒤 검증으로 채운다. 2안 EdgeX(셋 다 기본 제공, 도입 기업 Eaton·Wipro 등).
  - **화면 — FUXA 1.3.4.** 공식 이미지·MQTT 구독·OPC UA·Modbus를 모두 무료(MIT)로 갖춘 유일한 공정 HMI다. 별 5,059, 최근 1년 개발자 29명, 12개월 릴리스 10회 이상. 약점: 재단 없음, 이름 있는 공장·대학 사례 없음, 알람 보류(shelving) 없음. 2안은 Rapid SCADA 6(Apache-2.0, 공장 사례 있음, 공식 도커 이미지 없음 — 직접 빌드 실측 필요).
  - 근거 강도: URL 89개 중 검색 요약만 본 곳 36군데. 무료 제품끼리의 점유율 설문은 없다.
- **상용·제한형을 쓰지 않는 근거:** CODESYS는 라이선스 없이 2시간 데모, Ignition 무료판은 비상업·개인 교육용만, HiveMQ Edge는 설비 쓰기가 유료, ThingsBoard는 4.4부터 BUSL, TimescaleDB 압축·연속 집계는 TSL.

**칸별 선택 근거 — 보고서도 이 틀(현업은 주로 무엇 → 우리는 무엇 → 왜)로 쓴다** (근거는 14·15번 파일)
| 칸 | 현업에서 주로 쓰는 것 | 우리가 쓰는 것 | 왜 |
|---|---|---|---|
| 설비 | 실제 설비 | Python 가상설비(배속 600) | 교육용. 나중에 OPC UA 설비(Microsoft OPC PLC) 추가 |
| PLC | 제조사 하드웨어 PLC, soft-PLC는 CODESYS 등(상용) | OpenPLC Runtime v4.2.4 | 상용·체험판(CODESYS는 라이선스 없이 2시간 데모). 무료 중 유일한 공식 도커 이미지, IEC 61131-3 다섯 언어, 논문 138편, 대학 PLC 과목 사용 |
| 엣지 연결 | Kepware·Ignition Edge·Litmus Edge(상용) | Node-RED 5.0.x(1안) 또는 EdgeX | 상용. Node-RED는 무료 중 산업 논문 486편(EdgeX 33)·OpenJS 재단·Opto 22 탑재·컨테이너 1개, EdgeX는 장치 등록·명령·끊김 시 저장 기본 제공. 조립 때 나란히 재서 확정(결정 ①) |
| MQTT 브로커 | MQTT가 산업 IoT 프로토콜 1위. 브로커는 EMQX·HiveMQ·Mosquitto | Mosquitto 2.1.2 | 현업에서도 널리 씀(내려받기 1위). EMQX는 5.9부터 BSL |
| MQTT→Kafka 중계 | 브로커 내장 Kafka 확장(상용·BSL), Kafka Connect 커넥터(독점 많음) | Bento 1.21.2 + 자체 명령 게이트웨이 | 상용·독점 제외. Bento는 MIT이고 V1과 같은 결과를 냈다 |
| 이벤트 장부 | Kafka | Kafka 4.3.1 | 현업과 같음 |
| 실시간 탐지 | Flink | Flink 2.2.1 | 현업과 같음 |
| 이력 저장 | 상용 히스토리언(AVEVA PI 등) | InfluxDB 2.9.1 | 상용. 무료 시계열 DB 1위(DB-Engines) |
| 화면(SCADA/HMI) | Siemens WinCC·Rockwell FactoryTalk·GE·Ignition(상용) | FUXA 1.3.4 | 상용(Ignition 무료판은 비상업·개인 교육용만). 무료로 MQTT·OPC UA·Modbus를 모두 갖춘 유일한 공정 HMI, 가장 활발히 개발 중 |
| 대시보드 | Grafana | Grafana 13.2.3 | 현업과 같음 |
| 플랫폼 감시 | Prometheus | Prometheus 3.13 LTS | 현업과 같음 |
| 지식 그래프 | Neo4j | Neo4j 5.26 Community | 현업과 같음(무료판) |
| 업무 DB | PostgreSQL | PostgreSQL 18.6 | 현업과 같음 |
| 설비 등록부 | AAS·OPC UA 정보 모델 기반 상용 플랫폼 | 자체(속성 이름은 AAS·ISA-95를 따름) | 무료 정식판 없음(BaSyx 정식판 없음) |
| 승인 흐름 | Camunda 등 BPMN 엔진 | 자체(선택 시 Operaton) | Camunda 7 무료판 종료, 8은 운영 유료 |
| 알람 수명주기 | Hexagon·Honeywell·Yokogawa 등 상용 | FUXA 알람 + PostgreSQL 상태표 | 상용. Alerta는 유지 중단 신호 |

**결정(에이전트 권고로 확정 — 사용자는 전문가가 아니므로 에이전트가 근거로 정한다. 사용자가 바꾸라고 하면 바꾼다):**
1. **엣지는 조립 단계에서 Node-RED와 EdgeX를 나란히 재서 확정한다(1안 Node-RED).** 문헌만으로는 막상막하다.
   - Node-RED: 무료 중 현업 사용 근거가 더 많다(산업 논문 486편 대 33편, OpenJS 재단, Opto 22 산업 제어기 기본 탑재). 컨테이너 1개. 흐름이 눈에 보여 학생이 이해하기 쉽다. 장치 등록·명령 받기·끊김 시 저장은 블록(흐름)으로 조립해야 한다(흐름은 설비 등록부에서 생성).
   - EdgeX: 장치 등록·명령 창구·끊김 시 저장이 기본으로 있다. 컨테이너 약 10개. V1이 이미 쓴다(1356/1356 수집 실측). 다음 판(Queensland)이 나오면 올린다.
   - **나란히 재는 것**(같은 가상설비·soft-PLC에 붙여 짧게): 12태그 누락 0 / 화면 명령이 PLC까지 가고 ACK가 돌아옴 / 10초 단절 뒤 복구 시간·유실이 V1(7.3 s·120 태그·초)보다 나쁘지 않음 / 메모리 / 설비 한 대 추가를 등록부에서 자동 생성할 수 있음.
   - **정하는 규칙:** 둘 다 합격하면 Node-RED(가볍고 더 많이 쓰임). 하나만 합격하면 그쪽. 결과는 decision-log에 숫자로 남긴다.
   - 기능 보존: 수업 자료가 쓰는 `edgex/telemetry` 계측 토픽은 어느 쪽이든 같은 모양으로 낸다. Node-RED로 가면 수업의 EdgeX 차시가 바뀌며 보고서의 "바뀐 것"에 적는다.
   - 학생 설명: 현업 엣지 칸의 주류는 Kepware 같은 상용이다. EdgeX는 "장치 등록·명령 API를 갖춘 플랫폼형", Node-RED는 "흐름을 이어 만드는 범용 도구"로 비교해 가르친다.
2. **버전 올림 규칙:** 패키지를 다시 만들 때(학기마다) 같은 메이저 안 최신 부 버전으로 올리고, 지원이 끝나는 판은 다음 판으로 올린다(§3-1). 판별 지원 종료일은 제품 선택의 이유로 쓰지 않는다.
3. **Flink는 2.2.1로 시작하고, 2.3용 Kafka 커넥터(FLINK-40121)가 나오면 2.3.x로 올린다.** 실시간 탐지의 현업 1위이고 판정 70/70·재시작 자동 복구를 실측했다.

**그 밖의 사실:**
- 메모리: 실측이 있는 칸만 더해 약 4,960 MiB. 미측정 5칸(OpenPLC, 엣지, 게이트웨이, AI 백엔드·LiteLLM, 승인). 문서 기본값으로는 Kafka·Flink·Neo4j·Grafana만 약 6.8 GB라 이 넷의 메모리를 명시적으로 낮춰 고정한다.
- FUXA 알람: 확인(ack)은 있고 보류(shelving)는 없다(master 소스 기준, 1.3.4와 같은지는 미확인).
- OpenPLC v4: 프로그램 업로드에 데스크톱 편집기가 필요하다. 미리 만든 프로그램을 넣는 방법을 먼저 시험한다. OpenPLC v3는 수명 종료다.
- 지원 기간 문서가 없는 제품: InfluxDB 2.x, Mosquitto, FUXA, OpenPLC, Bento(릴리스 활동으로 판단, [미확인]).

## 3. 기준
### 3-1. 관문 (하나라도 걸리면 쓰지 않음)
- 비용 0원(LLM API만 예외). 금지: BSL, SSPL, TSL, RCL, 체험판, 키로 여는 기능, 상용 전용 기능.
- 지원·유지: **제품 계열이 계속 개발·유지되고 있어야 한다.** 개발이 멈춘 제품(예: 저장소가 archived된 OpenPLC v3)과 라이선스가 유료·제한형으로 바뀐 판(예: EMQX 5.9+ BSL, ThingsBoard 4.4+ BUSL)은 쓰지 않는다. 판마다 있는 지원 종료일은 제품을 빼는 이유가 아니다 — 패키지를 다시 만들 때(학기마다) 같은 메이저 안 최신 부 버전으로 올리고, 지원이 끝나는 판은 다음 판으로 올린다.
- `latest` 태그 금지, 버전 고정. 도커로 돌아가야 한다.
### 3-2. 구조
- 현업 주류 구조를 뼈대로 쓴다. 같은 종류의 흐름은 길 하나로 모은다: 읽기 하나, 쓰기(명령) 하나, 알람 전달 하나.
- 방향이 여러 개인 것은 정상이다. 데이터는 올라가고, 명령은 내려가고, 알람은 화면과 분석 쪽으로 간다. 망 분리 때문에 알람이 OT로 내려가는 길도 현업 패턴이다(v3).
- 층을 빼는 것은 현업 구조에 그 층이 없을 때만 한다.
### 3-3. 제품
- 칸마다 현업 주류 1위를 우선한다. 관문에 걸리면 ① 지원 중인 마지막 무료판 또는 ② 가장 가까운 무료 제품을 고르고 이유를 적는다.
### 3-4. 기능 보존
- V1이 하던 일을 잃지 않는다. 사람이 쓰는 기능도 포함한다: MQTT 실시간 계측(`edgex/telemetry` — 수업·시연 자료가 씀), `scripts/verify.py`, 수업 자료.
- 빼거나 바꾸는 부품마다 "그 기능을 누가 대신하나"를 표로 쓰고 실측으로 확인한다. 대체가 없으면 "잃은 것"으로 보고서에 적는다.
### 3-5. 검증 묶음 (조립 뒤 한 번, §5 V1 기준값과 비교)
- 할 것:
  - 흐름: 12태그 저장, 화면값과 이력값 일치
  - 탐지 판정 70건(회귀 S02~S08 리플레이)
  - 고장→알람: 배속 600에서 모든 고장 10초 안
  - 제어·안전: S14~S22
  - 재시작 복구: 브로커·Kafka·수집기·탐지기 재시작 뒤 3회 모두 스스로 복구, 유실·중복
  - 알람→화면 지연 p95
  - 메모리·CPU·이미지·디스크
  - 내부 오류 로그
- 판정: 정확도·유실·중복은 V1보다 조금도 나빠지면 안 된다. 지연 p95는 +5% 이내면 같다. 성능·복구 시간은 3회 중앙값.
- 하지 않을 것: 과부하, 장시간(개인 실습 목적에 과함).
### 3-6. 시간
- 가상설비는 **배속 600이 기본값**이다(`simulator/plant.yaml physics_time_scale: 600`). 그 반대 개념을 가리키는 말은 쓰지 않는다.
- 목표: 이상 주입→알람 10초 안, 한 사이클(이상→감지→AI 조치 제안) 1분 안.
- 걸리는 시간은 짐작하지 말고 첫 실행을 재서 말한다.

## 4. 작업 방식
1. **질문에는 먼저 쉬운 자연어로 답한다.** "~하면 안 되나?"는 지시가 아니라 질문이다. 권고로 답한다. 단계마다 번호 붙은 짧은 중간 보고를 쓰고, 보고 뒤에는 멈추지 말고 계속한다.
2. **사실만 쓴다.** 재지 않은 수치, "~같다"는 쓰지 않는다. 확인하지 못한 것은 "미확인"과 확인 방법으로 적는다. 틀린 말을 했으면 바로 정정한다.
3. **조사는 의뢰서 하나로 한 번에, 넓게 한다.** 우리 구조를 정답으로 전제하지 않는다("우리는 이렇다, 현업은 어떻냐"). 구조와 스택은 함께 묻는다. 질문 목록은 띄우기 전에 사용자에게 보여 준다. 서브에이전트에게는 도커 실행·격리 컨테이너 exec 금지, 결과 파일 하나만 쓰기, 파일을 먼저 만들고 절마다 덧붙이기를 명시한다.
4. **조사가 살아 있는지는 결과 파일 수정 시각으로 확인한다.** 사용자가 다른 명령을 끊을 때 백그라운드 조사가 함께 멈출 수 있다. 멈췄으면 묻지 말고 같은 의뢰서로 다시 띄운다.
5. **조립과 측정은 한 번에 한다.** 후보마다 층별 단독 시험(벤치)은 하지 않는다. 새 측정 도구는 한 번 끝까지 돌려 결과 파일을 확인한 뒤 쓴다.
6. **근본 수정만 한다.** 땜빵은 하지 않고, 고칠 때마다 남은 땜빵이 있는지 같이 본다.
7. **말은 쉽게 한다.** 무엇을 왜 했는지를 말한다. 부품은 실제 이름으로 부른다("중계기" 같은 만든 말을 쓰지 않는다).
8. PC 자원(이미지 받기·빌드, 컨테이너 기동·삭제, Docker 재시작)은 허락 없이 쓴다. 무거운 측정은 Docker 메모리 7.6 GB 안에서 한 번에 하나씩.
9. 방향(구조 확정 등)은 사용자에게 한 장으로 보여 주고 간다. 그 밖의 실행 판단은 스스로 하고 `reports/decision-log.md`에 추가한다(추가만).
10. 맥락이 차기 전에 이 파일을 최신으로 고친다. 이 파일에는 경위를 쓰지 않는다(경위는 decision-log). 조각을 덧대지 말고 해당 절을 통째로 바꾼다.

**하지 않는 것(이유):**
- 경량화를 이유로 층을 빼거나 비주류 제품을 고르기 — 현업 기준·기능 보존과 어긋난다.
- 엔진급 기능(스트림 처리·메시징·저장·탐지)을 직접 짠 코드로 대체하기, AI 규칙 엔진 — 현업 제품을 가르친다.
- 오토인코더를 배속 설비 데이터로 단순 재학습 — 드리프트·베어링 탐지율이 100 %에서 0 %로 떨어진다(S6). V1 모델을 유지한다.
- Vector 사용 — Kafka 재조정 뒤 소비가 멈춘다(#22006, 수정판 없음, S19).

## 5. 재사용할 증거 — 다시 재지 않는다
**V1 기준값**(배속 600 설비; 요약 `experiments/EXP-001/summary_V1_r2_.json` ← `python harness/tools/summarize_baseline.py EXP-001 V1 r2_`; 고장→알람 `experiments/EXP-000/raw/onset_v2sim_600*.json`; 탐지 `experiments/EXP-L4`; 기록 데이터 `experiments/REC-V1/`)
| 항목 | V1 값 |
|---|---|
| 자원 | 메모리 합계 5,918 MiB · CPU 51.2 % · SCADA 컨테이너 29 |
| 알람→화면 p95 | Kafka 1.67 s · FUXA 태그 1.84 s · 최근알람 1.98 s · AI 사건 2.06 s |
| 화면값 = 이력값 | 99.17 % |
| 브로커 10 s 정지 | 3회 중 2회 수집이 스스로 복구하지 못함 |
| 수집기 단절 10 s | 복구 중앙 7.3 s · 유실 중앙 120 태그·초 |
| Kafka 재시작 | 복구 중앙 11.6 s · 유실 0 · Kafka 중복 중앙 150 |
| 탐지기 재시작 | 잡 소멸 · 알람 11~12 유실(HA 꺼짐) |
| 저장 DB 30 s 정지 | 복구 3.2 s · 유실 0 |
| 고장→알람 최대 | 스파이크 1.9 · 히터 5.9 · 베어링 8.1 · 결측 5.8 · 드리프트 2.8 s, 잡음(Z-Score)은 확률적 약 10.8 s |
| 탐지 정확도 | 판정 70/70 · 기준 알람 263건 |
| 보안 | 인증 없이 열린 접점 11 중 10 |

**제품 사실(1차 출처는 `docs/research/`)**
- 라이선스·지원: EMQX 5.9+ BSL, 5.8은 2026-02-28 지원 종료. EdgeX 4.0.2가 현재 최신 판(다음 판 Queensland 2027 봄 예정). V1의 Kafka 3.9·InfluxDB 2.7 등은 최신 부 버전으로 올린다. InfluxDB `latest`는 3 Core. TimescaleDB 압축·연속 집계는 TSL. Confluent MQTT 커넥터 독점. Redpanda BSL.
- Flink 2.2.1 + ZooKeeper HA: 판정 70/70으로 V1 알람과 같고, JobManager 재시작 뒤 잡 4개가 체크포인트에서 스스로 복귀한다(`flink/Dockerfile.v2`, `flink/onnx-job-2x`, `flink/conf/*.v2.yaml`, 이미지 `rot-flink-onnx:v2`). ONNX 잡은 제출 설정에 체크포인트를 따로 켠다(S17).
- Bento 1.21.2: V1 Telegraf 3개와 같은 결과(Kafka 재조정 뒤 재개는 미검증).
- Telegraf 1.40.1 `kafka_consumer`를 Kafka 4.3.1과 쓰려면 `kafka_version = "3.0.0"`이 필요하다.
- 수집: EdgeX 1356/1356·p95 9.75 ms·컨테이너 10. 저장 24시간 디스크: InfluxDB 19 MB, TimescaleDB·QuestDB 680~1100 MB. 브로커 재시작 중복: Mosquitto 1건(2회), RMQTT 0건.
- 조립할 때 지킬 것(`reports/STABILITY.md` S1~S22): InfluxDB 설정 볼륨에 이름을 붙인다. Kafka에 `KAFKA_LOG_DIRS`를 지정한다. 설비 전용망에는 별칭을 준다. verify.py는 실패를 실패로 센다.
- 측정 함정: EMQX 기본 ACL은 `#` 구독을 거부한다. ONNX 점수는 입력이 멈춰도 나오므로 흐름 확인에 쓰지 않는다. 흐름은 Kafka 원시 토픽 오프셋 증가로 본다(10초 간격 약 144 증가가 정상). Windows 줄끝 때문에 셸 루프에는 `tr -d '\r'`. "거부" 표시가 떠도 명령이 실행됐을 수 있으니 결과를 확인한다.

**안정화 V1 덧씌우기 `docker-compose.stable.yml`:** 원본 V1 compose 위에 같은 제품 수정 다섯 가지를 얹는다(Flink 2.2.1 + ZooKeeper HA, ONNX 체크포인트, `KAFKA_LOG_DIRS`, InfluxDB 설정 이름 볼륨, FUXA 1.3.4 고정). 원본 파일은 그대로다. 재설계 뒤 같은 제품을 쓰면 이 수정을 그대로 가져간다.
- 기동: `docker compose --env-file .env --env-file .env.rotation -f docker-compose.yml -f docker-compose.edgex.yml -f docker-compose.timescale.yml -f docker-compose.stable.yml --profile edgex up -d --no-build`(`--no-build`는 원본 이름 `iiot/*` 이미지 빌드를 막는다. 원본 V1 이미지는 다시 받아야 한다).
- 확인 결과(2026-09-29): 흐름 +144건/10 s, Kafka 데이터가 볼륨에 저장됨, JobManager 재시작 8 s 뒤 잡 4개가 체크포인트에서 복귀. verify.py는 결측 주입 관련 3개 실패(원시 TT-101 결측 구간이 보이지 않음, 보간 0건, 보간값 quality 식별) — **미결**, 원인 미확인, 재설계 때 처리.

## 6. 지금 상태
- **컨테이너:** SCADA 컨테이너 없음. AI 컨테이너 6개(`rot-ai-*`) 정지, 볼륨 보존.
- **볼륨:** `rot-ai_*` 12개, 학습 모델 `rot-iiot_model-store`·`-v2`.
- **이미지:** 직접 빌드한 것(rot-flink-onnx:v2, rot-plant-simulator:v2-ts, e2e-client:1.0, l4bench-tools:1.0), iiot/model-trainer:1.0, AI(rot-ai-*, neo4j, postgres:17, ollama), 베이스 후보(apache/kafka:4.3.1, edgexfoundry/*:4.0.0, eclipse-mosquitto:2.1.2-alpine, frangoteam/fuxa:1.3.4, grafana/grafana:12.4.12, influxdb:2.9.1-alpine, zookeeper:3.9.5, postgres:16.3-alpine3.20, python:3.12-slim).
- **코드:** V1 원본(`docker-compose.yml`, `docker-compose.edgex.yml`, edgex/·emqx/·telegraf/·kafka/·flink/·fuxa/·grafana/·prometheus/·ml/), 배속 600 가상설비(`simulator/`, `docker-compose.timescale.yml`), Flink 2.2.1 HA 빌드, 측정 도구(`harness/`), AI 층(`ai-layer/compose.v2.yml`, `ontology/v2`, `knowledge-docs`).
- **git:** 브랜치 `exp/stack-rotation-202609`, 기준 태그 `v1-original`, push 안 함. 옛 문서·V2 구성은 커밋 `bdced23`에 있다.

## 7. 넘으면 안 되는 선
- 원본 `D:\work\study\lecture-iiot-scada`는 수정하지 않는다. 원본 이름(`iiot*`·`ar100*`)의 컨테이너·볼륨·이미지를 만들거나 덮어쓰지 않는다(격리 이름 `rot-*`).
- git push 금지. `latest` 태그 금지. §3-1 금지 라이선스.
- `ai-layer/.env.local`의 키는 출력하거나 커밋하지 않는다. LLM 호출은 필요한 만큼만(크레딧).

## 8. 명령
- 격리 스택 이름: `.env.rotation`(rot-iiot, rot-ai).
- V1 격리 기동: `docker compose --env-file .env --env-file .env.rotation -f docker-compose.yml -f docker-compose.edgex.yml -f docker-compose.timescale.yml up -d --no-build`
- AI 기동: `COMPOSE_PATH_SEPARATOR=: docker compose -p rot-ai --env-file ai-layer/.env.local --env-file .env.rotation -f ai-layer/compose.yml -f ai-layer/compose.scada.yml --profile knowledge up -d --no-build`(V2 AI는 `-f ai-layer/compose.v2.yml` 추가)
- 측정 도구: `harness/e2e/baseline.sh`(전체), `regression.sh`(회귀), `fault_onset.py`(고장→알람), `completeness.py`, `e1.py`. 요약: `harness/tools/summarize_baseline.py`, `e3_summary.py`, `internal_errors.sh`, `scorecard.py`. 정의: `harness/situations/`(ROBUSTNESS·STRUCTURE·L4·paths.yaml), `scenarios/catalog.yaml`. 새 구조는 `harness/e2e/struct_<이름>.sh`에 컨테이너 이름표를 둔다. 사용법은 각 파일 머리말.
- 확인 스크립트: `VERIFY_CN_PREFIX=rot- VERIFY_NETWORK=rot-iiot VERIFY_ENV_FILE=.env.rotation python scripts/verify.py`
- 환경: 호스트 RAM 15.7 GB, Docker VM 7.6 GB(넘으면 엔진 500 오류). 긴 작업은 Git Bash(`D:\dev\Git\bin\bash.exe`). 컨테이너 경로 인자 앞에 `MSYS_NO_PATHCONV=1`. Python은 `PYTHONUTF8=1`.

## 9. 자산 지도
| 위치 | 역할 |
|---|---|
| `HANDOFF.md` | 유일한 정본 |
| `docs/research/DEEP_RESEARCH_BRIEF_2026-09-29.md` | 조사 의뢰서(목표, 우리 구조 요약, 부록 A v3, §6 세부, §7 스택, §8 무료 대체품 비교) |
| `docs/research/deep-2026-09-29/12`~`15` | 현업 조사 결과(구조·세부·스택·무료 대체품 비교, 모두 완료) |
| `docs/research/deep-2026-09-29/01`~`11`, `compass_artifact_*` 4개, `AGENT_BRIEF_FINAL.md`(회귀 S01~S25·G0~G10 정의), `ARCHITECTURE_SIMPLIFICATION.md`(V1 중복·우회 분석) | 제품별 사실 자료. `11`은 미완 |
| `docker-compose.stable.yml` | 안정화 V1 덧씌우기 |
| `시스템구성도_*.pdf`·`.md`, `프로토타입_아키텍처_보고용.*` | V1 구조도(사용자 자료) |
| `reports/STABILITY.md` | 결함과 교훈 S1~S22 |
| `reports/decision-log.md` | 실행·판정·경위 기록(추가만) |
| `experiments/EXP-000`·`EXP-001`·`REC-V1`·`EXP-L4`·`EXP-S09`·`EXP-AI` | 증거 원본 |
| `harness/` | 측정 도구(솔루션 부품 아님) |
| 원본 `D:\work\study\lecture-iiot-scada` | 읽기만 |
