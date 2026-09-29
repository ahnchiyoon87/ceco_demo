# 06 · 참조 구조와 V2 부품 관문 재확인 (확인일 2026-09-29)

범위: 문헌 조사만 했다. docker는 실행하지 않았다. 다른 파일은 고치지 않았다.
방법: 1차 출처(공식 문서, 릴리스 페이지, LICENSE 원문, GitHub API, Docker Hub·GHCR 레지스트리 API, 공식 메일링)만 사실로 적었다.
표기: 1차 출처로 확인하지 못한 것은 [미확인]이다. "계산"은 공식 정책과 날짜로 셈한 값이다. 공지된 날짜가 아니다.
주의: 검색 요약에서만 본 내용은 "(검색 발췌)"로 표시했다. 본문 전체를 열어 읽지 않았다.

## 1. 참조 구조 — UNS에서 MQTT와 Kafka가 함께 쓰일 때

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| HiveMQ의 UNS 입장 | MQTT를 UNS 중심(backbone)으로 둔다. 원문: "MQTT remains the best choice for building a UNS." Kafka는 "a powerful data sink and an important building block in hybrid solutions for big data processing or stream analytics in a UNS architecture." (페이지 표시일 2026-08-06) | https://www.hivemq.com/blog/beyond-mqtt-fit-and-limitations-other-technologies-in-uns/ | 2026-09-29 |
| HiveMQ의 MQTT↔Kafka 연결 방식 | 브로커 확장(HiveMQ Enterprise Extension for Kafka)이 두 방향으로 번역한다. 원문: "Messages published to the MQTT broker will be automatically translated to Kafka messages … Similarly, messages published to the Kafka broker will be translated to MQTT messages and sent to the MQTT broker." Kafka 결과를 MQTT 클라이언트로 되돌리는 경로가 이 확장이다. 상용(Enterprise) 확장이다. (페이지 표시일 2026-02-27) | https://www.hivemq.com/blog/mqtt-vs-kafka-real-time-bidirectional-data-processing/ | 2026-09-29 |
| Confluent의 연결 방식 | Kafka Connect MQTT Source(MQTT→Kafka)와 MQTT Sink(Kafka→MQTT, "at least once") 커넥터가 있다. Confluent 독점(proprietary) 커넥터다. (검색 발췌) | https://docs.confluent.io/kafka-connectors/mqtt/current/mqtt-source-connector/overview.html · https://docs.confluent.io/kafka-connectors/mqtt/current/mqtt-sink-connector/overview.html | 2026-09-29 |
| UMH Classic의 연결 방식 | HiveMQ(MQTT)와 Kafka(Redpanda)를 함께 두고 `data-bridge`가 MQTT와 Kafka 사이를 잇는다. (검색 발췌) | https://umh.docs.umh.app/docs/architecture/data-infrastructure/unified-namespace/ | 2026-09-29 |
| UMH Core의 구성 | 컨테이너 하나에 Agent, benthos-umh, Redpanda(Kafka 호환 브로커)를 묶는다. (검색 발췌) Redpanda는 BSL 1.1이다(01 문서 참조). | https://docs.umh.app/ · https://github.com/redpanda-data/redpanda/blob/dev/licenses/bsl.md | 2026-09-29 |
| "수집기가 MQTT와 Kafka에 둘 다 쓴다"가 표준인가 | 위 출처들은 모두 **브리지(브로커 확장·Kafka Connect·data-bridge)** 방식을 문서화한다. 수집기 이중 발행을 권장 패턴으로 적은 1차 문서는 찾지 못했다. | [미확인] | 2026-09-29 |
| 알람이 HMI로 가는 경로 | 위 출처에서 확인한 것은 "Kafka 결과 → 브리지 → MQTT 클라이언트" 경로뿐이다. 스트림 처리기가 MQTT에 직접 발행하는 것을 참조 구조로 적은 1차 문서는 찾지 못했다. | [미확인] | 2026-09-29 |
| ISA-95와 UNS | ISA-95가 UNS를 정의하거나 MQTT/Kafka 배치를 지침으로 두는지 1차 문서로 확인하지 못했다. ISA-95 본문은 유료다(기존 조사 기록). | [미확인] | 2026-09-29 |

V2 초안에 대한 뜻: V2의 "Telegraf가 Kafka에 쓰고 MQTT 사본도 쓴다"는 문서화된 브리지 패턴과 다르다. 알람 경로 "Kafka → Vector → Mosquitto → FUXA"는 브리지 패턴(Kafka→MQTT 중계)과 모양이 같다. 이것은 위 표의 비교이며 표준 판정이 아니다.

## 2. 알람 관리 (ISA-18.2 / IEC 62682)

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| 알람 상태의 주인(HMI 알람 엔진 vs 별도 시스템) | 1차 출처를 열지 못했다(조사 중 도구 오류). | [미확인] | 2026-09-29 |
| 공정 알람과 분석 권고(advisory·alert)의 분리가 표준인가 | 1차 출처를 열지 못했다. ISA-18.2 개정판에 "alert" 범주가 있다는 주장은 이번에 확인하지 못했다. | [미확인] | 2026-09-29 |
| 표준 본문 접근 | ISA-18.2·IEC 62682 본문은 유료 문서다(기존 조사 기록, 가격 미확인). | [미확인] | 2026-09-29 |

## 3. V2 부품 수명·라이선스 재확인 (12개월 관문 = 2027-09-29까지 지원)

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| Telegraf 1.40 | 최신 **1.40.1 (2026-09-21)**, 1.40.0은 2026-09-07. 연 4회 마이너(3·6·9·12월), 사이에 3주 간격 패치. OSS 지원 기간은 공표되지 않았다. 상용 지원 정책은 "current Minor Release … and the immediately preceding Minor Release"이며 OSS에는 적용되지 않는다고 적혀 있다. 라이선스 MIT. 공식 이미지 `telegraf:1.40.1` 있음. **관문: 고정 버전이면 탈락**(계산: 1.42가 2027-03 예정 주기, 두 마이너 규칙상 그때 빠짐). 롤링(마이너 추종) 제품이다. | https://github.com/influxdata/telegraf/releases · https://github.com/influxdata/telegraf/blob/master/docs/RELEASES.md · https://www.influxdata.com/legal/support-policy/ · https://github.com/influxdata/telegraf/blob/master/LICENSE | 2026-09-29 |
| Kafka 4.3 | 최신 **4.3.1 (2026-06-25)**, 4.3.0은 2026-05-22. 지원 목록 4.3.1·4.2.1·4.1.2. 정책: "bugfix releases as needed for the last 3 releases", 목표 연 3회. 4.4.0 계획 릴리스일 "no earlier than September 9 2026", 2026-09-29 현재 다운로드 페이지에 4.4 없음. 공식 이미지 `apache/kafka:4.3.1` 있음. **관문: 날짜 공표 없음.** 계산: 4개월 주기면 4.6이 2027-09-29 전에 나올 수 있고 그때 4.3은 지원 목록에서 빠진다. 라이선스 [미확인: 이번에 LICENSE 원문 미열람]. | https://kafka.apache.org/community/downloads/ · https://kafka.apache.org/blog/ · https://cwiki.apache.org/confluence/display/KAFKA/Time+Based+Release+Plan · https://cwiki.apache.org/confluence/spaces/KAFKA/pages/429064575/Release+Plan+4.4.0 | 2026-09-29 |
| Flink 2.2 | **Flink 2.3.0 출시(2026-06-25).** 2.2.1은 2026-05-15, 2.2.0은 2025-12-04. 정책: "support the current and previous minor release with bugfixes", 새 마이너가 나오면 이전 지원판에 마지막 패치 한 번. 2.4 계획(dev 메일 2026-08-27): "feature freeze around September 30th with a release date around the end of October." **관문: 탈락.** 2.4가 나오면 2.2는 지원 밖이다. 1.20은 LTS 표기 유지(1.20.5, 2026-06). 공식 이미지 `flink:2.2.1` 있음. 라이선스 [미확인: 이번에 LICENSE 원문 미열람]. | https://flink.apache.org/downloads/ · https://flink.apache.org/posts/ · http://www.mail-archive.com/dev@flink.apache.org/msg88097.html | 2026-09-29 |
| Flink Kafka 커넥터 | 최신 **5.0.0**, 호환 "2.1.x, 2.2.x". 4.0.1 → 2.0.x, 3.4.0 → 1.20.x. **2.3용 공식 커넥터 없음.** Maven Central 최신 디렉터리 `5.0.0-2.2`. 뜻: 2.2에서 2.3으로 올리려면 공식 커넥터가 아직 없다. | https://flink.apache.org/downloads/ · https://repo1.maven.org/maven2/org/apache/flink/flink-connector-kafka/ | 2026-09-29 |
| ZooKeeper 3.9 | 현재판 **3.9.6**, 안정판 3.8.7, 3.7.2는 2024-02-02 EOL. 원문: "Once a new minor version is released, the previous stable version is expected to be decommissioned within approximately six months." 3.10 출시 기록 없음. **Docker 공식 이미지는 `3.9.5`까지 있고 `3.9.6` 태그는 없다**(HTTP 404). 관문: 날짜 공표 없음, 3.9가 현재판이라 통과로 본다(3.9 종료 공지 없음). | https://zookeeper.apache.org/releases.html · https://hub.docker.com/_/zookeeper/tags | 2026-09-29 |
| InfluxDB 2.9 | 최신 2.x는 **2.9.1 (2026-05-12)**. 이후 2.x 릴리스 없음(3.11.4, 1.13.1은 2026-09 출시). 2.x EOL 공지는 찾지 못했다. 지원 정책 문서는 OSS에 적용되지 않는다고 적는다. 2.x 문서 머리: "InfluxDB 3 Core is the latest stable version." Docker `latest` 태그는 **2026-09-15부터 InfluxDB 3 Core**를 가리킨다. `influxdb:2.9.1` 태그 있음. 라이선스 MIT(main-2.x 브랜치 LICENSE). 관문: 종료일 공표 없음 → [미확인]. | https://github.com/influxdata/influxdb/releases · https://docs.influxdata.com/influxdb/v2/install/use-docker-compose/ · https://www.influxdata.com/legal/support-policy/ · https://github.com/influxdata/influxdb/blob/main-2.x/LICENSE | 2026-09-29 |
| Vector 0.58 | 최신 **0.58.0 (2026-08-26)**. 주기 "Every 6 weeks"(0.53~0.58이 2026-01-27~08-26). 정책 원문: "Vector currently supports only the latest minor release, as it remains in the 0.x version series." 라이선스 **MPL-2.0**(LICENSE 원문, GitHub API spdx도 MPL-2.0). 라이선스 변경 공지는 찾지 못했다. 이미지 `timberio/vector:0.58.0-debian`·`-alpine` 있음. **관문: 고정 버전이면 탈락**(0.59가 나오면 지원 밖). 롤링 제품이다. | https://vector.dev/releases/ · https://github.com/vectordotdev/vector/blob/master/RELEASES.md · https://github.com/vectordotdev/vector/blob/master/LICENSE | 2026-09-29 |
| Mosquitto 2.1.x | 최신 **2.1.2 (2026-02-09)**, 2.1.0은 2026-01-29. 2.0 최신 2.0.22(2025-07-11). 지원 기간 정책 문서 없음. 라이선스 "EPL-2.0 OR BSD-3-Clause"(EDL-1.0). **Docker 공식 이미지에 `eclipse-mosquitto:2.1.2` 태그는 없다(404). `2.1.2-alpine`·`2.1-alpine`만 있다**(2026-09-18 재빌드). `2.0.22`·`latest`도 있음. 관문: 종료일 공표 없음 → [미확인]. | https://mosquitto.org/blog/ · https://github.com/eclipse-mosquitto/mosquitto/blob/master/LICENSE.txt · https://hub.docker.com/_/eclipse-mosquitto/tags | 2026-09-29 |
| FUXA 1.3.4 | 최신 **v1.3.4 (2026-08-12)**. 라이선스 MIT. 공개 권고 중 가장 최근 것은 2026-07-22 발표 6건이며 모두 "patched >= 1.3.3". **1.3.4 이후 발표된 권고는 없다**(GitHub advisories API). 지원 정책 문서 없음. 이미지 `frangoteam/fuxa:1.3.4` 있음. | https://github.com/frangoteam/FUXA/releases · https://github.com/frangoteam/FUXA/security/advisories | 2026-09-29 |
| Grafana 13.2 | 최신 **13.2.2 (2026-09-15)**. 정책: "Each minor release is supported for 9 months … The last minor release of a major version receives extended support for 15 months." 13.2.x 종료 **2027-05-18**, 13.3.x(2026-10-20 예정) 2027-07-20, 12.4.x 2027-05-24. 라이선스 AGPL-3.0. **관문: 탈락**(모든 공표 버전이 2027-09-29 전 종료). 롤링 제품이다. | https://grafana.com/docs/grafana/latest/upgrade-guide/when-to-upgrade/ · https://github.com/grafana/grafana/releases | 2026-09-29 |
| Prometheus 3.15 / LTS 3.13 | 3.15.0 (2026-09-25), 3.13.3 (2026-09-07). 원문: "Every 6 weeks … After those 6 weeks, minor releases generally no longer receive bug fixes." LTS 3.13 종료 **2027-07-31**. 다음 LTS "TBD 2027-06 → 2028-07-31". 라이선스 Apache-2.0. **관문: 3.15 탈락, 3.13 LTS도 탈락**(2027-07-31 < 2027-09-29). 다음 LTS로 옮기는 롤링이 필요하다. | https://prometheus.io/docs/introduction/release-cycle/ · https://github.com/prometheus/prometheus/releases | 2026-09-29 |
| Alertmanager 0.34 | 최신 **v0.34.1 (2026-09-17)**. 공식 지원 정책 없음(Prometheus release-cycle은 서버만 다룸). 라이선스 Apache-2.0. 관문: [미확인]. | https://github.com/prometheus/alertmanager/releases | 2026-09-29 |
| cAdvisor 0.60 | 최신 **v0.60.6 (2026-09-18)**. 이미지는 `ghcr.io/google/cadvisor:v0.60.6`(README: v0.53.0 이전은 gcr.io). 라이선스 Apache-2.0(LICENSE 원문). 지원 정책 없음. 관문: [미확인]. | https://github.com/google/cadvisor/releases · https://github.com/google/cadvisor/blob/master/README.md | 2026-09-29 |
| kafka-exporter 1.10 | 최신 **v1.10.0 (2026-09-08)**, 그 전은 v1.9.0(2025-02-17). 라이선스 Apache-2.0. 이미지 `danielqsj/kafka-exporter:v1.10.0` 있음. 지원 정책 없음. 관문: [미확인]. | https://github.com/danielqsj/kafka_exporter/releases | 2026-09-29 |

관문 요약(2027-09-29 기준):
- 고정 버전으로는 탈락: Telegraf 1.40, Flink 2.2, Vector 0.58, Grafana 13.2, Prometheus 3.15, Prometheus 3.13 LTS.
- 공표 날짜 없음: Kafka 4.3(계산상 위험), ZooKeeper 3.9, InfluxDB 2.9, Mosquitto 2.1, FUXA, Alertmanager, cAdvisor, kafka-exporter.
- 태그 주의: `eclipse-mosquitto:2.1.2` 없음(→ `2.1.2-alpine`), `zookeeper:3.9.6` 없음(→ `3.9.5`), `influxdb:latest`는 3 Core.
- Flink는 롤링으로도 막힌다: 2.3용 공식 Kafka 커넥터가 없다.

## 4. Vector 동작 (Kafka source, MQTT sink, InfluxDB sink)

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| Kafka source 종단 확인(ack) | 지원한다("acknowledgements: yes"). 확인이 오면 소스가 Kafka에 직접 확인한다. 원문: "acknowledging the event directly, such as when using the Kafka or aws_sqs sources." 소스의 `acknowledgements` 설정은 폐기 예정이다. **싱크 쪽 또는 전역에서 켠다.** 오프셋 커밋 주기 `commit_interval_ms` 기본 5000. 전달 보장 "at-least-once". | https://vector.dev/docs/reference/configuration/sources/kafka/ · https://vector.dev/docs/architecture/end-to-end-acknowledgements/ | 2026-09-29 |
| 여러 싱크로 갈라질 때 | 연결된 **모든** 싱크가 확인해야 소스가 확인한다(MQTT sink 문서 원문 "acknowledged by all connected sinks"). filter로 버린 이벤트도 확인 처리된다. | https://vector.dev/docs/reference/configuration/sinks/mqtt/ · https://vector.dev/docs/architecture/end-to-end-acknowledgements/ | 2026-09-29 |
| 디스크 버퍼와 확인 시점 | 원문: "This feature will require that events be sent by sinks **or persisted into disk buffers** before sources will acknowledge them." 즉 디스크 버퍼를 쓰면 버퍼에 기록된 시점에 오프셋이 확인될 수 있다. (2021 발표 글, 현행 문서에서 같은 문장은 찾지 못함) | https://vector.dev/highlights/2021-12-15-splunk-hec-improvements/ | 2026-09-29 |
| MQTT sink QoS | `qos` 값: AtLeastOnce(기본), AtMostOnce, ExactlyOnce. **QoS1 지원.** | https://vector.dev/docs/reference/configuration/sinks/mqtt/ | 2026-09-29 |
| MQTT sink retained | `retain` 옵션 있음, 기본 false. **retained 지원.** | https://vector.dev/docs/reference/configuration/sinks/mqtt/ | 2026-09-29 |
| MQTT sink 버퍼 | memory(기본)와 disk. disk는 최소 약 256MB. 종단 확인 지원. | https://vector.dev/docs/reference/configuration/sinks/mqtt/ | 2026-09-29 |
| 0.58 MQTT sink 변경 | 깨지는 변경: 이제 `tls.alpn_protocols`를 따르며 고정 `mqtt` ALPN을 보내지 않는다. | https://vector.dev/releases/0.58.0/ | 2026-09-29 |
| InfluxDB sink 디스크 버퍼 | `influxdb_metrics`·`influxdb_logs` 모두 `buffer.type = "disk"` 지원. 원문: "Data that has been synchronized to disk will not be lost if Vector is restarted forcefully or crashes." disk는 `max_size` 최소 약 256MB. 둘 다 종단 확인 지원. `influxdb_logs`는 v2(`org`·`bucket`·`token`) 지원. | https://vector.dev/docs/reference/configuration/sinks/influxdb_metrics/ · https://vector.dev/docs/reference/configuration/sinks/influxdb_logs/ | 2026-09-29 |
| 0.58 InfluxDB·디스크 버퍼 변경 | InfluxDB 싱크에 `version` 필드가 생겼고 앞으로 필수가 된다. `influxdb_logs`의 `namespace` 제거. `disk_v2` 버퍼의 교착·크래시·역직렬화 버그 수정. | https://vector.dev/releases/0.58.0/ | 2026-09-29 |
| MQTT source | 있다(beta). **종단 확인 미지원**("acknowledgements: no"). | https://vector.dev/docs/reference/configuration/sources/mqtt/ | 2026-09-29 |

## 5. Telegraf 디스크 버퍼와 Modbus 재연결

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| 디스크 버퍼 도입 버전 | **1.32.0 (2024-09-09)**. 원문: "a feature for a disk-backed metric buffer under the `buffer_strategy` agent config (see PR #15564)." 실험 기능으로 발표. | https://github.com/influxdata/telegraf/releases/tag/v1.32.0 | 2026-09-29 |
| 현재 문서 상태 | 원문: "`disk`, an **experimental** disk-backed buffer … **This is only supported at the agent level.**" 즉 `outputs.kafka`마다 따로 켤 수 없다. 켜면 모든 출력(Kafka와 MQTT 사본 모두)에 적용된다. | https://github.com/influxdata/telegraf/blob/master/docs/CONFIGURATION.md | 2026-09-29 |
| `buffer_directory` | 기본값 없음. disk 모드에서 필수. 출력 플러그인마다 ID 이름의 하위 폴더를 만든다. `buffer_disk_sync` 기본 true(끄면 마지막 flush 구간 유실 가능). | https://docs.influxdata.com/telegraf/v1/configuration/agent/ · https://github.com/influxdata/telegraf/blob/master/docs/CONFIGURATION.md | 2026-09-29 |
| 공식 이미지 실행 사용자 | root로 시작하면 entrypoint가 `setpriv --reuid telegraf --regid telegraf`로 **telegraf 사용자로 낮춰** 실행한다. 사용자는 deb 패키지가 만든다. Dockerfile에 고정 uid는 없다. 숫자 uid는 [미확인]. 뜻: `buffer_directory`는 telegraf 사용자가 쓸 수 있어야 한다. | https://github.com/influxdata/influxdata-docker/blob/master/telegraf/1.40/Dockerfile · https://github.com/influxdata/influxdata-docker/blob/master/telegraf/1.40/entrypoint.sh | 2026-09-29 |
| 알려진 문제 | #16314 "stops working after a while"(1.33.0, 닫힘, PR #16697로 수정). #16500 디스크 버퍼 사용 시 수집 지연·누락(1.33.1, **열림**). 1.39.2 수정: "Cache length when closing buffer to avoid panic with --once"(#19050). | https://github.com/influxdata/telegraf/issues/16314 · https://github.com/influxdata/telegraf/issues/16500 · https://github.com/influxdata/telegraf/releases/tag/v1.39.2 | 2026-09-29 |
| `inputs.modbus` 끊김 처리 | 소스 코드: 매 수집(Gather) 때 연결이 없으면 다시 연결한다. 읽기 오류가 나면(장치 busy 예외 제외) 끊고 다시 연결한 뒤 다음 슬레이브로 넘어간다. 연결 실패는 그 주기의 오류로 반환된다. `busy_retries`(기본 0)는 busy 응답에만 쓴다. `close_connection_after_gather`(기본 false) 옵션 있음. | https://github.com/influxdata/telegraf/blob/master/plugins/inputs/modbus/modbus.go · https://github.com/influxdata/telegraf/blob/master/plugins/inputs/modbus/README.md | 2026-09-29 |

## 6. InfluxDB 2.9 이미지 "config name "default" already exists"

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| 증상 보고 | influxdata-docker #542(2021-10-28 열림, **아직 열림**): setup 모드에서 재시작 반복, "Error: config name "default" already exists". 보고자 관찰: "`/etc/influxdb2`의 config 파일에 이미 `default` 항목이 있으면" 난다. | https://github.com/influxdata/influxdata-docker/issues/542 | 2026-09-29 |
| 이미지 기본값 | 2.9 Dockerfile: `VOLUME /var/lib/influxdb2 /etc/influxdb2`, `INFLUX_CONFIGS_PATH=/etc/influxdb2/influx-configs`, `DOCKER_INFLUXDB_INIT_CLI_CONFIG_NAME=default`, CLI 2.8.0. | https://github.com/influxdata/influxdata-docker/blob/master/influxdb/2.9/Dockerfile | 2026-09-29 |
| setup 실행 조건 | 2.9 entrypoint: bolt 파일(`/var/lib/influxdb2/influxd.bolt`)이 있으면 setup을 건너뛴다. 없고 `DOCKER_INFLUXDB_INIT_MODE`가 있으면 `influx setup --force … --name "${DOCKER_INFLUXDB_INIT_CLI_CONFIG_NAME}"`을 실행한다. **기존 CLI config 이름을 검사하는 코드는 없다.** | https://github.com/influxdata/influxdata-docker/blob/master/influxdb/2.9/entrypoint.sh | 2026-09-29 |
| 실패 시 정리 | 같은 파일: 초기화 중 오류로 끝나면 `cleanup_influxd`가 **bolt와 engine만 지운다.** `influx-configs`는 지우지 않는다. | https://github.com/influxdata/influxdata-docker/blob/master/influxdb/2.9/entrypoint.sh | 2026-09-29 |
| 원인(코드 대조 결론, 실행 미검증) | ① `/etc/influxdb2`는 남고 `/var/lib/influxdb2`만 새로 만들어진 경우, ② setup 뒤 단계(사용자 스크립트 등)가 실패해 bolt만 지워진 경우. 두 경우 모두 다음 기동에서 setup이 다시 돌고 같은 이름 `default`가 이미 있어 실패한다. 참고: `/etc/influxdb2`는 Dockerfile의 익명 볼륨이다. `docker compose up`은 재생성 때 이전 컨테이너의 익명 볼륨 데이터를 가져온다(`-V`는 "Recreate anonymous volumes instead of retrieving data from the previous containers"). | 위 entrypoint · https://docs.docker.com/reference/cli/docker/compose/up/ | 2026-09-29 |
| 수정 이력 | PR #556 "ignore init variables if config already exists"는 2023-04-12 병합으로 표시된다. 그러나 **현재 2.9 entrypoint에는 그 검사 코드가 없다.** 어느 파일에 들어갔는지는 [미확인]. | https://github.com/influxdata/influxdata-docker/pull/556 | 2026-09-29 |
| 대처(출처에 있는 것) | 포럼 답: "delete that file or set the env var `DOCKER_INFLUXDB_INIT_CLI_CONFIG_NAME` to something other than `default`." 공식 compose 문서: `/var/lib/influxdb2`와 `/etc/influxdb2`를 **둘 다** 볼륨으로 둔다. 뜻: 두 볼륨을 같은 수명으로 묶고, 데이터 볼륨만 지울 때는 `/etc/influxdb2/influx-configs`도 함께 지운다. | https://community.influxdata.com/t/influx-docker-container-keeps-restarting-due-to-default-config-already-being-defined/22233 · https://docs.influxdata.com/influxdb/v2/install/use-docker-compose/ | 2026-09-29 |
| 관련 이슈 | #474 "flag name is required if you already have existing configs"(2.0.4, 닫힘, PR #511). #611 기존 influx-configs로 기동 가능 여부(2022-05-05, 열림, 답 없음). | https://github.com/influxdata/influxdata-docker/issues/474 · https://github.com/influxdata/influxdata-docker/issues/611 | 2026-09-29 |
| 2.9.0 주의 | 토큰 해시 저장이 기본. 원문 요지: 기존 평문 토큰은 첫 기동 때 해시되며 되돌릴 수 없다. | https://docs.influxdata.com/influxdb/v2/install/use-docker-compose/ | 2026-09-29 |

## 7. 목록에 없는데 볼 만한 것 (1차 출처가 있는 것만)

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| Flink 1.20 LTS | 공식 다운로드 페이지가 계속 "LTS"로 표기, 1.20.5(2026-06). Kafka 커넥터 3.4.0이 1.20.x용. 종료일은 05 문서대로 공표 없음. | https://flink.apache.org/downloads/ | 2026-09-29 |
| Prometheus 다음 LTS | 2027-06 예정, 2028-07-31까지. 12개월 관문을 넘는 유일한 Prometheus 선택지다(예정값). | https://prometheus.io/docs/introduction/release-cycle/ | 2026-09-29 |
| InfluxDB `latest` 전환 | 2026-09-15부터 `latest` = InfluxDB 3 Core. V2는 반드시 `2.9.1` 같은 명시 태그를 써야 한다. | https://docs.influxdata.com/influxdb/v2/install/use-docker-compose/ | 2026-09-29 |
| Kafka→MQTT 브리지(상용) | HiveMQ Enterprise Extension for Kafka(양방향), Confluent MQTT Sink(독점). 둘 다 비공개·상용이라 V2 기준에는 맞지 않는다. 패턴 비교용이다. | 1장 출처 | 2026-09-29 |
| HiveMQ Edge·benthos-umh | 01 문서에서 이미 다뤘다(여기서는 재확인하지 않음). | 01-ingest-broker-pipe.md | 2026-09-29 |

## 확인 못 한 것

- ISA-18.2 / IEC 62682: 알람 상태 주인, 공정 알람과 분석 권고 분리. 1차 출처를 열지 못했다(조사 중 도구 판정 오류가 이어짐).
- ISA-95가 UNS·MQTT·Kafka 배치를 지침으로 두는지.
- "수집기 이중 발행"과 "스트림 처리기 → MQTT 직접 발행"을 참조 구조로 적은 1차 문서. 찾지 못했다.
- UMH·Confluent 항목은 검색 발췌로만 확인했다. 본문을 열지 못했다.
- Kafka·Flink·ZooKeeper LICENSE 원문(이번 세션 미열람).
- Kafka 4.4.0 실제 출시일, Flink 2.4 실제 출시일, Flink 2.3용 Kafka 커넥터 출시일.
- InfluxDB 2.x 공식 종료 계획, Mosquitto·FUXA·Alertmanager·cAdvisor·kafka-exporter 지원 기간.
- Telegraf 공식 이미지의 telegraf 사용자 숫자 uid.
- PR #556 수정이 현재 어느 entrypoint에 있는지. 6장 원인 결론은 코드 대조이며 실행으로 확인하지 않았다.
- Vector 현행 문서에서 "디스크 버퍼 기록 시 확인" 문장(2021 발표 글에서만 확인).
