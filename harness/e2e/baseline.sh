#!/bin/sh
# [측정 도구] 기준 버전 전체 측정(STRUCTURE E1·E3·E7·E11·E12, ROBUSTNESS R01~R03·R06~R09·R11).
#   sh harness/e2e/baseline.sh <EXP> <구조이름>   예) sh harness/e2e/baseline.sh EXP-000 V1
# R04·R05 = EXP-S09 재사용(+#81 실제 재현), R10 = EXP-L4 재사용, E2 = e2_complexity.py, E6·E9·E10 = 별도.
set -u
EXP=$1; NAME=$2
export MSYS_NO_PATHCONV=1 COMPOSE_PATH_SEPARATOR=:
R=experiments/$EXP/raw; mkdir -p $R
LOG=experiments/$EXP/baseline_$NAME.log
REPO="D:/work/study/scada-rotation"
CLIENT="docker run --rm --network rot-iiot --add-host host.docker.internal:host-gateway --env-file .env -v $REPO:/repo -w /repo e2e-client:1.0"
SCADA="docker compose --env-file .env --env-file .env.rotation"
AI="docker compose -p rot-ai --env-file ai-layer/.env.local --env-file .env.rotation -f ai-layer/compose.yml -f ai-layer/compose.scada.yml --profile knowledge"
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a $LOG; }
ms(){ echo $(( $(date +%s) * 1000 )); }
complete(){ $CLIENT python harness/e2e/completeness.py --start-ms $1 --end-ms $2 --out /repo/$R/$3.json 2>&1 | tail -1 | tee -a $LOG; }
jobs_running(){ curl -s -m 10 http://127.0.0.1:37081/jobs/overview | python -c "import json,sys;print(sum(j['state']=='RUNNING' for j in json.load(sys.stdin)['jobs']))" 2>/dev/null || echo 0; }
ensure_jobs(){ n=$(jobs_running); if [ "$n" != 4 ]; then say "Flink 잡 $n 개 → 제출기 재실행"; docker start -a rot-flink-job-submitter >>$LOG 2>&1; fi; say "Flink RUNNING $(jobs_running)"; }
wait_flow(){ # 텔레메트리가 Influx 에 다시 들어올 때까지(복구 시간) — 초 단위 반환
  t0=$(date +%s); while :; do n=$(curl -s -m 5 "http://127.0.0.1:37080/state" >/dev/null && $CLIENT python -c "
import os,json,urllib.request,urllib.parse,time
q='from(bucket:\"'+os.environ['INFLUX_BUCKET']+'\") |> range(start:-3s) |> filter(fn:(r)=>r._measurement==\"process_raw\" and r.tag==\"TT-101\") |> count()'
r=urllib.request.Request('http://influxdb:8086/api/v2/query?'+urllib.parse.urlencode({'org':os.environ['INFLUX_ORG']}),json.dumps({'query':q,'type':'flux'}).encode(),{'Authorization':'Token '+os.environ['INFLUX_TOKEN'],'Content-Type':'application/json','Accept':'application/csv'})
try: print(1 if ',_value' in urllib.request.urlopen(r,timeout=5).read().decode() else 0)
except Exception: print(0)" 2>/dev/null); [ "$n" = 1 ] && break; [ $(( $(date +%s) - t0 )) -gt 600 ] && break; sleep 2; done; echo $(( $(date +%s) - t0 )); }

phase0(){
  say "P0 순수 기준 버전 복구"
  $SCADA -f docker-compose.yml -f docker-compose.edgex.yml -f docker-compose.timescale.yml up -d --no-build --no-deps plant-simulator >>$LOG 2>&1   # V2 설비(배속 기본값) — V1·V2 같은 설비(QUESTIONS §1 "시간")
  docker start rot-grafana rot-edgex-ui rot-cadvisor rot-prometheus rot-alertmanager rot-kafka-exporter >>$LOG 2>&1
  docker stop rot-ai-embed-1 rot-ai-knowledge-1 rot-ai-graph-1 >>$LOG 2>&1
  docker run --rm -v rot-ai_graph-snap-A:/from:ro -v rot-ai_graph-data:/to alpine:3.22 sh -c "rm -rf /to/*; cp -a /from/. /to/"
  $AI up -d --no-build --wait graph work-db knowledge alarm-worker web >>$LOG 2>&1
  docker inspect rot-plant-simulator rot-ai-knowledge-1 --format '{{.Name}} {{.Config.Image}}' | tee -a $LOG
  ensure_jobs
}

phase1(){
  say "P1 정상 3분(E3·R09·E7·E12)"
  T0=$(ms)
  sh harness/sample_stats.sh $R/e3_${NAME}_stats.csv 180 '^rot-' &
  SPID=$!
  sleep 20
  $CLIENT python harness/e2e/security_probe.py --out /repo/$R/e12_${NAME}.json 2>&1 | tail -3 | tee -a $LOG
  $CLIENT python harness/e2e/screen_vs_history.py --n 10 --out /repo/$R/e7_${NAME}.json 2>&1 | tail -2 | tee -a $LOG
  wait $SPID
  complete $((T0 + 20000)) $(ms) r09_${NAME}
  say "P1 끝"
}

phase2(){
  say "P2 E1 알람→화면 10회 × 3"
  for k in 1 2 3; do
    $CLIENT python harness/e2e/e1.py --exp $EXP --run e1_${NAME}_$k --reps 10 --quiet-s 3 --sim http://plant-simulator:8080 \
      --mqtt emqx --kafka kafka:9092 --kafka-topic sensor.alerts --mqtt-topics scada/alerts/PT-101,scada/hmi/latest-alert \
      --match THRESHOLD_USL --fault-duration 2 --incident-api http://host.docker.internal:38000/api/operations/incidents 2>&1 | tail -1 | tee -a $LOG
  done
}

rtest(){ # $1 이름 $2 주입 명령 $3 복구 명령 $4 대기초
  for k in $(seq 1 ${REPS:-3}); do
    T0=$(ms); say "$1 #$k 주입"; sh -c "$2" >>$LOG 2>&1; sleep $4; sh -c "$3" >>$LOG 2>&1
    rec=$(wait_flow); say "$1 #$k 복구 ${rec}s"; ensure_jobs; sleep 15
    complete $((T0 - 10000)) $(ms) ${1}_${NAME}_$k
    echo "{\"test\":\"$1\",\"k\":$k,\"recover_s\":$rec}" >> $R/robustness_${NAME}.jsonl
  done
}

phase3(){
  say "P3 비정상"
  REPS=1 rtest r01 "docker stop rot-emqx" "docker start rot-emqx" 10
  REPS=1 rtest r02 "docker network disconnect rot-iiot rot-edgex-app-mqtt-export" "docker network connect rot-iiot rot-edgex-app-mqtt-export" 10
  REPS=1 rtest r03 "docker restart rot-kafka" "true" 1
  REPS=1 rtest r06 "docker stop rot-influxdb" "docker start rot-influxdb" 30
  # R07: 업무 DB 다운 중 운전원 명령 → 설비에 쓰지 않아야(fail-closed)
  before=$(curl -s http://127.0.0.1:37080/state); docker stop rot-ai-work-db-1 >>$LOG 2>&1
  resp=$(curl -s -m 20 -X POST -H 'Content-Type: application/json' -d "{\"request_id\":\"$(python -c 'import uuid;print(uuid.uuid4())')\",\"target\":\"valve_open_sp\",\"value\":50}" http://127.0.0.1:38000/api/operations/simulation/control)
  after=$(curl -s http://127.0.0.1:37080/state); docker start rot-ai-work-db-1 >>$LOG 2>&1
  python -c "import json,sys;b=json.loads(sys.argv[1]);a=json.loads(sys.argv[2]);print(json.dumps({'test':'r07','response':sys.argv[3][:300],'valve_before':b['commands']['valve_open_sp'],'valve_after':a['commands']['valve_open_sp']},ensure_ascii=False))" "$before" "$after" "$resp" | tee -a $LOG >> $R/robustness_${NAME}.jsonl
  # R08: 10배 과부하 10분, 그동안 E1 20회
  T0=$(ms); say "r08 과부하 시작"
  $CLIENT python harness/e2e/loadgen.py --devices 10 --seconds 60 >>$LOG 2>&1 &
  LPID=$!; sleep 10
  $CLIENT python harness/e2e/e1.py --exp $EXP --run e1_${NAME}_r08 --reps 5 --quiet-s 3 --sim http://plant-simulator:8080 \
      --mqtt emqx --kafka kafka:9092 --kafka-topic sensor.alerts --mqtt-topics scada/alerts/PT-101,scada/hmi/latest-alert \
      --match THRESHOLD_USL --fault-duration 2 2>&1 | tail -1 | tee -a $LOG
  wait $LPID; rec=$(wait_flow); say "r08 끝, 흐름 ${rec}s"; sleep 15
  complete $T0 $(ms) r08_${NAME}_1
  # R11: 설비 통신 끊김(dropout 15초)
  T0=$(ms); curl -s -X POST -H 'Content-Type: application/json' -d '{"scenario":"dropout"}' http://127.0.0.1:37080/fault >>$LOG; sleep 20
  complete $((T0 - 10000)) $(ms) r11_${NAME}_1
  # E11: 감시가 컨테이너 정지·탐지기 정지를 잡는가
  docker kill rot-telegraf-sink >>$LOG 2>&1; sleep 90
  curl -s http://127.0.0.1:37093/api/v2/alerts > $R/e11_container_${NAME}.json; docker start rot-telegraf-sink >>$LOG 2>&1
  for j in $(curl -s http://127.0.0.1:37081/jobs/overview | python -c "import json,sys;[print(j['jid']) for j in json.load(sys.stdin)['jobs'] if j['state']=='RUNNING']"); do curl -s -X PATCH "http://127.0.0.1:37081/jobs/$j?mode=cancel" >/dev/null; done
  sleep 90; curl -s http://127.0.0.1:37093/api/v2/alerts > $R/e11_detector_${NAME}.json; ensure_jobs
  say "P3 끝"
}

say "== baseline $NAME 시작"
for ph in ${PHASES:-0 1 2 3}; do phase$ph; done
say "== baseline $NAME 끝"
