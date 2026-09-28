#!/usr/bin/env bash
# 중계 벤치 공통(stage2.sh·stage4.sh 가 source). 레포 루트에서 실행.
. harness/benchguard.sh
. harness/pipebench/profiles.sh
DC="docker compose -p pipebench -f harness/pipebench/compose.yml"
EXP=experiments/EXP-PIPE; RAW=$EXP/raw

# pipe_up <profile> <tag 접두> : 정리 → 기동 → SETUP → 워밍업. TAG 변수 설정.
pipe_up() {
  P=$1
  pipe_profile "$P" || exit 1
  [ "$NEED_KAFKA4" = 1 ] && [ -z "${KAFKA_IMAGE:-}" ] && KAFKA_IMAGE=apache/kafka:4.3.1
  export KAFKA_IMAGE=${KAFKA_IMAGE:-apache/kafka:3.9.0}
  KV=${KAFKA_IMAGE##*:}
  TAG=$2${P}$([ "$KV" != 3.9.0 ] && echo "_k$KV")${RUN:+_$RUN}
  mkdir -p "$RAW"
  bench_require_images $PIPE_COMMON_IMAGES "$KAFKA_IMAGE" $IMAGES
  $DC --profile '*' down -v --remove-orphans >/dev/null 2>&1
  $DC --profile tools build -q client || exit 6
  echo "[pipe] up $P (kafka $KV, $(date +%T))"
  $DC --profile "$P" up -d ${BUILD:+--build} || { $DC --profile "$P" logs --no-color > "$RAW/logs_${TAG}.txt" 2>&1; exit 6; }
  if [ -n "$SETUP" ]; then
    sleep 5
    $DC --profile tools run --rm -T client $SETUP || { $DC --profile "$P" logs --no-color > "$RAW/logs_${TAG}.txt" 2>&1; echo "[pipe] SETUP 실패 → ② 탈락 후보(재현 가능 설정 실패 포함)"; exit 7; }
  fi
  sleep "${WARM:-15}"
}

# pipe_check <out.json 컨테이너 경로> <발생 초> [추가 인자]
pipe_check() {
  local out=$1 dur=$2; shift 2
  $DC --profile tools run --rm -T client python /repo/harness/pipebench/check_pipe.py --profile "$P" --run "${RUN:-r1}" \
    --duration "$dur" --mqtt-host "$MQTT_HOST" --shape-in "$SHAPE_IN" --alert-rate "${ALERT_RATE:-2}" --out "$out" "$@" 2>&1 | grep -v Container
}

pipe_finish() {
  local out=$1
  bench_image_sizes "$RAW/images_${TAG}.json" $IMAGES
  [ -f "$out" ] && python harness/benchstats.py --result "$out" --stats "$RAW/stats_${TAG}.csv" --images "$RAW/images_${TAG}.json" --only "$CAND"
  $DC --profile "$P" logs --no-color > "$RAW/logs_${TAG}.txt" 2>&1
  [ "${KEEP:-0}" = 1 ] || $DC --profile '*' down -v --remove-orphans >/dev/null 2>&1
  echo "[pipe] 결과: $out"
}
