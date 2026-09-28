#!/usr/bin/env bash
# 회전 1 브로커 후보 ②③ 한 바퀴 — 기존 측정 스크립트(mqtt_bench.py·br07.py)를 그대로 쓴다(EXP-130 과 같은 조건).
#   harness/brokerbench/stage2_new.sh <run 접두사> [브로커 목록(기본 전체 신규 후보)]
#   환경변수: FORCE=1(가드 무시), KEEP=1(끝나도 안 내림)
# 순서(브로커마다, 한 번에 하나만 띄움): 기동·접속 대기 → normal(BR-01, 자원 기록) → live_restart(BR-02) →
#   offline_queue+재시작(BR-04·05) → offline_queue 재시작 없음(BR-03) → ws(BR-06) → br07(BR-07) → 내림
# 결과: experiments/EXP-130/raw/<broker>_<mode>_<run>.json, stats_<broker>_<pre>.csv, br07_<pre>_<broker>.json
# 3회 중앙값: 접두사를 바꿔 세 번(b1, b2, b3). 앞 단계 실패(기동·BR-01 유실) 시 뒤는 생략하고 다음 브로커로.
set -uo pipefail
. harness/benchguard.sh
bench_guard
. harness/brokerbench/brokers.sh
pre=${1:?run 접두사}; list=${2:-$BB_NEW}
raw=experiments/EXP-130/raw; mkdir -p "$raw"
$BB --profile tools build -q client
for b in $list; do
  echo "######## $b ($(date +%T))"
  $BB --profile '*' stop >/dev/null 2>&1          # 한 번에 하나(측정 완료 4종 포함 모두 멈춤)
  bb_up "$b" || continue
  C="$BB --profile tools run --rm -T $BENV client python /repo/harness/brokerbench/mqtt_bench.py --exp EXP-130"
  harness/sample_stats.sh "$raw/stats_${b}_${pre}.csv" 90 "$STATS" &
  sp=$!
  $C --broker "$b" --mode normal --run "${pre}n" 2>&1 | grep -v Container | tail -1
  wait $sp
  lost=$(python -c "import json;print(json.load(open('$raw/${b}_normal_${pre}n.json'))['lost'])" 2>/dev/null || echo X)
  if [ "$lost" != 0 ]; then echo "[broker] $b BR-01 유실 $lost → 뒤 단계 생략(② 탈락 후보)"; [ "${KEEP:-0}" = 1 ] || bb_down "$b"; continue; fi
  ( sleep 22; echo "$(date +%s.%N) restart $b" >> "$raw/${b}_${pre}r_actions.log"; docker restart -t 10 "brokerbench-$b-1" >> "$raw/${b}_${pre}r_actions.log" 2>&1 ) &
  $C --broker "$b" --mode live_restart --run "${pre}r" 2>&1 | grep -v Container | tail -1
  wait
  $BB --profile tools run --rm -T $BENV client python /repo/harness/brokerbench/wait_mqtt.py --broker "$b" --timeout "$READY_S" >/dev/null
  $C --broker "$b" --mode offline_queue --run "${pre}q" 2>&1 | grep -v Container | tail -1 &
  cp=$!
  for i in $(seq 1 240); do [ -e "$raw/${b}_${pre}q.ready" ] && break; sleep 0.5; done
  echo "$(date +%s.%N) restart $b" >> "$raw/${b}_${pre}q_actions.log"
  docker restart -t 10 "brokerbench-$b-1" >> "$raw/${b}_${pre}q_actions.log" 2>&1
  $BB --profile tools run --rm -T $BENV client python /repo/harness/brokerbench/wait_mqtt.py --broker "$b" --timeout "$READY_S" >/dev/null
  sleep 5; touch "$raw/${b}_${pre}q.restarted"
  wait $cp
  $C --broker "$b" --mode offline_queue --run "${pre}q0" 2>&1 | grep -v Container | tail -1 &
  cp=$!
  for i in $(seq 1 240); do [ -e "$raw/${b}_${pre}q0.ready" ] && break; sleep 0.5; done
  echo "$(date +%s.%N) no-restart $b (BR-03)" >> "$raw/${b}_${pre}q0_actions.log"
  sleep 5; touch "$raw/${b}_${pre}q0.restarted"
  wait $cp
  $C --broker "$b" --mode ws --run "${pre}w" 2>&1 | grep -v Container | tail -1
  $BB --profile tools run --rm -T client python /repo/harness/brokerbench/br07.py --exp EXP-130 --run "${pre}_${b}" --brokers "$b" 2>&1 | grep -v Container | tail -1
  bench_image_sizes "$raw/images_${b}.json" $IMAGES
  $BB ${PROFILE:+--profile $PROFILE} logs --no-color $SVC > "$raw/logs_${b}_${pre}.txt" 2>&1
  [ "${KEEP:-0}" = 1 ] || bb_down "$b"
done
