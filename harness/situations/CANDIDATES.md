# 층별 대안 후보표 — 결과 보기 전 고정 2026-09-29 (#59, #60 개정)

원칙(QUESTIONS Q2-0b): 대안은 **현업에서 쓰는 OSI·무료 제품·프레임워크**만. 직접 짠 대체 코드는 후보 아님.
각 층은 모듈 벤치로 정상 성능 + `ROBUSTNESS.md` 비정상 상황을 V1 부품과 같은 방법으로 잰다. 이긴 부품을 모아 V2 조립 → V1 전체 기준(EXP-000)과 비교.
출처: `docs/research/AGENT_BRIEF_FINAL.md` §11~13·§16. "미시험"은 유지 확정이 아니다(#59).

**결정 방식(09-29 사용자 지시 "추론 말고 직접 해 보고 결정", #60):** 문헌으로 제외하는 것은 **라이선스·약관(법적 사실)** 뿐이다. 성능·용도 추정으로 뺐던 후보는 전부 직접 시험 대상으로 옮긴다.
층마다 벤치 하나에 V1 부품과 후보를 함께 띄우고 같은 순서로 직접 돌린다: ① 기동·기능(V1이 하던 일을 실제로 하는가, 실패는 로그·화면으로 기록하고 그 자리에서 탈락) → ② 정상 성능(지연·처리량·자원) → ③ 비정상(`ROBUSTNESS.md` 중 그 층 해당 항목). 앞 단계 탈락 시 뒤 단계 생략.

| 층 | V1 | 대안 후보(직접 시험) | 라이선스·약관 제외만 | 상태 |
|---|---|---|---|---|
| 브로커 | EMQX 5.8.6 | Mosquitto 2.1.2 · NanoMQ 0.25.6 · HiveMQ CE 2026.5 | EMQX 5.9+(BSL), VerneMQ 공식 이미지(EULA) | Mosquitto 조건부(#56), NanoMQ·HiveMQ 실측 탈락(#48) |
| 이상탐지 | Flink 1.20.1 | Flink 2.2.1 SQL · Flink 2.2.1 DataStream CEP · Flink HA(자동 복구) · Kafka Streams · Timeplus Proton · RisingWave 코어(Premium 미사용) · Esper(GPL-2.0) | Materialize(BSL). 직접 짠 Python은 원칙 위반(#53) | Flink 2.2.1 정확도 동일, 나머지 미시험 |
| 수집 | EdgeX 4.0.0(10컨테이너) | Telegraf inputs.modbus · Neuron OSS(Modbus TCP·MQTT 무료 범위) · Node-RED+modbus | Neuron 상용 드라이버 | 미시험 |
| 중계 파이프 | Telegraf ×3 | Telegraf 1개 통합 · Redpanda Connect(Apache 컴포넌트만) | Redpanda Connect 엔터프라이즈 커넥터(RCL) | 미시험 |
| 백본 | Kafka 3.9.0 | Kafka 4.2.x(KRaft) · NATS JetStream · Pulsar · MQTT 단독(재처리 가능 여부 실측) | Redpanda 브로커(BSL) | 미시험 |
| 시계열 저장 | InfluxDB 2.7 | TimescaleDB Apache 에디션 · PostgreSQL+pg_partman · QuestDB · InfluxDB 3 Core(72시간 조회 한도 실측) | TimescaleDB TSL 기능, InfluxDB 3 Enterprise | 미시험 |
| 알람 표시·상태 | Telegraf#3→MQTT→FUXA, 상태 관리 없음 | Vue MQTT over WebSocket 직접 구독 · ISA-18.2 알람 상태(PostgreSQL) | — | 미시험 |
| 운영 감시 | Prometheus+Alertmanager | VictoriaMetrics | — | 미시험(우선순위 낮음) |
| HMI | FUXA 1.3.x | FUXA 1.3.4(보안 버전) | Ignition(상용·Maker 비상업) | 업그레이드 |
| 그래프 DB | Neo4j 5.26 | 유지(사용자 지시). Apache AGE 참고 측정 가능 | Memgraph(BSL), FalkorDB(SSPL), Kuzu(아카이브) | 유지 |

우선순위(가치·위험 순): 이상탐지 자동 복구(V1 최대 약점) → 수집(10컨테이너) → 중계 파이프·알람 경로 → 백본 → 시계열 저장 → 운영 감시.
