#!/usr/bin/env bash
# BR-03: 구독자만 오프라인(브로커 재시작 없음) 동안 600건 → 재접속 후 수신. offline_queue 모드를 그대로 쓰되 재시작을 건너뛴다.
# 결과 JSON 의 received_after_restart 는 이 시험에서 "재접속 후 수신"을 뜻한다(actions.log 에 no-restart 기록).
#   harness/brokerbench/run_br03.sh <run 접두사> [브로커 목록]
set -uo pipefail
. harness/benchguard.sh   # 09-29 추가: rot-iiot/rot-ai 실행 중이면 거부(FORCE=1 무시). 측정 로직 불변
bench_guard
pre=$1; brokers=${2:-"emqx mosquitto nanomq hivemq"}
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1
B="docker compose -f harness/brokerbench/compose.yml"
C="$B --profile tools run --rm -T client python /repo/harness/brokerbench/mqtt_bench.py --exp EXP-130"
raw=experiments/EXP-130/raw; mkdir -p "$raw"
for b in $brokers; do
  echo "######## $b (BR-03, 재시작 없음)"
  $C --broker "$b" --mode offline_queue --run "${pre}q0" ${RESUB:+--resub} 2>&1 | grep -v Container | tail -1 &
  cp=$!
  for i in $(seq 1 240); do [ -e "$raw/${b}_${pre}q0.ready" ] && break; sleep 0.5; done
  echo "$(date +%s.%N) no-restart $b (BR-03)" >> "$raw/${b}_${pre}q0_actions.log"
  sleep 5; touch "$raw/${b}_${pre}q0.restarted"
  wait $cp
done
