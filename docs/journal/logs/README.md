# 원본 로그 모음

교재 제작 시 **실제 출력**을 인용할 수 있도록 수집 시점의 원본을 보관합니다.
가공하거나 요약하지 않았습니다.

| 파일 | 내용 |
|---|---|
| `00-pdf-extracted.txt` | 원본 PDF 에서 추출한 전체 텍스트 (`pdftotext -layout`) |
| `01-image-arch-check.txt` | 이미지 arm64 지원 실사 |
| `02-edgex-bootstrap.txt` | EdgeX 기동 로그 (오류 포함) |
| `03-kafka-schema-sample.txt` | Kafka 토픽 실제 메시지 |
| `04-flink-jobs.txt` | Flink 잡 제출 및 상태 |
| `05-model-training.txt` | 오토인코더 학습 + 판별력 자가검증 (실패본/성공본) |
| `06-detection-results.txt` | 시나리오별 탐지 결과 |
| `07-verification-full.txt` | 전 계층 검증 결과 |
| `08-fuxa-control.txt` | FUXA 양방향 제어 실측 |
| `09-clean-boot.txt` | 클린 부팅 전체 로그 |

## 인용 시 주의

- 타임스탬프는 구축 당시(2026-09-16)의 것입니다.
- 포트는 `.env` 의 27000 대역 기준입니다.
- 일부 로그는 `rtk proxy docker logs` 로 요약 없이 받은 원본입니다.
