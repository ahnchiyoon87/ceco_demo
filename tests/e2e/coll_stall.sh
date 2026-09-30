#!/bin/bash
# [측정 도구] IT 수집기 망 끊김 → 복귀 뒤 DMZ→Kafka 전달이 멈추는지 되풀이해 재현한다(재시작 복구 coll #1 원인 조사).
#   bash tests/e2e/coll_stall.sh <EXP> [최대 회수]   멈추면 SIGQUIT 로 고루틴 덤프를 남기고 끝낸다(컨테이너는 unless-stopped 로 다시 뜬다).
set -u
export MSYS_NO_PATHCONV=1
EXP=$1; N=${2:-8}; P=${COMPOSE_PROJECT_NAME:-rot-base}; C=$P-it-collector-1; K=$P-kafka-1
D=experiments/$EXP/coll_stall; mkdir -p $D; LOG=$D/run.log
say(){ echo "[$(date +%T)] $*" | tee -a $LOG; }
off(){ docker exec $K /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server localhost:9092 --topic sensor.telemetry.raw 2>/dev/null | awk -F: '{s+=$3} END{print s+0}'; }
for i in $(seq 1 $N); do
  IP=$(docker inspect -f "{{(index .NetworkSettings.Networks \"${P}_it-net\").IPAddress}}" $C)   # 같은 주소로 다시 붙인다(실제 망 끊김)
  docker network disconnect ${P}_it-net $C; sleep 10; docker network connect --alias it-collector --ip $IP ${P}_it-net $C
  sleep 60; a=$(off); sleep 15; b=$(off)
  say "#$i 복귀 60 s 뒤 raw 오프셋 15 s 증가 $((b - a))"
  if [ $((b - a)) -eq 0 ]; then
    say "#$i 멈춤 — 고루틴 덤프"
    since=$(date -u +%Y-%m-%dT%H:%M:%SZ)
    docker kill -s QUIT $C >/dev/null; sleep 5
    docker logs --since "$since" $C > $D/goroutines_$i.txt 2>&1
    say "덤프 $(wc -l < $D/goroutines_$i.txt)줄 → $D/goroutines_$i.txt"
    exit 0
  fi
done
say "== $N 회 모두 흐름 유지"
