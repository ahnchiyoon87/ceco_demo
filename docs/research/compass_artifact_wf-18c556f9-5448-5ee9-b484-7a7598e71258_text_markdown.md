# IoT/SCADA/AI 프로토타입 V1→V2→V3 빠른 회전 탐색: 근거 자료와 5영업일 실행 가이드 (2026년 9월 기준)

5영업일 안에 궤적을 만들려면 모듈 수를 줄여야 합니다. 이번 조사에서 실제로 실측이 필요한 모듈은 세 곳으로 좁혀졌습니다. ① 스트림 패턴탐지(Flink CEP·SQL·Python 상태머신), ② OT 수집 경로(EdgeX를 뺄지), ③ 승인→재검사→제어→확인 워크플로우 엔진입니다. 나머지(브로커 라이선스, 저장소, 그래프 DB, LLM 게이트웨이)는 문헌만으로 결정하거나 탈락시켜도 됩니다. "CEP는 요즘 안 쓴다"는 말은 절반만 맞습니다. Esper·Siddhi 같은 독립 CEP 엔진은 쇠퇴했고, CEP는 스트림 처리 엔진과 스트리밍 SQL 안으로 흡수됐습니다.\[1\] 하지만 "전류 상승 후 N초 내 진동 상승" 같은 시간순서 패턴 탐지는 여전히 필요한 기능이고, Flink CEP도 2026년에 계속 배포·수정되고 있습니다.\[2\]\[3\]

## TL;DR
- **CEP 주장 검증**: 대표님 말씀은 부분적으로만 맞습니다. Flink 2.x는 `flink-cep` 아티팩트를 계속 배포하고, 2026-05-15 Flink 2.2.1에서도 MATCH_RECOGNIZE 버그가 수정됐습니다. 반면 EsperTech 공식 Change History 기준 Esper의 마지막 릴리스는 9.0.0(2024-04-26)이고 Siddhi는 정체 상태입니다. Gartner도 이 시장을 'Event Stream Processing'으로 부릅니다. 따라서 결론은 "CEP 엔진을 빼자"가 아닙니다. "패턴탐지를 어떤 구현으로 할지 실측해 정하자"로 바꿔 잡아야 합니다.
- **문헌만으로 확정할 것**: EMQX 5.9+는 BSL 1.1로 바뀌어 단일 노드만 무료입니다. Kuzu는 2025-10-10 아카이브됐습니다. ksqlDB는 사실상 유지보수 모드이고 Bytewax는 2025년 5월부터 커뮤니티 유지로 넘어갔습니다. LiteLLM은 2026-03-24 PyPI 공급망 공격(1.82.7/1.82.8)을 당했습니다. InfluxData 공식 설정 문서에 따르면 InfluxDB 3 Core는 기본값 432 파일 기준으로 쿼리당 최대 72시간 분량의 데이터만 읽습니다. 이 내용으로 후보를 정리하면 비교 대상이 모듈당 2~3개로 줄어듭니다.
- **실행 원칙**: 회전마다 한 번에 한 변수만 바꿉니다. 동일 리플레이 하니스(같은 데이터·시드·시나리오)로 p50/p95/p99, 리소스, 코드량, 구현시간을 자동 측정합니다. 인터록, 승인 후 재검사, 명령 후 실제상태 확인은 모든 후보에 공통으로 거는 안전 Gate로 둡니다. Gate를 통과하지 못한 후보는 성능과 관계없이 탈락입니다. 측정값 칸은 비워 두고 실행 후에만 채웁니다.

---

## Key Findings

### 1. "CEP는 요즘 안 쓴다" 사실 검증 결과

| 검증 항목 | 문헌 근거 | 판정 |
|---|---|---|
| Flink CEP 라이브러리 유지 | Flink 공식 문서는 MATCH_RECOGNIZE가 "Apache Flink's CEP library internally"를 사용한다고 명시합니다. stable 문서의 의존성은 `flink-cep` 2.2.0입니다. Flink 2.2.1(2026-05-15)의 수정 목록에 "FLINK-39293 – SqlParserException if I select from a view that uses MATCH_RECOGNIZE"가 있습니다\[2\]\[3\] | **유지 중** |
| CEP 신기능 개발 | Apache Flink 위키의 "FLIP-200: Support Multiple Rule and Dynamic Rule Changing (Flink CEP)"은 dev@flink 메일링 리스트에서 2021년 12월 논의됐습니다(Becket Qin 답신 2021-12-21). 오픈소스 Flink에는 병합되지 않은 것으로 보이며, Alibaba Cloud(`CEP.dynamicPatterns()` API)·Ververica 상용 제품에 FLIP-200 기반 "Dynamic Flink CEP"로만 들어가 있습니다. 2024~2026년에 CEP 전용 신규 FLIP은 찾지 못했습니다 | **정체(유지보수 위주)** |
| 독립 CEP 엔진 | EsperTech 공식 Change History에 "Version 9.0.0 Released April 26, 2024 Requires Java 17 runtime or newer"라고 나옵니다. 바로 앞 릴리스는 8.9.0(2023-04-27)이고, 9.0.0 이후 약 2.4년간 릴리스가 없습니다. Siddhi는 2024년 10월 이슈가 미해결로 남아 있어 정체 신호가 보입니다\[4\] | **쇠퇴** |
| 산업계 프레이밍 | Gartner "Market Guide for Event Stream Processing"(2023-05)은 시장을 ESP로 정의하고 CEP를 하위 개념으로만 다룹니다.\[5\]\[6\] EDBT 2024 논문은 FlinkCEP·KafkaStreamCEP 등이 CEP를 "additional unary operator"로 편입한 hybrid stream processing system으로 수렴한다고 기술합니다\[1\] | **흡수·통합** |
| 벤더 동향 | 2026년에도 Confluent 계열 필자(Kai Waehner, 2026-04-28)가 Flink CEP를 Agentic AI의 패턴탐지 층으로 홍보합니다.\[7\] 벤더 발언이므로 채택 근거가 아닌 "아직 쓰인다"는 방증으로만 봐야 합니다 | 참고 |

**해석**: 대표님 말씀 중 맞는 부분은 "Esper 같은 별도 CEP 엔진이나 CEP 전용 DSL을 새로 도입할 이유는 약하다"입니다. 틀린 부분은 "시간순서 패턴 탐지 요구가 사라졌다"입니다. V1의 L4에 있는 'CEP'를 V2에서 없앨지는 기술 유행으로 정할 문제가 아닙니다. 같은 패턴 시나리오를 (a) Flink CEP(DataStream), (b) Flink SQL MATCH_RECOGNIZE, (c) Python 상태머신 서비스로 구현한 뒤, out-of-order·late·재시작 시나리오에서 정답률과 복구 동작을 비교해 결정해야 합니다.

**Flink CEP/MATCH_RECOGNIZE의 문헌상 제약** (PoC 설계 시 반영):
- Flink CEP는 "assumes correctness of the watermark"입니다. 워터마크보다 늦은 이벤트는 "not further processed" 처리되고 sideOutput으로만 수집할 수 있습니다.\[8\] late event 시나리오에서 "탐지 누락"이 설계상 정상 동작일 수 있다는 뜻이므로, 기대 결과를 미리 정의해 둬야 합니다.
- DataStream API는 `notFollowedBy()`로 패턴을 끝내려면 `within()`이 필요합니다(FLINK-16010). SQL에는 notFollowedBy 의미론이 아직 없습니다(FLINK-33428).\[8\]\[9\]\[10\] "전류 상승 후 N초 내 진동 상승이 **없으면**" 같은 부정 패턴은 SQL로 표현하기 어렵습니다.
- Confluent 문서 기준으로 MATCH_RECOGNIZE는 표준의 "subset"이고 "append-only table as input"을 요구합니다.\[11\] 실무 가이드(Streamkap)는 MATCH_RECOGNIZE에 CEP 라이브러리 같은 네이티브 타임아웃이 없으므로 DEFINE 조건에 시간 제약을 넣으라고 권고합니다.\[12\]

### 2. 문헌만으로 정리되는 라이선스·유지보수 사실 (2025~2026)

| 대상 | 사실 | 이 프로젝트에 대한 함의 |
|---|---|---|
| EMQX | 5.9부터 Community·Enterprise를 통합하고 BSL 1.1로 전환했습니다. Additional Use Grant로 "production use of a single node"가 허용되고, 각 버전은 4년 후 Apache 2.0으로 전환됩니다. 무료 클러스터 모드는 없어졌습니다\[13\]\[14\]\[15\]\[16\] | 단일 머신 프로토타입에는 문제가 없습니다. 다만 고객 제품에 "embedded"하거나 클러스터가 필요하면 상용 라이선스를 사야 합니다.\[17\]\[18\] 대안 비교 대상은 Mosquitto·NanoMQ입니다 |
| EdgeX Foundry | 4.0 "Odesa"(2025-03, LTS)에서 PostgreSQL이 기본 DB, MQTT가 기본 내부 메시지 버스가 됐고 OpenBao·Core Keeper로 교체됐습니다. BSL로 바뀐 Redis 등을 대체한 결과입니다.\[19\]\[20\] 위키에는 4.0.2 "Palau"(2026-06) 표준 릴리스가 올라와 있습니다\[21\] | 유지보수는 활발합니다. 다만 소규모 Modbus 6대 규모에서 마이크로서비스 수가 과한지는 실측해야 할 항목입니다 |
| EMQX Neuron | 오픈소스 Neuron은 LGPLv3이고 Modbus·MQTT 드라이버를 포함합니다.\[22\] 상용 "EMQX Neuron(구 NeuronEX)"은 70개 이상 프로토콜을 지원하고 "permanent free license for up to 30 data tags"를 제공하며 Sparkplug B·OPC UA 서버를 지원합니다\[23\]\[24\] | 태그 수십 개 규모라면 30태그 무료 한도를 넘길 수 있습니다. Modbus만 쓸 경우 오픈소스판으로 충분한지 확인해야 합니다 |
| Redpanda / Redpanda Connect | Redpanda 브로커는 BSL이고 4년 후 Apache 2.0으로 전환됩니다.\[25\] Connect 코어 엔진은 MIT, Community·Certified 커넥터는 Apache 2.0입니다. Enterprise 커넥터(CDC 등)는 라이선스 키가 없으면 차단됩니다\[26\]\[27\] | Modbus→MQTT/Kafka 브리지 용도라면 무료 범위 안에서 가능할 것으로 봅니다. 사용할 커넥터 등급은 PoC 전에 확인해야 합니다 |
| Kafka 4.x | 4.0(2025-03-18)에서 ZooKeeper가 완전히 제거되고 KRaft 전용이 됐습니다. KIP-848 새 컨슈머 그룹 프로토콜이 GA가 됐고 KIP-932 Queues(share group)가 early access로 들어왔습니다.\[28\]\[29\] 4.1(2025-09)에서 KIP-932는 preview가 됐고, 2026-02-17 릴리스된 4.2.0에서 production-ready가 됐습니다. 공식 4.2 업그레이드 문서: "Queues for Kafka (KIP-932) is production-ready in Apache Kafka 4.2." 브로커는 Java 17+가 필요합니다\[28\] | 단일 노드 KRaft 컨테이너 하나로 운영 부담이 줄었습니다. 쓸지 말지는 replay·다중 컨슈머 요구에 달렸습니다 |
| NATS | Synadia가 BSL 전환과 CNCF 탈퇴를 시도했으나 2025-05-01 합의로 CNCF에 남았습니다. Synadia는 "continue to maintain … under the Apache 2.0 license"라고 발표했습니다\[30\]\[31\]\[32\] | 라이선스 리스크는 해소됐습니다. JetStream은 replay가 가능한 경량 대안입니다 |
| ksqlDB | Conduktor는 "effectively maintenance-mode"라고 평가합니다. Confluent는 2023년 Immerok을 인수한 뒤 Flink SQL로 전략을 옮겼습니다\[33\]\[34\] | 신규 후보에서 **탈락** |
| Bytewax | 2025년 5월 README에 "no longer commercially viable"이라고 적고 커뮤니티 유지로 넘어갔습니다. 마지막 릴리스는 0.21.1(2024-11)이고 waxctl은 아카이브됐습니다\[35\]\[36\]\[37\] | 신규 후보에서 **탈락**(Quix Streams나 순수 Python으로 대체) |
| Arroyo | 2025-04 Cloudflare에 인수됐고 엔진은 Apache 라이선스로 셀프호스팅이 가능하다고 발표했습니다.\[38\] 경쟁 제품(Varpulis) 문서는 마지막 태그를 v0.15.0(2025-12)으로 보고 "alive but slow"라고 평가합니다(경쟁사 평가라 편향 가능)\[39\] | 선택 후보입니다. 우선순위는 낮습니다 |
| InfluxDB 3 Core | InfluxData 공식 설정 문서: "With the default 432 setting and the default gen1-duration setting of 10 minutes, queries can access up to a 72 hours of data… We recommend keeping the default setting and querying smaller time ranges." 이 제한은 influxdb PR #25890에서 들어왔습니다. `--query-file-limit`로 조정할 수 있지만 성능 저하를 감수해야 합니다. Enterprise에만 compactor가 있습니다. v3에서는 Flux를 지원하지 않습니다 | 사건 분석 시 "며칠 전 이력 조회"가 필요하면 제약이 됩니다. InfluxDB 2나 TimescaleDB와 비교해야 합니다 |
| TimescaleDB | 회사가 2025-06-17 TigerData로 개명했고 확장 이름은 TimescaleDB로 유지됐습니다. 코어는 Apache 2.0이고, 압축·연속집계 등은 TSL 라이선스로 DBaaS로 제공하지 않는 한 무료입니다. 2.30.1이 2026-09-17에 릴리스됐습니다\[40\]\[41\]\[42\] | L5(InfluxDB+PostgreSQL)를 PostgreSQL 하나로 합칠 수 있는 유력 후보입니다 |
| Kuzu | 2025-10-10 GitHub이 아카이브됐고 0.11.3이 최종 릴리스입니다. 2026년 2월 EU 제출 서류로 Apple의 acqui-hire가 확인됐습니다. LadybugDB·Bighorn 포크가 있습니다\[43\]\[44\]\[45\] | 후보에서 **탈락**(포크의 성숙도는 미검증) |
| Apache AGE | PostgreSQL 11~18을 지원합니다. 2024년 11월 ASF 보드 보고에서 "stagnant"로 분류된 적이 있고, 2025년 말부터 활동이 재개됐습니다. 메인테이너 스스로 "small team"이라고 밝힙니다\[46\]\[47\]\[48\] | PostgreSQL 단일화에는 매력적이지만 유지보수 리스크가 있습니다. 소규모라면 AGE 없이 관계형 테이블+재귀 CTE로 충분한지 먼저 확인해야 합니다 |
| LiteLLM | 2026-03-24 TeamPCP가 Trivy CI 침해로 얻은 PyPI 자격증명을 이용해 1.82.7/1.82.8에 악성코드(자격증명 탈취·지속성 백도어)를 넣어 배포했습니다. PyPI 사고보고서에 따르면 공격 창구 동안 119k회 이상 다운로드됐습니다.\[49\]\[50\]\[51\] 노출 시간은 출처마다 다릅니다. LiteLLM 공식 보안 공지는 "live on March 24, 2026 from 10:39 UTC for about 40 minutes"라고 했고, Snyk은 1.82.7이 10:39 UTC, 1.82.8이 10:52 UTC에 게시돼 "approximately three hours" 동안 받을 수 있었다고 봅니다. LiteLLM 공지는 "Customers running the official LiteLLM Proxy Docker image were not impacted"라고도 밝혔습니다 | 계속 쓴다면 해시 포함 lock 파일과 버전 고정, 프록시 컨테이너 격리, API 키 최소화가 필수입니다. 게이트웨이 없이 SDK를 직접 호출하는 방안과 비교해야 합니다 |
| FUXA | 활발합니다. 최근 릴리스에 Node-RED 연동, uPlot 청크 스트리밍 등이 추가됐고 문서는 2026-02에 공식 사이트로 이전됐습니다. Modbus·OPC UA·MQTT·InfluxDB를 지원합니다\[52\]\[53\]\[54\] | 유지해도 됩니다. 비교는 선택 사항입니다 |
| Ignition | 8.3.3이 2026-01-22에 릴리스됐습니다\[55\] | Maker Edition은 비상업 전용이므로(라이선스 원문 확인 필요) 회사 PoC 용도에는 부적합할 가능성이 큽니다 |

---

## Details

### A. 모듈별 후보 표와 PoC 레시피

표기: **[문헌]** = 본 조사에서 확인된 사실, **[측정]** = 로컬에서만 알 수 있는 값(현재 공란), **[미확인]** = 본 조사에서 1차 출처를 확인하지 못함.

#### A-1. OT 프로토콜/게이트웨이 (L1→L2) — 우선순위 높음

| 후보 | 활동성·라이선스 [문헌] | 이 규모 적합성(가설) | 제거·통합 시 잃는 것 | 최소 PoC | 측정 [측정] |
|---|---|---|---|---|---|
| EdgeX 4.x (V1 기준선) | 4.0 LTS(2025-03), 4.0.2(2026-06),\[21\] Apache 2.0 | 기능은 과잉일 수 있음 | 장치 프로파일·메타데이터 모델, 보안 스택(OpenBao) | 공식 compose + device-modbus 서비스 | 컨테이너 수, RAM, 폴링→MQTT 지연, 설정 LOC |
| pymodbus 폴러(직접) | [미확인] 최신 버전은 PoC 전에 PyPI에서 확인 | 6대·수십 태그에는 가장 단순 | 장치 추상화, 표준 프로파일, UI | Python 1파일(폴링 루프+paho-mqtt), 수백 줄 이하 예상 | 동일 |
| Telegraf `inputs.modbus` → MQTT/Kafka | V1에 이미 Telegraf가 있음 | L2의 EdgeX+Telegraf를 Telegraf 하나로 통합하는 후보 | 쓰기(명령) 경로 없음 → Pilot 제어는 별도 경로 필요 | telegraf.conf 1개 | 동일 + 명령 경로 분리 여부 |
| EMQX Neuron(OSS/상용) | OSS는 LGPLv3(Modbus·MQTT), 상용은 30태그 영구 무료\[22\]\[23\] | 태그 수를 세어 한도 확인 필요 | 벤더 종속 | `docker run emqx/neuron` + UI 설정 | 동일 + 한도 초과 여부 |
| Redpanda Connect / Node-RED | Connect 코어 MIT·커넥터 Apache 2.0\[26\] / Node-RED [미확인] | 브리지·변환 용도 | 장치 모델 없음 | YAML 1개 / 플로우 1개 | 동일 |

- **OPC UA·Sparkplug B·UNS**: UNS와 Sparkplug B는 벤더(EMQ 등)가 강하게 밀고 있는 트렌드입니다. 다만 태그 수십 개 규모의 단일 가상공정에서는 이득(자동 검색, 상태 인지 birth/death 메시지)을 측정할 수 있는 시나리오를 먼저 정의해야 합니다. 권장: V2에서는 UNS 스타일 토픽 네이밍(`site/area/line/equipment/tag`)만 적용하고, Sparkplug B 페이로드는 V3 후보로 미룹니다.
- **Apache PLC4X**: 본 조사에서 2025~2026 릴리스 정보를 확인하지 못했습니다[미확인]. 5일 일정에서는 제외를 권장합니다.
- **안전 요구(모든 후보 공통)**: 게이트웨이는 "읽기 경로"만 담당하고, Pilot의 Modbus write는 별도 서비스가 수행하는 구조를 유지합니다(V1 원칙인 "FUXA 직접조작과 Pilot 승인조치는 별도 경로"와 일치).

#### A-2. MQTT 브로커/이벤트 백본 (L2~L3) — 우선순위 중간(문헌으로 대부분 정리됨)

| 후보 | 핵심 사실 [문헌] | 판단 |
|---|---|---|
| EMQX 5.9+ | BSL 1.1, 단일 노드 무료\[15\] | 유지 가능. 제품화 시 라이선스를 재검토해야 함 |
| Mosquitto / NanoMQ | [미확인] 최신 릴리스 | 라이선스 리스크를 없애고 싶을 때 1:1 교체 후보(변수 1개) |
| Kafka 4.x KRaft | ZooKeeper 제거, Java 17\[28\]\[56\]\[57\] | replay·다중 컨슈머·오프셋 기반 재처리가 필요하면 유지 |
| NATS JetStream | Apache 2.0 유지 확정\[32\] | MQTT+Kafka 두 계층을 하나로 합치는 후보(변수 2개가 바뀌므로 회전 2 이후로) |
| Redpanda | BSL | Kafka API 호환 단일 바이너리. 라이선스 조건이 수용 가능하면 후보 |

**MQTT만으로 충분한 조건과 Kafka가 필요한 조건**: MQTT는 retained message와 QoS는 있지만, 과거 구간을 오프셋으로 다시 읽는 replay는 기본적으로 없습니다. V1 요구 가운데 "Flink 재시작 후 상태 복구", "동일 데이터 재생 하니스", "alerts/clean/score 다중 소비"는 로그형 백본(Kafka·Redpanda·JetStream)이 있어야 자연스럽게 해결됩니다. 따라서 백본 제거는 "재시작·replay 시나리오를 MQTT만으로 통과하는가"를 측정한 결과로 정해야 합니다.

#### A-3. 스트림/이상탐지 (L4) — 최우선(가장 불확실하고 영향 큼)

**비교할 패턴(공통 정의)**: `IT-102(전류) > 임계 상태가 시작된 뒤 N초 이내에 VT-101(진동) > 임계` → alert. 파티션 키는 설비 ID, 시간 기준은 이벤트 시간(센서 타임스탬프)으로 합니다.

| 후보 | 구현 방법 | out-of-order/late | 재시작 상태복구 | 활동성 [문헌] | 코드 규모 감(가설) |
|---|---|---|---|---|---|
| Flink CEP (DataStream, Java) | `Pattern.begin("i").where(...).followedBy("v").where(...).within(N s)` | 워터마크 기반. late 이벤트는 폐기되거나 sideOutput으로 감\[8\] | 체크포인트/세이브포인트 | 2.x에서 계속 배포\[3\]\[58\] | 중 |
| Flink SQL MATCH_RECOGNIZE | `PARTITION BY equip ORDER BY ts PATTERN (I V) DEFINE ... ` + 시간 조건 | 위와 동일(내부적으로 CEP 사용) | 동일 | 지원 중, 표준의 부분집합, notFollowedBy 없음\[10\]\[11\] | 소 |
| Python 상태머신 서비스 | Kafka 소비 → 설비별 상태 dict → 타이머 → Kafka 발행. 상태는 PostgreSQL/SQLite에 저장 | 직접 구현(허용 지연 버퍼·정렬) | 오프셋과 상태를 원자적으로 저장해야 함(직접 구현) | 해당 없음 | 소~중 |
| Quix Streams / Faust fork | [미확인] 2025~2026 릴리스 | 라이브러리마다 다름 | 상태 저장소(RocksDB 등) | [미확인] | 소 |
| RisingWave / Materialize / Timeplus(Proton) | 스트리밍 SQL 뷰 | 엔진마다 다름 | 엔진이 관리 | [미확인] 본 조사에서 1차 확인 못함 | 소 |
| 탈락 | ksqlDB(유지보수 모드), Bytewax(커뮤니티 이관·릴리스 정지), Esper/Siddhi(정체) | — | — | [문헌] | — |

**권고 가설(검증 대상이며 결론이 아님)**: 태그 수십 개 규모에서는 Python 상태머신이 코드량과 운영 부담에서 유리할 가능성이 큽니다. 대신 late·재시작 정확성을 직접 구현해야 하므로 버그 위험이 큽니다. Flink는 이 정확성을 엔진이 보장하는 대신 JVM·클러스터 부담이 큽니다. 이 트레이드오프는 아래 시나리오 S4·S5·S7의 정답률로만 판정할 수 있습니다.

**ML 이상탐지**: V1의 ONNX Autoencoder는 유지하고, 비교 대상은 "서빙 위치"(Flink 내부 vs 별도 Python 서비스) 한 가지로 좁힙니다. River(온라인 학습)와 PyOD/Isolation Forest는 동일 리플레이 데이터로 오프라인 비교(탐지 지연, 정밀도/재현율)만 수행합니다. 이 라이브러리들의 2025~2026 릴리스는 본 조사에서 확인하지 못했습니다[미확인].

#### A-4. 시계열/저장소 (L5) — 문헌으로 후보 축소 후 1회 실측

| 후보 | 핵심 사실 [문헌] | 판단 |
|---|---|---|
| InfluxDB 3 Core | 432파일(약 72h) 쿼리 제한, Flux 미지원\[59\]\[60\] | "사건 시점 ±수일 조회" 요구가 있으면 불리 |
| InfluxDB 2 | [미확인] 유지보수 상태 | V1과 같다면 기준선 |
| TimescaleDB(TigerData) | Apache 코어 + TSL(자체 호스팅 무료)\[42\] | **PostgreSQL 단일화 1순위 후보**(L5를 DB 1개로) |
| QuestDB / ClickHouse / GreptimeDB | [미확인] 이 규모에서는 과잉일 가능성 | 5일 일정에서 제외 권장 |

**PostgreSQL 단일화를 하면 잃는 것**: InfluxDB 라인 프로토콜의 간편한 Telegraf 연동, Grafana의 기존 Flux·InfluxQL 대시보드. **얻는 것**: 사건·승인·조치와 센서 이력을 한 트랜잭션·한 쿼리로 조인할 수 있고, 백업 대상이 하나로 줍니다. 이득이 가장 큰 곳은 감사 추적입니다.

#### A-5. HMI/SCADA vs Observability (L6) — 역할 분리를 문헌으로 정리

- **FUXA**: 운전원 HMI(제어 가능)로 유지합니다. 릴리스가 활발합니다[문헌].\[52\]
- **Grafana**: 관측·분석용입니다. 제어(쓰기) 경로로 쓰면 인터록·권한·감사 요구와 충돌할 수 있으므로 **제어 금지 원칙**을 권장합니다. 버튼 플러그인으로 쓰기는 기술적으로 가능하지만 이는 설계 원칙상의 판단입니다.
- **Prometheus/Alertmanager**: 인프라·서비스 상태(컨테이너 다운, 컨슈머 lag) 알람만 담당합니다. **공정 알람(ISA-18.2 대상)은 L4→PostgreSQL 사건 테이블로** 분리해 두 알람 체계가 섞이지 않게 합니다.
- Ignition Maker·Rapid SCADA·SCADA-LTS·Node-RED Dashboard 2.0은 5일 일정에서 비교하지 않을 것을 권장합니다. HMI 교체는 궤적의 핵심 질문(기술선정·온톨로지·시나리오)에 기여하는 정도가 작습니다.

#### A-6. 그래프/온톨로지/지식 (L7) — "DB 교체"가 아니라 "모델 품질" 문제로 재정의

기존 리서치가 저지른 오류(Neo4j vs JanusGraph 100만 노드)를 반복하지 않기 위해 비교 축을 바꿉니다. 설비 6대 규모에서 그래프 DB 성능은 의사결정 변수가 아닙니다. 비교 축은 **(1) competency question 응답률, (2) 근거(provenance) 완전성, (3) 스키마 변경 비용**입니다.

| 후보 | 사실 [문헌] | 역할 |
|---|---|---|
| Neo4j (V1) | [미확인] 버전 | 기준선 |
| PostgreSQL 관계형+재귀 CTE(+선택: AGE) | AGE는 PG11~18 지원, 소규모 팀\[46\]\[48\] | "DB 1개" 단일화 후보. 같은 CQ 세트로 비교 |
| Kuzu | 아카이브됨\[61\] | **탈락** |
| FalkorDB / Memgraph | [미확인] | 5일 일정에서 제외 |
| RDF(Oxigraph 등) + SOSA/SSN, PROV-O | [미확인] 버전 | V3 후보: 표준 어휘 재사용이 목적일 때만 |
| pgvector 결합(문서 청크 임베딩) | [미확인] 버전 | L7 문서 검색. 그래프와 같은 PostgreSQL에 두면 조인이 쉬움 |

### B. 온톨로지 개선 근거

**관련 표준의 역할 구분** (표준 원문은 유료이거나 본 조사에서 직접 확인하지 못했으므로, 모델링에 쓸 개념 수준으로만 요약합니다):
- **ISA-95**: 설비 계층(Enterprise–Site–Area–Work Center–Work Unit). 설비↔구성품 계층의 뼈대입니다.
- **ISA-88**: 배치 절차 모델(Procedure–Unit Procedure–Operation–Phase). "절차/조치"를 단계로 표현할 때 씁니다.
- **ISA-18.2 / IEC 62682**: 알람 수명주기(발생–인지–복귀–shelve 등)와 알람 합리화. "알람≠사건" 분리 근거입니다.
- **ISA-101**: HMI 설계 철학. FUXA 화면 개선의 근거입니다.
- **OPC UA 정보모델, AAS, DEXPI, ISO 15926**: 설비·P&ID 교환 표준. 이 규모에서는 **명명·식별자 규칙만 차용**하고 전체 모델 도입은 과잉일 가능성이 큽니다.
- **W3C SOSA/SSN**: Sensor–Observation–ObservableProperty–FeatureOfInterest. "관측 사실" 층의 표준 어휘입니다.
- **W3C PROV-O**: Entity–Activity–Agent, wasGeneratedBy·wasDerivedFrom·wasAssociatedWith. "AI 추론과 근거, 승인자" 추적의 표준 어휘입니다.

**최근 연구 사례 (2025~2026)**:
- Gill 등, "Leveraging LLM Agents and Digital Twins for Fault Handling in Process Plants"(IEEE ETFA 2025, arXiv 2505.02076):\[62\] 프로세스 플랜트 고장 대응에 LLM 에이전트와 디지털 트윈을 결합한 사례로, 본 프로젝트 구조와 가장 가깝습니다.
- "A Tutorial on Autonomous Fault-Tolerant Control Using Knowledge-Grounded LLM Agents"(arXiv 2606.31635): 지식그래프 구축이 "the dominant deployment cost"라고 지적합니다. P&ID·인터록 목록·운전범위·고장 카탈로그를 정규화해 표준 기반 온톨로지에 맞춰야 하고, 안전 관련 산출물의 자동 추출은 아직 "human-in-the-loop review"가 필요하다고 명시합니다. 스키마는 플랜트 독립적으로 재사용하고 인스턴스만 채우라고 권고합니다.\[63\]
- KG-DML 기반 복합 시스템 진단(arXiv 2505.21291): KG 내용을 매번 프롬프트에 넣지 않고, 에이전트가 상향·하향 전파 **도구**를 골라 구조적으로 추론합니다.\[64\] V1 L8 "조회도구" 설계에 직접 적용할 수 있습니다.
- Ma 등(IJPR 2025, KG 강화 LLM 고장진단·정비 의사결정)과 Liu 등(Engineering 2025, CNC 고장진단 LLM+KG): 제조 도메인의 KG-RAG 사례입니다.\[65\]\[66\] 성능 수치는 해당 논문의 자체 벤치마크 결과이므로 본 프로젝트의 기대치로 옮기면 안 됩니다.

**모델링 원칙 — 관측 사실과 AI 추론의 분리**:

| 층 | 클래스(예) | 규칙 |
|---|---|---|
| 자산 | Equipment(TK-101…), Component(임펠러·베어링), Sensor/Tag(TT-101…), ControlPoint(코일·레지스터) | ISA-95 계층, 식별자 불변 |
| 관측(사실) | Observation(값, 이벤트시간, 수집시간, 품질), CommandIssued, StateConfirmed | 기계가 만든 사실만 담습니다. 수정하지 않고 추가만 합니다 |
| 알람·사건 | Alarm(ISA-18.2 상태), Incident(여러 Alarm 묶음) | Alarm→Incident는 규칙 또는 사람이 연결합니다 |
| 추론(가설) | Hypothesis, CauseCandidate(신뢰도·불확실성), Evidence(→Observation/DocumentSection 링크) | 모든 추론에 `prov:wasGeneratedBy`(Agent 실행, 모델·프롬프트 버전)를 필수로 답니다 |
| 지식 | Procedure(ISA-88 단계), Document, **DocumentVersion**, Section | 근거는 버전 단위로 가리킵니다(문서 개정 후에도 당시 근거를 재현할 수 있도록) |
| 조치 | ActionProposal, Approval/Rejection(승인자, 시각, **승인 시점 조건 스냅샷**), Execution(명령), ExecutionResult(실제상태 확인) | Proposal→Approval→Recheck→Execution→Confirmation의 체인이 끊기지 않아야 합니다 |

**Competency Question(CQ) 기반 평가 방법** (V2·V3 비교의 정량 지표):
1. 운영자 관점 CQ를 15~30개 작성합니다. 예: "CV-101 배출밸브 명령 후 실제 상태가 바뀌지 않은 사건은?", "사건 X의 원인후보 Y를 뒷받침한 관측과 문서 버전은?", "반려된 조치안과 반려 사유는?", "승인 시점 조건과 실행 직전 재검사 조건이 달랐던 경우는?"
2. 각 CQ를 쿼리(Cypher/SQL)로 작성하고 **Answerability**(응답 가능한 CQ 비율)를 측정합니다[측정].
3. **Provenance completeness**: 모든 Hypothesis·Proposal 가운데 Evidence→Observation 또는 DocumentVersion 링크가 있는 비율을 봅니다[측정].
4. **분리 위반 수**: 추론 노드가 관측 층을 수정하거나 관측으로 위장한 건수를 셉니다. 목표는 0입니다[측정].
5. 스키마 변경 비용: 버전 간 마이그레이션 LOC와 소요시간[측정].

**V1→V2→V3 확장 예시** (확장 근거 = 응답하지 못한 CQ):
- V1: 설비↔센서↔문서.
- V2(근거: 알람·사건·승인 CQ에 답할 수 없음): Alarm/Incident, ActionProposal/Approval/Execution/ExecutionResult, DocumentVersion을 추가하고 PROV 링크를 필수화합니다.
- V3(근거: 원인 분석·명령 실패 CQ에 답할 수 없음): Component와 고장모드(CauseCandidate↔Component), Interlock(조건↔ControlPoint), SOSA식 Observation 품질 속성(late/duplicate 플래그), Hypothesis 불확실성을 추가합니다.

### C. 시나리오 개선 근거

**시나리오 카탈로그** (각각 입력·기대결과·판정 기준을 사전에 고정합니다. 결과는 실행 후 기록):

| ID | 시나리오 | 주입 방법 | 기대 결과(사전 정의) |
|---|---|---|---|
| S1 | 정상 운전 | 리플레이 기준 데이터 | 알람 0 |
| S2 | 단일 이상(TT-101 상승) | 값 주입 | threshold 알람 1 |
| S3 | 복합 이상(전류→N초 내 진동) | 순서대로 주입 | 패턴 알람 1 |
| S4 | 순서 역전(진동→전류) | 역순 주입 | 패턴 알람 0 |
| S5 | late event(진동이 워터마크 이후 도착) | 타임스탬프 지연 발행 | 후보별 정책 명시(폐기+side output 기록 등) |
| S6 | duplicate / missing | 중복 발행 / 샘플 드롭 | 중복 알람 없음, 결측은 품질 플래그로 표시 |
| S7 | 스트림 처리기 재시작(패턴 중간) | `docker kill` 후 재기동 | 패턴 상태 복구, 알람 누락·중복 없음 |
| S8 | 네트워크 단절(게이트웨이↔브로커) | Toxiproxy/Pumba | 재연결, 버퍼링 여부 기록 |
| S9 | DB 장애(PostgreSQL 다운) | 컨테이너 정지 | 승인·실행 차단(fail-closed) |
| S10 | 근거 문서 없음 | 문서 제거 | Agent가 "근거 없음"과 불확실성 표시, 조치안 제한 |
| S11 | 승인 반려 | UI 반려 | Modbus write 0건 |
| S12 | stale approval(승인 후 조건 변화) | 승인 대기 중 값 변경 | 재검사 실패 → 실행 거부 |
| S13 | 인터록 활성 중 명령 | 인터록 조건 주입 | 명령 차단 |
| S14 | Modbus write 실패 | Toxiproxy로 연결 끊기 | 실패 기록, 재시도 정책 |
| S15 | 명령 성공·상태 미변경 | 가상설비가 ACK만 하고 상태 유지 | HTTP /state 확인 실패 → "미확인" 사건 |
| S16 | 동일 승인 이중 제출 | 버튼 연타·재전송 | 실행 1회(idempotency) |

**공개 데이터셋 활용**:
- **SKAB**(Skoltech Anomaly Benchmark): 펌프·밸브 테스트베드 데이터입니다. GitHub README 기준 v0.9에 "34 datasets with collective anomalies"가 있고(파일 수는 35로도 표기), 300개 이상 파일을 더한 v1.0은 예고만 됐습니다.\[67\]\[68\] P-101·CV-101 시나리오와 구성이 가장 비슷해 **V2 리플레이 데이터로 1순위**입니다. 컬럼을 IT-102·VT-101 등으로 매핑하고 단위 차이는 스케일링으로 흡수합니다.
- **Tennessee Eastman Process**: 반응기 공정 고장 시나리오의 고전적 벤치마크입니다. R-101·HX-101 온도·압력 이상 패턴을 차용하는 데 적합합니다[출처 버전 미확인].
- **SWaT/WADI**(iTrust): 공격·이상 시나리오 데이터이며 신청 절차가 필요합니다[미확인]. 5일 안에는 확보가 어려울 수 있어 V3 이후를 권장합니다.
- 주의: 데이터셋 원본의 샘플링 주기·타임스탬프를 그대로 재생해야 late·순서 시나리오가 의미를 가집니다.

**장애주입 도구**: **Toxiproxy**(Shopify) 최신은 v2.12.0(2025-03-18)이고, TCP 프록시에 latency·timeout·연결 끊기 toxic을 넣을 수 있어\[69\]\[70\] Modbus TCP·MQTT·PostgreSQL 앞단에 두기 좋습니다. **Pumba**는 컨테이너 kill·netem 기반 장애주입 도구입니다[최신 버전 미확인]. 가장 단순한 방법은 `docker compose stop/kill`로 S7·S9를 재현하는 것입니다.

### D. 빠른 회전(바이브 코딩) 방법론

**병렬 구현 구조**:
- 후보마다 `git worktree add ../cand-flinkcep exp/l4-flinkcep` 식으로 독립 작업트리를 만들고, 각각에 AI 코딩 에이전트 세션을 하나씩 붙입니다. 후보 간 공유 코드는 `harness/`(리플레이어·측정기·시나리오 정의)뿐이며 읽기 전용으로 둡니다.
- 에이전트 프롬프트에는 "인터페이스 계약"을 고정해 넣습니다. 입력 토픽·스키마, 출력 토픽·스키마, 설정 파일 위치, `make test-scenarios` 통과 조건.

**공통 테스트 하니스**:
- 리플레이어: 고정 시드와 고정 데이터(SKAB 매핑본 + 합성 시나리오 S1~S16)를 **이벤트 시간 그대로** 발행합니다.
- 측정: 각 이벤트에 `trace_id`와 발행 시각을 넣고, 출력 토픽에서 수신 시각과 비교해 p50/p95/p99를 계산합니다. `docker stats` 샘플링으로 CPU·RAM을 기록하고, `cloc`으로 코드량, git 로그 타임스탬프로 구현 소요시간을 잽니다. OpenTelemetry를 붙일 수 있으면 L2→L9 구간별 지연을 분해합니다.
- 공정성: 같은 머신, 같은 compose 리소스 제한(`cpus`, `mem_limit`), 워밍업 후 측정, 3회 이상 반복한 중앙값, **한 회전에 한 모듈만 교체**(나머지는 V1 고정).

**가벼운 실험 로그/ADR 형식** (파일 1개, 실행 전후 작성):
```
EXP-ID / 날짜 / 담당(사람+에이전트)
질문: (예) L4 패턴탐지를 Python 상태머신으로 대체해도 S3~S7 정답을 유지하는가?
바꾼 변수(1개): 
고정 조건: 커밋 해시, compose 파일 해시, 데이터 해시, 리소스 제한
사전 정의 판정 기준: (예) Gate 전부 통과 + S3~S7 정답 + p95 ≤ 기준선
결과: [실행 후 기입]
결정: [채택/기각/보류] — 근거: [측정 로그 경로]
한계: (바이브 코딩 특유의 미검증 영역)
```

**바이브 코딩 PoC의 신뢰도 한계와 최소 보완 장치**:
- 한계: 에이전트는 테스트를 통과시키는 방향으로 코드를 짭니다. 테스트가 약하면 "동작하는 것처럼 보이는" 구현이 나옵니다. 예외 경로(재시작·late·실패)는 특히 비어 있기 쉽습니다. 따라서 **시나리오와 기대결과는 사람이 먼저 쓰고, 에이전트는 수정할 수 없게** 합니다(하니스 디렉터리 쓰기 금지).
- **안전·무결성 Gate(모든 후보·모든 회전 필수, 하나라도 실패하면 탈락)**:
  1. **G1 인터록**: S13에서 Modbus write가 0건인지 가상설비 로그로 확인합니다.
  2. **G2 반려 = 무제어**: S11에서 write가 0건인지 확인합니다.
  3. **G3 승인 후 재검사**: S12에서 실행 직전 최신값을 다시 읽고, 승인 시점 스냅샷과 비교해 불일치하면 거부하는지 확인합니다. 승인에는 만료 시각(TTL)을 둡니다.
  4. **G4 명령≠상태**: S15에서 HTTP /state 확인이 실패하면 "미확인"으로 기록하고 성공으로 기록하지 않는지 확인합니다.
  5. **G5 idempotency**: S16에서 승인 ID 기반 유니크 제약(PostgreSQL `UNIQUE(approval_id)`)으로 실행이 1회만 되는지 확인합니다.
  6. **G6 감사 추적**: 모든 실행에 Proposal→Approval→Recheck→Command→Confirmation 레코드가 있는지 확인합니다.

**워크플로우/HITL 후보 비교 시 주의 [문헌]**: LangGraph는 노드 안에서 `interrupt()`를 호출하면 체크포인트를 저장하고 멈추며, `Command(resume=...)`로 같은 thread에서 재개합니다. 운영 환경에서는 PostgresSaver 사용이 권장됩니다.\[71\]\[72\] 다만 **재개 시 노드가 처음부터 다시 실행되므로**, interrupt 이전 코드와 부작용(Modbus write)은 재실행에 안전해야 합니다(idempotent).\[73\]\[74\] 경쟁사인 Diagrid는 LangGraph가 같은 thread_id의 동시 재개를 막는 내장 조정 장치가 없다고 지적합니다(벤더\[75\] 주장이므로 S16으로 직접 확인). **결론**: 엔진이 무엇이든 G3·G5는 **PostgreSQL 트랜잭션과 제약조건으로 엔진 밖에서** 보장하는 설계를 권장합니다. 그래야 LangGraph·Temporal·DBOS·단순 상태머신을 비교할 때 안전 요구를 공통 조건으로 고정할 수 있습니다. Temporal·DBOS·Restate·Pydantic AI·OpenAI Agents SDK·Claude Agent SDK의 2026년 버전·기능은 본 조사에서 1차 확인하지 못했습니다[미확인]. 5일 일정에서는 **LangGraph(V1 기준선) vs 단순 상태머신+PostgreSQL** 두 후보만 비교할 것을 권장합니다.

**LLM 게이트웨이**: LiteLLM 사고(2026-03-24)를 감안해 두 후보를 비교합니다. (a) LiteLLM 유지(버전 고정, 해시 lock, 네트워크 격리 컨테이너), (b) SDK 직접 호출(모델 1~2개라면 게이트웨이 기능 대부분이 불필요). PyPI는 사고보고서에서 "checksums / hashes"를 포함한 lock 파일을 쓰라고 권고했습니다.\[49\] 다만 Snyk 분석에 따르면 1.82.8의 악성 `litellm_init.pth`는 wheel RECORD에 해시와 함께 정상 선언돼 있어 "pip install --require-hashes would have passed"였습니다. 해시 lock은 악성 버전이 올라온 뒤의 신규 해석만 막아 주므로, 핵심 방어는 검증된 버전 고정입니다. Portkey는 [미확인]입니다.

**배포/운영**: 단일 머신·5일 기준이면 Docker Compose를 유지하고, k3s는 비교하지 않을 것을 권장합니다. 이 규모에서 k3s가 풀어 주는 문제(멀티노드 스케줄링)가 요구사항에 없습니다.

---

## Recommendations

### 5영업일 실행 계획

**우선순위 판단**
- **실측 필수(불확실성·영향 모두 높음)**: L4 패턴탐지(Flink CEP vs MATCH_RECOGNIZE vs Python 상태머신), L1~L2 수집 경로(EdgeX vs Telegraf/pymodbus), L9 승인 워크플로우(LangGraph vs 상태머신+PG).
- **1회 실측(영향 중간)**: L5 PostgreSQL(+TimescaleDB) 단일화, L7 Neo4j vs PostgreSQL CQ 응답률.
- **문헌으로 결정(실측 생략)**: 브로커 라이선스(EMQX 단일 노드 유지 가능), 탈락 목록(ksqlDB·Bytewax·Kuzu·Esper/Siddhi), LiteLLM 보안 조치, Compose 유지, Grafana 제어 금지.

| Day | 목표 | 산출물 |
|---|---|---|
| Day 1 | 하니스 먼저: 리플레이어, S1~S16 정의와 기대결과, Gate G1~G6 자동 테스트, V1을 하니스로 측정(기준선) | `harness/`, V1 기준선 로그(측정값) |
| Day 2 | **회전 1**: worktree 병렬로 L4 후보 3개, L1~L2 후보 2개, L9 후보 2개 구현. 각 후보는 V1에서 해당 모듈만 교체 | 후보별 EXP 로그, Gate 결과 |
| Day 3 오전 | 회전 1 결과 비교 → **V2 확정**(모듈별 채택/기각 ADR). 온톨로지 V2(알람·사건·승인·PROV) 적용 | V2 태그, ADR |
| Day 3 오후~Day 4 | **회전 2**: SKAB 리플레이·late·재시작·장애주입으로 V2 재검증, L5 단일화·L7 CQ 비교, 온톨로지 V3 후보를 CQ 응답률로 검증 | EXP 로그, CQ 점수표 |
| Day 5 | **V3 확정** + 진화 궤적 보고서(아래 템플릿) 작성, 미해결 항목과 다음 회전 제안 | 궤적 보고서 |

- 일정이 밀리면 L5·L7 비교를 먼저 잘라 냅니다. L4와 Gate는 자르지 않습니다.
- 회전 1에서 Gate를 통과한 후보가 하나도 없는 모듈은 V1을 유지하고, 그 사실 자체를 궤적에 기록합니다(실패도 궤적입니다).

### 진화 궤적 보고서 템플릿 (결과값 미기입)

```
## 버전: V_ (날짜, 커밋 해시)

### 1. 변경 요약
- 교체/추가/제거 모듈:
- 변경 이유(이전 버전의 실패 시나리오·미응답 CQ):

### 2. 후보와 실험
| 모듈 | 후보 | EXP-ID | 바꾼 변수(1개) | 고정 조건 해시 |
|---|---|---|---|---|
|  |  |  |  |  |

### 3. 측정값 (실행 후 기입 — 비워둠)
| 후보 | Gate G1~G6 | S1~S16 정답 | p50 | p95 | p99 | CPU | RAM | LOC | 구현시간 |
|---|---|---|---|---|---|---|---|---|---|
|  |  |  |  |  |  |  |  |  |  |

### 4. 결정
- 채택/기각/보류:
- 근거(측정 로그 경로 + 문헌 근거 구분):
- 탈락 사유(문헌 기반인지 측정 기반인지 명시):

### 5. 온톨로지 변화
- 추가/변경 클래스·관계:
- CQ 응답률 (이전 → 현재): [기입]
- Provenance completeness: [기입]
- 분리 위반 수: [기입]

### 6. 시나리오 변화
- 추가된 시나리오와 추가 이유:
- 기대결과가 수정된 시나리오와 수정 사유:

### 7. 한계와 다음 회전 질문
```

---

## Caveats

- **미측정 수치 없음**: 이 보고서에는 지연·자원·정확도 수치가 하나도 없습니다. 이는 의도한 것이며, 모든 성능 판단은 Day 1~4 측정 후 템플릿에 기록해야 합니다.
- **[미확인] 표시 항목**: PLC4X, Mosquitto/NanoMQ/HiveMQ CE, RisingWave/Materialize/Timeplus, Quix Streams, River/PyOD, QuestDB/ClickHouse/GreptimeDB, Memgraph/FalkorDB/Oxigraph/GraphDB, Temporal/DBOS/Restate, 각종 Agent SDK, Portkey, Pumba의 2025~2026 최신 상태는 본 조사에서 1차 출처로 확인하지 못했습니다. 채택 전에 각 GitHub 릴리스 페이지를 확인해야 합니다.
- **출처 간 불일치**: LiteLLM 악성 버전의 노출 시간은 LiteLLM 공식 보안 공지("from 10:39 UTC for about 40 minutes"), Snyk(1.82.7 10:39 UTC·1.82.8 10:52 UTC 게시, "approximately three hours"), NHS(10:39→13:38 UTC 격리)가 서로 다릅니다. PyPI 공식 사고보고서의 다운로드 수(119k 이상)를 기준으로 삼을 것을 권장합니다.\[49\]
- **벤더·경쟁사 출처**: Arroyo 현황(Varpulis), LangGraph 동시성 한계(Diagrid), CEP 활용 홍보(Kai Waehner)는 이해관계가 있는 출처입니다. 방향성 참고로만 쓰고 결정 근거는 로컬 측정으로 대신해야 합니다.
- **계획과 사실 구분**: Kafka KIP-932는 4.2.0(2026-02-17)에서 production-ready로 확정됐습니다. Arroyo의 "오픈소스 유지"는 인수 시점의 약속입니다.\[38\]
- **표준 원문**: ISA-95/88/18.2/101, IEC 62682는 유료 표준이라 개념 수준으로만 요약했습니다. 조항 단위로 인용하려면 원문 확인이 필요합니다.
- **라이선스 해석**: EMQX BSL의 "embedded" 판단, Ignition Maker Edition의 사용 범위, TimescaleDB TSL의 적용 범위는 제품화 단계에서 법무 검토가 필요합니다. 이 보고서의 판단은 내부 프로토타입 기준입니다.

## 출처

1. [Bridging the Gap: Complex Event Processing on Stream Processing Systems](https://openproceedings.org/2024/conf/edbt/paper-114.pdf)
2. [Apache Flink 2.2.1 Release Announcement | Apache Flink](https://flink.apache.org/2026/05/15/apache-flink-2.2.1-release-announcement/)
3. [Pattern Recognition | Apache Flink](https://nightlies.apache.org/flink/flink-docs-stable/docs/dev/table/sql/queries/match_recognize/)
4. [siddhi-io/siddhi](https://github.com/siddhi-io/siddhi/issues)
5. [Market Guide for Event Stream Processing](https://www.gartner.com/en/documents/4010467)
6. [May 2023 Gartner® Market Guide for Event Stream Processing within Unified Real-Time Platforms. | Nstream](https://www.nstream.io/white-paper/2023-gartner-market-guide-event-stream-processing-unified-platform/)
7. [Flink CEP and Agentic AI: Real-Time Pattern Detection as the Foundation for Autonomous Decisions - Kai Waehner](https://www.kai-waehner.de/blog/2026/04/28/flink-cep-and-agentic-ai-real-time-pattern-detection-as-the-foundation-for-autonomous-decisions/)
8. [Event Processing (CEP) | Apache Flink](https://nightlies.apache.org/flink/flink-docs-stable/docs/libs/cep/)
9. [\[FLINK-16010\] Support notFollowedBy with interval as the last part of a Pattern - ASF JIRA](https://issues.apache.org/jira/browse/FLINK-16010)
10. [\[FLINK-33428\] Flink SQL CEP support 'followed','notNext' and 'notFollowedBy' semantics - ASF Jira](https://issues.apache.org/jira/browse/FLINK-33428)
11. [Pattern Recognition Queries in Confluent Cloud for Apache Flink | Confluent Documentation](https://docs.confluent.io/cloud/current/flink/reference/queries/match_recognize.html)
12. [Flink SQL MATCH\_RECOGNIZE: Complex Event Processing with SQL - Streamkap](https://streamkap.com/resources-and-guides/flink-sql-pattern-matching)
13. [EMQX Adopts Business Source License to Accelerate MQTT + AI Innovation | EMQ](https://www.emqx.com/en/news/emqx-adopts-business-source-license)
14. [EMQX 5.9 adopts Business Source License (BSL) · emqx/emqx · Discussion #15163](https://github.com/emqx/emqx/discussions/15163)
15. [EMQX Licensing FAQ | EMQ](https://www.emqx.com/en/content/license-faq)
16. [emqx/LICENSE at master · emqx/emqx](https://github.com/emqx/emqx/blob/master/LICENSE)
17. [blog/en/202505/adopting-business-source-license-to-accelerate-mqtt-and-ai-innovation.md at main · emqx/blog](https://github.com/emqx/blog/blob/main/en/202505/adopting-business-source-license-to-accelerate-mqtt-and-ai-innovation.md)
18. [Work with EMQX Enterprise License | EMQX Enterprise Docs](https://docs.emqx.com/en/emqx/latest/deploy/license.html)
19. [EdgeX Foundry Launches EdgeX 4.0 “Odesa”: The Most Secure and Industry-Ready Release Yet – LF EDGE: Building an Open Source Framework for the Edge.](https://lfedge.org/edgex-foundry-launches-edgex-4-0-odesa-the-most-secure-and-industry-ready-release-yet/)
20. [Our Latest Release | EdgeX Foundry, Open Source Edge Platform](https://www.edgexfoundry.org/software/releases/)
21. [Releases - EdgeX Wiki - Confluence](https://lf-edgexfoundry.atlassian.net/wiki/display/FA/Releases)
22. [GitHub - emqx/neuron: Open source industrial connectivity server · GitHub](https://github.com/emqx/neuron)
23. [EMQX Neuron — Modern Industrial Connectivity Server](https://www.emqx.com/en/products/emqx-neuron)
24. [Product Overview | EMQX Neuron Docs](https://docs.emqx.com/en/neuronex/latest/)
25. [Redpanda Licenses and Enterprise Features | Redpanda Streaming](https://docs.redpanda.com/streaming/current/get-started/licensing/overview/)
26. [Data Integration Platform & Connectors | Redpanda Connect](https://www.redpanda.com/connect)
27. [Enterprise Licensing | Redpanda Connect](https://docs.redpanda.com/redpanda-connect/get-started/licensing/)
28. [Apache Kafka 4.0.0 Released: KRaft, Queues, Better Rebalance Performance](https://softwaremill.com/apache-kafka-4-0-0-released-kraft-queues-better-rebalance-performance/)
29. [Kafka 4.0 Changes Streaming Platform Operations](https://datalakehousehub.com/blog/2026-05-kafka-streaming-operations/)
30. [CNCF and Synadia settle NATS dispute](https://www.theregister.com/2025/05/02/cncf_synadia_nats/)
31. [Protecting NATS and the integrity of open source: CNCF’s commitment to the community | CNCF](https://www.cncf.io/blog/2025/05/01/protecting-nats-and-the-integrity-of-open-source-cncfs-commitment-to-the-community/)
32. [Synadia and the NATS project | Synadia](https://www.synadia.com/blog/nats-server-next-steps)
33. [Kafka Streams vs ksqlDB: Honest Guide | Conduktor](https://www.conduktor.io/kafka-streams/vs-ksqldb)
34. [Flink SQL vs ksqlDB: Which Stream SQL Engine Should You Use? - Streamkap](https://streamkap.com/resources-and-guides/flink-sql-vs-ksqldb)
35. [The Past and Present of Stream Processing (Part 20): Bytewax — The Burned-Out Data Candle | by Gang Tao | Medium](https://taogang.medium.com/the-past-and-present-of-stream-processing-part-20-bytewax-the-burned-out-data-candle-760223db6b64)
36. [GitHub - bytewax/bytewax: Python Stream Processing · GitHub](https://github.com/bytewax/bytewax)
37. [Bytewax | LLMS3](https://llms3.com/node/bytewax)
38. [Arroyo is joining Cloudflare | Arroyo blog](https://www.arroyo.dev/blog/arroyo-is-joining-cloudflare/)
39. [Varpulis — Rust Stream Processing for Real-Time Detection](https://varpulis-cep.com/docs/comparisons/varpulis-vs-arroyo.html)
40. [Timescale alternatives in 2026: TigerData, Tiger Cloud, and QuestDB | Layerbase](https://layerbase.com/blog/timescale-alternatives)
41. [TimescaleDB](https://en.wikipedia.org/wiki/TimescaleDB)
42. [Software Licensing: Timescale License (TSL) | Tiger Data](https://www.tigerdata.com/legal/licenses)
43. [What Is KuzuDB?](https://www.puppygraph.com/blog/what-is-kuzudb)
44. [Kuzu’s Legacy and the New Wave of Embedded Graph Databases | gdotv](https://gdotv.com/blog/kuzu-legacy-embedded-graph-database-landscape/)
45. [Kuzu — Graph Embedded Database | GDB-Engines](https://gdb-engines.com/db/kuzu/)
46. [2026 roadmap, release cadence, and PG17/PG18 support (production) · apache/age · Discussion #2305](https://github.com/apache/age/discussions/2305)
47. [Re: \[I\] PostgreSQL 17 not supported \[age\]](https://www.mail-archive.com/dev@age.apache.org/msg07438.html)
48. [GitHub - apache/age: Graph database optimized for fast analysis and real-time data processing. It is provided as an extension to PostgreSQL. · GitHub](https://github.com/apache/age)
49. [Incident Report: LiteLLM/Telnyx supply-chain attacks, with guidance - The Python Package Index Blog](https://blog.pypi.org/posts/2026-04-02-incident-report-litellm-telnyx-supply-chain-attack/)
50. [How a Poisoned Security Scanner Became the Key to Backdooring LiteLLM | Snyk](https://snyk.io/blog/poisoned-security-scanner-backdooring-litellm/)
51. [Your AI Gateway Was a Backdoor: Inside the LiteLLM Supply Chain Compromise | TrendAI (US)](https://www.trendmicro.com/en_us/research/26/c/inside-litellm-supply-chain-compromise.html)
52. [Releases · frangoteam/FUXA](https://github.com/frangoteam/FUXA/releases)
53. [Home · frangoteam/FUXA Wiki · GitHub](https://github.com/frangoteam/FUXA/wiki/)
54. [GitHub - frangoteam/FUXA: Web-based Process Visualization (SCADA/HMI/Dashboard) software · GitHub](https://github.com/frangoteam/FUXA)
55. [Ignition SCADA](https://en.wikipedia.org/wiki/Ignition_SCADA)
56. [Kafka 4.0 & KRaft: The End of ZooKeeper - Java Code Geeks](https://www.javacodegeeks.com/2026/02/kafka-4-0-kraft-the-end-of-zookeeper.html)
57. [Kafka 4.0: ZooKeeper Is Finally Gone, and Queues Arrived](https://codefarm.in/blog/kafka/kafka-4-zookeeper-gone-queues-arrived)
58. <https://nightlies.apache.org/flink/flink-docs-master/docs/libs/cep/>
59. [Query data | Get started with InfluxDB 3 Core | InfluxDB 3 Core Documentation](https://docs.influxdata.com/influxdb3/core/get-started/query/)
60. [Announcing InfluxDB 3 Enterprise free for at-home use and an update on InfluxDB 3 Core’s 72-hour limitation | InfluxData](https://www.influxdata.com/blog/influxdb3-open-source-public-alpha-jan-27/)
61. [KuzuDB to FalkorDB Migration - FalkorDB](https://www.falkordb.com/blog/kuzudb-to-falkordb-migration/)
62. [Automating Cause-Effect Specification with Knowledge Graphs and Large Language Models](https://arxiv.org/pdf/2606.31614)
63. [A Tutorial on Autonomous Fault-Tolerant Control Using Knowledge-Grounded LLM Agents](https://arxiv.org/pdf/2606.31635)
64. [Complex System Diagnostics Using a Knowledge Graph ...](https://arxiv.org/pdf/2505.21291)
65. [Agent-based Condition Monitoring Assistance with Multimodal Industrial Database Retrieval Augmented Generation](https://arxiv.org/pdf/2506.09247)
66. [Intelligent Fault Diagnosis for CNC Through the Integration of Large Language Models and Domain Knowledge Graphs](https://www.engineering.org.cn/engi/EN/10.1016/j.eng.2025.04.003)
67. [SKAB/README.md at master · waico/SKAB](https://github.com/waico/SKAB/blob/master/README.md)
68. [An Evaluation of Anomaly Detection and Diagnosis in Multivariate Time Series](https://arxiv.org/pdf/2109.11428)
69. [GitHub - Shopify/toxiproxy at v2.1.4 · GitHub](https://github.com/Shopify/toxiproxy/tree/v2.1.4)
70. [Toxiproxy - Browse /v2.12.0 at SourceForge.net](https://sourceforge.net/projects/toxiproxy.mirror/files/v2.12.0/)
71. [langgraph-persistence | Claude Skills & Agent Skills Library](https://mcpservers.org/agent-skills/langchain-ai/langgraph-persistence)
72. [LangGraph Persistence: Checkpointers & Memory | AI/TLDR](https://ai-tldr.dev/learn/agent-frameworks/langchain-ecosystem/langgraph-persistence-checkpointers/)
73. [LangGraph 201: Adding Human Oversight to Your Deep Research Agent | Towards Data Science](https://towardsdatascience.com/langgraph-201-adding-human-oversight-to-your-deep-research-agent/)
74. [Durable Execution for AI Agent Runtimes: Checkpointing, Replay, and Recovery | Zylos Research](https://zylos.ai/research/2026-04-24-durable-execution-agent-runtimes/)
75. [Why Checkpoints Aren't Durable Execution: LangGraph](https://www.diagrid.io/blog/checkpoints-are-not-durable-execution-why-langgraph-crewai-google-adk-and-others-fall-short-for-production-agent-workflows)
