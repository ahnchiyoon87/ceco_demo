# 10. 설정 파일 레퍼런스

> 교재 활용: **실습 자료** — 각 설정의 "왜 이 값인가" 를 담았습니다.

## 10.1 설정 파일 지도

```
.env                              포트·버전·자격증명 (전역)
simulator/plant.yaml              ★ 태그·레지스터맵·물리파라미터·고장 (단일 출처)
edgex/profiles/ar100.profile.yaml   (자동 생성)
edgex/devices/ar100.devices.yaml    (자동 생성)
emqx/emqx.conf                    QoS1·세션 영속
kafka/create-topics.sh            토픽·파티션·보존
telegraf/bridge-edgex.conf        MQTT→Kafka (EdgeX 경로)
telegraf/bridge-lite.conf         MQTT→Kafka (우회 경로)
telegraf/sink.conf                Kafka→InfluxDB
telegraf/alert-republish.conf     Kafka→MQTT (FUXA 알람)
flink/conf/config.yaml            체크포인트·재시작·상태백엔드
flink/conf/client-config.yaml     잡 제출용 (rest.address 분리)
flink/sql/*.sql                   Tier-1 탐지 전체
flink/sql/tag_limits.csv            (자동 생성)
flink/onnx-job/job.properties     보간 방식·윈도우·임계치
ml/train.yaml                     학습 데이터·모델구조·임계치
grafana/provisioning/**           데이터소스·대시보드
fuxa/project.json                   (자동 생성)
prometheus/{prometheus,rules,alertmanager}.yml
```

★ 표시가 단일 출처입니다. 여기를 고치고 `make regen-edgex && make regen-fuxa`.

---

## 10.2 주요 설정값과 근거

### EMQX — 무손실 수집

```hocon
mqtt {
  max_qos_allowed = 2
  session_expiry_interval = 2h    # 에지 단절 후 재접속까지 메시지 보존
  max_mqueue_len = 100000         # 오프라인 큐 길이
  max_inflight = 128
}
```

`session_expiry_interval` 이 핵심입니다. PDF p.4 의 "세션 영속성을 활성화하여
일시적인 물리 계층 단절 시에도 브로커가 미전송 메시지를 보존" 에 해당합니다.
2시간은 데모용이며, 실제로는 에지 게이트웨이의 최대 예상 단절 시간으로 잡습니다.

### Kafka — 토픽 설계

```bash
create sensor.telemetry.raw   6 86400000     # 파티션 6, 보존 24h
create sensor.telemetry.clean 6 86400000
create sensor.anomaly.score   3 86400000
create sensor.alerts          3 604800000    # 알람만 7일
```

파티션 6 = 태그 12개를 2개씩 나눠 담을 수 있는 크기.
파티션 키가 `tag` 이므로 태그 단위 순서가 보장되고, Flink 의 keyed state 와 정합합니다.

### Flink — 체크포인트와 상태

```yaml
execution:
  checkpointing:
    interval: 10s
    mode: EXACTLY_ONCE
    externalized-checkpoint-retention: RETAIN_ON_CANCELLATION
state:
  backend:
    type: rocksdb          # PDF p.6 — RocksDB 기반 분산 상태 저장소
    incremental: true
restart-strategy:
  type: exponential-delay  # ← 이것이 없으면 복구가 일어나지 않는다
```

`restart-strategy` 를 빠뜨리면 체크포인트가 있어도 잡이 죽은 채로 남습니다.
[ADR-010](08-decisions.md) 참조.

### Flink ONNX 잡

```properties
interpolation.mode       = linear      # linear | locf
interpolation.max-gap-ms = 20000       # 초과 시 LOCF 로 대체
scan.interval.ms         = 1000
window.steps             = 10          # ml/train.yaml 과 반드시 일치
inference.interval.ms    = 1000
anomaly.threshold        =             # 비우면 model_meta.json 값 사용
```

`window.steps` 가 학습 설정과 다르면 텐서 차원이 맞지 않아 추론이 실패합니다.
두 파일을 함께 고쳐야 합니다.

### 오토인코더 학습

```yaml
data:
  warmup_s: 1800        # 초기 과도구간 폐기
  duration_s: 21600     # 6시간 상당
  autopilot: true       # ← false 면 학습할 상관 구조가 없어짐
model:
  window_steps: 10
  hidden: [64, 16]      # 120 → 64 → 16 → 64 → 120
  epochs: 60
threshold:
  percentile: 99.5
  safety_factor: 1.15
```

`autopilot: false` 로 바꾸면 모델이 무의미해집니다([ADR-007](08-decisions.md)).

### Z-Score 지속성

```sql
CASE WHEN z > 3.5 THEN 1 ELSE 0 END AS viol
...
SUM(viol) OVER (... ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) >= 3
```

3.5 와 "5중 3" 은 실측으로 정한 값입니다. 3.0 + 지속성 없음일 때
정상 운전 2분간 8건 오탐이 발생했습니다.

### CEP 패턴

```sql
PATTERN (OVERCURRENT OTHER*? VIB) WITHIN INTERVAL '10' SECOND
```

`OTHER*?` 없이는 두 조건이 같은 스캔에 있을 때만 매칭되어
시간 간격이 항상 0으로 나옵니다([사례 4-4](04-tier3-stream.md)).

### Prometheus 경보

```yaml
- alert: KafkaConsumerLagHigh
  expr: sum by (consumergroup, topic) (kafka_consumergroup_lag) > 5000
  for: 2m
- alert: FlinkCheckpointFailing
  expr: increase(flink_jobmanager_job_numberOfFailedCheckpoints[5m]) > 2
- alert: TelemetryIngestStalled
  expr: sum(rate(kafka_topic_partition_current_offset{topic="sensor.telemetry.raw"}[2m])) == 0
  for: 2m
```

전부 **파이프라인 자체**의 건전성입니다. 공정 이상은 Flink → `sensor.alerts` 경로가
담당하며 Prometheus 는 관여하지 않습니다.

---

## 10.3 자주 바꾸게 되는 값

| 목적 | 파일 | 키 |
|---|---|---|
| 부하 시험 | `.env` | `SCAN_INTERVAL_MS` (1000 → 100) |
| 알람 민감도 | `flink/sql/03_tier1_zscore.sql` | `z > 3.5`, `viol_run >= 3` |
| ML 민감도 | `ml/train.yaml` | `threshold.percentile`, `safety_factor` |
| 보간 방식 | `flink/onnx-job/job.properties` | `interpolation.mode` |
| 공정 규격 | `simulator/plant.yaml` | 태그의 `lsl`/`usl` |
| 운전 변동 폭 | `simulator/plant.yaml` | `autopilot.ranges` |
| 병렬도 | `flink/conf/config.yaml` | `parallelism.default` |

---

## 10.4 설정 변경 시 재시작 범위

| 변경 | 필요한 조치 |
|---|---|
| `.env` 포트/버전 | `make down && make up` |
| `plant.yaml` 태그 | `make regen-edgex && make regen-fuxa && make up` |
| `plant.yaml` 고장/물리 | 시뮬레이터 재빌드 + 재기동 |
| `flink/sql/*.sql` | `make jobs` |
| `job.properties` | Flink 이미지 재빌드 + `make jobs` |
| `ml/train.yaml` | `make train && make jobs` |
| `telegraf/*.conf` | 해당 컨테이너 재기동 |
| `prometheus/rules.yml` | `docker compose restart prometheus` |
| `grafana/dashboards/*.json` | 자동 반영 (30초) |
