#!/usr/bin/env bash
# S09 반복 행렬: 후보 × kill 대상 × kill 시점. 매 실행마다 세 후보가 같은 리플레이를 소비하고 kill 된 쪽을 대조군과 비교.
# JobManager 를 죽인 뒤에는 V1 과 같이 잡이 사라지므로 다음 실행 전에 해당 Flink 에 SQL 을 다시 제출한다.
#   harness/s09_matrix.sh <run 접두사>
set -uo pipefail
pre=$1
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1
B="docker compose -f harness/l4bench/compose.yml"
P120=l4bench-flink; P22=l4bench-flink22
resubmit(){  # $1 = flinksql|flink22
  if [ "$1" = flinksql ]; then $B --profile tools run --rm -T submit-flinksql 2>&1 | grep -c "Job ID"
  else $B --profile flink22 run --rm -T submit-flink22 2>&1 | grep -c "Job ID"; fi
  sleep 15
}
i=0
# 목록은 fd 3 으로 읽는다: 반복문 안의 docker compose run 이 표준입력을 소비해 첫 줄만 돌던 결함(x 행렬) 수정
while read -r killed targets ctrl rest timing <&3; do
  [ -z "$killed" ] && continue
  [ "${SKIP_PYTHON:-0}" = 1 ] && [ "$killed" = python ] && continue
  for t in $timing; do
    i=$((i+1)); run="${pre}${i}"
    export KILL_AT=${t%%/*} START_AT=${t##*/}
    fr=http://flink-jobmanager:8081; [ "$killed" = flink22 ] && fr=http://flink22-jobmanager:8081
    [ "$killed" = python ] && fr=http://flink-jobmanager:8081
    FLINK_REST=$fr harness/s09_eval.sh "$run" "$(echo $targets | tr ',' ' ')" "$killed" "$ctrl"
    case "$rest" in resubmit) resubmit "$killed";; esac
  done
done 3<<'EOF'
python l4bench-l4-python-1 flinksql - 1/5 3/8 5/12
flinksql l4bench-flink-taskmanager-1 python - 1/5 3/8 5/12
flink22 l4bench-flink22-taskmanager-1 python - 1/5 3/8 5/12
flinksql l4bench-flink-jobmanager-1,l4bench-flink-taskmanager-1 python resubmit 3/8 5/12
flink22 l4bench-flink22-jobmanager-1,l4bench-flink22-taskmanager-1 python resubmit 3/8 5/12
EOF
echo "matrix done: $i runs"
