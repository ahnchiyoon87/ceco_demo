#!/usr/bin/env bash
# L4 정상 조건: 한 번의 리플레이를 여러 후보가 동시에 소비 → 후보별 판정 → 알람 전체 상호 대조 → 자원 요약.
#   harness/run_l4_multi.sh <EXP> <run> [replay 추가 인자...]
#   환경변수 CANDIDATES (기본 "python flinksql flink22"), STATS_SECS (기본 자동)
# 출력을 숨기지 않는다.
set -uo pipefail
exp=$1; run=$2; shift 2
cands=${CANDIDATES:-"python flinksql flink22"}
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1
B="docker compose -f harness/l4bench/compose.yml"
T="$B --profile tools run --rm -T tools"
raw="experiments/$exp/raw"; mkdir -p "$raw"
[ -e "$raw/replay_${run}_manifest.json" ] && { echo "실행 ID $run 은 $exp 에서 이미 쓰였다"; exit 1; }

# 사전 점검: 각 Flink 클러스터 잡 4개 RUNNING, 취소·완료 외 다른 상태(FAILED·RESTARTING 등) 0 (r10a: 취소 이력 때문에 오판 → 수정) (규칙 SQL/CEP 3 + V1 ONNX 잡 1, 후보 목록에 있을 때)
for pair in "flinksql:http://flink-jobmanager:8081" "flink22:http://flink22-jobmanager:8081" "cep:http://flinkcep-jobmanager:8081"; do
  c=${pair%%:*}; url=${pair#*:}
  case " $cands " in *" $c "*) ;; *) continue;; esac
  st=$($T python -c "import json,urllib.request;j=json.load(urllib.request.urlopen('$url/jobs/overview'))['jobs'];print(sum(x['state']=='RUNNING' for x in j),sum(x['state'] not in ('CANCELED','FINISHED') for x in j))" 2>/dev/null | tail -1)
  [ "$st" = "${JOBS:-4} ${JOBS:-4}" ] || { echo "사전 점검 실패: $c 잡 상태 '$st'"; exit 1; }
  echo "사전 점검 통과: $c ($st)"
done

secs=${STATS_SECS:-400}
harness/sample_stats.sh "$raw/stats_${run}.csv" "$secs" "l4bench-(flink|l4-python)" &
sp=$!
$T python /repo/harness/tools/replay.py --exp "$exp" --run "$run" "$@" 2>&1 | grep -v Container | tail -2
[ -s "$raw/replay_${run}_emitted.jsonl" ] || { echo "리플레이 미실행 — 중단"; kill $sp; exit 1; }
sleep 15
kill $sp 2>/dev/null
for c in $cands; do
  extra=""; [ "$c" = python ] && extra="--dropped exp.l4.dropped.python"
  echo "== $c"
  $T python /repo/harness/tools/evaluate.py --exp "$exp" --run "$run" --alerts "exp.l4.alerts.$c" $extra 2>&1 | grep -v Container | tail -1
  cp "$raw/alerts_${run}.jsonl" "$raw/alerts_${run}_${c}.jsonl"
  cp "$raw/result_${run}.json" "$raw/result_${run}_${c}.json"
done
python - "$raw" "$run" $cands <<'EOF'
import collections, csv, json, statistics as st, sys
raw, run, cands = sys.argv[1], sys.argv[2], sys.argv[3:]
# ML(TIER2_ML) 알람은 처리시각 타이머라 실행마다 시각이 달라 규칙 비교에서 뺀다. 동일성은 S13(harness/tools/s13.py)에서 따로 판정
load = lambda t: collections.Counter((r["device"], r["alert_type"], r["tag"], r["ts"])
                                     for r in map(json.loads, open(f"{raw}/alerts_{run}_{t}.jsonl", encoding="utf-8"))
                                     if r.get("detector") != "TIER2_ML")
sets = {c: load(c) for c in cands}
base = cands[0]
summary = {"run": run, "alerts": {c: sum(s.values()) for c, s in sets.items()},
           "diff_vs_" + base: {c: {"only_" + c: sum((sets[c] - sets[base]).values()),
                                   "only_" + base: sum((sets[base] - sets[c]).values())} for c in cands[1:]}}
g = collections.defaultdict(lambda: [0.0, 0.0])
name = lambda n: "python" if "l4-python" in n else ("flink22" if "flink22" in n else ("cep" if "flinkcep" in n else "flinksql"))
for r in csv.DictReader(open(f"{raw}/stats_{run}.csv")):
    g[(name(r["name"]), r["t_epoch"])][0] += float(r["mem_mib"])
    g[(name(r["name"]), r["t_epoch"])][1] += float(r["cpu_pct"])
res = {}
for c in cands:
    v = [x for (k, _), x in g.items() if k == c]
    if v:
        res[c] = {"n": len(v), "mem_avg_mib": round(st.mean(a for a, b in v)), "mem_max_mib": round(max(a for a, b in v)),
                  "cpu_avg_pct": round(st.mean(b for a, b in v), 1), "cpu_max_pct": round(max(b for a, b in v), 1)}
summary["resources"] = res
json.dump(summary, open(f"{raw}/summary_{run}.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(summary, ensure_ascii=False))
EOF
