# 09 · 단일 호스트 IIoT 스택 경량화 사이징 (문헌 조사)

- 확인일: 2026-09-29 (모든 행 공통. 행별로 다르면 표에 적음)
- 범위: 공식 문서·릴리스 노트·Docker Hub 태그 API·GitHub 소스만. 컨테이너 실행 없음.
- 확인 못 한 것은 "[미확인]"으로 적었다. 추정하지 않았다.
- 측정 배경(요청자 제공 값, 이 문서가 재측정한 값 아님): TM RSS 1,434 MiB(process.size 4608m), JM RSS 603 MiB(1600m), Kafka 4.3.1 RSS 839 MiB(-Xmx1G -Xms1G), ZooKeeper 3.9.5 RSS 99 MiB, Grafana 13.2.2 476 MiB, InfluxDB 2.9.1 140 MiB, Telegraf 1.40.1 136 MiB.

(작성 완료: 절 1–6, 경량화 후보 설정, 확인 못 한 것.)

## 1 · Flink 2.2 메모리·상태 백엔드

소스 확인 기준: `apache/flink` 저장소 `release-2.2` 브랜치(태그 `release-2.2.1` 존재 확인).

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| JM 기본값 | `jobmanager.memory.jvm-metaspace.size` 256 mb, `jvm-overhead.min` 192 mb, `jvm-overhead.max` 1 gb, `jvm-overhead.fraction` 0.1, `off-heap.size` 128 mb. `process.size`는 기본값 없음. | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/deployment/config/ | 2026-09-29 |
| TM 기본값 | `jvm-metaspace.size` 256 mb, `jvm-overhead.min` 192 mb / `max` 1 gb / `fraction` 0.1, `managed.fraction` 0.4, `network.min` 64 mb / `max` infinite / `fraction` 0.1, `framework.heap.size` 128 mb, `framework.off-heap.size` 128 mb, `task.off-heap.size` 0, `numberOfTaskSlots` 1. | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/deployment/config/ | 2026-09-29 |
| 배포본 config.yaml | 배포 기본 설정 파일은 `jobmanager.memory.process.size: 1600m`, `taskmanager.memory.process.size: 1728m`, `numberOfTaskSlots: 1`, `parallelism.default: 1`. | https://github.com/apache/flink/blob/release-2.2/flink-dist/src/main/resources/config.yaml | 2026-09-29 |
| JM 힙 최소 | `jobmanager.memory.heap.size` 설명: "The minimum recommended JVM Heap size is 128 mb". 코드 상수 `MIN_JVM_HEAP_SIZE = MemorySize.ofMebiBytes(128)`. 이보다 작으면 경고 로그만 남긴다(예외 아님): "The configured or derived JVM heap memory size (%s) is less than its recommended minimum value (%s)". | https://github.com/apache/flink/blob/release-2.2/flink-core/src/main/java/org/apache/flink/configuration/JobManagerOptions.java , https://github.com/apache/flink/blob/release-2.2/flink-runtime/src/main/java/org/apache/flink/runtime/util/config/memory/jobmanager/JobManagerFlinkMemoryUtils.java | 2026-09-29 |
| JM 예외 조건 | Total Flink Memory가 Off-heap보다 작으면 `IllegalConfigurationException`. 힙이 Total Flink Memory를 넘어도 예외. | 위 JobManagerFlinkMemoryUtils.java | 2026-09-29 |
| TM 예외 조건 | Task Heap은 나머지로 계산된다. Framework Heap + Framework Off-Heap + Task Off-Heap + Managed + Network 합이 Total Flink Memory를 넘으면 예외("... exceed configured Total Flink Memory"). Network가 [min,max] 밖이면 예외. Task Heap·Managed에 하드코딩 최소값은 없다. | https://github.com/apache/flink/blob/release-2.2/flink-runtime/src/main/java/org/apache/flink/runtime/util/config/memory/taskmanager/TaskExecutorFlinkMemoryUtils.java | 2026-09-29 |
| 상한·하한 규칙 | 비율로 계산한 값이 min보다 작으면 min을 쓴다. max보다 크면 기동 실패(문서 표현). min=max로 두면 크기를 고정한다. | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/deployment/memory/mem_setup/ | 2026-09-29 |
| JVM 인자 | TM `-Xmx/-Xms` = Framework Heap + Task Heap. JM은 JVM Heap. `-XX:MaxDirectMemorySize` = Framework Off-heap + Task Off-heap + Network(TM). `-XX:MaxMetaspaceSize` = Metaspace. | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/deployment/memory/mem_setup/ | 2026-09-29 |
| 컨테이너 권장 | 컨테이너 배포는 `*.memory.process.size`로 전체 프로세스 메모리를 설정하라고 권장한다. | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/deployment/memory/mem_tuning/ | 2026-09-29 |
| HashMap + managed 0 | mem_tuning: "When running a stateless job or using the HashMapStateBackend, set managed memory to zero." state_backends: "It is also recommended to set managed memory to zero." | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/deployment/memory/mem_tuning/ , https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/ops/state/state_backends/ | 2026-09-29 |
| RocksDB 메모리 | 기본적으로 RocksDB 메모리 할당을 TM managed memory 크기에 맞춘다. RocksDB는 native 메모리를 쓴다. | 위 두 문서 | 2026-09-29 |
| HashMap 체크포인트 | 상태는 Java 힙 객체로 보관하고, 체크포인트는 설정한 checkpoint storage 디렉터리에 쓴다. 문서의 권장 용도에 "All high-availability setups"가 있다. | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/ops/state/state_backends/ | 2026-09-29 |
| 증분 체크포인트 | EmbeddedRocksDBStateBackend는 "currently the only backend that offers incremental checkpoints"(문서 문구). ForSt(실험적)는 비동기 증분 스냅샷을 지원한다고 적혀 있다. HashMap은 증분 체크포인트 대상이 아니다. | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/ops/state/state_backends/ | 2026-09-29 |
| 기본 백엔드 | `state.backend.type` 기본값 "hashmap", `execution.checkpointing.incremental` 기본값 false. | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/deployment/config/ | 2026-09-29 |
| 백엔드 전환 | 1.13부터 savepoint 이진 형식이 통일되어 다른 백엔드로 복원할 수 있다고 적혀 있다. | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/ops/state/state_backends/ | 2026-09-29 |
| 로컬 복구 | HashMap은 keyed state의 task-local recovery를 지원하며 상태를 로컬 파일로 복제한다. 기본 비활성(`state.backend.local-recovery`). | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/ops/state/large_state_tuning/ | 2026-09-29 |
| 슬롯·병렬도 | "A Flink cluster needs exactly as many task slots as the highest parallelism used in the job."(한 잡 안의 slot sharing 기준). 슬롯은 managed memory만 나누고 CPU 격리는 없다. | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/concepts/flink-architecture/ | 2026-09-29 |

### 1-a 문서 규칙에서 계산한 최소 크기 (실행 검증 안 함)

아래는 위 기본값과 규칙을 그대로 더한 산술값이다. 기동 여부는 실행으로 확인하지 않았다.

| 대상 | 조건 | 계산 | 결과 |
|---|---|---|---|
| JM | 힙을 권장 최소 128m로 맞출 때 | 힙 128 + off-heap 128 + metaspace 256 + overhead min 192 (0.1×P가 192보다 작음) | process.size 704m. 이보다 작으면 힙 128m 미만 경고. Total Flink Memory(=P−448m)가 off-heap 128m보다 작아지는 576m 미만은 예외 조건. |
| TM | `managed.size: 0`(또는 fraction 0), 다른 값 기본 | framework heap 128 + framework off-heap 128 + network min 64 + metaspace 256 + overhead min 192 | 768m에서 Task Heap이 0이 된다(합이 "초과"일 때만 예외). 실제 연산자·ONNX가 쓸 Task Heap은 이 위에 더해야 한다. |
| TM | managed fraction 기본 0.4 | Total Flink F: 0.6F ≥ 128+128+64 → F ≥ 약 534m, + 448m | 약 982m에서 Task Heap 0. |

측정값과 대조: TM heap used 527 MB(요청자 제공). -Xmx = framework heap 128m + task heap이므로 task heap을 이 사용량보다 여유 있게 두어야 한다. 얼마가 적정한지는 [미확인](부하 측정 필요).

## 2 · Kafka 4.3 (KRaft 단일 노드)

소스 확인 기준: `apache/kafka` 태그 `4.3.1`(gradle.properties `version=4.3.1`). 4.3.2는 Docker Hub에 `4.3.2-rc0`만 있다(2026-09-28 갱신).

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| 힙 기본값 | `bin/kafka-server-start.sh`: `KAFKA_HEAP_OPTS`가 비어 있으면 `export KAFKA_HEAP_OPTS="-Xmx1G -Xms1G"`. | https://github.com/apache/kafka/blob/4.3.1/bin/kafka-server-start.sh | 2026-09-29 |
| 공식 JVM 예시 | 운영 문서의 "Typical arguments"는 `-Xmx6g -Xms6g -XX:MetaspaceSize=96m -XX:+UseG1GC ...`이며, LinkedIn 60 브로커·80만 msg/s 클러스터 기준 예시다. 소규모·단일 노드용 힙 권장값은 문서에 없다. | https://github.com/apache/kafka/blob/4.3.1/docs/operations/java-version.md (게시본 https://kafka.apache.org/43/operations/) | 2026-09-29 |
| 지원 Java | Java 17·21·25 완전 지원. 최신 LTS(작성 시 Java 25) 권장. | 위 java-version.md | 2026-09-29 |
| JVM 이미지 힙 설정 경로 | `apache/kafka` 이미지 `docker/jvm/launch`는 마지막에 `exec /opt/kafka/bin/kafka-server-start.sh ...`를 호출한다. 따라서 위 스크립트의 `KAFKA_HEAP_OPTS` 분기가 적용된다(소스 흐름). 이미지 문서에 `KAFKA_HEAP_OPTS` 항목은 따로 없다. | https://github.com/apache/kafka/blob/4.3.1/docker/jvm/launch , https://github.com/apache/kafka/blob/4.3.1/docker/examples/README.md | 2026-09-29 |
| JVM 이미지 기반 | `docker/jvm/Dockerfile` 최종 단계 `FROM eclipse-temurin:21-jre-alpine`. 기동 시 CDS 아카이브(`-XX:SharedArchiveFile=/opt/kafka/kafka.jsa`)를 `KAFKA_JVM_PERFORMANCE_OPTS`에 덧붙인다. | https://github.com/apache/kafka/blob/4.3.1/docker/jvm/Dockerfile , 위 launch | 2026-09-29 |
| 이미지 기본 설정 | 설정을 안 주면 단일 combined-mode KRaft 기본 설정을 쓴다. 기본 파일 값: `num.network.threads=3`, `num.io.threads=8`, `num.recovery.threads.per.data.dir=2`, `log.retention.check.interval.ms=300000`. 환경변수는 `KAFKA_` 접두사 + `.`→`_` 규칙. | https://github.com/apache/kafka/blob/4.3.1/docker/server.properties , https://github.com/apache/kafka/blob/4.3.1/docker/examples/README.md | 2026-09-29 |
| 스레드·버퍼 기본값 | `background.threads` 10, `num.io.threads` 8, `num.network.threads` 3, `num.replica.fetchers` 1, `log.cleaner.threads` 1, `log.cleaner.enable` true, `log.cleaner.dedupe.buffer.size` 134217728, `queued.max.requests` 500, `metadata.log.max.snapshot.interval.ms` 3600000. | https://kafka.apache.org/43/configuration/broker-configs/ | 2026-09-29 |
| 유휴 CPU 공식 지침 | 유휴 CPU를 줄이는 공식 지침 문서는 찾지 못했다. | [미확인] | 2026-09-29 |
| kafka-native 상태 | 공식 문서: "This image is experimental and intended for local development and testing purposes only; it is not recommended for production use." 3.8.0부터 제공. 기동 스크립트도 "WARNING: THIS IS AN EXPERIMENTAL DOCKER IMAGE ..."를 출력한다. | https://github.com/apache/kafka/blob/4.3.1/docs/getting-started/docker.md , https://github.com/apache/kafka/blob/4.3.1/docker/native/launch | 2026-09-29 |
| KIP-974 | Current state "Accepted". "recommended only for development, and testing and not for production workloads." KIP 본문 측정 예: 기동 ~130ms(native serial+PGO) 대 ~1150–1200ms(JVM), 메모리 ~250MB(native serial) 대 ~1GB(JVM). KIP 작성 당시 수치다. | https://cwiki.apache.org/confluence/display/KAFKA/KIP-974%3A+Docker+Image+for+GraalVM+based+Native+Kafka+Broker | 2026-09-29 |
| kafka-native 제약 | 동적 기능은 정적 메타데이터에 의존. 사용자 런타임 jar 추가 불가(재빌드 필요). GraalVM Community라서 serial GC만 지원, G1 미지원. | https://github.com/apache/kafka/blob/4.3.1/docker/native/README.md | 2026-09-29 |
| kafka-native 이미지 기반 | 빌드 `ghcr.io/graalvm/graalvm-community:21`, 최종 `FROM alpine:latest`. | https://github.com/apache/kafka/blob/4.3.1/docker/native/Dockerfile | 2026-09-29 |
| kafka-native 힙 경로 | native `launch`는 `kafka-server-start.sh`를 거치지 않고 `exec /opt/kafka/kafka.Kafka start --config ... $KAFKA_LOG4J_CMD_OPTS $KAFKA_JMX_OPTS ${KAFKA_OPTS-}`를 실행한다. 즉 `KAFKA_HEAP_OPTS`는 쓰이지 않는다(소스 흐름). `KAFKA_OPTS`로 `-Xmx`를 넘기면 적용되는지는 문서에 없다. | https://github.com/apache/kafka/blob/4.3.1/docker/native/launch | 2026-09-29 |
| GraalVM 힙 기본 | Serial GC native image는 최대 힙을 지정하지 않으면 "80% of the physical memory size"로 잡는다. 실행 시 `-Xmx/-Xms/-Xmn` 지정 가능. GC 중 RSS가 일시적으로 늘 수 있다(최악 2배). | https://www.graalvm.org/jdk21/reference-manual/native-image/optimizations-and-performance/MemoryManagement/ | 2026-09-29 |
| kafka-native 4.3.x 태그 | `4.3.0`, `4.3.1`(2026-06-23), 후보 `4.3.2-rc0`. | https://hub.docker.com/v2/repositories/apache/kafka-native/tags?name=4.3 | 2026-09-29 |

## 3 · ZooKeeper 3.9 공식 이미지

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| 이미지 태그 | 공식 이미지 `zookeeper` 태그 `3.9.5, 3.9, 3.9.5-jre-17, 3.9-jre-17, latest`가 같은 디렉터리(3.9.5)에서 빌드된다. 즉 3.9.5와 3.9.5-jre-17은 같은 이미지다. | https://github.com/docker-library/official-images/blob/master/library/zookeeper | 2026-09-29 |
| 베이스 | `3.9.5/Dockerfile`: `FROM eclipse-temurin:17-jre-jammy`. | https://github.com/31z4/zookeeper-docker/blob/master/3.9.5/Dockerfile | 2026-09-29 |
| 힙 설정(이미지 문서) | `JVMFLAGS` 환경변수를 문서화한다. 예: `-e JVMFLAGS="-Xmx1024m"`(최대 힙 1 GB 예시). | https://github.com/docker-library/docs/blob/master/zookeeper/content.md | 2026-09-29 |
| 기본 힙(배포 스크립트) | `bin/zkEnv.sh`: `ZK_SERVER_HEAP="${ZK_SERVER_HEAP:-1000}"`, `SERVER_JVMFLAGS="-Xmx${ZK_SERVER_HEAP}m $SERVER_JVMFLAGS"`. `zkServer.sh`는 `JVMFLAGS="$SERVER_JVMFLAGS $JVMFLAGS"`로 합친다(사용자 `JVMFLAGS`가 뒤에 붙는다). | https://github.com/apache/zookeeper/blob/release-3.9.5/bin/zkEnv.sh , https://github.com/apache/zookeeper/blob/release-3.9.5/bin/zkServer.sh | 2026-09-29 |
| 기타 env | `ZOO_TICK_TIME`, `ZOO_INIT_LIMIT`, `ZOO_SYNC_LIMIT`, `ZOO_MAX_CLIENT_CNXNS`, `ZOO_STANDALONE_ENABLED`, `ZOO_ADMINSERVER_ENABLED`, `ZOO_AUTOPURGE_PURGEINTERVAL`, `ZOO_AUTOPURGE_SNAPRETAINCOUNT`, `ZOO_4LW_COMMANDS_WHITELIST`, `ZOO_CFG_EXTRA`. | https://github.com/docker-library/docs/blob/master/zookeeper/content.md | 2026-09-29 |
| 공식 힙 지침 | "Set the Java heap size. This is very important to avoid swapping ..." 적정값은 부하 시험으로 정하라고 한다. 예시는 "maximum heap size of 3GB for a 4GB machine". 문서화된 최소 힙 값은 없다. | https://zookeeper.apache.org/doc/r3.9.5/zookeeperAdmin.html | 2026-09-29 |

## 4 · Grafana 13

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| 지원 정책 | "Each minor release is supported for 9 months after its release date". 메이저의 마지막 마이너는 15개월. | https://grafana.com/docs/grafana/latest/upgrade-guide/when-to-upgrade/ | 2026-09-29 |
| 지원 종료일 | 12.4.x(12의 마지막 마이너): 출시 2026-02-24, 지원 종료 2027-05-24. 13.0.x: 2027-01-09. 13.1.x: 2027-03-20. 13.2.x: 출시 2026-08-18, 종료 2027-05-18. | 위 URL | 2026-09-29 |
| 이미지 변형 | Alpine(기본), Ubuntu, Distroless 기반이 있고 각각 slim 변형이 있다. 태그 접미사: `-slim`, `-ubuntu-slim`, `-distroless`, `-distroless-slim`. | https://github.com/grafana/grafana/blob/main/docs/sources/setup-grafana/configure-docker.md , https://github.com/grafana/grafana/pull/132894 | 2026-09-29 |
| slim의 차이 | "Slim images don't include the plugins that Grafana bundles with the standard images." 필요한 플러그인은 `GF_PLUGINS_PREINSTALL`로 기동 때 설치한다. | 위 configure-docker.md | 2026-09-29 |
| distroless의 차이 | 셸·패키지 관리자·범용 OS 도구가 없다. Alpine은 musl libc를 쓴다는 제약이 적혀 있다. | 위 configure-docker.md | 2026-09-29 |
| 기본 preinstall 목록 | v13.2.2 소스 `defaultPreinstallPlugins`에 `influxdb`가 들어 있다. 그 밖에 grafana-lokiexplore-app, grafana-pyroscope-app, grafana-exploretraces-app, grafana-metricsdrilldown-app, elasticsearch, prometheus, tempo, zipkin, opentsdb, stackdriver, mssql, jaeger, loki, mysql, grafana-advisor-app, grafana-postgresql-datasource, grafana-pyroscope-datasource. | https://github.com/grafana/grafana/blob/v13.2.2/pkg/setting/setting_plugins.go | 2026-09-29 |
| preinstall 설정 | `[plugins] preinstall`(비동기 설치), `preinstall_sync`(기동 전 동기 설치, provisioning과 함께 쓸 때 유용), `preinstall_disabled`(기본 false, 모든 preinstall 비활성), `preinstall_auto_update`(defaults.ini 기본 true), `disable_plugins`(코어 포함 로드하지 않을 플러그인 목록). | https://github.com/grafana/grafana/blob/v13.2.2/docs/sources/setup-grafana/configure-grafana/_index.md , https://github.com/grafana/grafana/blob/v13.2.2/conf/defaults.ini | 2026-09-29 |
| 환경변수 규칙 | `GF_<SECTION>_<KEY>` (예: `GF_PLUGINS_PREINSTALL`). | https://grafana.com/docs/grafana/latest/setup-grafana/installation/docker/ | 2026-09-29 |
| 기타 끌 수 있는 기능 | `[unified_alerting] enabled` 기본 true. `[analytics] reporting_enabled`, `check_for_updates`, `check_for_plugin_updates`. `[live] max_connections` 기본 100. `[expressions] math_expression_memory_limit` 기본 1 GiB. | 위 _index.md | 2026-09-29 |
| 메모리 절감 공식 지침 | "메모리를 줄이는 방법"을 다루는 공식 문서는 찾지 못했다. 위 설정이 RSS를 얼마나 줄이는지 문서 근거 없음. | [미확인] | 2026-09-29 |
| slim + InfluxDB | slim 이미지에서 InfluxDB 데이터소스가 설치 없이 동작하는지는 문서에 명시 없음. 위 사실(slim은 번들 플러그인 제외, influxdb가 기본 preinstall 목록)만 확인. | [미확인] | 2026-09-29 |

## 5 · InfluxDB 2.9 · Telegraf 1.40

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| storage 캐시 | `storage-cache-max-memory-size` 기본 1073741824(1 GiB). 샤드 캐시가 이 크기에 닿으면 쓰기를 거부한다. env `INFLUXD_STORAGE_CACHE_MAX_MEMORY_SIZE`. | https://docs.influxdata.com/influxdb/v2/reference/config-options/ | 2026-09-29 |
| 캐시 스냅샷 | `storage-cache-snapshot-memory-size` 기본 26214400(25 MiB). `storage-cache-snapshot-write-cold-duration` 기본 10m0s. | 위 URL | 2026-09-29 |
| 기타 storage | `storage-max-concurrent-compactions` 기본 0, `storage-series-id-set-cache-size` 기본 100, `storage-wal-max-concurrent-writes` 기본 0. | 위 URL | 2026-09-29 |
| 쿼리 메모리 | `query-memory-bytes` 기본 무제한(단일 쿼리 한도). `query-max-memory-bytes` 기본 = query-concurrency × query-memory-bytes. `query-initial-memory-bytes` 기본 = query-memory-bytes. `query-concurrency`, `query-queue-size` 기본 0(문서 표기). | 위 URL | 2026-09-29 |
| 끌 수 있는 기능 | `reporting-disabled`, `ui-disabled`, `metrics-disabled`, `pprof-disabled` 모두 기본 false. `log-level` 기본 info. | 위 URL | 2026-09-29 |
| Telegraf agent | `interval` 10s, `metric_batch_size` 1000, `metric_buffer_limit` 10000(출력별, 가득 차면 가장 오래된 것을 덮어씀), `buffer_strategy` 기본 memory(disk 선택 가능), `flush_interval` 10s. 버퍼 한도를 올리면 메모리를 더 쓴다고 적혀 있다. | https://docs.influxdata.com/telegraf/v1/configuration/agent/ | 2026-09-29 |
| Telegraf custom_builder | "a tool to select the plugins compiled into the Telegraf binary ... Telegraf can become smaller, saving both disk space and memory if only a sub-set of plugins is selected." Go와 make가 필요하다(직접 빌드). | https://github.com/influxdata/telegraf/blob/master/tools/custom_builder/README.md | 2026-09-29 |
| Go 메모리 한도 | InfluxDB·Telegraf 문서에서 `GOMEMLIMIT` 등 Go 런타임 메모리 설정 안내는 찾지 못했다. | [미확인] | 2026-09-29 |

## 6 · 이미지 변형과 크기 (Docker Hub API)

크기는 Docker Hub 태그 API의 `size` 값을 MiB로 바꾼 것이다. 이 값은 압축 레이어 크기로 널리 해석되며, 풀어서 디스크에 놓인 크기가 아니다(해석의 공식 문서 근거는 [미확인]). 조회: `https://hub.docker.com/v2/repositories/<repo>/tags?name=<tag>`.

| 이미지:태그 | amd64 MiB | arm64 MiB | 갱신일 | 비고 |
|---|---|---|---|---|
| apache/kafka:4.3.1 | 227.8 | 227.5 | 2026-06-23 | JVM, eclipse-temurin:21-jre-alpine 기반 |
| apache/kafka-native:4.3.1 | 52.5 | 52.0 | 2026-06-23 | GraalVM native, alpine 기반, 실험적 |
| apache/kafka:4.3.2-rc0 / kafka-native:4.3.2-rc0 | 224.3 / 53.4 | 223.8 / 52.8 | 2026-09-28 | 릴리스 후보 |
| flink:2.2.1 (= 2.2.1-java17 = 2.2.1-scala_2.12) | 634.0 | 632.6 | 2026-09-26 | 기본 태그는 java17. `FROM eclipse-temurin:17-jre-noble` |
| flink:2.2.1-java21 | 639.3 | 637.6 | 2026-09-26 | |
| flink:2.2.1-java11 | 633.8 | 631.3 | 2026-09-26 | |
| zookeeper:3.9.5 (= 3.9.5-jre-17) | 111.9 | 109.3 | 2026-09-26 | 3.9.5는 jre-17 변형 하나뿐 |
| influxdb:2.9.1 | 105.7 | 101.4 | 2026-09-19 | |
| influxdb:2.9.1-alpine | 82.8 | 79.1 | 2026-09-18 | |
| telegraf:1.40.1 | 172.2 | 162.6 | 2026-09-21 | |
| telegraf:1.40.1-alpine | 93.3 | 84.6 | 2026-09-21 | |
| grafana/grafana:13.2.2 (Alpine) | 453.7 | 418.3 | 2026-09-15 | |
| grafana/grafana:13.2.2-slim | 304.8 | 282.2 | 2026-09-15 | 번들 플러그인 없음 |
| grafana/grafana:13.2.2-distroless | 439.0 | 411.5 | 2026-09-15 | |
| grafana/grafana:13.2.2-distroless-slim | 290.1 | 275.4 | 2026-09-15 | |
| grafana/grafana:13.2.2-ubuntu | 471.7 | 443.6 | 2026-09-15 | |
| grafana/grafana:13.2.2-ubuntu-slim | 322.8 | 307.5 | 2026-09-15 | |
| grafana/grafana:12.4.12 | 284.0 | 261.9 | 2026-09-29 | 조회 시점 12.4 최신 패치 |

출처: https://hub.docker.com/v2/repositories/apache/kafka/tags?name=4.3 , https://hub.docker.com/v2/repositories/apache/kafka-native/tags?name=4.3 , https://hub.docker.com/v2/repositories/library/flink/tags?name=2.2.1 , https://hub.docker.com/v2/repositories/library/zookeeper/tags?name=3.9 , https://hub.docker.com/v2/repositories/library/influxdb/tags?name=2.9.1 , https://hub.docker.com/v2/repositories/library/telegraf/tags?name=1.40.1 , https://hub.docker.com/v2/repositories/grafana/grafana/tags?name=13.2.2 , https://hub.docker.com/v2/repositories/grafana/grafana/tags?name=12.4 (모두 2026-09-29 조회)

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| Flink 태그 매핑 | `2.2.1, 2.2, 2.2.1-java17, 2.2.1-scala_2.12`는 같은 `2.2/scala_2.12-java17-ubuntu`에서 빌드. java21·java11은 별도 디렉터리. Scala는 2.12만 있다. | https://github.com/docker-library/official-images/blob/master/library/flink | 2026-09-29 |
| Flink 이미지 env | 엔트리포인트가 `FLINK_PROPERTIES`를 설정에 반영한다. 기본으로 jemalloc을 쓰며 `DISABLE_JEMALLOC=true`로 끈다. | https://github.com/apache/flink-docker/blob/983be3455636eb12cd1d3dee1efc8e32c4b875db/2.2/scala_2.12-java17-ubuntu/docker-entrypoint.sh | 2026-09-29 |
| InfluxDB 태그 | `2, 2.9, 2.9.1, latest`와 `2-alpine, 2.9-alpine, 2.9.1-alpine, alpine`이 별도 디렉터리. 같은 파일에 `3.9-core, 3.9.13-core`도 있다. | https://github.com/docker-library/official-images/blob/master/library/influxdb | 2026-09-29 |
| Telegraf 태그 | `1.40, 1.40.1, latest`와 `1.40-alpine, 1.40.1-alpine, alpine`. | https://github.com/docker-library/official-images/blob/master/library/telegraf | 2026-09-29 |

## 경량화 후보 설정 (사실 근거만, 효과 예상 금지)

각 줄은 위 표의 사실만 근거로 든다. 줄어드는 양·지연·복구 영향은 적지 않았다. 적용 전 실행 측정이 필요하다.

| 구성요소 | 후보 설정 | 근거가 된 사실 | 주의(문서에 적힌 것 또는 미확인) |
|---|---|---|---|
| Flink TM | `state.backend.type: hashmap` + `taskmanager.memory.managed.size: 0`(또는 fraction 0) | 문서가 HashMap 사용 시 managed memory 0을 권장. RocksDB가 managed memory를 쓴다. | HashMap은 증분 체크포인트 대상이 아니다. 상태는 힙에 있다. 체크포인트는 checkpoint storage에 쓴다. |
| Flink TM | `taskmanager.memory.process.size`를 줄이되 Task Heap이 남도록 | 규칙 계산상 managed 0이면 768m에서 Task Heap 0. -Xmx = 128m + Task Heap. | 현재 heap used 527 MB(요청자 측정). 적정 Task Heap은 [미확인]. |
| Flink TM | `taskmanager.numberOfTaskSlots`를 잡들의 필요 슬롯 합에 맞춤 | 한 잡은 최고 병렬도만큼 슬롯이 필요. 슬롯은 managed memory만 나눈다. | 4잡×병렬도2 = 8 슬롯은 현재 구성과 일치(산술). |
| Flink JM | `jobmanager.memory.process.size` 704m 이상 | 힙 권장 최소 128m. 704m은 기본 off-heap·metaspace·overhead min의 합. | 128m 미만은 경고만. 576m 미만은 예외 조건(계산). 실행 확인 안 함. |
| Flink 공통 | `jvm-metaspace.size`, `jvm-overhead.min`도 설정 가능한 값 | 기본 256m, 192m. | 낮췄을 때 안전한 값은 [미확인]. |
| Kafka(JVM) | `KAFKA_HEAP_OPTS="-Xmx… -Xms…"` | 이미지 launch가 `kafka-server-start.sh`를 거치고, 비었을 때만 1G 기본값이 들어간다. | 단일 노드용 권장 힙은 문서에 없다. |
| Kafka(JVM) | `KAFKA_NUM_IO_THREADS`, `KAFKA_NUM_NETWORK_THREADS`, `KAFKA_BACKGROUND_THREADS`, `KAFKA_LOG_CLEANER_DEDUPE_BUFFER_SIZE` | 기본 8, 3, 10, 134217728. 이미지 env 이름 규칙. | 유휴 CPU·메모리 효과 근거 없음 [미확인]. |
| Kafka(native) | `apache/kafka-native:4.3.1` | 이미지 52.5 MiB. KIP 측정 ~250MB. | 공식: 실험적, 운영 비권장. serial GC만. 사용자 jar 불가. 힙은 `KAFKA_HEAP_OPTS` 경로가 아님. |
| ZooKeeper | `JVMFLAGS="-Xmx…"` 또는 `ZK_SERVER_HEAP` | 기본 `-Xmx1000m`. 사용자 `JVMFLAGS`가 뒤에 붙는다. | 문서화된 최소값 없음. 스왑 금지 지침. |
| Grafana | `13.2.2-slim` 또는 `-distroless-slim` + `GF_PLUGINS_PREINSTALL_SYNC=influxdb` 등 필요한 것만 | slim은 번들 플러그인 제외. influxdb가 기본 preinstall 목록에 있다. `preinstall_sync`는 기동 전 설치. | preinstall은 Grafana 카탈로그에서 받는다. 오프라인 동작은 [미확인]. |
| Grafana | `GF_PLUGINS_PREINSTALL_AUTO_UPDATE=false`, `GF_ANALYTICS_REPORTING_ENABLED=false`, `GF_ANALYTICS_CHECK_FOR_UPDATES=false`, `GF_ANALYTICS_CHECK_FOR_PLUGIN_UPDATES=false` | 설정 존재·기본값 확인. | 메모리 효과 근거 없음. |
| Grafana | `GF_UNIFIED_ALERTING_ENABLED=false` | 기본 true. | 스택이 Grafana 알림을 쓰면 끄면 안 된다. 메모리 효과 근거 없음. |
| Grafana 버전 | 12.4.x 지원 종료 2027-05-24, 13.2.x는 2027-05-18 | 공식 지원 표. | |
| InfluxDB | `influxdb:2.9.1-alpine` | 이미지 82.8 MiB(기본 105.7). | |
| InfluxDB | `INFLUXD_STORAGE_CACHE_MAX_MEMORY_SIZE`, `INFLUXD_QUERY_MEMORY_BYTES`, `INFLUXD_QUERY_CONCURRENCY`, `INFLUXD_UI_DISABLED`, `INFLUXD_REPORTING_DISABLED` | 기본 1 GiB, 무제한, 0, false, false. | 캐시 한도에 닿으면 쓰기 거부. UI를 끄면 웹 UI 사용 불가. |
| Telegraf | `telegraf:1.40.1-alpine` | 93.3 MiB(기본 172.2). | |
| Telegraf | `metric_buffer_limit` 조정, custom_builder로 필요한 플러그인만 빌드 | 버퍼가 클수록 메모리 더 씀(문서). custom_builder는 디스크·메모리 절감 목적(문서). | custom_builder는 직접 빌드 필요. |

## 확인 못 한 것

- Flink 2.2 TM·JM을 위 계산 최소값으로 실제 기동할 수 있는지. 실행 검증 없음.
- Flink `jvm-metaspace.size`·`jvm-overhead.min`을 기본보다 낮출 때 안전한 하한. 공식 문서에 없음.
- ONNX Runtime(DataStream 잡)의 네이티브 메모리를 Flink 메모리 모델의 어느 칸(task off-heap 등)에 잡아야 하는지. 이번 조사에서 공식 근거를 찾지 않았다.
- Kafka 단일 노드·저부하용 공식 힙 권장값. 문서에는 6g 운영 예시만 있다.
- Kafka 유휴 CPU를 줄이는 공식 설정 지침.
- kafka-native에서 `KAFKA_OPTS="-Xmx…"`가 네이티브 바이너리 런타임 힙으로 적용되는지. launch는 인자로 넘기지만 문서 명시 없음.
- GraalVM native image의 "physical memory" 80% 기본값이 컨테이너 메모리 제한을 기준으로 하는지.
- kafka-native 4.3.1이 이 스택의 Flink Kafka 커넥터·Telegraf와 문제없이 동작하는지(실행 안 함).
- ZooKeeper 최소 힙. 문서화된 값 없음.
- Grafana 메모리 절감 공식 지침. slim 이미지에서 InfluxDB 데이터소스가 추가 설치 없이 동작하는지. 오프라인에서 preinstall 동작.
- InfluxDB·Telegraf의 Go 런타임 메모리 한도(GOMEMLIMIT) 공식 안내.
- Docker Hub API `size`가 압축 크기라는 해석의 공식 문서 근거.
