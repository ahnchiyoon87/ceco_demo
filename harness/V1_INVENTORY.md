# V1 인벤토리 (v1-original)

- 조사 시각: 2026-09-28, 실행 중인 원본 스택(`D:\work\study\lecture-iiot-scada`)에서 `docker ps`·`docker inspect`·`docker images --digests`로 수집
- 기준 커밋: `v1-original` = `def56b1` (원본 작업 트리 그대로. `*.zip`, `_references/` 제외)
- compose 프로젝트 2개
  - `iiot`: `docker-compose.yml` + `docker-compose.edgex.yml` (`make up`)
  - `ar100-ai`: `ai-layer/compose.yml` + `ai-layer/compose.scada.yml`
- 실행 컨테이너 29개

## iiot (L1~L6)

| 서비스 | 이미지:태그 | digest(앞 12자) | 호스트 포트 | 역할 |
|---|---|---|---|---|
| plant-simulator | iiot/plant-simulator:1.0 (로컬 빌드 `./simulator`) | 2dbd0e673a22 | 27002→502, 27080→8080 | L1 가상설비, Modbus TCP·HTTP /state |
| edgex-device-modbus | edgexfoundry/device-modbus:4.0.0 | 849248916ae0 | 27901 | L2 Modbus 폴링 |
| edgex-core-data | edgexfoundry/core-data:4.0.0 | ad04ea0d5cbe | — | L2 |
| edgex-core-metadata | edgexfoundry/core-metadata:4.0.0 | bbae5d0751ac | — | L2 |
| edgex-core-command | edgexfoundry/core-command:4.0.0 | ed288f5b0507 | 27882 | L2 명령 API |
| edgex-core-keeper | edgexfoundry/core-keeper:4.0.0 | 7bfd36a390ff | — | L2 설정·레지스트리 |
| edgex-app-mqtt-export | edgexfoundry/app-service-configurable:4.0.0 | da81581ecb9b | 27704 | L2 MQTT export |
| edgex-ui | edgexfoundry/edgex-ui:4.0.0 | ae64cbaf4ff6 | 27040 | L2 UI |
| edgex-postgres | postgres:16.3-alpine3.20 | 36ed71227ae3 | — | EdgeX 내부 DB |
| edgex-mqtt-broker | eclipse-mosquitto:2.0.21 | 94f5a3d7deaf | — | EdgeX 내부 메시지 버스 |
| emqx | emqx/emqx:5.8.6 | a1e3d10fa1dc | 27083→1883, 27183→18083 | L2 브로커 (Apache 2.0 라인, BSL 이전) |
| telegraf-bridge | telegraf:1.33-alpine | 3ea0664bed1c | — | Telegraf#1 수집 MQTT→Kafka |
| telegraf-sink | telegraf:1.33-alpine | 3ea0664bed1c | — | Telegraf#2 저장 Kafka→InfluxDB |
| alert-republisher | telegraf:1.33-alpine | 3ea0664bed1c | — | Telegraf#3 알람 중계 Kafka→MQTT |
| kafka | apache/kafka:3.9.0 | fbc7d7c428e3 | 27092→19092 | L3 백본 |
| kafka-exporter | danielqsj/kafka-exporter:**latest** | c4baf2251980 | — | 운영 지표 |
| flink-jobmanager | iiot/flink-onnx:1.0 (로컬 빌드) | digest 없음 | 27081 | L4 |
| flink-taskmanager | iiot/flink-onnx:1.0 (로컬 빌드) | digest 없음 | — | L4 |
| influxdb | influxdb:2.7 | b8d940ca9376 | 27086 | L5 시계열 |
| fuxa | frangoteam/fuxa:**latest** (내부 버전 1.3.4-2898, 이미지 생성 2026-09-09) | aa5002fd927b | 27018→1881 | L6 SCADA/HMI |
| grafana | grafana/grafana:11.4.0 | d8ea37798ccc | 27030 | L6 관측 |
| prometheus | prom/prometheus:v3.1.0 | 6559acbd5d77 | 27090 | L6 관측 |
| alertmanager | prom/alertmanager:v0.28.0 | d5155cfac40a | 27093 | L6 운영 경보 |
| cadvisor | gcr.io/cadvisor/cadvisor:v0.49.1 | 3cde6faf0791 | — | 컨테이너 지표 |

## ar100-ai (L7~L9)

| 서비스 | 이미지:태그 | digest(앞 12자) | 호스트 포트 | 역할 |
|---|---|---|---|---|
| ai-knowledge | ar100-ai-knowledge:**latest** (로컬 빌드) | 245b38caf52c | 28000 | 지식·사건·승인·조치 API |
| ai-alarm-worker | ar100-ai-alarm-worker:**latest** (로컬 빌드) | 7fca19a6c585 | — | 알람 접수 워커 |
| ai-web | ar100-ai-web:**latest** (로컬 빌드) | aa8b6d8bfccb | 28180 | Vue 통합 화면 |
| ai-work-db | postgres:17 | f4c66b820c6f | 27532 | 업무 DB |
| ai-graph | neo4j:5.26-community | 3388e05ee53c | 27474, 27687 | L7 그래프 |

## 외부 의존

| 대상 | 값 | 비고 |
|---|---|---|
| LLM 게이트웨이 | LiteLLM 프록시, Cloud Run `knu-litellm` (`ai-layer/.env.local`의 `LITELLM_BASE_URL`), 모델 별칭 `coding` | 레포 안에 litellm 패키지 설치 없음(OpenAI 호환 URL로만 호출). 프록시 버전 **미확인**: 2026-09-28 `/health/readiness` 호출 30초 무응답 |

## 위생 조치 대상 (§6.2)

| 항목 | 현재 | 조치 |
|---|---|---|
| FUXA | `latest` = 1.3.4 | CISA 권고(1.3.2+)는 이미 충족. 태그를 버전으로 고정. Node-RED 통합 사용 여부 확인 |
| kafka-exporter | `latest` | 버전 태그로 고정 |
| ar100-ai-* 3종 | 로컬 빌드 `latest` | 실험 브랜치에서는 버전 태그로 빌드 |
| LiteLLM | 외부 프록시, 버전 미확인 | 프록시 버전 확인 필요(QUESTIONS) |
| InfluxDB | 2.7 고정 | 조치 없음(9/15 `latest`→3 Core 전환 영향 없음) |
| EMQX | 5.8.6 | 조치 없음(BSL 이전 라인) |
