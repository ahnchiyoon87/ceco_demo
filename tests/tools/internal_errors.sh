#!/bin/sh
# [측정 도구] 내부 오류 수집(안정성 대장 근거): 실행 구간 동안 컨테이너 로그의 오류·예외·경고, 재시작·OOM, Flink 예외 기록.
#   sh tests/tools/internal_errors.sh <since(예: 15m 또는 RFC3339)> <out.json> [이름정규식=^rot-]
since=$1; out=$2; pat=${3:-^rot-}
export MSYS_NO_PATHCONV=1
tmp=$(mktemp -d)
for c in $(docker ps -a --format '{{.Names}}' | grep -E "$pat"); do
  docker logs --since "$since" "$c" > "$tmp/$c.log" 2>&1
  docker inspect "$c" --format '{{.Name}}|{{.RestartCount}}|{{.State.OOMKilled}}|{{.State.Status}}|{{.State.ExitCode}}' > "$tmp/$c.state" 2>/dev/null
done
curl -s -m 5 http://127.0.0.1:37081/jobs/overview > "$tmp/_flink_jobs.json" 2>/dev/null
for j in $(python -c "import json,sys;[print(j['jid']) for j in json.load(open(sys.argv[1]))['jobs']]" "$tmp/_flink_jobs.json" 2>/dev/null); do
  curl -s -m 5 http://127.0.0.1:37081/jobs/$j/exceptions > "$tmp/_flink_exc_$j.json" 2>/dev/null
done
wtmp=$(cygpath -w "$tmp" 2>/dev/null || echo "$tmp")   # Windows Python 은 Git Bash 의 /tmp 를 못 읽음(09-29 #103)
PYTHONUTF8=1 python - "$wtmp" "$out" <<'PY'
import json, re, sys, glob, os
tmp, out = sys.argv[1], sys.argv[2]
PAT = re.compile(r"(ERROR|Exception|Traceback|FATAL|panic|OOM|refused|timed? ?out|WARN)", re.I)
res = {"containers": {}, "flink": {}}
for f in glob.glob(os.path.join(tmp, "*.log")):
    name = os.path.basename(f)[:-4]
    lines = open(f, encoding="utf-8", errors="replace").read().splitlines()
    hits = [l for l in lines if PAT.search(l)]
    sig = {}
    for l in hits:
        k = re.sub(r"[0-9a-f]{8,}|\d+(\.\d+)?", "#", l)[:160]
        sig[k] = sig.get(k, 0) + 1
    st = open(os.path.join(tmp, name + ".state"), encoding="utf-8").read().strip().split("|") if os.path.exists(os.path.join(tmp, name + ".state")) else []
    res["containers"][name] = {"lines": len(lines), "error_like": len(hits),
        "restarts": int(st[1]) if len(st) > 1 else None, "oom_killed": st[2] == "true" if len(st) > 2 else None,
        "status": st[3] if len(st) > 3 else None, "top": sorted(sig.items(), key=lambda kv: -kv[1])[:5]}
for f in glob.glob(os.path.join(tmp, "_flink_exc_*.json")):
    try:
        d = json.load(open(f)); res["flink"][os.path.basename(f)[11:-5]] = str(d.get("root-exception"))[:300]
    except Exception:
        pass
try:
    res["flink_jobs"] = [(j["name"], j["state"]) for j in json.load(open(os.path.join(tmp, "_flink_jobs.json")))["jobs"]]
except Exception:
    res["flink_jobs"] = None
if not res["containers"]:
    sys.exit("수집된 컨테이너 로그 0개 — 경로·이름 정규식 확인")
json.dump(res, open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
bad = {k: (v["error_like"], v["restarts"], v["oom_killed"]) for k, v in res["containers"].items() if v["error_like"] or v["restarts"] or v["oom_killed"]}
print(json.dumps({"with_errors_or_restarts": bad, "flink_exceptions": {k: v[:80] for k, v in res["flink"].items() if v and v != "None"}}, ensure_ascii=False))
PY
rm -rf "$tmp"
