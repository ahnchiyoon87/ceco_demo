#!/bin/sh
# [측정 도구] 버전 하나의 측정 묶음을 한 번에: 전체 측정(E·R) → 회귀(S) → 고장→알람 → 내부 오류 → 구성 복잡도.
#   STRUCT=V2 sh harness/e2e/run_full.sh EXP-002 V2 r2_
set -u
EXP=$1; NAME=$2; RUN=$3
export MSYS_NO_PATHCONV=1 COMPOSE_PATH_SEPARATOR=:
R=experiments/$EXP/raw; mkdir -p $R
L=experiments/$EXP/run_full_${NAME}_${RUN}.log
say(){ echo "[$(date +%H:%M:%S)] $*" | tee -a $L; }
T0=$(date -u +%Y-%m-%dT%H:%M:%SZ)
say "묶음 시작 $STRUCT $NAME $RUN (since $T0)"
PHASES="0 1 2 3" TESTS="r01 r02 r03 r06 r07 r08 r11 e11" RUN=$RUN sh harness/e2e/baseline.sh $EXP $NAME >> $L 2>&1
say "전체 측정 끝"
S25=1 sh harness/e2e/regression.sh $EXP $NAME >> $L 2>&1
say "회귀 끝"
case "$STRUCT" in V2) OB="--broker mqtt --mqtt-topic scada/hmi/latest-alert";; *) OB="";; esac
docker run --rm --network rot-iiot --env-file .env -v D:/work/study/scada-rotation:/repo -w /repo e2e-client:1.0 \
  python harness/e2e/fault_onset.py --reps 3 $OB --out experiments/$EXP/raw/onset_${NAME}_${RUN}600.json >> $L 2>&1
say "고장→알람 끝"
sh harness/tools/internal_errors.sh $T0 experiments/$EXP/internal_errors_${NAME}_${RUN}.json >> $L 2>&1
case "$STRUCT" in V2) CF="-f docker-compose.v2.yml";; *) CF="";; esac
docker compose --env-file .env --env-file .env.rotation $CF config --format json > $R/compose_${NAME}.json 2>>$L
python harness/tools/e2_complexity.py $NAME $R/compose_${NAME}.json > experiments/$EXP/e2_${NAME}.json 2>>$L
say "묶음 끝"
