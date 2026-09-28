# 진행 기록

## 2026-09-28 Day 0 §6.1 원본 동결
- 한 일: 실행 중인 원본 V1 작업 트리를 `v1-original`(`def56b1`)로 태그. main·원본 작업 트리 무변경. 실험 브랜치 `exp/stack-rotation-202609`를 `D:\work\study\scada-rotation` worktree로 분리.
- 결과: `harness/V1_INVENTORY.md`(29개 컨테이너 이미지·digest·포트), `harness/V1_FACTS.md`(브리프↔코드 차이, I2~I4 확정, 위험 3건)
- 막힌 것: LiteLLM 프록시 버전 미확인(Q4). 실험 스택 기동 전 원본 설비 주소 고정 문제 해결 필요(V1_FACTS §4-1).

## 2026-09-28 Day 0 §6.2 위생 조치 (v1-baseline 후보, 실행 검증 전)
- 한 일: FUXA·kafka-exporter `latest` → v1-original 실행 이미지 digest로 고정. 컨테이너명(`CN_PREFIX`)·SCADA 네트워크(`SCADA_NETWORK`)·AI 호스트 포트(`AI_PORT_*`)를 변수화(기본값=원본). AI 서비스의 Modbus 주소·설비 API를 환경변수화(`actions.py`, `simulation.py`), Vue 운전원 콘솔 FUXA iframe 주소를 빌드 인자(`VITE_FUXA_URL`)로. 실험 스택 설정 `.env.rotation`(37xxx·38xxx), 격리 검사 `harness/check_isolation.py`.
- 결과: 원본 설정 렌더링 차이 = 이미지 2개 digest 고정 + AI 환경변수 7개(값은 기존 하드코딩과 동일). 격리 검사 실험 설정 누출 0, 원본 설정 누출 58(검사기 정상).
- 막힌 것: 실험 스택 실제 기동·FUXA 동작 확인 전이라 `v1-baseline` 태그 보류. `scripts/*.py` 운영 스크립트 다수가 원본 포트(27018·27080·28000·28180)를 하드코딩 → 실험 스택에 쓰지 말 것.

## 2026-09-28 기준 문서 교체 → AGENT_BRIEF_FINAL
- 한 일: 이전 브리프 폐기, FINAL 단일 기준. EMQX 5.8.6 = EOL(G9 위반, 회전 1 교체 필수), Flink 1.20.1, Kafka 3.9 이미 KRaft를 V1_FACTS에 반영. G10(컨테이너 실행 가능성) 추가: FINAL 후보 29개 전부 통과(`harness/G10_CONTAINER.md`), Docker Desktop 4.87 비용 조건은 Q6.
- 결과: `QUESTIONS.md` 재작성(Q1~Q6), `harness/G10_CONTAINER.md`
- 막힌 것: Q4 LiteLLM 버전, Q5 원본 Flink 잡 재제출, Q6 Docker Desktop 비용 판단

## 2026-09-28 회전 1 · L4 (EXP-110대)
- 한 일: 원본과 분리된 L4 벤치(`harness/l4bench`, V1 Flink 이미지·SQL 그대로, 토픽만 `exp.l4.*`)와 리플레이·판정 도구(`harness/tools/replay.py`, `evaluate.py`), 자원 샘플러(`harness/sample_stats.sh`), S09 조율(`harness/s09.sh`), 정상 측정 스크립트(`harness/run_l4.sh`).
- 결과:
  - EXP-112a V1 Flink 1.20.1 SQL: r1 무효(벤치 슬롯 4 설정 오류), r2 21/21, CEP 지연 p95 5.7s, S07 늦은 이벤트 무기록 폐기.
  - EXP-113 Python: r3 후보 결함(늦은 레코드 임계치 누락), r4 21/21·알람 81건 V1과 완전 일치, 메모리 평균 12 MiB vs Flink 1,131 MiB, CPU 0.4% vs 17%.
  - S09 r5 무효(조율 스크립트 인코딩 오류로 kill 시점 틀림) — 그 과정에서 Python 후보 워터마크 결함 발견(몰아받기 중 과전류 117건 late 폐기).
- 진행 중: EXP-113b(파티션 직접 할당, Flink식 유휴 규칙, 1초 스냅샷 복구) 코드 작성 완료, 빌드·r8 정상 회귀·S09(r9 Python kill / r10 Flink TM kill / r11 JM+TM kill) 미실행.
- 막힌 것: 셸 명령 안전 점검 일시 무응답(2026-09-28 오후)으로 실행 대기.
