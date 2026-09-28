#!/usr/bin/env bash
# R11 설비 통신 끊김 (ROBUSTNESS R11, fault dropout). 수집기가 결측을 어떻게 표시하는지, 거짓 값(동결·센티널)을 내보내는지, 복구 시간.
#   harness/ingestbench/stage4_r11_modbus.sh <profile> [mode=pause|fieldcut|dropout] [구간 초=30] [측정 총 초=180]
#     pause    : 시뮬레이터 컨테이너 docker pause (Modbus TCP 는 붙어 있으나 응답 없음 → 타임아웃)
#     fieldcut : 시뮬레이터를 field 네트워크에서 분리(연결 끊김 → 재접속)
#     dropout  : 시뮬레이터 고장 주입 API(POST /fault dropout) — TT-101 만 센티널(-999999) 값으로 바뀜(V1 Telegraf#1 이 버리는 값)
#   환경변수: RUN, KEEP, WARM, FORCE
# 결과: experiments/EXP-ING/stage4_r11_<mode>_<profile>[_<RUN>].json
set -uo pipefail
. harness/ingestbench/lib.sh
bench_guard
P=${1:?profile}; MODE=${2:-pause}; SEC=${3:-30}; TOTAL=${4:-180}
case "$MODE" in pause|fieldcut|dropout) ;; *) echo "mode: pause|fieldcut|dropout" >&2; exit 2;; esac
TAG=r11_${MODE}_${P}${RUN:+_$RUN}
OUT=$EXP/stage4_${TAG}.json
[ -e "$OUT" ] && { echo "$OUT 이미 있음 — RUN=<새 ID> 로" >&2; exit 5; }
ing_up "$P" "$TAG"
FF=$RAW/fault_${TAG}.txt; rm -f "$FF"
SIM=ingestbench-plant-simulator-1; NET=ingestbench_field
harness/sample_stats.sh "$RAW/stats_${TAG}.csv" $((TOTAL + 15)) '^ingestbench-' &
sp=$!
ing_check "$TAG" "$TOTAL" --persistent --fault-kind "r11-$MODE" --fault-file "/experiments/EXP-ING/raw/fault_${TAG}.txt" \
  --out "/experiments/EXP-ING/stage4_${TAG}.json" &
cp=$!
sleep $(( (TOTAL - SEC) / 3 ))
T0=$(date +%s.%N)
case "$MODE" in
  pause)    docker pause "$SIM"; sleep "$SEC"; docker unpause "$SIM" ;;
  fieldcut) ALIASES=$(docker inspect -f "{{json (index .NetworkSettings.Networks \"$NET\").Aliases}}" "$SIM" | tr -d '[]"' | tr ',' ' ')
            docker network disconnect "$NET" "$SIM"; sleep "$SEC"
            args=""; for al in $ALIASES; do args="$args --alias $al"; done
            docker network connect $args "$NET" "$SIM" ;;
  dropout)  $DC --profile tools run --rm -T client python -c "import json,urllib.request as u;r=u.Request('http://plant-simulator:8080/fault',data=json.dumps({'scenario':'dropout','duration_s':$SEC}).encode(),headers={'Content-Type':'application/json'});print(u.urlopen(r).read().decode())"
            sleep "$SEC" ;;
esac
T1=$(date +%s.%N)
echo "$T0 $T1 r11-$MODE" > "$FF"
echo "[r11] $MODE $T0 → $T1"
wait $cp; wait $sp
ing_finish "$OUT" "$TAG"
