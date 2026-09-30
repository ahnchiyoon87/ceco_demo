#!/bin/bash
# [측정 도구] 한 사이클(HANDOFF §3-6): 이상 주입 → 감지(알람) → AI 사건 → AI 분석(LLM) → 조치 제안. 목표 1분 안.
#   bash tests/e2e/cycle_base.sh <EXP> <이름>        LLM 호출은 분석 1회(크레딧). 끝나면 고장을 푼다.
# 시각은 모두 벽시계 초(주입 = 0). 결과: experiments/<EXP>/raw/cycle_<이름>.json
set -u
EXP=$1; NAME=$2
. tests/e2e/struct_base.sh
AUTH="-u $SIM_AUTH"
OUT=experiments/$EXP/raw/cycle_${NAME}.json
now(){ python -c "import time;print(time.time())"; }
curl -s $AUTH -X POST -H 'Content-Type: application/json' -d '{}' $SIM_HOST/fault/clear >/dev/null
sleep 5
T0=$(now)
curl -s $AUTH -X POST -H 'Content-Type: application/json' -d '{"scenario":"bearing_wear","duration_s":252000}' $SIM_HOST/fault >/dev/null
inc=""
while [ -z "$inc" ] && python -c "import sys,time;sys.exit(0 if time.time()-$T0<60 else 1)"; do
  inc=$(curl -s "$AI_HOST/incidents" | PYTHONUTF8=1 python tests/e2e/find_incident.py ${T0%.*} 2>/dev/null); [ -z "$inc" ] && sleep 0.5
done
T_INC=$(now)
[ -z "$inc" ] && { echo '{"pass":false,"error":"사건 없음"}' > $OUT; cat $OUT; exit 1; }
curl -s -X POST "$AI_HOST/incidents/$inc/analyze" > /dev/null
T_REQ=$(now)
st=running
while [ "$st" = running ] || [ "$st" = resuming ]; do
  sleep 1
  st=$(curl -s "$AI_HOST/incidents/$inc/analysis" | python -c "import json,sys;print(json.load(sys.stdin)['items'][0]['status'])")
  python -c "import sys,time;sys.exit(0 if time.time()-$T0<180 else 1)" || break
done
T_END=$(now)
curl -s "$AI_HOST/incidents/$inc/analysis" > "$TEMP/cyc_a.json"
curl -s "$AI_HOST/incidents/$inc/proposals" > "$TEMP/cyc_p.json"
curl -s $AUTH -X POST -H 'Content-Type: application/json' -d '{}' $SIM_HOST/fault/clear >/dev/null
PYTHONUTF8=1 python - "$T0" "$T_INC" "$T_REQ" "$T_END" "$inc" "$TEMP/cyc_a.json" "$TEMP/cyc_p.json" "$OUT" <<'PY'
import json, sys
t0, ti, tr, te = map(float, sys.argv[1:5]); inc = sys.argv[5]
a = json.load(open(sys.argv[6], encoding="utf-8"))["items"][0]; p = json.load(open(sys.argv[7], encoding="utf-8"))["items"]
acts = [x["body"].get("action") for x in p]
out = {"incident": inc, "run_status": a["status"], "model": a.get("model"), "proposals": acts,
       "t_incident_s": round(ti - t0, 2), "t_analysis_s": round(te - tr, 2), "t_cycle_s": round(te - t0, 2),
       "pass": a["status"] == "awaiting_review" and bool(p) and te - t0 <= 60}
json.dump(out, open(sys.argv[8], "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
PY
