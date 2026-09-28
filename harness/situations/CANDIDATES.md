# 층별 대안 후보표 — 결과 보기 전 고정 2026-09-29

원칙(QUESTIONS Q2-0b): 대안은 **현업에서 쓰는 OSI·무료 제품·프레임워크**만. 직접 짠 대체 코드는 후보 아님.
각 층은 모듈 벤치로 정상 성능 + `ROBUSTNESS.md` 비정상 상황을 V1 부품과 같은 방법으로 잰다. 이긴 부품을 모아 V2 조립 → V1 전체 기준(EXP-000)과 비교.
출처: `docs/research/AGENT_BRIEF_FINAL.md` §11~13·§16. "미시험"은 유지 확정이 아니다(#59).

| 층 | V1 | 대안 후보 | 문헌 탈락·제외 | 상태 |
|---|---|---|---|---|
| 브로커 | EMQX 5.8.6 | Mosquitto 2.1.2 · NanoMQ 0.25.6 · HiveMQ CE 2026.5 | EMQX 5.9+(BSL), VerneMQ 이미지(EULA) | Mosquitto 조건부(#56) |
| 이상탐지 | Flink 1.20.1 | Flink 2.2.1 SQL · Flink 2.2.1 DataStream CEP · (+자동 복구 구성) · Kafka Streams · Timeplus Proton | Materialize(BSL), RisingWave(Premium 키), 독립 CEP(Esper·Siddhi), 직접 짠 Python(#53) | Flink 2.2.1 정확도 동일, 나머지 미시험 |
| 수집 | EdgeX 4.0.0(10컨테이너) | Telegraf inputs.modbus · Neuron OSS(Modbus TCP·MQTT만) · Node-RED+modbus | Neuron 상용 드라이버 | 미시험 |
| 중계 파이프 | Telegraf ×3 | Telegraf 1개 통합 · Redpanda Connect(Apache 컴포넌트만) | Redpanda 브로커(BSL), 엔터프라이즈 커넥터(RCL) | 미시험 |
| 백본 | Kafka 3.9.0 | Kafka 4.2.x(KRaft) · NATS JetStream | Redpanda(BSL), Pulsar·RocketMQ(과함), MQTT 단독(재처리 불가) | 미시험 |
| 시계열 저장 | InfluxDB 2.7 | TimescaleDB Apache 에디션 · PostgreSQL+pg_partman · QuestDB | InfluxDB 3 Core(72시간 한도·Flux 없음), TimescaleDB TSL 기능 | 미시험 |
| 알람 표시·상태 | Telegraf#3→MQTT→FUXA, 상태 관리 없음 | Vue MQTT over WebSocket 직접 구독 · ISA-18.2 알람 상태(PostgreSQL) | — | 미시험 |
| 운영 감시 | Prometheus+Alertmanager | VictoriaMetrics(선택) | — | 미시험(우선순위 낮음) |
| HMI | FUXA 1.3.x | FUXA 1.3.4(보안 버전) | Ignition(상용) | 업그레이드만 |
| 그래프 DB | Neo4j 5.26 | 유지(사용자 지시). Apache AGE 참고 측정 가능 | Memgraph(BSL), FalkorDB(SSPL), Kuzu(아카이브) | 유지 |

우선순위(가치·위험 순): 이상탐지 자동 복구(V1 최대 약점) → 수집(10컨테이너) → 중계 파이프·알람 경로 → 백본 → 시계열 저장 → 운영 감시.
