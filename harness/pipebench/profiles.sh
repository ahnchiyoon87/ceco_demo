#!/usr/bin/env bash
# 중계 벤치 프로파일 표(stage2.sh 가 source). pipe_profile <이름> 이 변수를 채운다.
#   IMAGES · CAND(자원 total 정규식) · MQTT_HOST(입력 A 발행·중계 ③ 구독) · SHAPE_IN(edgex|lite) · SETUP(UI 제품도 REST 재적용) · BUILD · NEED_KAFKA4
PIPE_COMMON_IMAGES="emqx/emqx:5.8.6 influxdb:2.7 python:3.12.8-slim"
pipe_profile() {
  P=$1; MQTT_HOST=emqx; BROKER_CTR=pipebench-emqx-1; SHAPE_IN=edgex; SETUP=""; BUILD=""; NEED_KAFKA4=0; CAND="^pipebench-$1-"
  case "$P" in
    v1)            IMAGES="telegraf:1.33-alpine" ;;                              # V1 기준(Telegraf 1.33 ×3, 강제 교체 대상)
    telegraf140x3) IMAGES="telegraf:1.40.1-alpine" ;;
    telegraf140x1) IMAGES="telegraf:1.40.1-alpine"; CAND='^pipebench-telegraf140x1-1$' ;;
    telegraf140v2) IMAGES="telegraf:1.40.1-alpine" ;;                                   # V2 조립용(#114)
    telegraf140x1k4) IMAGES="telegraf:1.40.1-alpine"; CAND='^pipebench-telegraf140x1k4-1$' ;;
    bento)         IMAGES="ghcr.io/warpstreamlabs/bento:1.21.2" ;;
    rpconnect)     IMAGES="docker.redpanda.com/redpandadata/connect:4.111.0" ;;
    benthos-umh)   IMAGES="ghcr.io/united-manufacturing-hub/benthos-umh:0.16.0" ;;
    ekuiper)       IMAGES="lfedge/ekuiper:2.4.2"; SETUP="python /repo/harness/pipebench/ekuiper/setup.py" ;;
    vector)        IMAGES="timberio/vector:0.58.0-alpine" ;;
    nifi)          IMAGES="apache/nifi:2.12.0"; SETUP="python /repo/harness/pipebench/nifi/setup.py apply" ;;   # REST 로 흐름 재적용(09-29)
    kconnect)      IMAGES="apache/kafka:4.3.1 telegraf:1.40.1-alpine"; BUILD=kconnect; NEED_KAFKA4=1 ;;
    rmqtt-pc)      IMAGES="rmqtt/rmqtt:0.24.0 telegraf:1.40.1-alpine"; MQTT_HOST=rmqtt; BROKER_CTR=pipebench-rmqtt-pc-1; SHAPE_IN=lite ;;
    tbmq-pc)       IMAGES="thingsboard/tbmq:2.4.0 thingsboard/tbmq-integration-executor:2.4.0 postgres:17 valkey/valkey:8.0.11-alpine telegraf:1.40.1-alpine"
                   MQTT_HOST=tbmq; BROKER_CTR=pipebench-tbmq-pc-1; SHAPE_IN=lite; SETUP="python /repo/harness/pipebench/tbmq/setup.py apply" ;;   # REST 로 통합 재적용(09-29)
    *) echo "알 수 없는 프로파일: $P ($PIPE_ALL)" >&2; return 1 ;;
  esac
}
PIPE_ALL="v1 telegraf140x3 telegraf140v2 telegraf140x1 telegraf140x1k4 bento rpconnect benthos-umh ekuiper vector nifi kconnect rmqtt-pc tbmq-pc"
