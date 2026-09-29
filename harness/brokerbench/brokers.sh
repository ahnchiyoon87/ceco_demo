#!/usr/bin/env bash
# 브로커 벤치 후보 표(stage2_new.sh·stage4_mosq.sh 가 source). bb_broker <이름> 이 변수를 채운다.
#   PROFILE(compose 프로파일, 측정 완료 4종은 없음) · SVC(기동할 서비스들) · IMAGES · BENV(docker compose run -e 인자)
#   STATS(자원 샘플 정규식) · READY_S(기동 대기 상한 초)
bb_broker() {
  B=$1; PROFILE=$1; SVC=$1; BENV=""; READY_S=120; STATS="^brokerbench-$1-"
  case "$B" in
    emqx)      PROFILE=""; IMAGES="emqx/emqx:5.8.6" ;;                        # V1 기준 버전
    mosquitto) PROFILE=""; IMAGES="eclipse-mosquitto:2.1.2-alpine" ;;          # 조건부 채택(#56)
    nanomq)    PROFILE=""; IMAGES="emqx/nanomq:0.25.6" ;;                      # 탈락(#48) — 재측정 안 함
    hivemq)    PROFILE=""; IMAGES="hivemq/hivemq-ce:2026.5" ;;                 # 탈락(#48) — 재측정 안 함
    rmqtt)     IMAGES="rmqtt/rmqtt:0.24.0" ;;
    tbmq)      IMAGES="thingsboard/tbmq:2.4.0 postgres:17 apache/kafka:4.3.1 valkey/valkey:8.0.11-alpine"
               SVC="tbmq tbmq-postgres tbmq-kafka tbmq-valkey"; STATS="^brokerbench-tbmq"; READY_S=300
               BENV="-e BENCH_WS_PORT=8084" ;;
    bifromq)   IMAGES="apache/bifromq:4.0.0-incubating"; BENV="-e BENCH_WS_PORT=80"; READY_S=180 ;;
    rabbitmq)  IMAGES="rabbitmq:4.3.6-management-alpine"; READY_S=180 ;;
    lavinmq)   IMAGES="cloudamqp/lavinmq:2.10.0"; BENV="-e BENCH_MQTT_USER=guest -e BENCH_MQTT_PASS=guest -e BENCH_WS_PORT=15672" ;;
    artemis)   IMAGES="apache/artemis:2.57.0"; BENV="-e BENCH_WS_PORT=61616"; READY_S=180 ;;
    activemq)  IMAGES="apache/activemq:6.3.2"; READY_S=180 ;;
    comqtt)    IMAGES="ghcr.io/wind-c/comqtt:2.6.5" ;;
    robustmq)  IMAGES="ghcr.io/robustmq/robustmq:v0.4.11"; BENV="-e BENCH_MQTT_USER=admin -e BENCH_MQTT_PASS=robustmq" ;;
    mochi)     IMAGES="mochimqtt/server:2.7.9" ;;
    nats)      IMAGES="nats:2.15.0-alpine" ;;
    hivemq-edge) IMAGES="hivemq/hivemq-edge:2026.14"; READY_S=180 ;;
    *) echo "알 수 없는 브로커: $B" >&2; return 1 ;;
  esac
}
BB_NEW="rmqtt tbmq bifromq rabbitmq lavinmq artemis activemq comqtt robustmq mochi nats hivemq-edge"
BB="docker compose -f harness/brokerbench/compose.yml"

# bb_up <broker> : 해당 브로커만 기동하고 MQTT 접속이 될 때까지 기다린다(실패 = ② 기동 탈락, 로그 보관)
bb_up() {
  bb_broker "$1" || exit 1
  bench_require_images $IMAGES python:3.12.8-slim
  $BB ${PROFILE:+--profile $PROFILE} up -d $SVC || exit 6
  $BB --profile tools run --rm -T $BENV client python /repo/harness/brokerbench/wait_mqtt.py --broker "$B" --timeout "$READY_S" \
    || { mkdir -p experiments/EXP-130/raw; $BB ${PROFILE:+--profile $PROFILE} logs --no-color $SVC > "experiments/EXP-130/raw/logs_${B}_up_$(date +%m%d%H%M).txt" 2>&1; echo "[broker] $B 기동·접속 실패"; exit 7; }
}
bb_down() {
  bb_broker "$1" || return 1
  $BB ${PROFILE:+--profile $PROFILE} rm -s -f -v $SVC >/dev/null 2>&1
}

# run_all_stage2.sh 가 브로커 이름을 "실행 접두사" 자리에 넘기는 호출(#104 도구 결함) — 그대로면 호출마다 12종 전체를 다시 돈다.
# 인자가 브로커 이름 하나뿐이면 접두사 b1·목록 = 그 브로커로 바꾸고, 이미 잰(또는 기동 실패 기록이 있는) 브로커는 건너뛴다.
if [ "${BASH_SOURCE[1]##*/}" = "stage2_new.sh" ] && [ $# -eq 1 ] && case " $BB_NEW " in *" $1 "*) true;; *) false;; esac; then
  if ls experiments/EXP-130/raw/${1}_normal_*n.json >/dev/null 2>&1 || ls experiments/EXP-130/raw/logs_${1}_up_* >/dev/null 2>&1; then
    echo "[broker] $1 이미 측정됨 → 건너뜀"; exit 0
  fi
  set -- b1 "$1"
fi
