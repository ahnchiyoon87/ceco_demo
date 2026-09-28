# EXP-112a — L4 기준선: V1 Flink 1.20.1 SQL MATCH_RECOGNIZE (그대로)

- 회전: R1 · 날짜: 2026-09-28
- 질문: V1 L4 규칙·CEP 잡이 S02·S04~S08 리플레이에서 어떻게 동작하는가 (EXP-111·112·113 비교 기준)
- 기준선: `v1-original` SQL (`flink/sql/01~04`), 토픽 이름만 `exp.l4.*`로 치환 (`harness/l4bench/prepare.py`)
- 교체한 모듈: 없음 (기준선)
- 후보 버전·이미지: `iiot/flink-onnx:1.0` (Flink 1.20.1, commit cb1e7b5, 로컬 빌드 → digest 없음), `apache/kafka:3.9.0`
- 라이선스: Flink Apache-2.0, Kafka Apache-2.0 (ASF) — LICENSE 파일 당일 확인 미실시 `[재확인]`
- 트렌드: Flink 주류(2.2.1 2026-05-15, 2.1.3 2026-06-14 릴리스, FINAL §11.1). 1.20.1 자체는 구 메이저
- 고정 조건:
  - 벤치: `harness/l4bench/compose.yml` (프로젝트 `l4bench`, 원본 V1과 네트워크·포트 비공유)
  - Flink: JM 800m / TM 1600m / 슬롯 8 / 병렬도 2 (V1은 JM 1600m / TM 4608m. 슬롯·병렬도·SQL 동일)
  - Kafka: V1과 같은 KRaft 설정, 힙 384m, `exp.l4.raw` 6파티션(V1 동일), 키=tag
  - 리플레이: `harness/tools/replay.py`, seed 20260928, 케이스당 3회, 배경값 합성(plant.yaml 규격 기반)
  - 리소스 제한(I5): 미설정 — 미서명
- 사전 판정 기준: FINAL §10 (변경 없음)

## 실행

| run | 결과 | 비고 |
|---|---|---|
| r1 | **무효** | 벤치 슬롯 4개 설정 오류 → CEP 잡 슬롯 부족 RESTARTING. `raw/INVALID_r1.md` |
| r2 | 유효 | 리플레이 전 사전 점검(잡 3개 RUNNING) 통과 후 발행 2,898건, 장치 24 |

## 결과 (r2, `raw/result_r2.json`)

| 시나리오 | 기대 | 결과 |
|---|---|---|
| S02 TT-101 상한 | THRESHOLD_USL ≥1 | 3/3 PASS |
| S04 IT-102↑ → 6초 뒤 VT-101↑ (사이에 정상 IT·VT 이벤트) | CEP 1 | 3/3 PASS |
| S05 역순 | CEP 0 | 3/3 PASS |
| S06a 9.5초 | CEP 1 | 3/3 PASS |
| S06b 10.5초 | CEP 0 | 3/3 PASS |
| S07 진동 레코드 8초 늦게 도착(워터마크 5초 초과) | 정책 명시 + 그대로 동작 | CEP 0, **폐기 기록 없음**. 정책 = 워터마크 뒤 레코드 무기록 폐기(Flink SQL 기본 동작) |
| S08a 전 레코드 2회 발행 | CEP 1 | 3/3 PASS |
| S08b IT-102 배경 3점 누락 | CEP 1 + 누락 기록 | CEP 3/3 PASS. 누락 기록은 L4 규칙 잡 범위 밖 → 미판정 (V1 raw `quality`는 항상 GOOD) |

- 정답: 21/21 (S07 기록 3건 제외)
- M1 CEP 탐지 지연 (진동 주입 emit → 알람 Kafka CreateTime, n=12): p50 5,309 ms · p95 5,697 ms · max 5,781 ms. 워터마크 5초 대기가 대부분
- M5 CPU·메모리: NOT MEASURED (이번 실행에 샘플링 없음)
- M6: 컨테이너 2 (JobManager, TaskManager) — L4 모듈만
- M7: SQL 4파일 (01 61줄 · 02 28줄 · 03 52줄 · 04 44줄 = 185줄, 주석 포함)

## 결정
기준선. 판정 없음.

## 한계
- 배경값이 합성이다. 실제 공정 노이즈(SKAB)는 회전 2 시나리오에서 추가.
- 벤치 메모리가 V1보다 작다. 정확도 판정에는 영향 없음으로 보나, M1은 V1 원본 환경 값이 아니다.
- S07 판정은 "폐기+기록" 요건 기준으로 V1 미충족 소지 → cep-verdict 에서 후보와 함께 다룬다.
