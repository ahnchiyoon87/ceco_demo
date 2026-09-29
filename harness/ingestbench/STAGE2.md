# 수집 층 벤치 (EXP-ING) — 준비 상태와 실행법

작성 2026-09-29. **준비만 했고 한 번도 띄우지 않았다**(무거운 측정 진행 중 — 컨테이너 기동 금지). 이 문서의 "재현 방법"은 설정 파일의 의도이고, 동작 여부는 전부 **미검증**이다. 검증된 것: `docker compose config -q` 통과, 검사기(`check_ingest.py`) 합성 입력 시험(정상·값 오류·결측·중복·모양 불일치 5종 + 하류 동등 판정의 정상·값 불일치·누락에서 기대대로 판정), 이미지 로컬 보유(아래 표).

**09-29 결정 반영:** ① 판정은 V1 설정 호환이 아니라 **결과 동등**(같은 12태그·값·시각이 `sensor.telemetry.raw` 에 도달) — 모양이 다른 후보는 후보별 하류 파서(설정만)를 둔다(§3·§3-1). ② UI 설정 제품은 **설정을 파일로 두고 스크립트가 재적용**할 때만 인정(StreamPipes·OpenRemote, §3-2). ③ 기본값이 V1 보장보다 작은 후보는 맞춘 뒤 비교(HiveMQ Edge 내장 큐, §3-3).

판정 기준은 `QUESTIONS.md` §1, 후보 목록은 `harness/situations/CANDIDATES.md` §2(+개정 #74), 비정상 목록은 `ROBUSTNESS.md` R02·R11·R09.

## 1. 개정 #74 가 수집 층에 뜻하는 것

- **V1 EdgeX 4.0.0 은 강제 교체 대상**(4.0 LTS 2027-03 종료). 같은 라인 4.0.2·"EdgeX 경량화"도 같은 LTS 라 **① 관문 제외 → 프로파일 없음**. 다음 정식판(Queensland)은 2027 봄 예정이라 "같은 제품 최신"이 없다.
- 따라서 이 층은 **반드시 바뀐다**. ②의 "기준보다 나빠지면 탈락"은 적용하지 않고(강제 교체 규칙), ① 통과 후보 중 ②에서 **가장 덜 나빠지는 것**을 고르고 나빠진 양을 약점 열에 적는다. 그래서 EdgeX 4.0.0 기준선(`edgex` 프로파일)은 **나빠진 양을 재기 위해서만** 측정한다.

## 2. 벤치 구조

- 가상설비: 회전 스택과 같은 V2 설비 `rot-plant-simulator:v2-ts`(배속 600 기본값, 09-29 #101 교체; 레지스터 지도는 V1 과 같음 — `simulator/plant.yaml`: 계측 12태그 float32 ABCD, HR 0~23, 1초 스캔, Modbus TCP 502, HTTP `/state`).
- 벤치 브로커: `eclipse-mosquitto:2.1.2-alpine`(브로커 층 측정 완료본, 고정 상수). HiveMQ Edge 만 자체 내장 브로커를 직접 구독(수집+브로커 통합안 P-EB).
- V1 발행 모양(정답): `edgex/telemetry`, QoS1, EdgeX Event v3 — `{apiVersion:"v3", id, deviceName, profileName, sourceName:"AllSensors", origin(ns), readings:[{origin, deviceName, resourceName, profileName, valueType:"Float32", units, value:"3.1290388e+00"(문자열)}] × 12}`(근거: `docs/journal/logs/02-edgex-bootstrap.txt`, `telegraf/bridge-edgex.conf`).
- `downstream`: 하류 파서(설정만). EdgeX 모양 후보는 **V1 Telegraf#1 원문**(`downstream/v1-edgex.conf`, telegraf 1.33 — 입력·가공 그대로, 출력만 파일), 모양이 다른 후보는 **후보별 적응 설정**(`downstream/<후보>.conf`, telegraf 1.40.1). 출력은 V1 raw 레코드 `{ts ns, site, device, tag, value, quality}` 와 같은 변환식. 검사기가 후보 reading 과 1:1 대조해 `downstream.equivalent` 를 낸다.
- 네트워크 둘: `field`(시뮬레이터·수집기) / `uplink`(수집기·브로커·검사기). R02 는 송신 컨테이너만 uplink 에서 뗀다(설비 폴링 유지).
- 가드: 모든 run 스크립트는 `rot-iiot`/`rot-ai` 컨테이너가 떠 있으면 거부(`FORCE=1` 로 무시). `harness/benchguard.sh`.

## 3. 후보 → 프로파일

| 후보(우선순위) | 프로파일 | 이미지(정확한 태그) | 재현하는 V1 기능과 방법 | 알려진 차이·위험 |
|---|---|---|---|---|
| V1 기준 EdgeX 4.0.0 | `edgex` | `edgexfoundry/{core-keeper,core-common-config-bootstrapper,core-metadata,core-data,core-command,device-modbus,app-service-configurable,edgex-ui}:4.0.0`, `postgres:16.3-alpine3.20`, `eclipse-mosquitto:2.0.21` | V1 `docker-compose.edgex.yml` 을 그대로 옮기고 export 브로커만 벤치 Mosquitto 로. 장치·프로파일은 `edgex/devices`·`edgex/profiles` 그대로(AutoEvent 1000 ms, AllSensors) | 강제 교체 대상. 10컨테이너(UI 포함, V1 과 같게) |
| Telegraf 1.40.1 `inputs.modbus` (P1) | `telegraf` | `telegraf:1.40.1-alpine` | register 모드 FLOAT32-IEEE/ABCD 12개 1초 → `outputs.mqtt` 비배치 + `json_transformation`(JSONata)으로 EdgeX Event v3 모양, QoS1 | value 가 `%e` 문자열이 아님(V1 소비자는 float 변환이라 무관 — downstream 동등으로 확인). 단절 보관은 메모리 버퍼(재시작 시 소실) — R02. JSONata `$keys/$lookup` 동작 [미검증] |
| benthos-umh v0.16.0 (P1) | `benthos-umh` | `ghcr.io/united-manufacturing-hub/benthos-umh:0.16.0` | `modbus` 입력(12 FLOAT32, 1 s) → reading 모양 → `archive json_array` 로 한 읽기 묶음을 Event v3 로 → `mqtt` 출력 QoS1 | modbus 입력은 배치 입력(`ReadBatch`, 소스 v0.16.0 `modbus_plugin/modbus.go` 확인) → 읽기 한 번 = Event 1건이 되어야 함(실동작 [미검증], `readings_per_message`로 확인). 메모리 버퍼 |
| HiveMQ Edge 2026.14 (P1, P-EB) | `hivemq-edge` | `hivemq/hivemq-edge:2026.14` | Modbus 어댑터 태그 12개(FLOAT_32, HOLDING_REGISTERS) 1000 ms, `publishChangedDataOnly=false` → `edgex/telemetry/<tag>` QoS1, 내장 브로커 | **EdgeX 모양 불가**: 태그마다 `{"value","timestamp","tagName"}` 1건 → 하류 `downstream/hivemq-edge.conf`. 모양 변환(Data Hub)·오프라인 버퍼는 상용 키 → 미사용(09-29: 무료판으로 동등 결과가 안 나오면 ② 실행 탈락). R02 보관 없음 예상. 내장 큐 1000 → 10만으로 맞춤(§3-3). `maxPollingErrorsBeforeRemoval=-1` 해석 [미검증] |
| Neuron 2.13.0 (P2) | `neuron` | `emqx/neuron:2.13.0` (Docker Hub 최신 이미지; git 2.15.0 과 불일치 — 2.14·2.15 이미지 없음 확인 2026-09-29) | REST(`neuron/setup.py`): `Modbus TCP` 드라이버, 그룹 1000 ms, FLOAT(9) `1!400001`… ABCD → `MQTT` 앱 QoS1, `offline-cache` 켬(OSS) | 모양 `{"node","group","timestamp"(ms),"values":{},"errors":{}}` → 하류 `downstream/neuron.conf`(values 펼치기). API 형식은 v2.13-daily 기능시험 코드 기준 |
| Node-RED 5.0.7 + contrib-modbus 5.60.2 (P2) | `nodered` | `nodered/node-red:5.0.7` 위에 빌드(`ingestbench-nodered:5.0.7-modbus5.60.2`) | `modbus-read` FC3 HR0 24워드 1 s → function 노드(float32 ABCD 해독·Event v3 조립) → `mqtt out` QoS1 | function 노드 JS 는 **어댑터 코드**(V1 도 직접 짠 범위). 첫 실행 때 npm 설치 빌드 필요(네트워크) |
| ThingsBoard IoT Gateway 3.8.5 (P3) | `tbgw` | `thingsboard/tb-gateway:3.8.5` | Modbus 커넥터(32float, BIG/BIG, 1000 ms, ON_RECEIVED) → "ThingsBoard" 자리에 벤치 Mosquitto(`v1/gateway/telemetry`) | 일반 브로커로 보낼 수 있는지가 ② 첫 항목(§12-3). 모양 `{"reactor-line-01":[{"ts","values"}]}` → 하류 `downstream/tbgw.conf`. 설정은 3.8.5 예제 형식 |
| Apache StreamPipes 0.98.0 (P3) | `streampipes` | `apachestreampipes/{backend,ui,extensions-all-iiot}:0.98.0`, `couchdb:3.3.1`, `influxdb:2.6`, `nats:2.15.0-alpine` | 공식 `installer/compose/docker-compose.yml`(0.98.0) 구성, 태그만 고정. 어댑터·MQTT 싱크는 `streampipes/setup.py apply` 가 `streampipes/exported.json` 을 REST 로 재적용(§3-2) → 하류 `downstream/streampipes.conf` | 공식 minimal 은 `backend-nats:0.98.0` 태그가 없어 기본 구성 사용. **동봉 InfluxDB 2.6 은 지원 종료 라인**(① 관문 관점 약점). 첫 설정은 UI 1회 + export 필요(아래) |
| OpenRemote 1.31.1 (P3, AGPL ⚠) | `openremote` | `openremote/manager:1.31.1`, `openremote/keycloak:26.7.3.0`, `openremote/postgresql:17.9.0.1-slim`, `openremote/proxy:3.2.19.0` | 공식 compose 구성(`latest` 대신 고정). `openremote/setup.py apply` 가 REST 로 Modbus TCP 에이전트·자산 12속성·MQTT 서비스 사용자 생성(§3-2). Manager 내장 MQTT 구독(토픽에 client_id 필수) → 하류 `downstream/openremote.conf` | 플랫폼 4컨테이너. 자산·에이전트 모델 필드 [미검증] |

### 3-1. 하류 파서(결과 동등, 설정만)

| 후보 | 하류 설정 | 이미지 | 입력 해석(나머지 필터·출력 변환식은 V1 원문) |
|---|---|---|---|
| edgex·telegraf·benthos-umh·nodered | `downstream/v1-edgex.conf` | `telegraf:1.33-alpine` | V1 Telegraf#1 원문(EdgeX Event `readings` 펼치기) |
| hivemq-edge | `downstream/hivemq-edge.conf` | `telegraf:1.40.1-alpine` | 토픽 끝 = 태그, `{value, timestamp(ms)}` 1건 = 레코드 1건 |
| neuron | `downstream/neuron.conf` | 〃 | `values{태그:값}` → `processors.unpivot` 로 태그별 레코드, `timestamp`(ms). `errors` 태그는 레코드 없음 |
| tbgw | `downstream/tbgw.conf` | 〃 | `reactor-line-01[]` 원소마다 `values` 펼치기, `ts`(ms) |
| streampipes | `downstream/streampipes.conf` | 〃 | 평면 이벤트 `{timestamp(ms), <태그>: 값}` 펼치기(어댑터 필드 이름 = 태그 이름) |
| openremote | `downstream/openremote.conf` | 〃 | 토픽 `master/<cid>/attribute/<태그>/<자산>`, `{value, timestamp(ms)}` |

적응 설정은 모두 **[미검증]**(기동 금지 중 작성). 하류 `equivalent=false` 가 설정 탓인지 후보 탓인지는 `missing_examples`·로그로 가른다. 후보 발행에 원천 시각(origin/timestamp)이 없으면 비교 자체가 안 되며(=동등 불가) 그대로 기록한다.

### 3-2. UI 설정 제품의 재현 절차(09-29 결정)

| 제품 | 스크립트 | 정본 파일 | 첫 1회 | ④ 운영 부담(기록) |
|---|---|---|---|---|
| StreamPipes | `streampipes/setup.py apply|export` (REST `/streampipes-backend/api/v2`) | `streampipes/exported.json`(어댑터·파이프라인) | UI(http://localhost:39088)에서 만들고 `export` | 어댑터 내부 모델 JSON 수작업 불가 → UI 1회 + 내보내기, 버전 올릴 때 재내보내기 |
| OpenRemote | `openremote/setup.py apply|export` (Keycloak 토큰 + `/api/master/asset`·`/user`) | `openremote/exported.json` 있으면 우선, 없으면 스크립트 안 선언 | 선언이 맞으면 불필요 | Keycloak·서비스 사용자 비밀값 관리, 4컨테이너 |

`export` 는 `experiments/EXP-ING/raw/<제품>_exported.json` 에 쓴다(client 의 `/repo` 는 읽기 전용). 사람이 확인한 뒤 `harness/ingestbench/<제품>/exported.json` 으로 복사하면 그것이 apply 의 정본이 된다.

### 3-3. V1 보장 맞춤 설정

| 후보 | 기본값 | 맞춘 값 | 근거 |
|---|---|---|---|
| HiveMQ Edge 내장 브로커 | 오프라인 큐 1000(HiveMQ 계열 기본) | `<mqtt><queued-messages><max-queue-size>100000` | V1 EMQX `max_mqueue_len 10만`. 키 이름 [미검증] |
| Neuron | 오프라인 캐시 꺼짐 | `offline-cache: true`(메모리 128 MB·디스크 1 GB) | V1 EdgeX Store-and-Forward 역할 |
| 벤치 Mosquitto | — | `max_queued_messages 100000`, 영속 | 브로커 층과 같은 조건 |

제외(① 관문, 프로파일 없음): EdgeX 4.0.2·경량화(#74), Apache PLC4X(이미지 없음), UMH Core(BSL 동봉), Eclipse Kura Modbus(EULA), Neuron 상용 드라이버.

## 4. 명령

레포 루트(`/d/work/study/scada-rotation`, Git Bash)에서. 무거운 측정이 끝난 뒤, 한 번에 하나.

```bash
# ②+③ (3회 중앙값: RUN=r1 r2 r3). 기본 120초.
harness/ingestbench/stage2.sh edgex            # 기준선 먼저
harness/ingestbench/stage2.sh telegraf
RUN=r2 harness/ingestbench/stage2.sh telegraf
# ④ R02 수집기↔브로커 단절 60초(총 240초)
harness/ingestbench/stage4_r02_netcut.sh telegraf 60 240
# ④ R11 설비 통신 끊김: pause(무응답) | fieldcut(연결 끊김) | dropout(TT-101 센티널)
harness/ingestbench/stage4_r11_modbus.sh telegraf pause 30 180
# ④ R09 장시간: stage2 를 길게
RUN=long harness/ingestbench/stage2.sh telegraf 3600
```

결과: `experiments/EXP-ING/stage2_<profile>[_<RUN>].json`, `stage4_r02_<profile>.json`, `stage4_r11_<mode>_<profile>.json`, 원자료 `experiments/EXP-ING/raw/`(stats·images·downstream·logs·fault·cred).

결과 JSON 읽는 법: `completeness`(기대 12×초 대비 고유 샘플·결측·중복·근접 중복), `values.match_rate`(설비 `/state` 대비 일치율, 허용오차 5e-4), `latency_ms`(수신−origin, 값 신선도), `throughput`, `shape`(V1 Event v3 충족·메시지당 reading 수), `downstream`(결과 동등: 후보 reading 대비 누락·여분·중복·값·스키마 불일치, `equivalent`), `resources`(후보 컨테이너만 합한 CPU·메모리, 이미지 크기), 4단계 `faults`(단절 구간 유실·재전송·동결값·센티널·복구 시간·순서 역전).

## 5. 판정에 쓸 때 주의

- 설비 값 비교는 `/state` 를 0.1초마다 읽어 최근 6개 스냅숏과 맞춘다. EdgeX 처럼 레지스터를 하나씩 읽으면 스캔 경계에 걸린 태그는 한 seq 늦은 값이 정상이다(`seq_lag_hist`).
- `complete_second_ratio` 는 폴링 위상 흔들림에 민감한 참고값이다. 유실 판정은 `missing_gap_based` 와 `unique_samples` 로 한다.
- R02 의 `lost_estimate` 는 origin 이 단절 구간에 있는 고유 샘플 수로 센다. 수집기가 단절 동안 폴링을 멈추는 설계(버퍼 없음)면 "재전송 0 + 유실"로 나온다 — 그것이 결과다.
- hivemq-edge 의 R02 는 Edge 자체가 uplink 에서 떨어지므로 "브로커 쪽 큐"를 재는 셈이다(수집기와 브로커가 한 컨테이너).
- 호스트 시각(`date +%s.%N`)과 컨테이너 시각은 Docker Desktop VM 시계 동기에 의존한다. 사건 시각은 수 ms 오차가 있을 수 있다.

## 6. 미검증·결정 필요

- 모든 후보 설정 파일의 동작(기동 금지로 lint·기동 미실행). 각 후보의 ② 첫 실행이 곧 설정 검증이다.
- 이미지는 모두 로컬 보유(빌드 이미지 `ingestbench-client`·`ingestbench-nodered` 는 첫 실행 때 빌드). Docker Hub 익명 한도(429)로 일부 이미지는 `mirror.gcr.io`(구글 Docker Hub 미러)에서 받아 원래 이름으로 태그했다. 내용은 같은 이미지지만 RepoDigest 는 미러 주소로 남는다.
- StreamPipes 는 어댑터 JSON 을 사람이 쓰기 어려워 **첫 1회 UI 설정 + `setup.py export`** 가 필요하다(내보낸 파일이 없으면 stage2 가 SETUP 에서 멈추고 ② 실행 불가로 기록). OpenRemote 는 REST 선언으로 시작하되 모델 필드가 틀리면 같은 절차(UI 수정 → export).
