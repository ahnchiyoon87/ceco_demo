#!/bin/bash
# [측정 도구] 새 베이스 격리 실습(HANDOFF §2-1 ⑩): 라우터에서 OT→DMZ 브리지(1883)를 CUT 초 끊었다 잇는다.
#   bash harness/e2e/isolation_base.sh <EXP> [CUT 초, 기본 60]
# 끊기: 라우터 FORWARD 맨 앞에 OT 대역 → DMZ 브로커 1883 을 TCP RST 로 거부하는 규칙(이미 열린 브리지 연결도 끊긴다).
# 잇기: 그 규칙만 지운다. 규칙 파일(router/rules.sh)은 바꾸지 않는다.
set -u
EXP=$1; CUT=${2:-60}
. harness/e2e/struct_base.sh
NP=$(env_get NET_PREFIX)
RULE="FORWARD -s $NP.10.0/24 -d $NP.20.11 -p tcp --dport 1883 -j REJECT --reject-with tcp-reset -m comment --comment isolation-test"
OUT=/repo/experiments/$EXP/raw/isolation_base.json
DMZ_SINK="--influx http://dmz-influx:8086 --bucket-env DMZ_INFLUX_BUCKET --token-env DMZ_INFLUX_TOKEN"
say(){ echo "[$(date +%T)] $*"; }
T0=$(( $(date +%s) * 1000 ))
docker exec $C_ROUTER iptables -I $RULE && say "OT→DMZ 브리지 끊음"
base_client python harness/e2e/isolation_base.py during --out $OUT --cut-s $CUT
base_client python harness/e2e/isolation_base.py after --out $OUT &
AP=$!
sleep 12   # "이은 뒤" 감시 클라이언트가 만들어지고 응답 토픽을 구독할 시간
docker exec $C_ROUTER iptables -D $RULE && say "다시 이음"
TJ=$(( $(date +%s) * 1000 ))
wait $AP
sleep 20
# 끊긴 동안 OT 허브 버퍼에 쌓였던 값이 DMZ 사본으로 올라왔는가(주입 10 s 전 ~ 이은 뒤 30 s)
base_client python harness/e2e/completeness.py --start-ms $((T0 - 10000)) --end-ms $((TJ + 30000)) $DMZ_SINK \
  --out /repo/experiments/$EXP/raw/isolation_complete.json | tail -1
docker exec $C_ROUTER iptables -S FORWARD | grep -c isolation-test | sed 's/^/남은 시험 규칙: /'
rm -f experiments/.isolation_state.json
