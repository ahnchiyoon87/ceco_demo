# DISP-CMP — IT 발송기: 자체 코드(Python) → Kafka 승인 토픽 + Bento http 프로세서 (2026-09-30)

근거: 설계검증 결과(19_설계검증_결과.md §3) "IT 발송기 — 시험 후 교체: Kafka 승인 토픽 → Bento http 프로세서 → 결과 토픽".

바뀐 구조
- AI 업무 도우미: 요청·승인을 PostgreSQL 에 기록한 **뒤** Kafka `request.approved` 에 요청 ID 만 낸다(연결 재사용). 알리지 못하면 `not_dispatched` 사건을 남기고 "보내지 않음"으로 답한다.
- IT 수집기(Bento) 스트림 `request_dispatch`: 승인 토픽 → (PostgreSQL) 마지막 사건이 approved 인 요청만 `dispatched` 기록 → DMZ 게이트웨이 POST(재시도 없음) → `gateway_accepted/rejected` 기록 + 감사 → Kafka `request.events`·`audit.copy` 사본.
- 발송기 컨테이너(`4_it/dispatcher`)는 지웠다. 계정은 그대로 `dispatcher`(최소 권한).

| 시험 | 기대 | 결과 |
|---|---|---|
| `tests/e2e/dispatch_check.py` ×4 | 수용 사건 순서·게이트웨이 거부 기록(422 PARAMETER_RANGE)·같은 승인 재알림 시 재발송 없음·기록 없는 ID 무시·감사 2줄 | 5/5 ×4회 통과 |
| 승인 → dispatched 지연 | 옛 발송기 폴링 0.2 s 이하 | 연결이 이미 있을 때 6 ms, 새 연결의 첫 전달은 약 1 s(그래서 AI 쪽은 연결을 재사용) |
| `control_ai.sh`(S17·S21·S18·S22) | 모두 통과 | 4/4 통과 |
| `control_base.sh`(S14~S22·MODE·EXP·OPT·AUD·S19) | 모두 통과 | MODE 외 전부 통과. MODE 는 1회 실패: REMOTE_MANUAL 사건은 끝까지 정상(observed OK)이었는데 직후 설비 상태 읽기에서 냉각기 False. 단독 재실행 2회 통과. 원인 미확인(발송 구간 사건·시각은 정상) |

원자료: `raw/dispatch_bento*.json`, `raw/control_ai_bento.jsonl`, `raw/control_bento.json`, `raw/control_mode_*.json`.
