# 6. Tier 4 · 저장·감시·관제

> 교재 활용: **9차시 — 히스토리안과 인프라 감시의 분리** / **10차시 — 웹 SCADA 와 양방향 제어**

## 6.1 역할 분리 — 설계 규약을 코드로 강제하기

PDF p.7 결론 5 는 InfluxDB 와 Prometheus 의 이원화를 요구합니다.
문서로 적어두는 것만으로는 지켜지지 않으므로, **검증 항목으로 넣었습니다.**

```python
series = get(f"{PROM}/api/v1/label/__name__/values")["data"]
sensor_leak = [m for m in series
               if any(t.replace("-","_").lower() in m.lower()
                      for t in ["LT_101","TT_101","PT_101","pH_101"])]
check("Prometheus 에 센서 데이터 없음 (역할 분리)", not sensor_leak, ...)
```

```
✓ Prometheus 에 센서 데이터 없음 (역할 분리)
  — 메트릭 993종 중 공정태그 0개 — PDF p.7 결론 5
```

> **교육 포인트**: 아키텍처 규약은 **테스트로 만들어야** 유지됩니다.
> "센서 데이터를 Prometheus 에 넣지 마세요" 라는 위키 문서는 6개월 뒤에 깨집니다.

### 두 시스템의 역할

| | InfluxDB | Prometheus |
|---|---|---|
| 저장 | 12개 공정 태그, 이상 점수, 알람 이력 | 컨슈머 랙, 체크포인트, EMQX 세션, 컨테이너 리소스 |
| 수집 | Push (Line Protocol) | Pull (scrape) |
| 근거 | 나노초 정밀도, 고카디널리티 대응 | 고카디널리티에 취약 |

실제 스크랩 타깃:

```
✓ Prometheus 인프라 스크랩 — 7/7 타깃 정상:
  cadvisor, emqx, flink(×2), influxdb, kafka, prometheus
```

---

## 6.2 Telegraf 싱크 — json_v2 의 함정 두 가지

### 함정 1 — `object.fields` 는 맵이다

```toml
# 잘못됨
[inputs.kafka_consumer.json_v2.object.fields]
  value = "float"
[inputs.kafka_consumer.json_v2.object.fields.detail]   # 하위 테이블 불가
  type = "string"
```

```
E! loading config file failed: error parsing kafka_consumer, adding parser failed:
   line 93: cannot unmarshal TOML table into string (need struct or map)
```

```toml
# 올바름
[inputs.kafka_consumer.json_v2.object.fields]
  value = "float"
  detail = "string"
```

### 함정 2 — 루트 레벨 평면 JSON 에는 `object` 를 쓸 수 없다

우리 스키마는 중첩이 없는 평면 객체입니다. `object` 파서에 루트를 지정하려 했으나:

```toml
path = "@"    →  E! the path "@" doesn't exist
path = ""     →  E! the GJSON path is required
```

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

> **교육 포인트**: 중첩 JSON(`object`)과 평면 JSON(`tag`/`field`)의 파서가
> 다르다는 점이 Telegraf 문서에서 잘 드러나지 않습니다.
> EdgeX 경로(중첩)와 lite 경로(평면)에서 서로 다른 파서를 쓴 이유입니다.

### 적재 결과

```
=== measurement 별 최근 5분 건수 ===
  alerts        426
  anomaly      1196
  process      3576
  process_raw  3534

=== quality 태그 분포 ===
  GOOD                 15858
  INTERPOLATED_LINEAR     42
```

`quality` 가 InfluxDB 태그로 보존되어 **감사 추적이 히스토리안까지 성립**합니다.

---

## 6.3 FUXA — 소스를 읽어야 했던 것들

FUXA 는 문서가 적어 소스 확인이 필수였습니다. 다만 **확인 경로가 명확**해서
오래 걸리지는 않았습니다.

### 6.3.1 프로젝트 스키마 — 데모 파일에서 역공학

```bash
curl -sL -o demo.fuxap \
  "https://raw.githubusercontent.com/frangoteam/FUXA/master/server/project.demo.fuxap"
python3 -c "
import json
d = json.load(open('demo.fuxap', encoding='utf-8-sig'))   # BOM 주의
print(list(d.keys()))
"
```

```
['devices', 'hmi', 'version', 'name', 'charts', 'server']
```

핵심 발견:

| 항목 | 구조 |
|---|---|
| `devices` | 디바이스 **이름**을 키로 하는 맵 |
| `hmi.views[].svgcontent` | 화면 전체가 **하나의 SVG 문자열** |
| `hmi.views[].items` | SVG 요소 `id` → 바인딩 속성 맵 |
| `variableId` | `"<디바이스명>^~^<태그id>"` |

위젯별 SVG 구조도 데모에서 그대로 추출했습니다.

```
#### svg-ext-value
<g id="VAL_xxx" type="svg-ext-value" ...>
  <text id="tVAL_xxx" ...>##.##</text>
</g>

#### svg-ext-html_button
<g id="HXB_xxx" type="svg-ext-html_button" ...>
  <rect .../>
  <foreignObject id="H-HXB_yyy" ...>
    <BUTTON id="B-HXB_yyy" class="md-btn md-btn-raised">ON</BUTTON>
  </foreignObject>
</g>

#### svg-ext-motor
<g id="MTR_xxx" type="svg-ext-motor" ...>
  <ellipse id="cMTR_xxx" .../>     ← 'c' 접두사 요소의 색이 range 로 바뀜
  <path id="sMTR_xxx" .../>
</g>
```

### 6.3.2 Modbus 주소 체계 — 드라이버 소스에서

```bash
curl -sL -o mb.js \
  "https://raw.githubusercontent.com/frangoteam/FUXA/master/server/runtime/devices/modbus/index.js"
grep -n "address) - 1" mb.js
```

```javascript
var offset = parseInt(data.tags[id].address) - 1;
// because settings address from 1 to 65536 but communication start from 0
```

**1-based** 입니다. 그리고 메모리 영역 키:

```javascript
const ModbusMemoryAddress = { CoilStatus: 0, DigitalInputs: 100000,
                              InputRegisters: 300000, HoldingRegisters: 400000 };
const formatAddress = function (address, token) { return token + '-' + address; }

// getMemoryAddress() 내부
if (address < ModbusMemoryAddress.DigitalInputs) {
    if (tokenized) return formatAddress('000000', token);   // ← 리터럴 '000000'
}
```

`memaddress` 를 `"0"` 으로 쓰면 키가 `"0-0"` 이 되는데
드라이버는 `"0-000000"` 을 찾으므로 불일치합니다.

```
'AR100' load error! TypeError: Cannot read properties of undefined (reading 'Items')
```

| 영역 | memaddress |
|---|---|
| 코일 | **`"000000"`** |
| 디스크리트 입력 | `"100000"` |
| 입력 레지스터 | `"300000"` |
| 홀딩 레지스터 | `"400000"` |

데이터타입도 확인:

```javascript
Float32: _gen(4, 'FloatBE', 2),           // 스왑 없음 = big-endian ABCD
Float32MLE: _gen(4, 'FloatBE', 2, 2),     // 워드 스왑
```

시뮬레이터가 `struct.pack('>f', v)` 로 쓰므로 `Float32` 가 맞습니다.

### 6.3.3 드라이버가 플러그인이다

디바이스가 **조용히 기동되지 않았습니다.** 로그에 `'AR100' start` 는 있는데
연결 메시지가 없었습니다.

```bash
curl -s localhost:27018/api/plugins | python3 -c "..."
```

```
  node-opcua         current=
  modbus-serial      current=          ← 비어 있음 = 미설치
  node-red           current=4.1.11
```

`registry['modbus-serial'] = new Plugin('modbus-serial', './modbus', 'Modbus', '8.0.19', ...)`

설치:

```bash
curl -X POST http://localhost:27018/api/plugins \
  -H 'Content-Type: application/json' \
  -d '{"params":{"name":"modbus-serial","version":"8.0.19"}}'
```

프로비저너가 자동으로 하도록 넣었습니다.

```python
REQUIRED_PLUGINS = [("modbus-serial", "8.0.19")]

def ensure_plugins():
    installed = {p.get("name"): p.get("current") for p in call("/api/plugins")}
    for name, version in REQUIRED_PLUGINS:
        if installed.get(name):
            continue
        call("/api/plugins", {"params": {"name": name, "version": version}}, timeout=300)
```

### 6.3.4 런타임 API 는 bare tag id 를 받는다

```bash
# 실패
curl "localhost:27018/api/getTagValue?ids=%5B%22AR100%5E~%5EPumpRun%22%5D"
# → "AR100^~^PumpRun not found"
```

소스 확인:

```javascript
function getDeviceIdFromTag(sigid) {
    for (var id in activeDevices) {
        var tag = activeDevices[id].getTagProperty(sigid);   // data.tags[sigid] 조회
        if (tag) return id;
    }
    return null;
}
```

`^~^` 형식은 **HMI 아이템의 `variableId` 전용**이고, 런타임 API 는 순수 태그 id 를 받습니다.

```bash
curl "localhost:27018/api/getTagValue?ids=%5B%22TT_101%22%5D"
```

```json
[{"id":"TT_101","value":68.32042694091797}]
```

---

## 6.4 양방향 제어 루프 — 최종 검증

PDF p.11 은 Grafana 의 한계를 지적합니다.

> 버튼 클릭을 통해 특정 PLC의 코일 레지스터를 조작하거나 밸브 개도율을 변경하는
> 양방향 명령 하달(Write-back) 기능이 네이티브로 제공되지 않는다.

FUXA 로 이를 실증했습니다.

```bash
st(){ curl -s http://plant-simulator:8080/state | python3 -c "..."; }

echo "[이전]"; st
curl -X POST localhost:27018/api/setTagValue -d '{"tags":[{"id":"PumpRun","value":0}]}'
sleep 7; echo "[정지 후]"; st
curl -X POST localhost:27018/api/setTagValue \
     -d '{"tags":[{"id":"PumpRun","value":1},{"id":"PumpSpeedSP","value":85}]}'
sleep 8; echo "[재기동+증속 후]"; st
```

```
[이전]
  pump=True  speedSP=59.9%  FT-101=6.12  IT-101=6.26
[정지 후]
  pump=False speedSP=59.9%  FT-101=0.03  IT-101=0.04
[재기동+증속 후]
  pump=True  speedSP=85.0%  FT-101=8.79  IT-101=7.88
```

**FUXA 버튼 → Modbus 쓰기 → 물리 모델 반응 → 센서값 변화 → EdgeX → EMQX →
Kafka → Flink → InfluxDB → Grafana** 전 구간 왕복이 성립합니다.

---

## 6.5 화면 자동 생성

P&ID 화면을 손으로 그리면 `plant.yaml` 과 어긋납니다.
`build_project.py` 가 태그 정의에서 화면을 생성합니다.

```bash
cd fuxa && python3 build_project.py
# project.json 생성: 디바이스 2개 / Modbus 태그 20개 / 바인딩 아이템 30개 / SVG 18,044자
```

```
아이템 구성: {'svg-ext-value': 17, 'svg-ext-motor': 2, 'svg-ext-valve': 1,
             'svg-ext-html_button': 7, 'svg-ext-html_input': 3}
주소 확인 (0-based Modbus → FUXA 1-based):
  TT_101       area=400000 addr=  5 type=Float32
  PT_101       area=400000 addr=  9 type=Float32
  PumpRun      area=     0 addr=  1 type=Bool     (실제 저장은 "000000")
  Interlock    area=     0 addr= 21 type=Bool
  PumpSpeedSP  area=400000 addr=101 type=Int16
```

---

## 6.6 Tier 4 완료 확인

```
Tier 4 · 저장 · 감시 · 관제
  ✓ InfluxDB 히스토리안 적재  — 최근 5분 태그 12종
  ✓ quality 태그 보존  — 실측/추정 구분이 히스토리안까지 전달됨
  ✓ Prometheus 에 센서 데이터 없음 (역할 분리) — 메트릭 993종 중 공정태그 0개
  ✓ Prometheus 인프라 스크랩  — 7/7 타깃 정상
결과: 4/4 통과

Tier 4 · 웹 SCADA — 양방향 제어 (Grafana 로는 불가능한 영역)
  ✓ FUXA P&ID 자동 프로비저닝  — 디바이스 2개, 뷰 1개, 바인딩 아이템 30개
  ✓ FUXA Modbus 읽기 (P&ID 실시간 표출) — TT_101=72.86 vs 시뮬레이터 72.86
  ✓ FUXA 양방향 제어 (SCADA 제어 루프) — 정지 FT-101=0.03 → 85% 재기동 8.29 m3/h
결과: 3/3 통과
```

---

## 6.7 실습 과제 (교재용)

1. Prometheus 에 센서 태그를 일부러 넣어 보고(Telegraf 에 prometheus_client 출력 추가),
   태그 카디널리티가 늘 때 메모리 사용량이 어떻게 변하는지 관찰하시오.
2. FUXA 의 `Interlock` 태그를 `svg-ext-value` 대신 `svg-ext-gauge_semaphore` 로
   바꿔 시각적 경보를 만들어 보시오.
3. `build_project.py` 를 수정해 반응기 레벨을 애니메이션 막대로 표현하시오.
4. Grafana 대시보드에 "실측 vs 보간" 비율 패널을 추가하고, `dropout` 주입 시
   비율이 어떻게 변하는지 확인하시오.
