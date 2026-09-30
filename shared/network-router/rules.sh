#!/bin/sh
# ═══ 구역 사이 규칙(상태 기반) ═══
# 원칙: 연결은 신뢰가 높은 쪽이 연다. OT→DMZ(브리지·감시 전송), IT→DMZ(수집·조회·요청)만 새 연결을 허용한다.
#       DMZ→OT·DMZ→IT·IT→OT 새 연결은 없다(CISA 2016 p.20, 2026 지침 p.26). 응답은 ESTABLISHED 로만 돌아간다.
# 방식: ot·dmz 는 internal 망이라 경로를 바꿀 수 없다(도커가 구역 밖 목적지를 막는다, ⑨-1 실측).
#       그래서 각 구역 컨테이너는 자기 망 안의 라우터 주소(별칭 dmz-broker 등)로 연결하고, 라우터가 허용 포트만
#       목적지로 넘긴다(DNAT + MASQUERADE). 허용 목록 밖은 기록(카운터) 후 차단한다.
set -eu
P=${NET_PREFIX:?}
OT=$P.10.0/24; DMZ=$P.20.0/24; IT=$P.30.0/24
R_OT=$P.10.2; R_IT=$P.30.2; IT_GW=$P.30.1        # IT_GW = 호스트(사람·도구)가 공개 포트로 들어오는 주소
DMZ_BROKER=$P.20.11; DMZ_INFLUX=$P.20.12; DMZ_PROM=$P.20.13; DMZ_GATEWAY=$P.20.14
OT_SIM=$P.10.11; OT_HUB=$P.10.12; OT_EDGE=$P.10.13; OT_PLC=$P.10.14; OT_FUXA=$P.10.15

ipt(){ iptables "$@"; }
ipt -F; ipt -t nat -F; ipt -X 2>/dev/null || true
ipt -P INPUT DROP; ipt -P FORWARD DROP; ipt -P OUTPUT ACCEPT
ipt -A INPUT -i lo -j ACCEPT
ipt -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
ipt -A FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT

allow(){ # allow <원본 대역> <라우터 주소> <라우터 포트> <목적지 주소> <목적지 포트> <이름>
  ipt -t nat -A PREROUTING -s "$1" -d "$2" -p tcp --dport "$3" -j DNAT --to-destination "$4:$5" -m comment --comment "$6"
  ipt -A FORWARD -s "$1" -d "$4" -p tcp --dport "$5" -m conntrack --ctstate NEW -j ACCEPT -m comment --comment "$6"
}
# OT → DMZ: 허브 브리지(MQTT), 감시 지표 전송(Prometheus agent remote_write)
allow $OT $R_OT 1883 $DMZ_BROKER 1883 "ot->dmz mqtt bridge"
allow $OT $R_OT 9090 $DMZ_PROM 9090 "ot->dmz prometheus remote_write"
# IT → DMZ: 수집기 구독·분석 경고 발행, 원시 사본 조회, 감시 federate, 작업 요청 POST (호스트 도구도 IT 쪽으로 들어온다)
allow $IT $R_IT 1883 $DMZ_BROKER 1883 "it->dmz mqtt"
allow $IT $R_IT 8086 $DMZ_INFLUX 8086 "it->dmz influxdb query"
allow $IT $R_IT 9090 $DMZ_PROM 9090 "it->dmz prometheus federate"
allow $IT $R_IT 8088 $DMZ_GATEWAY 8088 "it->dmz request gateway"
# 호스트(사람·도구) → OT 사람용 화면: 호스트 게이트웨이 주소에서 온 것만. IT 컨테이너는 못 연다
allow $IT_GW/32 $R_IT 21881 $OT_FUXA 1881 "host->ot fuxa"
allow $IT_GW/32 $R_IT 28080 $OT_SIM 8080 "host->ot instructor api"
allow $IT_GW/32 $R_IT 28081 $OT_SIM 8081 "host->ot field panel"
allow $IT_GW/32 $R_IT 21883 $OT_HUB 1883 "host->ot hub mqtt"
allow $IT_GW/32 $R_IT 21880 $OT_EDGE 1880 "host->ot edge editor"
allow $IT_GW/32 $R_IT 28443 $OT_PLC 8443 "host->ot plc editor api"
ipt -t nat -A POSTROUTING -d $DMZ -j MASQUERADE
ipt -t nat -A POSTROUTING -d $OT -j MASQUERADE
# 허용 밖: 구역별로 세고 버린다
for z in "ot:$OT" "dmz:$DMZ" "it:$IT"; do
  ipt -A FORWARD -s "${z#*:}" -j DROP -m comment --comment "drop from ${z%%:*}"
done
ipt -A FORWARD -j DROP -m comment --comment "drop other"
echo "[router] 규칙 적재: $(iptables -t nat -S PREROUTING | grep -c DNAT)개 허용 경로, 나머지 차단 (iptables $(iptables -V | cut -d' ' -f2-))"

# 차단 기록: 바뀔 때만 1분마다 구역별 누적 패킷 수를 남긴다
counts(){ iptables -L FORWARD -v -n -x | awk '/drop from|drop other/ { z = ($0 ~ /drop other/) ? "other" : $(NF-1); printf "%s=%s ", z, $1 }'; }
last=""
while true; do
  cur=$(counts)
  if [ "$cur" != "$last" ]; then echo "[router] 차단 누적(패킷): $cur"; last=$cur; fi
  sleep 60
done
