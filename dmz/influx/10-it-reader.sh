#!/bin/bash
# DMZ InfluxDB(OT 원시값 사본) 초기 설정: IT 가 조회만 하도록 v1 호환 읽기 전용 계정과 InfluxQL 매핑을 만든다.
# (v2 API 토큰은 값을 정할 수 없어 IT 설정에 넣을 수 없다 — ⑨ 실측. 쓰기는 DMZ 적재기 토큰만 한다)
set -euo pipefail
BID=$(influx bucket list -n "$DOCKER_INFLUXDB_INIT_BUCKET" --hide-headers | cut -f1)
influx v1 dbrp create --db "$DOCKER_INFLUXDB_INIT_BUCKET" --rp autogen --bucket-id "$BID" --default >/dev/null
influx v1 auth create --username "$DMZ_INFLUX_READER_USER" --password "$DMZ_INFLUX_READER_PASSWORD" --read-bucket "$BID" >/dev/null
echo "[dmz-influx] 읽기 전용 계정 $DMZ_INFLUX_READER_USER · InfluxQL 매핑 생성"
