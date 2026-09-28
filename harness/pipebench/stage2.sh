#!/usr/bin/env bash
# 중계 파이프 ② 기동·기능 + ③ 정상 성능 한 바퀴 (CANDIDATES §4 시험 순서).
#   harness/pipebench/stage2.sh <profile> [발생 초=120]
#   환경변수: RUN(반복 ID), KAFKA_IMAGE(기본 apache/kafka:3.9.0 = V1; Kafka 4.x 소비 확인(#17570)은 apache/kafka:4.3.1),
#             ALERT_RATE(초당 알람, 기본 2), KEEP=1, WARM=15, FORCE=1
# 결과: experiments/EXP-PIPE/stage2_<profile>[_k<kafka버전>][_<RUN>].json (+ raw/stats_·images_·logs_)
set -uo pipefail
. harness/pipebench/lib.sh
bench_guard
DUR=${2:-120}
pipe_up "${1:?profile: $PIPE_ALL}" ""
OUT=$EXP/stage2_${TAG}.json
[ -e "$OUT" ] && { echo "$OUT 이미 있음 — RUN=<새 ID> 로" >&2; exit 5; }
harness/sample_stats.sh "$RAW/stats_${TAG}.csv" $((DUR + 30)) '^pipebench-' &
sp=$!
pipe_check "/experiments/EXP-PIPE/stage2_${TAG}.json" "$DUR"
wait $sp
pipe_finish "$OUT"
