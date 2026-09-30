#!/bin/bash
# ═══ Kafka 토픽(멱등 — 있으면 건너뜀). 보존 기간은 HANDOFF §2-2 저장 표(17번 H3) ═══
#  데이터 토픽 7일, 요청·감사 토픽 30일(정본은 PostgreSQL, Kafka 는 통로·사본)
#  파티션 키 = 설비 ID(계측·상태) / 요청 ID(요청). 소비자가 중복을 거른다(최소 1회 전달)
set -euo pipefail
BS=kafka:9092
K=/opt/kafka/bin/kafka-topics.sh
D7=604800000; D30=2592000000
create() {
  local name=$1 parts=$2 retention=$3
  if $K --bootstrap-server "$BS" --list | grep -qx "$name"; then
    echo "  = $name"
  else
    $K --bootstrap-server "$BS" --create --topic "$name" --partitions "$parts" --replication-factor 1 \
       --config retention.ms="$retention" --config compression.type=lz4 >/dev/null
    echo "  + $name (파티션 $parts, 보존 $((retention/86400000))일)"
  fi
}
echo "Kafka 토픽 초기화"
create sensor.telemetry.raw   6 $D7    # 원시 계측(ts·site·device·tag·value·quality + asset·seq·pts)
create sensor.telemetry.clean 6 $D7    # Flink 중복 제거·결측 보간
create sensor.anomaly.score   3 $D7    # 오토인코더 재구성 오차
create sensor.alerts          3 $D7    # Flink 분석 alert(규칙·Z-Score·CEP·ML)
create plant.status           3 $D7    # PLC 상태·통신 상태·ACK
create alerts.display         1 $D7    # 표시할 alert(억제·정비 중 제외) → FUXA 분석 경고(참고)
create request.approved       3 $D30   # 승인된 작업 요청 ID(AI 업무 도우미 → IT 수집기 발송 스트림, 내용 정본은 PostgreSQL)
create request.events         3 $D30   # 게이트웨이 응답(ⓐ) 사본
create request.responses      3 $D30   # OT 수신기 응답(ⓑⓒ)
create audit.copy             1 $D30   # 감사 기록 사본(정본은 PostgreSQL audit.log)
echo "완료"
