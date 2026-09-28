# r1 무효 (2026-09-28)
벤치 설정 오류: TaskManager 슬롯 4개(V1은 8개) → SQL 잡 3개 × 병렬도 2 = 6 슬롯 부족.
CEP 잡이 NoResourceAvailableException 으로 RESTARTING 반복 → CEP 알람 0건.
V1 결함 아님. 결과 파일은 보존만 하고 판정에 쓰지 않는다. 재측정 = r2 (슬롯 8, 리플레이 사전 점검 추가).
