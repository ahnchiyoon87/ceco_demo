#!/bin/sh
# 시험용 라우터: FORWARD 기본 차단, 허용 포트만 DNAT
set -e
OT=10.231.10.0/24; DMZ=10.231.20.0/24; IT=10.231.30.0/24
R_OT=10.231.10.2; R_DMZ=10.231.20.2; R_IT=10.231.30.2
DMZSRV=10.231.20.10; DMZMQ=10.231.20.11; OTAPP=10.231.10.10; IT_GW=10.231.30.1
iptables -P FORWARD DROP
iptables -P INPUT DROP
iptables -A INPUT -i lo -j ACCEPT
iptables -A INPUT -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
iptables -A FORWARD -m conntrack --ctstate ESTABLISHED,RELATED -j ACCEPT
# ot -> dmz 1883 (DMZ 브로커)
iptables -t nat -A PREROUTING -s $OT -d $R_OT -p tcp --dport 1883 -j DNAT --to-destination $DMZMQ:1883
iptables -A FORWARD -s $OT -d $DMZMQ -p tcp --dport 1883 -m conntrack --ctstate NEW -j ACCEPT
# ot -> dmz 9090
for p in 9090; do
  iptables -t nat -A PREROUTING -s $OT -d $R_OT -p tcp --dport $p -j DNAT --to-destination $DMZSRV:$p
  iptables -A FORWARD -s $OT -d $DMZSRV -p tcp --dport $p -m conntrack --ctstate NEW -j ACCEPT
done
iptables -t nat -A PREROUTING -s $IT -d $R_IT -p tcp --dport 1883 -j DNAT --to-destination $DMZMQ:1883
iptables -A FORWARD -s $IT -d $DMZMQ -p tcp --dport 1883 -m conntrack --ctstate NEW -j ACCEPT
# it -> dmz 8086 9090 8088
for p in 8086 9090 8088; do
  iptables -t nat -A PREROUTING -s $IT -d $R_IT -p tcp --dport $p -j DNAT --to-destination $DMZSRV:$p
  iptables -A FORWARD -s $IT -d $DMZSRV -p tcp --dport $p -m conntrack --ctstate NEW -j ACCEPT
done
# host(사람) -> ot 사람용 포트 8000 (호스트 공개 포트는 it 게이트웨이 주소로 들어온다)
iptables -t nat -A PREROUTING -s $IT_GW -d $R_IT -p tcp --dport 8000 -j DNAT --to-destination $OTAPP:8000
iptables -A FORWARD -s $IT_GW -d $OTAPP -p tcp --dport 8000 -m conntrack --ctstate NEW -j ACCEPT
iptables -t nat -A POSTROUTING -d $DMZ -j MASQUERADE
iptables -t nat -A POSTROUTING -d $OT -j MASQUERADE
iptables -A FORWARD -j DROP
echo "rules loaded"; iptables -V
exec sleep infinity
