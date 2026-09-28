#!/usr/bin/env bash
# L4 벤치 정상 조건 측정: 한 번의 리플레이를 Flink 후보와 Python 후보가 동시에 소비 → 각각 판정 → 알람 전체 대조.
#   harness/run_l4.sh <EXP> <run> [stats_seconds]
#   환경변수: FLINK_TOPIC(기본 flinksql) FLINK_REST(기본 http://flink-jobmanager:8081) STATS_PAT(기본 l4bench-(flink|l4-python))
#            REPLAY_ARGS(예: "--repeat 10 --jitter")
set -uo pipefail
exp=$1; run=$2; secs=${3:-100}
ft=${FLINK_TOPIC:-flinksql}; fr=${FLINK_REST:-http://flink-jobmanager:8081}; pat=${STATS_PAT:-"l4bench-(flink|l4-python)"}
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1
B="docker compose -f harness/l4bench/compose.yml"
T="$B --profile tools run --rm -T -e FLINK_REST=$fr tools"
raw="experiments/$exp/raw"; mkdir -p "$raw"
harness/sample_stats.sh "$raw/stats_${run}.csv" "$secs" "$pat" &
$T python /repo/harness/tools/replay.py --exp "$exp" --run "$run" --require-jobs 3 ${REPLAY_ARGS:-} 2>&1 | grep -v Container | tail -2
[ -s "$raw/replay_${run}_emitted.jsonl" ] || { echo "리플레이 미실행 — 중단"; wait; exit 1; }
sleep 15
for topic in python "$ft"; do
  extra=""; [ "$topic" = python ] && extra="--dropped exp.l4.dropped.python"
  echo "== $topic"
  $T python /repo/harness/tools/evaluate.py --exp "$exp" --run "$run" --alerts "exp.l4.alerts.$topic" $extra 2>&1 | grep -v Container | tail -1
  cp "$raw/alerts_${run}.jsonl" "$raw/alerts_${run}_${topic}.jsonl"
  cp "$raw/result_${run}.json" "$raw/result_${run}_${topic}.json"
done
python - "$raw" "$run" "$ft" <<'EOF'
import collections, json, sys
raw, run, ft = sys.argv[1], sys.argv[2], sys.argv[3]
k = lambda t: collections.Counter((r["device"], r["alert_type"], r["tag"], r["ts"])
                                  for r in map(json.loads, open(f"{raw}/alerts_{run}_{t}.jsonl", encoding="utf-8")))
a, b = k("python"), k(ft)
print(f"alerts python={sum(a.values())} {ft}={sum(b.values())} only_python={sum((a-b).values())} only_{ft}={sum((b-a).values())}")
EOF
wait
