#!/bin/bash
# [측정 도구] 새 베이스(compose.yml, 망 3개) 이름표. 다른 측정 스크립트가 `. harness/e2e/struct_base.sh` 로 읽는다.
# 측정 클라이언트는 솔루션 부품이 아니므로 OT·DMZ·IT 망 세 곳에 모두 붙여 각 지점을 같은 시계로 관측한다.
#   base_client python harness/e2e/e1.py ...        (저장소는 /repo, 증거는 /experiments)
set -u
export MSYS_NO_PATHCONV=1
P=${COMPOSE_PROJECT_NAME:-rot-base}
REPO=${REPO:-D:/work/study/scada-rotation}
CLIENT_IMG=${CLIENT_IMG:-e2e-client:1.2}
env_get(){ grep -E "^$1=" "$REPO/.env" | head -1 | cut -d= -f2-; }
SIM_INT=http://plant-sim:8080                       # 강사용 고장 주입 API(Basic 인증)
FUXA_INT=http://fuxa:1881
AI_INT=http://knowledge:8000/api/operations
SIM_HOST=http://127.0.0.1:$(env_get PORT_SIM_API)
AI_HOST=http://127.0.0.1:$(env_get PORT_AI_KNOWLEDGE)/api/operations
SIM_AUTH="$(env_get INSTRUCTOR_USER):$(env_get INSTRUCTOR_PASSWORD)"
C_PLANT=$P-plant-sim-1; C_PLC=$P-plc-1; C_OTHUB=$P-ot-hub-1; C_EDGE=$P-edge-1; C_FUXA=$P-fuxa-1
C_DMZB=$P-dmz-broker-1; C_DMZI=$P-dmz-influx-1; C_LOADER=$P-dmz-loader-1; C_GW=$P-dmz-gateway-1
C_KAFKA=$P-kafka-1; C_COLL=$P-it-collector-1; C_ITI=$P-it-influx-1; C_PG=$P-postgres-1
C_JM=$P-flink-jobmanager-1; C_TM=$P-flink-taskmanager-1; C_SUBMIT=$P-flink-job-submitter-1
C_KNOW=$P-knowledge-1; C_BUS=$P-business-1; C_DISP=$P-dispatcher-1; C_ROUTER=$P-router-1

# 측정 클라이언트: 이름 붙은 일회용 컨테이너를 만들고 세 망에 붙인 뒤 실행·삭제한다.
base_client(){
  local n=rot-measure-$$-$RANDOM
  docker create --name $n --network ${P}_it-net \
    -e SIM_USER="$(env_get INSTRUCTOR_USER)" -e SIM_PASSWORD="$(env_get INSTRUCTOR_PASSWORD)" \
    -e MQTT_USER=viewer -e MQTT_PASS="$(env_get MQTT_VIEWER_PASSWORD)" \
    -e INFLUX_ORG="$(env_get INFLUX_ORG)" -e IT_INFLUX_BUCKET="$(env_get IT_INFLUX_BUCKET)" -e IT_INFLUX_TOKEN="$(env_get IT_INFLUX_TOKEN)" \
    -e DMZ_INFLUX_BUCKET="$(env_get DMZ_INFLUX_BUCKET)" -e DMZ_INFLUX_TOKEN="$(env_get DMZ_INFLUX_TOKEN)" \
    -e FIELD_USER="$(env_get FIELD_PANEL_USER)" -e FIELD_PASSWORD="$(env_get FIELD_PANEL_PASSWORD)" \
    -e MQTT_FUXA_PASSWORD="$(env_get MQTT_FUXA_PASSWORD)" -e MQTT_RECEIVER_PASSWORD="$(env_get MQTT_RECEIVER_PASSWORD)" \
    -e MQTT_GATEWAY_PASSWORD="$(env_get MQTT_GATEWAY_PASSWORD)" -e PG_AI_PASSWORD="$(env_get PG_AI_PASSWORD)" \
    -e PG_OPS_PASSWORD="$(env_get PG_OPS_PASSWORD)" -e PG_SUPERUSER_PASSWORD="$(env_get PG_SUPERUSER_PASSWORD)" \
    -v "$REPO/experiments:/repo/experiments" -v "$REPO/experiments:/experiments" -w /repo $CLIENT_IMG "$@" >/dev/null
  # 코드는 바인드 마운트 대신 복사해 넣는다: Docker VM 여유가 적을 때 파일 공유 층이 목록 읽기에서 ENOMEM 을 낸다(09-30 실측).
  # 결과는 experiments 바인드 마운트로만 쓴다.
  for d in harness registry/generated simulator scenarios; do
    [ -e "$REPO/$d" ] && tar -C "$REPO" -cf - "$d" | docker cp - $n:/repo/ >/dev/null
  done
  docker network connect ${P}_ot-net $n; docker network connect ${P}_dmz-net $n
  docker start -a $n; local rc=$?
  docker rm -f $n >/dev/null 2>&1
  return $rc
}
jobs_running(){ docker exec $C_JM curl -s -m 10 localhost:8081/jobs/overview | python -c "import json,sys;print(sum(j['state']=='RUNNING' for j in json.load(sys.stdin)['jobs']))" 2>/dev/null | tr -d '\r' || echo 0; }
