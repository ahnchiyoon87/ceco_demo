#!/bin/sh
# Mosquitto 기동 준비: 계정 파일을 환경변수에서 만들고(비밀값은 이미지·저장소에 두지 않는다),
# 설정의 __VAR__ 자리를 환경변수로 채운 뒤 mosquitto 사용자로 실행한다.
#   MQTT_USERS="이름:비밀번호환경변수 ..."   예) "edge:MQTT_EDGE_PASSWORD fuxa:MQTT_FUXA_PASSWORD"
set -eu
C=/mosquitto/config
umask 077   # 계정 파일은 처음부터 소유자만 읽게 만든다
rm -f $C/passwd; touch $C/passwd
for pair in $MQTT_USERS; do
  user=${pair%%:*}; var=${pair#*:}
  eval "pw=\${$var:?$var 가 비어 있다}"
  mosquitto_passwd -b $C/passwd "$user" "$pw" >/dev/null
done
sed_expr=""
for token in $(grep -o '__[A-Z0-9_]*__' /cfg/mosquitto.conf | sort -u); do
  name=$(echo "$token" | sed 's/^__//; s/__$//')
  eval "val=\${$name:?$name 가 비어 있다}"
  sed_expr="$sed_expr -e s|$token|$val|g"
done
if [ -n "$sed_expr" ]; then sed $sed_expr /cfg/mosquitto.conf > $C/mosquitto.conf; else cp /cfg/mosquitto.conf $C/mosquitto.conf; fi
cp /cfg/acl $C/acl
chown -R mosquitto:mosquitto $C /mosquitto/data
chmod 0700 $C/passwd $C/acl
exec mosquitto -c $C/mosquitto.conf
