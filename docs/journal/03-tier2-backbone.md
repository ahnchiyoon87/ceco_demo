# 3. Tier 2 · 수집 미들웨어와 엔터프라이즈 백본

> 교재 활용: **4차시 — MQTT 브로커와 Kafka, 그리고 그 사이를 잇는 문제**

## 3.1 설계 변경의 출발점

PDF p.10 은 이렇게 말합니다.

> EMQX의 데이터 통합 브리지를 통해 수신된 센서 텔레메트리는 지체 없이
> Apache Kafka 클러스터의 sensor.telemetry.raw 토픽으로 적재된다.

[1장의 실사](01-analysis.md)에서 확인했듯 **이 기능은 Enterprise 전용**입니다.
따라서 이 자리를 무엇으로 채울지가 Tier 2 의 핵심 결정이었습니다.

### 후보 비교

| 대안 | 장점 | 단점 | 판정 |
|---|---|---|---|
| EMQX Enterprise | PDF 그대로 | 상용 라이선스, 체험판 제약 | ✗ "오픈소스 예제" 목표와 충돌 |
| Kafka Connect + MQTT 소스 | Kafka 생태계 표준 | Confluent 커넥터는 독점, 대안은 설정 복잡 | △ |
| **Telegraf** | **TOML 설정만, 공식 이미지, Apache 2.0** | 별도 컴포넌트 추가 | **✓ 채택** |
| 자체 브리지 코드 | 완전한 제어 | "설정만으로 동작" 목표 위반 | ✗ |

Telegraf 를 고른 결정적 이유: PDF 가 **Tier 4 에서 이미 Telegraf 를 언급**하므로
새로운 기술을 들이는 것이 아니라 이미 스택에 있는 도구의 활용 범위를 넓히는 것입니다.

---

## 3.2 데이터 계약 설계

어느 경로로 들어오든 Kafka 진입 시점에 **단일 스키마**로 정규화합니다.

```json
{
  "ts":      1789546028493305900,
  "site":    "AR-100",
  "device":  "reactor-line-01",
  "tag":     "FT-102",
  "value":   6.286102,
  "quality": "GOOD"
}
```

설계 근거:

| 필드 | 이유 |
|---|---|
| `ts` 나노초 | InfluxDB 의 나노초 정밀도 활용 (PDF p.7 표) |
| `quality` | 실측/추정 구분. 감사 추적의 근거 (PDF p.5) |
| `tag` 를 파티션 키로 | 태그 단위 순서 보장 → Flink keyed state 정합 |

### 멱등성에 대한 결정

PDF p.4 는 "고유 시퀀스 번호와 타임스탬프를 페이로드에 포함한 QoS 1" 을 권고합니다.
EdgeX 경로에서는 시퀀스 번호를 각 리딩에 붙이기 어려워
**(tag, ts) 를 멱등 키로 삼는 방식**을 택했습니다. EdgeX 의 `origin` 이
나노초 단위이므로 태그별로 충돌하지 않습니다.

```java
// Interpolator.processElement
Long lastTs = lastEmittedTsNs.value();
if (lastTs != null && in.ts <= lastTs) {
    return;   // QoS1 재전송으로 인한 중복 제거
}
```

---

## 3.3 Telegraf 브리지 구성

### EdgeX 경로 — 중첩 JSON 파싱

EdgeX Event 는 `readings[]` 배열 구조라 `object` 파서를 씁니다.

```toml
[[inputs.mqtt_consumer.json_v2]]
  measurement_name = "sensor"
  [[inputs.mqtt_consumer.json_v2.object]]
    path = "readings"
    timestamp_key = "origin"
    timestamp_format = "unix_ns"
    tags = ["resourceName", "deviceName"]
    [inputs.mqtt_consumer.json_v2.object.fields]
      value = "float"       # EdgeX 는 값을 문자열로 싣는다 → 강제 변환
```

### 출력 스키마 변환 — JSONata

Telegraf 의 기본 JSON 출력은 `{name, tags, fields, timestamp}` 형태라
우리 계약과 다릅니다. `json_transformation` 으로 변환합니다.

```toml
[[outputs.kafka]]
  topic = "sensor.telemetry.raw"
  routing_tag = "tag"           # 파티션 키
  required_acks = -1            # 전 replica ack (무손실)
  data_format = "json"
  json_timestamp_units = "1ns"
  json_transformation = '''
  {
    "ts": $number(timestamp), "site": tags.site, "device": tags.device,
    "tag": tags.tag, "value": fields.value, "quality": tags.quality
  }
  '''
```

### 센티널 필터링 — 결측을 진짜 결측으로

시뮬레이터는 통신 불량을 `-999999.0` 센티널로 표현합니다.
Modbus 레지스터는 "값이 없음" 을 표현할 수 없기 때문입니다.
이 값을 Telegraf 에서 걸러내야 **Kafka 상에 실제 공백**이 생기고
Flink 의 보간이 의미를 갖습니다.

```toml
[[processors.starlark]]
  order = 3
  source = '''
BAD_QUALITY = -999998.0
def apply(metric):
    tag = metric.tags.get("tag")
    if tag == None or tag not in SENSOR_TAGS:
        return None          # 제어 태그·SEQ 는 텔레메트리에서 제외
    v = metric.fields.get("value")
    if v == None or v <= BAD_QUALITY:
        return None          # 통신 불량 → 발행하지 않음
    metric.tags["quality"] = "GOOD"
    return metric
'''
```

> **교육 포인트**: 프로토콜이 표현할 수 없는 의미(여기서는 "결측")를
> 어떻게 전달할지는 산업 통신의 오래된 문제입니다. 센티널 값, 별도 품질 레지스터,
> 프로토콜 예외 응답 등의 선택지가 있고 각각 장단이 있습니다.

### 함정 — 프로세서 실행 순서

Telegraf 프로세서는 `order` 를 지정하지 않으면 실행 순서가 보장되지 않습니다.
`rename`(태그명 정규화) 이 `starlark`(필터) 보다 먼저 돌아야 하므로 명시했습니다.

---

## 3.4 Kafka 토픽 설계

```bash
create sensor.telemetry.raw   6 86400000    # 무손실 원본
create sensor.telemetry.clean 6 86400000    # 중복제거 + 보간 완료
create sensor.anomaly.score   3 86400000    # 재구성 오차 + 기여 센서
create sensor.alerts          3 604800000   # 통합 알람 (7일 보존)
```

`raw` 와 `clean` 을 분리한 것이 이 설계의 핵심입니다.
**원본은 절대 덮어쓰지 않는다** 는 PDF p.5 의 무결성 원칙을 토폴로지로 강제합니다.

---

## 3.5 검증

### 스키마 확인

```bash
docker exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic sensor.telemetry.raw --max-messages 5
```

```json
{"device":"reactor-line-01","quality":"GOOD","site":"AR-100","tag":"FT-102","ts":1789546028493305900,"value":6.286102}
{"device":"reactor-line-01","quality":"GOOD","site":"AR-100","tag":"LT-102","ts":1789546028492632000,"value":54.991196}
```

### 처리량 측정 — 컨슈머 대신 오프셋

```bash
off(){ docker exec kafka /opt/kafka/bin/kafka-get-offsets.sh \
        --bootstrap-server localhost:9092 --topic "$1" | awk -F: '{s+=$3} END{print s+0}'; }
a=$(off sensor.telemetry.raw); sleep 20; b=$(off sensor.telemetry.raw)
echo "$((b-a))건/20초"
```

```
252건/20초  →  12건/초  (12태그 × 1Hz, 기대치와 일치)
```

> **교육 포인트**: 처리량 측정에 콘솔 컨슈머를 쓰면 JVM 기동 시간과
> 백로그 드레인 때문에 과대 측정됩니다. 실제로 이 프로젝트에서
> 한때 "4.7배 과다" 로 오판했고, 오프셋 차분으로 재측정해 바로잡았습니다.

### 결측 구간이 실제로 생기는가

```
총 2266건 / 태그 12종
  TT-101(결측대상) 176건   LT-102(대조군) 190건   누락 14건
  TT-101 2초 초과 공백: [15.0]
  → Kafka 에 실제 결측 구간 생성됨 (Flink 보간 대상)
```

대조군(LT-102)은 연속인데 대상(TT-101)에만 15.0초 공백이 생겼습니다.

---

## 3.6 Tier 2 완료 확인

```
Tier 2 · 수집 & 백본 — 무손실 유입
  ✓ Kafka 토픽 구성  — 4개 토픽
  ✓ 정규화 스키마 일관성  — 444건 / 태그 12종
  ✓ 나노초 타임스탬프 보존  — InfluxDB 정밀도 활용 (PDF p.7)
결과: 3/3 통과
```

---

## 3.7 실습 과제 (교재용)

1. `lite` 프로파일(`make lite`)로 기동해, EdgeX 를 거치지 않아도
   Kafka 진입 스키마가 동일함을 확인하시오.
2. `telegraf/bridge-edgex.conf` 의 starlark 필터를 제거하고
   `dropout` 을 주입했을 때 Kafka 에 무엇이 들어오는지 관찰하시오.
3. `required_acks` 를 `1` 로 바꾸면 어떤 장애 상황에서 데이터가 유실될 수 있는지
   설명하시오.
