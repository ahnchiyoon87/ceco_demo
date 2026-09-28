# 백본 벤치 ② 준비 (EXP-BB) — 2026-09-29 준비, **미실행**

판정 규칙: `QUESTIONS.md` §1. 후보 목록: `harness/situations/CANDIDATES.md` §5(+개정 #74). 비정상 항목: `ROBUSTNESS.md` R03·R08·R09.
이 문서는 준비물 설명이다. 결과 수치는 실행 후 `experiments/EXP-BB/stage2_<profile>.json` 에만 쓴다.

## 무엇을 재나 (결과 보기 전 고정)

| 변형 | 부하 | 잴 것 | 대응 |
|---|---|---|---|
| `base` | 12태그 × 1장치 × 1Hz (V1 정상, 120초) | 유실·중복·키 안 순서, 지연 p50/p95/p99, 재생 2종 | F01, E6/F11 |
| `x10` | 12태그 × 1장치 × 10Hz | 같은 항목 | R08 배수(10분 과부하는 ④) |
| `scale` | 12태그 × 10장치 × 1Hz | 같은 항목 | 확장 여유 |
| `restart` | base + 45초에 브로커 `docker restart` | 유실·중복·재개(소비자 복귀) | R03 |
| `telegraf` | Kafka 프로토콜 후보만 | Telegraf 1.40.1 `outputs.kafka`(V1 bridge 설정) 모양·건수, `inputs.kafka_consumer`(V1 sink 설정 그대로 / `kafka_version="2.1.0"`) 저장 건수 | CANDIDATES §4, #17570 |

- 레코드: `harness/SCHEMA.md` §3 raw 모양 + 측정 필드 `seq·emit_ns·run`(§4). 토픽 `sensor.telemetry.raw` 6파티션·24h·lz4·키=tag (V1 `kafka/create-topics.sh`).
- 정답: (장치,태그)별 seq 1..N — 유실 = 기대 − 고유 수신, 중복 = 같은 seq 재수신, 순서 = 키 안 seq 감소.
- 재생(V1 이 Kafka 오프셋 재생에 의존 — E6): 발행 중간 시각 이후 부분집합을 (a) 위치(오프셋/시퀀스) (b) 시각으로 새 소비자가 다시 읽어 `missing=0` 이면 통과.
- 지연: 발행·소비가 같은 컨테이너(같은 시계). 클라이언트 배치 차이는 아래 "후보별" 열에 적었다.
- 자원: `harness/sample_stats.sh` 1초 샘플(변형별 CSV) → 중앙값·최대. ③ 판정은 같은 조건 3회 중앙값(§1) — ②는 1회.
- **자원 한도 없음(09-29 결정 I5):** 컨테이너 메모리·CPU 제한을 두지 않는다 — 실제 사용량 자체가 ③ 효율 측정값. 공정성은 같은 호스트에서 벤치 하나씩(각 stage2.sh 가 같은 벤치 동시 기동 거부, rot 스택과는 가드로 분리). JVM 힙 등 제품 설정은 상류 예시·기본값 그대로.

## 후보 → 프로파일

| 후보 | 프로파일 | 이미지(정확한 태그) | V1 기능을 어떻게 재현 | 갭·주의 | 명령 |
|---|---|---|---|---|---|
| Kafka 3.9.0 (기준 V1, 강제 교체 대상) | `kafka39` | `apache/kafka:3.9.0` | V1 compose kafka 환경 그대로(KRaft 단일) | 외부 리스너만 없음 | `harness/backbonebench/stage2.sh kafka39` |
| **Kafka 4.3** (같은 제품 최신, P1) | `kafka43` | `apache/kafka:4.3.1` | 같은 환경·같은 토픽·같은 클라이언트 | Telegraf #17570 확인 필수(`telegraf` 단계) | `… stage2.sh kafka43` |
| Kafka 4.2 (P1) | `kafka42` | `apache/kafka:4.2.2` | 같음 | 같음 | `… stage2.sh kafka42` |
| Kafka 4.1 (P3, 종료 2027-10-15) | `kafka41` | `apache/kafka:4.1.2` | 같음 | 12개월 경계 | `… stage2.sh kafka41` |
| AutoMQ 1.7.4 | `automq` | `automqinc/automq:1.7.4` + S3 `chrislusf/seaweedfs:4.47` | Kafka 프로토콜 그대로(상류 compose 명령, 엔드포인트만 SeaweedFS) | **S3 저장소 필수 → 상류 예시 `minio/minio:RELEASE.2025-05-24…` 는 받을 수 없음(2026-09-29 확인: Docker Hub `minio/minio` 저장소 404, GitHub `minio/minio` archived=true)** → SeaweedFS(Apache-2.0)로 대체 — AutoMQ 와의 S3 호환 [미검증]. 컨테이너 3개(+init) | `… stage2.sh automq` |
| Tansu 0.6.0 | `tansu` | `ghcr.io/tansu-io/tansu:0.6.0` + `postgres:18.6` | Kafka 프로토콜, 저장 엔진 PostgreSQL(영속) | **이미지 존재 확인(2026-09-29 manifest) → §12-2 [미확인] 해소, 관문 → 직접 시험.** 1.0 이전. `offsets_for_times`(시각 재생) 지원 [미확인] | `… stage2.sh tansu` |
| NATS 2.15 JetStream | `nats` | `nats:2.15.0-alpine` | 파일 스트림 1개(주제 `sensor.telemetry.raw.<device>.<tag>`), 재생 = 시퀀스·시각 | **파티션 없음(스트림 전체 한 순서)**. Telegraf `kafka_consumer`·Flink Kafka 커넥터 직결 불가(Flink 는 제3자 Synadia 커넥터, ALO) | `… stage2.sh nats` |
| Pulsar 4.0 LTS | `pulsar` | `apachepulsar/pulsar:4.0.13` | 분할 토픽 6·키=tag, 네임스페이스 보존 24h, 재생 = MessageId(Reader)·시각(seek) | 보존 설정 없으면 확인된 메시지는 재생 불가(설정으로 해결). standalone 메모리 큼. 활성 지원 2026-10-21 종료(보안 2027-10-21) | `… stage2.sh pulsar` |
| RabbitMQ 4.3 Streams | `rabbitmq` | `rabbitmq:4.3.6-alpine` (+`rabbitmq_stream` 플러그인) | 스트림 1개 max-age 24h, 재생 = 오프셋·시각 | **단일 스트림(파티션은 슈퍼 스트림 — ④에서)**. 클라이언트(rstream)는 틱 단위 `send_batch`(기본 0.5초 타이머 회피). Flink 공식 커넥터 없음 [미확인] | `… stage2.sh rabbitmq` |
| Apache Iggy 0.9.0 | `iggy` | `apache/iggy:0.9.0` | 스트림 `sensor`/토픽 `telemetry_raw` 6파티션·키, 재생 = 오프셋·시각 | **상류 compose 가 `seccomp:unconfined`·`SYS_NICE`·memlock 무제한 요구(io_uring) → ① 기본 보안 약점 기록.** 토픽 이름 점 회피. Kafka 비호환 → Telegraf·Flink 연동 없음 | `… stage2.sh iggy` |
| RocketMQ 5.5.0 | `rocketmq` | `apache/rocketmq:5.5.0` ×2(namesrv, broker+proxy) | FIFO 토픽 6큐, message_group=tag, 순서 소비 그룹 | **토픽 이름에 점 금지** → `sensor_telemetry_raw`. 클라이언트에 오프셋 노출 없음 → **위치 재생 불가**, 시각 재생은 `mqadmin resetOffsetByTime`(stage2.sh 가 파일 핸드셰이크로 실행) [미검증]. Telegraf 입출력 플러그인 없음 | `… stage2.sh rocketmq` |
| MQTT 단독(백본 없음) | `mqtt` | `eclipse-mosquitto:2.1.2-alpine` | QoS1·영속 세션(brokerbench EXP-131 설정) | **과거 재생 수단 없음(retained=마지막 1건)** → 재생 두 항목은 0건 기록 예상. E6 재처리 불가가 문헌상 약점 → 실측으로 확정 | `… stage2.sh mqtt` |
| Fluss 1.0.0 | — (프로파일 없음) | `apache/fluss` | — | Flink 내부 저장 전용, Telegraf·일반 클라이언트 직결 불가 → ②에서 "V1 raw 적재 경로 재현 불가"로 판정할 근거만 기록. 필요 시 Flink SQL 커넥터 경로로 별도 벤치 | — |
| Pulsar 5.0 | — | `5.0.0-M2` | — | 정식판 없음(보류, CANDIDATES) | — |

## V1 기능 ↔ 재현 방법 (동등성 확인 대상)
- raw 적재(F01): 발행·소비 건수·순서.
- 소비자 여럿(Flink·Telegraf#2·#3·알람 워커): 다른 그룹/구독자로 같은 데이터를 다시 읽는 능력 = 재생 항목으로 대리 확인. 실제 소비자 연동(Flink 커넥터·Telegraf 플러그인)은 **Kafka 프로토콜 후보만 무수정 가능** — 나머지는 어댑터 필요(구조 비교 때 경유 단계 +1 로 계산).
- 재처리(E6): 위치·시각 재생.
- 재시작(R03): `restart` 변형.
- Telegraf 1.40 호환: `telegraf` 단계(#17570: Kafka 4 에서 `consume: EOF`, 이슈는 2025-11-19 비활동 종료 — 해결 근거 없음, 워크어라운드 `kafka_version`).

## 실행
```bash
# 무거운 측정이 끝나고 rot-iiot/rot-ai 가 내려간 뒤(가드: 떠 있으면 거부, FORCE=1 로만 무시)
harness/backbonebench/stage2.sh kafka39                 # 기준선 먼저(같은 벤치·같은 방법)
for p in kafka43 kafka42 kafka41 nats pulsar rabbitmq automq tansu iggy rocketmq mqtt; do harness/backbonebench/stage2.sh $p; done
DURATION=600 VARIANTS="x10" harness/backbonebench/stage2.sh kafka43   # ④ R08 10분 과부하
DURATION=3600 VARIANTS="base" harness/backbonebench/stage2.sh kafka43 # ④ R09 60분
```
산출: `experiments/EXP-BB/stage2_<profile>.json`(요약·판정), `raw/<profile>_<variant>.json`, `raw/stats_*.csv`, `raw/<profile>_telegraf.json`, `raw/telegraf/*.log`, `raw/images_<profile>.txt`.

## 준비 검증(2026-09-29)
- `docker compose -f harness/backbonebench/compose.yml --profile '*' config -q` 통과, latest 0(`harness/benchcommon/validate.sh`).
- 가드: rot 컨테이너 29개 실행 중 `stage2.sh kafka43` → 종료 코드 3(거부) 확인. 필터는 정상/깨진 입력 둘 다 확인.
- 이미지 받기: 5개 벤치 외부 이미지 58개 받음·실패 0(`experiments/BENCH-PREP/pull_20260929_0258.log`), 직접 빌드 이미지(bench-*)는 실행 때 빌드.
- 클라이언트 라이브러리 휠 존재 확인(PyPI, linux cp312): confluent-kafka 2.15.1, nats-py 2.16.0, pulsar-client 3.13.0, rstream 1.1.0, apache-iggy 0.9.0(manylinux_2_34), rocketmq-python-client 5.1.2, paho-mqtt 2.1.0. **실행은 안 함** — 어댑터 코드의 API 호출은 휠의 타입 스텁·소스로 맞췄고 실제 동작은 미검증.
