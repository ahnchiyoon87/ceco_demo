#!/usr/bin/env bash
# 벤치 compose 의 모든 프로파일 이미지를 받는다(컨테이너는 띄우지 않음). 이미 있으면 건너뛴다.
#   harness/benchcommon/pull_images.sh harness/backbonebench/compose.yml [결과 로그]
# Docker Hub 비로그인 한도(시간당 10회)에 걸리면 FAIL(ratelimit)로 남기고 다음으로 넘어간다 → 나중에 다시 돌리면 이어서 받는다.
set -uo pipefail
f=$1; log=${2:-/dev/null}
export MSYS_NO_PATHCONV=1
imgs=$(docker compose -f "$f" --profile '*' config --images 2>/dev/null | sort -u)
for i in $imgs; do
  if [[ "$i" == *:latest ]]; then echo "REFUSE latest $i" | tee -a "$log"; continue; fi
  if [[ "$i" == bench-* ]]; then echo "BUILD $i (벤치가 직접 빌드)" | tee -a "$log"; continue; fi
  if docker image inspect "$i" >/dev/null 2>&1; then echo "HAVE  $i" | tee -a "$log"; continue; fi
  out=$(docker pull -q "$i" 2>&1); rc=$?
  if [ $rc -eq 0 ]; then echo "PULL  $i" | tee -a "$log"
  elif echo "$out" | grep -qi "toomanyrequests\|rate limit"; then echo "FAIL(ratelimit) $i" | tee -a "$log"
  else echo "FAIL  $i :: $(echo "$out" | tail -1)" | tee -a "$log"; fi
done
