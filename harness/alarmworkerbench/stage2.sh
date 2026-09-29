#!/usr/bin/env bash
# 알람 워커 ②③(+재전달·중단 복구) 한 바퀴 — 09-29 지시. 기준 v1 을 먼저 돌려 기준 덤프를 만든다.
#   harness/alarmworkerbench/stage2.sh <profile: v1 bento rpconnect ekuiper kconnect>
#   환경변수: RUN(반복 ID), KAFKA_IMAGE(기본 3.9.0; kconnect 는 4.3.1 자동), REF(기준 덤프, 기본 experiments/EXP-ALW/dump1_v1.json),
#             LOAD_N(600), LOAD_RATE(20), KEEP, FORCE
# 순서: 기동 → ① 시나리오 50건(파티션 0, 순서 고정) 처리 → dump1 → ② 재전달: 워커 정지 → 그룹 오프셋 earliest 로 되감기 → 재기동
#       → dump2 (dump1 과 같아야 함 = 멱등) → ③ 부하 600건 20/s(3파티션) 도중 워커 kill → 재기동 → 유실·중복·지연 → 자원
# 결과: experiments/EXP-ALW/stage2_<profile>[_<RUN>].json(비교·재전달·부하·자원 합본), raw/dump1_·dump2_·load_·stats_·logs_
set -uo pipefail
. harness/benchguard.sh
bench_guard
P=${1:?profile: v1 bento rpconnect ekuiper kconnect}
case "$P" in
  v1)        SVC=v1-worker; GROUP=ar100-ai-incidents-v1; INITDB=initdb/none; IMAGES="python:3.12.8-slim"; BUILD=1 ;;
  bento)     SVC=bento;     GROUP=alw-bento;     INITDB=sql; IMAGES="ghcr.io/warpstreamlabs/bento:1.21.2" ;;
  rpconnect) SVC=rpconnect; GROUP=alw-rpconnect; INITDB=sql; IMAGES="docker.redpanda.com/redpandadata/connect:4.111.0" ;;
  ekuiper)   SVC=ekuiper;   GROUP=alw-ekuiper;   INITDB=sql; IMAGES="lfedge/ekuiper:2.4.2"; SETUP="python /repo/harness/alarmworkerbench/ekuiper/setup.py" ;;
  kconnect)  SVC=kconnect;  GROUP=connect-alw-jdbc; INITDB=sql; IMAGES="eclipse-temurin:21.0.8_9-jdk apache/kafka:4.3.1"; BUILD=1
             KAFKA_IMAGE=${KAFKA_IMAGE:-apache/kafka:4.3.1} ;;
  *) echo "profile?" >&2; exit 2 ;;
esac
export INITDB KAFKA_IMAGE=${KAFKA_IMAGE:-apache/kafka:3.9.0}
EXP=experiments/EXP-ALW; RAW=$EXP/raw; mkdir -p "$RAW"
TAG=${P}${RUN:+_$RUN}
OUT=$EXP/stage2_${TAG}.json
[ -e "$OUT" ] && { echo "$OUT 이미 있음 — RUN=<새 ID> 로" >&2; exit 5; }
bench_require_images postgres:17 "$KAFKA_IMAGE" python:3.12.8-slim $IMAGES
DC="docker compose -p alwbench -f harness/alarmworkerbench/compose.yml"
W=alwbench-${SVC}-1
C="$DC --profile tools run --rm -T client python /repo/harness/alarmworkerbench/check_alw.py"
$DC --profile '*' down -v --remove-orphans >/dev/null 2>&1
$DC --profile tools build -q client || exit 6
$DC --profile "$P" up -d ${BUILD:+--build} || { $DC --profile "$P" logs --no-color > "$RAW/logs_${TAG}_up_fail.txt" 2>&1; $DC --profile '*' down -v --remove-orphans >/dev/null 2>&1; exit 6; }   # 실패 시 정리(#116)
[ -n "${SETUP:-}" ] && { sleep 5; $DC --profile tools run --rm -T client $SETUP > "$RAW/setup_${TAG}.txt" 2>&1 || { cat "$RAW/setup_${TAG}.txt"; $DC --profile "$P" logs --no-color > "$RAW/logs_${TAG}.txt" 2>&1; echo "[alw] SETUP 실패 → 원인 확인 필요(설정 출력 $RAW/setup_${TAG}.txt, #112)"; $DC --profile '*' down -v --remove-orphans >/dev/null 2>&1; exit 7; }; cat "$RAW/setup_${TAG}.txt"; }
sleep 10
harness/sample_stats.sh "$RAW/stats_${TAG}.csv" 900 '^alwbench-' &
sp=$!
echo "[alw] ① 시나리오"; $C scenario --tag "$TAG" || echo "[alw] 시나리오 처리 미완(시간 초과) — 결과에 그대로 남김"
$C dump --out "/experiments/EXP-ALW/raw/dump1_${TAG}.json"
echo "[alw] ② 재전달(오프셋 되감기)"
docker stop -t 10 "$W" >/dev/null
docker exec alwbench-kafka-1 /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --group "$GROUP" \
  --reset-offsets --to-earliest --topic sensor.alerts --execute > "$RAW/reset_${TAG}.txt" 2>&1
docker start "$W" >/dev/null
lag_zero() {   # 그룹 지연(LAG)이 전부 0 이 될 때까지(최대 180 s) — 재처리 완료 판단
  for i in $(seq 1 90); do
    sleep 2
    l=$(docker exec alwbench-kafka-1 /opt/kafka/bin/kafka-consumer-groups.sh --bootstrap-server localhost:9092 --describe --group "$GROUP" 2>/dev/null         | awk '$1=="'"$GROUP"'" && $6 ~ /^[0-9]+$/ {s+=$6; n++} END {print (n>0 ? s : -1)}')
    [ "$l" = 0 ] && { sleep 5; return 0; }
  done; echo "[alw] LAG 0 미도달(재처리 미완 가능)"; return 1
}
lag_zero
$C dump --out "/experiments/EXP-ALW/raw/dump2_${TAG}.json"
echo "[alw] ③ 부하 + 워커 kill"
LOAD_N=${LOAD_N:-600}; LOAD_RATE=${LOAD_RATE:-20}
( sleep $(( LOAD_N / LOAD_RATE / 2 )); echo "$(date +%s.%N) kill $W" >> "$RAW/actions_${TAG}.log"; docker kill "$W" >/dev/null; sleep 5; docker start "$W" >/dev/null; echo "$(date +%s.%N) start $W" >> "$RAW/actions_${TAG}.log" ) &
kp=$!
$C load --tag "$TAG" --n "$LOAD_N" --rate "$LOAD_RATE" --out "/experiments/EXP-ALW/raw/load_${TAG}.json"
wait $kp
kill $sp 2>/dev/null
REF=${REF:-$EXP/dump1_v1.json}
[ "$P" = v1 ] && [ -z "${RUN:-}" ] && cp "$RAW/dump1_${TAG}.json" "$EXP/dump1_v1.json"
$C compare --a "/experiments/EXP-ALW/raw/dump1_${TAG}.json" --b "/experiments/EXP-ALW/raw/dump2_${TAG}.json" --out "/experiments/EXP-ALW/raw/redelivery_${TAG}.json"
if [ -f "$REF" ]; then
  $C compare --a "/repo/${REF}" --b "/experiments/EXP-ALW/raw/dump1_${TAG}.json" --out "/experiments/EXP-ALW/raw/vs_v1_${TAG}.json"
fi
python - "$OUT" "$RAW" "$TAG" <<'PY'
import json, pathlib, sys
out, raw, tag = sys.argv[1], pathlib.Path(sys.argv[2]), sys.argv[3]
def rd(n):
    p = raw / n
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
res = {"exp": "EXP-ALW", "profile": tag, "vs_v1": rd(f"vs_v1_{tag}.json"), "redelivery_idempotent": rd(f"redelivery_{tag}.json"),
       "load_with_worker_kill": rd(f"load_{tag}.json")}
pathlib.Path(out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
PY
bench_image_sizes "$RAW/images_${TAG}.json" $IMAGES
python harness/benchstats.py --result "$OUT" --stats "$RAW/stats_${TAG}.csv" --images "$RAW/images_${TAG}.json" --only "^alwbench-(${SVC}|work-db)-"
$DC --profile "$P" logs --no-color > "$RAW/logs_${TAG}.txt" 2>&1
[ "${KEEP:-0}" = 1 ] || $DC --profile '*' down -v --remove-orphans >/dev/null 2>&1
echo "[alw] 결과: $OUT"
