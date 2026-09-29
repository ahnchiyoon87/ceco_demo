# 구조 비교 판정표 (레이어 재설계) — 결과 보기 전 고정 2026-09-29

> **개정(#57·#66, 결과 보기 전):** 판정 규칙은 `QUESTIONS.md` §1만 따른다(이 파일의 합격 칸은 측정 방법 설명이며, 비교 기준은 현재 기준 버전 — 1회전은 V1). 비교 대상은 기준 버전 대 조립안(HANDOFF §2 축 3: 축 2·4 승자로 경로·중복을 줄인 구조). 아래 §1의 A는 조립 출발점, C는 직접 제작 요소 때문에 본안 제외(기록용). 비정상 상황은 `ROBUSTNESS.md`를 함께 적용.

정본: `docs/research/ARCHITECTURE_SIMPLIFICATION.md` §6·§9·§10, `docs/research/AGENT_BRIEF_FINAL.md` §4.5(CAP)·§13.2.
사용자 지시 우선: Neo4j 유지(검토서 단계 10 제외, 그래프 DB 필수), 판정 규칙은 `QUESTIONS.md` §1. FINAL §3-3 "한 모듈 교체"의 예외인 **구조 비교**로 표시한다.

## 1. 비교 대상 (실측)
| 구조 | 흐름 | V1 대비 제거·통합 |
|---|---|---|
| V1 | 가상설비 → EdgeX(10) → EMQX → Telegraf#1 → Kafka → Flink(규칙·ONNX) → Kafka → Telegraf#2 → InfluxDB / Telegraf#3 → EMQX → FUXA, 워커 → PostgreSQL, Prometheus+AM+exporter+cAdvisor | — |
| A 보수적 | Telegraf 1개(Modbus 폴링) → Kafka → Flink → alarm-core → Mosquitto → FUXA·Vue, 저장 InfluxDB 유지 | EdgeX·EMQX·Telegraf#1·#3 제거, 알람 되돌림 제거 |
| C MQTT 단일 백본 | FUXA 직접(운전) + Telegraf 1개 → Mosquitto → 탐지기(규칙+Z+CEP+ONNX) → advisory(retained) → FUXA·Vue, 저장 PostgreSQL 하나(시계열) + Neo4j(AI) | EdgeX·EMQX·Telegraf×2·Kafka·Flink·InfluxDB·Alertmanager 제거, Prometheus 선택 |
문헌 판정만: B(FUXA 중심, 분석이 HMI에 종속), C2(C 채택 시 E6 재처리 비교로 실측 승격), D(브로커 없음, FUXA MQTT 수신 불가). 탐지기 엔진은 L4 부품 판정(EXP-L4) 결과를 쓴다.

## 2. 기능 보존 (동등성 관문, 전부 통과해야 함)
| # | 항목 | CAP | 시험 | 합격 |
|---|---|---|---|---|
| F01 | 12태그 수집·저장 | 01·05 | S01 정상 3분 | 12태그 전부 저장, 누락 0 |
| F02 | 상·하한/Z-Score/CEP/모델 탐지 | 06 | S02~S08·S13 경로 전체 주입 | 판정이 V1과 같음(EXP-L4 기준) |
| F03 | 공정 알람 표시·확인 | 07 | S23·S24 | FUXA 표시·확인 동작 |
| F04 | advisory 표시·확인 | 07 | S23 | FUXA advisory·Vue 표시 |
| F05 | 이력 조회 72시간 초과 포함 | 05 | 적재 후 7일 범위 조회 | 결과 반환 |
| F06 | 사건 등록·중복 결합 | 08 | 같은 원인 반복 주입 | 사건 1건에 결합 |
| F07 | AI 조사(설비 관계 질의) | 10 | CQ01·CQ02 | V1과 같은 답 |
| F08 | 승인→재검사→정지→read-back | 11·13·14 | S17~S21 | G2~G5 통과 |
| F09 | 조작 이력·감사 | 15 | S14~S22 | G6 통과 |
| F10 | 운영 감시·경보 | 09 | E11 | 컨테이너·탐지기 정지를 둘 다 탐지 |
| F11 | 재처리 | 16 | E6 | 같은 advisory 집합 재현 |
| F12 | 인터록·안전 실패 | 12·18 | S16·S22 | G1·fail-closed |
| F13 | 운전원 직접 조작 | 04 | S14·S15 | C1 동작, C2 대체 경로 명시 |
| F14 | 관측 사실과 AI 추론 분리 | 17 | S25 | 원인 확정 금지 유지 |

## 3. 측정 (E, 검토서 §9) — 시간 값은 QUESTIONS §1 "시간"(#89, 측정 전 개정)
| E | 무엇 | 방법 | 합격(QUESTIONS §1, 기준 버전 대비) |
|---|---|---|---|
| E1 | 알람→화면 지연 | 이상 주입 → FUXA 알람 토픽·Vue 수신 시각, 20회 × 3묶음 | p95 ≤ 기준 버전(+5% 이내는 같음, 3회 이상 중앙값) |
| E2 | 구성 복잡도 | compose 분석 | hop·컨테이너·설정 파일 수 기록(이득 판정용) |
| E3 | 자원 | 정상 운전 3분 docker stats(시점별 합계 중앙값) | 메모리·CPU 합계, 기동 시간 기록 |
| E4 | 브로커 장애 | 브로커 10초 정지 후 재기동 | 운전 화면(FUXA 직접 폴링) 영향 0, 유실·중복 ≤ V1 |
| E5 | 탐지기 장애 | 강제 종료 후 재기동 | 누락 advisory ≤ V1 |
| E6 | 재처리 | 과거 구간 재생(Kafka 오프셋 / DB 재생 / JetStream) | 같은 advisory 집합 |
| E7 | 화면 값 = 이력 값 | 동시각 값 비교 | 허용오차 이내 99% 이상 |
| E8 | CEP 정확도 | EXP-L4 결과 재사용 | V1과 같은 판정 |
| E9 | 제어 안전성 | S18~S21 | 부적합 실행 0, 감사 누락 0 |
| E10 | 알람 수명주기 | 발생→확인→복귀, 셸빙 만료 | 상태도와 100% 일치(V1은 공백 — 개선 항목) |
| E11 | 운영 감시 대체 | 컨테이너 kill, 탐지기 정지 | 둘 다 탐지 |
| E12 | 보안 기본선 | FUXA 보안 버전(1.3.4 이상) 확인 + 인증·접근 제어(MQTT·FUXA·DB·UI) 상태 | 기준 버전 이상 |

## 4. 판정
`QUESTIONS.md` §1 그대로: ① 관문 → ② §2 기능 보존 전부 + 성능(E1·E4·E5·E6·E8)·비정상(`ROBUSTNESS.md`)이 기준 버전보다 나쁘지 않음 → ③ 효율(E2 경로·컨테이너, E3 자원)로 우열 → ④ 참고.
