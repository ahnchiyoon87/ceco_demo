#!/usr/bin/env bash
# S09 한 번 실행 + 두 후보 판정 + 알람 전체 중복·유실 대조(대조군 기준).
#   harness/s09_eval.sh <run> "<kill 대상 컨테이너들>" <kill 쪽 토픽 접미사> <대조 토픽 접미사>
#   환경변수 FLINK_REST: 사전 점검할 Flink REST (기본 http://flink-jobmanager:8081)
# 출력을 숨기지 않는다. 결과는 experiments/EXP-S09/raw/ 에 남는다.
set -uo pipefail
run=$1; targets=$2; killed=$3; ctrl=$4
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1
fr=${FLINK_REST:-http://flink-jobmanager:8081}
raw=experiments/EXP-S09/raw
B="docker compose -f harness/l4bench/compose.yml"
T="$B --profile tools run --rm -T -e FLINK_REST=$fr tools"
echo "===== S09 $run kill=[$targets] killed=$killed control=$ctrl"
FLINK_REST=$fr harness/s09.sh EXP-S09 "$run" "$targets" --require-jobs 3 || { echo "S09 실행 실패 — 판정하지 않음"; exit 1; }
cat "$raw/s09_${run}_actions.log"
sleep 40
echo "-- 재시작 후 Flink 잡 상태 ($fr)"
$T python -c "import json,urllib.request,os;print({j['name']:j['state'] for j in json.load(urllib.request.urlopen(os.environ['FLINK_REST']+'/jobs/overview'))['jobs']})" 2>&1 | grep -v Container | tee "$raw/${run}_jobs_after.txt"
for t in "$killed" "$ctrl"; do
  $T python /repo/harness/tools/evaluate.py --exp EXP-S09 --run "$run" --alerts "exp.l4.alerts.$t" 2>&1 | grep -v Container | grep -E "S09|^PASS" | sed "s/^/[$t] /"
  cp "$raw/alerts_${run}.jsonl" "$raw/alerts_${run}_${t}.jsonl"
  cp "$raw/result_${run}.json" "$raw/result_${run}_${t}.json"
done
python - "$raw" "$run" "$killed" "$ctrl" <<'EOF'
import collections, json, sys
raw, run, k, c = sys.argv[1:]
load = lambda t: collections.Counter((r["device"], r["alert_type"], r["tag"], r["ts"])
                                     for r in map(json.loads, open(f"{raw}/alerts_{run}_{t}.jsonl", encoding="utf-8")))
a, b = load(k), load(c)
dup = sum(v - 1 for v in a.values() if v > 1)
out = {"run": run, "killed": k, "control": c, "alerts_killed": sum(a.values()), "alerts_control": sum(b.values()),
       "duplicates": dup, "lost_vs_control": sum((b - a).values()), "extra_vs_control": sum((a - b).values()),
       "types_killed": dict(collections.Counter(x[1] for x in a.elements())),
       "types_control": dict(collections.Counter(x[1] for x in b.elements()))}
json.dump(out, open(f"{raw}/g8_{run}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("G8:", out)
EOF
