# 2. Tier 1 · 현장 에지

> 교재 활용: **2차시 — 공정 시뮬레이터와 Modbus** / **3차시 — EdgeX Foundry**

## 2.1 왜 물리 모델이 필요한가

"동작하는 SCADA 예제" 가 되려면 **제어하면 물리량이 실제로 변해야** 합니다.
값을 랜덤으로 흔드는 시뮬레이터로는 제어 루프를 보여줄 수 없습니다.

그래서 질량수지·에너지수지·헤드스페이스 압력을 1차 오일러 적분으로 풀었습니다.

```python
# 질량수지
self.rx_vol += (q_in - q_out) * dt_s / 3600.0

# 에너지수지
q_loss = heat_loss_kw_per_k * (self.temp_c - ambient)
q_feed = (q_in / 3600.0) * rho * cp * (ambient - self.temp_c)
self.temp_c += (q_heat - q_loss + q_feed) / (mass * cp) * dt_s

# 헤드스페이스 압력 (레벨·온도와 물리적으로 결합)
head_frac = max(1.0 - level_frac, 0.05)
p_abs = charge * (temp_c + 273.15) / (ambient + 273.15) * (ref_head / head_frac)
p_vap = 0.0061094 * math.exp(17.625 * temp_c / (temp_c + 243.04))   # Magnus
```

이 결합 덕분에 **레벨이 오르면 압력이 오르고**, 압력이 오르면 펌프 유량이 줄고,
유량이 줄면 펌프 전류가 떨어집니다. 오토인코더가 학습할 상관 구조가 여기서 나옵니다.

## 2.2 운전점 튜닝 — 수치적으로

처음 파라미터로는 운전점이 목표에서 벗어났습니다.

```
LT-102 = 51.78 %    (목표 55)
TT-101 = 49.06 °C   (목표 72, SP 72)   ← 히터 용량 부족
PT-101 =  0.12 barg (목표 3.0)         ← 초기 충전압 미반영
```

손으로 맞추는 대신 **파라미터 스윕**을 돌렸습니다.

```python
for hp, cv, mf, refill in itertools.product([380,520,700],[10.0,12.0,14.0],
                                             [14.0,18.0,22.0],[9.0,12.0]):
    ...
    err = ((r['LT-102']-55)/10)**2 + ((r['TT-101']-72)/5)**2 + ((r['PT-101']-3.0)/0.8)**2
```

결과: `heater_kw=700, cv=10.0, max_flow=14.0, refill=9.0`

최종 운전점 (50분 수렴):

```
  LT-101      82.695   [10.0, 95.0]  OK
  LT-102      54.307   [15.0, 90.0]  OK
  TT-101      70.910   [40.0, 95.0]  OK
  TT-102      91.966   [None, 125.0] OK
  PT-101       3.223   [None, 6.0]   OK
  FT-101       6.166   IT-101  6.264   IT-102  6.397
  VT-101       2.058   pH-101  7.423   CT-101  3.382
```

> **교육 포인트**: TT-101 이 SP(72) 에 정확히 닿지 않고 70.9 에 머무릅니다.
> P 제어만 쓰면 정상상태 오차(droop)가 남기 때문이며, 이는 **버그가 아니라
> 물리적으로 올바른 거동**입니다. 이런 것을 "고치려" 들면 모델이 비현실적이 됩니다.

## 2.3 함정: 벽시계 vs 시뮬레이션 시간

고장의 램프와 지연(`lag_s`)을 `time.monotonic()` 으로 계산했더니,
배속 테스트에서 전혀 동작하지 않았습니다. 루프가 마이크로초 단위로 도니
경과 시간이 항상 ~0 이었던 것입니다.

```python
# 잘못됨
started_at: float = field(default_factory=time.monotonic)
@property
def elapsed(self): return time.monotonic() - self.started_at

# 올바름 — 적분된 시뮬레이션 시각 기준
self.sim_time += dt_s
for f in self.faults.values():
    f.elapsed = self.sim_time - f.started_at
```

**증상**: 고장을 주입해도 아무 변화가 없거나, `lag_s` 가 무시됨.
**진단**: 고장 주입 후 태그 변화 상위 3개를 출력해 보니 대상 태그가 없었음.

## 2.4 함정: 인터록이 물리 진값을 보면 안 된다

처음에는 인터록이 `self._pressure(...)` 계산값을 봤습니다.
그랬더니 `spike`(계기 고장) 를 주입해도 트립이 걸리지 않았습니다.

실제 PLC 는 물리 진값을 알 수 없습니다. **트랜스미터 지시값**만 봅니다.

```python
# 실제 PLC 와 동일하게 직전 스캔의 '트랜스미터 지시값' 을 참조한다.
# 따라서 계기 고장(spike)으로도 트립이 발생한다.
press_now = self.measured_pressure or self._pressure(rx_level_frac, self.temp_c)
```

이렇게 바꾸니 `spike` 주입 시 인터록이 정상 발동했습니다.

> **교육 포인트**: 안전 로직의 입력이 무엇인지가 설계의 핵심입니다.
> 계기 고장 시 오동작(스퓨리어스 트립)은 실제 플랜트의 주요 이슈이며,
> 시뮬레이터가 이를 재현할 수 있어야 의미 있는 훈련이 됩니다.

## 2.5 트랜스미터 하한(LRV)

펌프를 정지했더니 유량이 **-0.03 m³/h** 로 나왔습니다. 계측 노이즈가 0에도
붙어서 생긴 물리적으로 불가능한 값입니다. 실제 트랜스미터처럼 하한 클램프를 넣었습니다.

```yaml
- { name: FT-101, hr: 10, unit: "m3/h", ..., clamp_lo: 0.0 }
```

## 2.6 Modbus 검증

```
=== 1. Modbus float32 읽기 vs REST 교차검증 ===
   LT-101 modbus=   70.652  rest=   70.652
   TT-101 modbus=   52.133  rest=   52.133
   ... → 전 태그 일치

=== 2. Southbound 제어: 펌프 정지 (coil 0 = 0) ===
   FT-101 공급유량 6.43 → -0.03 m3/h
   IT-101 펌프전류 6.25 →  0.06 A
   → 제어 반영 확인

=== 5. spike 고장 → 고압 인터록 트립 ===
   PT-101=6.51 barg (USL 6.0)  인터록코일20=True  FT-101=0.00
   → 과압 인터록으로 펌프 트립 확인
```

## 2.7 EdgeX Foundry 4.0 — 가장 까다로웠던 부분

### 2.7.1 3.x 와 완전히 다른 구조

```bash
curl -O https://raw.githubusercontent.com/edgexfoundry/edgex-compose/v4.0.0/docker-compose-no-secty.yml
grep -E "^  [a-z-]+:" docker-compose-no-secty.yml
```

```
core-command:
core-common-config-bootstrapper:
core-data:
core-keeper:          ← Consul 이 아님
core-metadata:
database:             ← postgres:16.3-alpine3.20 (Redis 아님)
mqtt-broker:          ← eclipse-mosquitto (내부 버스)
```

| | 3.x | **4.0** |
|---|---|---|
| 레지스트리 | Consul | core-keeper |
| DB | Redis | PostgreSQL |
| 내부 버스 | Redis Streams | MQTT |

### 2.7.2 프로파일 생성 — plant.yaml 을 단일 출처로

태그 정의를 두 곳에 두면 반드시 어긋납니다. `plant.yaml` 에서 EdgeX 프로파일을
생성하는 스크립트를 만들었습니다.

```bash
cd edgex && python3 gen_profile.py
# 생성 완료: deviceResources=21  autoEvent=1000ms
```

### 2.7.3 오류 1 — deviceCommand 권한 불일치

```
Failed to YAML decode Device Profile from /res/profiles/ar100.profile.yaml:
device command's ReadWrite permission 'RW' doesn't align the device resource
```

`Control` 커맨드(RW)에 읽기전용 `Interlock` 을 넣은 것이 원인.
읽기전용 리소스를 `Status`(R) 커맨드로 분리해 해결.

```
  AllSensors rw=R  members=12 perms=['R']  OK
  Control    rw=RW members= 7 perms=['RW'] OK
  Status     rw=R  members= 2 perms=['R']  OK
```

### 2.7.4 오류 2 — compose 가 영원히 대기

`core-common-config-bootstrapper` 를 `service_completed_successfully` 로 걸었더니
compose 가 멈췄습니다. 로그를 보면 분명히 끝났는데도 컨테이너가 살아 있습니다.

```
msg="Core Common Config exiting"
```
```
$ docker inspect edgex-common-config --format '{{.State.Status}} exit={{.State.ExitCode}}'
running exit=0
```

공식 compose 는 `service_started` 를 씁니다 — EdgeX 서비스들이 keeper 에
설정이 올라올 때까지 **재시도하도록 설계**되어 있기 때문입니다.

### 2.7.5 오류 3 — 환경변수가 무시됨

`-o` 없이는 최초 1회만 적용됩니다. EdgeX 4.0 이 설정을 keeper 에 영속화하기 때문.

```yaml
command: ["--registry", "-cp=keeper.http://edgex-core-keeper:59890", "-o"]
```

적용 전후 로그 비교:

```
(전) msg="Private configuration loaded from the Configuration Provider. No overrides applied"
(후) msg="Private configuration loaded from file with 11 overrides applied"
```

### 2.7.6 오류 4 — Store-and-Forward 설정이 안 먹음

`Enabled` 는 적용됐는데 재시도 주기는 그대로였습니다.

```
Starting StoreAndForward Retry Loop with 5m0s RetryInterval and 10 max retries.
                                         ^^^^                  ^^
                                         내가 설정한 5s/1000 이 아님
```

keeper 의 실제 키를 직접 조회해서 원인을 찾았습니다.

```bash
docker run --rm --network iiot curlimages/curl -s \
  "http://edgex-core-keeper:59890/api/v3/kvs/key/edgex?keyOnly=true" | \
  python3 -c "...grep StoreAndForward..."
```

```
edgex/v4/app-mqtt-export/Writable/StoreAndForward/Enabled                          ← 서비스
edgex/v4/core-common-config-bootstrapper/app-services/Writable/StoreAndForward/MaxRetryCount  ← 공통
edgex/v4/core-common-config-bootstrapper/app-services/Writable/StoreAndForward/RetryInterval  ← 공통
```

재시도 설정은 **공통 설정**에 있었습니다. 부트스트래퍼에 주입:

```yaml
APP_SERVICES_WRITABLE_STOREANDFORWARD_RETRYINTERVAL: "5s"
APP_SERVICES_WRITABLE_STOREANDFORWARD_MAXRETRYCOUNT: "1000"
```

```
Starting StoreAndForward Retry Loop with 5s RetryInterval and 1000 max retries.
```

> **교육 포인트**: 설정이 안 먹을 때 "문서를 다시 읽기" 보다
> **설정 저장소를 직접 조회**하는 것이 빠릅니다.
> EdgeX 는 keeper, Kubernetes 는 `kubectl get -o yaml`, Spring 은 `/actuator/env`.

## 2.8 Tier 1 완료 확인

```
Tier 1 · 현장 에지 — 프로토콜 정규화와 양방향 제어
  ✓ 시뮬레이터 응답  — 태그 12점, seq=1015
  ✓ EdgeX 프로토콜 정규화 (Modbus → JSON)  — 10초간 이벤트 +10건
  ✓ Southbound 제어 (Modbus 코일 쓰기 → 물리 반응)
      FT-101 8.29 → 0.07 m3/h, IT-101 7.87 → 0.06 A
결과: 3/3 통과
```

EdgeX 가 산출한 실제 Event JSON:

```json
{
  "apiVersion": "v3",
  "deviceName": "reactor-line-01",
  "profileName": "AR100-Reactor-Line",
  "sourceName": "AllSensors",
  "origin": 1789545856852575500,
  "readings": [
    { "resourceName": "CT-101", "valueType": "Float32", "units": "mS/cm", "value": "3.1290388e+00" },
    { "resourceName": "pH-101", "valueType": "Float32", "units": "pH",    "value": "7.6120467e+00" },
    ...
  ]
}
```

Modbus 바이너리가 태그명·단위·타입을 갖춘 시맨틱 JSON 으로 정규화되었습니다.
이것이 PDF 결론 1 이 말하는 "IoT 미들웨어의 본질적 역할" 입니다.
