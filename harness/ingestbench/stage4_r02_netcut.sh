#!/usr/bin/env bash
# R02 수집기↔브로커 네트워크 단절 (ROBUSTNESS R02, 시나리오 S10). 설비 폴링(field)은 그대로, 송신 컨테이너만 uplink 에서 뗀다.
#   harness/ingestbench/stage4_r02_netcut.sh <profile> [단절 초=60] [측정 총 초=240]
#   환경변수: RUN, KEEP, WARM, FORCE (stage2.sh 와 같음)
# 잴 것: 단절 구간 데이터 보관·재전송(유실), 순서, 복구 시간 → experiments/EXP-ING/stage4_r02_<profile>[_<RUN>].json
# 검사기는 영속 세션(--persistent)으로 구독해 검사기 쪽 유실이 섞이지 않게 한다.
# hivemq-edge(수집+브로커 통합)는 Edge 컨테이너 자체가 uplink 에서 떨어지므로 "구독자 쪽 단절 + 브로커 큐"를 재는 셈이다(STAGE2.md).
set -uo pipefail
. harness/ingestbench/lib.sh
bench_guard
P=${1:?profile}; CUT=${2:-60}; TOTAL=${3:-240}
TAG=r02_${P}${RUN:+_$RUN}
OUT=$EXP/stage4_${TAG}.json
[ -e "$OUT" ] && { echo "$OUT 이미 있음 — RUN=<새 ID> 로" >&2; exit 5; }
ing_up "$P" "$TAG"
FF=$RAW/fault_${TAG}.txt; rm -f "$FF"
NET=ingestbench_uplink
harness/sample_stats.sh "$RAW/stats_${TAG}.csv" $((TOTAL + 15)) '^ingestbench-' &
sp=$!
ing_check "$TAG" "$TOTAL" --persistent --fault-kind "netcut-uplink:$EGRESS" --fault-file "/experiments/EXP-ING/raw/fault_${TAG}.txt" \
  --out "/experiments/EXP-ING/stage4_${TAG}.json" &
cp=$!
PRE=$(( (TOTAL - CUT) / 3 )); sleep "$PRE"
ALIASES=$(docker inspect -f "{{json (index .NetworkSettings.Networks \"$NET\").Aliases}}" "$EGRESS" | tr -d '[]"' | tr ',' ' ')
T0=$(date +%s.%N)
docker network disconnect "$NET" "$EGRESS" || echo "disconnect 실패"
sleep "$CUT"
args=""; for al in $ALIASES; do args="$args --alias $al"; done
docker network connect $args "$NET" "$EGRESS" || echo "connect 실패"
T1=$(date +%s.%N)
echo "$T0 $T1 netcut-uplink:$EGRESS" > "$FF"
echo "[r02] cut $EGRESS $T0 → $T1 (aliases: $ALIASES)"
wait $cp; wait $sp
ing_finish "$OUT" "$TAG"
