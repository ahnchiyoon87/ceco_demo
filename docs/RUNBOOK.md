# 운영 런북

## 기동 / 정지

```bash
make up            # 전체 기동 (EdgeX 경유)
make lite          # EdgeX 우회 경량 기동
make down          # 중지 (데이터 보존)
make clean         # 중지 + 볼륨 삭제
make ps            # 상태
make logs S=<서비스>  # 개별 로그
```

최초 `make up` 은 다음을 수행하므로 5~10분 걸립니다.

1. 시뮬레이터 / Flink(Maven 빌드) / 학습기 이미지 빌드
2. EdgeX 부트스트랩 (core-keeper → 공통설정 → 메타데이터 → 데이터 → 디바이스)
3. 오토인코더 학습 (6시간 상당 정상 데이터 합성 → 60 epoch → ONNX)
4. Flink 잡 4종 자동 제출
5. FUXA Modbus 플러그인 설치 + P&ID 화면 주입

두 번째 실행부터는 레이어 캐시와 모델 볼륨이 재사용되어 2~3분입니다.

---

## 기동 순서 의존성

```
edgex-postgres ──┐
edgex-mqtt-broker┴→ core-keeper → common-config → metadata → data → device-modbus
                                                           └→ app-mqtt-export
plant-simulator ────────────────────────────────────────────┘

kafka → kafka-init ─┐
emqx ───────────────┴→ telegraf-bridge
model-trainer ──────┐
flink-jobmanager ───┴→ flink-job-submitter
influxdb → telegraf-sink → grafana
fuxa → fuxa-provisioner
```

`flink-job-submitter` 는 `kafka-init` 과 `model-trainer` 가 **정상 종료**해야 시작합니다.
모델이 없으면 Tier-2 잡이 뜨지 않습니다.

---

## 설정 변경

| 바꾸고 싶은 것 | 파일 | 적용 |
|---|---|---|
| 포트, 이미지 버전, 자격증명 | `.env` | `make down && make up` |
| 공정 태그·레지스터맵·물리 파라미터 | `simulator/plant.yaml` | `make regen-edgex && make regen-fuxa && make up` |
| 고장 시나리오 | `simulator/plant.yaml` 의 `faults:` | 시뮬레이터 재기동 |
| 임계치·Z-Score·CEP 규칙 | `flink/sql/*.sql` | `make jobs` |
| USL/LSL 규격 | `simulator/plant.yaml` → `flink/sql/tag_limits.csv` 재생성 | `make jobs` |
| 보간 방식 (linear/locf) | `flink/onnx-job/job.properties` | 이미지 재빌드 후 `make jobs` |
| 오토인코더 구조·임계치 | `ml/train.yaml` | `make train && make jobs` |
| 인프라 경보 룰 | `prometheus/rules.yml` | `docker compose restart prometheus` |
| 대시보드 | `grafana/dashboards/*.json` | 30초 내 자동 반영 |

> `plant.yaml` 이 태그 정의의 단일 출처입니다. 여기만 고치고 재생성하면
> EdgeX 프로파일과 FUXA 화면이 따라옵니다.

---

## 자주 겪는 문제

### Flink 잡이 뜨지 않음

```bash
make jobs                                      # 재제출 (멱등)
docker compose logs flink-job-submitter        # 제출 로그
curl -s localhost:27081/jobs/overview          # 실제 상태
```

제출기는 텍스트가 아니라 **실제 RUNNING 잡 수**로 성공을 판정하므로,
"제출 완료" 라고 나왔는데 잡이 없는 일은 발생하지 않습니다.

예외 상세는 Flink UI(http://localhost:27081) → 해당 잡 → Exceptions.

### FUXA 화면에 값이 안 보임

```bash
curl -s localhost:27018/api/plugins | grep -A1 modbus-serial   # current 가 비어있으면 미설치
docker compose run --rm fuxa-provisioner                       # 플러그인 설치 + 화면 재주입
```

값 확인은 bare tag id 로 합니다.

```bash
curl "localhost:27018/api/getTagValue?ids=%5B%22TT_101%22%5D"
```

### EdgeX 가 기동되지 않음

```bash
docker compose logs edgex-core-keeper edgex-common-config
docker compose restart edgex-device-modbus
```

설정을 바꿨는데 반영되지 않으면 keeper 에 남은 이전 설정 때문입니다.
compose 의 EdgeX 서비스는 전부 `-o`(overwrite) 로 실행되므로 재기동하면 갱신됩니다.
그래도 안 되면 `make clean` 으로 볼륨을 지우세요.

### 알람이 과도하게 발생

```bash
make fault-clear                                 # 주입된 고장 해제
docker exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic sensor.alerts --timeout-ms 30000
```

`detector` 필드로 어느 계층이 내는지 구분합니다.
`TIER1_ZSCORE` 가 과다하면 `flink/sql/03_tier1_zscore.sql` 의 임계치(3.5)와
지속성 조건(최근 5중 3회)을 조정하세요.

### 컨슈머 랙 증가

```bash
curl -s 'localhost:27090/api/v1/query?query=sum(kafka_consumergroup_lag)'
docker compose logs telegraf-sink | tail
```

대개 InfluxDB 쓰기 지연입니다. `telegraf/sink.conf` 의 `metric_batch_size` 를 키우거나
Flink 병렬도(`flink/conf/config.yaml` 의 `parallelism.default`)를 올리세요.

---

## 리소스

| 항목 | 값 |
|---|---|
| 컨테이너 | 약 29개 (lite 20개) |
| 메모리 | 약 8 GB |
| 디스크 | 이미지 약 6 GB + 데이터 |
| 유입량 | 12 건/초 (12태그 × 1 Hz) |

Docker Desktop 메모리를 12 GB 이상으로 잡아 두세요.
부하 시험을 하려면 `.env` 의 `SCAN_INTERVAL_MS` 를 낮추고
Kafka 파티션과 Flink 병렬도를 함께 올립니다.

---

## 백업 대상

| 볼륨 | 내용 |
|---|---|
| `iiot_influx-data` | 공정 히스토리안 (가장 중요) |
| `iiot_model-store` | 학습된 ONNX 모델 + 정규화 계수 |
| `iiot_fuxa-appdata`, `iiot_fuxa-db` | SCADA 화면 및 DAQ |
| `iiot_flink-checkpoints` | 스트림 상태 |
| `iiot_edgex-db` | 디바이스 등록 정보 |

FUXA 화면은 `fuxa/project.json` 에서 언제든 재생성되므로 볼륨이 날아가도
`make regen-fuxa` 로 복구됩니다.
