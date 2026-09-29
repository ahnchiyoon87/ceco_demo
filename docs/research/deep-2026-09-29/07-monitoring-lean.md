# 07 · 소형 IIoT 스택의 경량 모니터링 조사 (2026-09-29 기준)

- 범위: 단일 호스트 Docker Compose 스택(센서 태그 12개). 감시 대상은 Mosquitto 2.1.2, Telegraf 1.40.1, Kafka 4.3.1(KRaft 단일), Flink 2.2.1(잡 4개, ZooKeeper HA), Vector 0.58, InfluxDB 2.9.1, FUXA.
- 현재 감시: Prometheus 3.15 + Alertmanager 0.34.1(수신자 없음) + kafka-exporter 1.10 + cAdvisor 0.60.6 + Grafana 13.2.
- 요구: (a) 파이프라인 컨테이너 정지 (b) JobManager는 살아 있고 Flink 잡만 정지 (c) 브로커 다운·클라이언트 끊김 (d) 텔레메트리 적재 정지 (e) 컨슈머 랙. Grafana 인프라 패널.
- 관문: OSI 라이선스만(BSL·SSPL·ELv2 제외), 엔터프라이즈 전용 기능 제외, 2027-09-29 전 지원 종료 금지(롤링 마이너 제품은 허용).
- 방법: 공식 문서·LICENSE·GitHub 릴리스 API·이슈·소스 코드만 읽었다. docker 실행 없음. 실측이 필요한 것은 "실측 필요"로 적었다.
- 확인일은 모두 2026-09-29. 확인 못 한 것은 [미확인].

---

## 1 · 경량 구성 네 가지

### 1-1 사실 표

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| Prometheus 라이선스·최신 | Apache-2.0. 최신 v3.15.0(2026-09-25). | https://github.com/prometheus/prometheus/releases · https://api.github.com/repos/prometheus/prometheus | 2026-09-29 |
| Prometheus 지원 정책 | 6주마다 새 마이너 주기가 시작된다. 6주 뒤 그 마이너는 대체로 버그 수정을 받지 않는다. LTS는 1년 지원, CVSS 7.0 이상만 수정. | https://prometheus.io/docs/introduction/release-cycle/ | 2026-09-29 |
| Prometheus LTS 표 | 3.13(2026-07-01 출시) 지원 끝 2027-07-31. 다음 LTS는 표에 "TBD 2027-06 / 2028-07-31 / Upcoming"으로 적혀 있다. 3.15는 LTS가 아니다. | https://prometheus.io/docs/introduction/release-cycle/ | 2026-09-29 |
| Prometheus 알림 규칙 단독 동작 | 알림 상태는 웹 UI "Alerts" 탭에서 본다. `ALERTS` 합성 시계열이 pending/firing일 때 1이다. 문서는 규칙이 "완전한 알림 솔루션이 아니다"라고 쓰고, 요약·억제·침묵·발송은 Alertmanager가 맡는다고 적는다. | https://prometheus.io/docs/prometheus/latest/configuration/alerting_rules/ | 2026-09-29 |
| Alertmanager 라이선스·최신 | Apache-2.0. 최신 v0.34.1(2026-09-17), v0.34.0(2026-08-16). | https://api.github.com/repos/prometheus/alertmanager/releases | 2026-09-29 |
| Alertmanager 지원 기간 | 공개된 지원 기간 문서를 찾지 못했다. [미확인] | — | 2026-09-29 |
| Grafana 라이선스·최신 | AGPL-3.0(OSI 승인, 네트워크 카피레프트). 최신 v13.2.2(2026-09-15). | https://api.github.com/repos/grafana/grafana · https://github.com/grafana/grafana/releases | 2026-09-29 |
| Grafana 지원 정책 | 마이너는 격월, 메이저는 연 1회(4~5월). 각 마이너는 출시 후 9개월 지원. 메이저의 마지막 마이너는 15개월. | https://grafana.com/docs/grafana/latest/upgrade-guide/when-to-upgrade/ | 2026-09-29 |
| Grafana 13.x 지원 표 | 13.2.x 출시 2026-08-18, 지원 끝 2027-05-18. 13.3.x 출시 2026-10-20, 지원 끝 2027-07-20. 12.4.x(12의 마지막 마이너) 지원 끝 2027-05-24. 13.2 고정 시 2027-09-29 전에 끝난다. 마이너를 따라 올리면 관문 허용 범위다. | https://grafana.com/docs/grafana/latest/upgrade-guide/when-to-upgrade/ | 2026-09-29 |
| Grafana 내장 Alertmanager | "Grafana includes a built-in Alertmanager that extends the Prometheus Alertmanager." 이것이 기본이며 UI에서 "Grafana"로 표시된다. 외부 Prometheus Alertmanager로 보내는 것은 선택이다. | https://grafana.com/docs/grafana/latest/alerting/fundamentals/notifications/alertmanager/ · https://grafana.com/docs/grafana/latest/alerting/set-up/configure-alertmanager/ | 2026-09-29 |
| Grafana 관리 규칙 | 문서가 "Grafana-managed alert rules — the recommended option"이라고 쓴다. 여러 백엔드 데이터 소스를 조회할 수 있고, 한 규칙에서 여러 소스를 함께 쓸 수 있다. | https://grafana.com/docs/grafana/latest/alerting/alerting-rules/ · https://grafana.com/docs/grafana/latest/alerting/fundamentals/alert-rules/ | 2026-09-29 |
| Grafana No Data 처리 | Grafana 관리 규칙은 데이터가 없을 때 기본으로 `DatasourceNoData` 알림을 만든다. Alerting / Normal / Keep Last State로 바꿀 수 있다. | https://grafana.com/docs/grafana/latest/alerting/fundamentals/alert-rule-evaluation/nodata-and-error-states/ | 2026-09-29 |
| VictoriaMetrics 라이선스·최신 | Apache-2.0(단일·클러스터). 최신 v1.153.0(2026-09-28). | https://docs.victoriametrics.com/victoriametrics/single-server-victoriametrics/ · https://api.github.com/repos/VictoriaMetrics/VictoriaMetrics/releases | 2026-09-29 |
| VictoriaMetrics 단일 노드 | `-promscrape.config`로 prometheus.yml을 읽어 직접 스크레이프한다. Prometheus 조회 API를 지원해 Grafana에서 Prometheus 대체로 쓸 수 있다. | https://docs.victoriametrics.com/victoriametrics/single-server-victoriametrics/ | 2026-09-29 |
| VictoriaMetrics 지원 정책 | LTS는 12개월, 6개월마다 새 LTS. LTS 릴리스는 엔터프라이즈 전용이다. 비엔터프라이즈 사용자는 최신 릴리스를 쓰라고 적혀 있다(롤링). | https://docs.victoriametrics.com/victoriametrics/lts-releases/ | 2026-09-29 |
| vmalert 알림 | 규칙을 `-datasource.url`에 대해 실행한다. "For sending alerting notifications vmalert relies on Alertmanager configured via -notifier.url". 웹 UI가 있다. S3/GCS 규칙 읽기, 클러스터 멀티테넌시는 엔터프라이즈 전용. | https://docs.victoriametrics.com/victoriametrics/vmalert/ | 2026-09-29 |
| Grafana Alloy 정체 | "OpenTelemetry Collector distribution with built-in Prometheus pipelines". 수집·전달기다. | https://grafana.com/docs/alloy/latest/introduction/ | 2026-09-29 |
| Alloy 저장 여부 | `prometheus.remote_write`는 WAL에 모았다가 지정 엔드포인트로 보낸다. WAL은 임시 버퍼다. 장기 저장소가 따로 필요하다. | https://grafana.com/docs/alloy/latest/reference/components/prometheus/prometheus.remote_write/ | 2026-09-29 |
| Alloy 라이선스·최신·정책 | Apache-2.0. 최신 v1.20.1(2026-09-28). 시맨틱 버전, GA 기능은 마이너·패치 간 후방 호환. 마이너별 지원 기간은 문서에 없다. | https://api.github.com/repos/grafana/alloy/releases · https://grafana.com/docs/alloy/latest/introduction/backward-compatibility/ | 2026-09-29 |
| Alloy 내장 kafka exporter | `prometheus.exporter.kafka`는 kafka_exporter를 내장한다. `offset_show_all`로 컨슈머 그룹 오프셋·랙 표시 범위를 정한다. | https://grafana.com/docs/alloy/latest/reference/components/prometheus/prometheus.exporter.kafka/ | 2026-09-29 |
| Alloy 내장 cAdvisor | `prometheus.exporter.cadvisor`는 cAdvisor를 쓴다. Linux 전용. Docker 배포는 privileged 필요. docker.sock, `/`, `/sys`, `/var/lib/docker/`, `/dev/disk/` 마운트 필요. | https://grafana.com/docs/alloy/latest/reference/components/prometheus/prometheus.exporter.cadvisor/ | 2026-09-29 |

### 1-2 비교 요약 (위 표의 사실만 조합, 컨테이너 수는 파이프라인 제외)

| 구성 | 감시용 컨테이너 | 라이선스 | 지원 정책 | (a)~(e) |
|---|---|---|---|---|
| (i) Prometheus + Alertmanager + 익스포터 (현재) | Prometheus, Alertmanager, Grafana, kafka-exporter, cAdvisor = 5 | Apache-2.0 / AGPL-3.0(Grafana) | Prometheus 롤링(6주), Grafana 롤링(9개월), Alertmanager [미확인] | 규칙 표현은 2장 지표로 모두 가능. 발송은 Alertmanager 수신자 설정이 있어야 한다. 현재 수신자 없음. |
| (ii) Prometheus + Grafana Alerting | Prometheus, Grafana, kafka-exporter, cAdvisor = 4 | 동일 | 동일 | 같은 PromQL 지표를 Grafana 관리 규칙으로 평가. Grafana 내장 Alertmanager가 기본이라 외부 Alertmanager 불필요. InfluxDB도 같은 규칙 체계로 조회 가능. |
| (iii) VictoriaMetrics + vmalert | VictoriaMetrics, vmalert, Grafana, kafka-exporter, cAdvisor = 5. 발송하려면 Alertmanager +1 | Apache-2.0 (일부 기능 엔터프라이즈) | 비엔터프라이즈는 최신 릴리스 롤링. LTS는 엔터프라이즈 전용 | 지표는 (i)과 같다. vmalert는 발송을 Alertmanager에 맡기므로 컨테이너가 줄지 않는다. |
| (iv) Alloy 수집기 | Prometheus(저장·원격쓰기 수신), Grafana, Alloy(kafka exporter·cAdvisor 내장) = 3 | Apache-2.0 / AGPL-3.0 | Alloy 지원 기간 [미확인] | kafka-exporter·cAdvisor 지표를 Alloy 한 컨테이너로 모은다. 내장 kafka_exporter 버전과 Kafka 4.3 호환은 [미확인]. |

---

## 2 · 구성요소별 Prometheus 노출과 `up` 판정

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| `up` 지표 | 스크레이프마다 `up{job,instance}`가 자동 생성된다. 도달 가능하면 1, 스크레이프 실패면 0. "useful for instance availability monitoring". | https://prometheus.io/docs/concepts/jobs_instances/ | 2026-09-29 |
| `absent()` / `absent_over_time()` | 해당 이름·라벨의 시계열이 없을 때(또는 일정 시간 없을 때) 1을 돌려준다. "useful for alerting on when no time series exist". | https://prometheus.io/docs/prometheus/latest/querying/functions/ | 2026-09-29 |
| docker_sd 대상 범위 | Prometheus v3.15.0 소스의 docker SD는 `ContainerList`를 `Filters`만 넣고 호출한다(All 옵션 없음). Docker 문서상 목록 기본값은 "default shows just running". 따라서 정지된 컨테이너는 `up=0`이 아니라 대상에서 사라진다. 이 경우 `absent()`로 잡아야 한다. 정적 설정(static_configs)에서 컨테이너 정지가 스크레이프 실패로 이어져 `up=0`이 되는지는 실측 필요. | https://github.com/prometheus/prometheus/blob/v3.15.0/discovery/moby/docker.go · https://docs.docker.com/reference/cli/docker/container/ls/ | 2026-09-29 |
| Docker 엔진 지표 | daemon.json `metrics-addr`로 켠다. "you can only monitor Docker itself". 지표 이름은 바뀔 수 있다고 경고한다. 컨테이너별 상태는 문서에 없다. | https://docs.docker.com/engine/daemon/prometheus/ | 2026-09-29 |
| cAdvisor | Apache-2.0(LICENSE 파일). 최신 v0.60.6(2026-09-18). `container_last_seen`은 "Last time a container was seen by the exporter". 빠른 시작은 `--privileged`, `/dev/kmsg`, `/`·`/var/run`·`/sys`·`/var/lib/docker`·`/dev/disk` 마운트. | https://github.com/google/cadvisor/blob/master/LICENSE · https://api.github.com/repos/google/cadvisor/releases · https://github.com/google/cadvisor/blob/master/docs/storage/prometheus.md · https://github.com/google/cadvisor/blob/master/README.md | 2026-09-29 |
| Mosquitto 2.1 | Prometheus 엔드포인트 없음(man 페이지·ChangeLog 2.1.0~2.1.2에 언급 없음). 2.1에 `http_api` 리스너 프로토콜이 있다. v2.1.2 소스 `http_api.c`는 `/api/v1/systree`, `/api/v1/listeners`, `/api/v1/version`을 처리하고 systree는 JSON이다. man: 인증 불가, 루프백 바인드와 리버스 프록시 권고. | https://mosquitto.org/man/mosquitto-8.html · https://github.com/eclipse-mosquitto/mosquitto/blob/master/ChangeLog.txt · https://github.com/eclipse-mosquitto/mosquitto/blob/v2.1.2/src/http_api.c · https://github.com/eclipse-mosquitto/mosquitto/blob/v2.1.2/man/mosquitto.conf.5.xml | 2026-09-29 |
| Mosquitto 버전 날짜 | 2.1.0 2026-01-29, 2.1.1 2026-02-04, 2.1.2 2026-02-09. ChangeLog 맨 위는 "2.1.3 - 2026-02-xx"(태그 목록 최신은 v2.1.2). | https://github.com/eclipse-mosquitto/mosquitto/blob/master/ChangeLog.txt | 2026-09-29 |
| Telegraf | MIT. 최신 v1.40.1(2026-09-21). `outputs.prometheus_client` 기본 `:9273`, `/metrics`. `inputs.internal`은 `internal_gather.metrics_gathered`, `internal_write.metrics_written`·`metrics_dropped`·`buffer_size`, `internal_agent.gather_errors` 등을 낸다. | https://api.github.com/repos/influxdata/telegraf/releases · https://github.com/influxdata/telegraf/blob/master/plugins/outputs/prometheus_client/README.md · https://github.com/influxdata/telegraf/blob/master/plugins/inputs/internal/README.md | 2026-09-29 |
| Telegraf docker 입력 | 기본 `unix:///var/run/docker.sock`. `container_state_include` 기본 `["running"]`. `exited`·`dead` 등을 넣을 수 있다. `docker_container_status`에 `exitcode`, `oomkilled` 필드. | https://github.com/influxdata/telegraf/blob/master/plugins/inputs/docker/README.md | 2026-09-29 |
| Kafka 4.3 | "Kafka uses Yammer Metrics ... Java clients use Kafka Metrics ... Both expose metrics via JMX." 원격 JMX는 기본 꺼짐(`JMX_PORT`). 내장 Prometheus/HTTP 엔드포인트는 문서에 없다. | https://kafka.apache.org/43/operations/monitoring/ | 2026-09-29 |
| JMX exporter | Apache-2.0. Java 에이전트(`jmx_prometheus_javaagent`)와 독립 서버 두 방식. 최신 1.6.0(2026-06-05). 에이전트 방식은 별도 컨테이너가 없다. | https://github.com/prometheus/jmx_exporter · https://api.github.com/repos/prometheus/jmx_exporter/releases | 2026-09-29 |
| Flink 2.2 PrometheusReporter | `metrics.reporter.prom.factory.class: org.apache.flink.metrics.prometheus.PrometheusReporterFactory`. 기본 포트 9249, 같은 호스트 여러 개면 `9250-9260` 범위 권고. Flink 변수는 라벨로 나간다. 문서: 이 페이지의 리포터는 기본 제공. | https://github.com/apache/flink/blob/release-2.2/docs/content/docs/deployment/metric_reporters.md · https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/deployment/metric_reporters/ | 2026-09-29 |
| Flink 잡 수 지표 | JobManager 그룹에 `numRunningJobs`(Gauge, "The number of running jobs"), `numRegisteredTaskManagers`, `taskSlotsAvailable`. 잡 단위 `numRestarts`. `uptime`·`downtime`은 폐기 예정(각각 runningTime, restartingTime 등으로 대체). | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/ops/metrics/ | 2026-09-29 |
| Flink Prometheus 이름 규칙 | 소스: 이름 = `"flink_"` + 논리 스코프 + `_` + 메트릭명. JobManager 그룹 이름은 `"jobmanager"`. 따라서 `flink_jobmanager_numRunningJobs`로 조립된다. 실제 노출 문자열은 실측 필요. | https://github.com/apache/flink/blob/release-2.2/flink-metrics/flink-metrics-prometheus/src/main/java/org/apache/flink/metrics/prometheus/AbstractPrometheusReporter.java · https://github.com/apache/flink/blob/release-2.2/flink-runtime/src/main/java/org/apache/flink/runtime/metrics/groups/JobManagerMetricGroup.java | 2026-09-29 |
| Vector 0.58 | MPL-2.0. v0.58.0(2026-08-26). `internal_metrics` 소스: `component_received_events_total`, `component_sent_events_total`, `component_errors_total`, `component_discarded_events_total`, `utilization` 등. `prometheus_exporter` 싱크 기본 `0.0.0.0:9598`. | https://api.github.com/repos/vectordotdev/vector/releases · https://vector.dev/docs/reference/configuration/sources/internal_metrics/ · https://vector.dev/docs/reference/configuration/sinks/prometheus_exporter/ | 2026-09-29 |
| InfluxDB 2.9 | `GET http://localhost:8086/metrics`, Prometheus 텍스트 형식. 예: `http_api_requests_total`, `storage_wal_size`, `influxdb_uptime_seconds`. | https://docs.influxdata.com/influxdb/v2/reference/internals/metrics/ | 2026-09-29 |
| ZooKeeper 3.9 | `metricsProvider.className=org.apache.zookeeper.metrics.prometheus.PrometheusMetricsProvider`, `metricsProvider.httpPort` 기본 7000. | https://zookeeper.apache.org/doc/r3.9.4/zookeeperMonitor.html | 2026-09-29 |
| FUXA | MIT. 최신 v1.3.4(2026-08-12). 저장소 파일 트리에 metric·prom·health 이름 파일이 없다. 이슈 검색 "prometheus" 0건. `server/api/index.js`에 `/api/version` GET이 있다. Prometheus 지표 노출은 확인 못 함. | https://api.github.com/repos/frangoteam/FUXA/releases · https://github.com/frangoteam/FUXA/blob/master/server/api/index.js · https://github.com/frangoteam/FUXA/issues?q=prometheus | 2026-09-29 |
| blackbox_exporter | Apache-2.0. HTTP·HTTPS·DNS·TCP·ICMP·gRPC 탐침. `probe_success` 지표. | https://github.com/prometheus/blackbox_exporter | 2026-09-29 |

정리(위 사실만): 네이티브 Prometheus 노출은 Telegraf·Flink·Vector·InfluxDB·ZooKeeper다. Kafka는 JMX(에이전트 추가 시 노출). Mosquitto·FUXA는 네이티브 Prometheus 노출이 없다. 따라서 `up`만으로는 Mosquitto·FUXA·Kafka(에이전트 없을 때) 정지를 직접 못 잡는다.

---

## 3 · Mosquitto 감시

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| $SYS 클라이언트 토픽 | `$SYS/broker/clients/connected`, `.../disconnected`, `.../total`, `.../expired`, `.../maximum`. `active`·`inactive`는 폐기 예정 별칭. | https://mosquitto.org/man/mosquitto-8.html | 2026-09-29 |
| $SYS 메시지 토픽 | `$SYS/broker/messages/received`, `.../sent`, `$SYS/broker/mqtt/publish/received`·`sent`·`dropped`, `$SYS/broker/store/messages/count`. | https://mosquitto.org/man/mosquitto-8.html | 2026-09-29 |
| $SYS 부하(1·5·15분) | `$SYS/broker/load/messages/received/+`, `.../sent/+`, `$SYS/broker/load/publish/received/+`, `$SYS/broker/load/connections/+`, `$SYS/broker/load/sockets/+` 등. | https://mosquitto.org/man/mosquitto-8.html | 2026-09-29 |
| sys_interval | $SYS 갱신 간격(초). 기본 10. 0이면 $SYS 발행 끔. 2.1.0부터 갱신이 sys_interval 배수 시각에 맞춰진다. | https://mosquitto.org/man/mosquitto-conf-5.html · https://github.com/eclipse-mosquitto/mosquitto/blob/master/ChangeLog.txt | 2026-09-29 |
| `#` 와 `$` | MQTT 5.0 4.7.2: "A subscription to '#' will not receive messages published to topics beginning with '$'". `$SYS/#`를 명시해 구독해야 한다. | https://docs.oasis-open.org/mqtt/mqtt/v5.0/os/mqtt-v5.0-os.html | 2026-09-29 |
| sapcc/mosquitto-exporter | Apache-2.0. 마지막 릴리스 v0.8.0(2021-10-25). 저장소 마지막 푸시 2026-09-20, 보관(archived) 아님. README에 지표 목록·검증 버전 표기 없음. 기본 포트 9234. | https://github.com/sapcc/mosquitto-exporter · https://api.github.com/repos/sapcc/mosquitto-exporter/releases | 2026-09-29 |
| kpetremann/mqtt-exporter | MIT. v1.11.2(2026-02-24). 메시지 페이로드(평면 JSON 숫자)를 게이지로, `mqtt_message_total` 카운터. $SYS 처리 언급 없음. | https://github.com/kpetremann/mqtt-exporter · https://api.github.com/repos/kpetremann/mqtt-exporter/releases | 2026-09-29 |
| Telegraf mqtt_consumer | `topics`에 MQTT 와일드카드 사용. 숫자 페이로드는 `data_format = "value"`, `data_type = "float"`. README에 $SYS 예시는 없다. | https://github.com/influxdata/telegraf/blob/master/plugins/inputs/mqtt_consumer/README.md | 2026-09-29 |
| Mosquitto http_api | `/api/v1/systree` JSON(2장 참고). Prometheus 형식이 아니다. 인증 불가. | https://github.com/eclipse-mosquitto/mosquitto/blob/v2.1.2/src/http_api.c | 2026-09-29 |

---

## 4 · 컨슈머 랙

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| kafka-exporter 상태 | Apache-2.0. v1.10.0(2026-09-08), v1.9.0(2025-02-17). 저장소 마지막 푸시 2026-09-24. v1.10.0 노트: CVE 대응 의존성 갱신, Go·sarama 갱신, OAuthBearer, 컨슈머 그룹 지표 동시 워커. | https://github.com/danielqsj/kafka_exporter/releases/tag/v1.10.0 · https://api.github.com/repos/danielqsj/kafka_exporter | 2026-09-29 |
| kafka-exporter 호환 | README: "Support Apache Kafka version 0.10.1.0 (and later)". Kafka 3.8+에서는 ListGroups 그룹 유형으로 `ConsumerGroupDescribe`/`DescribeGroups`를 고른다(KIP-848). `kafka.version`을 브로커 버전으로 설정하라고 적힘. | https://github.com/danielqsj/kafka_exporter/blob/master/README.md | 2026-09-29 |
| kafka-exporter Kafka 4 질문 | 이슈 #508 "Does this tool support Kafka version 4.1.0?"(2026-01-09) 열림, 유지보수자 답 없음. | https://github.com/danielqsj/kafka_exporter/issues/508 | 2026-09-29 |
| kafka-exporter 지표 | `kafka_brokers`, `kafka_topic_partition_current_offset`, `kafka_consumergroup_lag`, `kafka_consumergroup_lag_sum`. 기본 포트 9308. | https://github.com/danielqsj/kafka_exporter/blob/master/README.md | 2026-09-29 |
| Kafka 네이티브 랙 | 컨슈머 클라이언트 JMX: `records-lag-max`, 파티션별 `records-lag`, `records-lag-avg`. 브로커 쪽 그룹 랙 HTTP 지표는 문서에 없다. | https://kafka.apache.org/43/operations/monitoring/ | 2026-09-29 |
| Flink Kafka 소스 | `pendingRecords`("not been fetched by the source"). Kafka 컨슈머 지표는 `KafkaSourceReader.KafkaConsumer` 그룹에 등록(`records-lag-max` 포함). 오프셋은 체크포인트 완료 시 커밋되며 "only for exposing the progress". `commit.offsets.on.checkpoint`로 끌 수 있다. | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/connectors/datastream/kafka/ | 2026-09-29 |
| Vector Kafka 소스 | `metrics.topic_lag_metric` 기본 false. 켜면 `kafka_consumer_lag`(topic_id·partition_id 라벨) 게이지. | https://vector.dev/docs/reference/configuration/sources/kafka/ | 2026-09-29 |
| Telegraf 랙 | `inputs.burrow`는 Burrow HTTP API에서 `lag`, `total_lag`, `status`를 읽는다. Burrow 서비스가 따로 필요하다. | https://github.com/influxdata/telegraf/blob/master/plugins/inputs/burrow/README.md | 2026-09-29 |

정리(위 사실만): 그룹 단위 랙을 브로커에서 한 번에 읽는 도구로는 kafka-exporter가 유지되고 있다(2026-09 릴리스). 대안은 소비자 쪽 지표(Flink `pendingRecords`·`records-lag-max`, Vector `kafka_consumer_lag`)다. 이것은 소비자 프로세스가 살아 있을 때만 나온다. Flink 그룹의 브로커 쪽 랙은 체크포인트 커밋 주기만큼 늦게 반영된다.

---

## 5 · 권고(사실 근거만)

### 5-1 선택

1. **Alertmanager 컨테이너를 뺀다(구성 ii).** Grafana는 내장 Alertmanager를 기본으로 쓰고, Grafana 관리 규칙이 문서상 권장 방식이다. 현재 Alertmanager는 수신자가 없다. vmalert(iii)는 발송을 Alertmanager에 맡겨 컨테이너가 줄지 않는다.
2. **kafka-exporter는 유지한다.** (e) 그룹 랙과 (d) 토픽 오프셋 증가를 브로커 기준으로 한 컨테이너가 준다. 2026-09-08 릴리스로 유지 중이다. 단 Kafka 4.x 공식 호환 표기는 없다(이슈 #508 미답). 현 스택에서 동작 여부는 실측으로 확인한다.
3. **cAdvisor는 유지한다.** Mosquitto·FUXA는 Prometheus 노출이 없어 `up`으로 못 잡는다. cAdvisor는 모든 컨테이너를 한 곳에서 보고 인프라 패널(CPU·메모리)도 준다. 빼고 blackbox_exporter를 넣으면 컨테이너 수는 같다.
4. **Mosquitto는 새 익스포터 없이 이미 있는 Telegraf로 읽는다.** `$SYS/#` 명시 구독(`#`로는 안 받음) → `outputs.prometheus_client`. sapcc 익스포터는 마지막 릴리스가 2021-10-25다.
5. **컨테이너를 3개까지 줄이려면 Alloy(iv)**가 사실상 유일하다. 단 Alloy 지원 기간, 내장 kafka_exporter 버전, Kafka 4.3 호환, 원격쓰기 수신 구성은 확인 못 했다.

결과: 감시용 컨테이너 5개 → 4개(Prometheus, Grafana, kafka-exporter, cAdvisor). 나머지는 설정 추가다(Flink·ZooKeeper·Vector·Telegraf·InfluxDB 스크레이프, Telegraf $SYS 구독).

### 5-2 요구별 최소 구성표

| 요구 | 쓸 지표·규칙(예) | 추가 컨테이너 | 근거 |
|---|---|---|---|
| (a) 컨테이너 정지 | 지표 노출 서비스: `up == 0` 또는 `absent(up{job="..."})`. Mosquitto·FUXA 포함 전체: cAdvisor `container_last_seen`이 멈춘 것을 `time() - container_last_seen > N`으로 판정. docker_sd를 쓰면 정지 컨테이너가 대상에서 사라지므로 `absent()` 사용. | 없음(cAdvisor 기존) | 2장 `up`·`absent`·docker_sd·cAdvisor 행 |
| (b) JM 생존·잡 정지 | `flink_jobmanager_numRunningJobs < 4` 그리고 `up{job="flink-jm"} == 1`. 재시작 폭주는 잡 단위 `numRestarts` 증가. | 없음 | 2장 Flink 행 |
| (c) 브로커 다운·클라이언트 끊김 | Mosquitto: Telegraf가 읽은 `$SYS/broker/clients/connected` 감소, 그 시계열 `absent_over_time(...[1m])`. Kafka: kafka-exporter `kafka_brokers < 1` 또는 JMX 에이전트 `up`. | 없음(JMX 에이전트는 Kafka JVM 안) | 3장 $SYS·`#` 행, 4장 지표 행, 2장 JMX 행 |
| (d) 적재 정지 | 입구: Telegraf `internal_gather` modbus `metrics_gathered` 증가율 0. 중간: `rate(kafka_topic_partition_current_offset{topic="raw"}[1m]) == 0`. 출구: Vector InfluxDB 싱크 `component_sent_events_total` 증가율 0. 저장소: Grafana 관리 규칙이 InfluxDB를 조회하고 No Data 기본 동작(`DatasourceNoData`) 사용. | 없음 | 2장 Telegraf·Vector 행, 4장 kafka-exporter 행, 1장 No Data 행 |
| (e) 컨슈머 랙 | `kafka_consumergroup_lag_sum`. Vector는 `metrics.topic_lag_metric = true` 후 `kafka_consumer_lag`. Flink는 `pendingRecords`. | 없음 | 4장 |
| 인프라 패널 | cAdvisor 컨테이너 CPU·메모리, InfluxDB `/metrics`, Vector `utilization`. | 없음 | 2장 |

---

## 6 · 확인 못 한 것 [미확인]

- Alertmanager의 공개 지원 기간 문서.
- Grafana Alloy 마이너별 지원 기간, `prometheus.exporter.kafka`·`prometheus.exporter.cadvisor`의 안정성 등급과 내장 버전.
- kafka-exporter 1.10의 Kafka 4.3 KRaft 공식 호환 여부(README 표기는 "0.10.1.0 이후"뿐, 이슈 #508 미답).
- Kafka 브로커가 죽었을 때 kafka-exporter가 `kafka_brokers`를 0으로 내는지, 스크레이프 자체가 실패하는지.
- static_configs에서 컨테이너 정지 시 `up=0`으로 바뀌는지(DNS 해석 실패 동작 포함). 실측 필요.
- `flink_jobmanager_numRunningJobs`의 실제 노출 문자열(소스 조립 규칙만 확인). 실측 필요.
- InfluxDB 2.9 `/metrics`의 인증 요구 여부와 끄는 설정.
- FUXA의 헬스·지표 엔드포인트 공식 문서(소스 트리·이슈에서 못 찾음). `/api/version`의 인증 필요 여부.
- sapcc/mosquitto-exporter의 Mosquitto 2.1 호환 여부와 지표 목록.
- Kafka 4.x KIP-714 클라이언트 지표 푸시(ClientTelemetry)가 랙 감시 대안이 되는지. 4.3 모니터링 문서에서 못 찾음.
- Burrow의 라이선스·유지 상태.
