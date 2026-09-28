#!/usr/bin/env bash
# 수집 벤치 공통 함수(stage2.sh·stage4_*.sh 가 source). 레포 루트에서 실행.
. harness/benchguard.sh
. harness/ingestbench/profiles.sh

DC="docker compose -p ingestbench -f harness/ingestbench/compose.yml"
EXP=experiments/EXP-ING
RAW=$EXP/raw

# ing_up <profile> <tag> : 이전 벤치 정리 → 후보 기동 → 설정(SETUP) → 워밍업
ing_up() {
  local p=$1 tag=$2
  ing_profile "$p" || exit 1
  mkdir -p "$RAW"
  bench_require_images $ING_COMMON_IMAGES $IMAGES "$DS_IMAGE"
  export V1PARSE_FILE=/out/downstream_${tag}.jsonl INGEST_TOPIC="${DS_TOPIC:-$TOPIC}" INGEST_BROKER="tcp://$MQTT_HOST:1883"          DOWNSTREAM_CONF="$DS_CONF" DOWNSTREAM_IMAGE="$DS_IMAGE" INGEST_USER="$MQTT_USER" INGEST_PASS="$MQTT_PASS"
  $DC --profile '*' down -v --remove-orphans >/dev/null 2>&1
  rm -f "$RAW/cred_${p}.env"
  $DC --profile tools build -q client || exit 6
  echo "[ingest] up $p ($(date +%T))"
  $DC --profile "$p" up -d ${BUILD:+--build} || { $DC --profile "$p" logs --no-color > "$RAW/logs_${tag}.txt" 2>&1; exit 6; }
  if [ -n "$SETUP" ]; then
    sleep 5
    $DC --profile tools run --rm -T client $SETUP || { $DC --profile "$p" logs --no-color > "$RAW/logs_${tag}.txt" 2>&1; echo "[ingest] SETUP 실패 → ② 기동·기능 탈락 후보(로그: $RAW/logs_${tag}.txt)"; exit 7; }
  fi
  # SETUP 이 만든 자격증명(OpenRemote 서비스 사용자 등)을 읽고, 하류 파서를 그 값으로 다시 만든다
  if [ -f "$RAW/cred_${p}.env" ]; then . "$RAW/cred_${p}.env"; export INGEST_USER="$MQTT_USER" INGEST_PASS="$MQTT_PASS"; fi
  $DC --profile "$p" up -d --force-recreate --no-deps downstream >/dev/null 2>&1
  sleep "${WARM:-20}"
}

# ing_check <tag> <초> [추가 인자…] : 검사기 실행(client 컨테이너)
ing_check() {
  local tag=$1 dur=$2; shift 2
  $DC --profile tools run --rm -T client python /repo/harness/ingestbench/check_ingest.py \
    --profile "$P" --run "${RUN:-r1}" --duration "$dur" --mqtt-host "$MQTT_HOST" --topic "$TOPIC" --shape "$SHAPE" \
    --downstream "/experiments/EXP-ING/raw/downstream_${tag}.jsonl" ${MQTT_USER:+--mqtt-user "$MQTT_USER" --mqtt-pass "$MQTT_PASS"} "$@"
}

# ing_finish <result.json> <tag> : 자원 합치기 · 로그 보관 · 정리(KEEP=1 이면 남김)
ing_finish() {
  local out=$1 tag=$2 imgs
  imgs="$RAW/images_${tag}.json"
  bench_image_sizes "$imgs" $IMAGES
  [ -f "$out" ] && python harness/benchstats.py --result "$out" --stats "$RAW/stats_${tag}.csv" --images "$imgs" --only "$CAND"
  $DC --profile "$P" logs --no-color > "$RAW/logs_${tag}.txt" 2>&1
  if [ "${KEEP:-0}" != 1 ]; then $DC --profile '*' down -v --remove-orphans >/dev/null 2>&1; fi
  echo "[ingest] 결과: $out"
}
