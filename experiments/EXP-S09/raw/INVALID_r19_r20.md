# r19·r20 미실행(무효) — Docker 엔진 장애 (2026-09-28)

- 의도: Flink 2.2.1 SQL 에서 TaskManager kill(r19), JobManager+TaskManager kill(r20).
- 실제: 두 실행 모두 리플레이 컨테이너 기동 시 Docker Desktop 엔진이 `500 Internal Server Error`(API `_ping`) 반환 → manifest 미생성 → s09.sh 가 kill 하지 않고 중단, 판정 없음.
- 관측(Docker 미사용 진단): 호스트 여유 RAM 0.5 GB / 15.7 GB, `vmmemWSL` 약 3.8 GB, `docker version` 도 500 응답.
- 재측정은 Docker 복구 후 새 ID 로.
