# 딥리서치 의뢰서 — 2026년 제조 현업의 IIoT·SCADA 구조는 어떻게 되어 있나

작성 2026-09-29. 조사자는 이 문서와 첨부 자료만 보고 조사한다.

## 0. 질문 한 줄

**"우리는 이렇게 짜 놨다(첨부 구조도 2종). 2026년 제조 현업은 실제로 어떤 구조로 되어 있나?"**

- 첨부한 두 구조(참조 설계서 v3, 우리 구조도)는 **비교 대상일 뿐 정답이 아니다.** 우리 구조에 기대지 말고 현업 구조를 독립적으로 먼저 그린다.
- 이번 조사는 **구조**만 본다. 층 구성, 데이터·명령·알람이 가는 길, 망 구분, 설비가 늘 때의 모양을 다룬다.
- 칸별 제품 순위와 버전 선택은 다음 조사에서 한다. 여기서는 층마다 "현업에서 흔히 쓰는 제품 종류"를 예시로만 적는다.

## 1. 목표

- **대상:** 국립 경남대 제조 AI 과정 학생이 배우고 실습할 IIoT·SCADA 시스템.
- **배포:** 학생마다 같은 패키지를 받아 자기 PC 한 대에서 Docker Compose로 띄운다(Windows, Docker 메모리 약 7.6 GB). 비용은 0원이다.
- **기준:** 장난감이 아니라 **2026년 제조 현업과 같은 구조**여야 한다. 학생이 배운 구조가 현장에서 그대로 통해야 한다.
- **확장 계획:**
  1. 먼저 베이스를 만든다. 설비 → 수집 → 전달 → 탐지 → 저장 → 화면 → 감시 → 알람이 도는 틀이다.
  2. 그다음 설비 종류와 대수를 크게 늘린다. 통신도 섞인다(지금은 Modbus만 쓰지만 OPC UA 등이 추가될 수 있다).
  3. 늘린 설비에 맞춰 고장 시나리오와 온톨로지(설비·고장·원인·조치 지식)를 풍부하고 자세하게 만든다.
  → 베이스 구조는 **설비가 늘어도 다시 짜지 않아도 되는 구조**여야 한다.
- **AI 층**(원인 분석 에이전트, 승인 프로세스)도 구조 그림에는 포함한다. 현업에서 AI·분석이 SCADA와 어떻게 연결되는지도 본다.

## 2. 첨부 자료

| 자료 | 위치 | 내용 |
|---|---|---|
| A. 참조 설계서 v3 | 이 문서 부록 A에 옮겨 적음(원본 PDF는 채팅으로만 받음) | 다른 팀이 설계하고 실제로 구축·실행한 구조. L1~L9 기능 층 + OT/DMZ/IT 배치 영역 |
| B. 우리 구조도(보강본) | `D:\work\study\scada-rotation\시스템구성도_풀스택_보강본.pdf` + 설명 대본 `시스템구성도_풀스택_설명대본.md` | 우리 원본(V1) 전체 구조 L1~L9. "AR-100 SCADA · Pilot" |
| C. 우리 실제 통신 구조(확인본) | `D:\work\study\scada-rotation\시스템구성도_실제통신구조_확인본.pdf` + 근거 `시스템구성도_실제통신구조_확인근거.md` | 코드와 실행으로 확인한 실제 통신 경로 |
| D. 보고용 그림(참고) | `프로토타입_아키텍처_보고용.pdf`, `IoT SCADA 파이프라인 아키텍처.pdf` | 같은 V1의 다른 판 그림 |

PDF는 Read 도구의 pages 인자로 읽는다. B·C는 반드시 전부 읽는다.

## 3. 우리 구조 요약 (B·C의 핵심, 조사자가 PDF와 대조할 것)

**흐름(V1):** 가상 설비(Python, Modbus TCP 서버 1개, 설비 7대, 센서 12개, 시간 배속 600) → EdgeX 4.0(Modbus로 읽음) → EMQX(MQTT) → Telegraf → Kafka → Flink(규칙 SQL 3개: 임계치·Z-Score·CEP, ONNX 오토인코더 1개) → Kafka 알람 → Telegraf → EMQX → FUXA 화면. 저장은 Kafka → Telegraf → InfluxDB → Grafana로 간다. 감시는 Prometheus, Alertmanager, cAdvisor, kafka-exporter가 맡는다. AI(Pilot)는 알람을 받아 원인을 분석하고, 사람이 승인하면 조치를 실행한다(Neo4j, LangGraph, PostgreSQL).

**실제 통신에서 확인한 특징(C 근거):**
- FUXA는 Modbus로 설비를 **직접 읽고 쓴다.** EdgeX도 같은 설비를 따로 읽는다(읽기 길 2개).
- AI 조치 코드는 승인된 정지 명령을 Modbus로 설비에 **직접 쓴다.** 쓰기 길은 FUXA 직접 쓰기, EdgeX core-command, AI 조치 3개다.
- AI의 결과 확인과 대시보드 현재값 조회는 HTTP 상태 API를 쓴다.
- MQTT 브로커가 2개다(EdgeX 전용 Mosquitto, EMQX).
- 저장소가 흩어져 있다(InfluxDB, 알람 PostgreSQL, Neo4j, EdgeX 전용 PostgreSQL).
- 망 구분이 없다. 모든 컨테이너가 도커 망 하나에 있다.

**우리가 아는 참조 v3와의 차이(부록 A와 대조):** v3는 FUXA가 MQTT 구독만 하고, 명령은 MQTT `cmd/manual` → EdgeX core-command → PLC 한 길로 보낸다. PLC 층(운전 모드, 명령 만료, 중복 방지, 인터록)이 따로 있다. OT/DMZ/IT로 망을 나누고, 경계를 넘는 것은 DMZ 컨테이너 3개뿐이다. 저장소는 TimescaleDB 하나다.

## 4. 조사할 것

1. **2026 현업 주류 구조를 독립적으로 그린다.**
   - 층 구성: 현장·PLC → 장치 연결·프로토콜 변환 → 메시지 허브(UNS) → 이벤트 스트리밍 → 스트림 처리·탐지 → 저장(히스토리언) → 화면(SCADA·HMI·대시보드) → 감시 → 분석·AI → MES·ERP 등
   - 각 층의 역할과 흔히 쓰는 제품 종류(예시만)
   - 데이터가 올라가는 길, 명령이 내려가는 길, 알람이 가는 길
   - 망 구분: 퍼듀 모델, IEC 62443 영역과 통로(zone·conduit), OT·DMZ·IT
   - 참고 틀: UNS(Unified Namespace), ISA-95 계층 토픽, MQTT와 Kafka의 역할 분담, OPC UA와 Sparkplug B와 Modbus의 위치, 데이터 맥락화·모델링 층, 엣지와 사이트 히스토리언, 스키마 관리, 알람 관리(ISA-18.2 / IEC 62682), 명령 경로의 안전 장치(운전 모드, 명령 만료, 중복 방지, 인터록, 승인)
2. **설비가 많아질 때 현업은 구조를 어떻게 확장하나?** 설비와 라인이 늘고 통신이 섞일 때 무엇으로 흡수하는지 본다. 장치 계층, 토픽 이름 체계, 설비 정보 모델(OPC UA 정보 모델, ISA-95 설비 계층, 자산 모델)을 다룬다.
3. **AI·분석이 SCADA에 붙는 현업 방식.** 알람 → 원인 분석 → 사람 승인 → 명령 실행의 흐름과 안전 경계를 본다. 온톨로지나 지식 그래프를 쓰는 사례가 있는지도 본다.
4. **비교표 세 개를 만든다.**
   - 현업 구조 vs 참조 v3(부록 A)
   - 현업 구조 vs 우리 구조(B·C)
   - 표 형식: 현업에 있고 대상에 없는 층 / 대상에 있고 현업에 없는 층 / 같은 층이지만 방식이 다른 곳 / 대상이 잘 맞춘 곳. 칸마다 근거를 붙인다.
5. **권고:** 우리 베이스가 현업과 같으려면 층과 길을 어떻게 짜야 하는지 적는다.
   - 교육용 한 대 PC라는 조건에서 **줄여도 되는 것**(예: 망 분리를 도커 망으로 흉내)과 **줄이면 현업과 달라지는 것**을 구분한다.
   - 그림처럼 읽히게 층 목록과 길 목록으로 제시한다.

## 5. 근거 규칙과 결과 형식

- 모든 사실에 출처 URL과 확인일(2026-09-29)을 붙인다. 근거 종류를 표시한다: 표준 문서 / 독립 조사·설문 / 공개 사례(실제 기업·공장) / 재단·오픈소스 문서 / 벤더 홍보.
  - 벤더가 자기 제품 구조를 권하는 글은 반드시 "벤더 홍보"로 표시한다. 벤더 한 곳의 말만으로 "현업 주류"라고 쓰지 않는다.
- 확인하지 못한 것은 `[미확인]`, 검색 요약에서만 본 것은 "(검색 발췌)"로 표시한다. 추정은 쓰지 않는다.
- 결과 파일 맨 앞: ① 현업 주류 구조 한 장(층 목록 + 길 목록) ② 우리 베이스 권장 구조 한 장.
- 그다음 §4의 1~5 순서로 적고, 마지막에 "확인 못 한 것"을 둔다.
- 쉬운 한국어로 짧은 문장을 쓴다. 제품명과 표준 이름은 원문 그대로 둔다.

---

## 부록 A. 참조 설계서 v3 옮겨 적기 (「유압 설비 IoT-SCADA 아키텍처 설계서 v3」, 2026-09-23, 12쪽)

**층(기능 레이어)과 배치 영역**
| 층 | 역할 | 구성요소 | 영역 |
|---|---|---|---|
| L1 | 현장 계측·구동 | 유압설비 HYD-01~03 / hyd-sim(센서 17채널, 구동기: 쿨러 팬·펌프 부하·밸브), PLC/soft-plc(센서 입력·인터록·운전 모드·명령 검증·가상 센서 계산), 고속 DAQ(PS·EPS 100 Hz, FS 10 Hz) | OT |
| L2 | 장치 연결·수집 | EdgeX Foundry 3.x(device-modbus: PLC 태그 1 Hz, device-daq: 파형 1초 배치, core-command: 명령→PLC 쓰기, app-service: 토픽·페이로드 변환), EMQX(OT 브로커, 토픽 ACL, cmd retained 금지) | OT |
| L3 | 이벤트 장부·분배 | Kafka Connect ingest(MQTT Source, OT→IT 단방향 복제), Kafka KRaft(IT의 단일 장부), 명령 게이트웨이(Kafka action.cmd·alerts를 검증해 OT로 내리는 유일한 하향 통로) | DMZ·IT·DMZ |
| L4 | 실시간 이상 탐지 | Flink(파형 → 1초 특징 → ONNX 오토인코더 점수 → CEP MATCH_RECOGNIZE → alerts RAISE/CLEAR) | IT |
| L5 | 이력 저장 | Kafka Connect sink(JDBC upsert), TimescaleDB(tag_1s·feat_1s·alerts·actions·audit, 1분 연속 집계·압축·보존), MinIO(선택, 원시 파형) | IT |
| L6 | 관제·감시 | FUXA(OT, P&ID·알람·수동 조작·모드 전환, IT 장애와 무관하게 동작), Grafana, Prometheus(+DMZ의 Agent가 OT 수집해 remote_write), Alertmanager → Mailpit | OT·IT |
| L7 | 원인·조치 지식 | Neo4j 5 + n10s + APOC, OWL·SHACL 온톨로지, RCA·가이드 Cypher 템플릿 | IT |
| L8 | 조치 가이드 생성 | LangGraph 에이전트, MCP 도구(mcp-kg·mcp-tsdb·mcp-prom, 읽기 전용), LiteLLM. 명령 권한 없음 | IT |
| L9 | 승인·실행 조율 | BPMN 엔진(Process GPT 또는 Flowable), 운전원 가이드 앱. 승인 → action.cmd → ACK 대기 → 15분 재관측 → 작업지시·종결 | IT |

**설계 원칙**
- OT에는 설비와 실시간 운전에 필요한 것만 둔다. IT가 멈춰도 FUXA 감시, 수동 조작, 인터록은 계속 돌아야 한다. DMZ는 OT와 IT를 잇는 유일한 통로다. 올라가는 것은 복제만 하고, 내려가는 것은 검증된 명령과 알람 두 종류뿐이다. IT는 설비에 직접 붙지 않는다. 도커 망은 ot-net과 it-net으로 나누고, 두 망에 동시에 붙는 컨테이너는 DMZ의 3개뿐이다.
- 층마다 핵심 기능은 하나다. Kafka가 IT의 단일 장부다. 설비 경보(Flink → 에이전트·운전원)와 플랫폼 경보(Prometheus → 인프라 담당)를 나눈다. 지식은 온톨로지에 둔다. 사람 승인 → 게이트웨이 검증 → PLC 모드·만료·중복·인터록 검사를 모두 통과해야 명령이 실행된다.

**MQTT 토픽(OT)**
- `plant/{a}/tag/{name}`(↑, 1 Hz `{t,v,q}`, FUXA 바인딩 단위)
- `plant/{a}/wave/{sensor}`(↑, 1초 배치, FUXA 구독 금지)
- `plant/{a}/status`(↑, 운전 모드, 명령 ACK)
- `plant/{a}/mode`(↓, FUXA만)
- `plant/{a}/cmd/manual`(↓, FUXA, `{cmdId, source, expiresAt, writes[]}`)
- `plant/{a}/cmd/auto`(↓, 게이트웨이, retained 금지)
- `plant/{a}/alert`(↓, 게이트웨이 → FUXA, 표시 전용)

**Kafka 토픽:** plant.tag(7일), plant.wave(7일), plant.status(30일), feat.1s(30일), alerts(1년), action.cmd(1년), audit(5년). 키는 asset이다.

**시간:** 이벤트 시간은 PLC와 DAQ가 찍는다. Flink 워터마크는 2 s, 허용 지연은 5 s다. 자산 안의 순서는 자산별 토픽 필터와 Kafka 키로 지킨다.

**운전 모드:** LOCAL(현장만), REMOTE_MANUAL(FUXA 수동만, 기본값), REMOTE_AUTO(HITL 자동 + 수동, 수동이 우선하고 수동 조작이 들어오면 MANUAL로 복귀).

**구간별 검증:** BPMN(승인, 파라미터 범위, expiresAt = 승인 + 120 s) → 게이트웨이(스키마, 화이트리스트, 만료, cmdId 중복, 모드, 초당 제한, 거부 사유는 audit) → EdgeX(토픽별 계정 ACL) → PLC(모드·출처, 만료, 최근 cmdId 32개 중복, 쓰기 범위, 하드 인터록). ACK는 status → ingest → Kafka plant.status → BPMN이 대조한다(30초).

**구현 순서(프로필):** M1 ot → M2 backbone → M3 detect → M4 monitor → M5 knowledge → M6 agent → M7 process. 시뮬레이터 시간 배율(예: ×20)을 BPMN 타이머와 CEP 시간창이 같이 읽는다.

**설계서가 적은 v2 대비 개정 16건의 요지:** 센서가 PLC를 거치게 함. FUXA 명령 경로와 운전 모드를 추가. 명령 만료와 중복 방지. OT/DMZ/IT 분리. tag와 wave 토픽 분리. 가상 센서 계산을 PLC로. 시간축과 순서 정의. JSON Schema 통일(Registry는 운영 때). 경보 선을 Kafka alerts에서 출발. FUXA 알람 경로 표시. ACK 경로. 시뮬레이터 루프. MCP 선. Alertmanager 수신처. Connect를 ingest와 sink로 분리하고 명령은 전용 게이트웨이로.
