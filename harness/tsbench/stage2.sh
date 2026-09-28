#!/usr/bin/env bash
# 시계열 ② 한 바퀴 (EXP-TS). 결과: experiments/EXP-TS/stage2_<engine>.json (+ raw/)
#   harness/tsbench/stage2.sh <engine>                 # 24h 적재 → 질의 → 가시화 지연
#   HOURS=168 harness/tsbench/stage2.sh influx3        # F05: 7일 적재(72h·432파일 한도 확인)
#   R06=1 harness/tsbench/stage2.sh influx29           # ④ R06 훅까지(적재 뒤 DB 5분 정지, 10분 소요)
# 엔진: influx27(기준) influx29 influx3 timescale pgpartman questdb victoriametrics iotdb greptime cratedb clickhouse tdengine
set -uo pipefail
cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1
source harness/benchcommon/guard.sh

eng=${1:?engine}
HOURS=${HOURS:-24}
F=harness/tsbench/compose.yml
DC="docker compose -f $F"
RAW=experiments/EXP-TS/raw; mkdir -p "$RAW"
case $eng in
  influx27|influx29) svc=$eng; ddir=/var/lib/influxdb2 ;;
  influx3)   svc=influx3; ddir=/var/lib/influxdb3 ;;
  timescale) svc=timescaledb; ddir=/var/lib/postgresql ;;
  pgpartman) svc=pgpartman; ddir=/var/lib/postgresql ;;
  questdb)   svc=questdb; ddir=/var/lib/questdb ;;
  victoriametrics) svc=victoriametrics; ddir=/victoria-metrics-data ;;
  iotdb)     svc=iotdb; ddir=/iotdb/data ;;
  greptime)  svc=greptime; ddir=/greptimedb_data ;;
  cratedb)   svc=cratedb; ddir=/data ;;
  clickhouse) svc=clickhouse; ddir=/var/lib/clickhouse ;;
  tdengine)  svc=tdengine; ddir=/var/lib/taos ;;
  *) echo "unknown engine $eng"; exit 2 ;;
esac
C="tsbench-$svc-1"
if [ -n "$(docker ps -q --filter label=com.docker.compose.project=tsbench)" ]; then echo "tsbench 가 이미 떠 있음 — 먼저 down"; exit 4; fi

$DC --profile tools build client >/dev/null || exit 5
$DC --profile "$eng" up -d --build || { $DC --profile "$eng" logs --tail 80; exit 6; }
$DC --profile "$eng" images | tail -n +2 | awk '{print $2":"$3" "$4}' > "$RAW/images_${eng}.txt"
t0=$(date +%s)
for i in $(seq 1 90); do
  st=$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}{{.State.Status}}{{end}}' "$C" 2>/dev/null)
  [ "$st" = healthy ] || [ "$st" = running ] && break; sleep 2; done
echo "{\"engine\":\"$eng\",\"state\":\"$st\",\"startup_s\":$(( $(date +%s) - t0 ))}" > "$RAW/${eng}_startup.json"

if [ "$eng" = influx3 ]; then     # 관리자 토큰(인증 켠 상태로 시험)
  for i in $(seq 1 30); do
    INFLUX3_TOKEN=$(docker exec "$C" influxdb3 create token --admin 2>&1 | grep -o 'apiv3_[A-Za-z0-9_-]*' | head -1)
    [ -n "$INFLUX3_TOKEN" ] && break; sleep 2; done
  export INFLUX3_TOKEN
  [ -n "$INFLUX3_TOKEN" ] || echo "WARN influx3 토큰 생성 실패 — 클라이언트는 무토큰으로 시도"
fi

disk(){ docker exec "$C" sh -c "du -sk $ddir 2>/dev/null | cut -f1" 2>/dev/null \
        || docker run --rm --volumes-from "$C" alpine:3.22 du -sk "$ddir" | cut -f1; }
disk > "$RAW/disk_${eng}_empty.txt"

CL="$DC --profile tools run --rm -T client python /repo/harness/tsbench/ts_stage2.py"
harness/sample_stats.sh "$RAW/stats_${eng}_stage2.csv" 7200 "^tsbench-" &   # 적재·질의 구간을 결과의 marks 로 나눈다
sp=$!
$CL load --engine "$eng" --hours "$HOURS" 2>&1 | tail -2
disk > "$RAW/disk_${eng}_after_load_${HOURS}h.txt"
sleep 60                                    # 압축·병합이 도는 엔진은 안정 후 한 번 더
disk > "$RAW/disk_${eng}_after_load_${HOURS}h_settled.txt"
$CL query --engine "$eng" 2>&1 | tail -2
$CL fresh --engine "$eng" 2>&1 | tail -1

if [ "${R06:-0}" = 1 ]; then
  TS_ENGINE=$eng $DC --profile "$eng" --profile r06 up -d telegraf-r06
  sleep 10
  $CL r06 --engine "$eng" &
  cp=$!
  for i in $(seq 1 120); do [ -e "$RAW/${eng}_r06.ready" ] && break; sleep 1; done
  sleep 120
  echo "$(date +%s.%N) stop $C" >> "$RAW/${eng}_r06_actions.log"; docker stop -t 10 "$C" >> "$RAW/${eng}_r06_actions.log" 2>&1
  sleep "${R06_DOWN_S:-300}"
  echo "$(date +%s.%N) start $C" >> "$RAW/${eng}_r06_actions.log"; docker start "$C" >> "$RAW/${eng}_r06_actions.log" 2>&1
  wait $cp
  docker logs tsbench-telegraf-r06-1 > "$RAW/${eng}_r06_telegraf.log" 2>&1
  rm -f "$RAW/${eng}_r06.ready"
fi

kill $sp 2>/dev/null
$DC --profile "$eng" logs --no-color > "$RAW/${eng}_engine.log" 2>&1
$CL summarize --engine "$eng" 2>&1 | tail -1
if [ "${KEEP:-0}" != 1 ]; then $DC --profile "$eng" --profile r06 down -v --remove-orphans >/dev/null 2>&1; fi
