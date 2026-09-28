#!/usr/bin/env bash
# 벤치 공통 가드. 실험 스택(rot-iiot)·AI 스택(rot-ai)이 떠 있으면 무거운 측정과 겹치므로 벤치를 띄우지 않는다.
#   source harness/benchcommon/guard.sh    (FORCE=1 이면 경고만 남기고 통과)
# 판정: compose 프로젝트 라벨 rot-iiot / rot-ai 이거나 이름이 rot- 로 시작하는 실행 중 컨테이너.
_running=$(docker ps --format '{{.Names}}|{{.Label "com.docker.compose.project"}}' 2>/dev/null \
  | awk -F'|' '$2=="rot-iiot" || $2=="rot-ai" || $1 ~ /^rot-/ {print $1}')
if [ -n "$_running" ]; then
  _n=$(echo "$_running" | wc -l | tr -d ' ')
  if [ "${FORCE:-0}" != "1" ]; then
    echo "GUARD: rot-iiot/rot-ai 컨테이너 ${_n}개 실행 중 → 벤치 기동 거부 (측정 겹침·메모리 부족 방지)." >&2
    echo "       측정이 끝났고 겹쳐도 되는 이유가 있으면 FORCE=1 로 다시 실행하고, 결과 JSON 의 guard.forced=true 를 확인한다." >&2
    exit 3
  fi
  echo "GUARD: FORCE=1 — rot 컨테이너 ${_n}개가 떠 있는 상태로 진행한다(결과에 기록)." >&2
  export BENCH_GUARD_FORCED=1 BENCH_GUARD_ROT_RUNNING=$_n
else
  export BENCH_GUARD_FORCED=0 BENCH_GUARD_ROT_RUNNING=0
fi
unset _running _n
