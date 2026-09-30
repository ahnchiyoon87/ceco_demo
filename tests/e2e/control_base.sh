#!/bin/bash
# [측정 도구] 새 베이스 제어·안전 회귀(OT 쪽) 전체: control_base.py 기본 묶음 → S19(엣지 정지·재기동) 단계.
#   bash tests/e2e/control_base.sh <EXP> <이름>
set -u
EXP=$1; NAME=$2
. tests/e2e/struct_base.sh
OUT=/repo/experiments/$EXP/raw/control_${NAME}.json
rm -f "experiments/$EXP/raw/control_${NAME}.json"
base_client python tests/e2e/control_base.py --out $OUT
base_client python tests/e2e/control_base.py --out $OUT --only S19      # 준비: REMOTE_AUTO
docker stop $C_EDGE >/dev/null && echo "엣지 정지 $(date +%T)"
base_client python tests/e2e/control_base.py --out $OUT --only S19A --no-restore
docker start $C_EDGE >/dev/null && echo "엣지 재기동 $(date +%T)"
base_client python tests/e2e/control_base.py --out $OUT --only S19B
rm -f experiments/.s19_state.json
