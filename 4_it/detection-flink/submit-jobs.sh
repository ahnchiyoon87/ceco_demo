#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════
# Flink 잡 자동 제출 — 사용자 조작 없이 기동 시 1회 실행
#
#   1) Tier-1 규칙 탐지 (임계치 · 롤링 Z-Score · MATCH_RECOGNIZE CEP)
#      → 4_it/detection-flink/sql/*.sql 을 SQL Client 로 제출. 순수 선언형.
#   2) Tier-2 ML 탐지 (결측보간 → 텐서 → 임베디드 ONNX)
#      → anomaly-job.jar
# ═══════════════════════════════════════════════════════════════════════════
set -uo pipefail

JM=flink-jobmanager:8081
SQL_DIR=/opt/flink/sql
FLINK=/opt/flink/bin/flink
SQL_CLIENT=/opt/flink/bin/sql-client.sh

echo "▶ JobManager 대기..."
for i in $(seq 1 60); do
  curl -sf "http://${JM}/overview" >/dev/null 2>&1 && break
  sleep 2
done
curl -sf "http://${JM}/overview" >/dev/null || { echo "✗ JobManager 응답 없음"; exit 1; }

echo "▶ TaskManager 슬롯 대기..."
for i in $(seq 1 60); do
  slots=$(curl -sf "http://${JM}/overview" | grep -o '"slots-total":[0-9]*' | cut -d: -f2)
  [ "${slots:-0}" -gt 0 ] && break
  sleep 2
done
echo "  가용 슬롯: ${slots:-0}"

# ── 이미 제출된 잡이 있으면 중복 제출하지 않는다 (재기동 멱등성) ──
running=$(curl -sf "http://${JM}/jobs/overview" | grep -o '"state":"RUNNING"' | wc -l | tr -d ' ')
if [ "${running:-0}" -gt 0 ]; then
  if [ "${running}" -eq 4 ]; then
    echo "✓ 이미 4개 잡이 실행 중 — 제출을 건너뜁니다."
    exit 0
  fi
  echo "✗ RUNNING ${running}/4 — 일부 작업만 실행 중입니다. 중복 제출하지 않았습니다. Flink UI에서 실패 작업을 확인하세요."
  exit 1
fi

# ── 1) Tier-1: 선언형 SQL ──
# SQL Client 는 파일 하나를 순차 실행하므로 조각들을 이어 붙인다.
COMBINED=/tmp/pipeline.sql
cat "${SQL_DIR}/01_sources.sql" \
    "${SQL_DIR}/02_tier1_rules.sql" \
    "${SQL_DIR}/03_tier1_zscore.sql" \
    "${SQL_DIR}/04_tier1_cep.sql" > "${COMBINED}"

EXPECTED_SQL_JOBS=3   # 임계치 / Z-Score / CEP

echo "▶ Tier-1 규칙 탐지 SQL 제출..."
# sql-client 출력에는 ANSI 색상코드가 섞여 있어 "^\[ERROR\]" 가 매칭되지 않는다.
# 색상코드를 먼저 제거해야 실패를 놓치지 않는다.
${SQL_CLIENT} -f "${COMBINED}" 2>&1 | sed -E 's/\x1b\[[0-9;]*m//g' > /tmp/sql.log
if grep -qE "^\[ERROR\]" /tmp/sql.log; then
  echo "✗ SQL 제출 실패:"
  grep -A3 -E "^\[ERROR\]" /tmp/sql.log | head -20
  exit 1
fi
submitted=$(grep -c "^Job ID:" /tmp/sql.log)
if [ "${submitted}" -lt "${EXPECTED_SQL_JOBS}" ]; then
  echo "✗ SQL 잡 ${submitted}/${EXPECTED_SQL_JOBS} 만 제출됨"
  grep -B2 -A3 -iE "error|exception" /tmp/sql.log | head -20
  exit 1
fi
echo "✓ Tier-1 SQL ${submitted}개 잡 제출 완료"

# ── 2) Tier-2: ONNX 임베디드 추론 잡 ──
if [ ! -f /opt/models/model.onnx ]; then
  echo "✗ 모델이 없습니다: /opt/models/model.onnx (model-trainer 를 먼저 실행하세요)"
  exit 1
fi

echo "▶ Tier-2 ONNX 이상탐지 잡 제출..."
${FLINK} run -d -m "${JM}" \
  -c org.uengine.iiot.AnomalyJob \
  /opt/flink/job/anomaly-job.jar /opt/flink/job/job.properties 2>&1 | tail -5

# ── 최종 확인: 텍스트가 아니라 실제 잡 상태로 검증한다 ──
echo ""
echo "▶ 잡 안정화 대기..."
sleep 20
EXPECTED_TOTAL=4   # SQL 3 + ONNX 1
overview=$(curl -sf "http://${JM}/jobs/overview")
echo "▶ 제출 결과:"
echo "${overview}" | tr ',' '\n' | grep -E '"name"|"state"' | paste - - | sed 's/"name"://; s/"state"://; s/"//g' | sed 's/^/   /'
running=$(echo "${overview}" | grep -o '"state":"RUNNING"' | wc -l | tr -d ' ')
echo ""
if [ "${running}" -lt "${EXPECTED_TOTAL}" ]; then
  echo "✗ RUNNING ${running}/${EXPECTED_TOTAL} — Flink UI 에서 예외를 확인하세요: http://localhost:27081"
  exit 1
fi
echo "✓ 전체 ${running}개 잡 RUNNING"
