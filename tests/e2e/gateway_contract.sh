#!/bin/bash
# [측정 도구] DMZ 게이트웨이 계약 시험 두 단계(정상 → DMZ 브로커 정지 중 → 다시 켬).
#   bash tests/e2e/gateway_contract.sh <EXP> <이름> [URL]     결과: experiments/<EXP>/raw/gw_<이름>_normal.json·_broker_down.json
set -u
EXP=$1; NAME=$2; URL=${3:-http://dmz-gateway:8088/requests}
. tests/e2e/struct_base.sh
R=experiments/$EXP/raw; mkdir -p $R
base_client python tests/e2e/gateway_contract.py --phase normal --url $URL --out /repo/$R/gw_${NAME}_normal.json; rc1=$?
docker stop ${P}-dmz-broker-1 >/dev/null; sleep 2
base_client python tests/e2e/gateway_contract.py --phase broker_down --url $URL --out /repo/$R/gw_${NAME}_broker_down.json; rc2=$?
docker start ${P}-dmz-broker-1 >/dev/null
echo "normal=$rc1 broker_down=$rc2"
[ $rc1 -eq 0 ] && [ $rc2 -eq 0 ]
