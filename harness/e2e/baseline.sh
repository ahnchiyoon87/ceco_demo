#!/bin/sh
# [측정 도구] 기준 버전 전체 측정(STRUCTURE E1·E3·E7·E11·E12, ROBUSTNESS R01~R03·R06~R09·R11).
#   sh harness/e2e/baseline.sh <EXP> <구조이름>   예) sh harness/e2e/baseline.sh EXP-000 V1
# R04·R05 = EXP-S09 재사용(+#81 실제 재현), R10 = EXP-L4 재사용, E2 = e2_complexity.py, E6·E9·E10 = 별도.
set -u
EXP=$1; NAME=$2
# 구조별 대상 컨테이너(같은 시험을 같은 방법으로, 이름만 다름). V1 기본값. 새 구조는 STRUCT=<이름> 으로 부르고 harness/e2e/struct_<이름>.sh 에 이름표를 둔다(옛 V2 예시는 git bdced23 의 struct_V2.sh).
STRUCT=${STRUCT:-V1}
BROKER_C=rot-emqx; BROKER_H=emqx; UPLINK_C=rot-edgex-app-mqtt-export; KAFKA_C=rot-kafka; TS_C=rot-influxdb
SINK_C=rot-telegraf-sink; FIX_C="rot-telegraf-bridge rot-telegraf-sink"; SUBMIT_C=rot-flink-job-submitter
export MSYS_NO_PATHCONV=1 COMPOSE_PATH_SEPARATOR=:
R=experiments/$EXP/raw; mkdir -p $R
LOG=experiments/$EXP/baseline_$NAME.log
REPO="D:/work/study/scada-rotation"
CLIENT="docker run --rm --network rot-iiot --add-host host.docker.internal:host-gateway --env-file .env -v $REPO:/repo -v $REPO/experiments:/experiments -w /repo e2e-client:1.2"   # e1.py 는 /experiments/<EXP>/raw 에 씀(#103 전엔 미연결 → 로그 요약 줄만 남음)
SCADA="docker compose --env-file .env --env-file .env.rotation"
AI="docker compose -p rot-ai --env-file ai-layer/.env.local --env-file .env.rotation -f ai-layer/compose.yml -f ai-layer/compose.scada.yml --profile knowledge"
# 구조 이름표는 기본값(SCADA·AI 포함) 뒤에 읽는다 — 앞에서 읽으면 V2 의 SCADA 가 V1 기본값으로 덮여 "V2 기동"이 V1 을 띄움(#125 실제 발생)
[ -f harness/e2e/struct_${STRUCT}.sh ] && . harness/e2e/struct_${STRUCT}.sh   # V1 이외 구조의 이름표
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a $LOG; }
ms(){ echo $(( $(date +%s) * 1000 )); }
complete(){ $CLIENT python harness/e2e/completeness.py --start-ms $1 --end-ms $2 --out /repo/$R/$3.json 2>&1 | tail -1 | tee -a $LOG; }
jobs_running(){ curl -s -m 10 http://127.0.0.1:37081/jobs/overview | python -c "import json,sys;print(sum(j['state']=='RUNNING' for j in json.load(sys.stdin)['jobs']))" 2>/dev/null | tr -d '
' || echo 0; }
ensure_jobs(){ n=$(jobs_running); if [ "$n" != 4 ]; then say "Flink 잡 $n 개 → 제출기 재실행"; docker start -a $SUBMIT_C >>$LOG 2>&1; fi; say "Flink RUNNING $(jobs_running)"; }
wait_flow(){ # 복구 판정 = 끝단(Influx)에 2분 연속 흐름(#97 오판 수정). JSON 한 줄 반환, recover_s=null 이면 스스로 복구 안 됨
  $CLIENT python harness/e2e/wait_flow.py --t0 $(date +%s) ${WF_ARGS:-} 2>/dev/null | tail -1; }
manual_fix(){ # 스스로 복구 못 한 경우만: 다음 시험 오염 방지용 수동 조치(기록 남김)
  say "수동 조치: 수집·저장 중계기 재시작 ($1)"; echo "$(date -Iseconds) $1 unrecovered -> docker restart $FIX_C" >> experiments/$EXP/manual_actions.log
  docker restart $FIX_C >>$LOG 2>&1; say "수동 조치 뒤 $(wait_flow)"; }

phase0(){
  say "P0 순수 기준 버전 복구"
  $SCADA -f docker-compose.yml -f docker-compose.edgex.yml -f docker-compose.timescale.yml up -d --no-build --no-deps plant-simulator >>$LOG 2>&1   # V2 설비(배속 기본값) — V1·V2 같은 설비(HANDOFF §3-6 "시간")
  docker start rot-grafana rot-edgex-ui rot-cadvisor rot-prometheus rot-alertmanager rot-kafka-exporter >>$LOG 2>&1
  docker stop rot-ai-embed-1 rot-ai-knowledge-1 rot-ai-graph-1 >>$LOG 2>&1
  docker run --rm -v rot-ai_graph-snap-A:/from:ro -v rot-ai_graph-data:/to alpine:3.22 sh -c "rm -rf /to/*; cp -a /from/. /to/"
  $AI up -d --no-build --wait graph work-db knowledge alarm-worker web >>$LOG 2>&1
  docker inspect rot-plant-simulator rot-ai-knowledge-1 --format '{{.Name}} {{.Config.Image}}' | tee -a $LOG
  ensure_jobs
}

# 구조 이름표가 자기 P0 를 주면 그것을 쓴다(V1 은 아래 phase0)
if [ "$(type -t phase0_$STRUCT 2>/dev/null)" = function ]; then eval "phase0(){ phase0_$STRUCT; }"; fi

phase1(){
  say "P1 정상 3분(E3·R09·E7·E12)"
  T0=$(ms)
  sh harness/sample_stats.sh $R/e3_${NAME}_stats.csv 180 '^rot-' &
  SPID=$!
  sleep 20
  $CLIENT python harness/e2e/security_probe.py --broker $BROKER_H --out /repo/$R/e12_${NAME}.json 2>&1 | tail -3 | tee -a $LOG
  $CLIENT python harness/e2e/screen_vs_history.py --n 10 --out /repo/$R/e7_${NAME}.json 2>&1 | tail -2 | tee -a $LOG
  wait $SPID
  complete $((T0 + 20000)) $(ms) r09_${NAME}
  say "P1 끝"
}

phase2(){
  say "P2 E1 알람→화면 10회 × 3"
  for k in 1 2 3; do
    $CLIENT python harness/e2e/e1.py --exp $EXP --run e1_${NAME}_$k --reps 10 --quiet-s 3 --sim http://plant-simulator:8080 \
      --mqtt $BROKER_H --kafka kafka:9092 --kafka-topic sensor.alerts --mqtt-topics ${E1_TOPICS:-scada/alerts/PT-101,scada/hmi/latest-alert} \
      --match THRESHOLD_USL --fault-duration 2 --incident-api http://host.docker.internal:38000/api/operations/incidents 2>&1 | tail -1 | tee -a $LOG
  done
}

rtest(){ # $1 이름 $2 주입 명령 $3 복구 명령 $4 대기초
  for k in $(seq 1 ${REPS:-3}); do
    T0=$(ms); say "$1 #$k 주입"; sh -c "$2" >>$LOG 2>&1; sleep $4; sh -c "$3" >>$LOG 2>&1
    wf=$(wait_flow); say "$1 #$k 복구 $wf"; ensure_jobs
    complete $((T0 - 10000)) $(ms) ${1}_${NAME}_${RUN:-}$k
    echo "{\"test\":\"$1\",\"run\":\"${RUN:-}\",\"k\":$k,\"flow\":$wf}" >> $R/robustness_${NAME}.jsonl
    case "$wf" in *'"recover_s": null'*) manual_fix "$1 #$k";; esac
  done
}

phase3(){
  say "P3 비정상"
  T="${TESTS:-r01 r02 r03 r06 r07 r08 r11 e11}"; has(){ case " $T " in *" $1 "*) return 0;; esac; return 1; }
  has r01 && REPS=${RREPS:-3} rtest r01 "docker stop $BROKER_C" "docker start $BROKER_C" 10
  has r02 && REPS=${RREPS:-3} rtest r02 "docker network disconnect rot-iiot $UPLINK_C" "docker network connect rot-iiot $UPLINK_C" 10
  has r03 && REPS=${RREPS:-3} rtest r03 "docker restart $KAFKA_C" "true" 1
  has r06 && REPS=1 rtest r06 "docker stop $TS_C" "docker start $TS_C" 30
  if has r07; then
  # R07: 업무 DB 다운 중 운전원 명령 → 설비에 쓰지 않아야(fail-closed)
  before=$(curl -s http://127.0.0.1:37080/state); docker stop rot-ai-work-db-1 >>$LOG 2>&1
  resp=$(curl -s -m 20 -X POST -H 'Content-Type: application/json' -d "{\"request_id\":\"$(python -c 'import uuid;print(uuid.uuid4())')\",\"target\":\"valve_open_sp\",\"value\":50}" http://127.0.0.1:38000/api/operations/simulation/control)
  after=$(curl -s http://127.0.0.1:37080/state); docker start rot-ai-work-db-1 >>$LOG 2>&1
  python -c "import json,sys;b=json.loads(sys.argv[1]);a=json.loads(sys.argv[2]);print(json.dumps({'test':'r07','response':sys.argv[3][:300],'valve_before':b['commands']['valve_open_sp'],'valve_after':a['commands']['valve_open_sp']},ensure_ascii=False))" "$before" "$after" "$resp" | tee -a $LOG >> $R/robustness_${NAME}.jsonl
  fi
  if has r08; then
  # R08: 10배 과부하 10분, 그동안 E1 20회
  T0=$(ms); say "r08 과부하 시작"
  $CLIENT python harness/e2e/loadgen.py --mqtt $BROKER_H ${LOAD_KAFKA:+--kafka $LOAD_KAFKA} --devices 10 --seconds 60 >>$LOG 2>&1 &
  LPID=$!; sleep 10
  $CLIENT python harness/e2e/e1.py --exp $EXP --run e1_${NAME}_r08 --reps 5 --quiet-s 3 --sim http://plant-simulator:8080 \
      --mqtt $BROKER_H --kafka kafka:9092 --kafka-topic sensor.alerts --mqtt-topics ${E1_TOPICS:-scada/alerts/PT-101,scada/hmi/latest-alert} \
      --match THRESHOLD_USL --fault-duration 2 2>&1 | tail -1 | tee -a $LOG
  wait $LPID; wf=$(wait_flow); say "r08 끝, 흐름 $wf"
  complete $T0 $(ms) r08_${NAME}_${RUN:-}1
  echo "{\"test\":\"r08\",\"run\":\"${RUN:-}\",\"k\":1,\"flow\":$wf}" >> $R/robustness_${NAME}.jsonl
  fi
  if has r11; then
  # R11: 설비 통신 끊김(dropout 15초)
  T0=$(ms); curl -s -X POST -H 'Content-Type: application/json' -d '{"scenario":"dropout"}' http://127.0.0.1:37080/fault >>$LOG; sleep 20
  complete $((T0 - 10000)) $(ms) r11_${NAME}_${RUN:-}1
  fi
  if has e11; then
  # E11: 감시가 컨테이너 정지·탐지기 정지를 잡는가
  docker kill $SINK_C >>$LOG 2>&1; sleep 90
  curl -s http://127.0.0.1:37093/api/v2/alerts > $R/e11_container_${NAME}${RUN:-}.json; docker start $SINK_C >>$LOG 2>&1
  for j in $(curl -s http://127.0.0.1:37081/jobs/overview | python -c "import json,sys;[print(j['jid']) for j in json.load(sys.stdin)['jobs'] if j['state']=='RUNNING']" | tr -d '
'); do curl -s -X PATCH "http://127.0.0.1:37081/jobs/$j?mode=cancel" >/dev/null; done
  sleep 90; curl -s http://127.0.0.1:37093/api/v2/alerts > $R/e11_detector_${NAME}${RUN:-}.json; ensure_jobs
  fi
  say "P3 끝"
}

say "== baseline $NAME 시작"
for ph in ${PHASES:-0 1 2 3}; do phase$ph; done
say "== baseline $NAME 끝"
