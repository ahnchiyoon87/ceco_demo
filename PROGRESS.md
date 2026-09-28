# 진행 기록

## 2026-09-28 Day 0 §6.1 원본 동결
- 한 일: 실행 중인 원본 V1 작업 트리를 `v1-original`(`def56b1`)로 태그. main·원본 작업 트리 무변경. 실험 브랜치 `exp/stack-rotation-202609`를 `D:\work\study\scada-rotation` worktree로 분리.
- 결과: `harness/V1_INVENTORY.md`(29개 컨테이너 이미지·digest·포트), `harness/V1_FACTS.md`(브리프↔코드 차이, I2~I4 확정, 위험 3건)
- 막힌 것: LiteLLM 프록시 버전 미확인(Q4). 실험 스택 기동 전 원본 설비 주소 고정 문제 해결 필요(V1_FACTS §4-1).

## 2026-09-28 Day 0 §6.2 위생 조치 (v1-baseline 후보, 실행 검증 전)
- 한 일: FUXA·kafka-exporter `latest` → v1-original 실행 이미지 digest로 고정. 컨테이너명(`CN_PREFIX`)·SCADA 네트워크(`SCADA_NETWORK`)·AI 호스트 포트(`AI_PORT_*`)를 변수화(기본값=원본). AI 서비스의 Modbus 주소·설비 API를 환경변수화(`actions.py`, `simulation.py`), Vue 운전원 콘솔 FUXA iframe 주소를 빌드 인자(`VITE_FUXA_URL`)로. 실험 스택 설정 `.env.rotation`(37xxx·38xxx), 격리 검사 `harness/check_isolation.py`.
- 결과: 원본 설정 렌더링 차이 = 이미지 2개 digest 고정 + AI 환경변수 7개(값은 기존 하드코딩과 동일). 격리 검사 실험 설정 누출 0, 원본 설정 누출 58(검사기 정상).
- 막힌 것: 실험 스택 실제 기동·FUXA 동작 확인 전이라 `v1-baseline` 태그 보류. `scripts/*.py` 운영 스크립트 다수가 원본 포트(27018·27080·28000·28180)를 하드코딩 → 실험 스택에 쓰지 말 것.
