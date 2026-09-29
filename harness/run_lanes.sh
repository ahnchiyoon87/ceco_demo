#!/bin/sh
# [측정 도구] 층별 ② 를 두 줄로 동시에(#91): 무거운 줄(l4 backbone ts) + 가벼운 줄(broker ingest pipe alw mon alarm hmi).
# ingest·pipe 는 같은 호스트 포트(39443)를 써서 같은 줄에 순서대로 둔다. 격리 스택(rot-*)을 내린 뒤 실행.
cd "$(dirname "$0")/.." || exit 1
sh harness/run_all_stage2.sh l4 backbone ts > experiments/_lane_heavy.log 2>&1 &
sh harness/run_all_stage2.sh broker ingest pipe alw mon alarm hmi > experiments/_lane_light.log 2>&1 &
wait
echo "두 줄 끝" | tee -a experiments/STAGE2_RUNS.log
