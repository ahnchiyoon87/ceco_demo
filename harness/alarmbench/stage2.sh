#!/usr/bin/env bash
# 알람 수명주기 ② (EXP-ALM). 결과: experiments/EXP-ALM/stage2_<profile>.json
#   harness/alarmbench/stage2.sh pgisa|alerta|keep|thingsboard
# 시나리오 L01~L12(al_stage2.py 머리 주석, 결과 보기 전 고정). 셸빙 만료 확인에 65초 대기 포함.
set -uo pipefail
cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1
source harness/benchcommon/guard.sh
p=${1:?profile}
F=harness/alarmbench/compose.yml
DC="docker compose -f $F"
RAW=experiments/EXP-ALM/raw; mkdir -p "$RAW"
[ -n "$(docker ps -q --filter label=com.docker.compose.project=alarmbench)" ] && { echo "alarmbench 가 이미 떠 있음"; exit 4; }
$DC --profile tools build client >/dev/null || exit 5
t0=$(date +%s)
$DC --profile "$p" up -d || { mkdir -p experiments/EXP-ALM/raw; $DC --profile "$p" logs --no-color > "experiments/EXP-ALM/raw/${p}_up_fail.log" 2>&1; $DC --profile "$p" logs --tail 80; $DC --profile '*' down -v --remove-orphans >/dev/null 2>&1; exit 6; }   # 실패 시 정리(#116)
$DC --profile "$p" images | tail -n +2 | awk '{print $2":"$3" "$4}' > "$RAW/images_$p.txt"
echo "{\"profile\":\"$p\",\"up_returned_s\":$(( $(date +%s) - t0 ))}" > "$RAW/${p}_startup.json"
harness/sample_stats.sh "$RAW/stats_$p.csv" 600 "^alarmbench-" &
sp=$!
$DC --profile tools run --rm -T client python /repo/harness/alarmbench/al_stage2.py run --profile "$p" 2>&1 | tail -2
kill $sp 2>/dev/null
$DC --profile "$p" logs --no-color > "$RAW/${p}_services.log" 2>&1
$DC --profile tools run --rm -T client python /repo/harness/alarmbench/al_stage2.py summarize --profile "$p" 2>&1 | tail -1
[ "${KEEP:-0}" = 1 ] || $DC --profile "$p" down -v --remove-orphans >/dev/null 2>&1
