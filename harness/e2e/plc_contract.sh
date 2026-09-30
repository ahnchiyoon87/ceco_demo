#!/bin/bash
# [측정 도구] soft-PLC 계약 시험 두 단계(정비 모드 켜기까지 → PLC 재시작 → RETAIN 확인부터 끝까지). 끝나면 단독 스택을 지운다.
#   bash harness/e2e/plc_contract.sh <EXP>      결과: experiments/<EXP>/raw/plc_contract_r1.json·r2.json
set -u
export MSYS_NO_PATHCONV=1
EXP=$1; R=experiments/$EXP/raw; mkdir -p $R
F=harness/e2e/plc_contract.compose.yml
DC="docker compose -f $F"
$DC up -d --wait plant-sim plc probe >/dev/null 2>&1 || $DC up -d plant-sim plc probe
docker cp harness/e2e/plc_contract.py rot-plc-contract-probe-1:/repo/plc_contract.py >/dev/null
run(){ docker exec -w /repo rot-plc-contract-probe-1 python plc_contract.py --phase $1 --out /tmp/r$1.json; rc=$?
       docker cp rot-plc-contract-probe-1:/tmp/r$1.json $R/plc_contract_r$1.json >/dev/null; return $rc; }
run 1; rc1=$?
$DC restart plc >/dev/null
run 2; rc2=$?
$DC down -v >/dev/null 2>&1
echo "phase1=$rc1 phase2=$rc2"
[ $rc1 -eq 0 ] && [ $rc2 -eq 0 ]
