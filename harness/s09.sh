#!/usr/bin/env bash
# S09: 패턴 진행 중 처리기 kill → 재시작. 과전류 주입(t0) 후 3초에 kill, 8초에 start. 진동은 t0+6s(처리기 다운 중 도착).
#   harness/s09.sh <EXP> <run> "<kill 대상 컨테이너들>" [replay 추가 인자...]
set -uo pipefail
exp=$1; run=$2; targets=$3; shift 3
export MSYS_NO_PATHCONV=1
B="docker compose -f harness/l4bench/compose.yml"
man="experiments/$exp/raw/replay_${run}_manifest.json"
# 실행 ID 재사용 금지: 옛 manifest 의 t0 로 kill 시점을 잡으면 시험이 무효가 된다
[ -e "$man" ] && { echo "실행 ID $run 은 $exp 에서 이미 쓰였다 — 새 ID 로 실행"; exit 1; }
mkdir -p "experiments/$exp/raw"
$B --profile tools run --rm -T -e FLINK_REST="${FLINK_REST:-http://flink-jobmanager:8081}" tools python /repo/harness/tools/replay.py --exp "$exp" --run "$run" --cases S09 "$@" \
  > "experiments/$exp/raw/replay_${run}.out" 2>&1 &
rp=$!
for i in $(seq 1 480); do [ -s "$man" ] && break; sleep 0.5; done   # 240 s: 도구 컨테이너가 kafka-init 을 다시 띄우면 60 s 를 넘김(#105, R05 kill 미실행 무효)
[ -s "$man" ] || { echo "manifest 없음 — 리플레이 시작 실패"; cat "experiments/$exp/raw/replay_${run}.out"; exit 1; }
t0=$(PYTHONUTF8=1 python -c "import json;print(json.load(open('$man',encoding='utf-8'))['t0_event_ns']/1e9)")
# t0 를 못 얻으면 kill 하지 않는다 (r5: 인코딩 오류로 t0 가 비어 kill 이 즉시 실행돼 무효)
case "$t0" in ''|*[!0-9.]*) echo "t0 읽기 실패('$t0') — kill 하지 않고 중단"; wait $rp; exit 1;; esac
log="experiments/$exp/raw/s09_${run}_actions.log"
wait_until(){ python -c "import time;d=$1-time.time();time.sleep(max(0,d))"; }
ka=${KILL_AT:-3}; sa=${START_AT:-8}   # 과전류 주입(t0) 기준 초. 진동은 t0+6
echo "timing kill=+${ka}s start=+${sa}s (vib=+6s)" | tee -a "$log"
wait_until "$t0+$ka"; echo "$(date +%s.%N) kill $targets" | tee -a "$log"; docker kill $targets >> "$log" 2>&1
wait_until "$t0+$sa"; echo "$(date +%s.%N) start $targets" | tee -a "$log"; docker start $targets >> "$log" 2>&1
wait $rp; tail -1 "experiments/$exp/raw/replay_${run}.out"
