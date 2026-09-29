# 08 · V2 부품 안정성 문헌 확인 (확인일 2026-09-29)

범위: 문헌 조사만 했다. docker와 컨테이너는 건드리지 않았다. 이 파일 하나만 새로 만들었다.
방법: 공식 문서, 변경 이력(CHANGELOG·릴리스 노트), GitHub 이슈·PR, 태그 고정 소스 코드만 사실로 적었다.
표기: 1차 출처로 확인하지 못한 것은 [미확인]이다. "코드 확인"은 해당 버전 태그의 소스를 직접 읽은 것이다. "코드 해석"은 코드를 읽고 추론한 동작이다. 실행해 본 것이 아니다.
V2 설정 대조: `v2/telegraf/ingest.conf`, `v2/vector/vector.yaml`, `v2/mosquitto/mosquitto.conf`, `docker-compose.v2.yml`, `flink/conf/config.v2.yaml`, `flink/sql/01_sources.sql`을 읽기만 했다.

## 1. Telegraf 1.40.1 (Modbus 수집 → Kafka·MQTT 출력)

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| 1.40.1 출시 | 1.40.1은 2026-09-21, 1.40.0은 2026-09-07 출시. | https://github.com/influxdata/telegraf/blob/master/CHANGELOG.md | 2026-09-29 |
| mqtt_consumer "send on closed channel" 패닉 | 이슈 #17564 "A panic may occur if the MQTT server loses network connectivity"(2025-09-03, 1.35.4). 상태 **Open**. 연결된 수정 PR 없음. 패닉 위치는 `onDelivered`에서 부르는 paho `Ack()`. | https://github.com/influxdata/telegraf/issues/17564 | 2026-09-29 |
| 1.40.1 코드에 같은 경로가 남았나 | 코드 확인: `onDelivered`는 연결 확인 없이 `msg.Ack()`를 부른다(`PersistentSession`일 때). 이슈 보고자가 제안한 `IsConnected()` 검사·recover는 들어 있지 않다. | https://github.com/influxdata/telegraf/blob/v1.40.1/plugins/inputs/mqtt_consumer/mqtt_consumer.go | 2026-09-29 |
| mqtt_consumer 재연결 수정 | PR #18452 "Rely on paho auto-reconnect to restore message flow after network disruption". 2026-03-05 병합, 1.38.0. #16035·#16293·#17555를 닫음. #17564와 패닉은 언급하지 않음. 1.38.0에 `max_reconnect_interval` 옵션 추가(#18466). | https://github.com/influxdata/telegraf/pull/18452 | 2026-09-29 |
| 출력 Kafka 클라이언트 | Go 라이브러리 **IBM/sarama v1.60.2**(franz-go 아님). 1.33.3은 sarama v1.43.3. | https://github.com/influxdata/telegraf/blob/v1.40.1/go.mod | 2026-09-29 |
| Kafka 4.0 호환 #16691 | "kafka output plugin breaks with kafka 4.0"(1.34.1). **Closed**. PR #16707(sarama 1.43.3→1.45.1, "support the new Kafka version 4.0") 병합, 1.34.2(2025-04-14). | https://github.com/influxdata/telegraf/issues/16691 , https://github.com/influxdata/telegraf/pull/16707 | 2026-09-29 |
| Kafka 4 소비자 #17570 | "kafka consumer plugin doesn't work with kafka 4"(1.35.4, JoinGroup v1 거부). 상태 **Closed**. 닫은 PR·버전은 페이지에서 보이지 않음. | https://github.com/influxdata/telegraf/issues/17570 | 2026-09-29 |
| Kafka 출력이 영원히 멈추는 버그 | 이슈 #19446 "outputs.kafka can block forever in SendMessages, wedging the flush loop"(2026-08-12, 1.39.2) **Open**. 원인: sarama `SyncProducer.SendMessages()`에 취소 수단이 없음. 브로커 정비·리더 선출 중 발생. | https://github.com/influxdata/telegraf/issues/19446 | 2026-09-29 |
| 1.40.1에 들어간 부분 수정 | PR #19670 "outputs.kafka Set timeout defaults" 2026-09-11 병합, 1.40.1. 기본값: net_dial/read/write 30s, producer_timeout 10s. 1.40.0에 시간 제한 옵션 자체 추가(#19447). | https://github.com/influxdata/telegraf/pull/19670 , https://github.com/influxdata/telegraf/blob/v1.40.1/plugins/outputs/kafka/kafka.go | 2026-09-29 |
| 완전 수정 PR | PR #19735 "Abandon deliveries that never complete" **Open**(2026-09-17). `delivery_timeout`(기본 5분) 추가 예정. 원문: "Retried batches may duplicate messages, also with idempotent writes as the new producer has a new identity." | https://github.com/influxdata/telegraf/pull/19735 | 2026-09-29 |
| Kafka 출력 기동 실패 처리 | 코드 확인: `Connect()` 실패를 `StartupError{Retry: true}`로 돌려준다. 그래서 `startup_error_behavior = "retry"`가 통한다. 기본값은 `error`(Telegraf 종료). | https://github.com/influxdata/telegraf/blob/v1.40.1/plugins/outputs/kafka/kafka.go , https://github.com/influxdata/telegraf/blob/v1.40.1/models/running_output.go | 2026-09-29 |
| Kafka 출력 오류 시 재전송 단위 | 코드 확인: 한 번의 `SendMessages(msgs)`로 배치 전체를 보낸다. 실패하면 첫 오류를 돌려주고 배치가 버퍼에 남는다. 코드 해석: 일부만 성공한 배치를 다시 보내면 중복이 생길 수 있다. | https://github.com/influxdata/telegraf/blob/v1.40.1/plugins/outputs/kafka/kafka.go | 2026-09-29 |
| outputs.mqtt 기동 실패 처리 | 코드 확인: `Connect()`는 일반 오류를 돌려준다(StartupError 아님). `RunningOutput.Connect`는 재시도 가능 오류가 아니면 그대로 오류를 낸다. 코드 해석: 브로커가 없을 때 Telegraf가 뜨면 `startup_error_behavior`와 상관없이 종료한다. | https://github.com/influxdata/telegraf/blob/v1.40.1/plugins/outputs/mqtt/mqtt.go , https://github.com/influxdata/telegraf/blob/v1.40.1/models/running_output.go | 2026-09-29 |
| outputs.mqtt 실행 중 브로커 정지 | 코드 확인: 발행이 시간 초과(`ErrTimeout`, 기본 timeout 5s)면 오류를 돌려주어 다시 보낸다. 다른 오류는 Warn 로그만 남기고 **버린다**("retry the metrics in this case and drop them otherwise"). 자동 재연결은 기본 켜짐(`AutoReconnect: true`). | https://github.com/influxdata/telegraf/blob/v1.40.1/plugins/outputs/mqtt/mqtt.go | 2026-09-29 |
| paho 발행 동작 | 코드 확인(paho.mqtt.golang v1.5.1): `IsConnected()`가 거짓이면 즉시 `ErrNotConnected`. AutoReconnect 중(reconnecting)이면 참으로 본다. QoS1 메시지는 저장소에 넣고(`persistOutbound`) 연결을 기다린다. 코드 해석: 재연결 중에는 시간 초과→Telegraf 재전송, 그리고 paho 저장분이 나중에 나가 중복될 수 있다. | https://github.com/eclipse-paho/paho.mqtt.golang/blob/v1.5.1/client.go | 2026-09-29 |
| 한 출력이 다른 출력을 막나 | 코드 확인: 출력마다 따로 고루틴과 타이머로 flush한다(`runOutputs`). 출력마다 버퍼도 따로다. 코드 해석: MQTT 출력이 막혀도 Kafka 출력 flush는 따로 돈다. | https://github.com/influxdata/telegraf/blob/v1.40.1/agent/agent.go | 2026-09-29 |
| MQTT keep_alive | README: 기본 0(끔). "For version v2.0.12 and later mosquitto there is a bug (see ... issues/2117), which requires this to be non-zero. As a reference eclipse/paho.mqtt.golang defaults to 30." | https://github.com/influxdata/telegraf/blob/v1.40.1/plugins/outputs/mqtt/README.md | 2026-09-29 |
| disk 버퍼 도입·상태 | 1.32.0(2024-09-09) 도입. "this feature is **experimental**". 1.40.1 문서도 "`disk`, an experimental disk-backed buffer". 1.40.1 코드는 시작 때 "this is an experimental feature" 경고를 찍는다. | https://github.com/influxdata/telegraf/blob/master/CHANGELOG.md , https://github.com/influxdata/telegraf/blob/v1.40.1/docs/CONFIGURATION.md , https://github.com/influxdata/telegraf/blob/v1.40.1/config/config.go | 2026-09-29 |
| `"disk"` 값의 실제 의미 | 코드 확인: `"disk"`는 `"disk_write_through"`로 바뀐다. 허용 값은 `memory`, `disk_write_through`뿐. | https://github.com/influxdata/telegraf/blob/v1.40.1/config/config.go , https://github.com/influxdata/telegraf/blob/v1.40.1/models/buffer.go | 2026-09-29 |
| WAL 의미 | 설계 문서 TSD-005: 모든 메트릭을 WAL 파일에도 쓴다(write-through). 출력마다 WAL 하나. 출력 성공분은 WAL에서 지운다. 재시작 때 남은 WAL을 먼저 보낸다. 원문 Is-not: "Is not a way to guarantee data safety in the event of a crash or system failure", "Is not a way to manage file system allocation size". | https://github.com/influxdata/telegraf/blob/v1.40.1/docs/specs/tsd-005-output-buffer-strategy.md | 2026-09-29 |
| WAL 라이브러리·동기화 | 코드 확인: `github.com/tidwall/wal` v1.2.1. `buffer_disk_sync` 기본 true(끄면 "losing metrics buffered in the last flush_interval in the event of a power cut"). | https://github.com/influxdata/telegraf/blob/v1.40.1/models/buffer_disk.go , https://github.com/influxdata/telegraf/blob/v1.40.1/docs/CONFIGURATION.md | 2026-09-29 |
| WAL 손상 시 | 코드 확인: 오류 문구 "wal file is corrupt, you have to manually delete the wal at %q and restart Telegraf". 버퍼 생성 실패는 출력 생성 실패가 된다. | https://github.com/influxdata/telegraf/blob/v1.40.1/models/buffer_disk.go , https://github.com/influxdata/telegraf/blob/v1.40.1/models/running_output.go | 2026-09-29 |
| disk 모드와 metric_buffer_limit | 코드 확인: disk 버퍼 생성에 용량 값을 넘기지 않는다(통계용으로만 씀). 버퍼 상태 로그도 disk 모드는 한도 없이 개수만 찍는다. 코드 해석: `metric_buffer_limit`은 disk 모드에서 상한이 아니다. | https://github.com/influxdata/telegraf/blob/v1.40.1/models/buffer.go , https://github.com/influxdata/telegraf/blob/v1.40.1/models/running_output.go | 2026-09-29 |
| WAL 폴더 이름 | 코드 확인: 출력 ID는 설정 옵션들의 sha256 해시다. WAL 경로 = `buffer_directory/<ID>`. 코드 해석: 출력 설정을 바꾸면 새 폴더가 되고 옛 WAL은 읽히지 않는다(TSD-005도 이 경우를 언급). | https://github.com/influxdata/telegraf/blob/v1.40.1/config/plugin_id.go , https://github.com/influxdata/telegraf/blob/v1.40.1/models/buffer_disk.go | 2026-09-29 |
| disk 버퍼 알려진 이슈 | 성능 저하 #16500 **Open**(1.33.1). 느린 쓰기 #18085 Closed(PR #18086 "Optimise disk buffer strategy", 1.38.0). 복구 후 flush 안 됨 #16615 Closed(PR #16697, 1.34.3). 같은 종류 출력 여러 개 패닉 #15876 Closed. 1.35.2에 disk-buffer 수정 4건, 1.39.2에 `--once` 패닉 수정(#19050). | https://github.com/influxdata/telegraf/issues/16500 , https://github.com/influxdata/telegraf/issues/18085 , https://github.com/influxdata/telegraf/issues/16615 , https://github.com/influxdata/telegraf/issues/15876 , https://github.com/influxdata/telegraf/blob/master/CHANGELOG.md | 2026-09-29 |
| 공식 이미지 실행 사용자 | 공식 1.40 이미지 entrypoint: root로 시작하면 `setpriv --reuid telegraf --regid telegraf`로 **telegraf 사용자**로 바꿔 실행한다. | https://github.com/influxdata/influxdata-docker/blob/master/telegraf/1.40/entrypoint.sh | 2026-09-29 |
| 컨테이너 쓰기 계층 | Docker 문서: "Data written to the container layer doesn't persist when the container is destroyed." | https://docs.docker.com/engine/storage/ | 2026-09-29 |
| Modbus 시간 초과 뒤 재연결 | 코드 확인: 읽기 오류가 "장치 바쁨"이 아니면 같은 수집 주기 안에서 끊고 다시 연결한다. 연결이 끊긴 상태면 다음 Gather 첫머리에서 다시 연결한다. `busy_retries`는 "장치 바쁨" 예외에만 쓴다. `close_connection_after_gather` 옵션 있음. | https://github.com/influxdata/telegraf/blob/v1.40.1/plugins/inputs/modbus/modbus.go , https://github.com/influxdata/telegraf/blob/v1.40.1/plugins/inputs/modbus/README.md | 2026-09-29 |
| Modbus 라이브러리 변경 | 1.40.1에서 `grid-x/modbus`를 2024-05 가성 버전에서 **1.5.1**로 올림(#19638). | https://github.com/influxdata/telegraf/blob/master/CHANGELOG.md | 2026-09-29 |

## 2. Kafka 생산자 멱등성 (중복 방지)

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| Telegraf 옵션 | `idempotent_writes`(기본 false). README 원문: "If enabled, exactly one copy of each message is written." | https://github.com/influxdata/telegraf/blob/v1.40.1/plugins/outputs/kafka/README.md | 2026-09-29 |
| Telegraf가 거는 값 | 코드 확인: `cfg.Producer.Idempotent = IdempotentWrites`. 켜면 `Net.MaxOpenRequests = 1`. `max_retry` 기본 3, `required_acks` 기본 -1. | https://github.com/influxdata/telegraf/blob/v1.40.1/plugins/common/kafka/config.go , https://github.com/influxdata/telegraf/blob/v1.40.1/plugins/outputs/kafka/kafka.go | 2026-09-29 |
| sarama 조건 | 멱등 생산자는 Version ≥ 0.11, Retry.Max ≥ 1, RequiredAcks = WaitForAll, MaxOpenRequests ≤ 1을 요구. sarama 기본 Version은 V2_8_0_0, 최대는 V4_3_1_0. | https://github.com/IBM/sarama/blob/v1.60.2/config.go , https://github.com/IBM/sarama/blob/v1.60.2/utils.go | 2026-09-29 |
| 멱등성의 한계 | PR #19735 원문: 새 생산자는 새 신원이라 멱등 쓰기에서도 재전송 배치가 중복될 수 있다. 코드 해석: sarama 내부 재시도 중복은 막지만, Telegraf가 실패 배치를 다음 flush에 다시 보내는 중복은 못 막는다. | https://github.com/influxdata/telegraf/pull/19735 | 2026-09-29 |
| Java 클라이언트 기본값(Kafka 4.3) | `enable.idempotence` 기본 true, `acks` 기본 all, `retries` 2147483647, `linger.ms` 기본 5. Telegraf는 Java 클라이언트가 아니므로 이 기본값을 받지 않는다(Go sarama). | https://kafka.apache.org/43/configuration/producer-configs/ | 2026-09-29 |
| librdkafka 기본값(Vector가 씀) | `enable.idempotence` 기본 false, `linger.ms` 기본 5. | https://github.com/confluentinc/librdkafka/blob/master/CONFIGURATION.md | 2026-09-29 |

## 3. Vector 0.58 (Kafka → MQTT, Kafka → InfluxDB)

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| 버전 | 0.58.0 2026-08-26 출시(최신). 0.57.0 2026-07-14. | https://vector.dev/releases/ | 2026-09-29 |
| 전달 확인(ack) 동작 | 싱크에서 켜면 "any source that supports end-to-end acknowledgements ... waits for events to be acknowledged by all connected sinks before acknowledging them at the source." | https://vector.dev/docs/reference/configuration/global-options/ | 2026-09-29 |
| Kafka 소스 오프셋 저장 | 코드 확인(v0.58.0): `enable.auto.commit=true`, `enable.auto.offset.store=false`. 이벤트 상태가 `Delivered`일 때만 `store_offset`. 저장된 오프셋은 `commit_interval_ms`(기본 5000)마다 커밋. 순서형 finalizer를 쓴다. | https://github.com/vectordotdev/vector/blob/v0.58.0/src/sources/kafka.rs | 2026-09-29 |
| Kafka 소스 기본값 | `auto_offset_reset` 기본 `largest`. 소스의 `acknowledgements` 필드는 폐기 예정, 전역·싱크에서 켜라고 안내. | https://vector.dev/docs/reference/configuration/sources/kafka/ | 2026-09-29 |
| 실패 이벤트와 오프셋 | 코드 해석: 실패(Rejected) 이벤트는 오프셋을 저장하지 않지만, 뒤의 성공 이벤트가 더 큰 오프셋을 저장하면 실패분은 다시 읽지 않는다. [미확인: 실행 검증 없음] | https://github.com/vectordotdev/vector/blob/v0.58.0/src/sources/kafka.rs | 2026-09-29 |
| MQTT 싱크 상태·QoS | 문서 상태 **beta**. QoS `atmostonce`/`atleastonce`(기본)/`exactlyonce`. `clean_session` 기본 false. keep_alive 기본 60s. 버퍼 memory(기본)/disk, `when_full` 기본 block. | https://vector.dev/docs/reference/configuration/sinks/mqtt/ | 2026-09-29 |
| MQTT 싱크 ack 시점 | 코드 확인: `client.publish(...)`가 rumqttc 요청 채널(용량 1024)에 들어가면 곧바로 `EventStatus::Delivered`를 돌려준다. PUBACK을 기다리지 않는다. 소스 주석: 연결 오류를 이벤트에 묶을 수 없어 "we can't accurately provide delivery guarantees"(rumqtt 이슈 #349 대기). | https://github.com/vectordotdev/vector/blob/v0.58.0/src/sinks/mqtt/service.rs , https://github.com/vectordotdev/vector/blob/v0.58.0/src/sinks/mqtt/sink.rs , https://github.com/vectordotdev/vector/blob/v0.58.0/src/common/mqtt.rs | 2026-09-29 |
| MQTT 싱크 재연결 | 코드 확인: 이벤트 루프가 `connection.poll()`을 무한 반복하고 오류는 `MqttConnectionError`로 내보내기만 한다. 재연결은 rumqttc 0.24.0의 poll에 맡긴다. 오류 뒤 대기 코드는 없다. 브로커 재시작 때 미완료 QoS1 재전송 여부는 [미확인]. | https://github.com/vectordotdev/vector/blob/v0.58.0/src/sinks/mqtt/sink.rs , https://github.com/vectordotdev/vector/blob/v0.58.0/Cargo.toml | 2026-09-29 |
| MQTT client_id | 코드 확인: 지정 안 하면 `vectorSink` + 무작위 6자. 빈 문자열은 설정 오류. | https://github.com/vectordotdev/vector/blob/v0.58.0/src/sinks/mqtt/config.rs | 2026-09-29 |
| influxdb_logs 재시도 대상 | 문서: "Vector will retry failed requests (status in [408, 429], >= 500, and != 501). Other responses will not be retried." 재시도 횟수 기본 사실상 무한, 첫 대기 1s 뒤 피보나치, 최대 30s, 요청 시간 제한 60s. | https://vector.dev/docs/reference/configuration/sinks/influxdb_logs/ | 2026-09-29 |
| 연결 거부 vs 4xx | 코드 확인: influxdb_logs는 `HttpRetryLogic::default()`를 쓴다. 요청 전송 오류(`HttpError::CallRequest`, 연결 거부 포함)는 재시도 대상. 401 같은 4xx는 재시도하지 않는다. | https://github.com/vectordotdev/vector/blob/v0.58.0/src/sinks/util/http.rs , https://github.com/vectordotdev/vector/blob/v0.58.0/src/http.rs , https://github.com/vectordotdev/vector/blob/v0.58.0/src/sinks/influxdb/logs.rs | 2026-09-29 |
| 버퍼 | memory는 내구성 없음. disk는 재시작 뒤 이어서 처리. disk 최소 약 256MiB. `block`은 무한 대기, `drop_newest`는 버림. 디스크 I/O 오류 때 "Vector will forcefully stop itself". `data_dir` 기본 `/var/lib/vector/`, 쓰기 권한 필요. | https://vector.dev/docs/architecture/buffering-model/ , https://vector.dev/docs/reference/configuration/global-options/ | 2026-09-29 |
| 0.58.0 버퍼 수정 | disk 버퍼를 쓰는 메트릭 싱크가 10~15분 뒤 멈추던 교착 수정. 충돌 뒤 `disk_v2` 버퍼가 가득 찬 것처럼 보이던 문제 수정. 너무 큰 레코드로 쓰기 불능이 되던 문제 수정. | https://vector.dev/releases/0.58.0/ | 2026-09-29 |
| 환경변수 치환 기본 꺼짐 | **0.57.0**부터 설정 파일 환경변수 치환이 기본 꺼짐. 되돌리기: `--dangerously-allow-env-var-interpolation` 또는 `VECTOR_DANGEROUSLY_ALLOW_ENV_VAR_INTERPOLATION=true`. `--disable-env-var-interpolation` 삭제. 권장 대안: secrets backend(file, exec, AWS Secrets Manager 등). 대안 2: `envsubst` 전처리. | https://vector.dev/highlights/2026-07-14-0-57-0-upgrade-guide/ | 2026-09-29 |
| 0.58 치환 이슈 | #26411 "0.58.0: Vector config doesn't interpolate environment variables supplied by docker-compose.yml" 2026-09-17, **Closed**. 유지보수자 답변 내용은 페이지에서 확인 못 함. | https://github.com/vectordotdev/vector/issues/26411 | 2026-09-29 |
| secrets 수정 | 0.58.0: `SECRET[<backend name>.<secret name>]`의 backend 이름에 하이픈 허용. | https://vector.dev/releases/0.58.0/ | 2026-09-29 |

## 4. Flink 2.2.1 + flink-connector-kafka 5.0.0

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| 버전 짝 | Kafka 커넥터 5.0.0(2026-06-02)은 Flink 2.1.x·2.2.x 지원. Flink 2.2.1은 2026-05-15. 2.2 문서는 `5.0.0-2.2`를 가리킴. | https://flink.apache.org/downloads/ , https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/connectors/table/kafka/ | 2026-09-29 |
| "Name collision" 경고의 원인 이슈 | FLINK-37559(Affects 1.20.1, **Open**): `CommitterOperator#snapshotState`→`CommittableCollector#copy`→`setCurrentPendingCommittablesGauge` 재등록. 문구 "Group already contains a Metric with the name 'pendingCommittables'. Metric will not be reported." FLINK-35321의 중복. | https://issues.apache.org/jira/browse/FLINK-37559 | 2026-09-29 |
| 본 이슈 상태 | FLINK-35321 **Open / Unresolved**, Fix Version 없음(확인 시점). | https://issues.apache.org/jira/browse/FLINK-35321 | 2026-09-29 |
| 수정 PR | apache/flink PR #27598 "Ensure pendingCommitables metric is not re-registered while copying CommittableCollector" **master에만 병합**(2026-09-10, 커밋 0a6d741). | https://github.com/apache/flink/pull/27598 | 2026-09-29 |
| 2.2.1에 수정이 있나 | 코드 확인: `release-2.2.1` 태그의 `CommittableCollector` 복사용 생성자가 여전히 `setCurrentPendingCommittablesGauge`를 부른다. `release-2.2`, `release-2.3` 브랜치도 같다. master만 `of()`로 옮겼다. 결론: **2.2.1에서 이 경고는 고쳐지지 않았다.** | https://github.com/apache/flink/blob/release-2.2.1/flink-runtime/src/main/java/org/apache/flink/streaming/runtime/operators/sink/committables/CommittableCollector.java | 2026-09-29 |
| SQL 싱크 전달 보장 | `sink.delivery-guarantee`: `none` / `at-least-once`(기본) / `exactly-once`. exactly-once면 `sink.transactional-id-prefix` 필수. 5.0.0에 `sink.transaction-naming-strategy` 옵션 있음. | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/connectors/table/kafka/ , https://github.com/apache/flink-connector-kafka/blob/v5.0.0/flink-connector-kafka/src/main/java/org/apache/flink/streaming/connectors/kafka/table/KafkaConnectorOptions.java | 2026-09-29 |
| exactly-once 요건 | 체크포인트 때 트랜잭션 커밋. `transaction.timeout.ms` ≥ 최대 체크포인트 시간 + 최대 재시작 시간, 아니면 데이터 유실 가능. 접두사는 같은 클러스터의 앱끼리 달라야 함. read_committed 소비자는 체크포인트 완료 뒤에만 데이터를 본다. | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/connectors/datastream/kafka/ | 2026-09-29 |
| 트랜잭션 시간 제한 충돌 | 코드 확인: 커넥터 기본 `transaction.timeout.ms` = 1시간(`DEFAULT_KAFKA_TRANSACTION_TIMEOUT = Duration.ofHours(1)`). Kafka 브로커 `transaction.max.timeout.ms` 기본 900000(15분), 넘으면 "the broker will return an error in InitProducerIdRequest". | https://github.com/apache/flink-connector-kafka/blob/v5.0.0/flink-connector-kafka/src/main/java/org/apache/flink/connector/kafka/sink/KafkaSinkBuilder.java , https://kafka.apache.org/43/configuration/broker-configs/ | 2026-09-29 |
| 하류 소비자 격리 수준 기본값 | librdkafka(Vector) `isolation.level` 기본 **read_committed**. sarama(Telegraf) 기본 ReadUncommitted. kafka-python 기본 `read_uncommitted`. Telegraf kafka_consumer README에는 격리 수준 옵션이 없다. | https://github.com/confluentinc/librdkafka/blob/master/CONFIGURATION.md , https://github.com/IBM/sarama/blob/v1.60.2/config.go , https://github.com/dpkp/kafka-python/blob/master/kafka/consumer/group.py , https://github.com/influxdata/telegraf/blob/v1.40.1/plugins/inputs/kafka_consumer/README.md | 2026-09-29 |
| SQL 소스 시작 위치 | `scan.startup.mode`: `group-offsets`(기본) / `earliest-offset` / `latest-offset` / `timestamp` / `specific-offsets`. | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/connectors/table/kafka/ | 2026-09-29 |
| 복구 때 오프셋 | "Kafka source does NOT rely on committed offsets for fault tolerance." 커밋은 모니터링용. 복구는 체크포인트 상태에서. 코드 해석: HA로 체크포인트에서 복구하면 시작 모드와 무관하게 틈 없이 이어간다. 체크포인트 없이 새로 제출하면 시작 모드가 적용된다. | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/connectors/datastream/kafka/ | 2026-09-29 |
| 지표 끄기 | 생산자 속성 `register.producer.metrics=false`로 Kafka 지표 전달을 끌 수 있다. 소비자는 `register.consumer.metrics`(기본 true). | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/connectors/datastream/kafka/ | 2026-09-29 |

## 5. Kafka 4.3.1 단일 노드

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| 버전 | 4.3.1 2026-06-25(버그 수정판, Streams RocksDB 메모리 누수 수정이 대표). 4.3.0 2026-05-22. | https://kafka.apache.org/blog/2026/06/25/apache-kafka-4.3.1-release-announcement/ | 2026-09-29 |
| 3.9 유휴 CPU 원인 이슈 | S11과 같은 증상(단일 노드 유휴 CPU 178~205%)을 직접 다룬 이슈는 찾지 못함 [미확인]. 가까운 것: KAFKA-17751 "Controller high CPU when formatted with --initial-controllers"(Affects 3.9.0, **3.9.0·4.0.0에서 수정**, 3노드 비리더 투표자만). KAFKA-18046 "High CPU usage when using Log4j2"(3.9.1·4.0.0 릴리스 노트). KAFKA-19605 "Fix the busy loop occurring in the broker observer"(Fix 4.2.0). KAFKA-19606 "Anomaly of JMX metrics RequestHandlerAvgIdlePercent in kraft combined mode"(4.2.0). | https://issues.apache.org/jira/browse/KAFKA-17751 , https://issues.apache.org/jira/browse/KAFKA-19605 , https://archive.apache.org/dist/kafka/3.9.1/RELEASE_NOTES.html , https://archive.apache.org/dist/kafka/4.2.0/RELEASE_NOTES.html | 2026-09-29 |
| 4.3.1 CPU 관련 | KAFKA-20535 "Investigate potential improvements to async consumer CPU usage under low max.poll.records"(클라이언트 쪽). | https://archive.apache.org/dist/kafka/4.3.1/RELEASE_NOTES.html | 2026-09-29 |
| 결합 모드 | "Combined mode is not recommended in critical deployment environments." 작은 개발 환경용. | https://kafka.apache.org/43/operations/kraft/ | 2026-09-29 |
| 단일 컨트롤러 포맷 | 동적 쿼럼 권장. 단일 초기 컨트롤러는 `--standalone`로 포맷. 동적 쿼럼이면 `controller.quorum.voters`를 쓰지 말고 `controller.quorum.bootstrap.servers`를 쓴다. 자동 포맷은 메타데이터 로그 오류를 가릴 수 있다고 경고. | https://kafka.apache.org/43/operations/kraft/ | 2026-09-29 |
| 단일 노드에 필요한 브로커 값 | 기본값: `offsets.topic.replication.factor` 3, `transaction.state.log.replication.factor` 3, `transaction.state.log.min.isr` 2, `min.insync.replicas` 1, `transaction.max.timeout.ms` 900000. | https://kafka.apache.org/43/configuration/broker-configs/ | 2026-09-29 |
| 4.0 기본값 변경 | "The default `linger.ms` changed from 0 to 5 in Apache Kafka 4.0". `enable.idempotence`는 `max.in.flight.requests.per.connection` > 5일 때 더 이상 자동으로 꺼지지 않음. 옛 프로토콜 API 제거(브로커 2.1 이상 필요). `log.message.format.version`/`message.format.version` 제거. | https://kafka.apache.org/43/getting-started/upgrade/ | 2026-09-29 |
| 4.2 지표 | `ControllerEventManager`·`MetadataLoader`에 `AvgIdleRatio` 지표 추가(유휴 비율 관찰용). | https://kafka.apache.org/43/getting-started/upgrade/ | 2026-09-29 |

## 6. Mosquitto 2.1.2

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| 2.1.2 변경 | 2026-02-09. "Forbid running with `persistence true` and with a persistence plugin at the same time." docker 빌드에 libedit 추가. | https://github.com/eclipse-mosquitto/mosquitto/blob/master/ChangeLog.txt | 2026-09-29 |
| 2.1.x 이후 수정 대기 | 2.1.3(날짜 "2026-02-xx", 미출시 표기)에 최대 패킷 크기 제한 오류(송신 #3503, 수신 #3515), will 지연 오류(#3505) 등 수정 예정. 2.1.3 출시 여부는 [미확인]. | https://github.com/eclipse-mosquitto/mosquitto/blob/master/ChangeLog.txt | 2026-09-29 |
| 2.1.0 동작 변경 | `max_packet_size` 기본 2,000,000바이트. `allow_duplicate_messages` 기본 true. `persistent_client_expiration`에 초 단위 허용. 시작 때 persistence 통계 출력. persist-sqlite 플러그인 추가. | https://github.com/eclipse-mosquitto/mosquitto/blob/master/ChangeLog.txt | 2026-09-29 |
| persistence | 기본 false. 켜면 연결·구독·메시지를 `mosquitto.db`에 쓰고 재시작 때 다시 읽는다. 종료 때와 `autosave_interval`마다 저장. 원문: "It is recommended that a plugin based persistence is used instead." | https://github.com/eclipse-mosquitto/mosquitto/blob/v2.1.2/man/mosquitto.conf.5.xml | 2026-09-29 |
| autosave_interval | 기본 1800초. 0이면 종료·SIGUSR1 때만 저장. `autosave_on_changes true`면 초가 아니라 변경 횟수로 본다. | https://github.com/eclipse-mosquitto/mosquitto/blob/v2.1.2/man/mosquitto.conf.5.xml | 2026-09-29 |
| 대기열 한도 | `max_queued_messages` 기본 1000(클라이언트마다, 전송 중 제외). `max_queued_bytes` 기본 0(무제한). 한도 도달 뒤 메시지는 "silently dropped". `max_inflight_messages` 기본 20. QoS0은 `queue_qos0_messages true`일 때만 대기열에. | https://github.com/eclipse-mosquitto/mosquitto/blob/v2.1.2/man/mosquitto.conf.5.xml | 2026-09-29 |
| 영속 세션 청소 | `persistent_client_expiration`: clean session false 클라이언트가 다시 안 오면 세션 제거. 원문: 무작위 client id + clean session false 클라이언트가 영구 세션을 남긴다고 경고. | https://github.com/eclipse-mosquitto/mosquitto/blob/v2.1.2/man/mosquitto.conf.5.xml | 2026-09-29 |
| max_keepalive | 기본 0. 0이면 keepalive 0 클라이언트를 허용. MQTT 3.1.1 클라이언트가 한도보다 큰 keepalive를 쓰면 CONNACK "identifier rejected". | https://github.com/eclipse-mosquitto/mosquitto/blob/v2.1.2/man/mosquitto.conf.5.xml | 2026-09-29 |
| persist-sqlite | "saves changes to disk as they are made, where as the traditional persistence only takes periodic snapshots." `plugin_opt_flush_period` 기본 5초, `plugin_opt_sync` 기본 normal. 문서 설정 예시 오류 신고 #3508. | https://mosquitto.org/documentation/persistence/sqlite/ , https://github.com/eclipse-mosquitto/mosquitto/issues/3508 | 2026-09-29 |
| 영속 세션 미전달 신고 | #3202 "Persistent session do not receive missed messages"(2.0.15·2.0.20) **Open**, 유지보수자 답 없음. 2.1.x 재현 여부 [미확인]. | https://github.com/eclipse-mosquitto/mosquitto/issues/3202 | 2026-09-29 |

## 7. InfluxDB 2.9

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| 현재 이미지 | 공식 `influxdb:2.9` Dockerfile은 `INFLUXDB_VERSION=2.9.1`, uid/gid 1000 `influxdb` 사용자. 2.9.1은 레벨 3 압축이 멈추던 문제 수정. | https://github.com/influxdata/influxdata-docker/blob/master/influxdb/2.9/Dockerfile , https://docs.influxdata.com/influxdb/v2/reference/release-notes/influxdb/ | 2026-09-29 |
| 2.9.0 토큰 해시 기본화 | 토큰을 해시로 저장. 원본 토큰 문자열은 복구 불가. 2.8.0 이전으로 내리면 API 토큰이 모두 지워짐. 끄려면 `--use-hashed-tokens=false`. | https://docs.influxdata.com/influxdb/v2/reference/release-notes/influxdb/ | 2026-09-29 |
| 토큰 조회 | 해시 뒤에는 토큰 값을 다시 볼 수 없다. 운영자 토큰을 잃으면 `influxd recovery auth`로 새로 만든다. 2.9.0 첫 기동 전에 필요한 토큰을 평문으로 확보하라고 안내. | https://docs.influxdata.com/influxdb/v2/admin/tokens/ | 2026-09-29 |
| docker 초기화 | 2.9 entrypoint는 `DOCKER_INFLUXDB_INIT_ADMIN_TOKEN`(또는 `_FILE`)을 `influx setup --token`으로 넘긴다. 코드 해석: 운영자가 준 값이므로 해시 뒤에도 그 값으로 쓸 수 있다. 다만 나중에 만든 토큰은 만들 때만 보인다. | https://github.com/influxdata/influxdata-docker/blob/master/influxdb/2.9/entrypoint.sh | 2026-09-29 |
| 쓰기 클라이언트 재연결 | 서버 쪽 재연결 관련 공식 설명은 찾지 못함 [미확인]. 재시도는 클라이언트 몫(Vector는 3절 규칙). | — | 2026-09-29 |

## 8. ZooKeeper 3.9.x (Flink HA)

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| 현재 버전 | current 3.9.6(2026-09-15), stable 3.8.7. 3.9.5는 2026-03-06. 3.7은 2024-02-02 EOL. | https://zookeeper.apache.org/releases.html , https://zookeeper.apache.org/news/ | 2026-09-29 |
| 3.9.6 수정 | Netty CVE(ZOOKEEPER-5056, Netty 4.1.136), Prometheus 지표 공급자가 KeyStore/TrustStore 암호를 INFO로 기록하던 문제(ZOOKEEPER-5049), TLS 사용자 설정 깨짐(ZOOKEEPER-4828) 등. | https://zookeeper.apache.org/doc/r3.9.6/releasenotes.html | 2026-09-29 |
| Docker 공식 이미지 태그 | Docker Hub 페이지에 3.9.5가 최신(`latest`)으로 표시. 3.9.6 태그는 페이지에서 확인 못 함. | https://hub.docker.com/_/zookeeper | 2026-09-29 |
| Flink 2.2.1 클라이언트 | 코드 확인: Flink pom `zookeeper.version` 3.7.2, `curator.version` 5.4.0, flink-shaded 20.0. | https://github.com/apache/flink/blob/release-2.2.1/pom.xml | 2026-09-29 |
| 클라이언트·서버 호환 | 3.9.0 공지: "ZooKeeper clients from 3.5.x onwards are fully compatible with 3.9.x servers." | https://zookeeper.apache.org/news/ | 2026-09-29 |
| Flink HA 필수 설정 | `high-availability.type: zookeeper`, `high-availability.storageDir`, `high-availability.zookeeper.quorum`, `high-availability.cluster-id`(YARN·k8s에서는 직접 넣지 말 것), 권장 `path.root: /flink`. ZooKeeper 연결은 제한된 지수 백오프로 재시도. 운영에서는 Flink 번들 스크립트 말고 직접 관리 ZooKeeper 권장. | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/deployment/ha/zookeeper_ha/ | 2026-09-29 |
| 이미지 기본 청소 | `ZOO_AUTOPURGE_PURGEINTERVAL` 기본 0(자동 청소 꺼짐), `ZOO_AUTOPURGE_SNAPRETAINCOUNT` 기본 3. 데이터 `/data`, 트랜잭션 로그 `/datalog`. | https://hub.docker.com/_/zookeeper | 2026-09-29 |
| Flink 2.2 + ZooKeeper 3.9 알려진 문제 | 찾지 못함 [미확인]. | — | 2026-09-29 |

## V2 설정에 주는 시사점(사실 근거만)

V2 파일에서 읽은 현재 값과 위 사실을 짝지었다. 바꾸라는 뜻은 사실에서 바로 따라오는 것만 적었다.

1. **Telegraf 기동 순서(S7 관련).** `outputs.mqtt`는 기동 실패를 재시도 가능 오류로 내지 않는다(1절). 그래서 Mosquitto가 없을 때 Telegraf가 뜨면 종료한다. `docker-compose.v2.yml`의 `ingest`는 `depends_on`에 `mqtt`가 없다. → `mqtt: { condition: service_healthy }`를 넣어야 한다. 이 경우 `startup_error_behavior`로는 막을 수 없다.
2. **Kafka 출력 기동 재시도.** `outputs.kafka`는 `startup_error_behavior = "retry"`가 통한다(1절). `ingest.conf`에는 이 값이 없다(기본 `error` = 종료). Docker 데몬 재시작 때 compose 순서가 지켜지는지는 [미확인]이므로, 넣으면 기동 순서 의존이 줄어든다.
3. **Kafka 출력이 멈추는 미해결 버그(#19446).** 1.40.1은 시간 제한 기본값만 들어갔다(#19670). 완전 수정 PR #19735는 아직 Open이다. 브로커 재시작 뒤 flush가 멈추는지 R-시험으로 봐야 한다. 멈춤 감시는 Telegraf 내부 지표나 Kafka 쪽 유입률로 해야 한다.
4. **S4 중복.** `ingest.conf`는 `max_retry = 10`이고 `idempotent_writes`가 없다. `idempotent_writes = true`는 sarama 내부 재시도 중복만 막는다. Telegraf의 배치 재전송 중복은 남는다(PR #19735 원문). 하류(Flink)에서 중복을 견디는 설계가 여전히 필요하다.
5. **disk 버퍼 한계.** 1.40.1에서도 실험 기능이다. disk 모드에서 `metric_buffer_limit = 100000`은 상한이 아니다(코드). 디스크가 가득 차는 것은 사용자 책임이다(TSD-005). `/tmp/telegraf-buffer`는 컨테이너 쓰기 계층이라 컨테이너를 지우면(재생성) 사라진다(Docker 문서). 재시작에는 남는다. 출력 설정을 바꾸면 WAL 폴더가 바뀌어 옛 WAL을 읽지 않는다. WAL이 손상되면 수동 삭제 전까지 기동 실패가 반복된다.
6. **MQTT keep_alive.** `ingest.conf`의 `outputs.mqtt`에 `keep_alive`가 없다(기본 0). Telegraf README는 Mosquitto 2.0.12 이후 0이 아닌 값을 요구한다고 적었다. 반면 Mosquitto 2.1.2 문서는 `max_keepalive` 기본 0이면 keepalive 0을 허용한다고 적었다. 두 문서가 다르다. `keep_alive = 30`(paho 기본값)을 넣는 것이 README 권고다.
7. **MQTT 출력 유실·중복.** 시간 초과가 아닌 발행 오류는 버린다(코드). 재연결 중에는 재전송과 paho 저장분이 겹쳐 중복이 날 수 있다(코드 해석). 계측 MQTT 흐름은 "최소 1회"로 보장된다고 쓰면 안 된다.
8. **Vector MQTT 싱크 보장 수준.** ack는 PUBACK이 아니라 rumqttc 채널 투입 시점이다(코드). 그래서 `acknowledgements: true`여도 Kafka 오프셋이 MQTT 전달 전에 넘어갈 수 있다. `vector.yaml` 주석의 "싱크(MQTT)가 받은 뒤에만 넘긴다"는 MQTT 쪽에는 사실과 다르다. 싱크는 beta다.
9. **Vector MQTT 세션.** `mqtt_hmi`는 고정 `client_id`를 쓰고 `clean_session` 기본 false다. 브로커에 영속 세션이 남는다. Mosquitto의 `persistent_client_expiration`은 V2 설정에 없다.
10. **Vector InfluxDB 오류 분류.** 연결 거부·5xx·408·429는 재시도한다. 401 같은 4xx는 재시도하지 않는다(S16과 같은 조용한 유실 경로). 뒤 이벤트가 성공하면 실패분 오프셋도 지나간다(코드 해석, 미검증). 4xx 발생은 Vector 내부 지표로 경보해야 한다.
11. **Vector 환경변수.** V2는 `VECTOR_DANGEROUSLY_ALLOW_ENV_VAR_INTERPOLATION=true`로 되돌렸다(compose 252행). 공식 권장 대안은 secrets backend(`SECRET[...]`, file/exec)다. 원문은 이 플래그를 모든 환경변수를 통제할 때만 쓰라고 한다.
12. **Flink "Name collision" 경고(S14).** 2.2.1에도 원인 코드가 남아 있다(수정은 master만). S14 경고의 지표 이름이 `pendingCommittables`라면 V2에서도 계속 나온다. 이 경고는 해당 지표가 보고되지 않는다는 뜻이다.
13. **Flink 중복 CEP 경보.** V2 SQL 싱크에 `sink.delivery-guarantee`가 없다(기본 at-least-once). JobManager 복구 뒤 마지막 체크포인트 이후분 중복은 문서상 정상 동작이다. exactly-once로 바꾸려면 `sink.transactional-id-prefix`와 `properties.transaction.timeout.ms`(≤ 브로커 15분, ≥ 체크포인트+재시작 시간)가 함께 필요하다. 기본 1시간 그대로면 브로커가 거절한다.
14. **exactly-once의 하류 영향.** 바꾸면 Vector(librdkafka 기본 read_committed)는 체크포인트(10s) 뒤에야 경보를 본다. 경보 지연이 최대 체크포인트 간격만큼 늘어난다. Telegraf kafka_consumer(sarama 기본 read_uncommitted, 옵션 없음)는 중단된 트랜잭션 데이터도 읽는다. Python 소비자는 쓰는 라이브러리 기본값을 확인해야 한다.
15. **Flink 시작 위치.** `01_sources.sql`은 `scan.startup.mode = 'latest-offset'`이다. HA로 체크포인트에서 복구하면 틈이 없다. 체크포인트 없이 잡을 새로 제출하면 정지 구간이 빠진다.
16. **Kafka 단일 노드 값.** compose는 오프셋·트랜잭션 로그 복제 계수 1, min ISR 1을 이미 넣었다(109~111행). exactly-once를 켜면 `transaction.max.timeout.ms`와의 관계(13번)를 맞춰야 한다. 결합 모드는 공식 문서상 중요 환경 비권장이다.
17. **ZooKeeper.** compose는 `zookeeper:3.9.5`다. 3.9.6이 Netty CVE를 고쳤다. 공식 이미지 페이지에 3.9.6 태그가 보이지 않아 교체 가능 여부는 [미확인]. 자동 청소 기본 꺼짐이므로 오래 돌리면 스냅숏이 쌓인다.

## 확인 못 한 것

- S11(Kafka 3.9 유휴 CPU 178~205%)의 직접 원인 이슈. 4.3.1에서 해소되는지 문헌으로 확정 못 함.
- S14 로그의 정확한 지표 이름. `pendingCommittables`가 아니면 12번 결론은 적용되지 않는다. flink-connector-kafka 5.0.0 자체의 지표 충돌 이슈는 찾지 못함.
- Telegraf #17570을 닫은 PR과 버전.
- mqtt_consumer 패닉이 paho 1.5.1 쪽에서 막혔는지. Telegraf 쪽 코드는 그대로다(V2는 mqtt_consumer를 쓰지 않음).
- grid-x/modbus 1.5.1 올림(1.40.1)으로 생긴 회귀 여부.
- Vector MQTT 싱크(rumqttc 0.24.0)가 브로커 재시작 때 미완료 QoS1 메시지를 다시 보내는지. 브로커 정지 중 CPU 부하.
- Vector #26411 유지보수자 답변과 닫힌 사유.
- Docker 데몬 재시작 때 compose `depends_on` 조건이 지켜지는지(공식 문서에서 문구를 찾지 못함).
- Mosquitto 2.1.3 출시 여부. #3202가 2.1.x에서 재현되는지.
- InfluxDB 2.9 쓰기 클라이언트 재연결에 대한 서버 쪽 공식 설명. 2.9.0·2.9.1 출시 날짜(릴리스 노트에 날짜 없음).
- Docker Hub에 zookeeper 3.9.6 태그가 있는지. Flink 2.2 + ZooKeeper 3.9 조합의 알려진 문제.
- 위의 "코드 해석" 항목들은 실행으로 검증하지 않았다.
