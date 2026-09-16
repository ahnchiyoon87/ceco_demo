# 7. 장애 진단 사례집

> 교재 활용: **실습 문제 은행** — 각 사례는 "증상 → 가설 → 확인 명령 → 원인 → 해결"
> 구조라 그대로 실습 문제로 쓸 수 있습니다.

전체 구축 과정에서 마주친 **22건**의 문제를 증상 기준으로 정리했습니다.
요약 표는 [GOTCHAS.md](../GOTCHAS.md) 에 있고, 여기에는 **진단 과정**을 담았습니다.

---

## 사례 1 — compose 가 영원히 멈춘다

**증상**
```
$ docker compose up -d
...
NAME                  STATUS
edgex-common-config   Up About a minute      ← 끝나야 하는데 안 끝남
edgex-core-command    Created                ← 전부 대기
edgex-core-data       Created
```

**가설 1**: 부트스트래퍼가 실패했다 → 로그 확인

```bash
rtk proxy docker logs edgex-common-config | tail -3
```
```
msg="Common configuration has been pushed to into Configuration Provider with overrides applied"
msg="Core Common Config exiting"
```

작업은 **성공**했고 "exiting" 까지 찍혔습니다. 가설 기각.

**가설 2**: 프로세스가 실제로는 안 끝났다 → 컨테이너 상태 확인

```bash
docker inspect edgex-common-config --format '{{.State.Status}} exit={{.State.ExitCode}} policy={{.HostConfig.RestartPolicy.Name}}'
```
```
running exit=0 policy=no
```

`restart: "no"` 인데 `running` — 로그는 exiting 인데 프로세스가 살아 있습니다.

**원인**: `service_completed_successfully` 는 컨테이너 종료를 기다립니다.
공식 EdgeX compose 는 `service_started` 를 씁니다 (서비스들이 재시도 설계).

**해결**
```yaml
depends_on:
  edgex-common-config: { condition: service_started }
```

**실습 문제**: 왜 EdgeX 는 `service_completed_successfully` 를 쓰지 않도록
설계되었는가? 분산 시스템의 기동 순서 문제와 연결지어 설명하시오.

---

## 사례 2 — 환경변수를 바꿔도 반영되지 않는다

**증상**: `.env` 에서 설정을 바꾸고 재기동했는데 이전 값이 그대로.

**확인 명령** — 로그에서 오버라이드 적용 여부를 봅니다.
```bash
rtk proxy docker logs edgex-app-mqtt-export | grep -i "configuration loaded"
```
```
msg="Private configuration loaded from the Configuration Provider. No overrides applied"
                                       ^^^^^^^^^^^^^^^^^^^^^^^  ^^^^^^^^^^^^^^^^^^^
```

"Configuration Provider 에서 로드, 오버라이드 없음" — 파일이 아니라 keeper 에서
읽었다는 뜻입니다.

**원인**: EdgeX 4.0 은 설정을 keeper 에 영속화하고, 이후 기동에서는 그것을 씁니다.

**해결**: `-o`(overwrite) 플래그
```yaml
command: ["--registry", "-cp=keeper.http://edgex-core-keeper:59890", "-o"]
```
```
msg="Private configuration loaded from file with 11 overrides applied"
```

**일반화**: 설정 저장소를 쓰는 시스템(Consul, etcd, keeper, Spring Cloud Config)은
대부분 같은 문제를 갖습니다. "파일 vs 저장소" 중 무엇이 이기는지 확인하세요.

---

## 사례 3 — 일부 설정만 반영된다

**증상**: `WRITABLE_STOREANDFORWARD_ENABLED` 는 먹는데 `RETRYINTERVAL` 은 안 먹음.

```
Starting StoreAndForward Retry Loop with 5m0s RetryInterval and 10 max retries.
                                         ^^^^ 설정한 5s 가 아님
```

**진단 — 설정 저장소를 직접 조회**
```bash
docker run --rm --network iiot curlimages/curl:latest -s \
  "http://edgex-core-keeper:59890/api/v3/kvs/key/edgex?keyOnly=true" | python3 -c "
import sys,json
d=json.load(sys.stdin)
ks=[x['key'] if isinstance(x,dict) else x for x in (d.get('response') or [])]
for k in ks:
    if 'StoreAndForward' in k: print(' ', k)
"
```
```
  edgex/v4/core-common-config-bootstrapper/app-services/Writable/StoreAndForward/MaxRetryCount
  edgex/v4/core-common-config-bootstrapper/app-services/Writable/StoreAndForward/RetryInterval
  edgex/v4/app-mqtt-export/Writable/StoreAndForward/Enabled
```

`Enabled` 만 서비스 private config 에 있고 나머지는 **공통 설정**에 있습니다.
EdgeX 는 존재하지 않는 키의 오버라이드를 조용히 건너뜁니다.

**해결**: 부트스트래퍼에 `APP_SERVICES_` 접두사로 주입.

**실습 문제**: 오버라이드가 무시될 때 "조용히 건너뛰기" 와 "오류로 실패" 중
어느 쪽이 나은 설계인가? 각각의 장단을 논하시오.

---

## 사례 4 — 성공했다고 하는데 아무것도 안 만들어진다

**증상**
```
▶ Tier-1 규칙 탐지 SQL 제출...
✓ Tier-1 SQL 제출 완료
```
```bash
$ curl -s localhost:27081/jobs/overview
총 0개 잡
```

**진단 — 같은 명령을 직접 실행**
```bash
docker exec flink-jobmanager bash -c \
  'cat /opt/flink/sql/0*.sql > /tmp/all.sql && /opt/flink/bin/sql-client.sh -f /tmp/all.sql' \
  2>&1 | grep -E "ERROR|Job ID"
```
```
Job ID: 09a5bd889b7da6d63bc6120b02260cfd
Job ID: 33493ace9770fdbce05a50c2181adba5
[31;1m[ERROR] Could not execute SQL statement. Reason:
org.apache.flink.table.api.ValidationException: Columns ambiguously defined: {device}
```

에러가 **있었습니다.** 그런데 스크립트는 못 잡았습니다.

**원인**: 출력의 `[ERROR]` 앞에 ANSI 색상코드(`\033[31;1m`)가 붙어
`grep "^\[ERROR\]"` 의 행 시작 매칭이 실패.

**해결 2단계**
```bash
# 1) 색상 제거 후 검사
sql-client.sh -f x.sql 2>&1 | sed -E 's/\x1b\[[0-9;]*m//g' > log
grep -qE "^\[ERROR\]" log && exit 1

# 2) 텍스트가 아니라 실제 상태로 최종 확인
running=$(curl -s "$JM/jobs/overview" | grep -o '"state":"RUNNING"' | wc -l)
[ "$running" -lt 4 ] && exit 1
```

**교훈**: 자동화 스크립트의 성공 판정은 **부작용(side effect)** 을 확인해야 합니다.
로그 텍스트는 포맷이 바뀌면 깨집니다.

---

## 사례 5 — NoSuchMethodError 가 relocate 후에도 반복된다

**증상 1차**
```
NoSuchMethodError: 'com.fasterxml.jackson.core.JsonParser$NumberTypeFP
                    com.fasterxml.jackson.core.JsonParser.getNumberTypeFP()'
```

**조치**: Flink 런타임과의 충돌로 보고 셰이드 시 relocate.

**증상 2차** — 이름만 바뀌고 동일
```
NoSuchMethodError: 'org.uengine.iiot.shaded.jackson.core.JsonParser$NumberTypeFP ...'
```

이름이 재배치됐다는 것은 **내 JAR 안에서** 충돌한다는 뜻입니다.

**진단**
```bash
docker run --rm -v "$PWD":/w -w /w maven:3.9-eclipse-temurin-17 \
  mvn -B dependency:list | grep -E "jackson-(core|databind|annotations):jar"
```
```
jackson-annotations:jar:2.17.2:compile
jackson-core:jar:2.15.2:compile        ← 혼자 다름
jackson-databind:jar:2.17.2:compile
```

**원인**: 전이 의존으로 `jackson-core` 만 2.15.2 가 선택됨 (Maven nearest-wins).

**해결**: BOM 임포트로 전 아티팩트 버전 고정.

**진단 순서 정리**
1. `NoSuchMethodError` = 컴파일 시점과 런타임 클래스 불일치
2. 외부 충돌인가 내부 충돌인가? → relocate 해보면 구분됨
3. 내부라면 실제 해결된 버전을 확인 (`dependency:list`)
4. BOM 또는 명시적 `<dependency>` 로 고정

---

## 사례 6 — "The record must not be null"

**증상**
```
Caused by: TimerException{java.lang.IllegalArgumentException: The record must not be null.}
  at org.uengine.iiot.OnnxScorer.onTimer(OnnxScorer.java:153)
```

**진단**: 스택트레이스가 정확한 행을 가리킵니다.
```bash
sed -n '145,165p' flink/onnx-job/src/main/java/org/uengine/iiot/OnnxScorer.java
```
```java
for (int i = 0; i < Math.min(n, steps - 1); i++) {
    window.put(i, window.get(i + 1));    // ← 153행
}
```

윈도우가 채 차기 전(`n < steps`)에 좌측 시프트를 하면
아직 기록되지 않은 슬롯 `i+1` 을 읽어 null 이 됩니다.
RocksDB 상태 백엔드는 null 값을 거부합니다.

**해결**: 차기 전에는 덧붙이기만, 가득 찬 뒤에만 시프트.

---

## 사례 7 — 디바이스가 조용히 기동되지 않는다

**증상**: FUXA 로그에 `'AR100' start` 는 있는데 값이 안 읽힘. 오류도 없음.

```
2026-09-16T09:03:09.948Z [INF]  'AR100' start
2026-09-16T09:03:09.973Z [INF]  'ALERTS' connected!     ← MQTT 는 연결됨
                                                        ← Modbus 는 연결 메시지 없음
```

**가설 1**: 디바이스 타입 문자열이 틀렸다
```bash
docker exec fuxa grep -n "ModbusTCP:" /usr/src/app/FUXA/server/runtime/devices/device.js
# 584:    ModbusTCP: 'ModbusTCP',
```
맞습니다. 기각.

**가설 2**: 드라이버 모듈이 없다
```bash
curl -s localhost:27018/api/plugins | python3 -c "
import sys,json
for p in json.load(sys.stdin):
    print(f\"  {p.get('name'):18s} current={p.get('current')}\")"
```
```
  modbus-serial      current=            ← 비어 있음
  node-red           current=4.1.11
```

**원인**: FUXA 는 산업 프로토콜 드라이버를 **런타임 플러그인**으로 설치합니다.
도커 이미지에 포함되어 있지 않습니다.

**해결**: 프로비저너가 기동 시 자동 설치.

**교훈**: "오류 없이 동작하지 않음" 은 가장 진단하기 어렵습니다.
**성공 경로의 로그(다른 디바이스의 `connected!`)와 비교**하는 것이 단서가 됩니다.

---

## 사례 8 — Cannot read properties of undefined (reading 'Items')

**증상**
```
[ERR] 'AR100' load error! TypeError: Cannot read properties of undefined (reading 'Items')
```

불친절한 오류라 소스를 읽어야 했습니다.

**진단**
```bash
docker exec fuxa sed -n '200,265p' /usr/src/app/FUXA/server/runtime/devices/modbus/index.js
```
```javascript
var memaddr = formatAddress(data.tags[id].memaddress, token);   // "0-0"
if (!memory[memaddr]) memory[memaddr] = new MemoryItems();
...
lastMemAdr = getMemoryAddress(lastStart, true, token);          // "0-000000"
mits.Items = getMemoryItems(memory[lastMemAdr].Items, ...);     // undefined.Items
```

두 함수가 **다른 키**를 만듭니다.
```javascript
const getMemoryAddress = function (address, tokenized, token) {
    if (address < ModbusMemoryAddress.DigitalInputs) {
        if (tokenized) return formatAddress('000000', token);   // 리터럴 '000000'
```

**원인**: 코일 영역의 `memaddress` 는 `"0"` 이 아니라 `"000000"` 이어야 합니다.

**교훈**: 오류 메시지가 불친절할 때는 **스택이 아니라 데이터 흐름**을 추적합니다.
"undefined 의 속성" 오류는 "그 키가 왜 없는가" 를 물어야 합니다.

---

## 사례 9 — API 가 "not found" 를 반환한다

**증상**
```bash
curl -X POST localhost:27018/api/setTagValue -d '{"tags":[{"id":"AR100^~^PumpRun","value":0}]}'
# {"error":"not_found","message":"setTagValue Failed: AR100^~^PumpRun not found; "}
```

HMI 아이템에서는 이 형식이 동작하는데 API 에서는 안 됩니다.

**진단**
```bash
docker exec fuxa sed -n '397,405p' /usr/src/app/FUXA/server/runtime/devices/index.js
```
```javascript
function getDeviceIdFromTag(sigid) {
    for (var id in activeDevices) {
        var tag = activeDevices[id].getTagProperty(sigid);   // data.tags[sigid]
        if (tag) return id;
    }
    return null;
}
```

`data.tags` 의 키로 직접 조회하므로 **bare tag id** 여야 합니다.

**해결**
```bash
curl "localhost:27018/api/getTagValue?ids=%5B%22TT_101%22%5D"
# [{"id":"TT_101","value":68.32042694091797}]
```

**교훈**: 같은 시스템 안에서도 **계층마다 식별자 규약이 다를 수 있습니다.**
프론트엔드용 복합키와 런타임용 단순키가 공존하는 경우가 흔합니다.

---

## 사례 10 — 처리량이 4.7배로 측정된다

**증상**: 기대 12건/초인데 콘솔 컨슈머로 재보니 56건/초.

**가설**: 중복 발행? EdgeX autoEvent 중복 등록?

**확인 — 상류부터 순서대로**
```bash
# EdgeX 이벤트 증가율
a=$(curl -s .../event/count | jq .count); sleep 10; b=$(...)
echo $((b-a))      # → 10  (정확히 1/초)

# EMQX 수신율
mosquitto_sub -h emqx -t 'edgex/telemetry' -W 10 | grep -c apiVersion
                   # → 10

# 등록된 autoEvent
curl -s .../device/all | python3 -c "...print(dev['autoEvents'])"
                   # → 1개
```

상류는 전부 정상입니다.

**재측정 — 오프셋 차분**
```bash
off(){ docker exec kafka /opt/kafka/bin/kafka-get-offsets.sh \
        --bootstrap-server localhost:9092 --topic "$1" | awk -F: '{s+=$3} END{print s+0}'; }
a=$(off sensor.telemetry.raw); sleep 20; b=$(off sensor.telemetry.raw)
echo "$((b-a))건/20초"     # → 252건/20초 = 12.6/초
```

**원인**: 콘솔 컨슈머는 JVM 기동에 10여 초가 걸리고, 그 사이 쌓인 백로그를
한꺼번에 드레인합니다. 서비스 재기동 직후라 백로그가 컸습니다.

**교훈**: 처리량 측정에는 **컨슈머가 아니라 오프셋 차분**을 쓰세요.
컨슈머는 자기 자신이 관측 대상에 영향을 줍니다.

---

## 사례 11 — kafka-console-consumer 가 끝나지 않는다

**증상**: `--timeout-ms 12000` 을 줬는데 87초가 지나도 안 끝남.

**원인**: `--timeout-ms` 는 "그 시간 동안 **메시지가 없으면** 종료" 입니다.
계속 생산되는 토픽에서는 영원히 끝나지 않습니다.

**해결**: 벽시계로 직접 창을 끊습니다.
```python
proc = subprocess.Popen([...], stdout=PIPE, text=True)
try:
    out, _ = proc.communicate(timeout=window_s)
except subprocess.TimeoutExpired:
    proc.kill()
    out, _ = proc.communicate()
```

---

## 사례 12 — 검증이 실패하는데 기능은 정상이다

**증상**
```
✗ 결측치 보간 수행  — clean 보간 0건, 방식 -
```

**직접 확인**
```bash
# 컨슈머를 먼저 띄우고
docker exec kafka ...--topic sensor.telemetry.clean > clean.jsonl &
sleep 14                      # JVM 기동 대기
# 그 다음 고장 주입
curl -XPOST .../fault -d '{"scenario":"dropout","duration_s":15}'
sleep 40
```
```
clean 토픽 총 660 건
  GOOD: 646건
  INTERPOLATED_LINEAR: 14건
```

**기능은 정상이었습니다.** 검증 코드가 컨슈머를 **순차 실행**해서
보간 레코드가 나오는 짧은 시점(공백이 닫히는 순간)을 놓친 것입니다.

**해결**: 두 토픽을 **동시에 구독한 뒤** 주입.

**교훈**: 테스트 실패 시 **테스트가 틀렸을 가능성**을 먼저 배제하세요.
특히 타이밍이 관여하는 스트림 테스트에서 흔합니다.

---

## 사례 13 — 모델 판별력이 무의미하다

**증상**
```
  정상   탐지율 49.0%   (오탐률)
  drift  탐지율 43.9%   ← 정상보다 낮음
```

**단서**: 정상 오탐률 49% 는 "모델이 나쁘다" 로 설명하기엔 너무 극단적입니다.
동전 던지기와 같습니다 → 입력 데이터를 의심.

**원인**
```python
rows = np.array([[plant.step(1.0)[t] for t in tags] for _ in range(seconds)])
#                 ^^^^^^^^^^^^^^^^^^ 태그마다 step() 호출 → 12배속 + 행 뒤섞임
```

**수정 후**
```
  정상   탐지율  0.5%
  drift  탐지율 100.0%
```

**교훈**: 모델 성능이 "무작위 수준" 이면 모델이 아니라 **데이터 파이프라인**을
먼저 보세요.

---

## 진단 도구 모음

| 목적 | 명령 |
|---|---|
| 컨테이너 실제 상태 | `docker inspect <c> --format '{{.State.Status}} exit={{.State.ExitCode}}'` |
| 원본 로그 (요약 없이) | `rtk proxy docker logs <c>` |
| 컨테이너 내부 소스 읽기 | `docker exec <c> sed -n 'N,Mp' <file>` |
| 서비스 간 통신 확인 | `docker run --rm --network iiot curlimages/curl:latest -s <url>` |
| Kafka 처리량 | `kafka-get-offsets.sh` + 차분 |
| Flink 잡 예외 | `curl -s $JM/jobs/<id>/exceptions` |
| Maven 실제 버전 | `mvn dependency:list \| grep <artifact>` |
| JAR 내용 | `unzip -l <jar>` |
| 이미지 아키텍처 | `docker manifest inspect <img> \| grep architecture` |
