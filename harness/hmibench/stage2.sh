#!/usr/bin/env bash
# HMI ② (EXP-HMI). 결과: experiments/EXP-HMI/stage2_<profile>.json
#   harness/hmibench/stage2.sh fuxa-v1|fuxa134|fuxa134-uns|nodered|thingsboard|scadalts|streampipes
# 판정 항목 D1~D6 은 hmi_stage2.py 머리 주석(결과 보기 전 고정).
set -uo pipefail
cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1
source harness/benchcommon/guard.sh
p=${1:?profile}
F=harness/hmibench/compose.yml
DC="docker compose -f $F"
RAW=experiments/EXP-HMI/raw; mkdir -p "$RAW"
[ -f harness/hmibench/generated/mosquitto.passwd ] || python harness/hmibench/hmi_prepare.py || exit 8
[ -n "$(docker ps -q --filter label=com.docker.compose.project=hmibench)" ] && { echo "hmibench 가 이미 떠 있음"; exit 4; }
$DC --profile tools build client >/dev/null || exit 5
t0=$(date +%s)
$DC --profile "$p" up -d --build || { $DC --profile "$p" logs --tail 80; exit 6; }
CL="$DC --profile tools run --rm -T client python /repo/harness/hmibench/hmi_stage2.py"
if [ "$p" = thingsboard ]; then
  $CL tb-prepare | tail -1
  $DC --profile "$p" --profile tb-gw up -d tb-gateway
  sleep 30
fi
$DC --profile "$p" --profile tb-gw images | tail -n +2 | awk '{print $2":"$3" "$4}' > "$RAW/images_$p.txt"
echo "{\"profile\":\"$p\",\"up_returned_s\":$(( $(date +%s) - t0 ))}" > "$RAW/${p}_startup.json"
harness/sample_stats.sh "$RAW/stats_$p.csv" 900 "^hmibench-" &
sp=$!
$CL run --profile "$p" 2>&1 | tail -2
kill $sp 2>/dev/null
$DC --profile "$p" --profile tb-gw logs --no-color > "$RAW/${p}_services.log" 2>&1
$CL summarize --profile "$p" | tail -1
[ "${KEEP:-0}" = 1 ] || $DC --profile "$p" --profile tb-gw down -v --remove-orphans >/dev/null 2>&1
