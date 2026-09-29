#!/bin/sh
# [측정 도구] 층별 ② 재측정(벤치 결함 수정 뒤) + 중계 ④ 비정상 선별 — run_lanes.sh 가 끝난 뒤 한 번에 하나씩.
#   sh harness/run_retry.sh [묶음...]   묶음: broker ingest ingest4 l4 pipe pipe4 backbone (기본 전부)
# 무효로 옮긴 1차 결과는 experiments/EXP-*/invalid/, 결정 기록 #105~#113. 요약은 experiments/STAGE2_RUNS.log 에 이어 쓴다.
set -u
cd "$(dirname "$0")/.." || exit 1
export MSYS_NO_PATHCONV=1 PYTHONUTF8=1
SUM=experiments/STAGE2_RUNS.log
LIM=${LIM:-2400}
run(){ layer=$1; shift; t0=$(date +%s); echo "[$(date +%H:%M:%S)] (재) $layer $* 시작" | tee -a $SUM
  out=experiments/_retry_${layer}.out; timeout $LIM "$@" > $out 2>&1; rc=$?
  echo "[$(date +%H:%M:%S)] (재) $layer $* 끝 rc=$rc $(( $(date +%s) - t0 ))s | $(tail -2 $out | tr '\n' ' ' | cut -c1-240)" | tee -a $SUM; }
for B in ${*:-broker ingest ingest4 l4 pipe pipe4 backbone}; do case $B in
  broker) run broker bash harness/brokerbench/stage2_new.sh b1 "tbmq bifromq mochi nats"
          for pre in b2 b3; do run broker bash harness/brokerbench/stage2_new.sh $pre "rmqtt lavinmq activemq artemis rabbitmq"; done
          run broker bash harness/brokerbench/stage2_new.sh b3 "mosquitto emqx" ;;       # 기존 b·c 와 합쳐 3회
  ingest) for p in telegraf hivemq-edge neuron tbgw openremote; do RUN=r2 run ingest bash harness/ingestbench/stage2.sh $p; done ;;
  l4)     for p in ekuiper risingwave; do run l4 bash harness/l4bench/stage2.sh $p; done
          run l4 bash harness/l4bench/stage2.sh streampipes ;;                             # 실패하면 후보 로그가 raw/stage2_<run>_services.log 에 남음
  pipe)   for p in rpconnect benthos-umh ekuiper; do run pipe bash harness/pipebench/stage2.sh $p; done
          # V2 는 Kafka 4.3.1 — V2 후보는 그 조합으로(#114)
          for p in telegraf140v2 telegraf140x1k4 vector bento; do KAFKA_IMAGE=apache/kafka:4.3.1 run pipe bash harness/pipebench/stage2.sh $p; done ;;
  backbone) VARIANTS=" " run backbone bash harness/backbonebench/stage2.sh kafka39     # Telegraf 확인 단계만(토픽 결함 #115, 나머지 변형은 유효)
            run backbone bash harness/backbonebench/stage2.sh kafka43                     # V2 고정판(같은 제품 — 회귀 확인용 수치)
            for p in automq tansu nats pulsar rabbitmq iggy rocketmq mqtt; do run backbone bash harness/backbonebench/stage2.sh $p; done ;;   # 연쇄 거부로 미실행(#116)
  ingest4) for p in edgex telegraf benthos-umh nodered; do run ingest4 bash harness/ingestbench/stage4_r02_netcut.sh $p 10 120; done ;;   # R02 단절 10 s(#89)
  pipe4)  for t in r03 r01 r06 r08; do run pipe4 bash harness/pipebench/stage4.sh $t v1
            for p in telegraf140v2 vector bento telegraf140x1k4; do KAFKA_IMAGE=apache/kafka:4.3.1 run pipe4 bash harness/pipebench/stage4.sh $t $p; done; done ;;
esac; done
echo "[$(date +%H:%M:%S)] 재측정 끝" | tee -a $SUM
