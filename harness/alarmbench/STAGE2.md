# 알람 표시·상태(ISA-18.2) 벤치 ② 준비 (EXP-ALM) — 2026-09-29 준비, **미실행**

판정 규칙 `QUESTIONS.md` §1(알람 수명주기 연결 코드는 V1 도 직접 짠 업무 로직이라 허용), 후보 `CANDIDATES.md` §7·패턴 P-ISA, 측정 E10(`STRUCTURE.md`), CQ15·CQ08(`ontology/cq.yaml`).

## 기준선(V1)
V1 은 **알람 상태 관리가 없다**(E10 공백): Telegraf#3 → EMQX → FUXA 는 "최근 알람" 문자열만 표시, `ai-alarm-worker`(`operations/consumer.py`)는 사건 등록만(`manufacturing_incidents`·`manufacturing_events`), 확인·셸빙·복귀 상태 없음. CQ15 칸(`ack_state`·`acknowledged_by`…) 없음(`harness/aibench/cq_eval.py` CQ15). 띄울 기준 부품이 없어 기준선 = "E10 0/12, CQ15 불가".

## 시나리오 L01~L12 (결과 보기 전 고정, `al_stage2.py` 머리 주석)
입력은 V1 alerts 레코드 모양. 발생 → 중복 흡수 → 확인(op-a) → 복귀 → 확인 전 복귀(RTNUN) → 확인(op-b) → 확인 뒤 악화 재알람 → 셸빙 60초(사유) → 셸빙 중 재발생(표시 안 함) → 만료 후 UNACK → 이력 감사. 각 단계 관측 상태를 ISA 이름(NORM·UNACK·ACKED·RTNUN·SHLVD)으로 정규화해 기대와 대조 → **E10 일치율**. 이력에서 **CQ15**(누가·언제 확인) · **CQ08 대응**(누가·언제·왜 셸빙) 답 가능 여부.
**V1 갭(모든 후보 공통):** V1 에는 복귀(RTN) 신호가 없다 — 알람 레코드는 이상일 때만 나온다. 수명주기를 쓰려면 raw 값이 한계 이하로 돌아온 것을 알리는 경로가 필요(연결 코드: raw 구독 또는 Flink 규칙에 복귀 출력 추가). 벤치는 같은 키의 복귀 사건을 직접 보낸다.

## 후보 → 프로파일

| 후보 | 프로파일 | 이미지 | V1 기능 재현 방법 | 갭·주의 |
|---|---|---|---|---|
| **PostgreSQL 상태 테이블 + 트랜잭션 함수 (P1)** | `pgisa` | `postgres:17@sha256:f4c66b82…`(V1 `ai-work-db` 와 같은 이미지, 별도 인스턴스, DB `ar100_work`, **스키마 `isa`**) | `pgisa/isa_pg.sql`: `alarm`(상태)·`alarm_event`(append-only 트리거로 수정·삭제 금지) + `alarm_raise/rtn/ack/shelve/unshelve_expired`, 전이는 `FOR UPDATE` 잠금 안, `pg_notify('alarm_state')` 로 화면 푸시 가능. Alerta `isa_18_2.py` 를 참조 설계 | 연결 코드(허용 범위) ≈170줄 SQL. 셸빙 만료는 주기 호출 필요(연결 코드 또는 pg_cron). **배치 결정(09-29): 업무 DB 와 같은 PostgreSQL, 별도 스키마 `isa`** — 함수는 `SET search_path = isa` 로 고정, 업무 테이블(`manufacturing_*`)과 분리 |
| Alerta 9.1 (#74 관문: alerta-ng 만 제외, Alerta 자체는 직접 시험) | `alerta` | `alerta/alerta-web:9.1.0` + `postgres:17.11` | `ALARM_MODEL='ISA_18_2'`(설정 파일 `alerta/alertad.conf` — 환경변수로는 안 됨), 인증 필수·운전원 계정 2(가입→로그인 토큰), 발생 `POST /alert`, 복귀 = 같은 resource/event 를 severity `OK` 로, 확인·셸빙 `PUT /alert/{id}/action`(셸빙 timeout 60) | **상류 ISA 모델은 셸빙 만료 규칙이 없고 `/management/housekeeping` 호출이 만료 처리** — 주기 호출 필요(연결 코드). 상류 마지막 이미지 2026-03-28 → 유지 위험 기록. 컨테이너 2 |
| Keep 0.54.3 (MIT 코어, `ee/` 미사용) | `keep` | `us-central1-docker.pkg.dev/keephq/keep/keep-api:0.54.3` (Docker Hub·ghcr 아님 — §12-2 [미확인] 해소) | 발생·복귀 = `POST /alerts/event`(status firing/resolved, fingerprint = 알람 키), 확인 = `/alerts/enrich` status acknowledged, 셸빙 ≈ `dismissed`+`dismissUntil`, 이력 = `/alerts/{fp}/audit` | **ISA 상태 없음**: RTNUN(복귀·미확인)·재알람 규칙 없음 → L05b·L08 불일치 예상. `AUTH_TYPE=DB` 로그인·사용자 생성 API 경로 [미검증]. 화면(keep-ui)은 이번 ② 범위 밖 |
| ThingsBoard CE 4.3 알람 | `thingsboard` | `thingsboard/tb-node:4.3.1.6` + `postgres:17.11` (+설치 1회 컨테이너) | REST 알람 생성(`POST /api/alarm`, 같은 타입 활성 알람에 합쳐짐)·ack·clear, 상태 ACTIVE_UNACK/ACTIVE_ACK/CLEARED_UNACK/CLEARED_ACK → UNACK/ACKED/RTNUN/NORM, 두 번째 운전원 = 테넌트 관리자 생성·활성화, 이력 = 알람 댓글(시스템 기록) | **셸빙 없음**(L09~L11 "unsupported"). 데모 계정 기본 비밀번호(LOAD_DEMO) — 운영 시 제거. JVM 무거움. §9 HMI 벤치와 같은 부품 |
| Grafana Alerting · Alertmanager(silence) | — | — | — | 공정 알람 수명주기(확인·RTNUN) 없음 — CANDIDATES P3. 운영 감시(§8) 쪽 통지 계층으로만 의미 → 이번 준비 범위 밖 |
| Vue MQTT/WebSocket 직접 구독(표시) | — | — | — | 표시 경로(P-HMI) — `hmibench` 와 구조 비교에서. 상태 저장은 위 후보 중 하나가 맡음 |

## 공통
- **자원 한도 없음(09-29 결정 I5):** 컨테이너 메모리·CPU 제한을 두지 않는다 — 실제 사용량 자체가 ③ 효율 측정값. 공정성은 같은 호스트에서 벤치 하나씩(각 stage2.sh 가 같은 벤치 동시 기동 거부, rot 스택과는 가드로 분리). JVM 힙 등 제품 설정은 상류 예시·기본값 그대로.

## 실행
```bash
for p in pgisa alerta keep thingsboard; do harness/alarmbench/stage2.sh $p; done
```
산출: `experiments/EXP-ALM/stage2_<profile>.json`(단계별 기대/관측, E10 일치율, CQ15·CQ08 답 가능 여부, 이력 원문), `raw/<profile>_services.log`.
③ 알람→화면 지연 p95(E1)는 표시 경로(HMI)와 묶어 구조 벤치에서, ④ R07(DB 다운 중 상태 변경 fail-closed)은 `pgisa` 에서 `docker stop alarmbench-alarm-db-1` 후 `alarm_ack` 호출이 실패하는지로(준비만).

## 준비 검증(2026-09-29)
- 이미지: 외부 이미지 전부 받음(`experiments/BENCH-PREP/pull_20260929_0258.log`, 실패 0).
- `config -q` 통과, latest 0, 가드 공통(`harness/benchcommon/guard.sh`).
- `isa_pg.sql` 문법·동작, Alerta/Keep/TB API 경로는 **미실행(미검증)** — 공개 소스(alerta v9.1.0 `isa_18_2.py`·`config.py`, keep v0.54.3 `routes/alerts.py`)와 대조해 작성.
