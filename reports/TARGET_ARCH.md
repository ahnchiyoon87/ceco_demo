# 목표 구조 기준 (2026-09-29 세션 4 확정)

사용자 요청("객관적으로 정해 달라")에 따른 결정. 이전 V2_DESIGN §0 의 "빼기" 방향보다 이 문서가 우선한다.

## 우선순위 (사용자 지시 09-29, 이 문서의 최상위)
1. **바탕 = 2026 현업 주류 스택.** 칸마다 현업에서 주로 쓰는 제품으로 교체한다(근거: research 12 채택 근거 — 독립 설문·공개 사례와 벤더 홍보를 구분).
2. **판·버전 선택 = 도커 적합성·비용 0·라이선스·지원 기간.** 주류가 유료·BSL 등이면 ① 지원 중인 마지막 무료판 또는 ② 가장 가까운 무료 주류 중 고르고 이유를 적는다.
3. **경량화는 그다음.** 제품을 정한 뒤 설정(힙 등)으로 줄인다. 가볍다는 이유로 비주류 제품을 고르지 않는다.
→ 아래 "칸별 결정" 중 경량 이유로 고른 칸(Mosquitto·Bento 등)은 research 12 결과로 재판정한다.

## 원칙
1. **뼈대 = 참조 설계서 v3**(`유압설비_IoT-SCADA_아키텍처_v3.pdf`, 2026-09-23): 역할·망 경계(OT·DMZ·IT)·길 규칙(데이터 상향 1길, 명령 하향 1길, 알람은 게이트웨이 경유로 OT 에 중계).
   근거: 리서치 06(UNS 참조 구조 — MQTT 허브, Kafka 는 분석용)과 같은 모양. 원본 V1 도 이 뼈대와 대부분 같다(아래 대조).
   v3 는 보이스리가 실제로 구축·실행한 구현이 있다(사용자가 실행 화면을 직접 확인, 09-29). 코드(compose·설정)를 받으면 칸별로 재사용하고,
   라이선스에 걸리는 칸(EMQX 5.9+ BSL, TimescaleDB 압축·연속집계 TSL 등 — 실제 사용 버전·기능은 코드로 확인)만 교체한다. 판정은 우리 조건(설비 7대·배속 600·V1 실측 대비)으로 따로 한다.
2. **부품 = 우리 리서치·실측**: 칸마다 라이선스(BSL·SSPL·TSL·RCL 금지)·지원 기간·무게·실측으로 제품을 고른다. v3 에 적힌 제품명은 예시로 본다.
3. **층을 빼는 대안은 쓰지 않는다**(EdgeX 제거, Kafka→NATS·RisingWave 등). 경량화는 칸마다 가벼운 제품·설정으로 한다.
4. 판정 비교 대상 = 원본 V1 실측(HANDOFF §4). 판정 규칙 = QUESTIONS §1.

## 원본 V1 ↔ v3 대조
| 역할 | v3 | V1 | 상태 |
|---|---|---|---|
| 장치 계층 | EdgeX 3.x + EMQX | EdgeX 4.0 + EMQX 5.8.6 | 같음 |
| MQTT→Kafka | Connect ingest | Telegraf #1 | 역할 같음 |
| 장부 | Kafka KRaft | Kafka 3.9 | 같음 |
| 탐지 | Flink CEP+ONNX | Flink 1.20(임계치·Z-Score·CEP·ONNX) | 같음 |
| 알람→FUXA | cmd-gateway → plant/{a}/alert | Telegraf #3 → EMQX | 같은 모양(망 분리용 정상 경로 — "알람 되돌림"을 결함으로 본 이전 판단 정정) |
| 저장 | Connect sink → TimescaleDB 하나 | Telegraf #2 → InfluxDB, 알람 PostgreSQL | 흩어짐 → 정리 |
| FUXA 읽기 | MQTT 태그 구독 | Modbus 직접 폴링 | 어긋남 → 고침 |
| FUXA 쓰기 | cmd/manual → EdgeX core-command | Modbus 직접 쓰기 | 어긋남 → 고침 |
| 망 | ot-net / it-net, DMZ 3개 | 단일 망 | 빠짐 → 적용 |
| PLC 모드·만료·중복 | soft-plc | 없음(시뮬레이터 인터록 코일만) | 다음 단계(새 기능) |

## 칸별 결정
| 칸 | 결정 | 근거 |
|---|---|---|
| 장치 계층 | EdgeX 4.0.x 유지 | 기능 보존(장치 등록부·명령 API), v3 보다 최신 |
| MQTT 허브 | Mosquitto 2.1.2 (RMQTT 비교 조사 중) | EMQX 5.9+ BSL |
| 커넥터(올림·알람 내림·저장) | Bento 1.21.2 | MIT, JVM 없음, 세션 3 V1 과 결과 동일 실측 |
| 장부 | Kafka 4.3.1 KRaft | V2 실측 통과 |
| 탐지 | Flink 2.2.1 | V2 실측 통과 |
| 저장 | 실측 1회로 결정: ① PostgreSQL+Timescale(Apache 기능만, 압축·연속집계 제외) 하나 ② InfluxDB 2.9.1 + PostgreSQL | TimescaleDB 압축·연속집계는 TSL |
| 화면 | FUXA 1.3.4 — MQTT 구독 + 명령 토픽 | 읽기·쓰기 길 통일(조사: research 11) |
| 명령 | FUXA → cmd/manual → EdgeX core-command → 설비 | 쓰기 길 하나 |
| 감시 | Prometheus + Alertmanager 기본 켬, 경량 설정 | 리서치 07 |
| 망 | ot-net / it-net 분리, DMZ = 커넥터·감시 에이전트 | v3 |
| AI(L7~L9) | 손대지 않음 | 담당 밖 |
| soft-plc(모드·cmdId·만료) | 다음 단계 | V1 에 없던 기능 추가 |

## 확인 대기
- research 11(FUXA MQTT 구독·명령, EdgeX 외부 브로커·core-command MQTT, Mosquitto·RMQTT) 결과
- 저장소 ①·② 실측
