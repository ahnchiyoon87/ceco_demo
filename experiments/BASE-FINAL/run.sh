#!/bin/bash
# 최종 회귀(설계검증 반영 뒤): E1 알람→화면 · 고장→첫 알람 · 격리 60 s · 재시작 복구(수집기·Kafka·DMZ 브로커)
cd "$(dirname "$0")/../.."
. tests/e2e/struct_base.sh
echo "== E1 $(date +%T)"; bash tests/e2e/e1_base.sh BASE-FINAL
echo "== onset $(date +%T)"; base_client python tests/e2e/fault_onset_base.py --reps 3 --out /repo/experiments/BASE-FINAL/raw/onset_base.json
echo "== isolation $(date +%T)"; bash tests/e2e/isolation_base.sh BASE-FINAL 60
echo "== restart $(date +%T)"; RREPS=2 bash tests/e2e/restart_base.sh BASE-FINAL coll kafka dmzb
echo "== 끝 $(date +%T)"
