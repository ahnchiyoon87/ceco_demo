# 가상 반응기 라인 V1 기술 재선정 기준 보고서 (새 기준 버전, 확인일 2026-09-28)

V1 스택 중 **MQTT 브로커(EMQX)가 유일한 "즉시 교체 필요" 컴포넌트**입니다. EMQX 5.9 이상은 BSL 1.1(비OSI)이고, 마지막 Apache 2.0 라인(5.8.x)은 2026-02-28에 EOL이 되어 더 이상 보안 패치를 받지 않습니다.\[1\]\[2\]\[3\]\[4\] 다음 세 가지는 교체가 아니라 **즉시 버전 조치**가 필요합니다. FUXA는 CISA ICSA-26-181-02(CVE-2026-13207, ≤1.3.1 영향)가 있어 1.3.4로 올려야 합니다.\[5\]\[6\] InfluxDB는 2026-09-15부터 Docker `latest` 태그가 InfluxDB 3 Core를 가리키므로 태그를 고정해야 합니다.\[7\] LiteLLM은 악성 배포본 1.82.7/1.82.8을 배제하고 버전을 고정해야 합니다.\[8\] 나머지 핵심 컴포넌트(EdgeX, Telegraf, Kafka, Flink, PostgreSQL, Prometheus/Alertmanager, Grafana, Neo4j Community, LangGraph)는 OSI 라이선스·비용 0원 기준을 충족하므로 유지합니다. "CEP는 요즘 쓰지 않는다"는 주장은 **사실이 아닙니다.** 독립 CEP 엔진이라는 제품 범주는 쇠퇴했지만, 패턴 탐지 기능 자체는 Flink 2.x의 CEP 라이브러리와 SQL `MATCH_RECOGNIZE`로 흡수되어 2025~2026년에도 유지·제공되고 있습니다.\[9\]

---

## TL;DR

- **라이선스·보안 Gate 결과:** 교체가 필요한 것은 EMQX 하나입니다. 5.9+는 BSL이고, 5.8.x는 2026-02-28 EOL입니다. 커뮤니티 포크(OpenQTT, LibreMQ)는 생긴 지 얼마 안 된 소규모 프로젝트라 신뢰하기 어렵습니다. 대체 1순위는 Mosquitto 2.1.2(2026-02-09)입니다. FUXA ≥1.3.4, Kafka 4.2.1, Flink 2.2.1로 올리고, InfluxDB·LiteLLM·Trivy는 태그/버전을 고정해야 합니다.
- **CEP 주장은 거짓입니다.** Flink 안정판 문서가 `MATCH_RECOGNIZE`를 유지하고 있고, 관리형 Flink 벤더도 CEP SQL을 제공합니다. Confluent는 자사 구현을 "a subset of the full standard"라고 밝히고, Alibaba는 "fully equivalent to the Java API"라고 주장합니다. 다만 ASF Jira FLINK-33428에 따르면 Flink CEP API는 next·notNext·followedBy·followedByAny·notFollowedBy를 모두 지원하는 반면 "Flink SQL only supports next semantics"이고, notFollowedBy는 SQL에서 아직 구현되지 않았습니다. 그래서 "전류↑ 후 N초 내 진동↑"처럼 중간 이벤트를 허용하는 패턴은 DataStream CEP(`followedBy`+`within`)로 구현하거나 SQL 우회 패턴으로 검증해야 합니다.
- **5영업일 회전 계획:** 한 회전에 한 모듈만 바꾸며, L4 패턴탐지를 최우선으로 합니다. 순서는 L4 → MQTT 브로커 → 저장소 → 게이트웨이/백본 → HMI·AI입니다. 판정은 "라이선스·비용 Gate와 안전 Gate 모두 통과 → 비열등 → 트렌드·복잡도·성능 우위" 순서로 합니다. 성능 수치는 측정 전까지 비워 둡니다.

---

## 0. 이 보고서의 출처 등급 규칙과 한계

- **[1차]** 공식 문서, 릴리스 노트, 공식 GitHub LICENSE·README·이슈, 재단 발표(ASF, CNCF, LF Edge), CISA 권고.
- **[2차]** 보안업체 분석(Snyk, Wiz, Datadog, Socket 등), 언론(The Register, The New Stack), 개인 블로그.
- **[벤더]** 해당 제품 회사가 직접 한 주장. 이해관계가 있으므로 판정 근거로는 보조로만 씁니다. 경쟁사 블로그(예: RisingWave가 쓴 Arroyo 평가, QuestDB가 쓴 InfluxDB 평가)도 벤더로 분류합니다.
- **[미검증]** 이번 조사 세션(2026-09-28)에서 공식 LICENSE 파일이나 릴리스 노트로 직접 확인하지 못한 항목입니다. 대부분 조사자의 사전 지식에 근거하며, Claude Code 작업 전에 LICENSE 파일을 열어 확인하는 것을 Gate 절차로 넣었습니다(§6).
- 모든 [1차]·[2차] 항목의 확인일은 **2026-09-28**입니다. 이 보고서는 **성능 수치를 측정하지 않았습니다.** 벤더가 주장하는 처리량·지연 수치는 인용하지 않거나 [벤더]로 표시했습니다.

---

## 1. 요약: V1 컴포넌트 판정표

| 레이어 | V1 컴포넌트 | 라이선스(확인 수준) | 판정 | 핵심 근거 | 조치 |
|---|---|---|---|---|---|
| L1 | 물리모델 시뮬레이터(pymodbus 추정) | pymodbus BSD-3 [미검증] | **유지** | 자체 코드 | OPC UA 병행 노출은 회전 후보(§3-A) |
| L2 | EdgeX Foundry | Apache-2.0 (LF Edge) [1차 재단] | **유지(버전 확인)** | 4.0 "Odesa"가 2025-03 출시된 LTS(지원 2027-03까지), 4.0.2 "Palau" 2026-06 표준 릴리스. BSL 전환된 서드파티(Redis, Consul)를 PostgreSQL·Core-Keeper로 교체 [1차 EdgeX Wiki]\[10\]\[11\]\[12\] | 4.0.x 태그 고정 |
| L2 | **EMQX** | 5.9+ **BSL 1.1**, 5.8.x Apache-2.0 [1차 EMQ]\[2\] | **교체 필요** | 5.9+는 비OSI라 기준 위반이고 제품 임베드 시 유료. 5.8 OSS는 2026-02-28 EOL로 보안 패치가 없음 [1차 EMQ 공지]\[1\]\[3\]\[4\]\[13\] | Mosquitto 2.1.2 / NanoMQ / HiveMQ CE 비교(Day 2) |
| L2 | Telegraf(3개 설정) | MIT [미검증 LICENSE] | **유지** | InfluxData OSS 에이전트 | 이미지 태그 고정 |
| L3 | Apache Kafka | Apache-2.0 (ASF) [1차] | **유지(업그레이드)** | 4.2.0(2026-02-17)에서 share groups가 production-ready. 4.2.1에서 share group 경로의 치명적 교착(KAFKA-20505) 수정 [1차 Kafka]\[14\]\[15\] | 4.2.1 이상으로 고정 |
| L4 | Apache Flink(규칙·CEP·ONNX) | Apache-2.0 (ASF) [1차] | **유지(업그레이드)** | 2.2.0(2025-12-04), 2.2.1(2026-05-15) 버그·취약점 수정 [1차 Flink]\[16\]\[17\] | 2.2.1 고정. CEP 구현 방식은 Day 1에 재검증 |
| L5 | InfluxDB | 2.x MIT로 추정 [미검증] / 3 Core [미검증] | **버전 고정(긴급)** | 2026-09-15부터 Docker `latest`가 InfluxDB 3 Core를 가리킴. 3 Core는 Flux 미지원, 쿼리당 Parquet 파일 432개 한도(기본값 기준 약 72시간) [1차 InfluxData 문서]\[7\]\[18\]\[19\] | `influxdb:2.x.y`로 명시 고정. 대체 후보는 Day 3에 비교 |
| L5 | PostgreSQL | PostgreSQL License [미검증 LICENSE, 널리 알려짐] | **유지** | — | 메이저 버전 고정 |
| L6 | **FUXA** | MIT [미검증 LICENSE] | **버전 고정(긴급 패치)** | CISA ICSA-26-181-02(2026-06-30): ≤1.3.1에서 인증 우회(CVE-2026-13207). ≤1.2.9에서 경로 조작 RCE(CVE-2026-25895, CVSS 9.5, 공개 익스플로잇 있음) [1차 CISA, 2차 Exploit-Intel]\[5\]\[20\] | **1.3.4(2026-08-12)**로 즉시 업그레이드, 외부 노출 금지\[6\]\[21\] |
| L6 | Grafana | AGPL-3.0 [미검증 LICENSE, 널리 알려짐] | **유지(조건부)** | 무수정 사용은 무료. 수정한 뒤 네트워크로 제공하면 소스 공개 의무 | 제품화 시 법무 검토 항목 |
| L6 | Prometheus / Alertmanager | Apache-2.0 (CNCF) [미검증 LICENSE] | **유지** | — | 태그 고정 |
| L6 | Vue 통합 대시보드 + 백엔드 | 자체 코드(Vue MIT) | **유지** | — | 안전 Gate 테스트 대상 |
| L7 | Neo4j Community | GPL-3.0 [미검증 LICENSE] | **유지(조건부)** | Enterprise 기능(클러스터, 세분화 RBAC, 온라인 백업 등)은 유료 [미검증] | 12태그 규모에서는 문제없음. 제품화 시 대안 비교 |
| L8 | LiteLLM | MIT 코어 + `enterprise/` 폴더는 별도 상용 [미검증 LICENSE] | **버전 고정(긴급)** | 2026-03-24 PyPI 공급망 공격: 1.82.7, 1.82.8이 악성 [1차 LiteLLM 블로그, 2차 Datadog·Snyk]\[8\]\[22\] | 1.82.7/1.82.8 배제, 해시 고정. enterprise 기능 미사용 확인 |
| L9 | LangGraph | MIT [미검증 LICENSE] | **유지** | — | 버전 고정 |
| L9 | Pilot(자체) | 자체 코드 | **유지** | — | 안전 Gate 테스트 대상 |

**V1 컴포넌트 중 현재 최신 버전이 기준을 위반하는 것:** EMQX(최신 라인이 BSL이며, EMQX 문서상 6.x는 6.3에서 끝나고 7.0으로 이어짐. 모두 BSL).\[2\] **최신을 따라가면 동작이 깨지는 것:** InfluxDB(`latest`가 3 Core로 바뀜). **Redpanda 브로커**는 V1에 없지만 후보로 올라와도 BSL이므로 제외합니다.

---

## 2. CEP 주장 검증 결론

**주장:** "CEP는 요즘 쓰지 않는 기술이다."

**판정:** 일반화된 형태로는 **거짓**입니다. 다만 부분적으로 맞는 요소가 있습니다.

| 관점 | 근거 | 등급 |
|---|---|---|
| Flink가 CEP를 계속 유지하는가 | Flink 안정판 문서의 "Pattern Recognition"이 `MATCH_RECOGNIZE`(ISO/IEC TR 19075-5:2016 행 패턴 인식)와 비표준 확장 `WITHIN` 절을 문서화함. `WITHIN`은 상태 정리를 위해 권장된다고 명시\[9\] | [1차] nightlies.apache.org/flink/flink-docs-stable/docs/dev/table/sql/queries/match_recognize/ |
| Flink 릴리스가 활발한가 | 2.2.0(2025-12-04, 기여자 73명, FLIP 9개, 이슈 220+ 해결), 2.2.1(2026-05-15, 44건 수정), 2.1.3(2026-06-14), 1.20 다섯 번째 버그픽스(2026-06-08), Kubernetes Operator 1.15.0(2026-05-26)\[16\]\[17\]\[23\]\[24\] | [1차] flink.apache.org |
| 산업계 관리형 서비스가 CEP를 제공하는가 | Confluent의 "SQL Pattern Recognition Queries in Confluent Cloud for Apache Flink" 문서가 `MATCH_RECOGNIZE`를 제공하면서 "The Flink implementation of the MATCH_RECOGNIZE clause is a subset of the full standard"라고 밝히고, 상태 보존 시간 대신 `WITHIN` 사용을 권함. Alibaba Cloud의 "CEP statements" 문서는 Realtime Compute for Apache Flink가 "extends this capability to support the expression capability that is fully equivalent to the Java API"라고 주장(vvr-6.0.2-flink-1.15 이상 필요) | [벤더] docs.confluent.io, alibabacloud.com |
| Flink SQL CEP의 한계 | FLINK-33428: Flink CEP API는 next, notNext, followedBy, followedByAny, notFollowedBy를 지원하지만 "Flink SQL only supports next semantics"이며, notFollowedBy는 "not currently implemented" | [1차] issues.apache.org/jira/browse/FLINK-33428 (해결 여부 [미검증]) |
| 신규 CEP 프로젝트 등장 | 2026년에도 Rust 기반 CEP/패턴 DSL(Varpulis)이 Arroyo 비교 문서를 내는 등 신규 프로젝트가 나오고 있음\[25\] | [벤더] varpulis-cep.com |
| 독립 CEP 엔진 범주 | Esper(GPL v2), WSO2 Siddhi(Apache-2.0) 같은 독립 CEP 엔진은 신규 채택 신호가 약함. 스트림 처리 엔진과 스트리밍 SQL(RisingWave, Proton 등)이 윈도우·패턴 기능을 흡수하는 추세 | [미검증] 최근 커밋·릴리스 빈도는 미확인 |

**해석:** 옳은 표현은 "**독립 CEP 제품은 비주류가 되었고, CEP 기능은 스트림 처리기 안의 표준 기능이 되었다**"입니다. V1의 "교반기 전류 상승 후 N초 내 진동 상승" 규칙은 교과서적인 CEP 사용 사례입니다. 이것을 폐기할 이유는 없고, **어떤 구현이 가장 단순하고 검증 가능한가**를 비교하면 됩니다.

**구현 선택지 비교(Day 1에서 검증):**

| 방식 | 패턴 표현 | 시간 제약 | 순서 바뀐·늦은 이벤트 | 재시작 복구 | 주의점 |
|---|---|---|---|---|---|
| Flink DataStream CEP | `begin("I").where(전류↑).followedBy("V").where(진동↑).within(N초)` | `within` | 이벤트타임 + 워터마크. 늦은 이벤트는 side output | 체크포인트/세이브포인트 | Java/Scala 코드 필요. PyFlink의 CEP 지원 범위 [미검증] |
| Flink SQL `MATCH_RECOGNIZE` | `PATTERN (I X*? V) WITHIN INTERVAL 'N' SECOND` (X는 아무 행이나 허용하는 filler 변수, reluctant 수량자) | `WITHIN` | `ORDER BY` 이벤트타임 오름차순 필수\[9\] | 체크포인트 | strict contiguity가 기본이라 filler 우회가 필요. 동작은 PoC로 검증 필요 [미검증]\[26\] |
| Python asyncio 상태 머신 | 태그별 상태 `{IDLE, I_RISEN(t0)}`, `t−t0 ≤ N`이면 발화 | 직접 구현 | 직접 버퍼링(허용 지연 L초) | 상태를 Kafka compacted topic이나 PostgreSQL에 저장해야 함 | 코드는 가장 짧지만 정확성(중복·재처리)을 직접 책임짐 |
| RisingWave / Proton 스트리밍 SQL | 윈도우 조인이나 LAG 기반 조건 | 윈도우 | 워터마크 지원 [벤더] | 내장 상태 | 패턴 표현력은 CEP보다 제한적. 라이선스 키 기능 회피 확인 필요 |

---

## 3. 레이어별 후보 상세표

> 표기: **허용** = OSI 라이선스이고 필요한 기능이 무료. **조건부** = OSI이지만 copyleft(AGPL/GPL)이거나 유료 기능 경계가 있음. **탈락** = 기준 위반.
> "PoC 규모"는 조사자의 추정치이며 측정값이 아닙니다.

### A. L1 설비·시뮬레이터 연결

| 후보 | 라이선스 | 최신 버전 | 트렌드 | 보안 | V1 매핑 | 12태그·Compose 적합성 | Docker 이미지 | 최소 PoC | 측정 지표 | 판정 |
|---|---|---|---|---|---|---|---|---|---|---|
| pymodbus | BSD-3 [미검증] | [미검증] | 주류(Python Modbus 사실상 표준) [미검증] | [미검증] | 현 시뮬레이터 | 매우 적합 | 공식 이미지 없음(자체 빌드) | 현행 유지 | 폴링 주기 준수율 | **허용·유지** |
| asyncua (opcua-asyncio) | LGPL-3.0 [미검증] | [미검증] | 상승(Python OPC UA 서버/클라이언트) | [미검증] | 시뮬레이터에 OPC UA 병행 노출 | 적합 | 없음 | 서버 1개에 노드 12개, Python 약 100~200줄 | 구독 지연, 노드 브라우징 | **허용(후보)** |
| open62541 | MPL-2.0 [미검증] | [미검증] | 주류(C, 임베디드) | [미검증] | 동일 | 적합하나 C 빌드 필요 | [미검증] | 몇 시간으로는 부담 | — | 허용(우선순위 낮음) |
| Eclipse Milo | EPL-2.0 [미검증] | [미검증] | 주류(Java) | [미검증] | 동일 | 적합 | [미검증] | Java 서버 | — | 허용(우선순위 낮음) |

**OPC UA 병행 노출 트렌드:** Neuron OSS는 OPC UA를 상용 NeuronEX에만 넣었습니다 [1차 GitHub emqx/neuron README].\[27\] 즉 OPC UA가 "상용 차별화 포인트"로 쓰일 만큼 수요가 있다는 간접 신호입니다. Modbus를 유지한 채 asyncua로 **같은 12태그를 OPC UA로도 노출**하면, 게이트웨이 비교(Telegraf opcua 입력, Node-RED)를 공정하게 할 수 있습니다.

### B. L1~L2 게이트웨이·수집

| 후보 | 라이선스 | 유료/비OSI 경계 | 최신 버전·날짜 | 트렌드(독립 근거) | V1 대체/통합 | 대체 시 잃는 기능 | Docker 이미지 | 최소 PoC | 판정 |
|---|---|---|---|---|---|---|---|---|---|
| **EdgeX Foundry 4.0.x** | Apache-2.0 | 없음. IOTech Edge Central은 별도 상용 제품 [벤더]\[12\] | 4.0 Odesa(2025-03, LTS 2027-03까지), 4.0.2 Palau(2026-06) [1차]\[10\]\[11\] | 정체~주류: LF Edge 재단 소속, Schneider·Eaton·Danfoss·Intel이 TSC 참여 [2차 ARC]\[28\] | 현행 | — | edgexfoundry/* [미검증 정확한 이름] | 현행 | **허용·유지** |
| Neuron OSS | LGPL-3.0 (코어, 대시보드, Modbus TCP, MQTT, eKuiper 플러그인만)\[29\] | OPC UA, S7, EtherNet/IP, BACnet, IEC-104/61850 등은 상용 라이선스 필요. 체험판 제한 있음 [1차 Neuron 문서]\[27\]\[30\]\[31\] | [미검증] | 정체(EMQ 상용 NeuronEX 중심) | EdgeX device-modbus + MQTT export | EdgeX 서비스 생태계 | emqx/neuron [1차 README] | 웹 UI로 Modbus 12태그와 MQTT 북향 설정, 1~2시간 | **허용(Modbus/MQTT 한정)** |
| eKuiper | Apache-2.0 (LF Edge) [미검증] | [미검증] | [미검증] | 정체~상승 | 엣지 규칙(L4 일부) | Flink 체크포인트급 상태 관리 | lfedge/ekuiper [미검증] | SQL 규칙 1개 | 허용(후보) |
| Redpanda Connect(Benthos) | Community/Certified 커넥터는 Apache-2.0. 엔터프라이즈 커넥터는 RCL(비OSI) [1차 Redpanda]\[32\]\[33\] | 엔터프라이즈 커넥터(CDC 입력, Snowflake, Iceberg 출력, Salesforce, splunk 등)는 라이선스 키 없으면 차단\[32\]\[34\]\[35\] | [미검증] | 상승 | Telegraf(MQTT→Kafka, Kafka→InfluxDB) | Telegraf 입력 플러그인 다양성 | redpandadata/connect [미검증] | YAML 1개 | **조건부 허용**: 사용할 mqtt/kafka/sql(postgres)/modbus 컴포넌트가 Apache 등급인지 LICENSE 헤더로 확인 [미검증: modbus 입력 존재 여부] |
| benthos-umh | Apache-2.0 [미검증] | UMH 상용 제품과 경계 [미검증] | [미검증] | 상승(UNS 커뮤니티) | Modbus/OPC UA → MQTT/Kafka | — | [미검증] | YAML 1개 | 후보(LICENSE 확인 필수) |
| Node-RED + node-red-contrib-modbus | Node-RED Apache-2.0 (OpenJS 재단) [미검증]. 모듈 라이선스 [미검증] | FlowFuse 상용 플랫폼과 별개 | [미검증] | 주류 | EdgeX, Telegraf 일부 | 선언적 설정, 재현성 | nodered/node-red [미검증] | 플로우 1개, 30분 | 허용(후보) |
| Apache PLC4X | Apache-2.0 (ASF) [미검증] | 없음 | [미검증] | 정체 | 드라이버 라이브러리 | — | — | 코드 필요 | 허용(우선순위 낮음) |
| Apache StreamPipes | Apache-2.0 (ASF) [미검증] | 없음 | [미검증] | 정체 | L2~L4 통합 플랫폼 | 모듈 교체 단위가 너무 큼 | [미검증] | 무거움 | 허용(회전 부적합) |
| Eclipse Tahu | EPL-2.0 [미검증] | 없음 | [미검증] | Sparkplug B 참조 구현 | MQTT 페이로드 표준화 | — | — | 라이브러리 | 허용(UNS 회전용) |
| Telegraf(modbus/opcua 입력) | MIT [미검증] | 없음 | [미검증] | 주류 | EdgeX 전체 대체 가능 | EdgeX 명령(쓰기) API | telegraf [미검증] | inputs.modbus 설정 30줄 | 허용(후보) |
| Fluent Bit / Vector | Apache-2.0 / MPL-2.0 [미검증] | Vector는 Datadog 소유 | [미검증] | 로그 중심 | 부적합(산업 프로토콜 없음) | — | — | — | 허용이나 **범위 외** |
| 직접 pymodbus 서비스 | BSD-3 [미검증] | 없음 | — | — | EdgeX + Telegraf(1) | 설정 기반 관리 | 자체 | 150줄 | 허용(기준선) |

**UNS·Sparkplug B:** ISA-95 계층 토픽(예: `site/area/line/cell/R-101/TT-101`)은 장비 중심 네이밍을 표준화한다는 점에서 V2 온톨로지 개선 과제와 직결됩니다. 오픈소스 구현으로는 Eclipse Tahu(Sparkplug 참조 구현)와 benthos-umh가 있습니다. 채택 신호(재단, 커밋 수)는 이번 세션에서 확인하지 못했습니다 [미검증].

### C. MQTT 브로커

| 후보 | 라이선스 | 무료 범위 / 제한 | 최신 버전·날짜 | 보안·유지보수 | 룰엔진 / Kafka 브리지 / 대시보드 / Prometheus | 판정 |
|---|---|---|---|---|---|---|
| **EMQX 5.9+ (6.x, 7.x)** | BSL 1.1 [1차] | 단일 노드 프로덕션은 무료. 단 "as-a-service로 제공하거나 제3자에게 판매하는 제품에 임베드"하면 불가. 2노드 이상 클러스터는 라이선스 파일 필요 [1차 EMQX FAQ, GitHub Discussion #15163]\[2\]\[4\]\[13\] | 6.x → 7.0 [1차 EOL 문서]\[2\] | 활발 | 있음 | **탈락**: 비OSI이며 제품화 시 유료 |
| **EMQX 5.8.x (Apache)** | Apache-2.0 [1차]\[36\]\[37\] | OSS판은 Kafka 등 데이터 브리지가 Enterprise 전용이었음 [벤더 EMQ 비교 블로그]\[37\] | 마지막 5.8.9 [2차 OpenQTT 이슈]\[3\] | **2026-02-28 EOL**. EMQ가 "unpatched vulnerabilities" 위험을 직접 경고함 [1차 EMQ 공지]\[1\]\[3\] | SQL 룰엔진, 대시보드 있음 | **탈락(보안)**: 패치가 끊긴 버전 고정은 금지 |
| OpenQTT(포크) | Apache-2.0 | BSL.txt가 붙은 59개 앱 디렉터리를 제거한 5.8.9 커뮤니티 빌드\[3\] | v0.1.0/1.0.0 (2026-09-05). 스타 3, 포크 0 [2차 GitHub]\[3\]\[38\] | 갓 시작함. 기본 Erlang 쿠키 문제를 직접 수정하는 수준\[38\] | 5.8.9와 동일 | **탈락(성숙도)**: 관찰 대상 |
| LibreMQ(포크) | Apache-2.0 | 5.8.x 브랜치 포크, 클러스터 무제한\[39\] | [미검증] | 개인 유지 | 동일 | **탈락(성숙도)**: 관찰 대상 |
| **Mosquitto 2.1.x** | EPL-2.0/EDL-1.0 [미검증 LICENSE 재확인]\[40\] | 전부 무료 | **2.1.2 (2026-02-09)**. 2.1.0(2026-01-29)에서 내장 WebSocket, PROXY protocol 지원. acl_file·password_file·per_listener_settings는 폐기 예고(3.0에서 제거) [1차 mosquitto.org]\[41\]\[42\] | Eclipse 재단 | 룰엔진·Kafka 브리지 없음(Telegraf가 담당). Prometheus는 외부 익스포터 필요 [미검증] | **허용·1순위** |
| NanoMQ | MIT [미검증] | EMQ 프로젝트 | [미검증] | [미검증] | 경량 룰엔진, 브리지 [미검증] | 허용(후보 2) |
| HiveMQ CE | Apache-2.0 [미검증 LICENSE]\[43\] | 클러스터링, Control Center, Kafka 확장 등은 Enterprise [미검증] | **2026.5 (2026-05-27)** [1차 GitHub releases]\[44\] | 활발 | 확장 SDK | 허용(후보 3) |
| VerneMQ | 소스 Apache-2.0 | **공식 바이너리·Docker 이미지는 VerneMQ EULA**가 적용되어 상용 사용 시 연간 구독 필요. 소스에서 직접 빌드하면 무료 [1차 vernemq.com]\[45\]\[46\] | 2.2.0 [미검증 날짜] | 소규모 유지 | 플러그인 | **조건부**: 공식 이미지 사용 금지, 자체 빌드만 허용. 5일 회전에는 부적합 |
| RabbitMQ MQTT 플러그인 | MPL-2.0 [미검증] | [미검증] | [미검증] | 주류(범용 MQ) | 큐 기능 | 허용(범위 외) |
| ActiveMQ Artemis | Apache-2.0 (ASF) [미검증] | 없음 | [미검증] | 정체 | — | 허용(우선순위 낮음) |
| BifroMQ | Apache-2.0, ASF 인큐베이터 [미검증] | [미검증] | [미검증] | 상승? [미검증] | — | 관찰 |
| Mochi-MQTT / rumqttd | MIT / Apache-2.0 [미검증] | 임베디드용 | [미검증] | 소규모 | 없음 | 허용(우선순위 낮음) |
| NATS 내장 MQTT | Apache-2.0 (CNCF) [1차]\[47\] | — | [미검증] | §3-D 참조 | JetStream 연계 | 허용(Kafka-less 아키텍처에서) |

### D. 이벤트 백본

| 후보 | 라이선스 | 핵심 사실 | replay·다중 소비자 | 판정 |
|---|---|---|---|---|
| **Apache Kafka 4.2.x** | Apache-2.0 | Kafka 4.0.0 공지(2025-03-18)가 "the first major release to operate entirely without Apache ZooKeeper"라고 명시했고, 같은 릴리스에서 KIP-932 Queues for Kafka가 Early Access로 들어감 [1차]. 4.2.0(2026-02-17)에서 share groups(KIP-932) production-ready, Streams DLQ 지원. 4.2.1에서 KAFKA-20505(share group 교착) 수정 [1차] | 오프셋 기반 재처리 완비 | **허용·유지** |
| Redpanda | 브로커 BSL. Enterprise는 RCL, 30일 체험 [1차 Redpanda 문서]\[48\]\[49\] | — | — | **탈락** |
| NATS JetStream | Apache-2.0 | 2025-05-01 CNCF·Synadia 합의로 상표가 LF에 이전되고 저장소는 CNCF가 보유, Apache-2.0 유지. Synadia는 "BSL 포크를 하지 않기로 결정" [1차 CNCF, Synadia]\[47\]\[50\] | 스트림 재생, 소비자 다수 | **허용(후보)**: 라이선스 리스크 해소 확인 |
| Apache Pulsar | Apache-2.0 [미검증] | 구성요소가 많음(BookKeeper 등) | 있음 | 허용(12태그에 과함) |
| Apache RocketMQ | Apache-2.0 [미검증] | — | 있음 | 허용(우선순위 낮음) |
| AutoMQ | [미검증] Apache-2.0 전환설 있음 | LICENSE 확인 전에는 사용 금지 | Kafka 호환 | **보류([미검증])** |
| Valkey Streams | BSD-3 [미검증] (Redis BSL 전환 이후 LF 포크) | EdgeX 4.0도 Redis 대신 Valkey 사용 가능성을 언급 [1차 EdgeX]\[51\]\[52\] | 소비자 그룹, XRANGE 재생 | 허용(경량 후보) |
| pgmq (PostgreSQL 큐) | PostgreSQL License [미검증] | — | 큐 의미론. 재생은 제한적 | 허용(업무 큐용) |
| MQTT 단독(Kafka-less) | — | 브로커 보존(retained)과 영속 세션만으로는 "임의 시점부터 재처리"가 불가 | **불충족** | V1 요구(여러 소비자의 독립 소비와 재처리)를 만족하려면 NATS JetStream이나 Kafka가 필요 |

### E. 스트림 처리·이상탐지

| 후보 | 라이선스 | 유료/비OSI 경계 | 최신·상태 | 트렌드 | CEP(순서 패턴) | 판정 |
|---|---|---|---|---|---|---|
| **Flink 2.2.x** (DataStream CEP, SQL) | Apache-2.0 | 없음 | 2.2.1 (2026-05-15). ML_PREDICT, VECTOR_SEARCH(2.2) [1차]\[16\]\[17\] | 주류 | 완전 지원(DataStream), SQL은 strict contiguity | **허용·유지** |
| Kafka Streams | Apache-2.0 | 없음 | 4.2에서 DLQ, 서버 측 리밸런스 GA [1차]\[14\] | 주류 | 직접 구현(Processor API) | 허용(후보) |
| RisingWave | 코어 Apache-2.0\[53\] | v2.0부터 **라이선스 키로 여는 Premium 기능**이 같은 바이너리에 포함. 4 RWU 이하 체험 제공 [1차 RisingWave 문서]\[53\]\[54\] | [미검증] | 상승 | SQL 윈도우 | **조건부**: Premium 기능 미사용을 Gate에서 확인(쓰면 에러 발생) |
| Materialize | **BSL 1.1**. Self-Managed Community도 라이선스 키 필요(24GiB 메모리·48GiB 디스크 제한) [1차]\[55\]\[56\]\[57\] | — | — | 상승 | — | **탈락** |
| Timeplus Proton | Apache-2.0 [1차 문서]\[58\] | Timeplus Enterprise는 상용 | [미검증] | 상승 | 스트리밍 SQL | 허용(후보) |
| Arroyo | Apache-2.0/MIT [2차]\[25\]\[59\] | Cloudflare Pipelines는 상용 서비스 | 2025-04 Cloudflare 인수. 엔진은 계속 OSS·셀프호스팅 가능 [1차 Arroyo 블로그]. "2025 하반기 릴리스 속도 둔화" [벤더 RisingWave]\[25\]\[59\]\[60\] | 정체 우려 | SQL | 허용이나 **트렌드 감점** |
| Quix Streams | Apache-2.0 [1차 LICENSE]\[61\] | Quix Cloud는 상용 | [미검증] | 상승(Python) | 직접 구현 | 허용(Python 후보) |
| Bytewax | Apache-2.0 [미검증] | — | 유지보수 상태 [미검증] | 쇠퇴 의심 | — | 보류 |
| Faust(faust-streaming 포크) | BSD-3 [미검증] | — | [미검증] | 정체 | — | 우선순위 낮음 |
| eKuiper | Apache-2.0 [미검증] | — | [미검증] | — | 제한적 | 허용(엣지) |
| Apache Beam | Apache-2.0 [미검증] | — | — | 주류(배치/스트림 추상화) | — | 12태그에 과함 |
| Esper | GPL-2.0 [미검증] | 상용 라이선스 별도 | [미검증] | 쇠퇴 | 완전 | 조건부(copyleft). 회전 제외 |
| Siddhi | Apache-2.0 [미검증] | — | 활동 저조 [미검증] | 쇠퇴 | 완전 | 제외 권고 |
| Python asyncio 상태 머신 | 자체 | — | — | — | 직접 | **허용(기준선)** |

**ML 구성요소**

| 후보 | 라이선스 | 비고 | 판정 |
|---|---|---|---|
| ONNX Runtime | MIT [미검증] | 현 Autoencoder 추론에 사용 중 | 허용·유지 |
| River (온라인 학습) | BSD-3 [미검증] | 스트리밍 Z-Score, HalfSpaceTrees 등 | 허용(후보) |
| PyOD | BSD-2 [미검증] | 배치 이상탐지 | 허용 |
| scikit-learn | BSD-3 [미검증] | — | 허용 |
| TimesFM | 코드 Apache-2.0 [미검증]. 가중치 라이선스 별도 확인 필요 | 예측 기반 이상탐지(잔차) | 조건부 |
| Chronos | Apache-2.0 [미검증] | 동일 | 조건부 |
| Moirai | 코드(uni2ts)는 Apache-2.0. Hugging Face 모델 카드(Salesforce/moirai-1.0-R-small·base·large, moirai-2.0-R-small)는 "license: cc-by-nc-4.0"(비상업)이고, Moirai 2.0 카드는 "This release is for research purposes only"라고 명시 [1차] | 비상업 가중치는 기준 위반 | **가중치별 확인 전 탈락** |
| MOMENT | [미검증] | — | 보류 |

**공통 구현 비교 포인트:**
- **Z-Score 윈도우:** 슬라이딩 N초 평균과 표준편차. 순서가 바뀐 이벤트는 워터마크와 허용 지연으로 처리합니다.
- **재시작 복구:** Flink은 체크포인트, Kafka Streams는 changelog topic, Python은 외부 상태 저장소를 씁니다.
- **평가 방법:** 같은 주입 시나리오의 탐지율, 오탐, 탐지 지연을 비교합니다(§6).

### F. 시계열·저장

| 후보 | 라이선스 | 무료 / 유료 경계 | 핵심 제약 | 판정 |
|---|---|---|---|---|
| InfluxDB 2.x | MIT [미검증] | — | 유지보수·EOL 일정 [미검증]. Docker `latest` 전환 주의 [1차]\[7\] | **현행 유지(태그 고정)**, 중기 대체 검토 |
| InfluxDB 3 Core | MIT/Apache 듀얼 [미검증] | Enterprise는 상용. "at-home 비상업 무료"판은 비상업 전용이라 **탈락** [1차 InfluxData 블로그]\[62\]\[63\] | Flux 미지원. `--query-file-limit` 기본 432(10분 파일 기준 약 72시간). 늦게 도착한 쓰기가 있으면 그보다 짧아짐. 한도를 올릴 수는 있으나 성능 저하 경고 [1차 문서, GitHub PR #25890, 2차 Layerbase]\[7\]\[18\]\[19\] | 조건부(단기 창 조회 전용) |
| TimescaleDB **Apache 2 Edition** | Apache-2.0 [1차 Tiger Data 문서]\[64\] | create_hypertable, show_chunks, drop_chunks(수동 보존), time_bucket, first/last, histogram은 사용 가능\[64\] | **TSL 전용(사용 불가):** 하이퍼코어/컬럼스토어 압축, 연속 집계, add_retention_policy, 사용자 잡 스케줄러(add_job 등), reorder/move_chunk, SkipScan, time_bucket_gapfill·locf·interpolate·percentile_agg 등 하이퍼펑션 [1차]\[64\] | **허용(후보)**: `SHOW timescaledb.license`가 `apache`인지 Gate에서 확인\[64\] |
| TimescaleDB Community | **TSL(Tiger Data License)**\[65\] | "서비스로 판매 불가"\[65\] | — | **탈락** |
| 순수 PostgreSQL(선언적 파티셔닝 + BRIN + pg_partman) | PostgreSQL License / pg_partman PostgreSQL License [미검증] | 전부 무료 | 연속 집계는 materialized view와 cron으로 대체 | **허용(후보 1)**: "PostgreSQL 단일화" 추세와 부합 |
| QuestDB | Apache-2.0 [미검증 LICENSE] | Enterprise 분리. QuestDB Cloud 셀프서브 종료 [2차 Layerbase]\[18\] | 10.0(2026-08) 바이너리 프로토콜 QWP [벤더]\[66\] | 허용(후보). FUXA가 QuestDB를 지원(1.3.0) [1차 FUXA]\[6\] |
| GreptimeDB | Apache-2.0 [미검증] | Enterprise 분리 | — | 허용(관찰) |
| Apache IoTDB | Apache-2.0 [미검증] | — | — | 허용(우선순위 낮음) |
| TDengine OSS | AGPL-3.0 [미검증] | 클러스터 등 일부 기능은 Enterprise [미검증] | copyleft | 조건부 |
| ClickHouse | Apache-2.0 [미검증] | — | 12태그에 과함 | 허용(우선순위 낮음) |
| VictoriaMetrics OSS | Apache-2.0 [미검증] | Enterprise 분리(다운샘플링 등) [미검증] | 운영 지표용 | 허용(관측용) |
| CrateDB | Apache-2.0 [미검증] | — | — | 우선순위 낮음 |

### G. HMI/SCADA

| 후보 | 라이선스 | 최신 / 보안 | V1 매핑 | 판정 |
|---|---|---|---|---|
| **FUXA** | MIT [미검증 LICENSE] | **1.3.4 (2026-08-12, npm 최신)**. 2026년 CVE 다수: CVE-2026-25895(≤1.2.9 RCE, 1.2.10에서 수정), CVE-2026-25751·25893·25752(≤1.2.9), 스케줄러 인가 우회(1.2.8~1.2.10), Node-RED 플러그인 인증 우회(1.2.11에서 수정), **CVE-2026-13207(≤1.3.1, CISA ICSA-26-181-02)**. 1.3.0에서 하드코딩 JWT 비밀키 제거 [1차 CISA, GitHub releases, 2차 Vulners]\[5\]\[6\]\[20\]\[21\]\[67\]\[68\] | 현행 | **허용·1.3.4 고정**. 최소 안전 버전은 CISA 기준 1.3.2 이상이며, 정확한 수정 버전 문구는 [미검증] |
| Node-RED Dashboard 2.0 (FlowFuse) | Apache-2.0 [미검증] | [미검증] | FUXA 대체 | 허용(후보) |
| Rapid SCADA | Apache-2.0 [미검증] | [미검증] | FUXA 대체(.NET) | 후보(LICENSE 확인) |
| SCADA-LTS | GPL-2.0 계열 [미검증] | [미검증] | FUXA 대체(Java) | 조건부 |
| OpenSCADA | GPL-2.0 [미검증] | [미검증] | — | 우선순위 낮음 |
| Eclipse 4diac | EPL-2.0 [미검증] | IEC 61499 런타임·IDE | 제어 로직 표준화 실험 | V3 후보(범위 외) |
| 커스텀 Vue + MQTT over WebSocket | 자체 + MIT 라이브러리 | Mosquitto 2.1 내장 WebSocket [1차]\[42\] | Vue 대시보드 확장, FUXA 알람 표시 대체 | **허용(후보)** |
| Ignition | 상용. Maker Edition은 개인·비상업 전용 [미검증 약관] | — | — | **탈락** (상용/비상업 기준) |

**ISA-101 / ISA-18.2:** 두 표준 모두 ISA 유료 문서입니다 [미검증 가격]. 오픈소스 "구현체"로 확인된 사례는 없습니다 [미검증]. 따라서 원칙(회색조 배경, 이상 시에만 색 사용, 알람 우선순위·셸빙·확인 상태 머신)을 요구사항으로 옮겨 Vue/FUXA에서 구현하고, 알람 KPI(시간당 알람 수, 채터링, stale)로 평가하는 방식을 권장합니다.

### H. 관측

| 후보 | 라이선스 | 판정 |
|---|---|---|
| Prometheus / Alertmanager | Apache-2.0 [미검증] | 유지 |
| Grafana OSS | AGPL-3.0 [미검증] | 유지(조건부). Enterprise 플러그인은 미사용 |
| Grafana Alloy | Apache-2.0 [미검증] | 후보(수집기 통합) |
| OpenTelemetry Collector | Apache-2.0 (CNCF) [미검증] | 후보 |
| Loki | AGPL-3.0 [미검증] | 조건부(로그 필요 시) |
| VictoriaMetrics OSS | Apache-2.0 [미검증] | 후보(Prometheus 저장 대체) |
| cAdvisor / node_exporter | Apache-2.0 [미검증] | 허용 |
| Kafka 익스포터 / Flink Prometheus 리포터 | Apache-2.0 [미검증] / Flink 내장 | 허용. Flink 2.2.1에서 Prometheus 리포터 설정 버그(FLINK-38704) 수정 [1차]\[16\] |
| EMQX 지표 | 브로커 교체 시 사라짐 | Mosquitto는 `$SYS` 토픽과 익스포터로 대체 [미검증] |

### I. 배포·공급망

| 항목 | 사실 | 권고 |
|---|---|---|
| Docker Compose | 12태그 단일 머신 요구에 가장 단순 | **유지** |
| Podman | Apache-2.0 [미검증] | 선택 사항 |
| k3s | Apache-2.0 [미검증] | 5일 회전에는 과함. V3 이후 검토 |
| Trivy 사건 | 2026-03-19 TeamPCP가 trivy-action 태그 76개 중 75개를 강제 푸시하고, trivy v0.69.4 바이너리와 Docker 태그 0.69.4/0.69.5/0.69.6에 탈취 코드를 심음. 발단은 2026-02-28 `pull_request_target` 워크플로 악용. 안전 버전은 **trivy v0.69.3, trivy-action v0.35.0, setup-trivy v0.2.6** [2차 Snyk, Wiz, Socket, Legit]\[69\]\[70\]\[71\]\[72\] | 액션은 커밋 SHA로 고정. 스캐너 이미지도 다이제스트로 고정\[73\]\[74\] |
| LiteLLM 사건 | Trivy에서 탈취한 CI 자격증명으로 PyPI 게시 권한을 얻어 1.82.7, 1.82.8 배포(2026-03-24 10:39 UTC 게시, 13:38 UTC 격리) [2차 NHS England, Snyk]. 공식 LiteLLM Proxy Docker 이미지는 영향 없음 [1차 LiteLLM]\[8\]\[75\]\[76\] | 해시 고정(`pip --require-hashes`), SBOM 생성 |
| SBOM | Syft, Trivy, Grype(Apache-2.0) [미검증] | 회전마다 SBOM과 라이선스 리포트를 산출물로 남김 |

### J. AI 레이어

| 후보 | 라이선스 | 판정·근거 |
|---|---|---|
| Neo4j Community | GPL-3.0 [미검증] | 유지(조건부) |
| Memgraph Community | **BSL 1.1** + Additional Use Grant(내부 업무 목적만. 제3자 임베드·배포 금지) [1차 LICENSE 인덱스 발췌]\[77\] | **탈락** |
| FalkorDB | **SSPLv1** [1차 docs.falkordb.com]\[78\] | **탈락** |
| Apache AGE | Apache-2.0 [미검증] | 허용(PostgreSQL 단일화 후보) |
| pgvector | PostgreSQL License [미검증] | 허용 |
| Kuzu | MIT, **2025-10경 아카이브** [1차 README]\[79\]\[80\] | 신규 채택 금지 |
| LadybugDB(Kuzu 포크) | MIT [1차 문서]\[81\] | 관찰(extensions 저장소에 LICENSE 없음, 이슈 #85)\[82\] |
| RyuGraph(Kuzu 포크) | MIT, CLA 필요 [1차]\[83\]\[84\] | 관찰 |
| Microsoft GraphRAG / LightRAG | MIT / MIT [미검증] | 허용(후보) |
| LiteLLM | MIT 코어 [미검증] | 유지(고정). `enterprise/` 기능 미사용 |
| 직접 SDK(google-genai 등) | Apache-2.0 [미검증] | 후보(게이트웨이 제거) |
| LangGraph | MIT [미검증] | 유지 |
| Temporal | MIT [미검증] | 후보(Pilot 내구 실행) |
| DBOS Transact | MIT [미검증] | 후보(PostgreSQL 기반 내구 실행, 경량) |
| Restate | 서버 **BSL 1.1**(SDK는 MIT) [1차 restate.dev FAQ]\[85\] | **탈락(서버)** |
| Camunda 8 | Camunda License [미검증 세부] | **탈락** |
| Flowable | Apache-2.0 [1차] | 허용(BPMN 실행 필요 시) |
| bpmn-js | "bpmn.io License" = MIT + **워터마크 삭제·가림 금지 조항** [1차 LICENSE]\[86\] | **조건부**: OSI 승인 MIT와 동일하지 않음. 표시 전용이면 워터마크를 유지한 채 쓰거나, 자체 SVG로 대체 |
| MCP 공식 SDK | MIT [미검증] | 허용 |

### K. 온톨로지 표준

| 표준 | 무료 사용 | 구현체 | 활용 |
|---|---|---|---|
| ISA-95 / B2MML | ISA-95 본문은 유료 [미검증]. B2MML 스키마는 MESA 무료 배포 [미검증] | — | 설비 계층(Enterprise/Site/Area/WorkCenter/WorkUnit) → UNS 토픽 |
| OPC UA 정보모델 | 사양은 OPC Foundation 등록 후 열람 [미검증] | asyncua, open62541 | 태그 메타데이터(EURange, EngineeringUnits) |
| AAS | IDTA 사양 무료 [미검증] | Eclipse BaSyx(EPL-2.0) [미검증] | 설비 디지털 트윈 서브모델 |
| W3C SOSA/SSN | W3C 공개 | RDF 도구 | 센서·관측(Observation) 모델 |
| W3C PROV-O | W3C 공개 | — | 지식 후보의 출처·승인 추적 |

**평가 방법:** competency question(CQ) 20~30개를 먼저 정의합니다. 예: "TT-101이 속한 설비와 그 설비의 비상정지 절차 문서 버전은?", "VT-101 경보 이력과 관련 조치 기록은?" 그다음 Cypher/SQL로 답변 가능 여부, 정답률, 쿼리 길이를 측정합니다. 산업 LLM+지식그래프 최근 연구(2024~2026)의 구체적 문헌은 이번 세션에서 확인하지 못했습니다 [미검증].

### L. 시나리오·테스트 도구

| 도구 / 데이터 | 라이선스·접근 조건 | 용도 |
|---|---|---|
| Toxiproxy | MIT [미검증] | Modbus/MQTT/Kafka 지연·단절 주입 |
| Pumba | Apache-2.0 [미검증] | 컨테이너 kill, netem |
| Chaos Mesh | Apache-2.0 (CNCF) [미검증] | Kubernetes 전용이라 Compose에서는 부적합 |
| Kafka 리플레이(kcat, 오프셋 리셋) | 오픈소스 [미검증] | 동일 입력 재생 |
| SKAB | [미검증] | 밸브·펌프 이상 벤치마크 |
| Tennessee Eastman | 공개 데이터셋(여러 버전) [미검증] | 화학공정 이상 |
| SWaT / WADI | iTrust(SUTD) 신청 기반, 연구 목적 약관 [미검증] | **제품화 목적 사용 가능성 불확실**하므로 테스트 전용 |

---

## 4. 클린시트 레퍼런스 아키텍처(모두 100% OSI·무료)

| 구분 | RA-1 "보수적 진화" | RA-2 "PostgreSQL 중심 경량" | RA-3 "스트리밍 SQL" | RA-4 "표준 우선(UNS/OPC UA)" |
|---|---|---|---|---|
| L1 | pymodbus 시뮬레이터 | 동일 | 동일 | pymodbus + asyncua OPC UA 병행 |
| L2 수집 | EdgeX 4.0.x | 직접 pymodbus 서비스 또는 Telegraf inputs.modbus | Neuron OSS(Modbus/MQTT) 또는 Redpanda Connect(Apache 컴포넌트만) | Telegraf opcua 입력 또는 Node-RED, Sparkplug B(Tahu) |
| 브로커 | Mosquitto 2.1.2 | Mosquitto 2.1.2 | NanoMQ 또는 Mosquitto | Mosquitto(ISA-95 UNS 토픽) |
| 백본 | Kafka 4.2.1 | **NATS JetStream**(Kafka 제거) | Kafka 4.2.1 | Kafka 4.2.1 |
| L4 | Flink 2.2.1 (DataStream CEP + ONNX) | Python asyncio 상태 머신 + River + ONNX Runtime | RisingWave Community 또는 Timeplus Proton | Flink 2.2.1 |
| L5 | InfluxDB 2.x(고정) + PostgreSQL | PostgreSQL + TimescaleDB Apache Edition 또는 pg_partman | PostgreSQL(+QuestDB) | TimescaleDB Apache 또는 PostgreSQL |
| L6 | FUXA 1.3.4, Grafana, Prometheus | Vue + MQTT/WS, Grafana | FUXA 1.3.4, Grafana | FUXA 1.3.4 / Vue |
| L7~L9 | Neo4j CE, LiteLLM(고정), LangGraph | Apache AGE + pgvector, 직접 SDK, LangGraph 또는 DBOS | Neo4j CE, LangGraph | BaSyx(AAS) + Neo4j CE, LangGraph |
| 제거 | EMQX | EMQX, Kafka, Flink, InfluxDB, Neo4j | EMQX, Flink, Telegraf 일부 | EMQX, EdgeX |
| 잃는 기능 | EMQX 룰엔진·대시보드 | Kafka 생태계, Flink 체크포인트·정확히 한 번 처리, CEP 라이브러리 | CEP `followedBy` 표현력, EdgeX 명령 API | EdgeX 디바이스 명령·메타데이터 서비스 |
| 위험 | 낮음 | 정확성을 자체 코드가 책임짐 | RisingWave Premium 기능 경계 | 설정 공수 |

**조사자 권고:** V2의 기본선은 **RA-1**입니다(교체 1개, 버전 조치 4개). V3 방향은 RA-2와 RA-1 중 L4 회전 결과로 결정합니다. RA-4의 UNS 토픽 체계는 아키텍처와 독립적으로 V2 온톨로지 개선에 바로 적용할 수 있습니다.

---

## 5. 5영업일 회전 계획(결과값은 비워 둠)

**원칙:** 한 회전에 한 모듈만 바꿉니다. 모든 회전은 같은 시나리오(§6)와 같은 Kafka 리플레이 입력을 사용합니다. 각 회전의 산출물은 compose diff, SBOM, 라이선스 리포트, 측정표, 판정 기록입니다.

| 일차 | 회전 | 교체 모듈 | 후보(2~3) | 탈락 사전 처리 | 측정 결과 | 판정 |
|---|---|---|---|---|---|---|
| D1 오전 | R1 | **L4 패턴탐지(CEP)** | ① Flink DataStream CEP `followedBy.within` ② Flink SQL `MATCH_RECOGNIZE` + filler ③ Python asyncio 상태 머신 | Esper(GPL, 비주류), Siddhi, Materialize(BSL) | ( ) | ( ) |
| D1 오후 | R2 | L4 이상탐지(Z-Score/ML) | ① Flink 현행 + ONNX ② River 온라인 ③ RisingWave/Proton SQL 윈도우 | Moirai 비상업 가중치 | ( ) | ( ) |
| D2 | R3 | **MQTT 브로커** | ① Mosquitto 2.1.2 ② NanoMQ ③ HiveMQ CE 2026.5 | EMQX 5.9+(BSL), EMQX 5.8(EOL), VerneMQ 공식 이미지(EULA) | ( ) | ( ) |
| D3 | R4 | 공정 히스토리안 | ① InfluxDB 2.x 고정 ② PostgreSQL + TimescaleDB Apache ③ QuestDB | TimescaleDB TSL, InfluxDB 3 Enterprise | ( ) | ( ) |
| D4 오전 | R5 | 게이트웨이 | ① EdgeX 4.0.x ② Neuron OSS ③ Telegraf inputs.modbus / Redpanda Connect(Apache) | NeuronEX, Redpanda 엔터프라이즈 커넥터 | ( ) | ( ) |
| D4 오후 | R6 | 이벤트 백본(선택) | ① Kafka 4.2.1 ② NATS JetStream | Redpanda(BSL) | ( ) | ( ) |
| D5 오전 | R7 | HMI 알람 표시 / AI 게이트웨이 | ① FUXA 1.3.4 ② Vue + MQTT/WS / ① LiteLLM 고정 ② 직접 SDK | Ignition, Camunda 8, Restate | ( ) | ( ) |
| D5 오후 | 확정 | V2 확정, V3 후보 목록 | — | — | ( ) | ( ) |

**V2/V3 확정 절차:**
1. 각 회전 승자를 V1에 누적 적용해 V2 compose를 만듭니다.
2. 전체 회귀 시나리오를 1회 실행합니다.
3. 안전 Gate 전 항목이 통과하면 V2를 동결합니다.
4. 비열등이지만 전략적 우위가 있는 후보(예: RA-2)는 V3 후보로 기록합니다.
5. 온톨로지는 CQ 통과율로 V2와 V3를 비교합니다.

---

## 6. 공통 시나리오·안전 Gate·지표

**시나리오**

| 영역 | 시나리오 | 기대 결과 |
|---|---|---|
| 데이터·처리 | S1 정상 운전 30분 / S2 TT-101 상한 초과 / S3 IT-102↑ 후 N초 내 VT-101↑(CEP 양성) / S4 IT-102↑ 후 N초 초과 뒤 VT-101↑(CEP 음성) / S5 이벤트 순서 뒤바뀜·지연 주입(Toxiproxy) / S6 처리기 재시작 중 패턴 진행(상태 복구) / S7 Kafka 오프셋 리셋 재처리 | 양성만 탐지하고 중복 알람 없음 |
| 제어·안전 | C1 고압 인터록 발동 중 기동 명령 / C2 범위 밖 설정값 / C3 명령 후 /state seq 불일치 / C4 같은 정지 명령 중복 전송 | 거부, 재확인, 한 번만 실행 |
| HMI·알람 | H1 알람 발생 → FUXA·Vue 표시 → 확인 버튼 → PostgreSQL 기록 / H2 브로커 재시작 후 알람 재표시 | 누락 없음 |
| AI | A1 알람 → 사건 등록 → 조사 → 승인 대기 → 승인 → Pilot 재검사 → 정지 → /state 확인 → 기록 / A2 반려 → 무명령 / A3 승인 후 조건 변화(재검사 실패) → 무명령 / A4 체크포인트 재개 | 모든 경로에 감사 기록 |

**안전 Gate(필수, 하나라도 실패하면 탈락)**

| Gate | 판정 기준 |
|---|---|
| 인터록 | 고압 인터록이 걸린 동안 모든 경로의 기동 명령이 설비에 도달하지 않음 |
| 반려 = 무제어 | 반려 시 Modbus 쓰기 0건(브로커·Modbus 캡처로 확인) |
| 승인 후 재검사 | 승인 시점에 조건을 다시 평가하고, 불일치하면 명령하지 않음 |
| 명령 ≠ 상태 | 명령 성공은 /state seq와 상태 확인으로만 판정 |
| 중복 실행 방지 | 멱등 키로 같은 승인 ID는 한 번만 실행 |
| 감사 추적 | 누가·언제·무엇을·결과가 PostgreSQL에 전부 기록 |
| 제어경로 분리 | FUXA / Vue 백엔드 / Pilot의 3경로가 독립적. AI 프로세스에 Modbus 자격이 없음 |
| 데이터 무결성 | 원본 대비 저장 건수 손실 0, 중복 규칙 명시 |
| **라이선스·비용 Gate** | 모든 이미지·패키지의 LICENSE 파일이 OSI 승인, 라이선스 키·체험판·Premium 기능 미사용(RisingWave `SHOW` 기능, TimescaleDB `SHOW timescaledb.license = apache`), SBOM 첨부 |

**측정 지표(값은 측정 후 기입):** 종단 지연(설비 → 알람 표시) p50/p95, CEP 탐지율·오탐·탐지 지연, 재시작 후 상태 복구 정확도, 재처리 결과 일치율, 컨테이너 메모리·CPU, 기동 시간, 설정·코드 줄 수, PoC 소요 시간, 운영 지표 노출 여부, 알람 KPI(시간당 건수, 채터링).

---

## 7. 판정 규칙

1. **라이선스·비용 Gate**(필수): 하나라도 비OSI, 키 필요, 체험판, 비상업 전용이면 즉시 탈락합니다.
2. **안전 Gate**(필수): §6의 모든 항목을 통과해야 합니다.
3. **비열등성:** 현행 대비 탐지율과 데이터 무결성이 떨어지지 않아야 합니다(허용 오차는 회전 전에 명시).
4. **우위 판정**(동률 시 순서대로): ① 보안·유지보수(최근 12개월 릴리스, CVE 대응 속도, 재단 소속) ② 트렌드(독립 신호) ③ 복잡도(컨테이너 수, 설정·코드 줄 수) ④ 측정 성능.
5. **기록:** 탈락 사유도 결과표에 남깁니다.

---

## 8. 문헌만으로 판정 가능한 항목

| 항목 | 판정 | 근거 |
|---|---|---|
| EMQX 5.9+ / 6.x / 7.x | 탈락 | BSL 1.1 [1차] |
| EMQX 5.8.x 고정 | 탈락 | 2026-02-28 EOL [1차] |
| OpenQTT, LibreMQ | 탈락(관찰) | 2026-09 시작, 스타 3 수준 [2차] |
| Redpanda 브로커 | 탈락 | BSL / RCL [1차] |
| Redpanda Connect 엔터프라이즈 커넥터 | 탈락 | RCL, 키 필요 [1차] |
| Materialize | 탈락 | BSL, 키 필요 [1차] |
| Memgraph | 탈락 | BSL [1차] |
| FalkorDB | 탈락 | SSPL [1차] |
| Restate 서버 | 탈락 | BSL [1차] |
| Camunda 8 | 탈락 | Camunda License [미검증 세부] |
| TimescaleDB TSL 기능 | 사용 금지 | TSL [1차] |
| InfluxDB 3 Enterprise 무료판 | 탈락 | at-home 비상업 전용 [1차] |
| NeuronEX / Neuron 상용 드라이버 | 탈락 | 상용 라이선스 [1차] |
| VerneMQ 공식 바이너리 | 탈락 | EULA [1차] |
| Ignition(Maker 포함) | 탈락 | 상용/비상업 |
| Kuzu 본체 | 신규 채택 금지 | 아카이브 [1차] |
| Kafka, Flink, EdgeX, NATS | 라이선스 유지 확정 | ASF / CNCF / LF [1차] |
| MQTT 단독 백본 | V1 재처리 요구 불충족 | 구조적 한계 |

---

## 9. 즉시 조치 목록(우선순위 순)

1. **FUXA를 1.3.4로 업그레이드**합니다(CVE-2026-13207 등). 인터넷 노출을 금지하고, 1.2.x 이하 흔적(settings.js, 업로드 디렉터리)을 점검합니다.
2. **InfluxDB 이미지 태그를 명시적으로 고정**합니다(`latest` 금지, 2026-09-15 전환). Telegraf `outputs.influxdb_v2`가 호환되는지 확인합니다.
3. **LiteLLM 버전을 해시로 고정**합니다. 1.82.7/1.82.8이 설치된 적이 있으면 그 환경의 모든 자격증명(GCP ADC 포함)을 교체합니다.
4. **EMQX를 교체**합니다. D2 회전 전까지 임시 조치로, 현 버전이 5.9 이상이면 제품화 산출물에서 제외하고, 5.8.x이면 외부 노출을 차단합니다.
5. **Kafka를 4.2.1, Flink를 2.2.1 이상으로 고정**합니다.
6. **CI 공급망:** GitHub Actions를 커밋 SHA로 고정합니다. Trivy는 v0.69.3 / trivy-action v0.35.0 / setup-trivy v0.2.6 이상의 검증된 버전만 쓰고, 이미지는 다이제스트로 고정합니다.
7. **모든 compose 이미지를 태그와 다이제스트로 고정**하고, 회전마다 SBOM과 라이선스 리포트를 생성합니다.
8. **라이선스 확인 필요 목록([미검증] 항목) LICENSE 파일 확인:** Telegraf, FUXA, Grafana, Neo4j, LiteLLM, LangGraph, Mosquitto, HiveMQ CE, NanoMQ, pymodbus, asyncua, QuestDB, benthos-umh.
9. **bpmn-js를 쓰고 있다면** 워터마크 유지 여부를 확인합니다.

---

## 10. 출처 요약(등급별)

- **[1차]** EMQ 공지·FAQ·EOL 문서(emqx.com, docs.emqx.com), GitHub emqx/emqx Discussion #15163, CISA ICSA-26-181-02, FUXA GitHub releases·npm, Apache Flink 릴리스 공지(flink.apache.org 2025-12-04, 2026-05-11/15, 2026-06-14)와 MATCH_RECOGNIZE 문서, FLINK-33428 Jira, Apache Kafka 4.2.0 공지(2026-02-17)·업그레이드 노트, InfluxData 문서·블로그·PR #25890, EdgeX Wiki(Odesa, Releases), CNCF·Synadia 발표(2025-05-01), Redpanda Connect 문서, Neuron 라이선스 문서, RisingWave Premium 문서, Materialize 라이선스 문서, Arroyo·Cloudflare 블로그, Timeplus 문서, quix-streams LICENSE, Tiger Data TimescaleDB 에디션 문서, Memgraph BSL, FalkorDB 라이선스 문서, Kuzu README, LadybugDB·RyuGraph 문서, restate.dev FAQ, Flowable 문서, bpmn.io LICENSE, mosquitto.org 블로그, vernemq.com EULA, HiveMQ CE releases, LiteLLM 보안 공지.
- **[2차]** Snyk, Wiz, Socket, Legit Security, Sysdig, Upwind, Datadog Security Labs, NHS England Digital, The Register, The New Stack, ARC Advisory, Layerbase, Exploit-Intel, Vulners, OpenQTT·LibreMQ GitHub.
- **[벤더]** EMQ 비교 블로그, Confluent·Alibaba Flink 문서, RisingWave의 Arroyo 비교, QuestDB 벤치마크 글, Varpulis 문서, IOTech.

---

## Caveats

- 이번 세션의 검색 예산 한도로 많은 라이선스를 **[미검증]**으로 남겼습니다. §9-8 확인 절차를 Claude Code 첫 작업으로 넣으십시오.
- CISA 권고 원문 페이지는 봇 차단으로 직접 열지 못했고, 검색 결과 발췌로 확인했습니다. FUXA의 정확한 수정 버전 표기는 GitHub 보안 권고에서 재확인이 필요합니다.
- FLINK-33428의 현재 해결 상태, SQL filler 패턴의 동작, PyFlink의 CEP 지원 범위는 D1 PoC에서 확인해야 합니다.
- 모든 성능 비교는 측정 전입니다. 벤더 수치는 판정 근거에서 제외하십시오.

## 출처

1. [A Notice on the EMQX 5.8 Open Source Version End-of-Life and Future Product Strategy | EMQ](https://www.emqx.com/en/news/a-notice-on-the-emqx-5-8-open-source-version)
2. [GitHub - emqx/emqx: The most scalable and reliable MQTT broker for AI, IoT, IIoT and connected vehicles · GitHub](https://github.com/emqx/emqx)
3. [Import EMQX 5.8.9 and publish v1.0.0 · Issue #1 · openqtt/openqtt](https://github.com/openqtt/openqtt/issues/1)
4. [Open Source MQTT Broker: Mosquitto vs EMQX vs HiveMQ CE vs VerneMQ](https://scadaprotocols.com/open-source-mqtt-broker/)
5. [Frangoteam FUXA SCADA/HMI | CISA](https://www.cisa.gov/news-events/ics-advisories/icsa-26-181-02)
6. [Releases · frangoteam/FUXA](https://github.com/frangoteam/FUXA/releases)
7. [Query data | Get started with InfluxDB 3 Core | InfluxDB 3 Core Documentation](https://docs.influxdata.com/influxdb3/core/get-started/query/)
8. [Security Update: Suspected Supply Chain Incident | liteLLM](https://docs.litellm.ai/blog/security-update-march-2026)
9. [Pattern Recognition | Apache Flink](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/table/sql/queries/match_recognize/)
10. [Odesa - EdgeX Wiki - Confluence - Atlassian](https://lf-edgexfoundry.atlassian.net/wiki/spaces/FA/pages/11678577/Odesa)
11. [Releases - EdgeX Wiki - Confluence](https://lf-edgexfoundry.atlassian.net/wiki/display/FA/Releases)
12. [EdgeX Odesa Release | IOTech, Edge Software Solutions](https://www.iotechsys.com/edgex-community/edgex-latest-release-odesa/)
13. [EMQX 5.9 adopts Business Source License (BSL) · emqx/emqx · Discussion #15163](https://github.com/emqx/emqx/discussions/15163)
14. [Apache Kafka 4.2.0 Release Announcement | Apache Kafka](https://kafka.apache.org/blog/2026/02/17/apache-kafka-4.2.0-release-announcement/)
15. [Upgrading | Apache Kafka](https://kafka.apache.org/42/getting-started/upgrade/)
16. [Apache Flink 2.2.1 Release Announcement | Apache Flink](https://flink.apache.org/2026/05/15/apache-flink-2.2.1-release-announcement/)
17. [Apache Flink 2.2.0: Advancing Real-Time Data + AI and Empowering Stream Processing for the AI Era | Apache Flink](https://flink.apache.org/2025/12/04/apache-flink-2.2.0-advancing-real-time-data--ai-and-empowering-stream-processing-for-the-ai-era/)
18. [InfluxDB 3 Core 72-hour query limit explained | Layerbase](https://layerbase.com/blog/influxdb-3-core-72-hour-limit)
19. [feat: loosen 72 hour query/write restriction by mgattozzi · Pull Request #25890 · influxdata/influxdb](https://github.com/influxdata/influxdb/pull/25890)
20. [CVE-2026-25895: FUXA Unauthenticated Remote Code Execution via Arbitrary File Write in Upload API](https://exploit-intel.com/vuln/CVE-2026-25895)
21. [UNPKG](https://unpkg.com/browse/@frangoteam/fuxa@1.1.3/)
22. [LiteLLM and Telnyx compromised on PyPI: Tracing the TeamPCP supply chain campaign | Datadog Security Labs](https://securitylabs.datadoghq.com/articles/litellm-compromised-pypi-teampcp-supply-chain-campaign/)
23. [Apache Flink 2.1.3 Release Announcement | Apache Flink](https://flink.apache.org/2026/06/14/apache-flink-2.1.3-release-announcement/)
24. [Flink Blog | Apache Flink](https://flink.apache.org/posts/)
25. [Varpulis — Rust Stream Processing for Real-Time Detection](https://varpulis-cep.com/docs/comparisons/varpulis-vs-arroyo.html)
26. [CEP statements - Realtime Compute for Apache Flink - Alibaba Cloud Documentation Center](https://www.alibabacloud.com/help/en/flink/developer-reference/cep-statements)
27. [GitHub - emqx/neuron: Open source industrial connectivity server · GitHub](https://github.com/emqx/neuron)
28. [EdgeX Foundry Releases EdgeX 4.0 with MQTT | ARC Advisory Group](https://www.arcweb.com/blog/edgex-foundry-releases-edgex-40-mqtt)
29. [License Policy | Neuron Docs](https://docs.emqx.com/en/neuron/latest/introduction/license/license-policy.html)
30. [Experience Neuron Industrial IoT Gateway Software for Free with Time-Unlimited Trial License | by EMQ Technologies | Medium](https://emqx.medium.com/experience-neuron-industrial-iot-gateway-software-for-free-with-time-unlimited-trial-license-7f29c229574a)
31. [Installing and Activating License | Neuron Docs](https://docs.emqx.com/en/neuron/latest/installation/license-install/license-install.html)
32. [Data Integration Platform & Connectors | Redpanda Connect](https://www.redpanda.com/connect)
33. [connect/licenses at main · redpanda-data/connect](https://github.com/redpanda-data/connect/tree/main/licenses)
34. [Introducing Redpanda Connect](https://www.redpanda.com/blog/redpanda-connect)
35. [Enterprise Licensing | Redpanda Connect](https://docs.redpanda.com/redpanda-connect/get-started/licensing/)
36. [Introducing Flowable Open Source · Flowable Open Source Documentation](https://www.flowable.com/open-source/docs/oss-introduction)
37. [Comparison of Open Source MQTT Brokers 2026 | EMQ](https://www.emqx.com/en/blog/a-comprehensive-comparison-of-open-source-mqtt-brokers-in-2023)
38. [OpenQTT 0.1.0: green build, new org, deployable on Kubernetes by crypto-a · Pull Request #5 · openqtt/openqtt](https://github.com/openqtt/openqtt/pull/5)
39. [GitHub - mikekelly/LibreMQ: Apache 2 Licensed MQTT broker with cluster mode for AI, IoT, IIoT and connected vehicles · GitHub](https://github.com/mikekelly/LibreMQ)
40. [Mosquitto Package - SynoCommunity](https://synocommunity.com/package/mosquitto)
41. [Version 2.1.2 released. | Eclipse Mosquitto](https://mosquitto.org/blog/2026/02/version-2-1-2-released/)
42. [Version 2.1.0 released. | Eclipse Mosquitto](https://mosquitto.org/blog/2026/01/version-2-1-0-released/)
43. [HiveMQ - Enterprise MQTT Platform · GitHub](https://github.com/hivemq)
44. [Releases · hivemq/hivemq-community-edition](https://github.com/hivemq/hivemq-community-edition/releases)
45. [Releases · vernemq/vernemq](https://github.com/vernemq/vernemq/releases)
46. [VerneMQ End User License Agreement](https://vernemq.com/blog/2019/11/26/vernemq-end-user-license-agreement.html)
47. [CNCF and Synadia Align on Securing the Future of the NATS.io Project | CNCF](https://www.cncf.io/announcements/2025/05/01/cncf-and-synadia-align-on-securing-the-future-of-the-nats-io-project/)
48. [Redpanda Licenses and Enterprise Features](https://docs.redpanda.com/streaming/26.1/get-started/licensing/overview.md)
49. [Redpanda Licenses and Enterprise Features | Redpanda Streaming](https://docs.redpanda.com/current/get-started/licensing/overview/)
50. [Synadia and the NATS project | Synadia](https://www.synadia.com/blog/nats-server-next-steps)
51. [Odesa - EdgeX Wiki - Confluence](https://lf-edgexfoundry.atlassian.net/wiki/spaces/FA/pages/11678577/Odesa+Next+Release)
52. [Our Latest Release | EdgeX Foundry, Open Source Edge Platform](https://www.edgexfoundry.org/software/releases/)
53. [RisingWave Premium features - RisingWave](https://docs.risingwave.com/get-started/premium-features)
54. [Everything You Want to Know about RisingWave Premium | by RisingWave Labs | Real-Time Data Evolution | Medium](https://medium.com/real-time-data-evolution/everything-you-want-to-know-about-risingwave-premium-7637d6e352d6)
55. [License | Materialize Documentation](https://materialize.com/docs/license/)
56. [GitHub - MaterializeInc/materialize: The live data layer for apps and AI agents. Create up-to-the-second views into your business, just using SQL · GitHub](https://github.com/MaterializeInc/materialize)
57. [Sign Up for a Self-Managed Community License - Materialize](https://materialize.com/self-managed/community-license/)
58. [Introduction | Timeplus](https://docs.timeplus.com/)
59. [RisingWave vs Arroyo: Rust-Based Stream Processors Compared | RisingWave](https://risingwave.com/blog/risingwave-vs-arroyo-rust-stream-processors/)
60. [Arroyo is joining Cloudflare | Arroyo blog](https://www.arroyo.dev/blog/arroyo-is-joining-cloudflare/)
61. [Apache License 2.0 - quixio/quix-streams](https://github.com/quixio/quix-streams/blob/main/LICENSE)
62. [Announcing InfluxDB 3 Enterprise free for at-home use and an update on InfluxDB 3 Core’s 72-hour limitation | InfluxData](https://www.influxdata.com/blog/influxdb3-open-source-public-alpha-jan-27/)
63. [Announcing InfluxDB 3 Enterprise free for at-home use and an update on InfluxDB 3 Core’s 72-hour limitation | daily.dev](https://daily.dev/posts/announcing-influxdb-3-enterprise-free-for-at-home-use-and-an-update-on-influxdb-3-core-s-72-hour-lim-9wu3kovlj)
64. [Compare TimescaleDB editions](https://www.tigerdata.com/docs/about/latest/timescaledb-editions)
65. [Compare TimescaleDB editions](https://www.tigerdata.com/docs/get-started/choose-your-path/timescaledb-editions)
66. [We finally benchmarked InfluxDB 3 OSS Core (Alpha) | QuestDB](https://questdb.com/blog/influxdb3-core-alpha-benchmarks-and-caveats/)
67. [Fuxa Security Vulnerabilities and Issues — Fuxa CVE List | Vulners.com](https://vulners.com/search/vendors/frangoteam/products/fuxa)
68. [@frangoteam/fuxa - npm](https://www.npmjs.com/package/@frangoteam/fuxa?activeTab=versions)
69. [Trivy GitHub Actions Supply Chain Compromise | Snyk](https://snyk.io/articles/trivy-github-actions-supply-chain-compromise/)
70. [Trivy Supply Chain Incident: GitHub Actions Compromise Breakdown](https://www.upwind.io/feed/trivy-supply-chain-incident-github-actions-compromise-breakdown)
71. [Trivy Under Attack Again: Widespread GitHub Actions Tag Compromise Exposes CI/CD Secrets | Socket](https://socket.dev/blog/trivy-under-attack-again-github-actions-compromise)
72. [Trivy Supply Chain Attack: GitHub Actions Security Breach | Cy5.io](https://www.cy5.io/blog/trivy-supply-chain-attack-github-actions-security/)
73. [TeamPCP expands: Supply chain compromise spreads from Trivy to Checkmarx GitHub Actions | Sysdig](https://www.sysdig.com/blog/teampcp-expands-supply-chain-compromise-spreads-from-trivy-to-checkmarx-github-actions)
74. [The Trivy Supply Chain Compromise: What Happened and Playbooks to Respond](https://www.legitsecurity.com/blog/the-trivy-supply-chain-compromise-what-happened-and-playbooks-to-respond)
75. [How a Poisoned Security Scanner Became the Key to Backdooring LiteLLM | Snyk](https://snyk.io/blog/poisoned-security-scanner-backdooring-litellm/)
76. [LiteLLM PyPI Package Compromise - NHS England Digital](https://digital.nhs.uk/cyber-alerts/2026/cc-4761)
77. [memgraph/licenses/BSL.txt at master · memgraph/memgraph](https://github.com/memgraph/memgraph/blob/master/licenses/BSL.txt)
78. [FalkorDB License - FalkorDB Docs](https://docs.falkordb.com/references/license)
79. [com.kuzudb:kuzu - Maven Central - Sonatype](https://central.sonatype.com/artifact/com.kuzudb/kuzu)
80. [KuzuDB, the Promising Embedded Graph Database, is Suddenly Archived - BigGo News](https://biggo.com/news/202510130126_KuzuDB-embedded-graph-database-archived)
81. [Install Ladybug - LadybugDB](https://docs.ladybugdb.com/installation/)
82. [Licensing: the repository has no LICENSE file · Issue #85 · LadybugDB/extensions](https://github.com/LadybugDB/extensions/issues/85)
83. [GitHub - predictable-labs/ryugraph: Ryu, a fork of Kuzu, is an Embedded Property Graph Database built for speed with vector search and full-text search built in. Implements Cypher. · GitHub](https://github.com/predictable-labs/ryugraph)
84. [predictable-labs/ryugraph | DeepWiki](https://deepwiki.com/predictable-labs/ryugraph)
85. [Restate | The Durable Runtime for your Agents and Backends](https://restate.dev/)
86. [License | bpmn.io](https://bpmn.io/license/)
