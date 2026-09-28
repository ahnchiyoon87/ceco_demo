#!/usr/bin/env bash
# Mosquitto 2.1.2 조건부 채택(#56)의 미검증 조건 — 기준 버전 EMQX 5.8.6 도 같은 스크립트로 먼저 잰다.
#   harness/brokerbench/stage4_mosq.sh <test> [broker=mosquitto]
#     netcut     : S10/R02 네트워크 단절 60초. SIDE=sub(기본, 구독자 컨테이너 분리) | pub(발행자 분리). 120건/s × 150 s
#     overload   : R08 과부하 10배. 1200건/s × 600 s, 구독자 1 → 유실·지연 p95·적체 해소
#     queuelimit : 큐 한도. 구독자 오프라인 중 1200건/s × 100 s(=12만 > 큐 10만) → 재접속 후 받은 수·버린 구간·메모리 최대
#     slowsub    : 느린 구독자. 120건/s × 300 s, 빠른 구독자 + 느린 구독자(12 ms/건 ≈ 83건/s) → 빠른 쪽 영향·느린 쪽 유실·브로커 메모리
#     longrun    : R09 장시간. 120건/s × 3600 s → 유실 0, 메모리 증가율(MiB/h)
#   환경변수: RUN(기본 a), FORCE=1, KEEP=1, SIDE
# 결과: experiments/EXP-130/stage4_<test>_<broker>_<RUN>.json (+ raw/ 역할별 파일·stats·events)
set -uo pipefail
. harness/benchguard.sh
bench_guard
. harness/brokerbench/brokers.sh
T=${1:?netcut|overload|queuelimit|slowsub|longrun}; b=${2:-mosquitto}; RUN=${RUN:-a}; SIDE=${SIDE:-sub}
raw=experiments/EXP-130/raw; mkdir -p "$raw"
EV=$raw/stage4_${T}_${b}_${RUN}_events.txt; rm -f "$EV"
NET=brokerbench_default
ev() { echo "$(date +%s.%N) $*" >> "$EV"; }
$BB --profile tools build -q client
$BB --profile '*' stop >/dev/null 2>&1
bb_up "$b"
R="$BB --profile tools run -d $BENV"
S4="python /repo/harness/brokerbench/stage4.py --broker $b --test $T --run $RUN"
n() { echo "bb4-${T}-${b}-${RUN}-$1"; }
for x in pub sub-main sub-fast sub-slow; do docker rm -f "$(n $x)" >/dev/null 2>&1; done
case "$T" in
  netcut)     PR=120; PD=150; SUBS="main:0"; SD=$((PD + 120)) ;;
  overload)   PR=1200; PD=600; SUBS="main:0"; SD=$((PD + 180)) ;;
  queuelimit) PR=1200; PD=100; SUBS="main:0"; SD=$((PD + 300)) ;;
  slowsub)    PR=120; PD=300; SUBS="fast:0 slow:12"; SD=$((PD + 300)) ;;
  longrun)    PR=120; PD=3600; SUBS="main:0"; SD=$((PD + 60)) ;;
  *) echo "test?" >&2; exit 2 ;;
esac
harness/sample_stats.sh "$raw/stats4_${T}_${b}_${RUN}.csv" $((SD + 20)) "$STATS" &
sp=$!
for s in $SUBS; do
  nm=${s%%:*}; slow=${s##*:}
  extra=""; [ "$T" = queuelimit ] && extra="--offline-after 5 --online-at $((PD + 20))"
  $R --name "$(n sub-$nm)" client $S4 --role sub --name "$nm" --slow-ms "$slow" --duration "$SD" $extra >/dev/null
done
sleep 5
$R --name "$(n pub)" client $S4 --role pub --rate "$PR" --duration "$PD" --start-delay 3 >/dev/null
ev "start pub"
if [ "$T" = netcut ]; then
  sleep 25
  tgt=$(n pub); [ "$SIDE" = sub ] && tgt=$(n sub-main)
  ev "cut $SIDE"; docker network disconnect "$NET" "$tgt"
  sleep 60
  docker network connect "$NET" "$tgt"; ev "reconnect $SIDE"
fi
docker wait "$(n pub)" >/dev/null; ev "pub done"
for s in $SUBS; do docker wait "$(n sub-${s%%:*})" >/dev/null; done
wait $sp
for x in pub $(for s in $SUBS; do echo sub-${s%%:*}; done); do docker logs "$(n $x)" > "$raw/stage4_${T}_${b}_${RUN}_${x}.log" 2>&1; docker rm "$(n $x)" >/dev/null; done
$BB --profile tools run --rm -T client $S4 --role analyze --stats "/experiments/EXP-130/raw/stats4_${T}_${b}_${RUN}.csv" 2>&1 | grep -v Container | tail -1
[ "${KEEP:-0}" = 1 ] || bb_down "$b"
