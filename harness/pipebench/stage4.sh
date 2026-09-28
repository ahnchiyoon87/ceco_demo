#!/usr/bin/env bash
# 중계 파이프 ④ 비정상 (ROBUSTNESS R01·R03·R06·R08) — 09-29 지시. 기준 v1 을 같은 스크립트로 먼저.
#   harness/pipebench/stage4.sh <test> <profile>
#     r01 : 브로커(EMQX, P-C 프로파일은 RMQTT/TBMQ) docker stop → 30초 → start. 발생 240 s(사건 60 s 지점). 입력 A 발행기는 paho 내부 큐로 보관(수집기 저장 후 전달 대역)
#     r03 : Kafka docker restart. 발생 240 s(60 s 지점)
#     r06 : InfluxDB docker stop → 300초 → start. 발생 480 s(60 s 지점) — 쓰기 버퍼(다운 중 알람이 복구 후 적재되는가)·다른 중계 영향
#     r08 : 과부하 — 입력 A 를 정상의 10배(EdgeX 이벤트 10/s = reading 120/s) 600 s. 알람 지연 p95·유실·적체 해소
#   환경변수: RUN, KAFKA_IMAGE, ALERT_RATE, SETTLE(발생 뒤 수집 대기, 기본 120), KEEP, WARM, FORCE
# 결과: experiments/EXP-PIPE/stage4_<test>_<profile>[...].json — 전체 유실·중복 + fault(구간 유실·복구 초·최대 공백)
set -uo pipefail
. harness/pipebench/lib.sh
bench_guard
T=${1:?r01|r03|r06|r08}; PROF=${2:?profile}
case "$T" in
  r01) DUR=240; AT=60; RATE=1 ;;
  r03) DUR=240; AT=60; RATE=1 ;;
  r06) DUR=480; AT=60; RATE=1 ;;
  r08) DUR=600; AT=0;  RATE=10 ;;
  *) echo "test?" >&2; exit 2 ;;
esac
pipe_up "$PROF" "${T}_"
OUT=$EXP/stage4_${TAG}.json
[ -e "$OUT" ] && { echo "$OUT 이미 있음 — RUN=<새 ID> 로" >&2; exit 5; }
FF=$RAW/fault_${TAG}.txt; rm -f "$FF"
SETTLE=${SETTLE:-120}
harness/sample_stats.sh "$RAW/stats_${TAG}.csv" $((DUR + SETTLE + 30)) '^pipebench-' &
sp=$!
pipe_check "/experiments/EXP-PIPE/stage4_${TAG}.json" "$DUR" --event-rate "$RATE" --settle "$SETTLE" \
  --fault-file "/experiments/EXP-PIPE/raw/fault_${TAG}.txt" &
cp=$!
if [ "$T" = r08 ]; then
  sleep 5; T0=$(date +%s.%N); sleep "$DUR"; T1=$(date +%s.%N); KIND="overload-x10"
else
  sleep "$AT"; T0=$(date +%s.%N)
  case "$T" in
    r01) docker stop -t 10 "$BROKER_CTR" >/dev/null; sleep 30; docker start "$BROKER_CTR" >/dev/null; KIND="broker-stop-30s" ;;
    r03) docker restart -t 10 pipebench-kafka-1 >/dev/null; KIND="kafka-restart" ;;
    r06) docker stop -t 10 pipebench-influxdb-1 >/dev/null; sleep 300; docker start pipebench-influxdb-1 >/dev/null; KIND="influx-down-300s" ;;
  esac
  T1=$(date +%s.%N)
fi
echo "$T0 $T1 $KIND" > "$FF"
echo "[pipe4] $KIND $T0 → $T1"
wait $cp; wait $sp
pipe_finish "$OUT"
