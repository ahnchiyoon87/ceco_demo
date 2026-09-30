#!/bin/bash
# [측정 도구] 새 베이스 E1 알람→화면 지연(V1 baseline.sh P2 와 같은 주입: 스파이크 2 s, PT-101 THRESHOLD_USL).
#   bash harness/e2e/e1_base.sh <EXP>
# 주입 전 조건: PT-101 ≥ 3.0 bar(스파이크 +3.6 이 규격 6.0 과 인터록 6.5 를 넘어 FUXA 운전원 알람까지 생기는 운전점, 최대 150 s 대기). 운전점이 낮으면 알람이 생기지 않아
#   그 회차는 지연 표본이 아니다(09-30 첫 실행: 20회 중 7회가 빈 회차).
# A: 10회 × 3 = 30회(조용함 3 s, 회차 제한 15 s — 공정 알람은 인터록이 1 s 넘게 걸릴 때만 FUXA 가 본다: 알람 검사 1 s 주기) — Kafka sensor.alerts / FUXA 공정 알람(PT-101 규격·고압 인터록) / AI 사건
# B: 10회(조용함 65 s) — FUXA 분석 경고 표시 토픽(OT 허브 AR-100/alert/display). 같은 설비·규칙의 열린 묶음이
#    60 s 조용해야 새로 표시하므로(17번 F4) 회차 사이를 띄운다.
set -u
EXP=$1
. harness/e2e/struct_base.sh
for k in ${E1_RUNS:-1 2 3}; do
  base_client python harness/e2e/e1.py --exp $EXP --run e1_base_$k --reps 10 --quiet-s 3 --sim $SIM_INT \
    --mqtt ot-hub --kafka kafka:9092 --kafka-topic sensor.alerts \
    --match THRESHOLD_USL --fault-duration 2 --incident-api $AI_INT/incidents \
    --fuxa-alarms $FUXA_INT/api/alarms --fuxa-match PT-101,인터록 --min-before PT-101=3.0 --timeout-s 15 2>&1 | tail -1
done
base_client python harness/e2e/e1.py --exp $EXP --run e1_base_display --reps 10 --quiet-s 65 --sim $SIM_INT \
  --mqtt ot-hub --mqtt-topics AR-100/alert/display --kafka kafka:9092 --kafka-topic sensor.alerts \
  --match THRESHOLD_USL --fault-duration 2 --min-before PT-101=3.0 2>&1 | tail -1
