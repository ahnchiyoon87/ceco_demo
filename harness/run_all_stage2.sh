#!/bin/sh
# [측정 도구] 층별 ② 기동·기능 일괄 실행(한 번에 한 후보). 격리 스택(rot-*)을 내린 뒤 실행한다.
#   sh harness/run_all_stage2.sh [층...]     층: l4 ingest broker pipe alw backbone ts mon alarm hmi (기본 전부, 우선순위 순)
# 결과: 각 벤치의 experiments/EXP-*/stage2_*.json, 요약 experiments/STAGE2_RUNS.log
set -u
cd "$(dirname "$0")/.." || exit 1
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1
SUM=experiments/STAGE2_RUNS.log
LIM=${LIM:-2400}   # 프로필당 제한(초)
run(){ layer=$1; shift; t0=$(date +%s); echo "[$(date +%H:%M:%S)] $layer $* 시작" | tee -a $SUM
  timeout $LIM "$@" > experiments/_stage2_last.out 2>&1; rc=$?
  echo "[$(date +%H:%M:%S)] $layer $* 끝 rc=$rc $(( $(date +%s) - t0 ))s | $(tail -2 experiments/_stage2_last.out | tr '\n' ' ' | cut -c1-240)" | tee -a $SUM
  docker ps -q --filter "name=rot-" | grep -q . && { echo "경고: rot-* 떠 있음" | tee -a $SUM; }
}
layers=${*:-"l4 ingest broker pipe alw backbone ts mon alarm hmi"}
for L in $layers; do case $L in
  l4)      for p in flinksql flink23 flinkha flink22 flinkhac flinkhad flinkhab flinkcep23 ekuiper quix kstreams storm beam risingwave proton arroyo streampipes; do
             R05=$(case $p in flinksql|flink23|flinkha|flink22|flinkhac|flinkhad) echo 1;; *) echo 0;; esac) run l4 bash harness/l4bench/stage2.sh $p; done ;;
  ingest)  for p in edgex telegraf benthos-umh hivemq-edge neuron nodered tbgw openremote streampipes; do run ingest bash harness/ingestbench/stage2.sh $p; done ;;
  broker)  for p in rmqtt tbmq bifromq rabbitmq lavinmq artemis activemq comqtt robustmq mochi nats hivemq-edge; do run broker bash harness/brokerbench/stage2_new.sh $p; done ;;
  pipe)    for p in v1 telegraf140x3 telegraf140x1 bento rpconnect benthos-umh ekuiper vector nifi kconnect rmqtt-pc tbmq-pc; do run pipe bash harness/pipebench/stage2.sh $p; done ;;
  alw)     for p in v1 bento rpconnect ekuiper kconnect; do run alw bash harness/alarmworkerbench/stage2.sh $p; done ;;
  backbone) for p in kafka39 kafka43 kafka42 kafka41 automq tansu nats pulsar rabbitmq iggy rocketmq mqtt; do run backbone bash harness/backbonebench/stage2.sh $p; done ;;
  ts)      for p in influx27 influx29 influx3 timescale pgpartman questdb victoriametrics iotdb greptime cratedb clickhouse tdengine; do run ts bash harness/tsbench/stage2.sh $p; done ;;
  mon)     for p in v1 prom315 prom313 vm prom315-v2 vm-v2; do run mon bash harness/monbench/stage2.sh $p; done ;;
  alarm)   for p in pgisa alerta keep thingsboard; do run alarm bash harness/alarmbench/stage2.sh $p; done ;;
  hmi)     for p in fuxa-v1 fuxa134 fuxa134-uns nodered thingsboard scadalts streampipes; do run hmi bash harness/hmibench/stage2.sh $p; done ;;
esac; done
echo "[$(date +%H:%M:%S)] 전체 끝" | tee -a $SUM
