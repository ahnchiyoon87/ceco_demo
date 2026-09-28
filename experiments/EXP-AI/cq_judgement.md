# CQ 15 판정 (harness/aibench/cq_eval.py, 조회문·조건 결과 전 고정) — 2026-09-29

A = V1 원형 그래프(snap-A) + V1 형식 대응안, C = V2 그래프(snap-C3) + V2 형식 대응안. 업무 DB 공통. 원출력 `cq_A.json`·`cq_C.json`, CQ14 검색 `cq14_search_C.json`.

| CQ | 질문(요약) | A | C | 근거 |
|---|---|---|---|---|
| 01 | VT-101 은 무엇을 측정 | answered | answered(+부품 M-101-BEARING·SHAFT) | 두 팔 설비·측정량·단위, C 는 부품까지 |
| 02 | R-101 소속 설비·센서 | answered(M-101) | answered(M-101·HX-101·HX-102) | |
| 03 | M-101 최신 절차 문서 버전 | answered | answered | MIXER-RESPONSE v2 |
| 04 | 알람 관측값(센서·값·시각·품질) | partial | partial | 알람 원문에 quality 없음 |
| 05 | 원인후보와 근거 | partial(요약문만, 구조화 후보 0) | **answered**(구조화 후보 3 + 인용 + 문서 버전) | |
| 06 | 관측 사실과 AI 추론 분리 | answered | answered | evidence / body 분리 저장 |
| 07 | Agent 실행(모델·프롬프트 버전·도구) | partial | partial | 프롬프트 버전 저장 안 됨 |
| 08 | 누가 언제 승인·반려, 사유 | partial | partial | decision·completed_at 있음, 결정자 칸 없음 |
| 09 | 승인 시점 대 실행 직전 조건 | answered | answered | state_fingerprint·result·started_at |
| 10 | 명령 성공했으나 상태 불변 | answered | answered | result(verified/uncertain) |
| 11 | 인터록 차단 명령(C1/C2/C3) | no | no | 차단 기록·경로 칸 없음(409 는 저장 전 반환) |
| 12 | 근거 문서 없는 원인후보 | answered | answered | 인용 0 건 수 집계 가능(0) |
| 13 | 같은 설비 반복 사건 | answered | answered | correlation_key 집계 |
| 14 | PT-101 인터록이 막는 명령 | no | **partial** | 그래프 관계 없음. C 는 검색 1위 PRESSURE#1 이 "P-101 강제 정지" 답함 |
| 15 | 알람 확인 여부·확인자·시각(ISA-18.2) | no | no | 확인 상태 칸 없음 → 알람 층(ISA-18.2) 과제 |

**합계:** A answered 8 · partial 4 · no 3 / C answered 9 · partial 4 · no 2.
남은 no(CQ11·CQ15)와 partial(CQ04·07·08)은 AI 층이 아니라 업무 DB·알람 수명주기(구조·알람 층 후보, `harness/alarmbench/`)에서 채울 항목이다.
