# 브로커 층 벤치 (EXP-130 계속) — 회전 1 후보 추가·Mosquitto 조건 시험 준비

작성 2026-09-29. **준비만 했고 띄우지 않았다**(무거운 측정 중 기동 금지). 검증된 것: `docker compose config -q` 통과(기본 서비스 목록은 기존 4개 그대로 `emqx hivemq mosquitto nanomq` — 새 후보는 모두 `profiles` 로만 뜸), `stage4.py` 분석부 합성 시험(정상·유실+중복 입력), `br07.py` 지표 판정 합성 시험(기존 키 판정 불변·NATS 동의어·깨진 입력), 이미지 로컬 보유.

기준: `QUESTIONS.md` §1, `harness/situations/BROKER.md`(BR-01~07), `CANDIDATES.md` §3 + 개정 #74, `ROBUSTNESS.md` R01·R02·R08·R09.
V1 = EMQX 5.8.6(강제 교체 확정, 2026-02-28 EOL). 측정 완료(재측정 안 함): Mosquitto 2.1.2 조건부 채택(#48·#56), NanoMQ 0.25.6 탈락, HiveMQ CE 2026.5 탈락.

## 1. 기존 측정 스크립트 재사용과 바꾼 곳

- `mqtt_bench.py`(BR-01·02·03·04·05·06)·`br07.py`(BR-07)를 그대로 쓴다. 바꾼 곳은 **환경변수가 없으면 기존과 똑같이 동작하는 추가분만**:
  - `mqtt_bench.py`: `BENCH_MQTT_USER/PASS`(제품 기본이 인증 필수인 RobustMQ·LavinMQ), `BENCH_WS_PORT/PATH`(WS 가 8083 /mqtt 가 아닌 TBMQ 8084·BifroMQ 80·Artemis 61616·LavinMQ 15672).
  - `br07.py`: 새 브로커의 지표 HTTP 경로, 제품별 지표 이름 동의어(`EXTRA_KEYS` — 공통 `KEYS` 불변이라 EXP-130 판정 불변), 인증 필수 브로커의 $SYS 자격증명, 접속 실패를 예외 대신 결과로 기록.
- 새 파일: `brokers.sh`(후보 표·기동/정리), `wait_mqtt.py`(CONNECT 성공까지 대기 — 실패 = ② 기동 탈락 근거), `stage2_new.sh`(run.sh·run_br03.sh 와 같은 순서를 후보마다), `stage4.py`·`stage4_mosq.sh`(Mosquitto 미검증 조건).
- `run.sh`·`run_br03.sh`·기존 설정 파일은 손대지 않았다(EXP-130 재현성).

## 2. 후보 → 프로파일

원칙(기존과 같음): 제품 기본값 + V1 EMQX 가 하던 역할(1883·WebSocket·오프라인 세션 보존·재시작 넘어 보존·지표)에 필요한 최소 설정만. V1 EMQX 는 `max_mqueue_len 10만`·`session_expiry 2h`·`max_inflight 128`·익명 허용.

| 후보(우선순위) | 프로파일 | 이미지 | 설정(V1 역할 재현) | 알려진 차이·위험 |
|---|---|---|---|---|
| RMQTT 0.24.0 (P1) | `rmqtt` | `rmqtt/rmqtt:0.24.0` | `rmqtt/rmqtt.toml` = 업스트림 0.24.0 원문 + 5곳: session-storage(sled 디스크) 켬, `max_mqueue_len` 1000→10만, `mqueue_rate_limit` 1000/s→10만/s, `message_expiry_interval` 5m→2h, `max_inflight` 16→128, WS 8080→8083 | **기본값이 V1 보다 훨씬 작다**(큐 1000·큐 속도 1000/s·메시지 만료 5분) — 기본 그대로면 BR-03/큐 시험에서 떨어짐. 익명 허용 기본(① 기본 보안 기록) |
| TBMQ 2.4.0 (P2) | `tbmq` | `thingsboard/tbmq:2.4.0`, `postgres:17`, `apache/kafka:4.3.1`, `valkey/valkey:8.0.11-alpine` | 공식 `msa/tbmq/configs/docker-compose.yml`(2.4.0) 구성. 바꾼 곳: Kafka 4.0.0→4.3.1(4.0 은 ① 관문 제외 라인), valkey 8.0→8.0.11 고정, `SECURITY_MQTT_BASIC_ENABLED` true→false(V1 처럼 익명), 지표 노출 | 컨테이너 4개(브로커+Kafka+PG+Valkey) — ③ 복잡도·메모리 불리. WS 8084 |
| Apache BifroMQ 4.0.0-incubating (P2) | `bifromq` | `apache/bifromq:4.0.0-incubating` (Docker Hub 존재 확인 → R01/R02 기재 불일치 해소) | **설정 무변경**(이미지 기본 `standalone.yml`) | WS 기본 포트 80(`/mqtt`) [미확인]. 지표 경로 [미확인](9090/8091 시도). 인증 플러그인 없으면 전부 허용. 오프라인 큐 기본 한도 [미확인] |
| RabbitMQ 4.3.6 MQTT (P2) | `rabbitmq` | `rabbitmq:4.3.6-management-alpine` | `rabbitmq.conf`: MQTT 1883, Web MQTT 8083 `/mqtt`, 익명(`anonymous_login_user`), Prometheus 15692. `enabled_plugins`: management·mqtt·web_mqtt·prometheus | 4.x 에서 `mqtt.allow_anonymous` 가 없어져 익명 설정 방식이 다름 — 접속 실패 시 ② 로그로 판정. 큐 한도 기본 없음(메모리·디스크 경보) |
| LavinMQ 2.10.0 (P3) | `lavinmq` | `cloudamqp/lavinmq:2.10.0` | 설정 무변경. 제품 기본 인증 guest/guest 로 접속 | MQTT 3.1.x 만. WS 경로 [미확인](15672 시도) |
| ActiveMQ Artemis 2.57.0 (P3) | `artemis` | `apache/artemis:2.57.0` (#74 이미지) | 이미지 환경변수만: `ANONYMOUS_LOGIN=true`, 관리자 artemis/artemis. MQTT 1883 기본 acceptor, WS 는 61616 다중 프로토콜 acceptor | Prometheus 플러그인 미동봉 → BR-07 은 Jolokia 로 시도 |
| ActiveMQ Classic 6.3.2 (P3) | `activemq` | `apache/activemq:6.3.2` (#74 이미지) | `activemq/activemq.xml` = 이미지 기본 파일에서 mqtt(1883)·ws(→8083) 커넥터 주석 해제만 | **이미지 기본은 MQTT 꺼짐**. Jolokia 8161 이 컨테이너 밖에서 열리는지 [미확인] |
| comqtt v2.6.5 (P3, MIT 확인: LICENSE.md) | `comqtt` | `ghcr.io/wind-c/comqtt:2.6.5` | `comqtt/single.yml` = 동봉 예제에서 저장 경로 /data, 대시보드 끔, WS 8083, 콘솔 로그. 저장 bolt(기본값) | — |
| RobustMQ v0.4.11 (P3) | `robustmq` | `ghcr.io/robustmq/robustmq:v0.4.11` (#74 "이미지 미확인" → ghcr 에서 확인) | `robustmq/server.toml` = 이미지 기본 + 템플릿 섹션 복사: `durable_sessions_enable` true, 세션 만료 30 s→7200 s | **기본 인증 켜짐**(admin/robustmq) — ① 기본 보안은 유리. 기본 세션 만료 30초(3.1.1 영속 세션이 30초 뒤 사라짐 → 기본 그대로면 BR-03 실패) |
| Mochi-MQTT 2.7.9 (P3) | `mochi` | `mochimqtt/server:2.7.9` | `mochi/config.yaml`: TCP 1883·WS 8083·sysinfo 8080, `allow_all`, badger 디스크 영속 | 18개월 무릴리스(유지보수 위험 기록). 설정 형식 [미검증] |
| NATS Server 2.15.0 MQTT (P2) | `nats` | `nats:2.15.0-alpine` | `nats/nats.conf`: JetStream(파일) + mqtt 1883 + websocket 8083(no_tls) + 모니터링 8222 | MQTT 3.1.1 만, JetStream 필수. MQTT over WebSocket 동작 [미검증] |
| HiveMQ Edge 2026.14 내장 브로커 (P2) | `hivemq-edge` | `hivemq/hivemq-edge:2026.14` | `hivemq-edge/config.xml`: TCP 1883 + WS 8083 `/mqtt` 만(수집 어댑터 없음) | 수집 층 벤치와 같은 이미지(P-EB 판정은 두 벤치 결과를 합쳐서) |

### 2-1. V1 보장 맞춤 설정(09-29 지시: 기본값이 작은 후보는 맞춘 뒤 비교)

V1 EMQX 보장: 오프라인 큐 10만(`max_mqueue_len`), 세션 만료 2h, 인플라이트 128, QoS1 영속 세션, 재시작 넘는 보존은 제품 영속 기능으로(Mosquitto `persistence` 와 같은 조건).

| 후보 | 기본값(문제) | 맞춘 값 | 어디서 | 못 맞춘 것(약점 열) |
|---|---|---|---|---|
| RMQTT | 큐 1000, 큐 속도 1000/s, 메시지 만료 5분, 인플라이트 16, 세션 메모리 | 큐 10만, 10만/s, 만료 2h, 128, session-storage(sled 디스크) | `rmqtt/rmqtt.toml` | — |
| RobustMQ | 세션 만료 기본 30 s·최대 1800 s, 세션 메모리 | 7200 s/7200 s, `durable_sessions_enable=true` | `robustmq/server.toml` | 오프라인 메시지 무제한(기본) — 한도 시험 결과가 V1 과 다를 수 있음 |
| TBMQ | DEVICE 영속 메시지 1만 | 10만(`MQTT_PERSISTENT_SESSION_DEVICE_PERSISTED_MESSAGES_LIMIT`) | compose 환경변수 | — |
| BifroMQ | 세션 inbox 1000, 연결당 발행 200/s, 수신 최대 200 | inbox 65535, 1000/s, 65535 (JVM `-D<설정>`, Setting.java 가 System 속성으로 기본값 덮어씀) | compose `EXTRA_JVM_OPTS` | **inbox 상한 65535 < 10만**, **연결당 발행 상한 1000/s < 과부하 시험 1200/s** — 제품 상한 |
| Mochi-MQTT | 인플라이트(오프라인 QoS1 보관) 8192, 쓰기 대기 8192 | 65535, 65535 | `mochi/config.yaml` `options.capabilities` | **보관 상한 65535 < 10만**(제품 상한 uint16) |
| comqtt | 쓰기 대기 65535(예제) | 100000 | `comqtt/single.yml` | — |
| NATS MQTT | 세션당 미확인 1024 | `max_ack_pending 65535`(제품 상한). 오프라인 보관은 JetStream(무제한) | `nats/nats.conf` | — |
| HiveMQ Edge | 큐 1000 | `max-queue-size 100000` | `hivemq-edge/config.xml` | 키 이름 [미검증] |
| RabbitMQ | 큐 한도 없음(메모리·디스크 경보로 흐름 제어), 세션 만료 최대 86400 s | 변경 없음(≥ V1) | — | 한도 초과 시 버리는 대신 발행자 차단 — queuelimit 시험에서 동작이 다름 |
| Artemis·ActiveMQ·LavinMQ | 디스크 영속·페이징 기본, 한도 없음 | 변경 없음 | — | 〃 |

제외(① 관문): EMQX 6.x(BSL), VerneMQ(이미지 EULA), FlashMQ·Aedes·Moquette(이미지 없음), Waterstream·Cedalo Pro(상용), **Amlen(#74: 고정 태그 없음)**.

## 3. Mosquitto 2.1.2 남은 조건(#56 미검증) — `stage4_mosq.sh`

기준 버전 EMQX 5.8.6 을 **같은 스크립트로 먼저** 잰다. 발행자·구독자를 별도 컨테이너로 띄워 한쪽만 네트워크에서 뗄 수 있다.

| 시험 | 대응 | 주입 | 잴 것(결과 JSON) |
|---|---|---|---|
| `netcut` | S10·R02 | 120건/s × 150 s, 25초 뒤 구독자(`SIDE=sub`) 또는 발행자(`SIDE=pub`) 컨테이너를 `brokerbench_default` 에서 60초 분리 | 유실·중복·순서 역전·최대 공백·재연결 후 첫 수신 시간(`after_events`)·적체 해소(`drain_after_pub_end_s`). 반쯤 열린 연결은 keepalive 60 s(1.5배=90 s)로 감지된다 |
| `overload` | R08 | 1200건/s(정상 120의 10배) × 600 s | 유실·지연 p95·적체 해소·브로커 CPU/메모리 |
| `queuelimit` | 큐 한도 | 구독자 5초 뒤 오프라인, 1200건/s × 100 s = 12만 건(> 큐 10만) 후 재접속 | 받은 수·버린 구간(`lost_ranges_sample`: 오래된 쪽/새 쪽)·메모리 최대. EMQX `max_mqueue_len 10만` vs Mosquitto `max_queued_messages 10만` |
| `slowsub` | 느린 구독자 | 120건/s × 300 s, 빠른 구독자 + 느린 구독자(12 ms/건 ≈ 83건/s) | 빠른 쪽 지연 p95 영향, 느린 쪽 유실·해소 시간, 브로커 메모리 |
| `longrun` | R09 | 120건/s × 3600 s | 유실 0, 메모리 증가율(`mem_growth_mib_per_h(linear)`, 처음·마지막 5분 중앙값) |

## 4. 명령

레포 루트(Git Bash)에서, 한 번에 하나.

```bash
# 새 후보 ②③ (브로커마다 기동→BR-01→02→04·05→03→06→07→내림). 3회: 접두사 c1 c2 c3
harness/brokerbench/stage2_new.sh c1                  # 전체 신규 후보
harness/brokerbench/stage2_new.sh c1 "rmqtt nats"     # 일부만
# Mosquitto 조건(기준 EMQX 먼저)
harness/brokerbench/stage4_mosq.sh netcut emqx
harness/brokerbench/stage4_mosq.sh netcut mosquitto
SIDE=pub RUN=b harness/brokerbench/stage4_mosq.sh netcut mosquitto
harness/brokerbench/stage4_mosq.sh overload mosquitto
harness/brokerbench/stage4_mosq.sh queuelimit mosquitto
harness/brokerbench/stage4_mosq.sh slowsub mosquitto
harness/brokerbench/stage4_mosq.sh longrun mosquitto
```

결과: `experiments/EXP-130/raw/<broker>_<mode>_<run>.json`(기존 형식), `br07_<pre>_<broker>.json`, `stats_<broker>_<pre>.csv`, `images_<broker>.json`, `logs_<broker>_<pre>.txt`; 4단계 `experiments/EXP-130/stage4_<test>_<broker>_<RUN>.json`(+ raw 역할별·events·stats4).

## 5. 주의·미검증

- `stage2_new.sh` 는 BR-01 에서 유실이 나면 그 브로커의 뒤 단계를 생략한다(QUESTIONS §1 빠르게 거르는 순서).
- 재시작 시험은 `docker restart brokerbench-<b>-1` — TBMQ 는 브로커 컨테이너만 재시작(Kafka·PG·Valkey 는 유지).
- 새 후보 설정의 실제 적용 여부는 기동 로그로만 확인 가능(미실행). 특히 BifroMQ·LavinMQ WS 경로, RabbitMQ 4.x 익명, Mochi 설정 로드, NATS MQTT-over-WS.
- 일부 이미지는 Docker Hub 429 때문에 `mirror.gcr.io` 에서 받아 원래 이름으로 태그(내용 동일, RepoDigest 는 미러 주소).
