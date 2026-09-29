# [측정 도구] baseline.sh 의 V2 이름표(docker-compose.v2.yml). 같은 시험을 같은 방법으로, 대상 컨테이너 이름만 다름.
BROKER_C=rot-mqtt; BROKER_H=mqtt
UPLINK_C=rot-ingest          # R02: 수집기의 백본 쪽 망(rot-iiot)만 끊음 — 설비 전용망(rot-iiot-field)으로 읽기는 계속(V1 R02 와 같은 의미)
KAFKA_C=rot-kafka; TS_C=rot-influxdb; SINK_C=rot-relay
FIX_C="rot-ingest rot-relay"; SUBMIT_C=rot-flink-job-submitter
SCADA="docker compose --env-file .env --env-file .env.rotation -f docker-compose.v2.yml"
phase0_V2(){
  say "P0 V2 기동 확인"
  $SCADA up -d >>$LOG 2>&1
  docker stop rot-ai-embed-1 rot-ai-knowledge-1 rot-ai-graph-1 >>$LOG 2>&1
  docker run --rm -v rot-ai_graph-snap-A:/from:ro -v rot-ai_graph-data:/to alpine:3.22 sh -c "rm -rf /to/*; cp -a /from/. /to/"
  $AI up -d --no-build --wait graph work-db knowledge alarm-worker web >>$LOG 2>&1
  docker inspect rot-plant-simulator rot-ai-knowledge-1 --format '{{.Name}} {{.Config.Image}}' | tee -a $LOG
  ensure_jobs
}
LOAD_KAFKA=kafka:9092     # R08: V2 원시 입구는 Kafka(수집기가 바로 씀)
E1_TOPICS=scada/hmi/latest-alert   # V2 는 화면이 구독하는 최근알람 토픽 하나만 낸다(태그별 토픽은 구독처 없음, #124). V1 비교값 = '최근알람'
