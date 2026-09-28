# EXP-113 — L4 후보: Python 스트림 서비스 (임계치 + Z-Score + CEP 한 프로세스)

- 회전: R1 · 날짜: 2026-09-28
- 질문: 12태그 규모에서 Flink 없이 Python 서비스 하나로 V1 L4 규칙을 같게 낼 수 있는가, 자원·복잡도는 어떤가
- 기준선: EXP-112a (V1 Flink 1.20.1 SQL). 같은 리플레이를 두 쪽이 동시에 소비(입력·시각 동일)
- 교체한 모듈: L4 규칙·CEP (ONNX 잡 제외)
- 후보: `candidates/l4-python/app.py` (155줄), 이미지 `l4bench-l4-python` (python:3.12.8-slim + confluent-kafka 2.6.1, 214MB, 로컬 빌드)
- 라이선스: CPython PSF-2.0, confluent-kafka Apache-2.0, librdkafka BSD-2 `[재확인]` · 유료·키 기능 없음 · SBOM 미작성(NOT DONE)
- 트렌드: 순수 asyncio/상태머신 방식은 "제품"이 아니라 판정 대상 아님. Quix Streams(Apache-2.0)는 이번 구현에 쓰지 않음
- G10: 통과(직접 빌드, python 공식 이미지)
- 의미 대응 (V1 SQL → Python)
  - 01 워터마크 `event_time - 5s`, idle-timeout 5s → 파티션별 최대 ts − 5s, 5초 무수신 파티션 제외
  - 02 임계치(정렬 없는 판정) → 도착 즉시 판정
  - 03 Z-Score: tag 파티션, ROWS 60, n≥30, |z|>3.5, 최근 5 중 3 → 동일(STDDEV_SAMP n−1)
  - 04 CEP `(OVERCURRENT OTHER*? VIB) WITHIN 10s`, SKIP PAST LAST ROW, device 파티션 → 장치별 과전류 대기열, 10초 미만이면 발화 후 대기열 비움
  - 늦은 레코드: Z-Score·CEP에서 폐기 + `exp.l4.dropped.python` 기록
- 사전 판정 기준: FINAL §10 (변경 없음)

## 실행

| run | 결과 | 비고 |
|---|---|---|
| r3 | 후보 결함 | 늦은 레코드를 임계치에서도 버림 → S07 장치 THRESHOLD_USL 3건 누락(V1 대비). `raw/NOTE_r3.md`. 후보 코드만 수정 |
| r4 | 유효 | 사전 점검(Flink 잡 3 RUNNING) 통과, 발행 2,898건 |

## 결과 (r4)

| 지표 | V1 Flink 1.20.1 SQL | Python 후보 | 근거 |
|---|---|---|---|
| 시나리오 정답 S02·S04~S08 | 21/21 | 21/21 | `raw/result_r4_*.json` |
| 알람 전체 일치 (device·type·tag·ts) | 81 | 81, 차이 0 | `raw/alerts_r4_*.jsonl` |
| S07 늦은 이벤트 | CEP 0, 폐기 기록 없음 | CEP 0, 폐기 기록 3/3 | dropped 토픽 |
| M1 CEP 지연 p50 / p95 (n=12) | 5,223 / 5,655 ms | 5,010 / 5,514 ms | 워터마크 5초 포함 |
| M5 메모리 평균 / 최대 | 1,131 / 1,149 MiB | 12 / 20 MiB | `raw/stats_r4.csv` (docker stats, 27샘플) |
| M5 CPU 평균 / 최대 | 17.0 / 36.6 % | 0.4 / 1.0 % | 〃 |
| M6 컨테이너 / 이미지 | 2 / 1.86 GB | 1 / 214 MB | |
| M7 코드·설정 줄 | 185 (SQL 4파일) | 155 | `wc -l` |
| M8 구현 | — | 1회 결함 수정 포함 | |

측정 조건: 원본 V1 스택(29 컨테이너)이 같은 호스트에서 실행 중. 두 후보 모두 같은 조건. 리소스 제한(I5) 미설정.

## 미완료 (판정 전 필요)
- **S09 재시작(G8)**: 미실행. Python 후보는 대기 중 패턴 상태를 저장하지 않으므로 핵심 위험.
- S03 Z-Score 드리프트(가상설비 `noise` 주입) 동등성: 미실행.
- SBOM·LICENSE 당일 확인(G9): 미실행.

## 결정
보류 — S09·G9 결과 후 §10 적용.
