#!/bin/sh
# [측정 도구] 빠른 확인(후보 적용 직후, 약 2~3분): ① 저장 흐름·탐지 잡 ② 메모리(SCADA rot- 컨테이너, AI 제외) ③ 스파이크 1회 알람
#   sh harness/e2e/quick_check.sh <이름>   → experiments/QUICK/<이름>.json
set -u
N=$1; export MSYS_NO_PATHCONV=1; mkdir -p experiments/QUICK
S=/c/Users/roede/AppData/Local/Temp/claude/d--work-study/324f5fcd-efb5-4b4d-a619-d4fd3f6b461f/scratchpad
jobs=$(curl -s -m 5 localhost:37081/jobs/overview | python -c "import json,sys;print(sum(j['state']=='RUNNING' for j in json.load(sys.stdin)['jobs']))" 2>/dev/null)
raw=$(python $S/influxcount.py 30s | grep process_raw | awk -F, '{print $6}')
mem=$(docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' | grep '^rot-' | grep -v 'rot-ai' | python -c "
import sys,re,json
d={}
for l in sys.stdin:
    n,u=l.split()[0],l.split()[1]; v=float(re.match(r'[\d.]+',u).group()); v*=1024 if 'GiB' in u else (1/1024 if 'KiB' in u else 1); d[n]=round(v)
print(json.dumps({'total_mib':sum(d.values()),'n':len(d),'per':d}))")
onset=$(docker run --rm --network rot-iiot --env-file .env -v D:/work/study/scada-rotation:/repo -w /repo e2e-client:1.2 python harness/e2e/fault_onset.py --reps 1 --faults spike --broker mqtt --mqtt-topic scada/hmi/latest-alert --out experiments/QUICK/${N}_onset.json 2>&1 | tail -1)
python -c "import json,sys;print(json.dumps({'name':sys.argv[1],'jobs_running':sys.argv[2],'influx_raw_30s':sys.argv[3],'mem':json.loads(sys.argv[4]),'spike':sys.argv[5]},ensure_ascii=False))" "$N" "$jobs" "$raw" "$mem" "$onset" | tee experiments/QUICK/$N.json
