# 진행 기록

## 2026-09-28 Day 0 §6.1 원본 동결
- 한 일: 실행 중인 원본 V1 작업 트리를 `v1-original`(`def56b1`)로 태그. main·원본 작업 트리 무변경. 실험 브랜치 `exp/stack-rotation-202609`를 `D:\work\study\scada-rotation` worktree로 분리.
- 결과: `harness/V1_INVENTORY.md`(29개 컨테이너 이미지·digest·포트), `harness/V1_FACTS.md`(브리프↔코드 차이, I2~I4 확정, 위험 3건)
- 막힌 것: LiteLLM 프록시 버전 미확인(Q4). 실험 스택 기동 전 원본 설비 주소 고정 문제 해결 필요(V1_FACTS §4-1).
