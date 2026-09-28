#!/usr/bin/env bash
# 브로커 비교 한 바퀴: 브로커마다 normal(자원 기록) → live_restart → offline_queue → ws.
#   harness/brokerbench/run.sh <run 접두사> [브로커 목록]
set -uo pipefail
. harness/benchguard.sh   # 09-29 추가: rot-iiot/rot-ai 실행 중이면 거부(FORCE=1 무시). 측정 로직 불변
bench_guard
pre=$1; brokers=${2:-"emqx mosquitto nanomq hivemq"}
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1
B="docker compose -f harness/brokerbench/compose.yml"
C="$B --profile tools run --rm -T client python /repo/harness/brokerbench/mqtt_bench.py --exp EXP-130"
raw=experiments/EXP-130/raw; mkdir -p "$raw"
for b in $brokers; do
  echo "######## $b"
  harness/sample_stats.sh "$raw/stats_${b}_${pre}.csv" 90 "brokerbench-$b-1" &
  sp=$!
  $C --broker "$b" --mode normal --run "${pre}n" 2>&1 | grep -v Container | tail -1
  wait $sp
  ( sleep 22; echo "$(date +%s.%N) restart $b" >> "$raw/${b}_${pre}r_actions.log"; docker restart -t 10 "brokerbench-$b-1" >> "$raw/${b}_${pre}r_actions.log" 2>&1 ) &
  $C --broker "$b" --mode live_restart --run "${pre}r" 2>&1 | grep -v Container | tail -1
  wait
  sleep 5
  $C --broker "$b" --mode offline_queue --run "${pre}q" 2>&1 | grep -v Container | tail -1 &
  cp=$!
  for i in $(seq 1 240); do [ -e "$raw/${b}_${pre}q.ready" ] && break; sleep 0.5; done
  echo "$(date +%s.%N) restart $b" >> "$raw/${b}_${pre}q_actions.log"
  docker restart -t 10 "brokerbench-$b-1" >> "$raw/${b}_${pre}q_actions.log" 2>&1
  for i in $(seq 1 120); do docker exec "brokerbench-$b-1" true 2>/dev/null && break; sleep 0.5; done
  sleep 5; touch "$raw/${b}_${pre}q.restarted"
  wait $cp
  $C --broker "$b" --mode ws --run "${pre}w" 2>&1 | grep -v Container | tail -1
done
