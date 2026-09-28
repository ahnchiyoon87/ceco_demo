# 02 · 백본·스트림처리·HA 광역 조사 (2026-09-29 기준)

대상 층: 백본(Kafka 3.9.0 KRaft 단일) · 스트림처리/이상탐지(Flink 1.20.1 세션, HA 없음, SQL 규칙 3 + ONNX DataStream 1).
조사 방식: 공식 릴리스 피드(GitHub releases.atom)·Docker Hub 태그 API·공식 문서·endoflife.date·Apache Incubator/Attic 페이지·2025–2026 기사. **실행 시험 없음(문헌 조사)**. 성능 추정으로 제외하지 않았다.

분류 기준
- **직접 시험 대상**: 라이선스(OSI)·공식 컨테이너·12개월 내 EOL 아님이 문헌으로 확인됨. 기능 적합성은 시험으로 판정.
- **① 관문 제외**: 라이선스/약관(BSL·상용·비OSI)·EOL/은퇴/장기 무릴리스·컨테이너 불가(쿠버네티스 전용) **사실**만으로 제외. 근거 URL 병기.
- 날짜는 릴리스 피드/Docker Hub 기준(UTC). `[미확인]`은 이번 조사에서 1차 출처로 확인 못 한 값.

---

## 0. 버전·EOL 핵심 (질문 3 답)

| 항목 | 사실 | 근거 |
|---|---|---|
| Kafka 3.9 | 최종 패치 3.9.2(2026-02-21), **지원 종료 2027-02-19** → 오늘 기준 약 5개월 남음(12개월 내 EOL) | https://endoflife.date/apache-kafka |
| Kafka 4.0 / 4.1 | 4.0 지원 종료 2027-06-11(12개월 내) / 4.1 종료 2027-10-15(약 12.5개월, 경계) | 같은 곳 |
| Kafka 4.2 / 4.3 | 4.2.1(2026-05-28), 종료 2028-03-04 / **4.3.1(2026-06-23) 최신 안정**, 종료 2028-06-17. Docker Hub에 4.2.2(2026-09-28), 4.4.0-rc2 진행 중 | endoflife.date, https://hub.docker.com/r/apache/kafka/tags |
| Kafka 4.x 파괴적 변경 | ZooKeeper 모드 제거(KRaft만) · 브로커 Java 17 · KIP-896로 2.1 미만 클라이언트 프로토콜 제거 · MirrorMaker1 제거. V1은 이미 KRaft라 경로는 단순 | https://kafka.apache.org/40/getting-started/upgrade/ |
| Telegraf↔Kafka 4 | 출력 플러그인 JoinGroup v1 거부 이슈 #16691 → PR #16707로 종료. 입력 kafka_consumer 이슈 #17570(sarama 1.45.2, 2025-09)은 "waiting for response"로 닫힘, 해결 버전 문서 없음 → **직접 시험 필수** | https://github.com/influxdata/telegraf/issues/16691 , https://github.com/influxdata/telegraf/issues/17570 |
| Flink 1.20 LTS | 1.20.0 2024-08-01, 최신 1.20.5(2026-06-03). FLIP-458: "fixed period of two years" → **명목 종료 ≈2026-08** (이미 경과). 공식 종료일 공지는 [미확인]. 연장 여부 [미확인] | https://cwiki.apache.org/confluence/display/FLINK/FLIP-458:+Long-Term+Support+for+the+Final+Release+of+Apache+Flink+1.x+Line , https://flink.apache.org/downloads/ |
| Flink 2.x | **2.3.0(2026-06-25) 최신**, 2.2.1(2026-05-15), 2.1.3(2026-06-14, 2.3 출시로 지원 종료 정책 대상), 2.0 EOL(2026-06-25). 정책: "current and previous minor"만 버그픽스 → 2.3/2.2만 지원 | https://flink.apache.org/2026/06/25/apache-flink-2.3.0-release-announcement/ , https://flink.apache.org/downloads/ , https://eosl.date/eol/product/apache-flink/ |
| Flink 공식 이미지 | Docker 공식 `flink`: 2.3.0 / 2.2.1 / 1.20.5 태그(java11/17/21, 2026-09-26 재빌드) | https://hub.docker.com/_/flink |
| Flink Kafka 커넥터 | 최신 5.0.0 = Flink 2.1/2.2 호환으로 표기. **2.3용 커넥터 여부 [미확인]** → 2.3 채택 시 첫 시험 항목 | https://flink.apache.org/downloads/ |
| ZooKeeper(HA용) | current 3.9.6 / stable 3.8.7, 공식 이미지 `zookeeper:3.9.5` | https://zookeeper.apache.org/releases.html |

→ **V2 기준선 제안(문헌)**: Kafka 4.2/4.3 + Flink 2.2.1(커넥터 확인됨) 또는 2.3.0(커넥터 확인 후). Kafka 3.9·Flink 1.20은 유지 대상이 아니라 갱신 대상.

---

## 1. 백본 층

| 후보 | 최신 버전(날짜) | 라이선스 | 공식 이미지 | EOL/패치 | 필요 기능(Telegraf·Flink 연동/재시작) | 분류 | 근거 URL |
|---|---|---|---|---|---|---|---|
| Apache Kafka 4.3 | 4.3.1 (2026-06-23) | Apache-2.0 | `apache/kafka` | 종료 2028-06-17 | Telegraf in/out, Flink 공식 커넥터, 로그 재생·오프셋 재개 | **직접 시험 대상** | https://endoflife.date/apache-kafka |
| Apache Kafka 4.2 | 4.2.1 (2026-05-28), 4.2.2 이미지(2026-09-28) | Apache-2.0 | `apache/kafka` | 종료 2028-03-04 | 동일 | **직접 시험 대상** | 같은 곳 |
| Apache Kafka 3.9(현행) | 3.9.2 (2026-02-21) | Apache-2.0 | `apache/kafka` | **2027-02-19 종료(12개월 내)** | — | ① 관문 제외(갱신 대상) | 같은 곳 |
| Apache Kafka 4.0 | 4.0.2 (2026-03-18) | Apache-2.0 | `apache/kafka` | 2027-06-11 종료 | — | ① 관문 제외 | 같은 곳 |
| AutoMQ | 1.7.4 (2026-08-29), 1.7.5-rc1 | Apache-2.0(오픈소스판). UI·RBAC·저지연 WAL 등은 BYOC 상용 | `automqinc/automq` | 활발 | Kafka 코드 재사용(프로토콜 호환). S3 호환 저장소 필요(MinIO) | 직접 시험 대상 | https://docs.automq.com/automq/what-is-automq/licensing |
| Tansu | 0.6.0 (2026-03-13), 0.7.0-pre.2 | Apache-2.0 | ghcr 이미지 [미확인] | 1.0 이전 | Kafka API 호환(Rust), 저장소 선택(S3/Postgres 등) | 직접 시험 대상(1.0 이전 주의) | https://github.com/tansu-io/tansu/releases |
| Apache Iggy | 0.9.0 (2026-09-18), 2026-08 TLP 졸업 | Apache-2.0 | `apache/iggy` | 활발, VSR 클러스터 | 자체 프로토콜(Kafka 비호환). Telegraf 플러그인·Flink 커넥터 [미확인] | 직접 시험 대상(연동 공백 확인 필요) | https://iggy.apache.org/blogs/2026/09/21/release-0.9.0/ |
| NATS Server + JetStream | 2.15.0 (2026-09-17) | Apache-2.0 (2025-05 CNCF–Synadia 합의로 BSL 전환 철회) | `nats` 공식 | 활발 | Telegraf nats_consumer/nats 출력, 서버 내장 MQTT, Flink 커넥터는 Synadia 제3자(`io.synadia:flink-connector-nats` 2.2.0, at-least-once) | 직접 시험 대상 | https://www.cncf.io/announcements/2025/05/01/cncf-and-synadia-align-on-securing-the-future-of-the-nats-io-project/ , https://mvnrepository.com/artifact/io.synadia/flink-connector-nats |
| Apache Pulsar 4.0 LTS | 4.0.13 (2026-08-03) | Apache-2.0 | `apachepulsar/pulsar` | 활성 2026-10-21, 보안 2027-10-21 | Pulsar Functions(경량 처리), KoP/MoP(Kafka/MQTT 프로토콜 핸들러). Flink 2.x Pulsar 커넥터 [미확인] | 직접 시험 대상(5.0 LTS 대기 권장) | https://endoflife.date/apache-pulsar |
| Apache Pulsar 4.2 | 4.2.4 (2026-08-03) | Apache-2.0 | 동일 | **지원 종료 2026-09-24** | — | ① 관문 제외 | 같은 곳 |
| Apache Pulsar 5.0 | 5.0.0-M2 (2026-09-18, 마일스톤) | Apache-2.0 | `5.0.0-M2` 태그 | 차기 LTS, 정식 미출시 | — | 정식 출시 후 직접 시험 | https://pulsar.apache.org/contribute/release-policy/ |
| Apache RocketMQ | 5.5.0 (2026-05-04 이미지) | Apache-2.0 | `apache/rocketmq` | 활발 | MQTT 프록시·Flink 커넥터 존재(버전 호환 [미확인]), Telegraf 플러그인 없음 [미확인] | 직접 시험 대상(연동 공백) | https://hub.docker.com/r/apache/rocketmq/tags |
| RabbitMQ Streams | 4.3.6 (2026-09-14) | MPL-2.0 | `rabbitmq` 공식 | 커뮤니티 지원은 최신 minor만 | MQTT 플러그인 내장, Streams(로그형). Flink 공식 커넥터 없음 [미확인] | 직접 시험 대상 | https://github.com/rabbitmq/rabbitmq-server/releases |
| Apache Fluss | 1.0.0 (2026-09-22), 2026-08-06 TLP | Apache-2.0 | `apache/fluss` | 활발 | Flink 전용 스트리밍 저장소(Kafka 프로토콜 아님 → Telegraf 직결 불가) | 직접 시험 대상(Flink 내부 저장 용도로만) | https://fluss.apache.org/blog/apache-fluss-graduates-to-top-level-project/ |
| Redpanda 브로커 | — | BSL | — | — | — | ① 관문 제외(기존 결정) | — |
| Bufstream | — | 상용(쓰기 GiB당 라이선스료) | — | — | Kafka 호환 | ① 관문 제외 | https://buf.build/pricing |
| WarpStream | — | 독점(제어평면 벤더 관리, Confluent 인수) | — | — | Kafka 호환 | ① 관문 제외 | https://www.automq.com/blog/warpstream-after-confluent-acquisition-what-changed |

### 1-b. MQTT 전용 백본 후보(브로커)

| 후보 | 최신 버전(날짜) | 라이선스 | 공식 이미지 | EOL/패치 | 필요 기능 | 분류 | 근거 URL |
|---|---|---|---|---|---|---|---|
| Eclipse Mosquitto | 2.1.2 (2026-02-09) | EPL-2.0/EDL-1.0 | `eclipse-mosquitto` | 활발 | 파일 영속, 클러스터 없음. 재생(replay) 불가 → 소비자 다운 시 QoS1 세션 보관만 | 직접 시험 대상 | https://github.com/eclipse-mosquitto/mosquitto/releases |
| NanoMQ | 0.25.6 (2026-08-19) | MIT | `emqx/nanomq` | 활발 | 경량, 내장 룰엔진·브리지 | 직접 시험 대상 | https://github.com/nanomq/nanomq/releases |
| HiveMQ CE | 2026.5 (2026-05-27) | Apache-2.0 | `hivemq/hivemq-ce` | 활발 | 단일 노드(클러스터는 상용) | 직접 시험 대상 | https://github.com/hivemq/hivemq-community-edition/releases |
| Apache BifroMQ | 4.0.0-incubating (2026-01-28) | Apache-2.0 | [미확인] | 인큐베이팅 | 멀티테넌트 MQTT | 직접 시험 대상 | https://github.com/apache/bifromq/releases |
| VerneMQ | 2.2.1 (2026-09-23) | 소스 Apache-2.0, **공식 이미지·바이너리는 EULA(상업 사용 시 유료 구독)** | `vernemq/vernemq` | 활발 | 클러스터 | ① 관문 제외(공식 이미지 약관). 소스 자체 빌드 시 재검토 가능 | https://vernemq.com/blog/2019/11/26/vernemq-end-user-license-agreement.html |
| EMQX ≥5.9 (현 6.x) | 6.3.1 LTS (2026-09-18) | **BSL 1.1**(단일 노드 운영 무료 허용, 클러스터는 라이선스 필요) | `emqx/emqx` | 활발 | — | ① 관문 제외(BSL) | https://www.emqx.com/en/news/emqx-adopts-business-source-license |

---

## 2. 스트림 처리·이상탐지 층

필요 기능 약어: **ET**=이벤트시간 윈도우+워터마크, **CEP**=패턴(MATCH_RECOGNIZE/CEP 라이브러리), **ONNX**=ONNX 실행 또는 UDF 경로, **EO/ALO**=exactly/at-least-once, **재시작**=일반 Docker Compose(무 K8s)에서 재시작 후 상태 복구.

| 후보 | 최신 버전(날짜) | 라이선스 | 공식 이미지 | EOL/패치 | 필요 기능 | 분류 | 근거 URL |
|---|---|---|---|---|---|---|---|
| Apache Flink 2.3 | 2.3.0 (2026-06-25) | Apache-2.0 | `flink:2.3.0` | 현 minor | ET·CEP(MATCH_RECOGNIZE/CEP lib)·ONNX(Java UDF/DataStream)·EO. 재시작: ZK HA 또는 체크포인트 수동 복원(§3). Kafka 커넥터 2.3 호환 [미확인] | **직접 시험 대상** | https://flink.apache.org/2026/06/25/apache-flink-2.3.0-release-announcement/ |
| Apache Flink 2.2 | 2.2.1 (2026-05-15) | Apache-2.0 | `flink:2.2.1` | 2.4 출시 시 종료(정책상 약 6개월 주기) | 위와 동일, Kafka 커넥터 5.0.0 호환 명시. V1 규칙 동일 알람 기확인 | **직접 시험 대상** | https://flink.apache.org/2026/05/15/apache-flink-2.2.1-release-announcement/ |
| Apache Flink 1.20 LTS(현행) | 1.20.5 (2026-06-03) | Apache-2.0 | `flink:1.20.5` | 2년 LTS 명목 종료 ≈2026-08 | — | ① 관문 제외(갱신 대상) | FLIP-458 URL(§0) |
| Kafka Streams | Kafka 4.3.1 동봉 | Apache-2.0 | 라이브러리(앱 이미지 자작) | Kafka와 동일 | ET(윈도우+grace)·CEP 없음(상태 저장소로 직접 구현)·ONNX(Java onnxruntime)·EO(exactly_once_v2)·재시작: changelog 토픽으로 상태 복원, 컨테이너 재시작만으로 복구 | 직접 시험 대상 | https://kafka.apache.org/42/streams/upgrade-guide/ |
| LF Edge eKuiper | 2.4.2 (2026-09-09, Latest), 2.2.8 패치(2026-09-18), 2.5.0-alpha.1 | Apache-2.0 | `lfedge/ekuiper` | 활발(2 브랜치 병행 패치) | **MQTT 직접 소스**, SQL 규칙, ET(isEventTime+lateTolerance), 카운트/세션/상태 윈도우·분석함수(CEP 전용 문법 없음), **ONNX 함수 플러그인**, QoS0/1/2 체크포인트. 제약: 싱크 정확히-1회 보장 안 함, MQTT 소스 되감기 불가 → 다운 중 이벤트는 브로커 세션에 의존 | **직접 시험 대상** | https://ekuiper.org/docs/en/latest/guide/ai/onnx.html , https://ekuiper.org/docs/en/latest/guide/rules/state_and_fault_tolerance.html |
| RisingWave | 3.1.0 (2026-09-21) | Apache-2.0(Premium 기능은 라이선스 키) | `risingwavelabs/risingwave` | 활발 | ET(워터마크+tumble/hop)·CEP/MATCH_RECOGNIZE [미확인]·UDF(Python/Java/JS/Rust; ONNX는 외부 UDF 서버 경로 추정 [미확인])·MQTT 소스(technical preview, QoS 선택). 재시작: 단일 노드 standalone 체크포인트 복구. 무료판 잠금: Console·time travel·일부 싱크 등(윈도우/UDF/워터마크는 잠금 목록에 없음) | 직접 시험 대상 | https://docs.risingwave.com/get-started/premium-features , https://docs.risingwave.com/integrations/sources/mqtt |
| Timeplus Proton | 3.0.31 (2026-09-17) | Apache-2.0(클러스터·NATS 등 확장 커넥터는 Enterprise) | `timeplus/proton`, `d.timeplus.com/timeplus-io/proton` | 활발 | ET(tumble/hop/session, 워터마크)·Python/JS UDF(onnxruntime 임포트 가능 여부 [미확인])·MV 증분 체크포인트 복구·CEP [미확인]·MQTT 소스 없음(Kafka 경유) | 직접 시험 대상 | https://github.com/timeplus-io/proton , https://docs.timeplus.com/materialized-view |
| Arroyo | 0.15.0 (2025-12-01), 0.16 예고(2026-09 블로그) | Apache-2.0 (Cloudflare 인수 후에도 OSS 유지 명시) | `ghcr.io/arroyosystems/arroyo` | 릴리스 간격 10개월 | ET·**MQTT 소스/싱크**·Rust/Python 스칼라 UDF(ONNX는 Rust `ort` 경유 가능성 [미확인])·체크포인트·단일 바이너리. CEP 없음 | 직접 시험 대상 | https://www.arroyo.dev/blog/arroyo-is-joining-cloudflare/ , https://doc.arroyo.dev/connectors/mqtt |
| Quix Streams | 3.26.0 (2026-09-14) | Apache-2.0 | 라이브러리(파이썬 앱 이미지 자작) | 활발 | ET(tumbling/hopping/sliding+grace)·**Python이라 onnxruntime 직결**·EO(Kafka 트랜잭션)·RocksDB+changelog 복구·MQTT 소스/싱크 커넥터. Kafka 필수 | 직접 시험 대상 | https://github.com/quixio/quix-streams/releases , https://quix.io/docs/quix-streams/connectors/sinks/mqtt-sink.html |
| Feldera | 0.357.0 (2026-09-27) | MIT | `images.feldera.com/feldera/pipeline-manager` | 매우 잦음(0.x) | 증분 SQL(DBSP), LATENESS/윈도우, Rust UDF, Kafka 커넥터, 결함허용은 preview | 직접 시험 대상 | https://github.com/feldera/feldera |
| Apache StreamPipes | 0.98.0 (2025-12-15), 0.99.0-SNAPSHOT 이미지 | Apache-2.0 (TLP, 2022-11 졸업) | `apachestreampipes/*` | 9개월 무릴리스(스냅샷은 활발) | **산업용 IoT 전용**: OPC-UA/PLC/MQTT/Kafka 어댑터, GUI 파이프라인, 내장 NATS/Kafka. ET·CEP·ONNX [미확인] | 직접 시험 대상 | https://streampipes.apache.org/download/ |
| Siddhi | 5.1.33 (2026-05-05) | Apache-2.0 | 러너 이미지 [미확인] | 저빈도 | CEP(패턴·시퀀스)·윈도우·파일 스냅샷 영속·Java 확장 | 직접 시험 대상(이미지 확인 선행) | https://github.com/siddhi-io/siddhi/releases |
| Apache Storm | 3.1.0 (2026-09-12) | Apache-2.0 | `storm` 공식 | 활발 | 이벤트시간 윈도우 볼트, CEP 없음, Java UDF, Nimbus+ZK 필요 | 직접 시험 대상 | https://github.com/apache/storm/releases |
| Hazelcast (Jet) | 5.7.0 (2026-05-13) | Apache-2.0 + Hazelcast Community License 혼합 | `hazelcast/hazelcast` | 커뮤니티판 CVE는 minor 릴리스에서만 | 이벤트시간 윈도우, Java/Python 매핑. 디스크 영속(재시작 복구)은 Enterprise [미확인 범위] | 직접 시험 대상(무료판 잠금 확인 선행) | https://hazelcast.com/blog/changes-to-community-edition/ |
| Redpanda Connect | 4.111.0 (2026-09-25) | Apache-2.0 + RCL(엔터프라이즈 커넥터) | `redpandadata/connect` | 활발 | MQTT↔Kafka 브리지·경량 변환, 윈도우 버퍼, 상태 복구 제한 | 직접 시험 대상(브리지 용도) | https://github.com/redpanda-data/connect/tree/main/licenses |
| Bento (Benthos 포크) | 1.21.2 (2026-09-11) | MIT | 이미지 [미확인] | 활발 | 위와 유사(무상태 중심) | 직접 시험 대상(브리지 용도) | https://github.com/warpstreamlabs/bento/releases |
| Apache Beam | 2.77.0-RC2 (2026-09-22) | Apache-2.0 | SDK 이미지 | 활발 | API 계층 — Flink 러너 등 필요(백엔드 대체 아님) | 직접 시험 대상(우선순위 낮음) | https://github.com/apache/beam/releases |
| Esper | 9.0.0 (2024-04-26) | GPL-2.0(상용 별도) | 없음 | **29개월 무릴리스**, 재시작 복구는 상용 EsperHA 전용 | CEP 최강, 영속 없음 | ① 관문 제외(패치 부재·HA 상용) | https://www.espertech.com/esper/esper-faq/ , https://github.com/espertechinc/esper/releases |
| Bytewax | 0.21.1 (2024-11-25) | Apache-2.0 | `bytewax/bytewax`(2025-03) | 회사 중단(2025-05), 22개월 무릴리스 | — | ① 관문 제외(유지보수 중단) | https://github.com/bytewax/bytewax |
| Pathway | 0.33.0 (2026-09-18) | **BSL 1.1** | — | — | — | ① 관문 제외(BSL) | https://pathway.com/license |
| Numaflow | 1.8.4 (2026-09-10) | Apache-2.0 | — | — | **쿠버네티스 네이티브 전용** | ① 관문 제외(Compose 불가) | https://numaflow.numaproj.io/ |
| Fluvio + SDF | Fluvio 0.18.1 (2025-07-04), fluvio-community 이관 중 | Fluvio Apache-2.0 / Stateful DataFlow는 InfinyOn 독점 | 이관 중 | 15개월 무릴리스 | — | ① 관문 제외(처리엔진 독점·릴리스 공백) | https://github.com/fluvio-community/fluvio , https://infinyon.com/docs/resources/stateful-dataflows-concepts/ |
| Apache Samza | 1.8.0 (2023-01-17) | Apache-2.0 | — | 3년 무릴리스 | — | ① 관문 제외 | https://samza.apache.org/ |
| Apache Heron | 0.20.5 (2022) | — | — | 인큐베이터 은퇴 2023-01-18 | — | ① 관문 제외 | https://incubator.apache.org/projects/heron.html |
| Materialize | — | BSL | — | — | — | ① 관문 제외(기존 결정) | — |

참고(층 경계 밖): Apache IoTDB 2.0.11(2026-09-13, `apache/iotdb`)은 Pipe·트리거·UDF를 가진 시계열 DB로, 처리 일부를 저장층에 흡수하는 패턴 후보(§4-5).

---

## 3. Flink HA — Docker Compose(무 K8s) 선택지

공식 HA 서비스는 **ZooKeeper와 Kubernetes 두 가지뿐**, 파일 기반 HA는 없음(`high-availability.type` = ZOOKEEPER/KUBERNETES/팩토리 FQCN). 출처: https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/deployment/ha/overview/ , 설정 키 확인: https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/deployment/config/

| 방식 | 구성 | 복구 범위 | 비용·주의 | 판정 |
|---|---|---|---|---|
| A. ZooKeeper HA + 세션 모드 | `zookeeper:3.9` 1대 + JM 2대(리더/대기) + TM, `high-availability.type: zookeeper`, `high-availability.storageDir`·`execution.checkpointing.dir`을 **공유 볼륨(file://)**, `high-availability.cluster-id` 지정 | JM 장애/재시작 시 제출된 잡(SQL 포함)을 최신 체크포인트에서 재개 — 문서: "can be used with every Flink cluster deployment" | 컨테이너 +2(ZK, 대기 JM). 단일 호스트라 공유 볼륨으로 충분 | 직접 시험 대상(1순위) |
| B. ZooKeeper HA + 애플리케이션 모드 | 잡별 JM 컨테이너, HA 활성 | 잡 ID 고정, 체크포인트 재개 | 잡 4개면 JM 4개. 2.3의 "application" 개념 변경 영향 [미확인] | 직접 시험 대상 |
| C. HA 없음 + 보존 체크포인트 + 재기동 스크립트 | `execution.checkpointing.externalized-checkpoint-retention: RETAIN_ON_CANCELLATION`, 재기동 시 최신 `chk-*`를 찾아 `execution.state-recovery.path`(2.x 키, 구 savepoint.path) 또는 `--fromSavepoint`로 제출 | 상태 복구되나 **자동이 아님**(래퍼 스크립트가 책임) | ZK 불필요. 스크립트 결함이 곧 유실 | 직접 시험 대상 |
| D. 오프셋 재개 폴백 | Kafka 소스 `scan.startup.mode = group-offsets`, 체크포인트 시 오프셋 커밋 | 윈도우 상태는 잃지만 **이벤트는 건너뛰지 않음**(재집계) — V1의 11–12건 유실 유형 완화 가능성 | 윈도우 경계 결과 오차 가능 | 직접 시험 대상(C/A의 보조) |
| E. 커스텀 HA 팩토리 | FQCN 지정(제3자 구현) | — | 유지 가능한 공개 구현 [미확인] | 보류 |
| F. Kubernetes HA / Operator 1.16.1 | — | — | K8s 필수 | 범위 밖 |

주의: Flink 문서 Docker 페이지는 HA 구성을 다루지 않음(수동 `--fromSavepoint`만 언급) — Compose HA 예제는 공식에 없음, 직접 구성·검증 필요.

---

## 4. 구조 패턴 (경로 단축)

| # | 패턴 | 구성 예 | 얻는 것 | 잃는 것/검증 포인트 | 근거 |
|---|---|---|---|---|---|
| 1 | 엣지 SQL 규칙 + MQTT 직결 | Telegraf/장비 → MQTT → **eKuiper**(SQL 규칙 + ONNX 플러그인) → MQTT/HTTP | Kafka·Flink 동시 제거 가능, Go 단일 프로세스 | MQTT 재생 불가(다운 중 이벤트는 브로커 QoS1 세션 의존), 싱크 중복 가능, CEP 전용 문법 없음 | eKuiper 문서(§2) |
| 2 | 스트림 DB가 MQTT 직독 | MQTT → **RisingWave**(MQTT 소스) 또는 **Arroyo**(MQTT 소스) → 싱크 | 백본 제거 + SQL MV로 규칙 표현 | MQTT 소스 preview/재생 불가 → 재시작 유실 가능 | §2 URL |
| 3 | 백본 유지·처리 경량화 | Kafka 4.x → **Kafka Streams** 또는 **Quix Streams**(Python+onnxruntime) | 클러스터 없는 라이브러리, changelog 복구, EO | CEP 직접 구현, SQL 규칙 → 코드 | §2 URL |
| 4 | 백본 경량 교체 | NATS JetStream(내장 MQTT) → Flink(Synadia 커넥터, ALO) | 브로커 하나로 MQTT+스트림 | Flink 커넥터가 제3자·ALO | §1 URL |
| 5 | 저장층 흡수 | Telegraf → IoTDB/시계열DB의 트리거·UDF로 임계 규칙 | 처리층 축소 | 이벤트시간 윈도우·CEP 표현력 [미확인] | https://github.com/apache/iotdb/releases |
| 6 | 하이브리드 | 단순 임계 규칙은 eKuiper(엣지), ONNX·CEP는 Flink 2.2(ZK HA) | 규칙/모델 분리, Flink 부하·잡 수 감소 | 두 엔진 운영 | — |
| 7 | 산업 IoT 올인원 | Apache StreamPipes(OPC-UA/MQTT 어댑터 + GUI 파이프라인 + 내장 브로커) | 수집·처리·저장 일체 | 커스텀 ONNX/CEP 경로 [미확인], 릴리스 9개월 공백 | §2 URL |

---

## 5. 확인 못 한 것

- [미확인] Flink 1.20 LTS 공식 종료일(FLIP-458의 2년만 확인, 연장 공지 못 찾음).
- [미확인] flink-connector-kafka의 Flink 2.3 호환 릴리스.
- [미확인] Telegraf 최신판 kafka_consumer가 Kafka 4.x에서 정상 소비하는지(#17570 해결 근거 없음) — 실측 필요.
- [미확인] Flink 2.2 `ML_PREDICT`의 ONNX 로컬 모델 제공자 존재 여부(OpenAI 계열만 확인).
- [미확인] RisingWave·Proton의 MATCH_RECOGNIZE/CEP 지원, embedded Python UDF에서 onnxruntime 임포트 가능 여부.
- [미확인] Arroyo 단일 노드 재시작 시 파이프라인 자동 체크포인트 복구, 0.16 정식 출시일.
- [미확인] Hazelcast 커뮤니티판에서 잡 스냅샷 디스크 영속(전체 재시작 복구) 가능 범위.
- [미확인] Siddhi·Tansu·Bento·BifroMQ 공식 컨테이너 이미지 위치/최신 태그.
- [미확인] Iggy·RocketMQ·RabbitMQ Streams·Pulsar(2.x)용 Telegraf/Flink 연동 공식성.
- [미확인] StreamPipes의 ONNX·이벤트시간 윈도우·CEP 처리 요소.
- [미확인] Spark 4.x Structured Streaming(실시간 모드) 최신 버전 — 무거운 클러스터라 이번 조사에서 제외, 필요 시 별도.
- 참고: GitHub API는 요청 한도 초과로 사용 못 함 → 날짜는 releases.atom 피드·Docker Hub API로 확인.
