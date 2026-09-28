#!/bin/sh
# EXP-AI 배치: 팔 전환(그래프 스냅샷 + 이미지) 후 시나리오 반복. 측정 도구.
#   sh harness/aibench/run_batch.sh "C:SC1_bearing:2:3 C:SC2_heater_stuck:1:3 ..."   (팔:시나리오:시작회차:끝회차)
set -u
export COMPOSE_PATH_SEPARATOR=: MSYS_NO_PATHCONV=1 PYTHONUTF8=1
BASE="docker compose -p rot-ai --env-file ai-layer/.env.local --env-file .env.rotation -f ai-layer/compose.yml -f ai-layer/compose.scada.yml"
current=""
switch_arm() {   # $1 = A|B|C
  case $1 in A) snap=rot-ai_graph-snap-A; files="";; B) snap=rot-ai_graph-snap-B; files="";; C) snap=rot-ai_graph-snap-C3; files="-f ai-layer/compose.v2.yml";; esac
  echo "== switch to arm $1 ($snap)"
  docker stop rot-ai-knowledge-1 rot-ai-graph-1 >/dev/null 2>&1
  docker run --rm -v $snap:/from:ro -v rot-ai_graph-data:/to alpine:3.22 sh -c "rm -rf /to/* 2>/dev/null; cp -a /from/. /to/" || exit 1
  [ "$1" = C ] || docker stop rot-ai-embed-1 >/dev/null 2>&1
  $BASE $files --profile knowledge up -d --no-build --wait graph work-db knowledge alarm-worker $([ "$1" = C ] && echo embed) 2>&1 | tail -1
  docker inspect rot-ai-knowledge-1 --format 'knowledge image: {{.Config.Image}}'
  current=$1
}
for item in $1; do
  arm=${item%%:*}; rest=${item#*:}; sc=${rest%%:*}; rest=${rest#*:}; from=${rest%%:*}; to=${rest#*:}
  [ "$arm" = "$current" ] || switch_arm $arm
  i=$from
  while [ $i -le $to ]; do
    short=$(echo $sc | cut -d_ -f1)
    python harness/aibench/run_scenario.py $arm $sc $arm-$short-$i 2>&1 | tail -1
    i=$((i+1))
  done
done
echo "== batch done"
