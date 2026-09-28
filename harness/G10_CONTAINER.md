# G10 컨테이너 실행 가능성 (2026-09-28)

규칙: 컨테이너로 가상화할 수 없는 스택은 폐기한다(사용 불가). 구현 전에 판정한다.

| 판정 | 조건 |
|---|---|
| 통과(공식 이미지) | 공식 Linux 이미지가 있고 x86-64(amd64)를 지원 → 버전·digest 고정 |
| 통과(직접 빌드) | 오픈소스 베이스 이미지에 설치해 Dockerfile로 재현 가능 → Dockerfile 커밋 |
| 폐기 | Windows 전용, GUI 설치, 호스트 직접 설치 필수, privileged·host 네트워크 필수, 이미지에 EULA → "문헌 탈락: 컨테이너 불가" |

## 실행 환경 (Day 0)

| 항목 | 값 | 근거 |
|---|---|---|
| 호스트 | Windows 11 Home 10.0.26200, x86-64, CPU 12, RAM 15.7 GB | `Get-CimInstance`, `docker info` |
| 컨테이너 런타임 | **Docker Desktop 4.87.0** (Engine 29.7.2), WSL2 커널 6.18.33.2, Docker 할당 메모리 7.6 GiB | `docker version`, `docker info` |
| Docker Desktop 비용 | 직원 250명 초과 또는 연매출 1천만 달러 초과 기업의 업무 사용은 유료 구독 `[재확인]` → 회사 규모 판단 필요(QUESTIONS Q6). 해당 시 WSL2 내 Docker Engine(Apache-2.0) 또는 Podman으로 전환, compose 파일은 그대로 사용 |
| 아키텍처 영향 | x86-64 호스트 → amd64 이미지 네이티브 실행. 에뮬레이션 왜곡 없음 |

## 후보 판정 (레지스트리 manifest 조회, 이미지 미다운로드)

| 레이어 | 후보 | 이미지 | 조회 | 아키텍처 | G10 |
|---|---|---|---|---|---|
| L4 | Flink 2.2.1 | `flink:2.2.1-java17` | OK | amd64,arm64,unknown, | 통과(공식 이미지) |
| L4 | Flink 2.2.1 scala | `flink:2.2.1-scala_2.12-java17` | OK | amd64,arm64,unknown, | 통과(공식 이미지) |
| L4 | Timeplus Proton | `ghcr.io/timeplus-io/proton:latest` | OK | amd64,arm64, | 통과(공식 이미지) |
| ML·L4·L1 | python 베이스 (onnxruntime·River·Quix Streams·pymodbus·asyncua 설치) | `python:3.12.8-slim` | OK | 386,amd64,arm,arm64,ppc64le,s390x,unknown, | 통과(직접 빌드) |
| Broker | Mosquitto 2.1.2 | `eclipse-mosquitto:2.1.2-alpine` | OK | amd64 (Hub 태그 2026-09-18, 2.1 라인은 alpine 변형만 배포) | 통과(공식 이미지) |
| Broker | NanoMQ | `emqx/nanomq:latest` | OK | amd64,arm,arm64,unknown, | 통과(공식 이미지) |
| Broker | HiveMQ CE 2026.5 | `hivemq/hivemq-ce:2026.5` | OK | amd64,arm64, | 통과(공식 이미지) |
| Gateway | EdgeX device-modbus 4.0.0 | `edgexfoundry/device-modbus:4.0.0` | OK | amd64,arm64, | 통과(공식 이미지) |
| Gateway | Neuron OSS | `emqx/neuron:latest` | OK | amd64,arm,arm64,unknown, | 통과(공식 이미지) |
| Gateway | Telegraf | `telegraf:1.36` | OK | amd64,arm,arm64,unknown, | 통과(공식 이미지) |
| Gateway | Node-RED | `nodered/node-red:4.1` | OK | amd64,arm,arm64,unknown, | 통과(공식 이미지) |
| Gateway | benthos-umh | `ghcr.io/united-manufacturing-hub/benthos-umh:latest` | OK | amd64,arm64, | 통과(공식 이미지) |
| Pipe | Redpanda Connect | `docker.redpanda.com/redpandadata/connect:latest` | OK | amd64,arm64,unknown, | 통과(공식 이미지) |
| Pipe | Redpanda Connect (hub) | `redpandadata/connect:latest` | OK | amd64,arm64,unknown, | 통과(공식 이미지) |
| Historian | InfluxDB 2.7 | `influxdb:2.7` | OK | amd64,arm64,unknown, | 통과(공식 이미지) |
| Historian | TimescaleDB OSS(Apache) pg17 | `timescale/timescaledb:latest-pg17-oss` | OK | 386,amd64,arm,arm64,unknown, | 통과(공식 이미지) |
| Historian | PostgreSQL 17 | `postgres:17` | OK | 386,amd64,arm,arm64,ppc64le,riscv64,s390x,unknown, | 통과(공식 이미지) |
| Historian | QuestDB | `questdb/questdb:latest` | OK | amd64,arm64,unknown, | 통과(공식 이미지) |
| Backbone | Kafka 4.2.1 | `apache/kafka:4.2.1` | OK | amd64,arm64,unknown, | 통과(공식 이미지) |
| Backbone | NATS | `nats:2.11` | OK | amd64,arm,arm64,ppc64le,s390x,unknown, | 통과(공식 이미지) |
| HMI | FUXA 1.3.4 | `frangoteam/fuxa:1.3.4` | OK | amd64,arm,arm64,unknown, | 통과(공식 이미지) |
| Obs | Grafana OSS | `grafana/grafana-oss:11.4.0` | OK | amd64,arm,arm64, | 통과(공식 이미지) |
| Obs | Prometheus | `prom/prometheus:v3.1.0` | OK | amd64,arm,arm64,ppc64le,s390x, | 통과(공식 이미지) |
| AI | Neo4j Community | `neo4j:5.26-community` | OK | amd64,arm64,unknown, | 통과(공식 이미지) |
| Tool | Toxiproxy | `ghcr.io/shopify/toxiproxy:2.12.0` | OK | amd64,arm,arm64, | 통과(공식 이미지) |
| Tool | Pumba | `gaiaadm/pumba:latest` | OK | amd64,arm64,unknown, | 통과(공식 이미지) |
| Tool | Syft | `anchore/syft:latest` | OK | amd64,arm64,ppc64le,riscv64,s390x, | 통과(공식 이미지) |
| Tool | Grype | `anchore/grype:latest` | OK | amd64,arm64,ppc64le,s390x, | 통과(공식 이미지) |
| Tool | Trivy 0.69.3 | `aquasec/trivy:0.69.3` | OK | amd64,arm64,ppc64le,s390x, | 통과(공식 이미지) |

- `:latest` 로 조회한 항목은 존재·아키텍처 확인용이다. 실제 사용 시 버전 태그 + digest로 고정한다(규칙 10).
- 자체 코드: 가상설비 시뮬레이터(`iiot/plant-simulator:1.0`), Vue(`ai-web`), AI 백엔드(`ai-knowledge`)는 V1에서 이미 Dockerfile로 빌드·실행 중 → 통과.

## 결론
FINAL 후보 29개 전부 G10 통과. 폐기 대상 없음. Mosquitto 2.1.x 는 `-alpine` 태그로만 배포됨에 유의.
