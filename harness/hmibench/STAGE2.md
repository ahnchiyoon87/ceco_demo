# HMI 벤치 ② 준비 (EXP-HMI) — 2026-09-29 준비, **미실행**

판정 규칙 `QUESTIONS.md` §1, 후보 `CANDIDATES.md` §9·패턴 P-UNS/P-HMI/P-CMD, 기능 F03·F13·E12(`STRUCTURE.md`).

## 벤치 구성
- 공통: **가상설비**(V1 `simulator/` 소스로 빌드 `bench-plant-simulator:1.0`, `DIRECT_MQTT_ENABLE=true` = V1 lite 경로 `iiot/AR-100/reactor-line-01/<tag>` 발행, Modbus 502·`/state` 8080) + **Mosquitto 2.1.2**(인증·ACL: 익명은 `iiot/#` 쓰기만, HMI 계정 읽기 전용, `bench` 계정만 `scada/#` 발행). 계정 해시는 `hmi_prepare.py` 가 `mosquitto_passwd` 와 같은 `$7$` 형식으로 생성.
- 알람: 하니스가 V1 형식 그대로 `scada/alerts/IT-102`(Telegraf JSON)·`scada/hmi/latest-alert`(문자열) 발행.

## 공통
- **자원 한도 없음(09-29 결정 I5):** 컨테이너 메모리·CPU 제한을 두지 않는다 — 실제 사용량 자체가 ③ 효율 측정값. 공정성은 같은 호스트에서 벤치 하나씩(각 stage2.sh 가 같은 벤치 동시 기동 거부, rot 스택과는 가드로 분리). JVM 힙 등 제품 설정은 상류 예시·기본값 그대로. Scada-LTS 는 상류 `CATALINA_OPTS=-Xmx2G -Xms2G` 그대로.

## 판정 D1~D6 (결과 보기 전 고정, `hmi_stage2.py`)
D1 12태그 숫자 표시 + `/state` 값 일치 · D2 신선도(값 변화→HMI 반영 p50/p95, 5Hz) · D3 알람 표시 지연 · D4 인증 운전원의 교반기 쓰기 → `/state` 반영, **인증 없는 읽기·쓰기 거부** · D5 누가 명령했는지 기록 · D6 읽기 경로(설비 직접 폴링 vs MQTT 구독).

## 후보 → 프로파일

| 후보 | 프로파일 | 이미지 | 12태그 읽기(D6) | 알람 | 명령·인증 | 갭·주의 |
|---|---|---|---|---|---|---|
| FUXA 기준(V1) | `fuxa-v1` | `frangoteam/fuxa@sha256:aa5002fd…`(V1 실행 이미지 1.3.4-2898) | **Modbus 직접 폴링**(V1 `fuxa/project.json` 그대로) = V1 이중 폴링 | MQTT `scada/hmi/latest-alert` | `setTagValue` **인증 없음**(V1 설정: `secureEnabled` 주석) | 기준선 — 보안 약점 측정용 |
| **FUXA 1.3.4 태그 고정 + 보안(P1)** | `fuxa134` | `frangoteam/fuxa:1.3.4` + `fuxa/settings.js`(`secureEnabled:true`, `nodeRedEnabled:false`) | Modbus 직접 폴링 | 같음(계정 hmi) | 로그인 토큰(`x-access-token`) | `1.3.4` 태그는 2026-08-13 빌드, V1 digest(2026-09-09 `latest`)와 빌드가 다름 → 둘 다 측정. 기본 계정 admin/123456 이 살아 있는지 `default_password_works` 로 기록 |
| FUXA MQTT 구독(P-UNS) | `fuxa134-uns` | 같음 | **MQTT 구독 12태그**(`type:json`, `memaddress:value` [미확인: FUXA 가 JSON 필드 추출을 하는지 — D1 숫자 여부로 판정]) + 명령 9태그만 Modbus | 같음 | 같음 | 명령 read-back 때문에 Modbus 폴링이 명령 태그만큼 남음(부분 이중 폴링). 운전 화면이 브로커에 종속(R01 에서 확인) |
| Node-RED 5 + Dashboard 2 | `nodered` | `bench-nodered:5.0.7-db2-1.32.0` = `nodered/node-red:5.0.7` + `@flowfuse/node-red-dashboard@1.32.0` + `node-red-contrib-modbus@5.60.2`(빌드) | **MQTT 구독**(`iiot/+/+/+`) | ui-notification + `/bench/alarm` | `/bench/command`(Basic 인증, 허용 목록 교반기·냉각기 코일만) → modbus-flex-write, 감사 목록에 사용자 기록 | 편집기 끔(`disableEditor`) — 흐름은 `nodered/flows.json` 파일로만. 인증은 `settings.js` 미들웨어(연결 코드). Dashboard 2 위젯 노드 속성은 문서 기준 [미검증] |
| ThingsBoard CE 4.3 | `thingsboard` | `thingsboard/tb-node:4.3.1.6` + `postgres:17.11` + `thingsboard/tb-gateway:3.8.5` | **MQTT 구독**(IoT Gateway MQTT 커넥터 → TB) | 게이트웨이가 `scada/alerts/+` 를 `last_alert` 시계열로(알람 객체는 규칙 체인 설정 필요 — §7 alarmbench 는 REST 로 시험) | RPC → 게이트웨이 Modbus 커넥터(RPC 전용, 폴링 1시간) | CE 에는 외부 MQTT 통합(Integration)이 없어 **게이트웨이 필수**(컨테이너 4). 게이트웨이 설정 스키마(3.8) [미검증]. 데모 계정 기본 비밀번호 |
| Scada-LTS 2.8.0 (GPL-2.0 ⚠, LICENSE 원문 확인) | `scadalts` | `scadalts/scadalts:v2.8.0` + `mysql:8.4.6` | **Modbus 직접 폴링**(Modbus IP 데이터 소스, MQTT 데이터 소스 없음 [미확인]) | [미검증] | [미검증] | 기동·기본 로그인만 자동화. 상류 compose 는 `latest`·`mysql/mysql-server:8.0.32`(8.0 은 2026-04 EOL) → 8.4 LTS 로 바꿈(호환 [미확인]). 데이터 소스·화면 구성 API 확인 후 D1~D5 자동화 |
| Apache StreamPipes 0.98.0 | `streampipes` | `apachestreampipes/backend:0.98.0`·`ui:0.98.0`·`extensions-iiot-minimal:0.98.0` + `couchdb:3.3.1` + `nats:2.15.0-alpine` + `influxdb:2.9.1` | MQTT 어댑터 [미검증] | [미검증] | [미검증] | **상류 0.98.0 minimal compose 의 `backend-nats:0.98.0` 이미지가 없음**(Docker Hub 404) → `backend:0.98.0`+nats 설정으로 대체 [미검증]. 상류는 InfluxDB 2.6(지원 종료)·nats 무태그 → 2.9.1·2.15.0 으로 바꿈. 관리자 탈취 CVE 수정판 [미확인](CANDIDATES §12-3). 컨테이너 6 |
| OpenRemote · ioBroker · Grafana+Business Forms | — | — | — | — | — | P3 — 이번 준비 범위 밖(프로파일 추가만 하면 같은 D1~D6 적용) |
| Vue `ai-web` MQTT/WS 직접 구독 | — | — | — | — | — | V1 자체 화면 — 구조 비교(P-HMI)에서, 이 벤치의 Mosquitto WS(8083)·ACL 재사용 가능 |

**직접 설비 폴링이 필요한 후보(V1 이중 폴링 문제):** `fuxa-v1`·`fuxa134`(전부), `fuxa134-uns`(명령 태그 9개만), `scadalts`(MQTT 소스 없음 [미확인]). MQTT 구독만으로 읽기: `nodered`, `thingsboard`(게이트웨이 경유), `streampipes`(어댑터 [미검증]).

## 실행
```bash
PYTHONUTF8=1 python harness/hmibench/hmi_prepare.py     # generated/ (stage2.sh 가 없으면 자동 실행)
for p in fuxa-v1 fuxa134 fuxa134-uns nodered thingsboard scadalts streampipes; do harness/hmibench/stage2.sh $p; done
```
산출: `experiments/EXP-HMI/stage2_<profile>.json`, `raw/<profile>_services.log`.
④ R01(브로커 정지 중 운전 화면)은 같은 벤치에서 `docker stop hmibench-mosquitto-1` 30초 동안 D1 을 반복하는 것으로(준비만), R11 은 가상설비 `POST /fault {"scenario":"dropout"}`.

## 준비 검증(2026-09-29)
- 이미지: 외부 이미지 전부 받음(`experiments/BENCH-PREP/pull_20260929_0258.log`, 실패 0).
- `config -q` 통과, latest 0(상류 `latest` 를 쓰는 Scada-LTS·StreamPipes 는 버전 태그로 고정).
- `hmi_prepare.py` 실행: passwd 4계정, poll 프로젝트(Modbus 21태그), uns 프로젝트(MQTT 12 + Modbus 명령 9).
- 미실행: FUXA API(signin·plugins·project·getTagValue·setTagValue — 저장소 `docs/GOTCHAS.md` §19 기준), Node-RED 흐름 적재, TB 게이트웨이 모두 미검증.
