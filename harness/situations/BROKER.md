# 브로커 상황 목록 (동등성 관문, QUESTIONS.md Q2-0) — 결과 보기 전 고정 2026-09-28

V1 브로커 = EMQX 5.8.6 단일 노드(`emqx/emqx.conf`). 소비자: Telegraf#1(QoS1 영속 세션), FUXA(scada/hmi/latest-alert·scada/alerts/{tag}), Telegraf#3(발행), Prometheus(EMQX 지표 스크레이프).
판정은 결과 기준. 벤치: `harness/brokerbench/`(MQTT 3.1.1, QoS1).

| # | 상황 | V1(EMQX) 처리 | 시험 | 합격 조건 |
|---|---|---|---|---|
| BR-01 | 정상 텔레메트리 QoS1 전달 | 기본 | normal: 12토픽 120건/s × 60s | 유실 0, 중복 0, 지연 p95 Q2-1 경계 |
| BR-02 | 브로커 재시작 중에도 흐름 복구 | 재시작 후 재접속 | live_restart | 유실 ≤ EMQX, 최대 공백 기록 |
| BR-03 | 구독자 오프라인 중 메시지 보존(Telegraf#1 영속 세션) | session_expiry 2h, mqueue 10만 | offline_queue(구독자 오프라인 600건) | 재접속 후 수신 ≥ EMQX |
| BR-04 | 브로커 재시작을 넘어선 오프라인 큐·세션 보존 | V1 설정은 메모리 세션 | offline_queue(중간에 브로커 재시작) | 수신 ≥ EMQX (가점) |
| BR-05 | retained 최신 알람(FUXA 최근 알람) | retain_available | offline_queue retained 확인 | retained 유지 ≥ EMQX |
| BR-06 | WebSocket 구독(브라우저·Vue) | listeners.ws 8083 | ws 20건 왕복 | 20/20 |
| BR-07 | 운영 지표 노출(CAP-09, Prometheus) | EMQX /api/v5/prometheus/stats | 스크레이프 가능한 지표(HTTP 또는 $SYS) 존재 | 연결 수·수신·발신 지표 조회 가능 |
| BR-08 | 룰 엔진·대시보드 | V1은 미사용(Telegraf 가 중계) | — | 범위 밖(기록만) |
| BR-09 | 클러스터 | V1 단일 노드 | — | 범위 밖 |
