# 구축 기록 (Build Journal)

PDF 아키텍처 문서 한 편에서 출발해 실제로 동작하는 IIoT/SCADA 파이프라인에
도달하기까지의 전 과정을 시간 순으로 남긴 기록입니다. **교재 제작을 위한 1차 자료**로
작성되었으므로, 성공한 경로뿐 아니라 **막힌 지점과 그것을 어떻게 진단했는지**를
함께 담았습니다.

## 구성

| 문서 | 내용 | 교재 활용 |
|---|---|---|
| [00-method.md](00-method.md) | 작업 방법론 — 왜 이 순서로 했는가 | 강의 도입부 |
| [01-analysis.md](01-analysis.md) | PDF 분석과 사전 기술 실사 | 1차시: 아키텍처 검토 |
| [02-tier1-edge.md](02-tier1-edge.md) | 현장 에지 — 물리모델·Modbus·EdgeX | 2~3차시 |
| [03-tier2-backbone.md](03-tier2-backbone.md) | 수집·백본 — EMQX·Kafka·Telegraf | 4차시 |
| [04-tier3-stream.md](04-tier3-stream.md) | 스트림 처리 — Flink SQL·CEP | 5~6차시 |
| [05-tier3-ml.md](05-tier3-ml.md) | ML — Autoencoder·ONNX 임베디드 서빙 | 7~8차시 |
| [06-tier4-scada.md](06-tier4-scada.md) | 저장·관제 — InfluxDB·Grafana·FUXA | 9~10차시 |
| [07-troubleshooting.md](07-troubleshooting.md) | 장애 진단 사례 모음 (명령·출력 포함) | 실습 문제 은행 |
| [08-decisions.md](08-decisions.md) | 의사결정 기록 (ADR) | 토론 주제 |
| [09-metrics.md](09-metrics.md) | 실측 수치 전체 | 평가 기준 |
| [10-config-reference.md](10-config-reference.md) | 설정 파일 레퍼런스 (왜 이 값인가) | 실습 자료 |
| [11-teaching-guide.md](11-teaching-guide.md) | 교재 구성 제안 (차시·평가·환경) | 강의 설계 |
| [logs/](logs/) | 원본 로그 모음 (가공 없음) | 인용 자료 |

## 이 기록의 원칙

1. **실제 명령과 실제 출력만** 싣습니다. 재구성하거나 다듬지 않았습니다.
2. **틀린 가설도 남깁니다.** 무엇을 잘못 짚었고 어떤 증거로 바로잡았는지가
   교육적으로 가장 가치 있는 부분입니다.
3. **왜 그 방법으로 확인했는지**를 함께 적습니다. 결론보다 검증 방법이 재사용됩니다.
