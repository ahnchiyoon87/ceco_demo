#!/usr/bin/env bash
# 모든 벤치 compose 를 모든 프로파일로 렌더링 검사(config -q). 컨테이너를 띄우지 않는다. latest 태그가 있으면 실패.
set -uo pipefail
cd "$(dirname "$0")/../.."
export MSYS_NO_PATHCONV=1
rc=0
for b in backbonebench tsbench monbench alarmbench hmibench; do
  f=harness/$b/compose.yml
  [ -f "$f" ] || { echo "MISS $f"; rc=1; continue; }
  if docker compose -f "$f" --profile '*' config -q 2>/tmp/cfg_err_$b; then echo "OK   $f (config -q)"; else echo "FAIL $f"; cat /tmp/cfg_err_$b; rc=1; fi
  bad=$(docker compose -f "$f" --profile '*' config --images 2>/dev/null | grep -E ':latest$|^[^:]+$' || true)
  if [ -n "$bad" ]; then echo "FAIL $f latest/무태그 이미지: $bad"; rc=1; fi
done
exit $rc
