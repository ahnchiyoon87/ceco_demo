#!/usr/bin/env bash
# 수집 벤치 프로파일 표(stage2.sh·stage4_*.sh 가 source). 한 줄 = 한 후보.
# 필드: IMAGES(pull 대상, 빌드 이미지는 BUILD) · CAND(자원 total 정규식) · MQTT_HOST · TOPIC · SHAPE · EGRESS(R02 단절 대상 컨테이너) · SETUP(기동 후 1회 명령)
#       DS_CONF·DS_IMAGE·DS_TOPIC: 하류 파서(결과 동등 판정, 09-29 결정). V1 모양이면 V1 Telegraf#1 원문, 아니면 후보별 적응 설정(설정만)
#       SETUP 은 UI 설정 제품도 스크립트로 재적용(09-29 결정: 재현 가능한 설정만 인정)
# 공통 컨테이너(시뮬레이터·벤치 Mosquitto·downstream)는 CAND 에 넣지 않는다(후보마다 같음). 예외: hivemq-edge 는 브로커 내장이라 Mosquitto 를 쓰지 않는다.

ING_COMMON_IMAGES="iiot/plant-simulator:1.0 eclipse-mosquitto:2.1.2-alpine telegraf:1.33-alpine python:3.12.8-slim"

ing_profile() {
  P=$1
  MQTT_HOST=mosquitto; TOPIC=edgex/telemetry; SHAPE=edgex; SETUP=""; BUILD=""; MQTT_USER=""; MQTT_PASS=""
  DS_CONF=v1-edgex.conf; DS_IMAGE=telegraf:1.33-alpine; DS_TOPIC=""
  case "$P" in
    edgex)        # V1 기준선(강제 교체 대상, 기준값 측정용)
      IMAGES="postgres:16.3-alpine3.20 eclipse-mosquitto:2.0.21 edgexfoundry/core-keeper:4.0.0 edgexfoundry/core-common-config-bootstrapper:4.0.0 edgexfoundry/core-metadata:4.0.0 edgexfoundry/core-data:4.0.0 edgexfoundry/core-command:4.0.0 edgexfoundry/device-modbus:4.0.0 edgexfoundry/app-service-configurable:4.0.0 edgexfoundry/edgex-ui:4.0.0"
      CAND='^ingestbench-edgex-'; EGRESS="ingestbench-edgex-app-mqtt-export-1" ;;
    telegraf)
      IMAGES="telegraf:1.40.1-alpine"; CAND='^ingestbench-telegraf-1$'; EGRESS="ingestbench-telegraf-1" ;;
    benthos-umh)
      IMAGES="ghcr.io/united-manufacturing-hub/benthos-umh:0.16.0"; CAND='^ingestbench-benthos-umh-'; EGRESS="ingestbench-benthos-umh-1" ;;
    hivemq-edge)  # 수집+브로커 통합(P-EB): 검사기·downstream 가 Edge 내장 브로커를 직접 구독
      IMAGES="hivemq/hivemq-edge:2026.14"; CAND='^ingestbench-hivemq-edge-'; EGRESS="ingestbench-hivemq-edge-1"
      MQTT_HOST=hivemq-edge; TOPIC='edgex/telemetry/#'; SHAPE=hivemq-edge
      DS_CONF=hivemq-edge.conf; DS_IMAGE=telegraf:1.40.1-alpine ;;
    neuron)
      IMAGES="emqx/neuron:2.13.0"; CAND='^ingestbench-neuron-'; EGRESS="ingestbench-neuron-1"; SHAPE=neuron
      DS_CONF=neuron.conf; DS_IMAGE=telegraf:1.40.1-alpine
      SETUP="python /repo/harness/ingestbench/neuron/setup.py --base http://neuron:7000" ;;
    nodered)
      IMAGES="nodered/node-red:5.0.7"; BUILD=nodered; CAND='^ingestbench-nodered-'; EGRESS="ingestbench-nodered-1" ;;
    tbgw)
      IMAGES="thingsboard/tb-gateway:3.8.5"; CAND='^ingestbench-tbgw-'; EGRESS="ingestbench-tbgw-1"
      TOPIC='v1/gateway/telemetry'; SHAPE=tbgw; DS_CONF=tbgw.conf; DS_IMAGE=telegraf:1.40.1-alpine ;;
    streampipes)  # UI 제품 — 설정은 streampipes/setup.py 가 파일(spec·내보낸 JSON)에서 REST 로 재적용
      IMAGES="apachestreampipes/backend:0.98.0 apachestreampipes/ui:0.98.0 apachestreampipes/extensions-all-iiot:0.98.0 couchdb:3.3.1 influxdb:2.6 nats:2.15.0-alpine"
      CAND='^ingestbench-streampipes-'; EGRESS="ingestbench-streampipes-extensions-all-iiot-1"; SHAPE=auto
      DS_CONF=streampipes.conf; DS_IMAGE=telegraf:1.40.1-alpine
      SETUP="python /repo/harness/ingestbench/streampipes/setup.py apply" ;;
    openremote)   # UI 제품 — openremote/setup.py 가 REST 로 에이전트·자산·서비스 사용자 생성. 내장 MQTT 구독(토픽에 client_id 필수)
      IMAGES="openremote/manager:1.31.1 openremote/keycloak:26.7.3.0 openremote/postgresql:17.9.0.1-slim openremote/proxy:3.2.19.0"
      CAND='^ingestbench-openremote-'; EGRESS="ingestbench-openremote-manager-1"; SHAPE=openremote
      MQTT_HOST=manager; TOPIC='master/{cid}/attribute/+/#'; MQTT_USER="master:ingestbench"; MQTT_PASS="ingestbench-secret"
      DS_CONF=openremote.conf; DS_IMAGE=telegraf:1.40.1-alpine; DS_TOPIC='master/downstream-ingestbench/attribute/+/#'
      SETUP="python /repo/harness/ingestbench/openremote/setup.py apply" ;;
    *) echo "알 수 없는 프로파일: $P (edgex telegraf benthos-umh hivemq-edge neuron nodered tbgw streampipes openremote)" >&2; return 1 ;;
  esac
}

ING_ALL="edgex telegraf benthos-umh hivemq-edge neuron nodered tbgw streampipes openremote"
