#!/bin/bash
# ═══════════════════════════════════════════════════════════════
# Kafka 토픽 생성 (멱등 — 이미 있으면 건너뜀)
#
#  sensor.telemetry.raw   무손실 원본. 보간 없음. 감사추적의 기준선.
#  sensor.telemetry.clean 중복제거 + 결측보간 완료. quality 로 추정치 표시.
#  sensor.anomaly.score   Autoencoder 재구성 오차 + 기여 센서
#  sensor.alerts          Tier1(임계치/Z-score/CEP) + Tier2(ML) 통합 알람
#
# 파티션 키 = 태그명 → 태그 단위 순서 보장 (Flink keyed state 정합)
# ═══════════════════════════════════════════════════════════════
set -euo pipefail
BS=kafka:9092
K=/opt/kafka/bin/kafka-topics.sh

create() {
  local name=$1 parts=$2 retention=$3
  if $K --bootstrap-server "$BS" --list | grep -qx "$name"; then
    echo "  = $name (이미 존재)"
  else
    $K --bootstrap-server "$BS" --create --topic "$name" \
       --partitions "$parts" --replication-factor 1 \
       --config retention.ms="$retention" \
       --config compression.type=lz4 >/dev/null
    echo "  + $name (파티션 $parts, 보존 $((retention/3600000))h)"
  fi
}

echo "Kafka 토픽 초기화..."
create sensor.telemetry.raw   6 86400000
create sensor.telemetry.clean 6 86400000
create sensor.anomaly.score   3 86400000
create sensor.alerts          3 604800000
echo "완료:"
$K --bootstrap-server "$BS" --list | sed 's/^/  /'
