# V2 설계 — 레이어·길 재설계, 기능 대응표, 스택 조합 선택 (회전 1)

작성 2026-09-29 세션 4. 판정 기준 정본 `QUESTIONS.md` §1(결정 순서 → 기능 보존 → 구조 판정 → ①~④).
근거: 리서치 원문(`docs/research/ARCHITECTURE_SIMPLIFICATION.md`·`AGENT_BRIEF_FINAL.md`·`deep-2026-09-29/01~06`), 층별 실측(`experiments/EXP-*/layer_*.json`, decision-log #101~#119), V1 기준값(`experiments/EXP-001/summary_V1_r2_.json`).
**실측 칸이 "측정 대기"인 항목은 V2 전체 측정(EXP-002)에서 채운다. 채우기 전에는 확정이 아니다.**

## 1. 출발점과 원칙 (한 문단)
V1 의 흐름(설비 → 수집 → 전달 → 탐지 → 저장 → 화면 → AI)과 기능은 현업에서 컨펌받은 것이라 **그대로 둔다**.
바꾸는 것은 "어떻게"뿐이다 — 같은 데이터를 두 번 옮기는 길, 되돌아가는 길, 같은 일을 하는 부품, 지원이 끝났거나 12개월 안에 끝나는 판.
층을 합칠지는 "합치면 무엇을 잃는가"로 따지고, 잃는 것이 없고 실측으로 확인될 때만 합친다. 남기는 층에는 이유를 붙인다.

## 1-1. V1 해부 — 갈래별 필요성 판정 (코드·설정에서 "누가 받아 쓰는가"를 확인, 세션 4)

| # | 갈래(보내는 곳 → 받는 곳) | 실제로 받아 쓰는 곳(근거) | 판정 |
|---|---|---|---|
| 1 | 설비 → EdgeX device-modbus → EdgeX 내부 브로커 → app-mqtt-export → EMQX → Telegraf#1 → Kafka raw | 끝단 Kafka raw 만 씀(Flink `flink/sql/01_sources.sql:23`, 저장). 중간 5단계는 값을 옮기기만 함 | **줄임**: 수집기 → Kafka 1단계 |
| 2 | (lite) 설비 MQTT 직발행 `iiot/+/+/+` → EMQX → Telegraf-lite → Kafka raw | 본 경로와 같은 raw 토픽을 채우는 두 번째 수집 길(`docker-compose.yml` profiles lite, `telegraf/bridge-lite.conf`) | **없앰**(중복 길) |
| 3 | Kafka raw → Flink 잡 4개(임계치·Z-Score·CEP SQL 각 1 + ONNX 1)가 각자 읽음 | 잡마다 다른 판정(`flink/sql/02~04`, `AnomalyJob.java`) | **남김**: 규칙 잡이 서로 따로 재시작·실패(격리), V1 SQL 무수정 70/70(#107). 잡을 합쳐도 줄어드는 컨테이너 없음 |
| 4 | ONNX 잡 → Kafka clean(보간값) → 저장 `process` | Grafana `01-process.json`, verify.py | **남김** |
| 5 | Kafka raw → 저장 `process_raw` | AI 근거 조회 `evidence.py:40`·`pipeline.py`, Grafana 01 패널 8(원본 vs 보간 비교) | **남김** |
| 6 | ONNX 잡 → Kafka score → 저장 `anomaly` | Grafana `02-anomaly.json`, verify.py | **남김** |
| 7 | Kafka alerts → 저장 `alerts` | Grafana `03-alerts.json` | **남김** |
| 8 | Kafka alerts → Telegraf#3 → EMQX `scada/hmi/latest-alert` → FUXA | FUXA 알람 태그(`fuxa/build_project.py:108~117`) | **줄임**: 중계기 1 → 표시 전용 브로커 → FUXA |
| 9 | Kafka alerts → Telegraf#3 → EMQX `scada/alerts/<tag>` | **받는 곳 없음** — FUXA 는 2026-09-23 latest-alert 로 이전(`scripts/apply-fuxa-alert-topic.py`), Vue 는 MQTT 미사용(`ai-web/src` 검색 0) | **없앰**(옛 흔적 갈래) |
| 10 | Kafka alerts → 알람 워커 → PostgreSQL 사건 | AI 층(`consumer.py:55,60`) | **남김**(AI 층 입구) |
| 11 | EdgeX → `edgex/telemetry` MQTT | 수업 안내(`ai-web/public/system-guide.html`), `scripts/reference-style-architecture.py` — 사람이 쓰는 기능 | **남김**: 수집기가 같은 토픽·모양으로 사본 발행 |
| 12 | FUXA → 설비 Modbus 직접 폴링·쓰기(C1) | 운전 화면·조작 | **남김**: 운전 화면은 수집·브로커 장애와 무관해야 함(현업 원칙) |
| 13 | EdgeX core-command → 설비 쓰기 REST | **받는 곳(호출자) 없음**(`docker-compose.edgex.yml` 외 검색 0), 인증 없음 | **없앰**(쓰기 창구 축소) |
| 14 | AI 백엔드 → 설비 /state·Modbus 쓰기(C2·C3) | AI 층 | **남김**(AI 층) |
| 15 | Prometheus ← EMQX 지표(접속 수·끊김) → Grafana 04 패널·EMQXDisconnectSpike 경보 | 운영 화면·경보 | **대체 필요**: 브로커 상태 지표(방식은 리서치 07 결과로 확정) |
| 16 | Prometheus ← kafka-exporter·Flink·InfluxDB·cAdvisor | Grafana 04·경보 5종(`prometheus/rules.yml`) | **남김** + 중계기 지표 추가(V1 E11 에서 중계기 kill·탐지 잡 정지 둘 다 미탐) |

## 2. 길(데이터 경로) — 전과 후

```
V1  설비 ─Modbus─▶ EdgeX device-modbus ─▶ EdgeX 내부 Mosquitto ─▶ app-mqtt-export ─▶ EMQX ─▶ Telegraf#1 ─▶ Kafka raw
    Kafka raw ─▶ Flink(규칙 SQL 3 + ONNX 1, HA 없음) ─▶ Kafka clean/score/alerts
    Kafka ─▶ Telegraf#2 ─▶ InfluxDB 2.7 ─▶ Grafana 11.4
    Kafka alerts ─▶ Telegraf#3 ─▶ EMQX ─▶ FUXA 최근 알람          ← 알람이 수집용 브로커로 되돌아감
    Kafka alerts ─▶ 알람 워커 ─▶ PostgreSQL 사건 ─▶ AI(담당 밖)
    FUXA ─Modbus 직접 폴링·조작─▶ 설비                            ← EdgeX 와 이중 폴링
    (lite 프로필) 설비 ─MQTT 직발행─▶ EMQX ─▶ Telegraf(lite) ─▶ Kafka   ← 본 경로를 건너뛰는 두 번째 수집 길
    Prometheus 3.1 + Alertmanager 0.28 + kafka-exporter(latest) + cAdvisor 0.49

V2  설비 ─Modbus(설비 전용망)─▶ 수집기(Telegraf 1.40) ─▶ Kafka 4.3 raw
                                     └─▶ Mosquitto edgex/telemetry (V1 과 같은 토픽·모양 — 수업 자료용 실시간 계측)
    Kafka raw ─▶ Flink 2.2(규칙 SQL 3 + ONNX 1, V1 SQL 그대로) + ZooKeeper HA ─▶ Kafka clean/score/alerts
    Kafka ─▶ 중계기(Vector 1대) ─┬▶ InfluxDB 2.9 ─▶ Grafana 13.2
                                 └▶ Mosquitto scada/hmi/latest-alert ─▶ FUXA
    Kafka alerts ─▶ 알람 워커 ─▶ PostgreSQL 사건 ─▶ AI(변경 없음)
    FUXA ─Modbus 직접 폴링·조작─▶ 설비   (운전 화면은 IT 층 장애와 무관하게 — 남긴 이유 §4-③)
    Prometheus 3.15 + Alertmanager 0.34 + kafka-exporter 1.10 + cAdvisor 0.60
```

알람 → 화면 경유 단계(`harness/situations/paths.yaml`, 같은 셈법): **V1 12 → V2 8**.
상시 컨테이너(SCADA, 일회성 제외): V1 25 → V2 측정 대기(설계상 15: 설비·수집·브로커·Kafka·ZooKeeper·Flink JM·TM·InfluxDB·중계·FUXA·Grafana·Prometheus·Alertmanager·exporter·cAdvisor). 서비스 수(일회성 포함) V1 SCADA 29 → V2 19.

## 3. 층별 판단 — 합칠 것·뺄 것·남길 것

| 층 | V1 | V2 | 판단(무엇을 잃는가 → 결론) | 근거 |
|---|---|---|---|---|
| 수집 | EdgeX 10컨테이너 + Telegraf#1 | 수집기 1 | EdgeX 4.0 LTS 2027-03 종료(12개월 안), 후속 정식판 없음 → **강제 교체**. 장치 추상화(프로파일·메타데이터·명령 API)는 12태그 설비 1대에서 수집 외 사용처 없음 → 수집기 하나로 | 05 §A, #107 |
| 수집 우회(lite) | 설비 MQTT 직발행 → Telegraf(lite) | 없음 | 본 경로가 이미 한 단계(설비→수집기→Kafka)라 가벼운 우회 길이 따로 있을 이유가 없음 → **제거**(중복) | `docker-compose.yml` profiles lite |
| 브로커 | EdgeX 내부 Mosquitto + EMQX | Mosquitto 1 | EMQX 5.8 OSS 2026-02-28 종료·이후 BSL → **강제 교체**. EdgeX 내부 버스는 EdgeX 와 함께 사라짐 → **2 → 1** | #48, 01 §2 |
| MQTT→Kafka 중계 | Telegraf#1 | 없음 | 수집기가 Kafka 에 바로 씀 → 되돌아가는 길 제거 | 구조 |
| 백본 | Kafka 3.9 | Kafka 4.3.1 | 3.9 는 2027-02-19 종료 → 같은 제품 지원판 고정. **MQTT 하나로 합치지 않는 이유**: 재처리(CAP-16)·소비자별 독립 진도가 필요하고, 합치면 Flink 를 직접 짠 탐지기로 바꿔야 함(급진안 C, 폐기 #57·#53) | 02 §0, FINAL §17 |
| 이상탐지 | Flink 1.20 세션(HA 없음) | Flink 2.2.1 + ZooKeeper HA | 다른 제품 6종은 엔진이 CEP·Z-Score 를 거부해 탈락(#109~#113). HA 는 사용자 확정 예외(#94). **ZooKeeper 를 따로 두는 이유**: Flink 공식 HA 는 ZooKeeper·Kubernetes 두 가지뿐(02 §3) | #107 |
| 저장 중계 + 알람 중계 | Telegraf#2·#3 | 중계기 1(Vector) | 두 중계를 한 프로세스로(패턴 P-E). 결과 동일·메모리 V1 3대 710 MiB → 45 MiB(#113) | #113 |
| 시계열 저장 | InfluxDB 2.7 | InfluxDB 2.9.1 | 2.7 지원 밖 → 지원판 고정. **PostgreSQL 로 합치지 않는 이유**: TimescaleDB(Apache 판)·pg_partman·QuestDB 는 질의 정답이나 24시간분 디스크 680~1,100 MB vs InfluxDB 19 MB(압축은 TSL 이라 금지) → ③ 효율 악화 | #117·#118·#119, EXP-TS |
| 업무 DB·그래프 DB | PostgreSQL 17 · Neo4j 5.26 | 그대로 | AI 층(담당 밖), Neo4j 는 사용자 고정 | QUESTIONS §1 AI 고정 |
| 알람 워커 | V1 워커 | 그대로 | 대안(Bento·Redpanda Connect) 결과 동일·효율 이득 미미 → 유지 | #119 |
| HMI | FUXA 1.3.4 | 그대로 | 보안판 이미 충족. 설비 직접 폴링은 남김(§4-③) | 03 §0 |
| 감시 | Prometheus 3.1·AM 0.28·exporter latest·cAdvisor 0.49 | 3.15·0.34.1·1.10.0·0.60.6 | 네 판 모두 지원 밖 → 지원판 고정. 줄일지는 E11(장애 탐지) 결과로 판단 — V1 은 0/2 | 05 §A, EXP-001 E11 |

## 4. 구조 재조립 대상 5개

| # | 대상 | V1 | V2 | 결론 | 실측 확인 |
|---|---|---|---|---|---|
| ① | 알람 되돌림 | Kafka → Telegraf#3 → EMQX(수집용 브로커) → FUXA, 12단계 | Kafka → 중계기 → Mosquitto(표시 전용) → FUXA, 8단계 | 단계 축소. **탐지기가 MQTT 로 바로 쏘지 않는 이유**: Flink 에 유지되는 MQTT 커넥터가 없고(직접 코드 = 금지 범위), 알람은 워커·저장도 Kafka 에서 받아야 함 | E1 p95·E2 — 측정 대기 |
| ② | 중계 5중 | EMQX·Telegraf×3·Kafka (+EdgeX 내부 버스·export) | Kafka·중계기 1·Mosquitto | 5 → 3 | E2·E3 — 측정 대기 |
| ③ | 설비 이중 폴링 | EdgeX·FUXA | 수집기·FUXA | **남김**: 운전 화면은 제어기를 직접 읽는 것이 현업 원칙(구조 분석서 §5·§11) — FUXA 를 MQTT 구독으로 바꾸면 브로커·수집기 장애 때 운전 화면이 멈춤. 일관성 비용은 E7 로 확인 | E7(V1 99.17 %)·R01 중 FUXA 영향 — 측정 대기 |
| ④ | 설비 쓰기 경로 3개 | FUXA(C1)·EdgeX core-command·AI 조치(C3, 운전원 C2 는 같은 백엔드) | FUXA·AI 백엔드 | EdgeX core-command(사용처 없음·인증 없는 쓰기 창구) 제거 → 3 → 2 | E12 접점 수 — 측정 대기 |
| ⑤ | 저장소 3개(+EdgeX DB) | InfluxDB·PostgreSQL·Neo4j·edgex-postgres | InfluxDB·PostgreSQL·Neo4j | edgex-postgres 제거(EdgeX 전용). 나머지 셋은 **남김**: 시계열은 디스크 실측(§3), 업무·그래프는 AI 층 | EXP-TS 디스크 |

## 5. 기능 대응표 (V1 부품 → 하던 기능 → V2 담당 → 확인 방법 → 결과)

| V1 부품 | 하던 기능 | V2 담당 | 확인 방법 | 결과 |
|---|---|---|---|---|
| plant-simulator | 가상설비·Modbus·/state·이상 주입·인터록 | 그대로(배속 600 설비) | 회귀 S14~S22 | 측정 대기 |
| edgex-device-modbus | 12태그 1초 폴링·정규화 | 수집기 inputs.modbus | S01 12태그 저장·raw 600건 표본(중복 0·1초 간격, 세션 4) | 표본 확인됨 · S01 측정 대기 |
| edgex-core-data·metadata·keeper·common-config | 장치 프로파일·메타데이터·설정 레지스트리(EdgeX 내부) | 수집기 설정 파일의 레지스터 지도(`v2/telegraf/ingest.conf`) | 12태그·단위 일치 | 측정 대기 |
| edgex-postgres | EdgeX 내부 저장·Store-and-Forward | 수집기 디스크 버퍼(`buffer_strategy = "disk"`) | R02 단절 10 s 유실 ≤ V1(중앙 120) | 측정 대기 |
| edgex-app-mqtt-export | `edgex/telemetry` MQTT 발행(수업 자료·도구가 구독) | 수집기 outputs.mqtt(같은 토픽·EdgeX Event v3 모양) | 토픽 구독 후 모양 대조 | 측정 대기 |
| edgex-mqtt-broker | EdgeX 내부 메시지 버스 | 없음(EdgeX 와 함께 불필요) | — | 해당 없음 |
| edgex-core-command | 장치 쓰기 REST(사용처 없음, 인증 없음) | 없음 — 제거가 보안 이득 | E12 접점, G7 | 측정 대기 |
| edgex-ui | EdgeX 장치 화면(장치 목록·현재 값 조회) | 현재 값: FUXA P&ID·Grafana 01 공정 화면. 장치 정의: 수집기 설정(`v2/telegraf/ingest.conf` 레지스터 지도) | verify.py scada·storage 단계 | 측정 대기 |
| emqx | 계측·알람 MQTT 중계, 대시보드(접속 상태), Prometheus 지표 | Mosquitto(계측 사본·최근알람). 접속 상태는 브로커 지표 → Grafana 04 운영 패널·경보(갈래 15) | S23 알람 표시, 토픽 구독, 브로커 정지 시 경보(E11) | 측정 대기 |
| telegraf-bridge(#1) | MQTT → Kafka raw | 없음(수집기가 Kafka 에 바로) | S01·completeness | 측정 대기 |
| telegraf-bridge-lite | EdgeX 우회 경량 수집 | 없음(본 경로가 같은 역할) | — | 해당 없음 |
| kafka·kafka-init | 백본·토픽 4개 | Kafka 4.3.1·같은 토픽 스크립트 | 토픽 목록, R03 | 기동 확인(4토픽 흐름) · R03 측정 대기 |
| flink-jobmanager·taskmanager·submitter·model-trainer | 규칙·Z-Score·CEP·ONNX 탐지 | Flink 2.2.1+HA(+ZooKeeper), V1 SQL·모델 그대로 | S02~S08 70건, R05 자동 복귀 | 벤치 70/70·잡 자동 복귀(#107) · 전체 스택 측정 대기 |
| telegraf-sink(#2) | Kafka 4토픽 → InfluxDB(최소 1회 전달) | 중계기(Vector, 전달 확인 켬) | S01 저장·R06 | 기동 확인(세션 4, 401 오류 수정 뒤) · R06 측정 대기 |
| alert-republisher(#3) | 알람 → MQTT latest-alert(FUXA 구독) + 태그별 토픽(구독처 없음, 갈래 9) | 중계기(Vector)가 latest-alert 를 냄 | S23·E1 | 측정 대기 |
| influxdb | 공정 이력 | InfluxDB 2.9.1 | S01·E7 | 기동 확인 · 측정 대기 |
| fuxa·fuxa-provisioner | 운전 화면·C1 조작·최근 알람 | 그대로(브로커 주소만 mqtt) | S14·S23·verify.py scada | 측정 대기 |
| grafana | 추세·이력 화면 | Grafana 13.2.2 | 대시보드 질의 | 측정 대기 |
| prometheus·alertmanager·kafka-exporter·cadvisor | 운영 지표·경보(E11) | 지원판 4개 | E11 ≥ V1(0/2) | 측정 대기 |
| **사람이 쓰는 기능** | 수업 자료의 `edgex/telemetry` 구독(`ai-web/public/system-guide.html`, `docs/소스코드로_…설명.html`, `docs/journal/07`) | 수집기 MQTT 사본 | 토픽 구독 | 측정 대기 |
| 〃 | `scripts/verify.py`(EdgeX 정규화 확인 포함) | EdgeX 단계는 수집기 확인으로 대체 필요 | verify.py 실행 | 측정 대기 |
| 〃 | 수업 3차시 EdgeX 장치 프로파일(장치를 파일로 정의해 수집) | 수집기 장치 정의(`ingest.conf` 의 레지스터 지도: 태그·주소·자료형·단위) — 같은 개념을 V2 파일로 가르침 | 파일 대조(12태그·단위) | 측정 대기 |

## 6. 스택 조합안 (남는 층에서만)

남는 층 중 제품을 고를 수 있는 곳은 **수집기**와 **중계기** 둘이다(백본·탐지·저장·브로커·HMI·감시는 §3 의 강제 교체·실측 결과로 이미 정해짐).

| 안 | 수집기 | 중계기 | 컨테이너(SCADA 상시) | 이미 있는 증거 | 판단 |
|---|---|---|---|---|---|
| A 보수안 | Telegraf 1.40 | Telegraf 1.40 ×2(저장·알람 따로, V1 설정 그대로) | 16 | V1 중계 3대 710 MiB(#111). 1.40 판 중계 재측정 없음 | 경로 격리는 좋지만 중계 2대 = 중복 |
| **B 효율안(선택)** | Telegraf 1.40 | Vector 0.58 1대 | 15 | Vector 결과 동일·45 MiB·알람 p95 793 → 37 ms(#113). Telegraf 는 V1 이 이미 쓰는 제품(수업 연속성), Modbus·Kafka·MQTT·디스크 버퍼 모두 OSS | 중복 없음, ③ 메모리 15.8배↓ |
| C 수집 교체안 | benthos-umh 0.16 | Vector 0.58 | 15 | 수집 1,356/1,356·p95 1.36 ms(#107). 디스크 버퍼·EdgeX 모양 MQTT 사본 미확인 | 컨테이너 수 같음, B 대비 확인된 이득이 지연뿐(수집 지연은 알람 경로에서 초 단위 대비 ms) → 결정적 이득 없음, 기준 유지 성격으로 B |

선택: **B**. 규칙 근거 — ③ 에서 A 대비 중계 컨테이너 1개·메모리 대폭 절감, C 와는 컨테이너 동수이고 C 의 추가 이득은 결정을 바꿀 크기가 아님(§1 ③ "미묘하면 기준 유지": 수집기는 V1 계열 제품 유지). 이 선택은 V2 전체 측정에서 ② 가 V1 보다 나쁘지 않을 때만 확정한다.

## 7. V2 조립 중 발견해 고친 내부 오류 (STABILITY 로 옮김)
- InfluxDB 2.9.1 초기 설정 반복 실패: `/etc/influxdb2` 가 이름 없는 볼륨이라 같은 이름 컨테이너 재생성 때 V1 컨테이너의 CLI 설정(2026-09-28 15:51 생성, `default` 항목)이 넘어옴 → V2 전용 이름 볼륨 `influx-config-v2`.
- 중계기(Vector 0.58) InfluxDB 401 → 저장 유실: Vector 0.58 은 설정 파일 `${VAR}` 치환이 기본 꺼짐(`--help` 원문), 토큰·org 가 글자 그대로 전송됨(가로챈 요청으로 확인) → `VECTOR_DANGEROUSLY_ALLOW_ENV_VAR_INTERPOLATION=true`. 같은 기회에 전달 확인(acknowledgements)을 켜 V1 Telegraf#2 의 최소 1회 전달 보장과 같게.
- 수집기 디스크 버퍼 경로 권한: `/var/lib/telegraf` 는 이미지에 없어 권한 오류 → `/tmp/telegraf-buffer`(세션 3 말 반영, 세션 4 기동 확인).

## 7-1. 리서치 반영 결정 (06 참조 구조 · 07 감시 경량화 · 08 부품 안정성, 모두 1차 출처)

| 결정 | 근거(리서치 파일) | 반영 |
|---|---|---|
| Alertmanager 유지 | Grafana 내장 알림으로 대체 가능하나, 빼도 줄어드는 것은 작은 컨테이너 1개이고 경보 규칙 이전이 필요 → ③ "미묘하면 기준 유지" | 그대로 |
| VictoriaMetrics+vmalert 로 교체 안 함 | vmalert 도 알림에 Alertmanager 필요, 무료판 장기지원판 없음(07) | — |
| 브로커 감시 = 브로커 생존(cAdvisor) + 수집기·중계기의 브로커 쓰기 오류 | Mosquitto 는 Prometheus 지표 없음(07). $SYS 구독(mqtt_consumer)은 1.40.1 에서도 브로커 정지 때 프로세스 종료 결함 열림(#17564, 08) → 수집기 안에 두지 않음. 전용 exporter 는 2021 이후 릴리스 없음(07) | 규칙 MQTTBrokerDown·MQTTPublishErrors, Grafana 04 패널 교체, 수집기 `inputs.internal`→`:9273` |
| 탐지 잡 정지 감지 | `flink_jobmanager_numRunningJobs` 실측 확인(V2 Prometheus 조회) | 규칙 FlinkJobsNotRunning(V1 E11 미탐 수정) |
| 중계기 정지 감지 | Vector `internal_metrics`+`prometheus_exporter`(07), up==0 | job relay |
| 수집기 기동 순서 | outputs.mqtt 는 기동 때 연결 실패를 재시도하지 않고 종료(08, 코드 확인) | `depends_on: mqtt healthy`, Kafka 출력 `startup_error_behavior = "retry"` |
| Kafka 쓰기 멱등 | `idempotent_writes` 는 클라이언트 재시도 중복만 막음, 배치 재전송 중복은 남음(08, PR #19735) | 켬(대장 S4 방향) — R03 에서 V1 중복 중앙 150 과 비교 |
| MQTT 연결 유지 | outputs.mqtt keep_alive 기본 0, README 가 Mosquitto 에 0 아닌 값 권고(08) | `keep_alive = 30` |
| 중계기 MQTT 알람 전달 보장 | Vector 0.58 MQTT 싱크는 PUBACK 전에 전달 표시(08, 코드 확인) — "받은 뒤에만 넘긴다"는 MQTT 경로에선 성립 안 함 | 주석 정정, R01 에서 화면 알람 영향 실측 |
| Flink 싱크 정확히 1회는 켜지 않음 | 켜면 트랜잭션 시간 한도 조정 필요, Telegraf 소비는 read_committed 설정 불가(08). 재시작 중복 1건은 알람 워커가 내용 해시로 결합(#107) | 최소 1회 유지(기록) |
| ONNX 잡 체크포인트 | 잡 설정 조회 interval=Long.MAX(꺼짐) — SQL 잡만 `SET` 으로 켜져 있었음(V1 도 같음) | V2 제출 설정 `client-config.v2.yaml` 에 10 s, 4잡 모두 체크포인트 완료 확인(대장 S17) |
| 중계기 로그 잡음 | InfluxDB 싱크 `version` 미지정 경고가 재시작마다 반복 | `version: "2"`(검사기 통과 뒤 적용, 경고 0) |
| Flink 지표 이름 충돌 경고(S14) | Flink 2.2.1 에도 미수정(FLINK-35321·37559 열림, 수정 PR 은 master 만, 08) | 대장 S14 "남김(상류 미수정)" — V2 로그에서 건수 실측 |

## 8. 측정 계획 (결정을 바꿀 수 있는 것만)
- 전체 측정 `STRUCT=V2 sh harness/e2e/baseline.sh EXP-002 V2`: P1(E3·E7·E12·R09) → P2(E1 3묶음) → P3(R01·R02·R03 각 3회, R06·R07·R08·R11·E11).
- 회귀 `STRUCT=V2 sh harness/e2e/regression.sh EXP-002 V2`(S01~S08·S14~S22·S24·S25). V2 가 전부 통과하면 V1 회귀는 결정을 바꾸지 못하므로 생략, 실패 항목이 있으면 그 항목만 V1 에서 잰다.
- 고장→알람 `fault_onset.py`(배속 600, 10 s 이내).
- E2 복잡도 `e2_complexity.py V2`.
