#!/bin/sh
# [측정 도구] 회귀 S01~S25 (전체 스택이 떠 있는 상태에서). 판정 기준 scenarios/catalog.yaml(결과 전 고정).
#   STRUCT=V1|V2 sh harness/e2e/regression.sh <EXP> <이름> [S25=1]
# S01 정상 3분 알람·저장 / S02·S04~S08 리플레이(실제 스택 raw 토픽, V1 과 같은 시드)로 판정 70건 / S14~S21·S24·S16 제어·안전
# (regression_control.py, AI 백엔드 안) / S22 업무 DB 다운 fail-closed / S25 근거 문서 없는 사건 분석(LLM 1회, S25=1 일 때).
# S09~S12 = baseline.sh 의 R05·R02·R01·R03·R06, S13 = l4bench S13, S23 = E1 — 여기서는 재지 않고 요약에서 가져온다.
set -u
EXP=$1; NAME=$2
export MSYS_NO_PATHCONV=1
STRUCT=${STRUCT:-V1}
R=experiments/$EXP/raw; mkdir -p $R
LOG=experiments/$EXP/regression_$NAME.log
REPO="D:/work/study/scada-rotation"
CLIENT="docker run --rm --network rot-iiot --add-host host.docker.internal:host-gateway --env-file .env -v $REPO:/repo -v $REPO/experiments:/experiments -w /repo e2e-client:1.0"
TOOLS="docker run --rm --network rot-iiot -v $REPO:/repo -v $REPO/experiments:/experiments -w /repo l4bench-tools:1.0"
API=http://127.0.0.1:38000/api/operations
SIM=http://127.0.0.1:37080
OUT=$R/regression_${NAME}.jsonl
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a $LOG; }
ms(){ echo $(( $(date +%s) * 1000 )); }
rec(){ echo "$1" >> $OUT; say "$1"; }

say "== 회귀 $NAME ($STRUCT) 시작"
curl -s -X POST -H 'Content-Type: application/json' -d '{}' $SIM/fault/clear >/dev/null; sleep 5

# ── S01 정상 운전 3분(#89 시간 값): 설비 장치 알람 수·12태그 저장 ──
T0=$(ms); sleep 180; T1=$(ms)
$CLIENT python harness/e2e/alerts_window.py --start-ms $T0 --end-ms $T1 --out /repo/$R/s01_alerts_${NAME}.json 2>&1 | tail -1 >> $LOG
$CLIENT python harness/e2e/completeness.py --start-ms $T0 --end-ms $T1 --out /repo/$R/s01_complete_${NAME}.json 2>&1 | tail -1 >> $LOG
rec "$(PYTHONUTF8=1 python -c "
import json;a=json.load(open('$R/s01_alerts_${NAME}.json',encoding='utf-8'));c=json.load(open('$R/s01_complete_${NAME}.json',encoding='utf-8'))
print(json.dumps({'s':'S01','alerts':a['alerts'],'by':a['by_type_tag'],'tags_stored':sum(1 for t,v in c['influx_process_raw']['per_tag'].items() if v['n']>0),'store_missing':c['influx_process_raw']['missing_s_total']},ensure_ascii=False))")"

# ── S02·S04~S08 리플레이(판정 70건, V1 기록과 같은 시드) ──
RUNL4=reg_${NAME}_l4
$TOOLS python /repo/harness/tools/replay.py --exp $EXP --run $RUNL4 --topic sensor.telemetry.raw --repeat 10 --seed 1001 --jitter 2>&1 | tail -1 >> $LOG
sleep 20
$TOOLS python /repo/harness/tools/evaluate.py --exp $EXP --run $RUNL4 --alerts sensor.alerts 2>&1 | tail -1 | tee -a $LOG > $R/${RUNL4}_eval.txt
rec "{\"s\":\"S02-S08\",\"eval\":\"$(tail -1 $R/${RUNL4}_eval.txt | tr -d '"' | cut -c1-300)\"}"

# ── 제어·안전: 교반기 이상을 걸고 그 사건으로 S14~S21·S24·S16 ──
T0=$(date +%s)
curl -s -X POST -H 'Content-Type: application/json' -d '{"scenario":"bearing_wear","duration_s":420}' $SIM/fault >> $LOG
inc=""
for i in $(seq 1 60); do
  inc=$(curl -s "$API/incidents" | PYTHONUTF8=1 python -c "
import json,sys,datetime
items=json.load(sys.stdin); items=items.get('items',items) if isinstance(items,dict) else items
for x in items:
    if 'mixer-current-vibration' in x.get('correlation_key','') and x.get('status') in ('received','awaiting_review','unresolved') and x.get('last_ts',0)/1e9 >= $T0-5:
        print(x['id']); break" 2>/dev/null)
  [ -n "$inc" ] && break; sleep 2
done
say "교반기 사건: ${inc:-없음} ($(( $(date +%s) - T0 ))s)"
sleep 10
docker exec -i rot-ai-knowledge-1 python - < harness/e2e/regression_control.py 2>>$LOG | tail -1 > $R/control_${NAME}.json
rec "{\"s\":\"S14-S21,S24,S16\",\"incident\":\"$inc\",\"result\":$(cat $R/control_${NAME}.json 2>/dev/null || echo null)}"
curl -s -X POST -H 'Content-Type: application/json' -d '{}' $SIM/fault/clear >/dev/null; sleep 10

# ── S22 업무 DB 다운 중 운전원 명령 → 설비에 쓰지 않음(fail-closed) ──
before=$(curl -s $SIM/state); docker stop rot-ai-work-db-1 >>$LOG 2>&1
resp=$(curl -s -m 20 -X POST -H 'Content-Type: application/json' -d "{\"request_id\":\"$(python -c 'import uuid;print(uuid.uuid4())')\",\"target\":\"valve_open_sp\",\"value\":50}" $API/simulation/control)
after=$(curl -s $SIM/state); docker start rot-ai-work-db-1 >>$LOG 2>&1
rec "$(python -c "import json,sys;b=json.loads(sys.argv[1]);a=json.loads(sys.argv[2]);print(json.dumps({'s':'S22','pass':b['commands']==a['commands'],'response':sys.argv[3][:200]},ensure_ascii=False))" "$before" "$after" "$resp")"
sleep 15

# ── S25 근거 문서 없는 사건 분석(LLM 1회) ──
if [ "${S25:-0}" = 1 ]; then
  ts=$(python -c "import time;print(time.time_ns())")
  inc25=$(curl -s -X POST -H 'Content-Type: application/json' -d "{\"ts\":$ts,\"site\":\"AR-100\",\"device\":\"reactor-line-01\",\"tag\":\"CT-101\",\"value\":9.9,\"alert_type\":\"THRESHOLD_USL\",\"severity\":\"WARNING\",\"detector\":\"regression-S25\",\"detail\":\"회귀 S25 입력: 문서가 연결되지 않은 태그\"}" $API/incidents | python -c "import json,sys;print(json.load(sys.stdin)['incident']['id'])")
  curl -s -X POST -H 'Content-Type: application/json' -d '{}' $API/incidents/$inc25/analyze >> $LOG
  for i in $(seq 1 90); do st=$(curl -s $API/incidents/$inc25/analysis | python -c "import json,sys;r=json.load(sys.stdin)['items'][0];print(r['status'])"); [ "$st" != running ] && [ "$st" != resuming ] && break; sleep 2; done
  curl -s $API/incidents/$inc25/analysis > $R/s25_${NAME}.json
  curl -s $API/incidents/$inc25/proposals > $R/s25_proposals_${NAME}.json
  rec "$(PYTHONUTF8=1 python -c "
import json;r=json.load(open('$R/s25_${NAME}.json',encoding='utf-8'))['items'][0];p=json.load(open('$R/s25_proposals_${NAME}.json',encoding='utf-8'))['items']
acts=[x['body'].get('action') for x in p]
print(json.dumps({'s':'S25','run_status':r['status'],'actions':acts,'device_action_proposed':any(a in ('stop_mixer','enable_cooling') for a in acts)},ensure_ascii=False))")"
fi
say "== 회귀 $NAME 끝"
