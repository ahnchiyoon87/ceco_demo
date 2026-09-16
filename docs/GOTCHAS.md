# 구현 중 실제로 부딪힌 함정들

문서만 읽고는 알 수 없었고, 실제로 돌려보고 나서야 드러난 것들입니다.
같은 스택을 구축하려는 분들이 시간을 아끼도록 원인과 해결을 함께 남깁니다.

---

## 1. EdgeX Foundry 4.0 은 3.x 와 구조가 다릅니다

3.x 기준 자료를 그대로 따르면 기동조차 되지 않습니다.

| | EdgeX 3.x | **EdgeX 4.0** |
|---|---|---|
| 서비스 레지스트리 | Consul | **core-keeper** (자체 구현) |
| 데이터베이스 | Redis | **PostgreSQL** |
| 내부 메시지버스 | Redis Streams | **MQTT (mosquitto)** |

확인 방법은 추측이 아니라 공식 compose 를 받는 것입니다.

```bash
curl -O https://raw.githubusercontent.com/edgexfoundry/edgex-compose/v4.0.0/docker-compose-no-secty.yml
```

### 내부 버스용 mosquitto 를 EMQX 와 분리해야 하는 이유

EdgeX 의 내부 메시지버스를 EMQX 로 합치면 컨테이너가 하나 줄지만,
Store-and-Forward 검증이 불가능해집니다. EMQX 를 정지시키면 EdgeX 내부 통신까지
끊겨 device-modbus → core-data 경로가 죽기 때문입니다.
**반출 구간만 끊어야** Store-and-Forward 가 단독으로 검증됩니다.

---

## 2. `service_completed_successfully` 를 쓰면 영구 대기합니다

`core-common-config-bootstrapper` 는 "Core Common Config exiting" 을 로그에 남긴 뒤에도
프로세스가 종료되지 않습니다. 의존 서비스를 `condition: service_completed_successfully`
로 걸면 compose 가 무한 대기하고 하위 서비스가 전부 `Created` 상태로 멈춥니다.

공식 구성이 `service_started` 를 쓰는 데에는 이유가 있습니다 — EdgeX 서비스들은
keeper 에 설정이 올라올 때까지 **재시도하도록 설계**되어 있습니다.

```yaml
depends_on:
  edgex-common-config: { condition: service_started }   # ← completed_successfully 아님
```

---

## 3. `-o` 플래그가 없으면 환경변수가 무시됩니다

EdgeX 4.0 은 서비스 설정을 core-keeper 에 **영속화**합니다. 최초 1회 기동 시에만
환경변수 오버라이드가 적용되고, 이후 재기동에서는 저장된 설정을 그대로 씁니다.
`.env` 를 고쳐도 반영되지 않는 현상의 원인입니다.

```yaml
command: ["--registry", "-cp=keeper.http://edgex-core-keeper:59890", "-o"]
```

`-o`(overwrite)를 붙이면 매 기동 시 파일+환경변수로 다시 밀어 넣습니다.
설정 주도 운영에는 사실상 필수입니다.

---

## 4. Store-and-Forward 재시도 설정은 서비스가 아니라 공통 설정에 있습니다

`WRITABLE_STOREANDFORWARD_ENABLED` 는 app-service 에 먹지만
`RETRYINTERVAL` / `MAXRETRYCOUNT` 는 **먹지 않습니다**. 후자는 app-service 의
private config 에 존재하지 않는 키라서 오버라이드가 조용히 건너뛰어집니다.
로그에 "5m0s RetryInterval and 10 max retries" 가 그대로 남아 있으면 이 경우입니다.

keeper 의 실제 키 위치:

```
edgex/v4/app-mqtt-export/Writable/StoreAndForward/Enabled            ← 서비스
edgex/v4/core-common-config-bootstrapper/app-services/Writable/StoreAndForward/RetryInterval   ← 공통
edgex/v4/core-common-config-bootstrapper/app-services/Writable/StoreAndForward/MaxRetryCount   ← 공통
```

따라서 부트스트래퍼에 넣어야 합니다.

```yaml
edgex-common-config:
  environment:
    APP_SERVICES_WRITABLE_STOREANDFORWARD_RETRYINTERVAL: "5s"
    APP_SERVICES_WRITABLE_STOREANDFORWARD_MAXRETRYCOUNT: "1000"
```

---

## 5. deviceCommand 의 `readWrite` 는 소속 리소스와 일치해야 합니다

읽기전용 리소스를 `readWrite: "RW"` 인 deviceCommand 에 넣으면 프로파일이 거부됩니다.

```
Failed to YAML decode Device Profile: device command's ReadWrite permission 'RW'
doesn't align the device resource
```

읽기전용(인터록 상태 등)은 별도 `R` 커맨드로 분리하세요.

---

## 6. EMQX 의 Kafka Sink 는 Enterprise 전용입니다

PDF 를 비롯해 많은 자료가 "EMQX 규칙 엔진으로 Kafka 에 직접 적재" 를 전제하지만,
**오픈소스 EMQX 5.x 에는 Kafka 프로듀서 커넥터 자체가 없습니다.**
대시보드의 데이터 통합 메뉴에도 나타나지 않습니다.

대안으로 Telegraf 를 씁니다. 설정만으로 동작하고 Apache 2.0 입니다.

```toml
[[inputs.mqtt_consumer]]
  servers = ["tcp://emqx:1883"]
  topics = ["edgex/telemetry"]
  qos = 1
[[outputs.kafka]]
  brokers = ["kafka:9092"]
  topic = "sensor.telemetry.raw"
```

---

## 7. Telegraf `json_v2` 의 함정 두 가지

**(a) `object.fields` 는 맵입니다.** 하위 테이블을 쓰면 파싱이 실패합니다.

```toml
# 잘못됨
[inputs.kafka_consumer.json_v2.object.fields]
  value = "float"
[inputs.kafka_consumer.json_v2.object.fields.detail]   # ✗
  type = "string"

# 올바름
[inputs.kafka_consumer.json_v2.object.fields]
  value = "float"
  detail = "string"
```

**(b) 루트 레벨 평면 JSON 에는 `object` 를 쓸 수 없습니다.**
`path = "@"` 도 `path = ""` 도 실패합니다 (`the GJSON path is required`).
`tag` / `field` 항목으로 기술해야 합니다.

```toml
[[inputs.kafka_consumer.json_v2]]
  measurement_name = "process"
  timestamp_path = "ts"
  timestamp_format = "unix_ns"
  [[inputs.kafka_consumer.json_v2.tag]]
    path = "tag"
  [[inputs.kafka_consumer.json_v2.field]]
    path = "value"
    type = "float"
```

**(c) 프로세서 실행 순서는 `order` 로 명시하세요.** 지정하지 않으면 순서가 보장되지 않아
rename 전에 필터가 돌 수 있습니다.

---

## 8. PyFlink 는 linux-aarch64 휠이 없습니다

Apple Silicon 에서 PyFlink 기반 잡을 컨테이너로 돌리려는 계획은 성립하지 않습니다.
PyPI 의 `apache-flink` 는 `macosx_11_0_arm64` 와 `manylinux_x86_64` 만 제공하며,
linux/arm64 컨테이너에서는 소스 tarball 로 떨어져 빌드에 실패합니다.

```bash
curl -s https://pypi.org/pypi/apache-flink/json | \
  python3 -c "import json,sys; d=json.load(sys.stdin); \
  print(sorted({f['filename'].split('-')[-1] for f in d['releases']['1.20.1']}))"
```

Java 잡 + `com.microsoft.onnxruntime` 로 가면 됩니다. 이 JAR 은
`linux-aarch64` / `linux-x64` 네이티브를 모두 번들합니다 (확인 방법: `unzip -l`).
PDF 가 말한 "C++ 기반 ONNX Runtime 임베디드" 에 오히려 더 정확히 부합합니다.

---

## 9. Flink 셰이드 JAR 의 Jackson 충돌

`NoSuchMethodError: JsonParser.getNumberTypeFP()` 가 나면 Jackson 버전 불일치입니다.
원인은 두 겹입니다.

1. **Flink 런타임의 Jackson 과 충돌** → 셰이드 시 relocate 로 격리
2. **셰이드 JAR 내부의 불일치** → 전이 의존으로 `jackson-core` 가 2.15.2,
   `jackson-databind` 가 2.17.2 로 어긋남

relocate 만으로는 2번이 남아 같은 오류가 반복됩니다. BOM 으로 고정하세요.

```xml
<dependencyManagement><dependencies><dependency>
  <groupId>com.fasterxml.jackson</groupId>
  <artifactId>jackson-bom</artifactId>
  <version>2.17.2</version><type>pom</type><scope>import</scope>
</dependency></dependencies></dependencyManagement>
```

확인: `mvn dependency:list | grep jackson`

---

## 10. `flink-connector-base` 는 명시적으로 선언해야 합니다

`DeliveryGuarantee` 를 못 찾는다면 이 경우입니다. `provided` 스코프는 전이되지 않으므로
`flink-streaming-java` 의 하위 의존으로는 컴파일 클래스패스에 들어오지 않습니다.

---

## 11. 이미지 기본 `config.yaml` 을 덮어쓰면 JVM 모듈 옵션이 사라집니다

Flink 1.20 이미지의 `config.yaml` 에는 `env.java.opts.all` 로 20여 개의
`--add-opens` / `--add-exports` 가 들어 있습니다. 설정 파일을 통째로 마운트해
교체하면 이것이 사라져 잡 제출 시 `InaccessibleObjectException` 이 납니다.

```
at java.base/java.lang.reflect.Field.checkCanSetAccessible(Unknown Source)
at ...DataStreamV2SinkTransformationTranslator.registerSinkTransformationTranslator
```

교체할 설정 파일에 `env.java.opts.all` 을 그대로 옮겨 담으세요.

---

## 12. Flink 메트릭 리포터는 이미지에 없습니다

1.20 도커 이미지의 `/opt/flink/opt/` 에는 메트릭 리포터가 포함되지 않습니다.
`cp /opt/flink/opt/flink-metrics-prometheus-*.jar` 는 실패합니다.
Maven Central 에서 직접 받으세요.

---

## 13. sql-client 는 별도의 클라이언트 설정이 필요합니다

서버용 `config.yaml` 의 `rest.address: 0.0.0.0` 은 **바인드 주소**라 클라이언트가
쓸 수 없습니다. 제출용 컨테이너에는 `rest.address: flink-jobmanager` 로 된
별도 설정을 마운트해야 합니다. 그렇지 않으면 `Connection refused` 가 납니다.

### sql-client 의 실패를 grep 으로 잡을 때 주의

출력에 ANSI 색상코드가 섞여 있어 `grep "^\[ERROR\]"` 가 매칭되지 않습니다.
이 때문에 **실패를 성공으로 보고**하는 일이 생깁니다. 색상코드를 먼저 제거하고,
최종 확인은 텍스트가 아니라 **실제 잡 상태**로 하세요.

```bash
sql-client.sh -f x.sql 2>&1 | sed -E 's/\x1b\[[0-9;]*m//g' > log
grep -qE "^\[ERROR\]" log && exit 1
curl -s "$JM/jobs/overview" | grep -o '"state":"RUNNING"' | wc -l
```

---

## 14. `MATCH_RECOGNIZE` 에서 PARTITION BY 컬럼을 MEASURES 에 다시 쓰면 안 됩니다

```
ValidationException: Columns ambiguously defined: {device}
```

PARTITION BY 컬럼은 출력에 자동 포함됩니다. 같은 이름을 MEASURES 에서
다시 정의하지 마세요.

---

## 15. 롤링 Z-Score 는 설정치 램프 구간에서 오탐합니다

공정값이 단조 이동하면 이동평균이 뒤처져 순간적으로 |z| 가 3 을 넘습니다.
실측에서 정상 운전 중 z=3.02~3.09 오탐이 확인되었습니다.

산업 현장의 표준 대응대로 **지속성 조건**을 거세요.
"최근 5샘플 중 3샘플 이상 위반" 을 적용하니 정상 운전 90초 오탐이 0건이 되었습니다.

```sql
SUM(viol) OVER (PARTITION BY tag ORDER BY event_time
                ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) >= 3
```

---

## 16. RocksDB 상태 백엔드는 null 값을 거부합니다

슬라이딩 윈도우를 좌측 시프트할 때, 윈도우가 채 차기 전에 아직 기록되지 않은
슬롯을 읽으면 `MapState.put(key, null)` 이 되어 이렇게 실패합니다.

```
IllegalArgumentException: The record must not be null.
```

윈도우가 차기 전에는 **덧붙이기만** 하고, 가득 찬 뒤에만 시프트하세요.

---

## 17. FUXA 는 산업 프로토콜 드라이버를 런타임 플러그인으로 설치합니다

도커 이미지에 Modbus 드라이버가 들어있지 않습니다. 설치하지 않으면 디바이스가
**조용히 기동되지 않습니다** (로그에 해당 디바이스의 start 만 찍히고 connect 는 없음).

```bash
curl -X POST http://localhost:1881/api/plugins \
  -H 'Content-Type: application/json' \
  -d '{"params":{"name":"modbus-serial","version":"8.0.19"}}'
```

`GET /api/plugins` 의 `current` 가 비어 있으면 미설치입니다.

---

## 18. FUXA Modbus 주소 체계

문서화가 부족해 소스를 읽어야 확인되는 부분입니다.

| 항목 | 값 | 근거 |
|---|---|---|
| `address` | **1-based** | 드라이버가 `parseInt(address) - 1` 수행 |
| 코일 `memaddress` | **`"000000"`** | `getMemoryAddress()` 가 리터럴 `'000000'` 로 키 생성 |
| 디스크리트 입력 | `"100000"` | |
| 입력 레지스터 | `"300000"` | |
| 홀딩 레지스터 | `"400000"` | |
| `Float32` | big-endian ABCD (워드 스왑 없음) | 스왑이 필요하면 `Float32MLE` |

코일에 `"0"` 을 쓰면 이렇게 실패합니다.

```
'AR100' load error! TypeError: Cannot read properties of undefined (reading 'Items')
```

---

## 19. FUXA 런타임 API 는 bare tag id 를 받습니다

`^~^` 구분자 형식(`AR100^~^PumpRun`)은 **HMI 아이템의 `variableId` 전용**입니다.
`/api/getTagValue`, `/api/setTagValue` 에는 순수 태그 id 를 넘겨야 합니다.

```bash
# 읽기
curl "http://localhost:1881/api/getTagValue?ids=%5B%22TT_101%22%5D"
# 쓰기
curl -X POST http://localhost:1881/api/setTagValue \
  -H 'Content-Type: application/json' \
  -d '{"tags":[{"id":"PumpRun","value":0}]}'
```

`device-values` 웹소켓 이벤트가 빈 배열로 오는 것은 정상입니다.
`broadcastAll: false` 기본값 때문에 뷰를 연 클라이언트가 없으면 전송하지 않습니다.

---

## 20. 오토인코더는 "정상 변동" 없이는 학습할 것이 없습니다

설정치가 고정된 정상 데이터로 학습하면 모델이 배울 상관 구조가 없어
단일 태그 Z-Score 와 구별되지 않습니다. 실제로 정상 구간의 pH↔전도도 상관이
0에 가깝게 나왔습니다.

시뮬레이터에 **autopilot**(생산 스케줄에 따른 설정치 변동)을 넣자
물리적으로 타당한 상관 구조가 형성되었습니다.

| 태그 쌍 | 상관계수 |
|---|---|
| FT-101 ↔ IT-101 | +0.99 |
| TT-101 ↔ pH-101 | −0.98 |
| LT-102 ↔ PT-101 | +0.94 |
| pH-101 ↔ CT-101 | **−0.93** ← drift 고장이 +0.99 로 뒤집음 |

다만 변동을 너무 크게 주면 고장 신호가 정상 변동에 묻힙니다. 학습 후
**판별력 자가 검증**(정상 오탐률 vs 시나리오별 탐지율)을 반드시 돌려서
양쪽 균형을 확인하세요.

---

## 21. 가속 시뮬레이션에서 벽시계를 쓰면 안 됩니다

고장의 램프·지연(`lag_s`)을 `time.monotonic()` 기준으로 계산하면, 배속으로 도는
테스트에서 경과 시간이 거의 0이라 효과가 나타나지 않습니다.
적분된 **시뮬레이션 시각**을 기준으로 하세요. 그래야 1 Hz 실시간 구동과
배속 테스트가 동일하게 재현됩니다.

---

## 22. 검증 루프에서 `step()` 을 태그마다 호출하지 마세요

```python
# 잘못됨 — 한 행이 12개의 서로 다른 시각에서 조합되고 시뮬레이션이 12배속으로 흐름
rows = [[plant.step(1.0)[t] for t in tags] for _ in range(n)]

# 올바름
for i in range(n):
    r = plant.step(1.0)
    rows[i] = [r[t] for t in tags]
```

이 버그 때문에 모델 판별력 검증이 "정상 오탐 49% / drift 탐지 43.9%" 라는
무의미한 결과를 냈습니다. 고치니 "정상 0.5% / drift 100%" 가 되었습니다.
