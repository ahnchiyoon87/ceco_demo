#!/usr/bin/env bash
# 수집 층 ② 기동·기능 + ③ 정상 성능 한 바퀴 (CANDIDATES §2 시험 순서).
#   harness/ingestbench/stage2.sh <profile> [측정 초=120]
#   환경변수: RUN=r2(반복 ID; 없으면 stage2_<profile>.json), KEEP=1(끝나도 안 내림), WARM=20(기동 후 대기 초), FORCE=1(가드 무시)
# 결과: experiments/EXP-ING/stage2_<profile>[_<RUN>].json (+ raw/stats_·images_·downstream_·logs_)
# 3회 중앙값 비교(QUESTIONS §1): RUN=r1, r2, r3 로 세 번.
set -uo pipefail
. harness/ingestbench/lib.sh
bench_guard
P=${1:?profile: edgex telegraf benthos-umh hivemq-edge neuron nodered tbgw streampipes openremote}
DUR=${2:-120}
TAG=${P}${RUN:+_$RUN}
OUT=$EXP/stage2_${TAG}.json
[ -e "$OUT" ] && { echo "$OUT 이미 있음 — RUN=<새 ID> 로" >&2; exit 5; }
ing_up "$P" "$TAG"
harness/sample_stats.sh "$RAW/stats_${TAG}.csv" $((DUR + 15)) '^ingestbench-' &
sp=$!
ing_check "$TAG" "$DUR" --out "/experiments/EXP-ING/stage2_${TAG}.json"
wait $sp
ing_finish "$OUT" "$TAG"
