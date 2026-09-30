#!/bin/bash
# [측정] 회귀 S01 정상 운전 3분 알람 수 — regression.sh 의 S01 부분만, 3번(3회 중앙값). 스택 이름표: NET(도커 망), SIM(고장 API), KAFKA 주소.
#   NET=rot-iiot SIM=http://127.0.0.1:37080 bash experiments/BASE-S01/run_s01.sh <이름>
set -u
export MSYS_NO_PATHCONV=1
NAME=$1; NET=${NET:-rot-iiot}; SIM=${SIM:-http://127.0.0.1:37080}
D=experiments/BASE-S01/raw; REPO="D:/work/study/scada-rotation"
CLIENT="docker run --rm --network $NET -v $REPO:/repo -w /repo ${CLIENT_IMG:-e2e-client:1.0}"
curl -s -X POST -H 'Content-Type: application/json' -d '{}' $SIM/fault/clear >/dev/null; sleep 5
for i in 1 2 3; do
  T0=$(( $(date +%s) * 1000 )); sleep 180; T1=$(( $(date +%s) * 1000 ))
  $CLIENT python harness/e2e/alerts_window.py --start-ms $T0 --end-ms $T1 --out /repo/$D/s01_${NAME}_$i.json | tail -1
done
