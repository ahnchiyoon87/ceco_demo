#!/usr/bin/env bash
# 벤치 공통 가드 — 모든 run 스크립트가 source 한다.
#   . harness/benchguard.sh
# 1) 실험 스택(rot-iiot, rot-ai)이 떠 있으면 거부한다(무거운 측정은 한 번에 하나, QUESTIONS §2 I5). FORCE=1 이면 통과.
# 2) Windows Git Bash 에서 docker 경로 인자가 변환되지 않게 MSYS_NO_PATHCONV=1, 파이썬 UTF-8.
# 3) 레포 루트에서 실행하도록 강제(상대 경로 compose·experiments 기준).
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1 PYTHONIOENCODING=utf-8

bench_guard() {
  if [ ! -f harness/benchguard.sh ] || [ ! -f QUESTIONS.md ]; then
    echo "[guard] 레포 루트(scada-rotation)에서 실행하세요." >&2; exit 2
  fi
  local running
  running=$(docker ps --format '{{.Names}} {{.Label "com.docker.compose.project"}}' 2>/dev/null \
    | awk '$2=="rot-iiot" || $2=="rot-ai" || $1 ~ /^rot-/ {print $1}')
  if [ -n "$running" ]; then
    if [ "${FORCE:-0}" = "1" ]; then
      echo "[guard] FORCE=1 — 실험 스택이 떠 있지만 진행합니다(측정 조건 오염 가능, 결과에 기록할 것):" >&2
      echo "$running" | sed 's/^/  - /' >&2
    else
      echo "[guard] rot-iiot / rot-ai 컨테이너가 실행 중이라 시작하지 않습니다(FORCE=1 로 무시 가능):" >&2
      echo "$running" | sed 's/^/  - /' >&2
      exit 3
    fi
  fi
}

# 이미지가 로컬에 있는지 확인(없으면 목록 출력 후 중단). 빌드 이미지는 검사하지 않는다.
bench_require_images() {
  local miss=0 img
  for img in "$@"; do
    docker image inspect "$img" >/dev/null 2>&1 || { echo "[guard] 이미지 없음: $img (docker pull 먼저)" >&2; miss=1; }
  done
  [ "$miss" = 0 ] || exit 4
}

# 이미지 크기(MB) JSON 을 만든다: bench_image_sizes out.json img1 img2 ...
bench_image_sizes() {
  local out=$1; shift
  {
    echo "{"
    local first=1 img sz
    for img in "$@"; do
      sz=$(docker image inspect -f '{{.Size}}' "$img" 2>/dev/null || echo 0)
      [ $first = 1 ] || echo ","
      printf '  "%s": %s' "$img" "$(awk -v s="$sz" 'BEGIN{printf "%.1f", s/1048576}')"
      first=0
    done
    echo; echo "}"
  } > "$out"
}
