# r17·r18 미실행(무효) — 하니스 결함 (2026-09-28)

- 의도: Flink 2.2.1 SQL 에서 TaskManager kill(r17), JobManager+TaskManager kill(r18).
- 실제: `s09.sh` 가 리플레이 컨테이너에 `FLINK_REST` 를 넘기지 않아, 사전 점검이 내려 둔 1.20.1 JobManager(`flink-jobmanager`)를 조회 → URLError → 리플레이 미시작 → manifest 미생성 → s09.sh 가 kill 하지 않고 중단(안전장치 정상). `replay_r17.out`, `replay_r18.out` 에 오류 기록.
- 재시작 후 잡 상태 파일(`r17_jobs_after.txt`, `r18_jobs_after.txt`)은 kill 이 없었으므로 의미 없음.
- 추가 원인: 실행 스크립트에서 s09.sh 출력을 `>/dev/null` 로 숨겨 즉시 알아채지 못함 → 이후 출력 숨기지 않음.
- 수정: s09.sh 가 `FLINK_REST` 를 리플레이 컨테이너에 전달. 재측정 = r19(TM), r20(JM+TM).
