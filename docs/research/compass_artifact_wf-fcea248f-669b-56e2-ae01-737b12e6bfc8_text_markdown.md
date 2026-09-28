# V1 IoT/SCADA/AI 프로토타입 레이어별 최신 기술 후보 조사 (2025~2026)

V1의 핵심 기술들(EdgeX, EMQX, Kafka, Flink, InfluxDB, FUXA, Grafana/Prometheus)은 대부분 2025~2026년에도 활발히 릴리스되는 "현역" 기술이다. 다만 이번 회전에서 실제로 비교해 볼 가치가 큰 변화는 세 가지다. 첫째, 라이선스와 보안 이벤트(EMQX 5.9 BSL 전환, FUXA 취약점, LiteLLM 공급망 공격)다. 둘째, 수집 계층을 한 도구로 통합하는 흐름(Benthos/Redpanda Connect, UMH)이다. 셋째, 태그 12개 규모에서 Kafka+Flink가 과한 구조인지에 대한 검증이다. "CEP는 요즘 안 쓴다"는 주장은 **절반만 맞다**. 독립 CEP 제품 시장은 레거시가 됐지만, CEP 기능은 Flink(MATCH_RECOGNIZE·CEP 라이브러리)에 흡수되어 2026년에도 유지보수되고 있다.\[1\]

## TL;DR

- **V1은 "낡은" 스택이 아니다.** 교체 1순위는 기술 유행이 아니라 리스크다. ① FUXA는 1.3.2 이상으로 즉시 올려야 한다(CISA ICSA-26-181-02, 2026-06-30). ② EMQX 5.9+는 BSL이므로 단일 노드만 무료 운영 가능하다. ③ InfluxData 공식 InfluxDB 3 Core 설정 문서에 따르면 기본값(Parquet 파일 432개, gen1 10분)에서 쿼리가 접근할 수 있는 범위는 "up to a 72 hours of data, but potentially less"이고, Flux는 지원하지 않는다. ④ LiteLLM은 2026-03-24 PyPI 악성 버전(1.82.7/1.82.8) 사고가 있었으므로 버전 고정이 필수다.
- **CEP 주장 검증: "독립 CEP 엔진은 쇠퇴, CEP 기능은 주류 스트림 엔진의 표준 기능".** Flink 2.2.1(2026-05)에도 MATCH_RECOGNIZE 버그 수정이 포함됐다. 반면 Esper의 마지막 메이저는 9.0.0(2024-04)이다. 따라서 "CEP를 빼자"보다 "Flink가 12태그 규모에 필요한가"를 묻는 편이 정확하다.
- **5영업일 회전 추천(한 번에 한 모듈):** ① L1~L2 게이트웨이(EdgeX 4.0 vs Neuron OSS vs benthos-umh) → ② L2 파이프(Telegraf 3종 vs Redpanda Connect 단일) → ③ L4 처리(Flink DataStream CEP vs Flink SQL MATCH_RECOGNIZE vs Python 서비스) → ④ L5 저장(InfluxDB 2 vs InfluxDB 3 Core vs TimescaleDB) → ⑤ L6(FUXA 업그레이드 필수, Ignition 8.3은 라이선스 확인 후 선택). Kafka 제거("Kafka-less") 구조는 마지막 날 클린시트 비교로만 한다.

## 표기 규칙

- **[1차]**: 이번 조사에서 공식 문서, 릴리스 노트, 공식 저장소, 정부기관(CISA) 자료로 직접 확인한 사실.
- **[2차]**: 제3자 블로그·언론·트래커로 확인한 사실. 벤더 계열 블로그는 별도 표시한다.
- **[미검증]**: 이번 세션에서 1차 확인을 하지 못해 일반 지식에 기반한 항목. PoC 착수 전 릴리스 페이지로 재확인해야 한다.
- 벤더 성능 수치는 모두 "벤더 주장"이며, 이 보고서는 측정값을 제시하지 않는다.

---

## 1. 요약: 레이어별 "V1이 여전히 주류인가 / 최신 후보는 무엇인가"

| 레이어 | V1 컴포넌트 | 현재도 주류인가 | 최신 트렌드 후보(우선순위순) | 한 줄 판정 |
|---|---|---|---|---|
| L1 설비·센서 | Python 물리 시뮬레이터 + Modbus TCP + HTTP /state | 교육용으로 적절(Modbus TCP는 여전히 표준) | OPC UA 서버 추가(asyncua/open62541) [미검증] | 유지. OPC UA 병행 노출은 V3 과제 |
| L1~L2 게이트웨이 | EdgeX Foundry | **정체~유지**: 4.0 "Odesa" LTS(2025-03) [1차]\[2\]\[3\] | Neuron OSS(LGPLv3), benthos-umh, Redpanda Connect, Node-RED [미검증], 직접 pymodbus | 12태그에는 EdgeX 마이크로서비스 구조가 과함. 교체 비교 1순위 |
| L2 브로커 | EMQX | 주류. 단 **5.9부터 BSL 1.1** [1차]\[4\] | Mosquitto, NanoMQ, HiveMQ CE [미검증], EMQX 5.8.x(Apache 고정) | 단일 노드는 무료 운영 가능 → 프로토타입엔 문제없음\[5\] |
| L2 수집 파이프 | Telegraf ×3 설정 | 주류(GitHub influxdata/telegraf 릴리스에 1.39.3 빌드. InfluxData 릴리스 노트는 v1.38.0의 Heartbeat 출력 panic 때문에 1.38.2 이상 업그레이드를 권고) [1차] | Redpanda Connect(Benthos), Grafana Alloy·OTel Collector [미검증] | Redpanda Connect 단일 바이너리로 3설정 통합 비교 가치 큼 |
| L3 이벤트 백본 | Kafka(raw/alerts/clean/score) | **주류**: 4.0 KRaft 전용, 4.2 Share Groups GA [1차]\[6\]\[7\] | Redpanda, NATS JetStream, "Kafka-less" MQTT 단일 [미검증] | 유지가 기본. 제거 여부는 클린시트 비교로 |
| L4 스트림·이상탐지 | Flink(규칙/CEP) + Flink ONNX | **주류**: Flink 2.x 활발(2.2.1, 2026-05) [1차]\[8\] | Flink SQL MATCH_RECOGNIZE, eKuiper(엣지 SQL), RisingWave, Python(Quix Streams·River) [일부 미검증] | CEP 자체는 현역. 규모 대비 Flink 무게가 쟁점 |
| L5 시계열 | InfluxDB(2.x로 추정) | 주류이나 **세대 전환기**(InfluxDB 3) [1차] | InfluxDB 3 Core, TimescaleDB(Tiger Data), QuestDB 10, GreptimeDB 1.x, TDengine, IoTDB | "PostgreSQL 단일화(Timescale)"가 가장 실용적 대안 |
| L5 업무 DB | PostgreSQL | **주류** | 유지 | 유지 |
| L6 HMI/SCADA | FUXA | 오픈소스 웹 SCADA 중 활발(GitHub 저장소 헤더 기준 "Star 5k · Fork 1.4k") [1차]. **보안 이슈 다수** | Ignition 8.3(상용), Node-RED Dashboard 2.0, Rapid SCADA, SCADA-LTS [미검증] | 1.3.2+ 업그레이드 필수. 교체보다 격리·업그레이드 |
| L6 관측 | Prometheus/Alertmanager/Grafana | **주류** [미검증: 버전] | VictoriaMetrics(v1.152.0) [1차],\[9\] Grafana Alloy [미검증] | 유지. VM은 선택적 비교 |
| L7 지식 | Neo4j | 주류 [미검증: 버전] | PostgreSQL+AGE/pgvector, Memgraph, FalkorDB; **Kuzu는 아카이브** [1차]\[10\] | 유지. PG 통합 옵션만 가볍게 |
| L8 에이전트 | LiteLLM + 커스텀 워커 | 주류이나 **2026-03 공급망 사고** [1차]\[11\] | 직접 SDK, Portkey, MCP 기반 도구 [미검증] | 버전 고정 + Docker 이미지 사용. 교체는 선택 |
| L9 워크플로 | LangGraph | 주류(에이전트 HITL) [미검증] | Temporal, DBOS, Restate [미검증]; Camunda 8은 **8.6+ 운영 시 유료** [1차]\[12\]\[13\] | 유지. 승인·실행 부분만 내구성 워크플로 비교 가치 |

---

## 2. "CEP는 요즘 쓰지 않는 기술" 주장 검증

### 결론
**독립 제품으로서의 CEP는 쇠퇴했고, 기능으로서의 CEP는 주류 스트림 엔진 안에서 유지·사용 중이다.** V1의 "교반기 전류 상승 후 N초 내 진동 상승" 같은 시간·순서 패턴은 정확히 CEP가 해결하는 문제 유형이다. 그래서 "CEP를 버린다"는 결정은 "그 패턴 탐지를 다른 방식(윈도 조인·상태 머신 코드)으로 재구현한다"는 뜻이 된다.

### 근거

| 관점 | 증거 | 해석 |
|---|---|---|
| 레거시 CEP 제품 | Kai Waehner(2026-04-14)는 TIBCO BusinessEvents, Software AG Apama, IBM/Oracle CEP를 "effectively legacy"로 평가 [2차, 저자는 Confluent/Kafka 진영 에반젤리스트로 이해관계 있음]\[1\] | 대표님 말씀의 근거가 되는 부분은 사실 |
| Esper | 마지막 Java 메이저 9.0.0(2024-04), NEsper 8.9.1(2025-03-19), GPL v2 [1차: espertech 배포 인덱스·변경 이력]\[14\]\[15\]\[16\] | 살아 있으나 릴리스 주기가 느림 → "정체" |
| Siddhi | 이번 조사에서 최근 릴리스 근거를 찾지 못함 [미검증] | 신규 채택 비추천 |
| Flink CEP/MATCH_RECOGNIZE | Flink 안정판 문서에 MATCH_RECOGNIZE가 현행 기능으로 있고, `flink-cep` 2.2.0 아티팩트 사용을 안내 [1차].\[17\] Flink 2.2.1(2026-05-15) 릴리스에 FLINK-39293(MATCH_RECOGNIZE 뷰 파싱 버그) 수정 포함 [1차]\[8\] | **유지보수 중인 현역 기능** |
| 매니지드 서비스 | Confluent Cloud·Amazon Managed Flink가 MATCH_RECOGNIZE를 지원 [2차]\[1\] | 상용 클라우드에서도 1급 기능 |
| Flink SQL의 한계 | FLINK-33428(미해결): Flink SQL MATCH_RECOGNIZE는 사실상 `next`(엄격 연속) 의미만 지원. `followedBy`·`notFollowedBy`는 DataStream CEP API에만 있음 [1차].\[18\] 문서는 MATCH_RECOGNIZE가 state retention을 쓰지 않으므로 `WITHIN` 사용을 권고 [1차]\[17\] | "전류↑ 후 (다른 이벤트 끼어도) N초 내 진동↑"는 SQL에서 `PATTERN (A X*? B) WITHIN INTERVAL 'N' SECOND` 형태로 우회해야 함. 비교 테스트 항목이 됨 |
| 부재 이벤트 | Waehner는 "이벤트가 오지 않음" 탐지에는 CEP보다 Flink SQL LEFT JOIN이 메모리 측면에서 적절하다고 권고 [2차]\[1\] | 센서 하트비트 끊김 탐지는 CEP 없이 구현 가능 |

### 대표님 보고용 문장(권장)
"CEP 전용 엔진(Esper·TIBCO류)은 요즘 신규로 쓰지 않습니다. 하지만 시간·순서 패턴 탐지는 Flink 같은 주류 엔진의 SQL 표준 기능(MATCH_RECOGNIZE, ISO SQL:2016 행 패턴 인식)으로 흡수되어 2026년에도 유지보수 중입니다.\[17\]\[19\] V2에서는 'CEP 라이브러리 코드 → SQL 패턴 or 경량 Python 상태 머신'으로 바꿨을 때 같은 시나리오 테스트를 통과하는지로 결정하겠습니다."

---

## 3. L1~L6 레이어별 상세 후보

### 3.1 L1~L2 OT 연결·게이트웨이·수집

| 후보 | 트렌드 판정 | 최신 버전·날짜 | 라이선스 | 채택 근거(독립/벤더 구분) | V1 대체 범위 | 잃는 기능 | 12태그 Compose 적합성 | 최소 PoC(수 시간) |
|---|---|---|---|---|---|---|---|---|
| **EdgeX Foundry**(기준선) | 정체~유지 | 4.0 "Odesa" LTS, 2025-03 [1차].\[2\] 위키 릴리스 표에 "Palau (4.0.2) – June 2026 – Standard Release" 기재 [1차, 위키]\[20\] | Apache 2.0 | TSC에 Schneider·Eaton·Danfoss·Intel(LF Edge 발표) [1차, 재단 발표]. 4.0에서 BSL 전환한 Redis 등 제3자 구성요소를 PostgreSQL·OpenBao로 교체, MQTT를 기본 내부 버스로 채택 [1차]\[2\]\[3\]\[21\]\[22\] | — | — | 서비스 수가 많아(core-data, metadata, command, device-modbus, app-service, Postgres, 보안) 12태그 대비 무거움 | 현 상태 유지 |
| **EMQX Neuron(구 NeuronEX) / Neuron OSS** | 상승(EMQ 생태계) | Neuron OSS 2.x. OSS 대시보드는 2.6.3에서 개발 중단 [1차, GitHub README]\[23\] | 코어·modbus-tcp·mqtt·eKuiper 플러그인은 **LGPLv3**. 기타 드라이버(OPC UA·S7 등)는 상용. 상용판은 **30태그 무료 체험 라이선스** 내장 [1차]\[24\]\[25\] | 벤더 문서 위주. 독립 채택 근거는 약함 | EdgeX 전체(Modbus 폴링 → MQTT 발행) | EdgeX의 장치 메타데이터·명령 API·보안 서비스. OSS 대시보드는 유지보수 중단 | **높음**(단일 컨테이너, V1 12태그는 30태그 이하) | `emqx/neuron` 컨테이너 1개 + UI에서 Modbus TCP 드라이버·MQTT 북향 설정. 코드 0줄, 설정만 |
| **benthos-umh**(UMH) | 상승 | v0.16.0(2026-09-23, Beckhoff ADS 입력 추가), v0.15.2(2026-09-04) [1차, GitHub PR]\[26\]\[27\] | Apache-2.0 [1차]\[28\]\[29\] | GitHub 활동 활발(2026-09 커밋). UMH 조직 저장소 약 391 stars [1차].\[28\] UMH 문서는 "Node-RED보다 대량 데이터에서 안정적"이라 주장 [벤더 주장]\[30\] | EdgeX + Telegraf(MQTT/Kafka 출력) | EdgeX 명령 서비스. UMH Core로 쓰면 관리 콘솔(management.umh.app) 토큰 의존 [1차]\[31\] | **높음**(standalone Benthos 모드 가능) | `ghcr.io/united-manufacturing-hub/benthos-umh` + YAML(modbus input → mqtt/kafka output) 30~60줄 |
| **Redpanda Connect(Benthos)** | 상승 | Redpanda 공식 문서(2026-09-04 수정본) 메타데이터 기준 최신 4.109.0. GitHub redpanda-data/connect 릴리스 페이지에는 4.103.1 빌드(2026-07-31) [1차] | 코어 엔진은 MIT(redpanda-data/benthos). 커넥터 대다수는 Apache-2.0, 엔터프라이즈 커넥터(CDC 등)는 RCL + 라이선스 키 필요 [1차]\[32\]\[33\] | Redpanda가 2024-05 Benthos 인수 [1차].\[32\] 라이선스 변경 문서화 불충분하다는 커뮤니티 이슈(#2621) [1차]\[34\] | Telegraf 3종 설정 전부 + (Modbus 입력이 있으면) 게이트웨이 | Telegraf의 풍부한 입력 플러그인 생태계 | **높음**(단일 바이너리) | 아래 3.2 참고 |
| **eKuiper**(엣지 SQL 룰엔진) | 유지~상승 | 2.2.0(2025-07), 2.3.1(2025-11-21), 2.4.0-alpha [1차]\[35\]\[36\] | Apache 2.0 | LF Edge 프로젝트. EdgeX·Neuron과 통합 [1차]. 2026 SSRF 보안 수정 진행 중 [1차]\[37\]\[38\] | L4 일부(엣지 필터·윈도 집계) | Flink 수준의 event-time·정확히-한번 보장 [미검증] | 높음 | `lfedge/ekuiper` + MQTT 소스 스트림 + SQL 룰 1~2개 |
| Node-RED 4.x / FlowFuse | 주류(현장 통합) | [미검증] | Apache 2.0 [미검증] | 커뮤니티 매우 큼 [미검증] | 게이트웨이 + 간단 HMI | 대량 처리 안정성(UMH 주장) | 높음 | `nodered/node-red` + node-red-contrib-modbus |
| Apache PLC4X / StreamPipes / Eclipse Tahu | 틈새 | [미검증] | Apache/EPL [미검증] | Tahu는 Sparkplug 참조 구현(Eclipse가 "Java 편중, 기여 필요"라 언급, 2023) [1차]\[39\] | 드라이버 라이브러리 | — | 중간 | 이번 회전 제외 권장 |
| 직접 pymodbus | 주류(코드 방식) | [미검증] | BSD [미검증] | — | EdgeX 전체 | 재시도·버퍼링·설정 UI를 직접 구현 | **매우 높음** | Python 80~150줄(폴링 → paho-mqtt 발행) |
| Telegraf modbus/opcua 입력 | 주류 | [미검증] | MIT [미검증] | — | EdgeX + Telegraf#1 통합 | EdgeX 명령 경로 | 높음 | telegraf.conf에 `[[inputs.modbus]]` 추가 |

**UNS·Sparkplug B·ISA-95 트렌드 판정**
- Sparkplug 3.0은 ISO/IEC 국제표준으로 인증됐다(Eclipse, 2023-12) [1차]. 4.0은 "2024 말~2025 초 RC 목표"로 발표됐으나\[39\] 이번 조사에서 출시를 확인하지 못했다 [미검증].
- **독립 채택 신호는 엇갈린다.** HiveMQ(MQTT 브로커 벤더)는 과거 Sparkplug 기반 UNS를 홍보했다. 그러나 현재 웨비나 페이지에 "Sparkplug는 중앙 UNS 솔루션으로 이상적이지 않다"는 방향 전환 면책 문구를 게시했다 [1차, 벤더 자체 입장 변화].\[40\] Kai Waehner는 Sparkplug의 QoS 0 한정 등을 미션 크리티컬 용도의 한계로 지적했다 [2차].\[41\]
- **판정:** UNS(ISA-95 계층 토픽 `enterprise/site/area/line/cell/...` + MQTT)는 "상승·주류화" 패턴이다. Sparkplug B는 Ignition·Cirrus Link 생태계 중심의 "선택적 표준"이다. V1은 토픽을 `edgex/telemetry` 단일 토픽에서 ISA-95 계층 토픽(예: `edu/lab/line1/R-101/TT-101`)으로 바꾸는 것만으로 트렌드를 반영할 수 있다. Sparkplug 도입은 Ignition과 연동할 때만 권장한다.

### 3.2 L2 수집 파이프(Telegraf 3종 설정)

| 후보 | 판정 | 대체 범위 | 잃는 기능 | PoC | 측정 지표 |
|---|---|---|---|---|---|
| Telegraf(기준선) | 주류(GitHub 릴리스에 1.39.3 빌드. InfluxData 릴리스 노트상 v1.38.0부터 환경변수 엄격 처리가 기본값이며, v1.38.0 Heartbeat 출력 panic 때문에 1.38.2 이상 권고) [1차] | — | — | — | — |
| **Redpanda Connect** | 상승 | Telegraf #1(MQTT→Kafka), #2(Kafka→InfluxDB), #3(Kafka alerts→MQTT) 전부를 하나의 바이너리·3개 스트림 YAML로 | Telegraf의 InfluxDB 네이티브 최적화, 익숙한 운영 경험 | `docker.redpanda.com/redpandadata/connect` [미검증: 이미지 경로] + streams 모드 YAML 3개(각 20~40줄). Bloblang으로 스키마 변환 | 설정 LOC, 메모리, 재시작 시 오프셋 재개, 메시지 누락 수 |
| Grafana Alloy / OTel Collector | 관측 데이터용 주류 [미검증] | Prometheus 스크레이프·로그 수집 | 산업 프로토콜·Kafka→MQTT 중계에는 부적합 [미검증] | 관측용으로만 | — |

**판정:** Alloy·OTel Collector는 **운영 관측(메트릭·로그·트레이스)용**이다. 공정 텔레메트리 파이프(MQTT↔Kafka↔TSDB) 대체재로는 적합하지 않다고 판단한다(1차 확인 못함). Telegraf 대체 비교는 Redpanda Connect 하나로 좁히는 것이 효율적이다.

### 3.3 L2~L3 브로커·이벤트 백본

| 후보 | 판정 | 최신·라이선스 | 채택 근거 | V1 대체 | 잃는 기능 | 적합성·PoC |
|---|---|---|---|---|---|---|
| **EMQX**(기준선) | 주류 | **5.9.0(2025-05)부터 BSL 1.1**, Community·Enterprise 통합 [1차].\[5\]\[42\] 운영 단일 노드는 무료. 다중 노드 클러스터, 상용 SaaS, 제품 임베딩 재배포에는 상용 라이선스 필요 [1차].\[43\]\[44\] 5.8.x 이하 오픈소스판은 Apache 2.0 유지 [1차]\[45\] | 마이너 버전에서 라이선스를 바꾼 데 대한 커뮤니티 반발 이슈(#15226, #15352) [1차]\[46\]\[47\] | — | — | 단일 노드 프로토타입은 영향 없음. **이미지 태그 고정**(자동 업그레이드 시 클러스터는 라이선스 없이 기동 실패 가능) [1차]\[5\] |
| Mosquitto | 주류(단일 노드) | [미검증] EPL/EDL | 매우 넓은 채택 [미검증] | EMQX | 룰엔진, 대시보드, 내장 Kafka 브리지 | `eclipse-mosquitto` + conf 5줄. 가장 가벼움 |
| NanoMQ | 상승(엣지) | [미검증] MIT | EMQ 계열 | EMQX | 대시보드·룰엔진 일부 | 엣지 브리지용 |
| HiveMQ CE / Edge | 유지 | [미검증] Apache 2.0(CE) | 벤더 콘텐츠 풍부 | EMQX | 엔터프라이즈 기능 | 비교 가치 낮음 |
| VerneMQ | 정체 [미검증] | — | — | — | — | 신규 비추천(유지보수 상황 재확인 필요) |
| **Apache Kafka**(기준선) | **주류** | 4.0: ZooKeeper 제거, KRaft 전용 [1차].\[7\]\[48\] 4.1: Share Groups 프리뷰 [2차].\[49\]\[50\] **4.2.0(2026-02-17): Share Groups 프로덕션 준비 완료**, Streams DLQ [1차].\[6\]\[51\] 4.2.1에서 Share Group 데드락 수정 [1차].\[7\] 4.3.0(2026-05) [2차]\[52\] | ASF 릴리스 주기 안정 | — | — | V1 Kafka가 3.x/ZooKeeper라면 4.x KRaft 단일 노드로 올리는 것 자체가 "최신화" |
| Redpanda | 상승 | Community는 Redpanda BSL(4년 후 Apache 전환), Enterprise는 RCL. 24.3+ 신규 클러스터는 30일 엔터프라이즈 트라이얼 [1차]\[53\]\[54\] | UMH Core가 내장 브로커로 채택 [1차]\[31\] | Kafka(API 호환) | Kafka 생태계 일부(Streams는 클라이언트라 무관), 순수 오픈소스 라이선스 | `redpandadata/redpanda` 단일 컨테이너 dev 모드. 토픽·소비자 코드 수정 0 |
| NATS JetStream | 상승(클라우드 네이티브) | [미검증] Apache 2.0 | [미검증] | Kafka(+MQTT 게이트웨이 가능) | Kafka 커넥터·Flink 소스 생태계 | Flink 커넥터 성숙도 재확인 필요 |
| Apache Pulsar / AutoMQ | 틈새(대규모) | [미검증] | — | Kafka | — | **12태그 규모에 부적합**. 문헌으로 탈락 |
| Kafka-native MQTT 프록시(Waterstream, Confluent MQTT Proxy) | 틈새 | [미검증] | — | EMQX + Telegraf#1 | MQTT 브로커 기능 전체(세션·보존 메시지) | FUXA가 MQTT 구독을 쓰므로 부적합 |

**레퍼런스 구조 판정**
- **MQTT+Kafka 이중 구조**(V1): 엔터프라이즈 IIoT의 전형이며 Waehner의 "MQTT·OPC UA·Kafka 트리니티" 서사와 일치한다 [2차, 벤더 진영].\[41\] 여러 소비자의 독립 재처리(replay)가 강점이다.
- **MQTT 단일("Kafka-less")**: UNS 커뮤니티가 선호하는 구조다. 태그 12개면 브로커 하나로 충분하다. 다만 Kafka의 **로그 재생, 소비자 그룹별 독립 오프셋, Flink 표준 소스**를 잃는다.
- **Kafka-native**(UMH Core처럼 Redpanda를 내장하고 MQTT는 주변부): UMH가 이 방향이다 [1차].\[31\]
- **판정:** 교육·실습 목적(데이터 흐름을 보여주는 것)이라면 V1의 이중 구조가 오히려 교육 가치가 있다. "최신"을 이유로 Kafka를 빼는 것은 근거가 약하다. 대신 Kafka 4.x KRaft 단일 노드로 최신화할 것을 권장한다.

### 3.4 L4 스트림 처리·이상탐지

**시나리오 4종 구현 방식 비교**(Z-Score 윈도, 순서 패턴, 지연 이벤트, 재시작 복구)

| 방식 | 판정 | 상·하한 / Z-Score 윈도 | "전류↑ 후 N초 내 진동↑" | out-of-order·late | 재시작 상태 복구 | 12태그 적합성 |
|---|---|---|---|---|---|---|
| **Flink DataStream + CEP**(기준선) | 주류 | 키드 윈도 + ProcessFunction | `begin("cur").followedBy("vib").within(N s)`로 자연스럽게 표현 | 워터마크 + allowedLateness + side output | 체크포인트/세이브포인트(정확히-한번) | 기능은 최상, 운영 무게(JM/TM, JVM)는 최대 |
| **Flink SQL MATCH_RECOGNIZE** | 주류 | `OVER (RANGE INTERVAL ...)`로 AVG/STDDEV | `PATTERN (A X*? B) WITHIN INTERVAL 'N' SECOND`로 우회. `followedBy` 네이티브 미지원(FLINK-33428) [1차]\[18\] | 이벤트 시간 ORDER BY + 워터마크 [1차]\[55\] | Flink 체크포인트 | 코드량 감소. 패턴 표현력 일부 손실 |
| **eKuiper** | 유지~상승 | SQL 윈도 함수(텀블링·호핑·슬라이딩·세션) [1차: 2.2 슬라이딩 개선 언급]\[35\] | 전용 순서 패턴 연산자 여부 [미검증]. 슬라이딩 윈도 + 조건으로 근사 | [미검증] | 룰 상태 체크포인트 [미검증] | 매우 가벼움. 엣지 규칙엔 적합, 정확성 보장은 약할 수 있음 |
| **RisingWave**(스트리밍 DB) | 상승 | 머티리얼라이즈드 뷰 + 윈도 함수 | MATCH_RECOGNIZE 지원 여부 [미검증]. 셀프 조인 + 시간 조건으로 구현 | 워터마크 지원 [미검증] | 내장 상태 저장(체크포인트) | v3.0.1(2026-06-30), 코어 Apache-2.0, 일부 기능은 라이선스 키 [1차]. PG 프로토콜이라 Grafana 직결 가능\[56\]\[57\]\[58\]\[59\] |
| Materialize / Timeplus Proton | 상승/틈새 | SQL | [미검증] | [미검증] | [미검증] | Materialize 라이선스 조건 재확인 필요 [미검증] |
| **Arroyo** | 불확실 | SQL | [미검증] | 워터마크 | 체크포인트 | 2025-04 Cloudflare 인수. 엔진은 Apache로 오픈소스 유지 약속 [1차]. 그러나 개발 중심이 Cloudflare Pipelines로 이동\[60\]\[61\] → **신규 채택 신중** |
| Kafka Streams | 주류(JVM) | 윈도 집계 | Processor API 상태 머신 | grace period | changelog 토픽 | 4.2에 DLQ 추가 [1차].\[51\] Java 서비스 1개 |
| **Python 서비스(Quix Streams / 순수 asyncio)** | 상승(Quix) [미검증: 버전] | pandas/deque 롤링 | 키별 상태 머신 20~40줄 | 수동 버퍼링 | Kafka 오프셋 + 로컬 상태 저장(RocksDB, Quix) [미검증] | **높음**. ONNX·River와 한 프로세스로 결합 가능 |
| Bytewax | **쇠퇴 의심** | — | — | — | — | 제3자 연재(Gang Tao)가 "프로젝트 침묵"을 지적 [2차].\[62\] 1차 확인 전 채택 비추천 |
| EMQX 룰엔진 / Flow Designer | 유지 | 단순 필터·변환 | 부적합 | — | — | 5.9+ BSL 단일 노드에서 전 기능 사용 가능 [1차]\[44\] |

**ML 이상탐지 서빙 트렌드**(가볍게)
- **ONNX Runtime**(V1 채택): 모델 서빙 표준 포맷으로 여전히 주류다 [미검증: 버전]. Flink 내 JVM ONNX 대신 Python 서비스에서 onnxruntime을 쓰는 구조가 12태그 규모에서는 디버깅이 쉽다.
- **River**(온라인 학습, HalfSpaceTrees 등) / **PyOD**(배치 이상탐지 모음) [미검증]: Autoencoder와 같은 score 토픽 계약으로 비교하기 좋다.
- **시계열 파운데이션 모델**(TimesFM, Chronos, Moirai, MOMENT) [미검증]: 주로 예측용이며, 이상탐지는 "예측 잔차" 방식으로 간접 활용한다. 교육용 12태그 PoC에서는 추론 비용 대비 설명 가치가 낮으므로 **V3 이후 선택 과제**로 둔다.

### 3.5 L5 시계열·히스토리안·업무 저장

| 후보 | 판정 | 최신 버전·날짜 | 라이선스 | 핵심 제약·특징 | V1 대체 | 잃는 기능 | PoC |
|---|---|---|---|---|---|---|---|
| **InfluxDB 2.x**(기준선 추정) | 유지(구세대) | [미검증] | MIT | Flux 기반 | — | — | — |
| **InfluxDB 3 Core** | 상승(세대 교체) | 3.11.x 라인. Core/Enterprise 패치 수준 상이 가능(3.11.2~3.11.5) [1차·2차 혼재]\[63\]\[64\]\[65\] | Core MIT/Apache-2.0, Enterprise 상용(가정용 무료 티어) [1차]\[66\]\[67\] | InfluxData 공식 설정 문서: 기본 파일 한도 432개와 gen1 10분 설정에서 "queries can access up to a 72 hours of data, but potentially less". 문서는 "We recommend keeping the default setting and querying smaller time ranges"라고 권고하며, `--query-file-limit`로 상향할 수 있으나 성능이 저하된다 [1차]. **Flux 미지원** [1차].\[68\] InfluxData 문서 원문: "On September 15, 2026, the latest tag for InfluxDB Docker images will point to InfluxDB 3 Core. To avoid unexpected upgrades, use specific version tags" [1차] | InfluxDB 2 | Flux 대시보드·태스크, 장기 범위 단일 쿼리 | `influxdb:3-core` + Telegraf `outputs.influxdb_v2` 대신 v3 쓰기. Grafana는 SQL/InfluxQL 데이터소스 |
| **TimescaleDB**(Tiger Data) | **주류·상승** | 2.30.1(2026-09-17) [1차]. 회사명 Timescale → **Tiger Data(2025-06-17)** [2차]\[69\]\[70\] | Apache 2 에디션 + Community 에디션(TSL: 자가 호스팅 무료, DBaaS 판매 금지) [1차]\[71\]\[72\] | 하이퍼테이블·연속 집계·압축(TSL 기능) | **InfluxDB + PostgreSQL 통합 가능** | Influx 라인 프로토콜 네이티브 수집(Telegraf postgresql 출력으로 대체) | `timescale/timescaledb`(PG 확장이라 V1 PostgreSQL 교체로 1컨테이너 절감) |
| **QuestDB** | 상승 | OSS 10.0.1(2026-08-24). 10.0에서 바이너리 프로토콜 QWP 도입 [1차]\[73\]\[74\]\[75\] | Apache-2.0 [1차] | ILP·PG 와이어 호환 | InfluxDB | Flux | `questdb/questdb` + ILP 쓰기 |
| **GreptimeDB** | 상승 | v1.0 GA(2026-04-08), v1.2.1(2026-09-16) [1차]\[76\]\[77\] | Apache-2.0(재확인 권장) | 메트릭·로그·트레이스 통합 지향\[78\] | InfluxDB(+Prometheus 원격 저장) | 성숙도(1.0 직후) | `greptime/greptimedb` |
| TDengine | 유지(중국권 강세) | 3.4.1.13 확인, 3.4.2 문서 존재 [1차]\[79\] | OSS **AGPL-3.0** [1차]\[80\] | 이미지명 `tdengine/tsdb`로 변경 [1차]\[81\] | InfluxDB | — | AGPL 조건 때문에 사내 배포 시 검토 필요 |
| Apache IoTDB | 유지 | 2.0.11(2026-09) [1차]\[82\] | Apache-2.0 | IoT 트리 모델 | InfluxDB | 생태계(Grafana 플러그인 등) | 12태그엔 과함 |
| ClickHouse | 주류(분석) | [미검증] | Apache-2.0 | 분석 OLAP | InfluxDB | 히스토리안 친화 기능 | 규모 대비 과함 |
| VictoriaMetrics | 주류(메트릭) | v1.152.0(2026-09-11) [1차]\[9\] | Apache-2.0(OSS) | Prometheus 호환 | Prometheus 저장(L6) | — | L6 관측용으로만 |

**판정**
- V1이 InfluxDB 2를 쓰고 있다면, 이는 **공식적으로 구세대**다. InfluxData 문서가 "On September 15, 2026, the latest tag for InfluxDB Docker images will point to InfluxDB 3 Core"라고 밝혔으므로 **태그 고정을 즉시 확인**해야 한다.
- InfluxDB 3 Core의 약 72시간 쿼리 제한은 "공정 히스토리안" 역할(교대·일간 추이 조회)과 충돌할 수 있다. 사내 비상업 연구용이라 해도 Enterprise "at-home" 무료 티어는 가정용 조건이므로 적용 대상이 아닐 가능성이 크다.\[66\]\[83\]
- **가장 실용적인 대안은 TimescaleDB로 시계열과 업무 기록을 PostgreSQL 하나에 통합하는 것**이다. 컨테이너가 1개 줄고, 사건 ↔ 센서 이력 조인을 SQL 한 번으로 할 수 있어 L7~L9 근거 조회가 단순해진다.

### 3.6 L6 HMI/SCADA·관측

| 후보 | 판정 | 최신·라이선스 | 근거 | V1 대체 | 잃는 기능 | 적합성·PoC |
|---|---|---|---|---|---|---|
| **FUXA**(기준선) | 오픈소스 웹 SCADA 중 활발 | MIT(GitHub frangoteam/FUXA 저장소 LICENSE 파일, Context7 색인 "License:MIT"). 저장소 헤더 기준 "Fork 1.4k · Star 5k", 공식 문서는 frangoteam.github.io/FUXA로 이전, 2026-08 토론 활동 [1차]. **CISA ICSA-26-181-02(2026-06-30): 1.3.1 이하 인증 우회(CVE-2026-13207), 1.3.2 이상 권고** [1차].\[84\] **2026-02 Node-RED 통합 비인증 RCE(Critical) 권고** [1차]\[85\] | 활발하나 보안 성숙도 낮음 | — | — | **1.3.2+로 즉시 업그레이드**. Modbus 쓰기 권한이 있으므로 네트워크 격리 필수 |
| **Ignition 8.3** | 산업 주류(상용) | 8.3 출시 2025-09-16, 5년 LTS [1차].\[86\] 다운로드 페이지 8.3.8 [1차]. **Maker Edition은 비상업·개인 교육용 전용**, Perspective 세션 10개, 태그 10,000개 제한 [1차].\[87\] 8.3에서 Kafka Connector가 Maker 호환 [1차]\[88\] | ICC 컨퍼런스, 대규모 SI 생태계(Corso Systems 등) [2차]\[89\] | FUXA(+Alertmanager 일부 알람 기능) | 오픈소스성, 무료 상업 사용 | **회사 업무 프로토타입에 Maker는 라이선스 위반 소지**. 표준판 체험 모드 사용 조건은 [미검증] → 법무 확인 전 제외 권장 |
| Node-RED Dashboard 2.0 / FlowFuse Dashboard | 상승 | [미검증] | [미검증] | FUXA 일부 | SCADA 심볼·P&ID 편집기 | 게이트웨이를 Node-RED로 할 때만 |
| Rapid SCADA 6 / SCADA-LTS / OpenSCADA | 틈새·정체 [미검증] | — | — | FUXA | — | 이번 회전 제외 |
| **Vue 커스텀 HMI + MQTT over WebSocket** | 상승(웹 표준) | — | [미검증] | FUXA 표시 기능 | 드래그앤드롭 편집기 | V1 Vue 대시보드가 이미 이 트렌드. mqtt.js로 EMQX `ws://:8083` 구독만 추가 |
| Grafana | 주류(관측·이력) | [미검증] | — | — | — | 쓰기·제어는 **제어 경로로 쓰지 말 것**(V1 방침 유지) |
| Prometheus/Alertmanager | 주류 | [미검증] | — | — | — | 유지 |
| VictoriaMetrics | 주류 대안 | v1.152.0. v1.150.0부터 `-enableMultitenancyViaHeaders` 기본 true [1차]\[9\] | — | Prometheus TSDB | Prometheus 네이티브 경보 흐름 일부 | 선택 비교(메모리 지표) |

**ISA-101 / ISA-18.2**
- ISA-101(고성능 HMI: 회색 배경, 이상 시에만 색상, 추세 중심)은 이미지 스타일 가이드다. V1 Vue 화면에 즉시 적용 가능한 "디자인 과제"이며, 도구 교체 문제가 아니다.
- ISA-18.2(알람 수명주기: 발생 → 확인 → 해제, shelving, 억제, 알람률 KPI)를 충실히 구현한 성숙 오픈소스 컴포넌트는 이번 조사에서 확인하지 못했다 [미검증]. **PostgreSQL 알람 상태 테이블 + Vue 확인 버튼**(V1에 이미 있음)을 18.2 상태 모델로 확장하는 것이 현실적이다.

### 3.7 배포

| 옵션 | 판정 | 소규모 프로토타입 관점 |
|---|---|---|
| **Docker Compose**(V1) | 주류 | **유지 권장.** 5일 회전에서는 `docker compose up <service>` 단위로 한 모듈씩 교체하는 방식이 가장 빠르다. UMH Core도 "쿠버네티스 불필요, Docker만"을 내세운다 [1차]\[31\] |
| k3s / K8s | 주류(운영) | 12태그 단일 머신에는 과함. V3 이후 배포 트랙 |
| Portainer / balena / KubeEdge | 틈새 [미검증] | 엣지 다수 배포 관리용. 이번 범위 밖 |
| Ignition 8.3 컨테이너 | 상승 | 8.3에서 컨테이너화 단순화·Helm 지원을 강조 [1차, 벤더]\[90\] |

---

## 4. 클린시트 레퍼런스 아키텍처 4종과 V1 매핑

| 레이어 | V1 | **A. UMH Core형(Kafka-native UNS)** | **B. Kafka-less MQTT 중심** | **C. PostgreSQL 중심 단순형** | **D. Redpanda + 스트리밍DB** |
|---|---|---|---|---|---|
| L1 | 시뮬레이터 | 동일 | 동일 | 동일 | 동일 |
| L2 게이트웨이 | EdgeX | benthos-umh(Modbus) | Neuron OSS | pymodbus 또는 Redpanda Connect | Redpanda Connect |
| L2 브로커 | EMQX | (내장 Redpanda가 UNS, MQTT는 선택) | EMQX 단일 노드 / Mosquitto | Mosquitto | EMQX 또는 생략 |
| L2 파이프 | Telegraf×3 | benthos 내부 | eKuiper 싱크 | Python 서비스 | Redpanda Connect |
| L3 | Kafka | Redpanda(내장) | **없음** | **없음**(또는 PG LISTEN/NOTIFY) | Redpanda |
| L4 | Flink(규칙+CEP, ONNX) | Python/benthos 처리 | eKuiper SQL + Python ONNX | Python(상태 머신 + onnxruntime) | RisingWave MV + Python ONNX |
| L5 | InfluxDB + PostgreSQL | TimescaleDB(UMH Classic 기본) [미검증: Core 기본 싱크] | InfluxDB 3 Core 또는 Timescale | **TimescaleDB 1개** | RisingWave → TimescaleDB |
| L6 | FUXA/Grafana/Prom/Vue | Grafana + Vue | FUXA + Grafana + Vue | Grafana + Vue(+FUXA) | Grafana + Vue |
| **제거되는 V1 컴포넌트** | — | EdgeX, EMQX(선택), Telegraf, Kafka, Flink, InfluxDB | EdgeX, Telegraf, Kafka, Flink | EdgeX, EMQX→Mosquitto, Telegraf, Kafka, Flink, InfluxDB | EdgeX, Telegraf, Flink, InfluxDB |
| **잃는 기능** | — | Flink CEP·정확히-한번. **UMH 관리 콘솔(SaaS) 의존**. FUXA용 MQTT 알람 중계 재구현 | 로그 재생·독립 소비자 오프셋. event-time 정확성 | 스트림 엔진의 체크포인트·워터마크(직접 구현). 교육용 "데이터 흐름 가시성" 감소 | 순서 패턴 표현력(MATCH_RECOGNIZE 지원 미확인). 라이선스 키 기능 |
| 컨테이너 수(대략) | 15+ | 3~5 | 5~7 | 4~6 | 6~8 |
| 교육 가치 | 높음(산업 표준 부품을 모두 보여줌) | 중간(UNS 트렌드 체험) | 중간 | 낮음~중간(단순하지만 "산업 스택" 느낌 약함) | 중간 |
| 추천 용도 | V1 기준선 | V2 "UNS 트렌드" 시연용 | 엣지 경량화 교육 | **운영 단순화 기준선** | 스트리밍 SQL 교육 |

**판정:** 대표님의 "최신 트렌드" 요구에 가장 잘 맞으면서 V1의 교육 가치를 덜 잃는 조합은 **"V1 골격 유지 + 부품 최신화"**(Kafka 4.x KRaft, Flink 2.x SQL, TimescaleDB 또는 InfluxDB 3, Redpanda Connect, FUXA 1.3.2+, ISA-95 토픽)다. A~D는 마지막 날 1개만 골라 "클린시트 비교"로 보여주기를 권한다. 추천은 **C**(단순성의 극단을 기준선으로 제시할 수 있음)다.

---

## 5. L7~L9 간단 후보 표(AI 레이어)

| 레이어 | 후보 | 상태 | V1 대비 | 판정 |
|---|---|---|---|---|
| L7 그래프 | Neo4j(기준선) | 주류 [미검증: 5.x/2025.x 버전] | — | 유지 |
| | PostgreSQL + Apache AGE + pgvector | 상승 [미검증] | Neo4j 제거, Timescale과 한 DB | 아키텍처 C와 결합 시 비교 가치 |
| | Memgraph / FalkorDB | 상승 [미검증] | Cypher 호환 | 선택 |
| | **Kuzu** | **2025-10-10 저장소 아카이브(최종 0.11.3), Apple 인수(EU 공시로 2026-02 확인)** [2차 다수, 일관]\[10\]\[91\] | — | **탈락.** 포크(LadybugDB, Bighorn)는 성숙도 미확인\[92\] |
| | GraphRAG / LightRAG | 상승 [미검증] | 문서 → 관계 후보 추출 | V1 "후보 검토 → 게시" 파이프라인과 개념 일치. V3 과제 |
| 온톨로지 | ISA-95(설비 계층·역할), OPC UA 정보모델(노드·타입), AAS(자산관리셸, 디지털 트윈 서브모델), SOSA/SSN(W3C 센서·관측), PROV-O(W3C 출처·파생) | 표준 [일반 지식] | — | 설비↔센서는 ISA-95 + SOSA, 문서 출처·승인 이력은 PROV-O로 매핑하면 V2 온톨로지 개선의 명분이 됨 |
| L8 게이트웨이 | **LiteLLM** | **2026-03-24 PyPI 1.82.7/1.82.8 악성 배포**(TeamPCP, Trivy CI 경유 토큰 탈취). LiteLLM 공식 보안 공지 기준 "March 24, 2026 from 10:39 UTC for about 40 minutes" 노출 후 PyPI가 격리(IONIX는 "approximately three hours"로 적어 출처 간 차이 있음). 공식 공지는 "Customers running the official LiteLLM Proxy Docker image were not impacted"라고 밝힘. v1.83.0부터 새 CI/CD [1차: LiteLLM 공지, PyPI 사고 보고] | — | **유지 가능하나** 버전 고정, 해시 검증, Docker 이미지 사용, 비밀키 로테이션 점검 필수 |
| | Portkey / 직접 SDK(google-genai 등) | [미검증] | 게이트웨이 제거 | 모델이 GCP 하나라면 직접 SDK가 가장 단순 |
| L8 에이전트 | MCP 기반 도구 서버, OpenAI Agents SDK, Claude Agent SDK, Pydantic AI, Google ADK | 상승 [미검증] | "조회 도구"를 MCP 서버로 표준화 | 조회 도구 3종을 MCP로 감싸는 것이 가장 트렌드 친화적이며 저위험 |
| L9 워크플로 | LangGraph(기준선: interrupt + checkpointer) | 주류 [미검증] | — | 유지. 조사 → 검토 대기 HITL에 적합 |
| | Temporal / DBOS / Restate | 상승 [미검증] | "승인 → 재검사 → Modbus 정지 → 상태 확인 → 기록"을 내구성 워크플로로 | **승인 후 중복실행 방지(멱등 키), 감사 추적, 재시도** 관점에서 비교 가치. DBOS는 PostgreSQL만으로 동작해 C안과 궁합 [미검증] |
| | Camunda 8 / Zeebe | 주류(BPMN) | 진짜 BPMN 엔진 | **8.6+부터 Self-Managed 운영 사용은 유료 Enterprise 라이선스 필요**(소스는 Camunda License v1.0) [1차].\[12\]\[13\]\[93\] 프로토타입(비운영)은 가능하나 운영 전환 시 비용 발생 |
| | Flowable | [미검증: 오픈소스판 Apache 2.0 여부] | BPMN | "BPMN 형태 표시" 요구만 있다면 bpmn-js로 LangGraph 상태를 렌더링하는 편이 가벼움 |

---

## 6. 5영업일 회전 우선순위(한 번에 한 모듈 교체)

**공통 원칙**
- **고정 테스트 하니스를 먼저 만든다(0.5일).** 시뮬레이터의 이상 주입으로 시나리오 S1~S6을 정의하고 매 회전 동일하게 재생한다. S1 고온(상한), S2 압력 인터록, S3 Z-Score 드리프트, S4 전류↑→N초 내 진동↑, S5 순서 뒤바뀐/지연 이벤트 주입, S6 처리 컨테이너 강제 재시작.
- **공통 측정 지표**(결과값은 비워 둠):
  - M1 종단 지연(Modbus 값 변경 → 알람 토픽/화면 표시, p50/p95)
  - M2 알람 정확도(주입 이상 대비 탐지·오탐 수)
  - M3 재시작 후 유실·중복 이벤트 수
  - M4 복구 시간
  - M5 컨테이너 메모리·CPU(`docker stats` 평균·최대)
  - M6 이미지 크기·컨테이너 수
  - M7 설정·코드 LOC
  - M8 바이브 코딩 소요 시간(에이전트 대화 턴 수 포함)
  - M9 라이선스·보안 리스크 메모
- 계약(토픽명·JSON 스키마·Kafka 토픽 raw/clean/score/alerts)은 고정하고 모듈만 교체한다.

| 일차 | 교체 대상(1모듈) | 후보(2~3개) | 핵심 관찰 포인트 | 결과(빈칸) |
|---|---|---|---|---|
| D1 오전 | 하니스 + 기준선 측정 | V1 그대로 | M1~M9 기준값 | |
| D1 오후 | **L1~L2 게이트웨이** | ① EdgeX 4.0(기준) ② Neuron OSS(LGPL, Modbus TCP) ③ benthos-umh standalone | 폴링 주기 정확도, 명령 경로 영향(EdgeX command 사용 여부), M5·M6 | |
| D2 오전 | **L2 수집 파이프** | ① Telegraf×3(기준) ② Redpanda Connect streams 모드 3파이프 | 설정 LOC, 오프셋 재개(S6), FUXA 알람 중계 지연 | |
| D2 오후 | **L2 토픽 구조**(선택) | `edgex/telemetry` vs ISA-95 UNS 토픽 | 소비자 수정량, 가독성 | |
| D3 | **L4 규칙·CEP** | ① Flink DataStream CEP(기준) ② Flink 2.x SQL MATCH_RECOGNIZE ③ Python 서비스(Quix Streams 또는 순수 asyncio + 상태 머신) | S4 패턴 탐지 동등성, **S5 지연 이벤트 처리**, S6 복구, M5(JVM vs Python) | |
| D3 부가 | L4 ONNX | Flink ONNX(기준) vs Python onnxruntime 서비스 | 점수 동일성(같은 입력 → 같은 score), 지연 | |
| D4 | **L5 시계열** | ① InfluxDB 2(기준, 태그 고정 확인) ② InfluxDB 3 Core ③ TimescaleDB(PG 통합) | Grafana 쿼리 이식 난이도(Flux → SQL), 72시간 이상 범위 쿼리 동작, 사건↔센서 조인 | |
| D5 오전 | **L6 HMI** | ① FUXA 1.3.2+ 업그레이드(필수) ② Vue + MQTT over WebSocket 알람 직접 구독(Telegraf#3 제거 가능성) | 알람 표시 지연, 제어 3경로 분리 유지 여부 | |
| D5 오후 | **클린시트 1안 비교** | 아키텍처 C(PG 중심) 또는 A(UMH형) | 같은 S1~S6 통과 여부, M5·M6·M7 총량 | |

**보류(시간이 남을 때만):** Redpanda로 Kafka 교체(API 호환이라 코드 수정이 적음), VictoriaMetrics로 Prometheus 교체, LangGraph 실행 단계를 DBOS/Temporal로 교체.

---

## 7. 문헌만으로 탈락 또는 유지 가능한 항목

**탈락(구현 비교 불필요)**
- **Kuzu**: 2025-10 저장소 아카이브, Apple 인수. 포크는 성숙도 미확인.\[92\]
- **Esper / Siddhi(독립 CEP 엔진)**: Esper는 GPL v2이고 마지막 메이저가 2024-04로 느리다.\[15\]\[16\] Siddhi는 최근 활동 근거가 없다. Flink가 이미 같은 기능을 제공한다.
- **Apache Pulsar, AutoMQ**: 대규모·멀티테넌시·클라우드 비용 최적화용이다. 12태그 단일 머신에는 무의미하다.
- **Kafka-native MQTT 프록시(Waterstream 등)**: FUXA·Vue가 MQTT 브로커 기능(구독·보존 메시지)을 필요로 해 부적합하다.
- **Ignition Maker Edition**: 비상업·개인용 전용이라 회사 프로토타입 사용 시 라이선스 위반 소지가 있다.\[87\]
- **Bytewax**: 제3자 자료 기준 활동 정체.\[62\] 1차 반증이 없으면 제외한다.
- **Arroyo**: 오픈소스 유지를 약속했으나 Cloudflare 인수 후 방향이 불확실하다.\[60\] 5일 회전 후보에서 제외한다.
- **시계열 파운데이션 모델 이상탐지**: 12태그 교육 PoC에 비용 대비 가치가 낮다. V3 이후로 둔다.
- **k3s/KubeEdge/balena**: 단일 머신 Compose 회전 목적과 맞지 않는다.
- **Camunda 8(운영 목적)**: 8.6+ 운영 시 유료다.\[12\] BPMN "표시"는 bpmn-js로 충분하다.

**유지(교체 근거 없음, 최신화만)**
- **PostgreSQL**(업무 DB): 주류이며 오히려 통합의 중심이 된다.
- **Kafka**: 4.x KRaft로 올리기만 해도 "최신"이다(4.2 Share Groups GA).\[6\]
- **Prometheus/Alertmanager/Grafana**: 관측 표준. Alertmanager를 설비 정지 경로로 쓰지 않는 V1 방침은 올바르다.
- **EMQX 단일 노드**: BSL이어도 단일 노드 운영은 무료다. 단 이미지 태그를 고정한다.\[5\]
- **ONNX Runtime**: 서빙 포맷 표준. 실행 위치(Flink vs Python)만 비교한다.
- **LangGraph**(L9 조사·HITL): 교체보다 실행 단계의 멱등성·감사 강화가 우선이다.
- **Vue 커스텀 HMI**: 웹 HMI 트렌드와 이미 일치한다. ISA-101 스타일만 적용한다.
- **3개 제어 경로 분리 + AI가 버튼을 누르지 않는 원칙**: 산업 안전 관점에서 기술 교체와 무관하게 유지한다.

**즉시 조치(비교 전 선행)**
- FUXA ≥ 1.3.2 업그레이드(CISA ICSA-26-181-02), Node-RED 통합 기능 비활성 또는 최신화.
- `influxdb:latest`, `emqx/emqx:latest` 등 **latest 태그를 제거하고 버전을 고정**한다(InfluxData 문서: "To avoid unexpected upgrades, use specific version tags in your Docker deployments").
- LiteLLM 버전 확인(1.82.7/1.82.8이 아닌지), 해당 환경의 GCP 자격증명 로테이션 여부 점검.

---

## 8. 주의사항(Caveats)

- **검증 범위의 한계:** 이번 조사는 검색 예산 제약으로 Mosquitto, NanoMQ, HiveMQ, NATS, Node-RED, Grafana Alloy, OTel, Materialize, Quix Streams, River, Neo4j, Memgraph, Temporal, DBOS, Restate, Flowable, 각종 Agent SDK의 최신 버전·라이선스를 1차 확인하지 못했다. 표의 [미검증] 항목은 PoC 착수 당일 공식 릴리스 페이지에서 5분 확인을 권장한다.
- **버전 불확실:** InfluxDB 3의 Core·Enterprise 최신 패치(3.11.2~3.11.5 범위), TDengine 3.4.2 출시 여부, RisingWave v3.1.0 공식 출시일은 자료 간 불일치 또는 미확인 상태다.\[94\] EdgeX "Palau 4.0.2"는 위키 릴리스 표에만 근거한다.\[20\]
- **출처 편향:** Kai Waehner(Kafka/Flink 진영), HiveMQ·EMQ·Redpanda·UMH·RisingWave·QuestDB 블로그는 모두 이해관계가 있는 출처다. 트렌드 판정은 릴리스 빈도·저장소 활동·보안 권고·재단 발표 같은 독립 신호를 우선했다. UMH의 "Node-RED보다 안정적", Redpanda의 "Kafka Connect 대비 3배 적은 자원" 같은 문구는 벤더 주장이며 측정되지 않았다.
- **성능 수치 없음:** 본 보고서는 어떤 후보의 처리량·지연도 측정하지 않았다. 6장의 결과 칸은 회전 실측으로만 채워야 한다.
- **라이선스 판단:** EMQX BSL, Redpanda BSL/RCL, Timescale TSL, TDengine AGPL, Camunda License, Ignition Maker 조건은 요약이다. 교육 콘텐츠로 외부 배포하거나 제품에 임베딩한다면 법무 확인이 필요하다.
- 출처 URL 목록은 본 문서 형식상 별도 인용 처리로 제공되며, 본문에는 출처 기관·문서명과 날짜를 명시했다.

## 출처

1. [Complex Event Processing (CEP) with Apache Flink: What It Is and When (Not) to Use It](https://www.kai-waehner.de/blog/2026/04/14/complex-event-processing-cep-with-apache-flink-what-it-is-and-when-not-to-use-it/)
2. [EdgeX Odesa Release | IOTech, Edge Software Solutions](https://www.iotechsys.com/edgex-community/edgex-latest-release-odesa/)
3. [Our Latest Release | EdgeX Foundry, Open Source Edge Platform](https://www.edgexfoundry.org/software/releases/)
4. [Work with EMQX Enterprise License | EMQX Enterprise Docs](https://docs.emqx.com/en/emqx/latest/deploy/license.html)
5. [Follow-up Notice: emqx/emqx Docker Image Update to v5.9.0 (BSL License) · emqx/emqx · Discussion #15212](https://github.com/emqx/emqx/discussions/15212)
6. [Apache Kafka 4.2.0 Released: Share Groups, Streams & More](https://www.confluent.io/blog/apache-kafka-4-2-release/)
7. [Upgrading | Apache Kafka](https://kafka.apache.org/42/getting-started/upgrade/)
8. [Apache Flink 2.2.1 Release Announcement | Apache Flink](https://flink.apache.org/2026/05/15/apache-flink-2.2.1-release-announcement/)
9. [Releases · VictoriaMetrics/VictoriaMetrics](https://github.com/VictoriaMetrics/VictoriaMetrics/releases)
10. [What Is KuzuDB?](https://www.puppygraph.com/blog/what-is-kuzudb)
11. [Security Update: Suspected Supply Chain Incident | liteLLM](https://docs.litellm.ai/blog/security-update-march-2026)
12. [Camunda Licensing: What You Need to Know | Camunda](https://camunda.com/blog/2024/10/camunda-licensing-what-you-need-to-know/)
13. [Licensing | Camunda 8 Docs](https://docs.camunda.io/docs/reference/licenses/)
14. [Esper - Wikidata](https://www.wikidata.org/wiki/Q19605478)
15. [Index of /](https://esper.espertech.com/)
16. [Esper (software)](<https://en.wikipedia.org/wiki/Esper_(software)>)
17. [Pattern Recognition | Apache Flink](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/table/sql/queries/match_recognize/)
18. [\[FLINK-33428\] Flink SQL CEP support 'followed','notNext' and 'notFollowedBy' semantics - ASF Jira](https://issues.apache.org/jira/browse/FLINK-33428)
19. [Flink SQL MATCH\_RECOGNIZE: Complex Event Processing with SQL - Streamkap](https://streamkap.com/resources-and-guides/flink-sql-pattern-matching)
20. [Releases - EdgeX Wiki - Confluence](https://lf-edgexfoundry.atlassian.net/wiki/display/FA/Releases)
21. [edgexfoundry Archives - IOTech Systems](https://iotechsys.com/tag/edgexfoundry/)
22. [EdgeX Foundry Launches EdgeX 4.0 “Odesa”: The Most Secure and Industry-Ready Release Yet – LF EDGE: Building an Open Source Framework for the Edge.](https://lfedge.org/edgex-foundry-launches-edgex-4-0-odesa-the-most-secure-and-industry-ready-release-yet/)
23. [GitHub - emqx/neuron: Open source industrial connectivity server · GitHub](https://github.com/emqx/neuron)
24. [Installing and Activating License | Neuron 2.8 Docs](https://docs.emqx.com/en/neuron/v2.8/installation/license-install/license-install.html)
25. [License Management | EMQX Neuron Docs](https://docs.emqx.com/en/neuronex/latest/installation/license_setting.html)
26. [chore: bump benthos-umh to v0.15.2 by umh-cross-repo-automation\[bot\] · Pull Request #2742 · united-manufacturing-hub/united-manufacturing-hub](https://github.com/united-manufacturing-hub/united-manufacturing-hub/pull/2742)
27. [chore: bump benthos-umh to v0.16.0 by umh-cross-repo-automation\[bot\] · Pull Request #2781 · united-manufacturing-hub/united-manufacturing-hub](https://github.com/united-manufacturing-hub/united-manufacturing-hub/pull/2781)
28. [United Manufacturing Hub · GitHub](https://github.com/united-manufacturing-hub)
29. [QuestDB 9.0 Released For High Performance, Time-Series Database - Phoronix](https://www.phoronix.com/news/QuestDB-9.0)
30. [Benthos UMH | United Manufacturing Hub](https://umh.docs.umh.app/docs/features/connectivity/benthos-umh/)
31. [GitHub - united-manufacturing-hub/united-manufacturing-hub: The data platform for manufacturing · GitHub](https://github.com/united-manufacturing-hub/united-manufacturing-hub)
32. [Data Integration Platform & Connectors | Redpanda Connect](https://www.redpanda.com/connect)
33. [connect/licenses at main · redpanda-data/connect](https://github.com/redpanda-data/connect/tree/main/licenses)
34. [Document change in licensing · Issue #2621 · redpanda-data/connect](https://github.com/redpanda-data/connect/issues/2621)
35. [eKuiper 2.2.0 Delivers Enhanced Streaming Capabilities and Advanced Rule Management – LF EDGE: Building an Open Source Framework for the Edge.](https://lfedge.org/ekuiper-2-2-0-delivers-enhanced-streaming-capabilities-and-advanced-rule-management/)
36. [Releases · lf-edge/ekuiper](https://github.com/lf-edge/ekuiper/releases)
37. [chore: port bugfixes and refactors by ngjaying · Pull Request #4168 · lf-edge/ekuiper](https://github.com/lf-edge/ekuiper/pull/4168)
38. [eKuiper Rules Engine - EdgeX Foundry Documentation](https://docs.edgexfoundry.org/2.0/microservices/support/eKuiper/Ch-eKuiper/)
39. [Sparkplug 3.0 Is Now an International Standard — and 4.0 Is on the Way! | Eclipse News, Eclipse in the News, Eclipse Announcement](https://newsroom.eclipse.org/eclipse-newsletter/2023/december/sparkplug-30-now-international-standard-%E2%80%94-and-40-way)
40. [MQTT Sparkplug: A Game Changer for Adopting IIoT and Digital Transformation](https://www.hivemq.com/webinars/mqtt-sparkplug-gamechanger-adopting-iiot-digital-transformation/)
41. [MQTT Market Trends: Cloud, Unified Namespace, Sparkplug, Kafka Integration - Kai Waehner](https://www.kai-waehner.de/blog/2023/12/08/mqtt-market-trends-for-2024-cloud-unified-namespace-sparkplug-kafka-integration/)
42. [EMQX Adopts Business Source License to Accelerate MQTT + AI Innovation | EMQ](https://www.emqx.com/en/news/emqx-adopts-business-source-license)
43. [EMQX's Next Chapter: Adopting Business Source License to Accelerate "MQTT + AI" Innovation | EMQ](https://www.emqx.com/en/blog/adopting-business-source-license-to-accelerate-mqtt-and-ai-innovation)
44. [EMQX 5.9 adopts Business Source License (BSL) · emqx/emqx · Discussion #15163](https://github.com/emqx/emqx/discussions/15163)
45. [EMQX Licensing FAQ | EMQ](https://www.emqx.com/en/content/license-faq)
46. [License change done on a minor release, · Issue #15226 · emqx/emqx](https://github.com/emqx/emqx/issues/15226)
47. [License change done on a minor release, · emqx/emqx · Discussion #15352](https://github.com/emqx/emqx/discussions/15352)
48. [Kafka 4.0 & KRaft: The End of ZooKeeper - Java Code Geeks](https://www.javacodegeeks.com/2026/02/kafka-4-0-kraft-the-end-of-zookeeper.html)
49. [Kafka 4.1: Enhancements in the Latest Release | OpenLogic](https://www.openlogic.com/blog/kafka-4-1-overview)
50. [Kafka 4.1 Release: Queues, Stream Groups, and More | Factor House](https://factorhouse.io/articles/kafka-4-1-release-announcement/)
51. [Apache Kafka 4.2.0 Release Announcement | Apache Kafka](https://kafka.apache.org/blog/2026/02/17/apache-kafka-4.2.0-release-announcement/)
52. [Apache Kafka Release Notes](https://axonops.com/docs/data-platforms/kafka/release-notes/)
53. [Redpanda Licenses and Enterprise Features | Redpanda Streaming](https://docs.redpanda.com/current/get-started/licensing/overview/)
54. [Redpanda Licenses and Enterprise Features](https://docs.redpanda.com/streaming/24.3/get-started/licensing/overview.md)
55. [FLIP-20: Integration of SQL and CEP - Apache Flink - Apache Software Foundation](https://cwiki.apache.org/confluence/display/FLINK/FLIP-20:+Integration+of+SQL+and+CEP)
56. [Release notes - RisingWave](https://docs.risingwave.com/changelog/release-notes)
57. [Open Source Streaming Database — RisingWave Apache 2.0 | RisingWave](https://risingwave.com/open-source-streaming-database/)
58. [Releases · risingwavelabs/risingwave](https://github.com/risingwavelabs/risingwave/releases)
59. [RisingWave · Database of Databases](https://dbdb.io/db/risingwave)
60. [Arroyo is joining Cloudflare | Arroyo blog](https://www.arroyo.dev/blog/arroyo-is-joining-cloudflare/)
61. [www.ycombinator.com](https://www.ycombinator.com/companies/arroyo)
62. [The Past and Present of Stream Processing (Part 20): Bytewax — The Burned-Out Data Candle | by Gang Tao | Medium](https://taogang.medium.com/the-past-and-present-of-stream-processing-part-20-bytewax-the-burned-out-data-candle-760223db6b64)
63. [InfluxData InfluxDB releases, versions & end-of-life (EOL)](https://www.versio.io/en/product-release-end-of-life-eol-influxdata-influxdb.html)
64. [Releases · influxdata/influxdb](https://github.com/influxdata/influxdb/releases)
65. [Release Release v3.11.5 · loongarch64-releases/influxdb](https://github.com/loongarch64-releases/influxdb/releases/tag/v3.11.5)
66. [InfluxDB](https://en.wikipedia.org/wiki/InfluxDB)
67. [InfluxData Announces General Availability of InfluxDB 3 Core and InfluxDB 3 Enterprise, Simplifying How Developers Build with Time Series Data - Silicon UK](https://www.silicon.co.uk/press-release/influxdata-announces-general-availability-of-influxdb-3-core-and-influxdb-3-enterprise-simplifying-how-developers-build-with-time-series-data)
68. [Query data | Get started with InfluxDB 3 Core | InfluxDB 3 Core Documentation](https://docs.influxdata.com/influxdb3/core/get-started/query/)
69. [Releases · timescale/timescaledb](https://github.com/timescale/timescaledb/releases)
70. [TimescaleDB](https://en.wikipedia.org/wiki/TimescaleDB)
71. [Software Licensing: Timescale License (TSL) | Tiger Data](https://www.tigerdata.com/legal/licenses)
72. [Tiger Data Documentation | Compare TimescaleDB editions](https://www.tigerdata.com/docs/about/latest/timescaledb-editions)
73. [We finally benchmarked InfluxDB 3 OSS Core (Alpha) | QuestDB](https://questdb.com/blog/influxdb3-core-alpha-benchmarks-and-caveats/)
74. [Release 10.0.0 · questdb/questdb](https://github.com/questdb/questdb/releases/tag/10.0.0)
75. [Documentation changelog | QuestDB](https://questdb.com/docs/changelog/)
76. [Release Release v1.0.0 · GreptimeTeam/greptimedb](https://github.com/GreptimeTeam/greptimedb/releases/tag/v1.0.0)
77. [v1.2.1 | GreptimeDB Documentation](https://docs.greptime.com/release-notes/release-1-2-1/)
78. [GreptimeDB v1.0 GA Is Here | Greptime](https://www.greptime.com/blogs/2026-04-14-greptimedb-v1-ga-release)
79. [TDengine 3.4.1.13 Release Notes | TDengine TSDB Docs](https://docs.tdengine.com/release-history/notes/3.4.1.13/)
80. [Open Source | TDengine](https://tdengine.com/open-source/)
81. [tdengine/tdengine - Docker Image](https://hub.docker.com/r/tdengine/tdengine)
82. [\[ANNOUNCE\] Apache IoTDB 2.0.11 released-Apache Mail Archives](https://lists.apache.org/thread/oo6gwxzswjr6xjl48qgsn6z6qcp3n8qg)
83. [Announcing InfluxDB 3 Enterprise free for at-home use and an update on InfluxDB 3 Core’s 72-hour limitation | InfluxData](https://www.influxdata.com/blog/influxdb3-open-source-public-alpha-jan-27/)
84. [Frangoteam FUXA SCADA/HMI | CISA](https://www.cisa.gov/news-events/ics-advisories/icsa-26-181-02)
85. [Overview · frangoteam/FUXA · GitHub](https://github.com/frangoteam/FUXA/security)
86. [Inductive Automation Releases Ignition 8.3 | Inductive Automation](https://inductiveautomation.com/news/inductive-automation-releases-ignition-83)
87. [Ignition Maker Edition | Ignition User Manual](https://www.docs.inductiveautomation.com/docs/8.3/other-editions/ignition-maker-edition)
88. [Ignition Release Notes for Version 8.3.0 | Inductive Automation](https://inductiveautomation.com/downloads/releasenotes/8.3.0)
89. [Is Ignition 8.3 the most powerful Ignition release yet? | Corso Systems](https://corsosystems.com/posts/ignition-83)
90. [Ignition 8.3 | Inductive Automation](https://inductiveautomation.com/ignition/whatsnew)
91. [Kuzu’s Legacy and the New Wave of Embedded Graph Databases | gdotv](https://gdotv.com/blog/kuzu-legacy-embedded-graph-database-landscape/)
92. [Kuzu — Graph Embedded Database | GDB-Engines](https://gdb-engines.com/db/kuzu/)
93. [Camunda](https://en.wikipedia.org/wiki/Camunda)
94. [docs: add v3.1.0 release notes by cyliu0 · Pull Request #1607 · risingwavelabs/risingwave-docs](https://github.com/risingwavelabs/risingwave-docs/pull/1607)
