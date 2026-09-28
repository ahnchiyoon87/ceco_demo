# 01 · 수집·브로커·중계 파이프 후보 넓게 훑기 (2026-09-29)

- 확인일: 모든 사실은 **2026-09-29**에 확인했다(GitHub releases.atom·git 태그·Docker Hub/GHCR 태그 API·공식 문서).
- 이번 문서는 문헌·저장소 기준 **① 관문**(버전·라이선스·공식 이미지·EOL·무료판 기능)만 판정한다. 성능은 판정하지 않았다. 성능은 직접 시험에서 잰다.
- 분류: **직접시험** = 문헌상 관문 통과, 실제 설치 시험 필요 / **관문제외** = 라이선스·약관·EOL·공식 컨테이너 부재가 사실로 확인됨 / **관문 미결** = 관문 사실 하나가 [미확인]
- 이미 실측한 항목: Mosquitto 2.1.2 조건부 우세, NanoMQ·HiveMQ CE 우리 시험 실패. 이 문서는 그 결과를 뒤집지 않는다.

## 0 · V1 구성요소 최신 상태

| V1 구성요소 | 최신 버전(날짜) | 라이선스 | 공식 이미지 | EOL/패치 | 같은 제품 최신판 판정 | 근거 URL |
|---|---|---|---|---|---|---|
| EdgeX Foundry | 4.0.2 "Palau"(2026-05-29). 4.1은 `v4.1.0-dev.132`(2026-09-16)까지 개발 태그만 있음. 다음 정식판 Queensland는 2027년 봄 예정 | Apache-2.0 | `edgexfoundry/core-data:4.0.2` 등 | 4.0 LTS 지원은 **2027-03까지**(12개월 안에 종료) | **직접시험**: 4.0.2(같은 LTS 안의 패치) | https://github.com/edgexfoundry/edgex-go/releases/tag/v4.0.2 · https://lf-edgexfoundry.atlassian.net/wiki/display/FA/Releases · https://www.edgexfoundry.org/software/releases/ |
| EMQX(V1 5.8.6) | 오픈소스 5.8은 **2026-02-28 EOL**. 현재 6.3 LTS(2026-09-03), 최신 패치는 Enterprise(LTS) 6.3.1(2026-09-18) | 5.9부터 **BSL 1.1**. 단일 노드 운영만 무료이고 클러스터는 상용 라이선스 필요. 각 버전은 4년 뒤 Apache-2.0으로 바뀜 | `emqx/emqx:6.3` | 5.8 OSS는 보안 패치와 공식 패키지 배포가 끝남 | **관문제외**(5.8 OSS는 EOL, 6.x는 BSL) | https://www.emqx.com/en/news/a-notice-on-the-emqx-5-8-open-source-version · https://www.emqx.com/en/content/license-faq · https://docs.emqx.com/en/emqx/latest/changes/eol-ee.html |
| Telegraf | 1.40.1(2026-09-21). 1.40.0은 2026-09-07 | MIT | `telegraf:1.40.1-alpine` | 1.39·1.40 지원 중. 1.38은 2026-09-07 EOL. 분기마다 새 버전이 나오며 한 버전은 약 9개월 지원됨 | **직접시험**: 1.40.x | https://github.com/influxdata/telegraf/releases · https://endoflife.date/telegraf |
| FUXA | 1.3.4(2026-08-12) | MIT | `frangoteam/fuxa:1.3.4` | 아래 보안 수정 목록 참고. **1.3.4 이상 필수** | **직접시험**: 1.3.4 | https://github.com/frangoteam/FUXA/releases |
| Mosquitto(이미 실측) | 2.1.2(2026-02-09). 이후 릴리스 없음 | EPL-2.0 OR EDL-1.0(BSD-3) | `eclipse-mosquitto:2.1.2-alpine` | EOL 공지 없음 [미확인: 공식 지원 기간] | 기존 실측 유지 | https://github.com/eclipse-mosquitto/mosquitto/releases · https://mosquitto.org/blog/2026/01/version-2-1-0-released/ |

**FUXA 보안 수정 버전**

| CVE | 영향 | 수정 버전 |
|---|---|---|
| CVE-2025-69970 | 1.2.7 기본 설정에서 인증이 꺼짐 | [미확인: 정확한 수정판] |
| CVE-2025-69971 | 1.2.7 JWT 비밀키 하드코딩 | [미확인] |
| CVE-2025-69985 | 1.2.8 이하 Referer 헤더 스푸핑으로 인증 우회 후 RCE(CVSS 9.8) | 1.2.9 이후 [미확인: 정확한 판] |
| CVE-2025-69981 | 제한 없는 파일 업로드 | [미확인] |
| CVE-2026-25751 | 정보 노출 | 1.2.10 |
| CVE-2026-25938 | 1.2.8~1.2.10 Node-RED 플러그인 인증 우회 후 RCE | 1.2.11 |
| CVE-2026-47719(SSRF), CVE-2026-47720(SQLi) | — | 1.3.2 |
| CVE-2026-67440, 67443(CVSS 9.2), 65984, 65985 | ≤1.3.2 Socket.IO 무인증 정보 노출·권한 누락·SSRF | 1.3.3 |
| (CVE 번호 없음) | 1.3.4 릴리스 노트: 관리자 Socket.IO 응답 범위 제한, 무단 API 접근 수정 | 1.3.4 |

근거: https://www.strix.ai/cve/CVE-2025-69985 · https://github.com/advisories/GHSA-7g56-fwxj-cm23 · https://www.sentinelone.com/vulnerability-database/cve-2026-67440/ · https://www.strix.ai/cve/CVE-2026-67443 · https://github.com/frangoteam/FUXA/releases

## 1 · 수집 계층(Modbus TCP → MQTT)

| 후보 | 최신 버전(날짜) | 라이선스 | 공식 이미지 | EOL/패치 | 분류 | 근거 URL |
|---|---|---|---|---|---|---|
| Telegraf `inputs.modbus` | 1.40.1(2026-09-21). 플러그인은 1.14부터 제공 | MIT | `telegraf` | 위와 같음 | **직접시험**. Modbus TCP 클라이언트, MQTT·Kafka 출력, InfluxDB·PostgreSQL 출력이 모두 무료 | https://docs.influxdata.com/telegraf/v1/input-plugins/modbus/ |
| Neuron(EMQ) | git 태그 2.15.0(2026-06-03). Docker Hub 최신은 **2.13.0(2025-12-18)**이며 2.14·2.15 이미지는 없음(404) | LGPL-3.0. 핵심 프레임워크와 Modbus·MQTT·eKuiper 플러그인이 OSS | `emqx/neuron:2.13.0` | OSS 대시보드는 2.6.3에서 개발·유지보수 중단 | **직접시험**. 이미지와 소스 버전이 어긋나는 점에 주의 | https://github.com/emqx/neuron · https://hub.docker.com/r/emqx/neuron/tags |
| Node-RED + node-red-contrib-modbus | Node-RED 5.0.7(2026-09-08), 4.1.15(2026-09-09). contrib-modbus 5.60.2(2026-08-14) | Apache-2.0 / BSD-3-Clause | `nodered/node-red` | 4.x는 버그·보안 수정만 받는 유지보수 모드. 5.0은 2026-06 출시 | **직접시험** | https://nodered.org/blog/2026/06/09/version-5-0-released · https://www.npmjs.com/package/node-red-contrib-modbus |
| **HiveMQ Edge**(새 후보) | 2026.14(2026-09-15) | Apache-2.0 | `hivemq/hivemq-edge:2026.14` | 월 단위 릴리스 | **직접시험**. OSS에 Modbus TCP·S7·OPC UA 어댑터, MQTT 3/5 브로커, 양방향 MQTT 브리지 포함. 오프라인 버퍼(저장 후 전달)와 Data Hub는 상용 키가 필요함. 같은 회사 제품이지만 CE와는 별개 제품 | https://github.com/hivemq/hivemq-edge · https://docs.hivemq.com/hivemq-edge/index.html |
| **benthos-umh**(새 후보) | v0.16.0(2026-09-23) | Apache-2.0 | `ghcr.io/united-manufacturing-hub/benthos-umh` | 활발히 개발 중 | **직접시험**. Benthos 계열 위에 Modbus·S7·OPC UA·Sparkplug 입력 추가. 도구 하나로 수집과 MQTT·Kafka·SQL 출력까지 처리할 수 있음 | https://github.com/united-manufacturing-hub/benthos-umh |
| UMH Core(United Manufacturing Hub) | v0.44.41(2026-09-24) | 저장소는 Apache-2.0. 다만 **Redpanda 브로커(BSL 1.1)**를 함께 묶어 배포함 | `ghcr.io/united-manufacturing-hub/umh-core` | 활발히 개발 중 | **관문제외**(BSL 구성요소 포함. EMQX를 제외한 기준과 같음). 관리 콘솔은 클라우드 서비스이며 약관 [미확인] | https://docs.umh.app/ · https://github.com/redpanda-data/redpanda/blob/dev/licenses/bsl.md |
| Apache PLC4X(+extras Kafka Connect) | 1.0.0(2026-09-07), extras 1.0.0(2026-09-22) | Apache-2.0 | Docker Hub에 `apache/plc4x` 없음. Kafka Connect 커넥터는 소스에서 빌드해야 함 | 활발히 개발 중 | **관문 미결**: 공식 컨테이너가 없음. 자체 빌드를 허용하면 재평가 | https://github.com/apache/plc4x/releases · https://plc4x.apache.org/plc4x/latest/users/integrations/apache-kafka.html |
| Apache StreamPipes | 0.98.0(2025-12-15) | Apache-2.0 | `apachestreampipes/backend:0.98.0` 등 | 릴리스 간격이 약 10개월 | **직접시험**. PLC4X 기반 Modbus 어댑터와 Kafka 출력 [미확인: 0.98 어댑터 목록] | https://github.com/apache/streampipes/releases |
| ThingsBoard IoT Gateway | 3.8.5(2026-09-17) | Apache-2.0 | `thingsboard/tb-gateway:3.8.5` | 활발히 개발 중 | **관문 미결**: Modbus 커넥터는 OSS. 하지만 상위 연결이 ThingsBoard 서버 전용인지, 일반 MQTT 브로커로도 보낼 수 있는지 [미확인] | https://github.com/thingsboard/thingsboard-gateway |
| OpenRemote | 1.31.1(2026-09-28) | AGPL-3.0(OSI) | [미확인: 공식 이미지 이름. 문서상 `openremote/manager`] | 활발히 개발 중 | **직접시험**(플랫폼 전체라 수집기 하나만 교체하는 것보다 범위가 큼). Modbus TCP/RTU 에이전트 포함 | https://docs.openremote.io/docs/user-guide/agents-protocols/modbus/ |
| Eclipse Kura | 5.6.2(2026-07-08) | EPL-2.0 | [미확인] | 활발히 개발 중 | **관문제외**. Modbus 드라이버는 Eurotech ESF 패키지이며, EULA가 "비전문(개발·시험·시연) 용도"로만 허용함 | https://marketplace.eclipse.org/content/modbus-master-driver-v2 |
| EdgeX 4.0.2(V1 같은 제품) | 0장 참고 | Apache-2.0 | `edgexfoundry/*` | LTS가 2027-03 종료 | **직접시험**(같은 제품 최신판) | 0장 |

## 2 · 브로커 계층

| 후보 | 최신 버전(날짜) | 라이선스 | 공식 이미지 | EOL/패치 | 분류 | 근거 URL |
|---|---|---|---|---|---|---|
| Mosquitto | 2.1.2(2026-02-09) | EPL-2.0/EDL | `eclipse-mosquitto` | 0장 참고 | 실측 완료(조건부 우세). OSS에 dynsec ACL, SQLite 영속화, Sparkplug-aware 플러그인 포함. **Kafka 브리지는 Cedalo Pro(상용) 전용** | https://mosquitto.org/blog/2026/01/version-2-1-0-released/ · https://www.cedalo.com/blog/mqtt-to-kafka-integration |
| EMQX 6.x | 6.3.1 LTS(2026-09-18) | BSL 1.1 | `emqx/emqx` | 6.3 LTS는 2029-09까지 지원 | **관문제외**(BSL, 클러스터는 상용) | 0장 |
| **RMQTT**(새 후보) | 0.24.0(2026-09-19) | MIT | `rmqtt/rmqtt:0.24.0` | 1.0 이전, 월 단위 릴리스 | **직접시험**. OSS에 내장·HTTP·JWT 인증/ACL과 **Kafka egress 브리지** 포함 | https://github.com/rmqtt/rmqtt |
| **TBMQ**(ThingsBoard) | 2.4.0(2026-08-27) | Apache-2.0 | `thingsboard/tbmq:2.4.0` | 활발히 개발 중 | **직접시험**. 내부 저장소로 Kafka를 씀. CE에도 Integration Executor(Kafka·HTTP·MQTT 출력) 포함. 대신 Kafka·PostgreSQL·Redis가 필요함 | https://github.com/thingsboard/tbmq · https://thingsboard.io/docs/mqtt-broker/integrations/kafka/ |
| **Apache BifroMQ**(인큐베이팅) | 4.0.0-incubating(2026-01-28) | Apache-2.0 | `apache/bifromq:4.0.0-incubating` | 릴리스 간격이 김 | **직접시험**. 인증과 ACL은 플러그인(AuthProvider)으로 구현해야 함 [미확인: 기본 제공 수준] | https://github.com/apache/bifromq |
| VerneMQ | 2.2.1(2026-09-23) | 소스는 Apache-2.0 | `vernemq/vernemq:2.2.1` | 활발히 개발 중 | **관문제외**(공식 이미지와 바이너리를 상업적으로 쓰려면 유료 구독이 필요한 EULA). 직접 빌드한 이미지로만 재평가 가능 | https://github.com/vernemq/docker-vernemq/blob/master/README.md |
| RabbitMQ(MQTT 플러그인) | 4.3.6(2026-09-14) | MPL-2.0 | `rabbitmq` | 커뮤니티 패치는 **최신 마이너 계열만** 받음 | **직접시험** | https://github.com/rabbitmq/rabbitmq-server/blob/main/COMMUNITY_SUPPORT.md |
| LavinMQ | 2.10.0(2026-09-25) | Apache-2.0 | `cloudamqp/lavinmq:2.10.0` | 활발히 개발 중 | **직접시험**. MQTT는 3.1.0·3.1.1만 지원(MQTT 5 없음). 세션은 디스크에 영속화 | https://github.com/cloudamqp/lavinmq |
| NATS Server(MQTT) | 2.15.0(2026-09-17) | Apache-2.0 | `nats` | 활발히 개발 중 | **직접시험**. MQTT 3.1.1만 지원, QoS 0/1/2, JetStream 필수 | https://docs.nats.io/running-a-nats-service/configuration/mqtt |
| ActiveMQ Artemis | 2.57.0(2026-09-09) | Apache-2.0 | `apache/activemq-artemis`. Docker Hub 최신 태그는 2.44.0(2025-11)이라 저장소 릴리스와 어긋남 [미확인: 이미지 배포 위치] | 활발히 개발 중 | **직접시험** | https://github.com/apache/activemq-artemis |
| ActiveMQ Classic | 6.3.2(2026-09-02) / 6.2.10 | Apache-2.0 | [미확인] | 활발히 개발 중 | **직접시험**(우선순위 낮음) | https://github.com/apache/activemq |
| Mochi-MQTT | 2.7.9(2025-03-01) | MIT | `mochimqtt/server:2.7.9` | EOL 공지는 없지만 **18개월째 릴리스 없음** | **직접시험**(유지보수 위험을 기록함) | https://github.com/mochi-mqtt/server |
| RobustMQ | 0.4.11(2026-07-31) | Apache-2.0 | [미확인: Docker Hub `robustmq/robustmq` 태그 없음] | 1.0 이전 | **관문 미결**(공식 이미지 [미확인]) | https://github.com/robustmq/robustmq |
| FlashMQ | 1.27.2(2026-09-28) | OSL-3.0(OSI) | **공식 이미지 없음**. README에 "Official Docker images aren't available yet"라고 적혀 있음 | 활발히 개발 중 | **관문제외**(컨테이너 없음. 자체 빌드를 허용하면 재평가) | https://github.com/halfgaar/FlashMQ |
| Eclipse Amlen | 정식판 1.0.0.2(2024-02-07). 이후는 `main` 빌드만 있음 | EPL-2.0 | `quay.io/amlen/amlen-server:main`(버전 고정 태그 [미확인]) | 2년 넘게 정식 릴리스 없음 | **관문 미결** | https://github.com/eclipse/amlen |
| comqtt | v2.6.5(2026-07-11) | [미확인] | [미확인] | — | **관문 미결** | https://github.com/wind-c/comqtt |
| Aedes | 1.2.0(2026-09-16) | MIT | 라이브러리라 공식 브로커 이미지 없음 | — | **관문제외**(컨테이너 없음. 라이브러리) | https://www.npmjs.com/package/aedes |
| Moquette | 0.18.x(2026-08) | Apache-2.0 | 공식 이미지 없음(Docker Hub `moquette/moquette` 없음) | — | **관문제외**(컨테이너 없음. 임베드용) | https://github.com/moquette-io/moquette |
| Waterstream | — | 상용(개발 라이선스 발급 필요) | `waterstreamio/waterstream-kafka` | — | **관문제외**(상용) | https://waterstream.io/ |
| Cedalo Pro Mosquitto | — | 상용 | — | — | **관문제외**(상용. Kafka 브리지가 여기에만 있음) | https://www.cedalo.com/pro-mosquitto/broker |
| NanoMQ / HiveMQ CE | 0.25.6(2026-08-19) / 2026.5(2026-05-27) | MIT / Apache-2.0 | `emqx/nanomq`, `hivemq/hivemq-ce` | — | 기존 시험에서 실패(변동 없음) | 각 GitHub releases |
| HiveMQ Edge(내장 브로커) | 1장 참고 | Apache-2.0 | 1장 참고 | — | **직접시험**(수집과 브로커를 하나로 합치는 안) | 1장 |

## 3 · 중계 파이프(MQTT → Kafka → InfluxDB/HMI, 알람 → PostgreSQL)

| 후보 | 최신 버전(날짜) | 라이선스 | 공식 이미지 | EOL/패치 | 분류 | 근거 URL |
|---|---|---|---|---|---|---|
| Telegraf 1대로 통합 | 1.40.1 | MIT | `telegraf` | 0장 참고 | **직접시험**. `mqtt_consumer`·`kafka_consumer` 입력과 `kafka`·`influxdb_v2`·`mqtt`·`postgresql` 출력이 모두 OSS | https://github.com/influxdata/telegraf |
| Redpanda Connect | v4.111.0(2026-09-25) | 무료 번들은 Apache-2.0. `mqtt`·`kafka_franz`·`sql_insert` 소스 헤더가 Apache-2.0임을 확인. 엔터프라이즈 커넥터는 키가 없으면 막힘 | `docker.redpanda.com/redpandadata/connect` | 주 단위 릴리스 | **직접시험**(Apache 구성요소만 사용) | https://github.com/redpanda-data/connect · https://docs.redpanda.com/redpanda-connect/get-started/licensing/ |
| **Bento**(WarpStream 포크, 새 후보) | v1.21.2(2026-09-11) | MIT | `ghcr.io/warpstreamlabs/bento` | 활발히 개발 중 | **직접시험**. MQTT·Kafka·SQL(PostgreSQL) 모두 포함, 엔터프라이즈 잠금 없음 | https://github.com/warpstreamlabs/bento |
| benthos-umh | 1장 참고 | Apache-2.0 | 1장 참고 | — | **직접시험**(수집부터 중계까지 도구 하나로 처리) | 1장 |
| **LF Edge eKuiper**(새 후보) | v2.4.2(2026-09-09). 2.2.x 유지보수판 2.2.8 | Apache-2.0 | `lfedge/ekuiper` | 활발히 개발 중 | **직접시험**. MQTT 소스와 SQL 규칙이 내장이라 **알람 워커를 대체할 후보**. Kafka·InfluxDB·SQL 싱크는 플러그인. Modbus 소스는 없음 | https://ekuiper.org/docs/en/latest/guide/sinks/overview.html |
| Lenses Stream Reactor(Kafka Connect MQTT source) | 12.1.2(2026-09-15) | Apache-2.0 | 전용 이미지 없음. Kafka Connect 런타임에 플러그인으로 올림 [미확인: 권장 이미지] | 12.x는 **Kafka 4.0 이상 필요** | **직접시험**(V1 Kafka 버전 확인 필요) | https://github.com/lensesio/stream-reactor · https://docs.lenses.io/latest/connectors/kafka-connectors/sources/mqtt |
| Confluent MQTT Source Connector | — | 상용. 30일 체험 후 구독 필요(단일 브로커 개발 라이선스는 예외) | — | — | **관문제외** | https://docs.confluent.io/kafka-connectors/mqtt/current/mqtt-source-connector/overview.html |
| Apache NiFi | 2.12.0(2026-09-13) | Apache-2.0 | `apache/nifi:2.12.0` | 활발히 개발 중 | **직접시험**(무거움). ConsumeMQTT·PublishKafka·PutDatabaseRecord 프로세서 사용 | https://github.com/apache/nifi |
| Vector | 0.58.0(2026-08-26) | MPL-2.0 | `timberio/vector` [미확인: 현재 공식 이미지 이름] | 활발히 개발 중 | **직접시험**. MQTT 소스는 **beta**이고 ack 미지원(best effort). Kafka 싱크 있음 | https://vector.dev/docs/reference/configuration/sources/mqtt/ |
| Fluent Bit | 5.1.2(2026-09-05) | Apache-2.0 | `fluent/fluent-bit` | 활발히 개발 중 | **관문제외**(필요 기능 없음). MQTT 입력은 브로커를 구독하는 클라이언트가 아니라 **서버로 동작**해 EdgeX·브로커 토픽을 구독할 수 없음 | https://docs.fluentbit.io/manual/data-pipeline/inputs/mqtt |
| RMQTT·TBMQ 내장 Kafka 출력 | 2장 참고 | MIT / Apache-2.0 | 2장 참고 | — | **직접시험**(Telegraf #1 제거안) | 2장 |
| Kapacitor(알람) | 1.8.7(2026-09-16) | MIT | `kapacitor` | 유지보수 릴리스가 계속 나옴 | **직접시험**(알람 워커 대체 후보). PostgreSQL 기록 경로는 [미확인] | https://github.com/influxdata/kapacitor |
| RisingWave | v3.1.0(2026-09-21) | Apache-2.0 | `risingwavelabs/risingwave` | 활발히 개발 중 | **직접시험**(구조 대안). MQTT 소스를 SQL 스트리밍 뷰로 처리하고 PostgreSQL 프로토콜로 제공 [미확인: MQTT 커넥터 무료 여부] | https://github.com/risingwavelabs/risingwave |

## 4 · 구조 패턴(경로를 줄이는 안)

| 패턴 | 줄어드는 것 | 이 패턴을 구현하는 후보(관문 통과) | 주의 |
|---|---|---|---|
| A. 수집기가 MQTT(UNS)에 바로 발행 | EdgeX 컨테이너 10개를 수집기 하나로 대체 | Telegraf modbus→mqtt, Neuron, Node-RED, benthos-umh, HiveMQ Edge | FUXA가 같은 MQTT 토픽을 구독하게 바꾸면 **이중 폴링 해소**. 단 FUXA의 MQTT 구독 방식은 FUXA 쪽 문서에서 확인 필요 |
| B. 수집기와 브로커를 하나로 | 수집기와 브로커를 합침 | HiveMQ Edge(Modbus 어댑터와 브로커 내장) | 저장 후 전달 기능은 상용 |
| C. 브로커 내장 Kafka 브리지 | Telegraf #1(MQTT→Kafka) 제거 | RMQTT(Kafka egress/ingress), TBMQ(Integration Executor) | Mosquitto OSS에는 없음(Pro 전용). EMQX는 BSL |
| D. Kafka Connect MQTT source | Telegraf #1을 Connect 작업으로 대체 | Lenses Stream Reactor(Apache) | Kafka 4.0 이상. Confluent판은 상용 |
| E. 파이프 도구 하나로 여러 경로 처리 | Telegraf 3대를 설정 하나로 | Telegraf 1대, Redpanda Connect(Apache), Bento, benthos-umh | 경로마다 장애가 격리되지 않음. 시험에서 확인 |
| F. 수집기가 DB에 직접 기록 | Kafka→InfluxDB 구간 생략 | Telegraf modbus→influxdb_v2/postgresql, Bento·benthos-umh sql 출력 | Kafka를 재생(replay) 버퍼로 둘지는 설계 결정 사항 |
| G. 규칙 엔진으로 알람 처리 | Python 알람 워커 대체 | eKuiper(SQL 규칙), Node-RED, Kapacitor | eKuiper의 SQL 싱크는 플러그인 |
| H. Sparkplug B 페이로드·상태 관리 | 토픽 구조와 생사 판정 규격화 | Eclipse Tahu 1.0.21(2026-07-27, EPL-2.0, 라이브러리), Mosquitto 2.1 Sparkplug-aware 플러그인, benthos-umh Sparkplug 입력 | Tahu는 라이브러리라 이미지 없음 |
| I. EdgeX 경량화(같은 제품) | core-data 등 비활성화, MQTT 메시지 버스 직결 | EdgeX 4.0.2 | 어떤 서비스를 끌 수 있는지 [미확인]. LTS가 2027-03 종료 |

## 5 · 확인 못 한 것

- EdgeX 4.0 LTS가 끝나는 정확한 날짜(검색 요약에는 "2027-03", 원문 LTS 페이지는 직접 확인 못 함). 4.1 정식 출시 여부(현재는 dev 태그만 있음).
- Mosquitto 2.1 계열의 공식 지원 기간.
- FUXA CVE-2025-69970/69971/69981/69985의 정확한 수정 버전.
- Neuron 2.14·2.15의 공식 컨테이너 배포 여부(Docker Hub에는 없음. 다른 레지스트리는 확인 안 함).
- ActiveMQ Artemis의 최신 Docker 이미지 배포 위치. ActiveMQ Classic 공식 이미지.
- RobustMQ·comqtt의 라이선스와 이미지. Amlen의 버전 고정 이미지.
- BifroMQ 4.0 기본 인증/ACL 제공 수준.
- ThingsBoard IoT Gateway를 일반 MQTT 브로커에 연결할 수 있는지.
- OpenRemote·Vector 공식 이미지 이름. Stream Reactor에 권장되는 Connect 런타임 이미지.
- StreamPipes 0.98의 Modbus 어댑터 목록. RisingWave MQTT 커넥터가 무료판에 있는지. Kapacitor→PostgreSQL 경로.
- UMH 관리 콘솔 약관.
- FUXA가 MQTT 토픽 구독으로 폴링을 대체할 수 있는지(HMI 문서에서 확인 필요).
- 한국어 산업 사례(“EMQX 대안”) 검색에서는 쓸 만한 1차 자료가 나오지 않았다.
