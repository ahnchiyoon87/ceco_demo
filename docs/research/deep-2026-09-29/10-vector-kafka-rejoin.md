# Vector kafka 소스 재참여 실패 조사 (문헌만)

- 확인일: 2026-09-29
- 범위: 문헌 조사만. 컨테이너·docker 실행 없음.
- 관측 사실(우리 시스템): Vector 0.58.0, kafka 소스 2개(vector-influx, vector-alert-republish), influxdb_logs 싱크 종단 확인(acknowledgements) 켬, session_timeout_ms 기본값. Kafka 4.3.1 단일 노드 KRaft 재시작(약 7초 중단) 후 SESSTMOUT(10009 ms) → AssignmentLost 커밋 오류 → 재참여 없음(간헐, 이전 3회는 5~17초 뒤 복구).


## 1. Vector 쪽 알려진 이슈

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| 이슈 #22006 | 제목 "On kafka consumer rebalance, Vector consumer stops consuming." 2024-12-10 열림. 2026-09-29 현재 open. 라벨 `source: kafka`. 보고 버전 0.40.0. | https://github.com/vectordotdev/vector/issues/22006 | 2026-09-29 |
| #22006 증상 | 연결 문제로 컨슈머 그룹이 바뀌면 무작위로 소비를 멈춘다. 컨슈머 랙이 쌓인다. 재시작만 해결한다. | https://github.com/vectordotdev/vector/issues/22006 | 2026-09-29 |
| #22006 댓글 | 0.44.0에 rdkafka 0.37 반영 후 "고쳐지지 않았다"는 보고(2025-02-21). 0.47.0(2025-10-29), 0.49.0(2026-03-10), 0.54·0.55(2026-04-27)에서도 재현 보고. 0.54·0.55 보고는 "짧은 리밸런스 때 일부 파티션이 멈추고 stdout 오류 없음". | https://github.com/vectordotdev/vector/issues/22006 | 2026-09-29 |
| #22006 유지보수자 답변 | 이슈 댓글에 Vector 유지보수자(MEMBER) 설명은 없다. 댓글 작성자 연관은 NONE 또는 CONTRIBUTOR뿐이다. | https://api.github.com/repos/vectordotdev/vector/issues/22006/comments | 2026-09-29 |
| 수정 PR #26438 | 제목 "fix(kafka source): wait for aborted partition consumers before continuing a rebalance". 2026-09-20 열림. 2026-09-29 현재 open, 미병합, 마일스톤 없음. 리뷰 0건. "Closes #22006". | https://github.com/vectordotdev/vector/pull/26438 | 2026-09-29 |
| #26438 원인 설명(작성자, 외부 기여자) | 파티션마다 `StreamPartitionQueue`가 같은 librdkafka fetch 큐를 감싼다. 깨우기 콜백은 마지막에 설정한 쪽이 이긴다. Drop 시 콜백을 무조건 지운다. 리보크 중 `drain_timeout_ms` 안에 대기 중 ack를 못 비우면(예: 싱크 역압) 파티션 태스크를 abort하고 리밸런스 콜백을 즉시 풀어 준다. 같은 파티션이 같은 컨슈머에 다시 배정되면 옛 태스크의 늦은 Drop이 새 큐의 깨우기 콜백을 지운다. 새 태스크는 다시 깨지 않는다. 로그가 없고 랙과 메모리만 는다. | https://github.com/vectordotdev/vector/pull/26438 | 2026-09-29 |
| #26438 재현 결과(작성자) | 옛 동작 + `range,roundrobin`: 3/3 정지. 옛 동작 + `cooperative-sticky`: 3/3 통과(리보크된 파티션이 다른 멤버로 가서). 수정본: 둘 다 3/3 통과. rdkafka 0.39.0 기준. | https://github.com/vectordotdev/vector/pull/26438 | 2026-09-29 |
| #26438 범위 한계 | 파티션 수 변경, 매우 큰 컨슈머 그룹 사례는 다루지 않는다고 적었다. | https://github.com/vectordotdev/vector/pull/26438 | 2026-09-29 |
| 수정 버전 | 없음. 최신 릴리스는 v0.58.0(2026-08-26). #26438은 미병합이다. | https://api.github.com/repos/vectordotdev/vector/releases | 2026-09-29 |
| 관련 이슈 #21134 | "Kafka lag metrics gives incorrect value". 2024-08-22 열림, open. 보고 버전 0.39.0. | https://github.com/vectordotdev/vector/issues/21134 | 2026-09-29 |
| 관련 PR #24647 | "Prevent stale lag after consumer rebalance". 2026-02-12 열림, open. 리밸런스 뒤 소유하지 않은 파티션의 `kafka_consumer_lag`가 옛 값으로 남는 문제를 고친다(비소유 파티션은 -1). | https://github.com/vectordotdev/vector/pull/24647 | 2026-09-29 |
| 관련 이슈 #20633 | 통합시험 `drains_acknowledgements_during_rebalance_sticky_assignments`가 불안정. 2024-06-10 열림, open. | https://github.com/vectordotdev/vector/issues/20633 | 2026-09-29 |
| 과거 수정 #17497 | 리밸런스·종료 때 ack 전량 드레인 구현. 2023-10-12 닫힘. | https://github.com/vectordotdev/vector/pull/17497 | 2026-09-29 |

## 2. Vector 0.58.0 코드 사실 (태그 v0.58.0)

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| 번들 라이브러리 | rdkafka 0.39.0, rdkafka-sys 4.10.0+2.12.1(librdkafka 2.12.1). | https://github.com/vectordotdev/vector/blob/v0.58.0/Cargo.lock | 2026-09-29 |
| 고정 설정 | `enable.auto.commit=true`, `auto.commit.interval.ms=commit_interval_ms`, `enable.auto.offset.store=false`, `statistics.interval.ms=1000`, `enable.partition.eof=false`, `client.id=vector`. `librdkafka_options`는 이 뒤에 적용되어 덮어쓸 수 있다. | https://github.com/vectordotdev/vector/blob/v0.58.0/src/sources/kafka.rs | 2026-09-29 |
| 리밸런스 콜백 | `pre_rebalance`에서 Assign이면 파티션별 큐 준비가 끝날 때까지 막는다. Revoke면 ack 드레인이 끝날 때까지 막고 동기 커밋(`commit_consumer_state(CommitMode::Sync)`)을 한다. | https://github.com/vectordotdev/vector/blob/v0.58.0/src/sources/kafka.rs | 2026-09-29 |
| 커밋 오류 로그 | 커밋 실패는 `KafkaOffsetUpdateError`로 "Unable to update consumer offset."(error_code `kafka_offset_update`)를 남긴다. "Consumer commit error"(`KafkaError::ConsumerCommit`)는 코드상 `commit_consumer_state` 호출에서만 나온다. 호출 위치는 리보크 콜백(드레인 중·직후), 종료 처리, 소스 종료 직후다(파티션 태스크의 `store_offset` 실패는 다른 오류 종류). 종료가 아니었다면 우리 로그는 리보크 콜백의 커밋 단계에서 나왔다고 읽힌다(코드 기반 해석). | https://github.com/vectordotdev/vector/blob/v0.58.0/src/internal_events/kafka.rs | 2026-09-29 |
| 드레인 시한 | 드레인 시한이 지나면 "Acknowledgement drain deadline reached..."를 debug 수준으로 남기고 남은 파티션 태스크를 abort한다. 기본 로그 수준에서는 안 보인다. | https://github.com/vectordotdev/vector/blob/v0.58.0/src/sources/kafka.rs | 2026-09-29 |
| 드레인 중 배정 | 드레인 상태에서 배정 콜백이 오면 error 로그 "Partition assignment received while draining revoked partitions, maybe an invalid assignment."만 남기고 그 배정의 큐를 만들지 않는다. | https://github.com/vectordotdev/vector/blob/v0.58.0/src/sources/kafka.rs | 2026-09-29 |
| 메인 폴링 | 전용 스레드가 `consumer.stream()`을 계속 폴링해 리밸런스 콜백을 처리한다. 메시지는 파티션별 태스크가 받는다. | https://github.com/vectordotdev/vector/blob/v0.58.0/src/sources/kafka.rs | 2026-09-29 |
| 0.58.0 이후 master | 2026-03-01 이후 `src/sources/kafka.rs` 커밋에 리밸런스 정지 수정은 없다(#25764는 시험 불안정 완화, #26024는 압축 해제 옵션). | https://github.com/vectordotdev/vector/commits/master/src/sources/kafka.rs | 2026-09-29 |

## 3. Vector kafka 소스 옵션 (공식 기본값·의미)

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| session_timeout_ms | 기본 10000. 설명 "The Kafka session timeout". librdkafka `session.timeout.ms`로 그대로 넘긴다. 코드 주석은 "default in librdkafka"라고 적었지만 librdkafka 현재 기본값은 45000이다(4절). | https://vector.dev/docs/reference/configuration/sources/kafka/ , https://github.com/vectordotdev/vector/blob/v0.58.0/src/sources/kafka.rs | 2026-09-29 |
| drain_timeout_ms | 기본값은 session_timeout_ms의 절반(기본 설정이면 5000). 종료나 리보크 때 대기 중 ack 처리를 최대 이 시간만큼 기다린다. 문서: session_timeout_ms보다 작아야 리밸런스 중 그룹에서 빠지지 않는다. 코드 검사는 `<=`이다. | https://vector.dev/docs/reference/configuration/sources/kafka/ , https://github.com/vectordotdev/vector/blob/v0.58.0/src/sources/kafka.rs | 2026-09-29 |
| socket_timeout_ms | 기본 60000. "Timeout for network requests". | https://vector.dev/docs/reference/configuration/sources/kafka/ | 2026-09-29 |
| fetch_wait_max_ms | 기본 100. "Maximum time the broker may wait to fill the response". librdkafka 자체 기본은 500이다. | https://vector.dev/docs/reference/configuration/sources/kafka/ , https://github.com/confluentinc/librdkafka/blob/v2.12.1/CONFIGURATION.md | 2026-09-29 |
| commit_interval_ms | 기본 5000. 오프셋 커밋 주기. `auto.commit.interval.ms`로 넘긴다. | https://vector.dev/docs/reference/configuration/sources/kafka/ | 2026-09-29 |
| librdkafka_options | 기본 없음. "Advanced options set directly on the underlying librdkafka client". 고정 설정 뒤에 적용된다. | https://vector.dev/docs/reference/configuration/sources/kafka/ | 2026-09-29 |
| acknowledgements(소스 수준) | 폐기 예정. 소스 수준 설정은 동작에 영향이 없다. 전역 또는 싱크 수준으로 켠다. | https://vector.dev/docs/reference/configuration/sources/kafka/ | 2026-09-29 |
| metrics.topic_lag_metric | 기본 false. 켜면 모든 토픽·파티션의 `kafka_consumer_lag` 게이지를 `topic_id`, `partition_id` 태그로 낸다. | https://vector.dev/docs/reference/configuration/sources/kafka/ | 2026-09-29 |
| 문서의 재시작 권고 | kafka 소스 문서에 브로커 재시작, 세션 타임아웃 권장값, `group.instance.id`, `cooperative-sticky` 언급은 없다. | https://vector.dev/docs/reference/configuration/sources/kafka/ | 2026-09-29 |

## 4. librdkafka 동작 (2.12.1 기준, Vector 0.58.0 번들 버전)

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| session.timeout.ms | 기본 45000. 범위는 브로커 `group.min.session.timeout.ms`~`group.max.session.timeout.ms`. | https://github.com/confluentinc/librdkafka/blob/v2.12.1/CONFIGURATION.md | 2026-09-29 |
| 기본값 변경 이유 | v1.7.0(KIP-735)에서 10초→45초. "make consumer groups more robust and less sensitive to temporary network and cluster issues". | https://github.com/confluentinc/librdkafka/blob/v2.12.1/CHANGELOG.md | 2026-09-29 |
| 클라이언트 측 세션 만료 | v1.6.0부터 코디네이터 연결이 끊긴 동안에도 세션 타임아웃을 로컬에서 적용한다. classic 프로토콜은 세션 만료 시 fetch를 멈춘다. | https://github.com/confluentinc/librdkafka/blob/v2.12.1/CHANGELOG.md , https://github.com/confluentinc/librdkafka/blob/v2.12.1/INTRODUCTION.md | 2026-09-29 |
| SESSTMOUT 뒤 동작 | 코드: 경고 "...: revoking assignment and rejoining group"을 남긴다. member id를 비운다. 배정을 lost로 표시하고 리보크 후 재참여를 시작한다. 이미 리밸런스 중이면 건너뛴다. | https://github.com/confluentinc/librdkafka/blob/v2.12.1/src/rdkafka_cgrp.c | 2026-09-29 |
| 재참여 조건(eager) | 배정이 있으면 애플리케이션 rebalance 콜백에 REVOKE를 보낸다. 애플리케이션이 `rd_kafka_assign(NULL)`을 해야 다음 단계로 간다. 배정이 없으면 바로 rejoin한다. | https://github.com/confluentinc/librdkafka/blob/v2.12.1/src/rdkafka_cgrp.c , https://github.com/confluentinc/librdkafka/blob/v2.12.1/src/rdkafka.h | 2026-09-29 |
| rebalance 콜백 책임 | 콜백을 등록하면 자동 배정·해제가 꺼지고 애플리케이션 책임이 된다. 콜백은 `rd_kafka_consumer_poll()`이 처리한다. | https://github.com/confluentinc/librdkafka/blob/v2.12.1/src/rdkafka.h | 2026-09-29 |
| rust-rdkafka 연결 | rust-rdkafka 0.39 기본 `rebalance`는 `pre_rebalance`를 먼저 부르고, 반환한 뒤에야 `rd_kafka_assign(NULL)`(eager) 또는 `incremental_unassign`(cooperative)을 부른다. 즉 Vector의 `pre_rebalance`가 끝나야 librdkafka가 재참여로 넘어간다. | https://github.com/fede1024/rust-rdkafka/blob/v0.39.0/src/consumer/mod.rs | 2026-09-29 |
| AssignmentLost 커밋 | 배정이 lost 상태이면 현재 배정 오프셋 커밋을 즉시 `ERR__ASSIGNMENT_LOST`로 거절한다(블록하지 않음). lost 파티션은 이미 다른 멤버 소유일 수 있어 커밋이 실패할 수 있다고 문서화돼 있다. | https://github.com/confluentinc/librdkafka/blob/v2.12.1/src/rdkafka_cgrp.c , https://github.com/confluentinc/librdkafka/blob/v2.12.1/src/rdkafka.h | 2026-09-29 |
| max.poll.interval.ms | 기본 300000. 초과하면 실패로 보고 리밸런스한다. 초과 시 경고 "MAXPOLL ... leaving group"을 남긴다. 컨슈머 큐나 그 큐가 포워딩된 큐를 폴링하면 폴링으로 센다. | https://github.com/confluentinc/librdkafka/blob/v2.12.1/CONFIGURATION.md , https://github.com/confluentinc/librdkafka/blob/v2.12.1/src/rdkafka_cgrp.c , https://github.com/confluentinc/librdkafka/blob/v2.12.1/src/rdkafka.h | 2026-09-29 |
| heartbeat.interval.ms | 기본 3000. | https://github.com/confluentinc/librdkafka/blob/v2.12.1/CONFIGURATION.md | 2026-09-29 |
| partition.assignment.strategy | 기본 `range,roundrobin`. `cooperative-sticky` 사용 가능. cooperative와 eager는 섞으면 안 된다. | https://github.com/confluentinc/librdkafka/blob/v2.12.1/CONFIGURATION.md | 2026-09-29 |
| group.protocol | 기본 `classic`. `consumer`(KIP-848) 선택 가능. `consumer`면 `session.timeout.ms`·`heartbeat.interval.ms`는 브로커 설정이 정한다. | https://github.com/confluentinc/librdkafka/blob/v2.12.1/CONFIGURATION.md | 2026-09-29 |
| group.instance.id | 정적 멤버십. `session.timeout.ms` 안에서 나갔다 들어와도 리밸런스 없이 배정을 유지한다. 문서는 더 큰 `session.timeout.ms`와 함께 써서 일시적 불가용에 따른 리밸런스를 피하라고 한다. 브로커 2.3.0 이상. | https://github.com/confluentinc/librdkafka/blob/v2.12.1/CONFIGURATION.md | 2026-09-29 |
| 정적 멤버십 위험 보고 | librdkafka #3437 "Consumer hangs when session times out while using static groups". 2021-06-18 열림, open(라벨 `try reproduce`). SESSTMOUT 뒤 "Static consumer fenced" 치명 오류 보고. | https://github.com/confluentinc/librdkafka/issues/3437 | 2026-09-29 |
| 관련 미해결 #5569 | classic 프로토콜에서 KIP-394 member id를 두 번 받아 첫 id를 버리면 그룹이 `PreparingRebalance`에 `session.timeout.ms` 동안 머문다. 그동안 어느 멤버도 파티션을 갖지 않는다. 2026-08-13 열림, open. 수정 PR #5570 open. 단일 노드 KRaft 3.9.0에서 관찰. 정지 시간은 session.timeout.ms로 한정된다고 적혀 있다. | https://github.com/confluentinc/librdkafka/issues/5569 , https://github.com/confluentinc/librdkafka/pull/5570 | 2026-09-29 |
| 관련 미해결 #5586 | `assign()` 뒤 OffsetFetch가 요청 수준 NOT_COORDINATOR(파티션 0개)를 받으면 파티션이 `.queried`에 영구히 남는다. fetch가 시작되지 않고 랙이 계속 는다. 코디네이터 브로커 재시작 중 재현. 2026-09-05 열림, open. 보고 버전 2.11.0. 보고자는 `subscribe()`가 아닌 `assign()`을 썼다. | https://github.com/confluentinc/librdkafka/issues/5586 | 2026-09-29 |
| 디버그 권장 | "Consumer not fetching messages" 문제는 `debug=consumer` 또는 `cgrp,fetch`로 시작하라고 한다. | https://github.com/confluentinc/librdkafka/blob/v2.12.1/INTRODUCTION.md | 2026-09-29 |
| statistics cgrp | 통계 JSON의 `cgrp`에 `state`, `join_state`, `rebalance_cnt`, `rebalance_reason`, `assignment_size`가 있다. `consumer_lag`은 (hi 또는 ls offset) − committed_offset. | https://github.com/confluentinc/librdkafka/blob/v2.12.1/STATISTICS.md | 2026-09-29 |
| rust-rdkafka 깨우기 경합 | rust-rdkafka #665 "StreamConsumer not waking"(open). 수정 PR #666 병합(2024-09-24). 0.37.0 changelog "Address wakeup races introduced by pivoting to the event API". 0.37에서도 소비 정지를 봤다는 사용자 댓글(2024-12)이 있다. | https://github.com/fede1024/rust-rdkafka/issues/665 , https://github.com/fede1024/rust-rdkafka/blob/v0.39.0/changelog.md | 2026-09-29 |
| rust-rdkafka #535 | "Dropping `PartitionQueue` makes partition unavailable". 2023-01-12 열림, open. | https://github.com/fede1024/rust-rdkafka/issues/535 | 2026-09-29 |

## 5. Kafka 브로커(4.3.1)·관측 도구

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| classic 그룹 세션 범위 | `group.min.session.timeout.ms` 기본 6000, `group.max.session.timeout.ms` 기본 1800000. | https://github.com/apache/kafka/blob/4.3.1/group-coordinator/src/main/java/org/apache/kafka/coordinator/group/GroupCoordinatorConfig.java | 2026-09-29 |
| 초기 리밸런스 지연 | `group.initial.rebalance.delay.ms` 기본 3000. | 같은 파일 | 2026-09-29 |
| consumer 프로토콜 세션 | `group.consumer.session.timeout.ms` 기본 45000(최소 45000, 최대 60000). | 같은 파일 | 2026-09-29 |
| describe의 "-" | `kafka-consumer-groups --describe`는 커밋 오프셋은 있으나 어느 멤버 배정에도 없는 파티션을 CONSUMER-ID "-"로 찍는다. 그룹이 Empty면 stderr에 "has no active members", 리밸런스 중이면 "is rebalancing"을 찍는다. | https://github.com/apache/kafka/blob/4.3.1/tools/src/main/java/org/apache/kafka/tools/consumer/group/ConsumerGroupCommand.java | 2026-09-29 |

## 6. Vector 내부 지표로 감지

| 항목 | 사실 | 1차 출처 URL | 확인일 |
|---|---|---|---|
| kafka_consumer_lag | `metrics.topic_lag_metric: true`일 때만 나온다. librdkafka 통계의 파티션별 `consumer_lag`를 그대로 옮긴다. | https://github.com/vectordotdev/vector/blob/v0.58.0/src/internal_events/kafka.rs | 2026-09-29 |
| 랙 지표 한계 | #21134(값이 틀림, open), #24647(리밸런스 후 옛 값 유지 수정, open, 미병합). #22006 보고자는 이 때문에 Vector 지표만으로 감시할 수 없다고 적었다. | https://github.com/vectordotdev/vector/issues/21134 , https://github.com/vectordotdev/vector/pull/24647 , https://github.com/vectordotdev/vector/issues/22006 | 2026-09-29 |
| 그룹 상태 지표 | 0.58.0 코드는 통계의 `cgrp`(state, join_state, rebalance_cnt 등)를 지표로 내보내지 않는다. 내보내는 것은 `kafka_queue_messages(_bytes)`, `kafka_requests/responses(_bytes)_total`, `kafka_consumed/produced_messages(_bytes)_total`, `kafka_consumer_lag`뿐이다. | https://github.com/vectordotdev/vector/blob/v0.58.0/src/internal_events/kafka.rs | 2026-09-29 |
| 일반 지표 | kafka 소스 문서 Telemetry에 `component_received_events_total`, `component_errors_total`, `source_lag_time_seconds` 등이 있다. | https://vector.dev/docs/reference/configuration/sources/kafka/ | 2026-09-29 |

## 근본 원인 후보 (사실 근거만)

우리 로그로 확정할 수 있는 것은 적다. 아래는 사실과 그 사실에서 나오는 한계만 적는다.

1. **세션 만료의 직접 조건은 설정값이다.** Vector 기본 session_timeout_ms는 10000이다. 우리 로그의 SESSTMOUT은 10009 ms다. librdkafka는 코디네이터 연결이 끊겨도 로컬에서 세션 만료를 적용한다. 약 7초 중단에 재접속·코디네이터 준비 시간이 더해져 10초를 넘기면 SESSTMOUT이 난다. librdkafka 기본값(45000)이었다면 같은 중단에서 만료가 났는지는 [미확인]이다(실측 없음).
2. **SESSTMOUT 뒤 재참여는 librdkafka 설계상 자동이다.** 단 eager 전략에서는 Vector의 `pre_rebalance`(리보크 ack 드레인, 기본 최대 5초)가 반환해야 librdkafka가 unassign 후 재참여한다. 우리 로그의 "Consumer commit error: AssignmentLost"는 리보크 경로에서 나오는 문구다. 그 뒤 `pre_rebalance`가 반환했는지는 로그로 알 수 없다 [미확인].
3. **Vector #22006 / PR #26438 경합.** 싱크 역압으로 드레인 시한이 지나 파티션 태스크가 abort되고, 같은 파티션이 같은 컨슈머로 돌아오면 새 큐가 깨어나지 않는다. 증상은 "로그 없음, 랙 증가, 재시작만 해결"로 우리와 같다. 그룹당 컨슈머가 하나이고 기본 `range,roundrobin`이면 파티션은 같은 컨슈머로 돌아온다. 0.58.0에는 수정이 없다. **다만 차이가 있다.** 이 경합에서는 컨슈머가 그룹 멤버로 파티션을 배정받은 채 멈춘다. 그러면 describe에 CONSUMER-ID가 보여야 한다. 우리 관측은 CONSUMER-ID "-"다. 브로커가 보기에 그 파티션을 가진 멤버가 없다는 뜻이다. 그래서 #26438 경합만으로 우리 관측을 설명할 수 있는지는 [미확인]이다.
4. **CONSUMER-ID "-"가 2분 넘게 이어진 것**은 (a) 그룹이 Empty(재참여 안 함) 또는 (b) 리밸런스가 끝나지 않음 중 하나다. 어느 쪽인지는 describe의 stderr 문구("has no active members" / "is rebalancing")로 가를 수 있다. 우리 기록에는 이 문구가 없다 [미확인]. librdkafka #5569의 정지는 session.timeout.ms(10초)로 한정된다고 보고돼 2분 넘는 정지를 설명하지 못한다. #5586은 `assign()` 사용자 보고라 `subscribe()`를 쓰는 Vector에 해당하는지 [미확인]이다.
5. **Vector가 아무 로그도 안 남긴 것**은 드레인 시한 초과 로그가 debug 수준이고, #26438 경합도 로그를 남기지 않는다는 사실과 맞는다. MAXPOLL 경고는 없었다. max.poll.interval 초과(기본 300초) 경로는 관측 범위(2분)와 맞지 않는다.

## 권장 조치 (출처 있는 것만)

| 조치 | 내용 | 근거 |
|---|---|---|
| 세션 타임아웃 상향 | `session_timeout_ms`를 브로커 중단보다 충분히 길게 둔다. librdkafka 기본 45000이 기준이다. 브로커 허용 범위는 6000~1800000. `drain_timeout_ms`를 명시하지 않으면 절반(22500)이 되고 리보크 때 그만큼 막힐 수 있다. 필요하면 따로 정한다(session보다 작게). | librdkafka CONFIGURATION.md·CHANGELOG(KIP-735), Kafka GroupCoordinatorConfig 4.3.1, Vector kafka 소스 문서 |
| 수정 버전 대기 | 2026-09-29 현재 수정 릴리스는 없다. 0.58.0이 최신 정식 릴리스다. PR #26438 병합과 그 뒤 릴리스 노트를 확인한 뒤 올린다. | https://github.com/vectordotdev/vector/pull/26438 , https://api.github.com/repos/vectordotdev/vector/releases |
| 할당 전략 | `librdkafka_options: {partition.assignment.strategy: cooperative-sticky}`는 PR #26438 재현에서 정지하지 않았다. 이유는 리보크된 파티션이 다른 멤버로 갔기 때문이라고 적혀 있다. 그룹당 컨슈머가 하나면 그 이점이 생기는지 [미확인]이다. 그룹 전체 멤버의 전략을 함께 바꿔야 한다(섞기 금지). | PR #26438, librdkafka CONFIGURATION.md |
| 정적 멤버십 | `group.instance.id` + 큰 session.timeout.ms는 librdkafka 문서가 일시적 불가용 대비로 권한다. 단 SESSTMOUT 뒤 fenced 치명 오류 보고(#3437, open)가 있다. 채택 전 검증이 필요하다. | librdkafka CONFIGURATION.md, INTRODUCTION.md, issue #3437 |
| 진단 로그 | 재발 조사용으로 `librdkafka_options: {debug: "cgrp,fetch"}`(또는 `consumer`)를 켠다. Vector 로그 수준을 debug로 올리면 드레인 시한 초과 로그("Acknowledgement drain deadline reached")가 보인다. | librdkafka INTRODUCTION.md, Vector v0.58.0 kafka.rs |
| 감지 | `metrics.topic_lag_metric: true`로 `kafka_consumer_lag`를 켠다. 단 #21134·#24647 한계가 있다. 소스 `component_received_events_total` 증가 정지와 브로커 측 `kafka-consumer-groups --describe --state`·`--members`를 함께 본다. Vector는 그룹 상태 지표를 내지 않는다. | Vector 문서·v0.58.0 코드, Kafka ConsumerGroupCommand |
| 복구 | #22006 보고자들이 쓰는 우회책은 Vector 재시작이다. 유지보수자 공식 권고는 없다. | https://github.com/vectordotdev/vector/issues/22006 |

## 확인 못 한 것

- [미확인] 우리 사례에서 리보크 드레인 시한이 실제로 지났는지. debug 로그가 없다.
- [미확인] 정지 중 그룹 상태(Empty인지 rebalancing인지). describe stderr 문구가 기록에 없다.
- [미확인] SESSTMOUT 뒤 JoinGroup을 시도했는지, 실패했는지. `debug=cgrp` 로그가 없다.
- [미확인] vector-alert-republish 그룹도 같은 시점에 멈췄는지.
- [미확인] 세션을 45000으로 올리면 7초 중단에서 만료가 사라지는지. 문헌상 기대일 뿐 실측이 없다.
- [미확인] cooperative-sticky가 단일 컨슈머 그룹에서 #26438 경합을 피하는지.
- [미확인] librdkafka #5586이 `subscribe()` 경로(Vector)에서도 생기는지.
- [미확인] Vector 유지보수자의 #22006·#26438 공식 입장. 2026-09-29 현재 유지보수자 댓글·리뷰가 없다.
- [미확인] PR #26438 병합 여부와 포함될 릴리스 번호.
