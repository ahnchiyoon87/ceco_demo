#!/usr/bin/env bash
# L4 벤치 정상 조건 측정: 한 번의 리플레이를 Flink SQL(V1)과 Python 후보가 동시에 소비 → 각각 판정 → 알람 전체 대조.
#   harness/run_l4.sh <EXP> <run> [stats_seconds]
set -uo pipefail
exp=$1; run=$2; secs=${3:-100}
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1
B="docker compose -f harness/l4bench/compose.yml"
T="$B --profile tools run --rm -T tools"
raw="experiments/$exp/raw"; mkdir -p "$raw"
harness/sample_stats.sh "$raw/stats_${run}.csv" "$secs" "l4bench-(flink|l4-python)" &
$T python /repo/harness/tools/replay.py --exp "$exp" --run "$run" --require-jobs 3 2>&1 | grep -v Container | tail -2 || exit 1
sleep 15
for topic in python flinksql; do
  extra=""; [ "$topic" = python ] && extra="--dropped exp.l4.dropped.python"
  echo "== $topic"
  $T python /repo/harness/tools/evaluate.py --exp "$exp" --run "$run" --alerts "exp.l4.alerts.$topic" $extra 2>&1 | grep -v Container | tail -1
  cp "$raw/alerts_${run}.jsonl" "$raw/alerts_${run}_${topic}.jsonl"
  cp "$raw/result_${run}.json" "$raw/result_${run}_${topic}.json"
done
python - "$raw" "$run" <<'EOF'
import collections, json, sys
raw, run = sys.argv[1], sys.argv[2]
k = lambda t: collections.Counter((r["device"], r["alert_type"], r["tag"], r["ts"])
                                  for r in map(json.loads, open(f"{raw}/alerts_{run}_{t}.jsonl", encoding="utf-8")))
a, b = k("python"), k("flinksql")
print(f"alerts python={sum(a.values())} flink={sum(b.values())} only_python={sum((a-b).values())} only_flink={sum((b-a).values())}")
EOF
wait
