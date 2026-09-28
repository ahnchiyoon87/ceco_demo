#!/usr/bin/env bash
# 백본 ② 기동·기능 한 바퀴 (EXP-BB). 결과: experiments/EXP-BB/stage2_<profile>.json (+ raw/)
#   harness/backbonebench/stage2.sh <profile>            # 예: kafka43
#   DURATION=120 VARIANTS="base x10 scale restart" harness/backbonebench/stage2.sh kafka42
# 변형: base = 12태그×1장치×1Hz(V1 정상) · x10 = 1장치×10Hz(R08 배수) · scale = 10장치×1Hz · restart = base + 도중 브로커 재시작(R03)
# 가드: rot-iiot/rot-ai 컨테이너가 떠 있으면 거부(FORCE=1 로 무시). 끝나면 down -v 로 벤치 볼륨까지 지운다(KEEP=1 이면 유지).
set -uo pipefail
cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1
source harness/benchcommon/guard.sh

prof=${1:?profile: kafka39 kafka43 kafka42 kafka41 automq tansu nats pulsar rabbitmq iggy rocketmq mqtt}
DURATION=${DURATION:-120}
VARIANTS=${VARIANTS:-"base x10 scale restart"}
F=harness/backbonebench/compose.yml
DC="docker compose -f $F"
RAW=experiments/EXP-BB/raw; mkdir -p "$RAW/telegraf"

case $prof in
  kafka39|kafka43|kafka42|kafka41) adapter=kafka; svc=$prof; kafka_like=1 ;;
  automq)   adapter=kafka; svc=automq; kafka_like=1 ;;
  tansu)    adapter=kafka; svc=tansu; kafka_like=1 ;;
  nats)     adapter=nats; svc=nats; kafka_like=0 ;;
  pulsar)   adapter=pulsar; svc=pulsar; kafka_like=0 ;;
  rabbitmq) adapter=rabbitmq-stream; svc=rabbitmq; kafka_like=0 ;;
  iggy)     adapter=iggy; svc=iggy; kafka_like=0 ;;
  rocketmq) adapter=rocketmq; svc=rocketmq-broker; kafka_like=0 ;;
  mqtt)     adapter=mqtt; svc=mosquitto; kafka_like=0 ;;
  *) echo "unknown profile $prof"; exit 2 ;;
esac

# 다른 벤치 프로파일이 떠 있으면 거부(한 번에 하나)
if [ -n "$(docker ps -q --filter label=com.docker.compose.project=backbonebench)" ]; then
  echo "backbonebench 컨테이너가 이미 떠 있음 — 먼저 down"; exit 4; fi

$DC --profile tools build client >/dev/null || { echo "client build 실패"; exit 5; }
$DC --profile "$prof" up -d || { echo "up 실패"; $DC --profile "$prof" logs --tail 50; exit 6; }
docker compose -f $F --profile "$prof" images --format json > "$RAW/images_${prof}.json" 2>/dev/null
docker compose -f $F --profile "$prof" images | tail -n +2 | awk '{print $2":"$3" "$4}' > "$RAW/images_${prof}.txt"

# 기동 대기: 헬스체크 있는 서비스는 healthy, 없으면 90초 안 컨테이너 실행 + 클라이언트 setup 재시도(60×2초)에 맡긴다
t0=$(date +%s)
for i in $(seq 1 120); do
  st=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "backbonebench-$svc-1" 2>/dev/null)
  [ "$st" = healthy ] || [ "$st" = running ] && break; sleep 2
done
echo "{\"profile\":\"$prof\",\"svc\":\"$svc\",\"state\":\"$st\",\"startup_s\":$(( $(date +%s) - t0 ))}" > "$RAW/${prof}_startup.json"

if [ "$prof" = rocketmq ]; then   # FIFO 토픽(6큐)·순서 소비 그룹을 미리 만든다
  MQ="docker exec backbonebench-rocketmq-broker-1 sh mqadmin"
  sleep 15
  $MQ updateTopic -n rocketmq-namesrv:9876 -c DefaultCluster -t sensor_telemetry_raw -r 6 -w 6 -a +message.type=FIFO
  for v in $VARIANTS; do for g in bb-live-$v bb-replay-$v; do
    $MQ updateSubGroup -n rocketmq-namesrv:9876 -c DefaultCluster -g $g -o true; done; done
  # 시각 재생 핸드셰이크 감시(클라이언트가 .replay_request 를 쓰면 resetOffsetByTime 실행)
  ( for i in $(seq 1 3000); do
      for r in "$RAW"/${prof}_*.replay_request; do [ -e "$r" ] || continue
        d="${r%.replay_request}.replay_done"; [ -e "$d" ] && continue
        g=$(sed 's/.*"group": "\([^"]*\)".*/\1/' "$r"); t=$(sed 's/.*"t_ms": \([0-9]*\).*/\1/' "$r")
        $MQ resetOffsetByTime -n rocketmq-namesrv:9876 -g "$g" -t sensor_telemetry_raw -s "$t" > "${r%.replay_request}.reset.log" 2>&1
        touch "$d"; done; sleep 1; done ) &
  watcher=$!
fi

CL="$DC --profile tools run --rm -T client python /repo/harness/backbonebench/bb_stage2.py"
for v in $VARIANTS; do
  case $v in
    base)    args="--devices 1 --hz 1" ;;
    x10)     args="--devices 1 --hz 10" ;;
    scale)   args="--devices 10 --hz 1" ;;
    restart) args="--devices 1 --hz 1 --restart-note host-restart-at-40s --drain 120" ;;
  esac
  harness/sample_stats.sh "$RAW/stats_${prof}_${v}.csv" $(( DURATION + 30 )) "^backbonebench-" &
  sp=$!
  if [ "$v" = restart ]; then
    ( sleep 45; echo "$(date +%s.%N) restart $svc" >> "$RAW/${prof}_restart_actions.log"
      docker restart -t 10 "backbonebench-$svc-1" >> "$RAW/${prof}_restart_actions.log" 2>&1 ) &
  fi
  $CL run --profile "$prof" --adapter $adapter --variant $v --duration "$DURATION" $args --overwrite 2>&1 | grep -v " Container " | tail -3
  wait $sp
  wait
done

if [ "$kafka_like" = 1 ] && [ "${TELEGRAF:-1}" = 1 ]; then
  rm -f "$RAW/telegraf/${prof}_in_"*.jsonl
  BB_PROFILE=$prof $DC --profile "$prof" --profile telegraf up -d telegraf-out telegraf-in-v1cfg telegraf-in-kver
  sleep 20
  $CL telegraf --profile "$prof" 2>&1 | tail -2
  for s in telegraf-out telegraf-in-v1cfg telegraf-in-kver; do
    docker logs "backbonebench-$s-1" > "$RAW/telegraf/${prof}_${s}.log" 2>&1; done
fi

[ -n "${watcher:-}" ] && kill $watcher 2>/dev/null
$DC --profile "$prof" logs --no-color > "$RAW/${prof}_broker.log" 2>&1
$CL summarize --profile "$prof" 2>&1 | tail -1
if [ "${KEEP:-0}" != 1 ]; then $DC --profile "$prof" --profile telegraf down -v --remove-orphans >/dev/null 2>&1; fi
