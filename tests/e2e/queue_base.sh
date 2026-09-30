#!/bin/bash
# [측정 도구] 새 베이스 브리지 큐 한도 시험(HANDOFF §3-5 "브리지 큐가 한도에 닿은 뒤에도 다시 이어 보낸다").
#   bash tests/e2e/queue_base.sh <EXP> [시험 한도, 기본 300] [끊는 초, 기본 60]
# 운영 한도(.env 72000 건 ≈ 1시간)는 시험 시간 안에 닿지 않으므로, 시험 동안만 OT 허브를 낮은 한도로 다시 만든다
# (셸 환경변수가 .env 보다 우선). 브리지를 끊어 한도를 넘긴 뒤 다시 잇고: $SYS dropped 증가, DMZ 사본 흐름 재개,
# 그 구간의 유실(버린 만큼)을 잰다. 끝나면 .env 값으로 OT 허브를 다시 만든다.
set -u
EXP=$1; LIM=${2:-300}; CUT=${3:-60}
. tests/e2e/struct_base.sh
NP=$(env_get NET_PREFIX)
RULE="FORWARD -s $NP.10.0/24 -d $NP.20.11 -p tcp --dport 1883 -j REJECT --reject-with tcp-reset -m comment --comment queue-test"
OUT=experiments/$EXP/raw/queue_base.json
DMZ_SINK="--influx http://dmz-influx:8086 --bucket-env DMZ_INFLUX_BUCKET --token-env DMZ_INFLUX_TOKEN"
say(){ echo "[$(date +%T)] $*"; }
healthy(){ for i in $(seq 1 60); do [ "$(docker inspect -f '{{.State.Health.Status}}' $1)" = healthy ] && return 0; sleep 2; done; return 1; }
sys_dropped(){ docker exec $C_OTHUB sh -c "mosquitto_sub -u viewer -P '$(env_get MQTT_VIEWER_PASSWORD)' -t '\$SYS/broker/publish/messages/dropped' -C 1 -W 15" 2>/dev/null | tr -d '\r'; }
MQTT_MAX_QUEUED_MESSAGES=$LIM docker compose -f compose.yml up -d ot-hub >/dev/null 2>&1; healthy $C_OTHUB
say "OT 허브 시험 한도 $(docker exec $C_OTHUB grep ^max_queued_messages /mosquitto/config/mosquitto.conf)"
sleep 15
D0=$(sys_dropped); T0=$(( $(date +%s) * 1000 ))
docker exec $C_ROUTER iptables -I $RULE && say "브리지 끊음 (dropped 전 $D0)"
sleep $CUT
D1=$(sys_dropped)
docker exec $C_ROUTER iptables -D $RULE && say "다시 이음 (dropped 끊긴 동안 $D1)"
TJ=$(date +%s)
FLOW=$(base_client python tests/e2e/wait_flow.py --t0 $TJ --sustain-s 60 $DMZ_SINK 2>/dev/null | tail -1)
D2=$(sys_dropped)
T1=$(( $(date +%s) * 1000 ))
COMP=$(base_client python tests/e2e/completeness.py --start-ms $((T0 - 10000)) --end-ms $T1 $DMZ_SINK --out /repo/experiments/$EXP/raw/queue_complete.json 2>/dev/null | tail -1)
say "흐름 $FLOW / dropped 이은 뒤 $D2"
docker compose -f compose.yml up -d ot-hub >/dev/null 2>&1; healthy $C_OTHUB
say "OT 허브 운영 한도로 되돌림: $(docker exec $C_OTHUB grep ^max_queued_messages /mosquitto/config/mosquitto.conf)"
python -c "
import json,sys
d0,d1,d2=[int(x) if x.strip().isdigit() else None for x in sys.argv[1:4]]
flow=json.loads(sys.argv[4]) if sys.argv[4].strip() else None
comp=json.loads(sys.argv[5]) if sys.argv[5].strip() else None
out={'limit':int(sys.argv[6]),'cut_s':int(sys.argv[7]),'dropped_before':d0,'dropped_during':d1,'dropped_after':d2,'flow_after':flow,'completeness':comp,
     'pass': None not in (d0,d2) and d2>d0 and bool(flow) and flow.get('recover_s') is not None,
     'note': 'Mosquitto 는 버린 건수($SYS)를 다시 이을 때 반영한다(끊긴 동안 값 0). 판정 = 시험 전보다 늘었고 다시 이은 뒤 흐름 복구'}
json.dump(out,open(sys.argv[8],'w',encoding='utf-8'),ensure_ascii=False,indent=1); print(json.dumps(out,ensure_ascii=False))
" "$D0" "$D1" "$D2" "$FLOW" "$COMP" $LIM $CUT $OUT
