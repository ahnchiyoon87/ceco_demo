#!/bin/bash
# [측정 도구] 새 베이스 제어·안전 회귀(AI 쪽): 교반기 이상을 걸고 그 사건으로 S17·S21·S18·S22.
#   bash tests/e2e/control_ai.sh <EXP> <이름>
set -u
EXP=$1; NAME=$2
. tests/e2e/struct_base.sh
OUT=experiments/$EXP/raw/control_ai_${NAME}.jsonl; : > $OUT
AUTH="-u $SIM_AUTH"
ai(){ docker exec -i $C_KNOW python - "$@" < tests/e2e/control_ai.py 2>/dev/null | tail -1; }
say(){ echo "[$(date +%T)] $*"; }
curl -s $AUTH -X POST -H 'Content-Type: application/json' -d '{}' $SIM_HOST/fault/clear >/dev/null
T0=$(date +%s)
# bearing_wear 는 kind: process → 설비 초. 420 s(실제) × 배속 600
curl -s $AUTH -X POST -H 'Content-Type: application/json' -d '{"scenario":"bearing_wear","duration_s":252000}' $SIM_HOST/fault >/dev/null
inc=""
for i in $(seq 1 60); do
  inc=$(curl -s "$AI_HOST/incidents" | PYTHONUTF8=1 python tests/e2e/find_incident.py $T0 2>/dev/null)
  [ -n "$inc" ] && break; sleep 2
done
say "교반기 사건: ${inc:-없음} ($(( $(date +%s) - T0 ))s)"
[ -z "$inc" ] && { echo '{"s":"AI","error":"교반기 사건 없음"}' >> $OUT; exit 1; }
sleep 5
say "S17"; ai reject | tee -a $OUT
say "S21"; ai approve2 | tee -a $OUT
# S18: 대응안 → 운전원 길로 히터 명령을 바꿈(FUXA 대역) → 승인 → 409 기대 → 원래대로
say "S18"
pid=$(ai propose | python -c "import json,sys;print(json.load(sys.stdin)['proposal_id'])")
HEAT=$(curl -s $AUTH $SIM_HOST/state | python -c "import json,sys;print(str(json.load(sys.stdin)['commands']['heater_enable']).lower())")
FLIP=$([ "$HEAT" = true ] && echo false || echo true)
op(){ base_client python -c "
import json,os,time,paho.mqtt.client as m
c=m.Client(m.CallbackAPIVersion.VERSION2);c.username_pw_set('fuxa',os.environ['MQTT_FUXA_PASSWORD']);c.connect('ot-hub',1883);c.loop_start()
c.publish('AR-100/reaction/reactor-line-01/HX-101/cmd/operator',json.dumps({'command':'enable','value':$1,'ts':time.strftime('%Y-%m-%dT%H:%M:%SZ',time.gmtime())}),qos=1).wait_for_publish(5);time.sleep(4)"; }
op $([ "$FLIP" = true ] && echo True || echo False)
ai stale $pid | tee -a $OUT
op $([ "$HEAT" = true ] && echo True || echo False)
# S22: 대응안 → PostgreSQL 정지 → 승인(HTTP) → 재기동 → 그 대응안의 작업 요청 0건
say "S22"
pid=$(ai propose | python -c "import json,sys;print(json.load(sys.stdin)['proposal_id'])")
docker stop $C_PG >/dev/null
resp=$(curl -s -m 30 -w ' HTTP%{http_code}' -X POST -H 'Content-Type: application/json' -d '{"decision":"approve","note":"regression S22 db down"}' $AI_HOST/proposals/$pid/decision)
docker start $C_PG >/dev/null
for i in $(seq 1 60); do [ "$(docker inspect -f '{{.State.Health.Status}}' $C_PG)" = healthy ] && break; sleep 2; done
sleep 10
cnt=$(ai count $pid | python -c "import json,sys;print(json.load(sys.stdin)['requests'])")
python -c "import json,sys;print(json.dumps({'step':'pg_down','proposal_id':sys.argv[1],'response':sys.argv[2][:300],'requests_after_recovery':int(sys.argv[3]),'pass':int(sys.argv[3])==0 and 'HTTP200' not in sys.argv[2]},ensure_ascii=False))" "$pid" "$resp" "$cnt" | tee -a $OUT
curl -s $AUTH -X POST -H 'Content-Type: application/json' -d '{}' $SIM_HOST/fault/clear >/dev/null
say "끝"
