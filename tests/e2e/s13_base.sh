#!/bin/bash
# [측정 도구] 새 베이스 S13: ONNX 점수(Flink 잡 코드) = Python 점수(onnxruntime) |차| ≤ 1e-6.
# 운영 클러스터 슬롯을 쓰지 않도록 같은 이미지·같은 잡(AnomalyJob)을 일회용 컨테이너의 로컬 실행 환경으로 돌린다.
# 시험 토픽(exp.l4.*)은 만들고 끝나면 지운다. 모델은 기동 때 학습기가 만든 모델 볼륨을 읽기 전용으로 쓴다.
#   bash tests/e2e/s13_base.sh <EXP> <run>
set -u
EXP=$1; RUN=$2
. tests/e2e/struct_base.sh
KB=/opt/kafka/bin
KT="docker exec $C_KAFKA $KB/kafka-topics.sh --bootstrap-server localhost:9092"
TOPICS="exp.l4.raw exp.l4.clean.base exp.l4.score.base exp.l4.alerts.base"
for t in $TOPICS; do $KT --create --if-not-exists --topic $t --partitions 1 --replication-factor 1 >/dev/null; done
JOB=ceco-measure-s13-job
docker rm -f $JOB >/dev/null 2>&1
docker run -d --name $JOB --network ${P}_it-net -v ${P}_model-store:/opt/models:ro \
  -v "$REPO/experiments/$EXP/s13_job.properties:/s13.properties:ro" --entrypoint java ceco-flink-onnx:base \
  -Xmx512m -cp "/opt/flink/lib/*:/opt/flink/job/anomaly-job.jar" org.uengine.iiot.AnomalyJob /s13.properties >/dev/null
# 준비 확인: 표지 레코드를 원시 시험 토픽에 넣고 정제 시험 토픽으로 나올 때까지(Flink Kafka 소스는 소비자 그룹을 쓰지 않아
# 그룹 조회로는 알 수 없다 — 09-30 첫 실행에서 창 4개가 잡이 읽기 전에 들어가 점수가 없었다)
ready=0
for i in $(seq 1 60); do
  echo "{\"ts\": $(date +%s)000000000, \"site\": \"EXP\", \"device\": \"s13-ready\", \"tag\": \"CT-101\", \"value\": 1.0}" | \
    docker exec -i $C_KAFKA $KB/kafka-console-producer.sh --bootstrap-server localhost:9092 --topic exp.l4.raw >/dev/null 2>&1
  if docker exec $C_KAFKA $KB/kafka-console-consumer.sh --bootstrap-server localhost:9092 --topic exp.l4.clean.base \
       --from-beginning --max-messages 1 --timeout-ms 3000 2>/dev/null | grep -q s13-ready; then ready=1; break; fi
done
echo "시험 잡 준비: $([ $ready = 1 ] && echo 확인 || echo 실패) (${i}회 시도)"
[ $ready = 1 ] || { docker logs $JOB 2>&1 | tail -5; docker rm -f $JOB >/dev/null; exit 1; }
# 코드는 복사해 넣는다(바인드 마운트는 Docker VM 여유가 적을 때 ENOMEM, struct_base.sh 와 같은 이유). 결과만 experiments 로 쓴다
M=ceco-measure-s13-$$
docker create --name $M --network ${P}_it-net -v ${P}_model-store:/models:ro -v "$REPO/experiments:/experiments" -w /repo \
  l4bench-tools:1.0 python /repo/tests/tools/s13.py --exp $EXP --run $RUN --cands base --mode k4 --model-dir /models >/dev/null
for d in harness simulator; do tar -C "$REPO" -cf - "$d" | docker cp - $M:/repo/ >/dev/null; done
docker start -a $M
rc=$?
docker rm -f $M >/dev/null 2>&1
docker logs $JOB 2>&1 | grep -iE "exception|error" | head -5
docker rm -f $JOB >/dev/null 2>&1
for t in $TOPICS; do $KT --delete --topic $t >/dev/null 2>&1; done
exit $rc
