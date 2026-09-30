#!/bin/bash
# [측정] 엣지 후보 하나를 잰다(HANDOFF §2-3 결정 ①). 같은 가상설비·PLC·OT 허브에 붙은 상태에서 돌린다.
#   bash experiments/EDGE-CMP/run_edge.sh <이름> "<엣지 컨테이너들(공백 구분)>"
#   예) bash experiments/EDGE-CMP/run_edge.sh nodered "rot-base-edge-1"
set -u
export MSYS_NO_PATHCONV=1
NAME=$1; EDGE_CS=$2
D=experiments/EDGE-CMP/$NAME; mkdir -p $D
REPO="D:/work/study/scada-rotation"
set -a; . ./.env; set +a
ENVS="-e MQTT_VIEWER_PASSWORD -e MQTT_FUXA_PASSWORD -e MQTT_GATEWAY_PASSWORD -e PYTHONUTF8=1"
LOG=$D/run.log
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a $LOG; }
tool(){ # tool <이름> <인자…> : ot-net + it-net 에 붙은 측정 도구 컨테이너
  local n=edgecmp-$1; shift
  docker rm -f $n >/dev/null 2>&1
  docker create --name $n --network rot-base_ot-net $ENVS -v $REPO:/repo -w /repo e2e-client:1.1 python -u harness/e2e/edge_compare.py "$@" >/dev/null
  docker network connect rot-base_it-net $n
  docker start -a $n; docker rm $n >/dev/null
}
mem(){ docker stats --no-stream --format '{{.Name}} {{.MemUsage}}' $EDGE_CS | tee $D/mem_$1.txt | awk '{v=$2; if (v ~ /GiB/) {sub(/GiB/,"",v); v*=1024} else sub(/MiB/,"",v); s+=v} END {printf "합계 %.1f MiB\n", s}' | tee -a $LOG; }

say "== $NAME 엣지 측정 시작 (컨테이너: $EDGE_CS)"
sleep 20
mem steady
say "1) 정상 3분: 누락·지연"
tool rec record --seconds 180 --name ${NAME}-steady --out /repo/$D/steady.json | tee -a $LOG
tool an analyze --inp /repo/$D/steady.json --out /repo/$D/steady_result.json | tee -a $LOG
say "2) 운전원 명령 왕복 10회"
tool cmd command --out /repo/$D/command.json | tee -a $LOG
say "3) OT 작업 요청 수신기"
tool rcv receiver --out /repo/$D/receiver.json | tee -a $LOG
for i in 1 2 3; do
  say "4-$i) OT 허브 10초 정지 → 재기동"
  ( tool rec record --seconds 75 --name ${NAME}-out$i --out /repo/$D/outage_$i.json >> $LOG 2>&1 ) &
  RP=$!
  sleep 20
  stop_at=$(python -c "import time;print(time.time())"); docker stop rot-base-ot-hub-1 >/dev/null
  sleep 10
  docker start rot-base-ot-hub-1 >/dev/null; restart_at=$(python -c "import time;print(time.time())")
  wait $RP
  tool an analyze --inp /repo/$D/outage_$i.json --out /repo/$D/outage_${i}_result.json --events "{\"stop_at\":$stop_at,\"restart_at\":$restart_at}" | tee -a $LOG
  sleep 10
done
for i in 1 2 3; do
  say "5-$i) 엣지 재시작 → 사람 손 없이 복귀"
  ( tool rec record --seconds 75 --name ${NAME}-rs$i --out /repo/$D/restart_$i.json >> $LOG 2>&1 ) &
  RP=$!
  sleep 20
  stop_at=$(python -c "import time;print(time.time())"); docker restart $EDGE_CS >/dev/null; restart_at=$(python -c "import time;print(time.time())")
  wait $RP
  tool an analyze --inp /repo/$D/restart_$i.json --out /repo/$D/restart_${i}_result.json --events "{\"stop_at\":$stop_at,\"restart_at\":$restart_at}" | tee -a $LOG
  sleep 10
done
mem end
say "== $NAME 끝"
