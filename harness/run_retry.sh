#!/bin/sh
# [측정 도구] 층별 ② 재측정 — 결정을 바꿀 수 있는 것만(사용자 지시 "빠르게", #119). run_lanes.sh 가 끝난 뒤 한 번에 하나씩.
# 생략(② 미완, 선택 가능성 없음 — 컨테이너 4~9개라 ③ 에서 1컨테이너 후보를 이길 수 없음): StreamPipes·OpenRemote·NiFi·TBMQ 통합·Neuron·TB GW, 백본 AutoMQ(S3 포함 3컨테이너)·Pulsar·RocketMQ.
set -u
cd "$(dirname "$0")/.." || exit 1
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1
SUM=experiments/STAGE2_RUNS.log
LIM=${LIM:-1500}
MEMCAP=${MEMCAP:-5000}   # 층 시험과 함께 돌 때: Docker 전체 사용량이 이 값(MiB) 아래일 때만 다음 후보 시작
memtotal(){ docker stats --no-stream --format '{{.MemUsage}}' | awk '{v=$1; if (v ~ /GiB/) {sub("GiB","",v); t+=v*1024} else if (v ~ /MiB/) {sub("MiB","",v); t+=v}} END {printf "%d", t}'; }
run(){ layer=$1; shift; w=0; while [ "$(memtotal)" -gt "$MEMCAP" ] && [ $w -lt 600 ]; do sleep 10; w=$((w+10)); done; t0=$(date +%s); echo "[$(date +%H:%M:%S)] (재) $layer $* 시작" | tee -a $SUM
  out=experiments/_retry_${layer}.out; timeout $LIM "$@" > $out 2>&1; rc=$?
  echo "[$(date +%H:%M:%S)] (재) $layer $* 끝 rc=$rc $(( $(date +%s) - t0 ))s | $(tail -2 $out | tr '\n' ' ' | cut -c1-240)" | tee -a $SUM; }
for B in ${*:-ingest pipe pipe4 ingest4 broker backbone l4 ts}; do case $B in
  ingest)  RUN=r2 run ingest bash harness/ingestbench/stage2.sh telegraf ;;
  pipe)    for p in telegraf140v2 vector bento; do KAFKA_IMAGE=apache/kafka:4.3.1 run pipe bash harness/pipebench/stage2.sh $p; done ;;
  pipe4)   for t in r03 r06; do run pipe4 bash harness/pipebench/stage4.sh $t v1
             for p in telegraf140v2 vector; do KAFKA_IMAGE=apache/kafka:4.3.1 run pipe4 bash harness/pipebench/stage4.sh $t $p; done; done ;;
  ingest4) for p in edgex telegraf benthos-umh; do run ingest4 bash harness/ingestbench/stage4_r02_netcut.sh $p 10 120; done ;;
  ts)      for e in influx27 influx29; do run ts bash harness/tsbench/stage2.sh $e; done ;;
  broker)  run broker bash harness/brokerbench/stage2_new.sh b2 "rmqtt lavinmq"
           run broker bash harness/brokerbench/stage2_new.sh b3 "mosquitto rmqtt lavinmq" ;;
  backbone) for p in tansu nats rabbitmq iggy mqtt; do run backbone bash harness/backbonebench/stage2.sh $p; done ;;
  l4)      for p in ekuiper risingwave; do run l4 bash harness/l4bench/stage2.sh $p; done ;;
esac; done
echo "[$(date +%H:%M:%S)] 재측정 끝" | tee -a $SUM
