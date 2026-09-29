# 층별 대안 후보표 — 결과 보기 전 고정 2026-09-29 (#69)

판정 규칙은 `QUESTIONS.md` §1 하나뿐이다. 이 표는 그 규칙을 층별 후보에 적용한 **시험 목록**이며, 결과를 본 뒤 후보를 넣거나 빼지 않는다(#59·#60·#65 개정분을 이 판으로 대체).
출처: 딥리서치 4편 `docs/research/deep-2026-09-29/` — R01 `01-ingest-broker-pipe.md` · R02 `02-backbone-stream-ha.md` · R03 `03-storage-monitor-hmi-alarm.md` · R04 `04-ai-graph-rag-agent.md`(모든 사실 확인일 2026-09-29), V1 버전은 `harness/V1_INVENTORY.md`·`harness/V1_FACTS.md`. 이미 잰 결과는 `reports/decision-log.md` #18·#48·#53·#56.

## 개정 #121 (2026-09-29 세션 3, 사용자 지시 "구조 먼저·기능 보존·빠르게") — 아래 모든 개정·본문보다 우선
- 진행 순서의 정본은 `QUESTIONS.md` §1 **"결정 순서"**: 자료 모으기 → 구조(길·레이어) 재설계 → **남는 층에서만** 이 표의 후보로 제품 조합 → 조립·검증.
- 이 표는 **남는 층의 후보 메뉴**다. 재설계로 없어지는 층(예: 수집기→MQTT 중계, MQTT→Kafka 중계)의 후보는 시험하지 않고, 이미 잰 결과(decision-log #104~#119, `experiments/EXP-*/layer_*.json`)는 참고로만 둔다.
- 본문 §0 "성능·용도·'과함' 추정으로는 빼지 않는다"의 예외(#119): ② 가 벤치 결함으로 미완인데 ③ 에서 이길 수 없음이 셀 수 있는 사실로 확정되면(컨테이너 3개 이상 vs ② 통과 1개짜리 등) "② 미완·선택 가능성 없음"으로 기록하고 생략.
- 부품을 빼는 판단은 `QUESTIONS.md` §1 **"기능 보존"**(중복·우회·대체 확인만, 기능 대응표)을 따른다.

## 개정 #92 (2026-09-29, 사용자 지시 "제품이 똑같으면 최신·더 좋은 판으로 고정, A 제품·B 제품처럼 아예 다른 것만 후보", 결과 보기 전) — #90 보다 우선
**후보 = 다른 제품만.** 같은 제품은 판·설정 방식 모두 후보가 아니다.
- **같은 제품 → 가장 좋은 지원 판으로 고정**: Flink 2.2.x(공식 Kafka 커넥터 지원 최신), Kafka 최신 지원판, Telegraf 최신, InfluxDB **2.9**(Flux·기존 질의 유지·지원 중. 3 Core 는 Flux 없음·조회 한도라 더 좋은 판이 아님), Prometheus·Alertmanager·Grafana·cAdvisor 최신, FUXA 1.3.4, Neo4j 5.26 LTS, Mosquitto(브로커 결정분) 최신.
- **같은 제품 안의 설정 개선은 하지 않는다(#93)**: 최신 판 고정으로 끝. **예외: Flink 재시작 복구(HA) 설정은 켠다(#94)** — `flinkha` 프로필은 후보가 아니라 이 설정 확인용.
- **구조 변경 → 구조 재설계(`QUESTIONS.md` §1 결정 순서 2)**: Telegraf 3→1 통합, FUXA 브로커 직접 구독(UNS), 브로커 Kafka 브리지 등 §11.
- 후보에서 빠지는 것: Flink HA-A~D·DataStream CEP 방식, InfluxDB 3, Telegraf 1개 통합 프로필, FUXA UNS 프로필, 감시 규칙 추가 프로필(Prometheus·VM 판).

## 개정 #90 (2026-09-29, 사용자 지시 "버전만 바뀐 것은 의미 없다", 결과 보기 전)
**같은 제품의 판만 다른 항목은 직접 시험 후보가 아니다.** 모든 제품은 지원되는 최신판을 명시 번호로 고정해 쓰고(`latest` 태그 금지), 그 판이 V1 기능을 깨는지는 회전 확정의 전체 회귀(S01~S25·G0~G10·E·R)에서 한 번에 확인한다.
- 후보에서 빠지는 판 항목(최신판 고정으로 흡수): Flink 2.2·2.3 단독, Flink DataStream CEP 2.3, Kafka 4.1·4.2·4.3, InfluxDB 2.9, Prometheus 3.13·3.15, Telegraf 1.40 ×3, FUXA 1.3.4(V1 이 이미 1.3.4), EMQX 6.x(어차피 BSL 제외).
- 남는 것: **다른 제품** 과 **다른 구조·방식**(Flink HA 4구성·DataStream CEP 방식, Telegraf 3→1 통합, FUXA 브로커 직접 구독(UNS), 감시 탐지기 정지 규칙, InfluxDB 3 = 질의 언어가 다른 사실상 다른 제품). V1 부품 프로필은 비교 기준으로 남는다.
- 판 선택 주의: Flink 는 공식 Kafka 커넥터가 지원하는 최신 조합(2.2.x)으로 고정.

## 개정 #74 (2026-09-29, 결과 보기 전 — 관문 사실 재확인 `docs/research/deep-2026-09-29/05-gate-verification.md`)
아래가 본문 표보다 우선한다.
- **강제 교체 확정:** EdgeX 4.0.0(4.0 LTS 2027-03 종료, 4.0.2도 같은 LTS → EdgeX 4.0.2·EdgeX 슬림화 행은 ① 관문 제외), Grafana 11.4(2025-09-05 종료), Alertmanager 0.28(마지막 패치 0.28.1 2025-03-07, 18개월+ 무패치), cAdvisor v0.49.1(현행 v0.60.6, `ghcr.io/google/cadvisor`).
- **Flink 1.20.1: 강제 교체 아님(정정).** "명목 종료 ≈2026-08(이미 경과)"는 틀림 — 1.20은 LTS 표기 유지, 2026-09-26에도 백포트 진행. 종료일 [미확인]. 같은 제품 최신판(2.x)이 첫 후보인 것은 그대로.
- **직접 시험 → ① 관문 제외:** Siddhi(런너 이미지 2019 마지막), M3(v1.6.0 이미지 없음), PyScada(공식 이미지 없음), alerta-ng(자체 이미지 없음), Hazelcast(재시작 복구·Jet 무손실 복구 Enterprise 전용), Amlen(릴리스 고정 태그 없음).
- **① 관문 제외/미확인 → 직접 시험:** Tansu, RobustMQ, ActiveMQ Classic(`apache/activemq:6.3.2`), comqtt(MIT, ghcr 2.6.5), fast-graphrag(MIT). Artemis 이미지 = `apache/artemis:2.57.0`.
- **Grafana 는 롤링 지원 제품으로 분류**(월간 마이너, 계열 지원 지속 → §12-0 원칙 동일, 조건 "마이너 추종"). 13.2 는 2027-05-18 종료지만 계열이 지원 중.
- 유지: Mosquitto 지원 정책 [미확인], Flink Kafka 커넥터 2.3 공식 미지원(②에서 비공식 조합 확인), `neo4j:2026.09-community` 존재.

## 0. 읽는 법

**분류(세 가지만)**
- **직접 시험**: 문헌상 ① 관문 통과. 성능·용도·"과함" 추정으로는 빼지 않는다. 기능이 안 맞을 것 같은 후보도 ② 기동·기능(수 분)에서 실제로 떨어뜨린다.
- **① 관문 제외**: 라이선스·약관(BSL·SSPL·TSL·RCL·ELv2·상용·체험판·비상업·키로 여는 기능) / EOL·보안 패치 없음·2027-09-29 이전 지원 종료 / 컨테이너 이미지 없음 — **사실 + URL + 날짜(2026-09-29 확인)** 가 있을 때만.
- **강제 교체 대상**: V1(현재 기준 버전) 부품이 ① 관문에 걸리거나 2027-09-29 이전 지원 종료. 성능과 무관하게 교체하며, ① 통과 후보 중 ②에서 가장 덜 나빠지는 것을 고르고 나빠진 양을 약점 열에 적는다(QUESTIONS §1 추가 규칙).
- 보조 표시: **[미확인]** = 관문 사실 하나를 1차 출처로 못 확인 → §12 "확인 필요"에서 재확인 후 분류 확정(그 전엔 ② 기동 확인까지만 진행 가능). **⚠제품화 시 주의** = GPL·AGPL(제외 아님). **측정 완료** = 이미 잰 결과, 변경 없이 이월.

**지원 기간 해석(이 표에서 쓴 방식, §12-0에서 재확인):** 같은 호환 라인 안에서 마이너만 올리면 계속 패치되는 **롤링 지원 제품**(Telegraf·Flink 2.x·Prometheus 3.x·Neo4j CalVer·InfluxDB 3 Core·RabbitMQ 등)은 "그 라인이 지원 중인가"로 판정하고 운영 조건 "마이너 추종"을 붙인다. 12개월 규칙은 **종료일이 정해져 있고 다음으로 가려면 메이저 이전이 필요한 라인**(EdgeX 4.0 LTS, Kafka 3.9·4.0, Flink 1.x, Pulsar 4.2)에 적용한다.

**우선순위(가치 × 위험):** P1 = V1 최대 약점·강제 교체·큰 단순화가 걸림, 먼저. P2 = 의미 있는 대안. P3 = 가치가 낮거나 기능 적합이 불확실, 마지막. 우선순위는 **순서**일 뿐 빼는 기준이 아니다. **[묶음 X]** 는 같은 엔진·계열로, 같은 ② 기동·기능 점검 한 벌을 먼저 한꺼번에 돌린다.

**시험 순서(구조 재설계 뒤 남는 층 공통, QUESTIONS §1 "빠르게 거르는 순서"):** ① 관문(문헌, 이 표로 완료) → ② 기동·기능(수 분, 기준 버전이 하던 일을 실제로 하는가. 실패는 로그·화면으로 기록하고 그 자리에서 탈락) → ③ 정상 성능(지연 p95·처리량·자원, 3회 중앙값) → ④ 비정상(`ROBUSTNESS.md` 행). 앞 단계 탈락 시 뒤 단계 생략. 층마다 기준 버전 부품을 같은 벤치에서 같은 방법으로 먼저 잰다.

---

## 1. 이상탐지(스트림 처리)

V1: Flink **1.20.1** 세션 클러스터(HA 없음), SQL 잡 3 + ONNX DataStream 잡 1. JM 재시작 시 잡 소멸(V1_FACTS §5, 최대 약점).
강제 교체: **대상** — Flink 1.20은 1.x 마지막 LTS로 FLIP-458 "2년 고정 지원" → 명목 종료 ≈2026-08(이미 경과). 공식 종료 공지·연장 여부 **[미확인]** (R02 §0, https://cwiki.apache.org/confluence/display/FLINK/FLIP-458:+Long-Term+Support+for+the+Final+Release+of+Apache+Flink+1.x+Line).
측정 완료(이월): Flink 2.2.1 SQL(V1 SQL 무수정) 21/21·알람 81=81, 정확도 동일, 재시작 미측정(#18). 직접 짠 Python 탐지기 원칙 위반 탈락(#53).
시험 순서: ② V1 SQL·ONNX 잡 제출·기동, L4-01~06 리플레이 판정 동일 → ③ CEP 지연 p95·메모리·CPU(L4-09·13) → ④ R04·R05(재시작, 자동 복구), R08(L4-14), R09(L4-15), R10.

| 후보 | 버전(날짜) | 라이선스 | 이미지 | 분류 | 근거(URL) | 우선순위 |
|---|---|---|---|---|---|---|
| **Flink 2.3 [묶음 F]** (같은 제품 최신) | 2.3.0 (2026-06-25) | Apache-2.0 | `flink:2.3.0` | 직접 시험. 마이너 추종(현·직전 마이너만 버그픽스). **Kafka 커넥터 2.3 호환 [미확인]** — ②의 첫 항목 | https://flink.apache.org/2026/06/25/apache-flink-2.3.0-release-announcement/ · https://flink.apache.org/downloads/ | P1 |
| Flink 2.2 SQL [묶음 F] | 2.2.1 (2026-05-15) | Apache-2.0 | `flink:2.2.1` (+커넥터 5.0.0) | 직접 시험. **측정 완료: 정확도 동일(#18)**. ④ 재시작부터 이어서. 2.4 출시 시 지원 종료 → 마이너 추종 | https://flink.apache.org/2026/05/15/apache-flink-2.2.1-release-announcement/ | P1 |
| Flink 2.2/2.3 DataStream CEP [묶음 F] | 위와 같음 | Apache-2.0 | 위와 같음 | 직접 시험(V1 SQL MATCH_RECOGNIZE의 대안 구현 방식) | 위와 같음 · V1_FACTS §2 | P2 |
| Flink HA-A: ZooKeeper HA + 세션 [묶음 F] | ZooKeeper 3.9.6(current) | Apache-2.0 | `zookeeper:3.9.5`(공식 최신 태그) | 직접 시험. JM 재시작 시 제출된 잡을 최신 체크포인트에서 재개 | https://nightlies.apache.org/flink/flink-docs-release-2.2/docs/deployment/ha/overview/ · https://zookeeper.apache.org/releases.html | **P1(V1 최대 약점)** |
| Flink HA-B: ZooKeeper HA + 애플리케이션 모드 [묶음 F] | 위와 같음 | Apache-2.0 | 위와 같음 | 직접 시험(잡 4개 = JM 4개) | 위와 같음 | P2 |
| Flink HA-C: 보존 체크포인트 + 재기동 스크립트 [묶음 F] | Flink 2.x 설정 | Apache-2.0 | 위와 같음 | 직접 시험(자동 복구 아님 — 스크립트는 연결 로직) | R02 §3 | P2 |
| Flink HA-D: `group-offsets` 재개 폴백 [묶음 F] | Flink 2.x 설정 | Apache-2.0 | 위와 같음 | 직접 시험(A·C의 보조, 윈도 상태 손실·재집계) | R02 §3 | P2 |
| Kafka Streams [묶음 K-lib] | Kafka 4.3.1 동봉 | Apache-2.0 | 라이브러리(앱 이미지 빌드) | 직접 시험. changelog로 상태 복원, EO. CEP는 상태 저장소로 구현 | https://kafka.apache.org/42/streams/upgrade-guide/ | P2 |
| Quix Streams [묶음 K-lib] | 3.26.0 (2026-09-14) | Apache-2.0 | 라이브러리(앱 이미지 빌드) | 직접 시험. Python + onnxruntime 직결, RocksDB+changelog(#53이 지목한 "실제 프레임워크" 경량 대안) | https://github.com/quixio/quix-streams/releases | P1 |
| LF Edge eKuiper | 2.4.2 (2026-09-09), 2.2.8 (2026-09-18) | Apache-2.0 | `lfedge/ekuiper` | 직접 시험. MQTT 직접 소스·SQL 규칙·ONNX 플러그인. MQTT 되감기 불가 | https://ekuiper.org/docs/en/latest/guide/ai/onnx.html · https://ekuiper.org/docs/en/latest/guide/rules/state_and_fault_tolerance.html | P1 |
| RisingWave 코어 [묶음 SQL-DB] | 3.1.0 (2026-09-21) | Apache-2.0 (Premium 기능은 키 → **미사용**) | `risingwavelabs/risingwave` | 직접 시험(키 기능 제외 조건). MATCH_RECOGNIZE·ONNX 경로 [미확인] → ②에서 확인 | https://docs.risingwave.com/get-started/premium-features | P2 |
| Timeplus Proton [묶음 SQL-DB] | 3.0.31 (2026-09-17) | Apache-2.0 (클러스터·확장 커넥터 Enterprise → 미사용) | `timeplus/proton` | 직접 시험. CEP·onnxruntime UDF [미확인] → ② | https://github.com/timeplus-io/proton | P2 |
| Feldera [묶음 SQL-DB] | 0.357.0 (2026-09-27) | MIT | `images.feldera.com/feldera/pipeline-manager` | 직접 시험(0.x, 결함허용 preview) | https://github.com/feldera/feldera | P3 |
| Arroyo | 0.15.0 (2025-12-01) | Apache-2.0 | `ghcr.io/arroyosystems/arroyo` | 직접 시험. MQTT 소스, CEP 없음, 릴리스 간격 10개월 | https://www.arroyo.dev/blog/arroyo-is-joining-cloudflare/ | P3 |
| Apache StreamPipes | 0.98.0 (2025-12-15) | Apache-2.0 | `apachestreampipes/*` | 직접 시험(산업 IoT 올인원, ET·CEP·ONNX [미확인]) | https://streampipes.apache.org/download/ | P3 |
| Apache Storm | 3.1.0 (2026-09-12) | Apache-2.0 | `storm` | 직접 시험(Nimbus+ZK, CEP 없음) | https://github.com/apache/storm/releases | P3 |
| Apache Beam(Flink 러너) | 2.77.0-RC2 (2026-09-22) | Apache-2.0 | SDK 이미지 | 직접 시험(API 계층, 백엔드 대체 아님) | https://github.com/apache/beam/releases | P3 |
| Siddhi | 5.1.33 (2026-05-05) | Apache-2.0 | 러너 이미지 **[미확인]** | 직접 시험 — 이미지 확인 전까지 관문 미결 | https://github.com/siddhi-io/siddhi/releases | P3 |
| Hazelcast (Jet) | 5.7.0 (2026-05-13) | Apache-2.0 + **Hazelcast Community License 혼합** | `hazelcast/hazelcast` | 관문 미결 — 필요 기능(디스크 영속 재시작 복구)이 비OSI·Enterprise 쪽인지 **[미확인]** | https://hazelcast.com/blog/changes-to-community-edition/ | P3 |
| Redpanda Connect · Bento (브리지 용도) | 4.111.0 / 1.21.2 | Apache-2.0(+RCL) / MIT | §4 참조 | §4 중계 파이프에서 시험(무상태 중심, 탐지 엔진 아님) | R02 §2 | — |
| Flink 1.20.5 (V1 같은 라인 최신 패치) | 1.20.5 (2026-06-03) | Apache-2.0 | `flink:1.20.5` | **① 관문 제외(갱신 대상)** — 1.x LTS 명목 종료 ≈2026-08 [미확인: 공식 종료일] | FLIP-458 URL(위) · https://flink.apache.org/downloads/ | — |
| Esper | 9.0.0 (2024-04-26) | GPL-2.0 (상용 별도) | 없음 | **① 관문 제외** — 29개월 무릴리스(보안 패치 없음), 재시작 복구는 상용 EsperHA 전용 | https://www.espertech.com/esper/esper-faq/ · https://github.com/espertechinc/esper/releases | — |
| Bytewax | 0.21.1 (2024-11-25) | Apache-2.0 | `bytewax/bytewax` | **① 관문 제외** — 회사 중단(2025-05), 22개월 무릴리스 | https://github.com/bytewax/bytewax | — |
| Pathway | 0.33.0 (2026-09-18) | **BSL 1.1** | — | **① 관문 제외**(라이선스) | https://pathway.com/license | — |
| Numaflow | 1.8.4 (2026-09-10) | Apache-2.0 | — | **① 관문 제외** — 쿠버네티스 전용, Docker Compose 불가 | https://numaflow.numaproj.io/ | — |
| Fluvio + SDF | 0.18.1 (2025-07-04) | Fluvio Apache-2.0 / SDF 독점 | 이관 중 | **① 관문 제외** — 처리 엔진(SDF) 독점, 15개월 무릴리스 | https://infinyon.com/docs/resources/stateful-dataflows-concepts/ | — |
| Apache Samza | 1.8.0 (2023-01-17) | Apache-2.0 | — | **① 관문 제외** — 3년 무릴리스 | https://samza.apache.org/ | — |
| Apache Heron | 0.20.5 (2022) | — | — | **① 관문 제외** — 인큐베이터 은퇴 2023-01-18 | https://incubator.apache.org/projects/heron.html | — |
| Materialize | — | **BSL** | — | **① 관문 제외**(라이선스, 기존 결정) | — | — |
| 직접 짠 Python 탐지기(EXP-113b) | — | — | — | **원칙 제외(#53)** — 엔진급 기능 직접 제작 금지. 기록 유지 | `reports/decision-log.md` #53 | — |

## 2. 수집 (Modbus TCP → MQTT)

V1: EdgeX **4.0.0**(10컨테이너, 내부 Mosquitto 2.0.21·PostgreSQL 16.3 포함). 별도로 FUXA가 설비를 직접 폴링(이중 폴링).
강제 교체: **대상 [미확인]** — EdgeX 4.0 LTS 지원 **2027-03 종료**(검색 요약 기준, 원문 LTS 페이지 미확인 → §12). 다음 정식판(Queensland)은 2027 봄 예정, 4.1은 dev 태그만(R01 §0, https://lf-edgexfoundry.atlassian.net/wiki/display/FA/Releases · https://www.edgexfoundry.org/software/releases/).
시험 순서: ② 12태그 1초 폴링 → MQTT 발행, 태그·단위·quality 동일(F01) → ③ 발행 지연·자원·컨테이너 수 → ④ R02(단절 60초 보관·재전송), R11(설비 통신 끊김 결측 표시), R09.

| 후보 | 버전(날짜) | 라이선스 | 이미지 | 분류 | 근거(URL) | 우선순위 |
|---|---|---|---|---|---|---|
| **EdgeX 4.0.2** (같은 제품 최신) | 4.0.2 "Palau" (2026-05-29) | Apache-2.0 | `edgexfoundry/core-data:4.0.2` 등 | **관문 미결 [미확인]** — 같은 4.0 LTS라 2027-03 종료가 확인되면 ① 관문 제외(후보 자신 12개월 내 종료). 확인 전엔 ② 기동만 | https://github.com/edgexfoundry/edgex-go/releases/tag/v4.0.2 | P2 |
| EdgeX 경량화(core-data 등 비활성, MQTT 버스 직결) | 4.0.2 | Apache-2.0 | 위와 같음 | 위와 같은 관문 미결. 끌 수 있는 서비스 [미확인] | R01 §4-I | P3 |
| Telegraf `inputs.modbus` [묶음 Go-pipe] | 1.40.1 (2026-09-21) | MIT | `telegraf:1.40.1-alpine` | 직접 시험. MQTT·Kafka·InfluxDB·PostgreSQL 출력 모두 OSS | https://docs.influxdata.com/telegraf/v1/input-plugins/modbus/ | **P1** |
| benthos-umh [묶음 Go-pipe] | v0.16.0 (2026-09-23) | Apache-2.0 | `ghcr.io/united-manufacturing-hub/benthos-umh` | 직접 시험. Modbus·S7·OPC UA·Sparkplug 입력 + MQTT·Kafka·SQL 출력 | https://github.com/united-manufacturing-hub/benthos-umh | P1 |
| Neuron (EMQ) | 이미지 2.13.0 (2025-12-18), git 2.15.0 (2026-06-03) | LGPL-3.0 | `emqx/neuron:2.13.0` | 직접 시험(Modbus TCP·MQTT OSS 범위만). 이미지·소스 버전 불일치, 2.14·2.15 이미지 [미확인] | https://github.com/emqx/neuron · https://hub.docker.com/r/emqx/neuron/tags | P2 |
| HiveMQ Edge | 2026.14 (2026-09-15) | Apache-2.0 | `hivemq/hivemq-edge:2026.14` | 직접 시험. Modbus 어댑터 + 내장 MQTT 브로커(수집·브로커 통합안). **오프라인 버퍼·Data Hub는 상용 키 → 미사용 조건**(R02 단절 시험에서 영향 확인) | https://github.com/hivemq/hivemq-edge · https://docs.hivemq.com/hivemq-edge/index.html | P1 |
| Node-RED + node-red-contrib-modbus | 5.0.7 (2026-09-08) / contrib 5.60.2 (2026-08-14) | Apache-2.0 / BSD-3 | `nodered/node-red` | 직접 시험(4.x는 유지보수 모드 → 5.x로) | https://nodered.org/blog/2026/06/09/version-5-0-released · https://www.npmjs.com/package/node-red-contrib-modbus | P2 |
| ThingsBoard IoT Gateway | 3.8.5 (2026-09-17) | Apache-2.0 | `thingsboard/tb-gateway:3.8.5` | 직접 시험 — 일반 MQTT 브로커로 보낼 수 있는지 [미확인] → ② 첫 항목 | https://github.com/thingsboard/thingsboard-gateway | P3 |
| Apache StreamPipes (Modbus 어댑터) | 0.98.0 (2025-12-15) | Apache-2.0 | `apachestreampipes/backend:0.98.0` | 직접 시험(어댑터 목록 [미확인]) | https://github.com/apache/streampipes/releases | P3 |
| OpenRemote | 1.31.1 (2026-09-28) | **AGPL-3.0 ⚠제품화 시 주의** | `openremote/manager:1.31.1` (R03) | 직접 시험(플랫폼 전체라 범위 큼) | https://docs.openremote.io/docs/user-guide/agents-protocols/modbus/ | P3 |
| Apache PLC4X (+Kafka Connect) | 1.0.0 (2026-09-07) | Apache-2.0 | **공식 이미지 없음**(소스 빌드) | **① 관문 제외**(컨테이너 이미지 없음, 자체 빌드 허용 시 재평가) | https://github.com/apache/plc4x/releases | — |
| UMH Core | v0.44.41 (2026-09-24) | 저장소 Apache-2.0, **Redpanda 브로커(BSL 1.1) 동봉** | `ghcr.io/united-manufacturing-hub/umh-core` | **① 관문 제외**(BSL 구성요소) | https://github.com/redpanda-data/redpanda/blob/dev/licenses/bsl.md | — |
| Eclipse Kura (Modbus 드라이버) | 5.6.2 (2026-07-08) | EPL-2.0, 드라이버는 Eurotech EULA | [미확인] | **① 관문 제외** — Modbus 드라이버 EULA가 비전문(개발·시험·시연) 용도만 허용 | https://marketplace.eclipse.org/content/modbus-master-driver-v2 | — |
| Neuron 상용 드라이버 | — | 상용 | — | **① 관문 제외**(기존 결정) | https://github.com/emqx/neuron | — |

## 3. 브로커 (MQTT)

V1: EMQX **5.8.6**(Apache-2.0 마지막 라인).
강제 교체: **대상(확정)** — EMQX 오픈소스 5.8은 **2026-02-28 EOL**, 보안 패치·공식 배포 종료. 같은 제품 최신(6.x)은 BSL이라 같은 제품 안에서 갈 곳이 없음(R01 §0, https://www.emqx.com/en/news/a-notice-on-the-emqx-5-8-open-source-version).
측정 완료(이월): **Mosquitto 2.1.2 조건부 채택**(#48 7항목 통과 → #56 조건부: S10 단절 60초·과부하·느린 구독자·장시간 미검증). **NanoMQ 0.25.6 탈락**(BR-03 0/600), **HiveMQ CE 2026.5 탈락**(BR-02 유실 527·569, p95 20배, BR-07 ✗) — #48.
시험 순서: ② `harness/situations/BROKER.md` BR-01~07 기능(QoS1 세션·재시작 큐 보존·인증/ACL) → ③ p95·메모리·이미지 → ④ R01, R02, R08, R09(+#56 미검증 항목).

| 후보 | 버전(날짜) | 라이선스 | 이미지 | 분류 | 근거(URL) | 우선순위 |
|---|---|---|---|---|---|---|
| EMQX 6.x (같은 제품 최신) | 6.3.1 LTS (2026-09-18) | **BSL 1.1** (단일 노드만 무료, 클러스터·제품 내장 제한) | `emqx/emqx:6.3` | **① 관문 제외**(라이선스) — 첫 후보가 관문에서 탈락 | https://www.emqx.com/en/content/license-faq · https://www.emqx.com/en/news/emqx-adopts-business-source-license | — |
| **Mosquitto** | 2.1.2 (2026-02-09) | EPL-2.0 / EDL-1.0 | `eclipse-mosquitto:2.1.2-alpine` | 직접 시험 — **측정 완료: 조건부 채택(#48·#56)**. 남은 것은 #56 미검증 항목만. 공식 지원 기간 [미확인]. Kafka 브리지는 Cedalo Pro(상용) 전용 | https://mosquitto.org/blog/2026/01/version-2-1-0-released/ | **P1(조건 해소)** |
| RMQTT | 0.24.0 (2026-09-19) | MIT | `rmqtt/rmqtt:0.24.0` | 직접 시험. OSS에 인증/ACL + **Kafka egress 브리지**(구조 패턴 P-C) | https://github.com/rmqtt/rmqtt | **P1** |
| TBMQ | 2.4.0 (2026-08-27) | Apache-2.0 | `thingsboard/tbmq:2.4.0` | 직접 시험. Integration Executor(Kafka 출력). Kafka·PostgreSQL·Redis 필요 | https://github.com/thingsboard/tbmq · https://thingsboard.io/docs/mqtt-broker/integrations/kafka/ | P2 |
| HiveMQ Edge(내장 브로커) | 2026.14 | Apache-2.0 | §2 참조 | 직접 시험(§2와 한 벤치, 수집+브로커 통합안) | §2 | P2 |
| NATS Server (MQTT) [묶음 NATS] | 2.15.0 (2026-09-17) | Apache-2.0 | `nats` | 직접 시험. MQTT 3.1.1만, JetStream 필수(§5 백본과 같은 이미지) | https://docs.nats.io/running-a-nats-service/configuration/mqtt | P2 |
| Apache BifroMQ | 4.0.0-incubating (2026-01-28) | Apache-2.0 | `apache/bifromq:4.0.0-incubating` (R01; R02는 [미확인]) | 직접 시험. 인증·ACL 기본 제공 수준 [미확인] | https://github.com/apache/bifromq | P2 |
| RabbitMQ (MQTT 플러그인) [묶음 RMQ] | 4.3.6 (2026-09-14) | MPL-2.0 | `rabbitmq` | 직접 시험. 커뮤니티 패치는 최신 마이너만(마이너 추종) | https://github.com/rabbitmq/rabbitmq-server/blob/main/COMMUNITY_SUPPORT.md | P2 |
| LavinMQ | 2.10.0 (2026-09-25) | Apache-2.0 | `cloudamqp/lavinmq:2.10.0` | 직접 시험(MQTT 3.1.x만) | https://github.com/cloudamqp/lavinmq | P3 |
| ActiveMQ Artemis [묶음 AMQ] | 2.57.0 (2026-09-09) | Apache-2.0 | `apache/activemq-artemis` (Docker Hub 최신 2.44.0 — 배포 위치 [미확인]) | 직접 시험 — 현행 이미지 [미확인] | https://github.com/apache/activemq-artemis | P3 |
| ActiveMQ Classic [묶음 AMQ] | 6.3.2 (2026-09-02) | Apache-2.0 | **[미확인]** | 관문 미결(공식 이미지 확인 전) | https://github.com/apache/activemq | P3 |
| Mochi-MQTT | 2.7.9 (2025-03-01) | MIT | `mochimqtt/server:2.7.9` | 직접 시험. EOL 공지 없음, 18개월 무릴리스(유지보수 위험 기록) | https://github.com/mochi-mqtt/server | P3 |
| RobustMQ | 0.4.11 (2026-07-31) | Apache-2.0 | **[미확인]** | 관문 미결(공식 이미지) | https://github.com/robustmq/robustmq | P3 |
| Eclipse Amlen | 1.0.0.2 (2024-02-07) | EPL-2.0 | `quay.io/amlen/amlen-server:main` (버전 고정 태그 [미확인]) | 관문 미결 — 2년+ 정식 릴리스 없음, 고정 태그 [미확인] | https://github.com/eclipse/amlen | P3 |
| comqtt | v2.6.5 (2026-07-11) | **[미확인]** | **[미확인]** | 관문 미결(라이선스·이미지) | https://github.com/wind-c/comqtt | P3 |
| NanoMQ | 0.25.6 (2026-08-19) | MIT | `emqx/nanomq` | **측정 완료: 탈락(#48, BR-03 0/600)** | https://github.com/nanomq/nanomq/releases | — |
| HiveMQ CE | 2026.5 (2026-05-27) | Apache-2.0 | `hivemq/hivemq-ce` | **측정 완료: 탈락(#48)** | https://github.com/hivemq/hivemq-community-edition/releases | — |
| VerneMQ | 2.2.1 (2026-09-23) | 소스 Apache-2.0, **공식 이미지·바이너리 EULA(상업 사용 유료)** | `vernemq/vernemq:2.2.1` | **① 관문 제외**(약관, 자체 빌드 시 재평가) | https://github.com/vernemq/docker-vernemq/blob/master/README.md · https://vernemq.com/blog/2019/11/26/vernemq-end-user-license-agreement.html | — |
| FlashMQ | 1.27.2 (2026-09-28) | OSL-3.0 | **공식 이미지 없음** | **① 관문 제외**(컨테이너 없음) | https://github.com/halfgaar/FlashMQ | — |
| Aedes | 1.2.0 (2026-09-16) | MIT | 없음(라이브러리) | **① 관문 제외**(컨테이너 없음) | https://www.npmjs.com/package/aedes | — |
| Moquette | 0.18.x (2026-08) | Apache-2.0 | 없음(임베드용) | **① 관문 제외**(컨테이너 없음) | https://github.com/moquette-io/moquette | — |
| Waterstream | — | 상용 | `waterstreamio/waterstream-kafka` | **① 관문 제외**(상용) | https://waterstream.io/ | — |
| Cedalo Pro Mosquitto | — | 상용 | — | **① 관문 제외**(상용) | https://www.cedalo.com/pro-mosquitto/broker | — |

## 4. 중계 파이프 (+알람 워커)

V1: Telegraf **1.33** ×3(#1 MQTT→Kafka, #2 Kafka→InfluxDB, #3 알람 Kafka→MQTT) + `ai-alarm-worker`(직접 짠 알람 접수 로직, 허용 범위).
강제 교체: **Telegraf 1.33 대상(확정)** — 한 버전 약 9개월 지원, 1.38이 2026-09-07 EOL이므로 1.33은 지원 종료(R01 §0, https://endoflife.date/telegraf · https://github.com/influxdata/telegraf/releases).
시험 순서: ② 세 경로(raw 적재·clean 저장·알람 재발행) 각각 동작, Kafka 4.x 입력 소비 확인(#17570) → ③ 경로별 지연·자원 → ④ R01, R03, R06(저장소 다운 중 알람 지속), R08. 한 프로세스 통합안은 경로 간 장애 격리를 ④에서 별도 확인.

| 후보 | 버전(날짜) | 라이선스 | 이미지 | 분류 | 근거(URL) | 우선순위 |
|---|---|---|---|---|---|---|
| **Telegraf 1.40 ×3** (같은 제품 최신) [묶음 Go-pipe] | 1.40.1 (2026-09-21) | MIT | `telegraf:1.40.1-alpine` | 직접 시험. 마이너 추종. Kafka 4 입력 이슈 #17570 해결 근거 없음 → ② 필수 | https://github.com/influxdata/telegraf/releases · https://github.com/influxdata/telegraf/issues/17570 | **P1(강제 교체)** |
| Telegraf 1대 통합 [묶음 Go-pipe] | 1.40.1 | MIT | 위와 같음 | 직접 시험(패턴 P-E) | https://github.com/influxdata/telegraf | P1 |
| Redpanda Connect (Apache 컴포넌트만) [묶음 Benthos] | v4.111.0 (2026-09-25) | Apache-2.0 번들(`mqtt`·`kafka_franz`·`sql_insert` 확인) | `docker.redpanda.com/redpandadata/connect` | 직접 시험(엔터프라이즈 커넥터 미사용) | https://github.com/redpanda-data/connect · https://docs.redpanda.com/redpanda-connect/get-started/licensing/ | P2 |
| Bento [묶음 Benthos] | v1.21.2 (2026-09-11) | MIT | `ghcr.io/warpstreamlabs/bento` | 직접 시험(엔터프라이즈 잠금 없음) | https://github.com/warpstreamlabs/bento | P2 |
| benthos-umh [묶음 Benthos] | v0.16.0 | Apache-2.0 | §2 참조 | 직접 시험(수집~중계 한 도구) | §2 | P2 |
| LF Edge eKuiper (알람 워커·규칙) | 2.4.2 (2026-09-09) | Apache-2.0 | `lfedge/ekuiper` | 직접 시험. MQTT 소스+SQL 규칙 → **알람 워커 대체 후보**. Kafka·SQL 싱크는 플러그인 | https://ekuiper.org/docs/en/latest/guide/sinks/overview.html | P1 |
| Kapacitor (알람) | 1.8.7 (2026-09-16) | MIT | `kapacitor` | 직접 시험. PostgreSQL 기록 경로 [미확인] → ② | https://github.com/influxdata/kapacitor | P3 |
| Node-RED (알람 흐름) | 5.0.7 | Apache-2.0 | `nodered/node-red` | 직접 시험(패턴 P-G) | §2 | P3 |
| Lenses Stream Reactor (Kafka Connect MQTT source) | 12.1.2 (2026-09-15) | Apache-2.0 | Connect 런타임 플러그인 — 권장 런타임 이미지 **[미확인]** | 직접 시험 — Kafka ≥4.0 필요(백본 교체 후), 런타임 이미지 확인 필요 | https://github.com/lensesio/stream-reactor · https://docs.lenses.io/latest/connectors/kafka-connectors/sources/mqtt | P2 |
| RMQTT·TBMQ 내장 Kafka 출력 | §3 참조 | MIT / Apache-2.0 | §3 참조 | 직접 시험(Telegraf#1 제거, 패턴 P-C) | §3 | P1 |
| Apache NiFi | 2.12.0 (2026-09-13) | Apache-2.0 | `apache/nifi:2.12.0` | 직접 시험 | https://github.com/apache/nifi | P3 |
| Vector | 0.58.0 (2026-08-26) | MPL-2.0 | `timberio/vector` (현재 이름 **[미확인]**) | 직접 시험. MQTT 소스 beta·ack 미지원 | https://vector.dev/docs/reference/configuration/sources/mqtt/ | P3 |
| Fluent Bit | 5.1.2 (2026-09-05) | Apache-2.0 | `fluent/fluent-bit` | 직접 시험 — 문헌상 MQTT 입력이 서버 모드라 브로커 구독 불가로 보임. 관문 사실이 아니므로 ② 기능 확인(수 분)에서 판정 | https://docs.fluentbit.io/manual/data-pipeline/inputs/mqtt | P3 |
| RisingWave (MQTT 소스 → SQL 뷰) | 3.1.0 | Apache-2.0 (Premium 미사용) | §1 참조 | 직접 시험(구조 대안, MQTT 커넥터 무료 여부 [미확인]) | §1 | P3 |
| Confluent MQTT Source Connector | — | **상용**(30일 체험 후 구독) | — | **① 관문 제외** | https://docs.confluent.io/kafka-connectors/mqtt/current/mqtt-source-connector/overview.html | — |
| Redpanda Connect 엔터프라이즈 커넥터 | — | **RCL**(키 필요) | — | **① 관문 제외** | https://github.com/redpanda-data/connect/tree/main/licenses | — |

## 5. 백본

V1: Kafka **3.9.0**(이미 KRaft 단일 노드, ZooKeeper 없음).
강제 교체: **대상(확정)** — Kafka 3.9 지원 종료 **2027-02-19**(12개월 안, R02 §0, https://endoflife.date/apache-kafka).
시험 순서: ② Telegraf 입·출력, Flink 커넥터 소비, 오프셋 재개·로그 재생(F11/E6) → ③ 처리량·지연·자원 → ④ R03, R08, R09, E6 재처리.

| 후보 | 버전(날짜) | 라이선스 | 이미지 | 분류 | 근거(URL) | 우선순위 |
|---|---|---|---|---|---|---|
| **Kafka 4.3** (같은 제품 최신) [묶음 Kafka] | 4.3.1 (2026-06-23), 종료 2028-06-17 | Apache-2.0 | `apache/kafka` | 직접 시험 | https://endoflife.date/apache-kafka | **P1(강제 교체)** |
| Kafka 4.2 [묶음 Kafka] | 4.2.1 (2026-05-28), 이미지 4.2.2 (2026-09-28), 종료 2028-03-04 | Apache-2.0 | `apache/kafka` | 직접 시험 | 위와 같음 · https://hub.docker.com/r/apache/kafka/tags | P1 |
| Kafka 4.1 [묶음 Kafka] | 종료 2027-10-15 (경계, 약 12.5개월) | Apache-2.0 | `apache/kafka` | 직접 시험(규칙상 통과, 4.2·4.3이 있어 순서 마지막) | 위와 같음 | P3 |
| NATS Server + JetStream [묶음 NATS] | 2.15.0 (2026-09-17) | Apache-2.0 (2025-05 BSL 전환 철회) | `nats` | 직접 시험. 내장 MQTT, Flink 커넥터는 제3자(Synadia, ALO) | https://www.cncf.io/announcements/2025/05/01/cncf-and-synadia-align-on-securing-the-future-of-the-nats-io-project/ · https://mvnrepository.com/artifact/io.synadia/flink-connector-nats | P2 |
| MQTT 단독(백본 없음) | Mosquitto 2.1.2 | EPL-2.0 | §3 | 직접 시험 — 재처리(E6)·소비자 다운 보관을 실측(재생 불가가 문헌상 약점) | R02 §1-b | P2 |
| Apache Pulsar 4.0 LTS | 4.0.13 (2026-08-03), 보안 지원 2027-10-21 | Apache-2.0 | `apachepulsar/pulsar` | 직접 시험(활성 지원은 2026-10-21 종료, 보안 패치 기준 통과) | https://endoflife.date/apache-pulsar | P3 |
| AutoMQ | 1.7.4 (2026-08-29) | Apache-2.0(오픈소스판; UI·RBAC·저지연 WAL은 BYOC 상용 → 미사용) | `automqinc/automq` | 직접 시험. S3 호환 저장소(MinIO 등) 필요 — 그 저장소의 관문은 별도 확인 | https://docs.automq.com/automq/what-is-automq/licensing | P3 |
| Tansu | 0.6.0 (2026-03-13) | Apache-2.0 | ghcr 이미지 **[미확인]** | 관문 미결(이미지), 1.0 이전 | https://github.com/tansu-io/tansu/releases | P3 |
| Apache Iggy | 0.9.0 (2026-09-18) | Apache-2.0 | `apache/iggy` | 직접 시험. Kafka 비호환, Telegraf·Flink 연동 [미확인] → ② | https://iggy.apache.org/blogs/2026/09/21/release-0.9.0/ | P3 |
| Apache RocketMQ | 5.5.0 (2026-05-04 이미지) | Apache-2.0 | `apache/rocketmq` | 직접 시험(Telegraf 연동 공백 [미확인]) | https://hub.docker.com/r/apache/rocketmq/tags | P3 |
| RabbitMQ Streams [묶음 RMQ] | 4.3.6 (2026-09-14) | MPL-2.0 | `rabbitmq` | 직접 시험(Flink 공식 커넥터 없음 [미확인]) | https://github.com/rabbitmq/rabbitmq-server/releases | P3 |
| Apache Fluss | 1.0.0 (2026-09-22) | Apache-2.0 | `apache/fluss` | 직접 시험(Flink 내부 저장 용도만, Telegraf 직결 불가) | https://fluss.apache.org/blog/apache-fluss-graduates-to-top-level-project/ | P3 |
| Pulsar 5.0 | 5.0.0-M2 (2026-09-18, 마일스톤) | Apache-2.0 | `5.0.0-M2` | 보류 — 정식판 없음(정식 출시 시 편입) | https://pulsar.apache.org/contribute/release-policy/ | — |
| Kafka 3.9 최신 패치 | 3.9.2 (2026-02-21) | Apache-2.0 | `apache/kafka` | **① 관문 제외** — 종료 2027-02-19 | https://endoflife.date/apache-kafka | — |
| Kafka 4.0 | 4.0.2 (2026-03-18) | Apache-2.0 | `apache/kafka` | **① 관문 제외** — 종료 2027-06-11 | 위와 같음 | — |
| Pulsar 4.2 | 4.2.4 (2026-08-03) | Apache-2.0 | `apachepulsar/pulsar` | **① 관문 제외** — 지원 종료 2026-09-24 | https://endoflife.date/apache-pulsar | — |
| Redpanda 브로커 | — | **BSL** | — | **① 관문 제외**(기존 결정) | https://github.com/redpanda-data/redpanda/blob/dev/licenses/bsl.md | — |
| Bufstream | — | **상용**(쓰기 GiB당 과금) | — | **① 관문 제외** | https://buf.build/pricing | — |
| WarpStream | — | **독점**(벤더 관리 제어평면) | — | **① 관문 제외** | https://www.automq.com/blog/warpstream-after-confluent-acquisition-what-changed | — |

## 6. 시계열 저장

V1: InfluxDB **2.7**(`influxdb:2.7` 마이너 태그) + 알람·업무 PostgreSQL 17(`ai-work-db`).
강제 교체: **InfluxDB 2.7 대상(확정)** — v2는 "현재·직전 마이너만 지원" → 2.9·2.8만 지원, 2.7 보안 패치 없음(R03 §0, https://docs.influxdata.com/influxdb/v2/reference/release-notes/supported-release/). PostgreSQL 17은 2029-11까지 지원 → 대상 아님(R03 §0의 "V1 PG 버전 [미확인]"은 V1_INVENTORY로 해소: `postgres:17`, EdgeX 내부 16.3).
시험 순서: ② 12태그 적재·조회, 72시간 초과 이력 조회(F05), 화면값=이력값(E7) → ③ 적재 지연·조회 지연·디스크·메모리 → ④ R06(DB 다운 5분), R08, R09.

| 후보 | 버전(날짜) | 라이선스 | 이미지 | 분류 | 근거(URL) | 우선순위 |
|---|---|---|---|---|---|---|
| **InfluxDB 2.9** (같은 제품 최신) | 2.9.1 (Docker 2026-09-19) | MIT | `influxdb:2.9.1` | 직접 시험. 2.9.0부터 토큰 해시 저장(원문 토큰 복구 불가) — 이전 절차 확인 | https://docs.influxdata.com/influxdb/v2/reference/release-notes/influxdb/ | **P1(강제 교체)** |
| InfluxDB 3 Core | 3.11.5 (2026-09-17) | MIT/Apache-2.0 | `influxdb:3-core` | 직접 시험. 쿼리당 Parquet 432파일 한도(≈72h) → F05에서 실측. HA는 Enterprise(미사용) | https://docs.influxdata.com/influxdb3/core/ · https://github.com/influxdata/influxdb/pull/25890 | P2 |
| TimescaleDB Apache판 [묶음 PG] | 2.30.1 (2026-09-17) | Apache-2.0 (`-oss` 태그만) | `timescale/timescaledb:2.30.1-pg18-oss` | 직접 시험. hypertable·`drop_chunks`·`time_bucket`만, 보존은 `pg_cron` 등으로 | https://www.tigerdata.com/docs/get-started/choose-your-path/timescaledb-editions | **P1(패턴 P-3→2)** |
| PostgreSQL 18 + pg_partman [묶음 PG] | PG 18.6 / pg_partman 5.5.0 (2026-07-22) | PostgreSQL License | `postgres:18` | 직접 시험 | https://github.com/pgpartman/pg_partman/releases · https://endoflife.date/postgresql | P1 |
| QuestDB | 10.0.1 (2026-08-24) | Apache-2.0 | `questdb/questdb:10.0.1` | 직접 시험(RBAC·TLS·HA는 Enterprise, 미사용) | https://questdb.com/docs/guides/architecture/security/ | P2 |
| VictoriaMetrics single [묶음 VM] | v1.153.0 (2026-09-25) | Apache-2.0 | `victoriametrics/victoria-metrics:v1.153.0` | 직접 시험(다운샘플링·다중 보존·Kafka 연동은 Enterprise, 미사용). 운영 감시 겸용 | https://docs.victoriametrics.com/victoriametrics/enterprise/ | P2 |
| Apache IoTDB | 2.0.11 (2026-09-14) | Apache-2.0 | `apache/iotdb:2.0.11-standalone` | 직접 시험(OSS 권한 범위 [미확인]) | https://iotdb.apache.org/UserGuide/latest-Table/Deployment-and-Maintenance/Docker-Deployment_apache.html | P2 |
| GreptimeDB | v1.2.1 (2026-09-16) | Apache-2.0 (open-core) | `greptime/greptimedb:v1.2.1` | 직접 시험(RBAC·LDAP·감사는 Enterprise, 미사용) | https://greptime.com/product/enterprise | P2 |
| TDengine TSDB-OSS | 3.4.2.8 (2026-08-31) | **AGPL-3.0 ⚠제품화 시 주의** | `tdengine/tsdb:3.4.2.8` | 직접 시험(taosX·RBAC 등은 Enterprise, 미사용) | https://tdengine.com/feature-comparison/ | P3 |
| CrateDB | 6.4.5 (2026-09-16) | Apache-2.0 | `crate/crate:6.4.5` | 직접 시험 | https://cratedb.com/blog/farewell-to-the-cratedb-enterprise-license-faq | P3 |
| ClickHouse | 26.8 LTS (2026-08-27) | Apache-2.0 | `clickhouse/clickhouse-server:26.8` | 직접 시험. LTS 1년 → 26.8은 2027-08 전후 종료 가능성, 다음 LTS 추종 [미확인] | https://endoflife.date/clickhouse | P3 |
| VictoriaLogs (알람·이벤트 로그) | v1.51.1 (2026-08-18) | Apache-2.0 | `victoriametrics/victoria-logs:v1.51.1` | 직접 시험(보조 저장) | https://github.com/VictoriaMetrics/VictoriaLogs/releases | P3 |
| InfluxDB 3 Enterprise | — | **상용** | — | **① 관문 제외**(기존 결정) | https://docs.influxdata.com/influxdb3/core/ | — |
| TimescaleDB TSL 기능(압축·연속집계·보존정책 등) | — | **TSL** | — | **① 관문 제외**(기존 결정) | https://www.tigerdata.com/docs/get-started/choose-your-path/timescaledb-editions | — |
| OpenTSDB | 2.4.1 (2021-09-02) | LGPL-2.1+ | 2023-11 스냅숏 | **① 관문 제외** — 유지보수 모드, 4년+ 정식 릴리스 없음 | https://opentsdb.net/faq.html | — |
| Machbase Neo | [미확인] | 독자 약관(무라이선스 = 평가 전용) | [미확인] | **① 관문 제외**(약관) | https://docs.machbase.com/dbms/install/license/ | — |

## 7. 알람 표시·상태 (ISA-18.2)

V1: Telegraf#3 → EMQX → FUXA 표시, 알람 **상태 관리 없음**(E10 공백). 사건 등록은 `ai-alarm-worker` → PostgreSQL.
강제 교체: 해당 없음(부재 기능 → 개선 항목).
시험 순서: ② 발생→표시→확인(ack)→복귀, 셸빙·만료가 상태도와 일치(E10, F03·F04) → ③ 알람→화면 지연 p95(E1) → ④ R01(브로커 정지 중 표시), R06, R07(DB 다운 중 상태 변경 fail-closed).

| 후보 | 버전(날짜) | 라이선스 | 이미지 | 분류 | 근거(URL) | 우선순위 |
|---|---|---|---|---|---|---|
| ISA-18.2 상태 테이블(PostgreSQL) + API 트랜잭션 | PostgreSQL 18.6 / 17 | PostgreSQL License | `postgres:18` | 직접 시험 — 알람 수명주기는 V1도 직접 짠 업무 로직 범위(QUESTIONS §1 허용). Alerta `isa_18_2.py`를 참조 설계로 | https://github.com/alerta/alerta/blob/master/alerta/models/alarms/isa_18_2.py | **P1** |
| Vue MQTT over WebSocket 직접 구독(표시) | Mosquitto 2.1.2 내장 WS | EPL-2.0 | §3 | 직접 시험(패턴 P-HMI). 읽기 전용 계정·토픽 ACL·`websockets_origin` | https://mosquitto.org/blog/2026/01/version-2-1-0-released/ | P1 |
| Alerta [묶음 Alerta] | 9.1.0 (Docker 2026-03-28) | Apache-2.0 | `alerta/alerta-web:9.1.0` | 직접 시험. ISA-18.2 모델 내장(NORM·UNACK·ACKED·RTNUN·SHLVD·DSUPR·OOSRV). 상류 유지 위험 기록 | https://docs.alerta.io/ | P2 |
| alerta-ng [묶음 Alerta] | 9.1 계열 (날짜 [미확인]) | Apache-2.0 | **[미확인]** | 관문 미결(이미지) | https://github.com/ospo-ionik/alerta-ng | P3 |
| ThingsBoard CE 알람 | 4.3.1.6 (`tb-node` 2026-09-28) | Apache-2.0 (PE 상용 미사용) | `thingsboard/tb-node` | 직접 시험(ACK/CLEAR, shelve 없음 — ISA-18.2 부분집합). §9 HMI와 한 벤치 | https://thingsboard.io/docs/user-guide/alarms/ | P2 |
| Keep | v0.54.3 (2026-09-09 추정) | MIT 코어 + 상용 `ee/`(미사용) | GHCR/Artifact Registry, 정확한 경로 **[미확인]** | 직접 시험 — 이미지 경로 확인 필요. ISA-18.2 상태 없음 | https://github.com/keephq/keep/blob/main/LICENSE | P3 |
| Grafana Alerting (OSS) | Grafana 13.2 | **AGPL-3.0 ⚠** | `grafana/grafana:13.2.2` | 직접 시험(탐지·통지만, ack 없음) | https://github.com/grafana/grafana/issues/24762 | P3 |
| Alertmanager (통지 계층) | v0.34.1 | Apache-2.0 | `prom/alertmanager:v0.34.1` | 직접 시험(silence만) | https://github.com/prometheus/alertmanager/releases | P3 |
| Grafana OnCall OSS | 최종판 | AGPL-3.0 | — | **① 관문 제외** — 2025-03-11 유지보수 모드 → **2026-03-24 아카이브** | https://grafana.com/docs/oncall/latest/set-up/open-source/ | — |

## 8. 운영 감시

V1: Prometheus **v3.1.0** + Alertmanager **v0.28.0** + Grafana **11.4.0** + cAdvisor **v0.49.1** + kafka-exporter(`latest`).
강제 교체:
- **Prometheus 3.1.0 대상(확정)** — 일반 마이너는 6주 주기로 지원, 3.x 첫 LTS(3.5)도 2026-07-31 종료. 3.1은 LTS가 아니고 이미 지원 밖(R03 §0, https://endoflife.date/prometheus · https://prometheus.io/docs/introduction/release-cycle/).
- **Alertmanager 0.28.0 [미확인]** — 0.x, LTS 없음, 최신 0.34.1. 구버전 패치 정책 미확인 → §12.
- **Grafana 11.4.0 [미확인]** — 최신 13.2.2. 11.x 보안 패치 지속 여부 미확인 → §12.
- **cAdvisor v0.49.1 · kafka-exporter [미확인]** — 딥리서치 범위 밖, 최신판·지원 상태 미조사 → §12.
시험 순서: ② 컨테이너 kill·탐지기 정지 둘 다 탐지(E11, F10), L4-11 지표 수집 → ③ 자원·스크레이프 지연 → ④ R09.

| 후보 | 버전(날짜) | 라이선스 | 이미지 | 분류 | 근거(URL) | 우선순위 |
|---|---|---|---|---|---|---|
| **Prometheus 3.x** (같은 제품 최신) | 3.15 (2026-09-25) / LTS 3.13 (2026-07-01, 지원 2027-07-31) | Apache-2.0 | `prom/prometheus:v3.15.0` | 직접 시험. LTS 3.13도 2027-07-31 종료 → 다음 LTS 추종(롤링 해석, §12-0) | https://endoflife.date/prometheus | **P1(강제 교체)** |
| Alertmanager (같은 제품 최신) | v0.34.1 (2026-09-17) | Apache-2.0 | `prom/alertmanager:v0.34.1` | 직접 시험 | https://github.com/prometheus/alertmanager/releases | P1 |
| Grafana (같은 제품 최신) | 13.2.2 (2026-09-15) | **AGPL-3.0 ⚠** | `grafana/grafana:13.2.2` (`grafana-oss`는 13.0.2에서 멈춤) | 직접 시험(RBAC·리포팅은 Enterprise, 미사용) | https://grafana.com/docs/learning-hub/which-grafana/02-understand-your-options/04-grafana-enterprise/ | P1 |
| VictoriaMetrics + vmalert [묶음 VM] | v1.153.0 | Apache-2.0 | `victoriametrics/victoria-metrics`, `victoriametrics/vmalert` | 직접 시험(멀티테넌트 vmalert는 Enterprise, 미사용) | https://docs.victoriametrics.com/victoriametrics/enterprise/ | P2 |
| Thanos [묶음 Prom-LTS] | v0.42.4 (2026-07-30 추정) | Apache-2.0 | `thanosio/thanos` | 직접 시험(장기 보관) | https://github.com/thanos-io/thanos/releases | P3 |
| Grafana Mimir [묶음 Prom-LTS] | 3.2.1 (2026-09-10) | **AGPL-3.0 ⚠** | `grafana/mimir:3.2.1` | 직접 시험 | https://github.com/grafana/mimir/releases | P3 |
| M3 [묶음 Prom-LTS] | v1.6.0 (2026-09-25 추정) | Apache-2.0 | 이미지명 **[미확인]** | 관문 미결(이미지) | https://github.com/m3db/m3/releases | P3 |
| GreptimeDB (PromQL) | v1.2.1 | Apache-2.0 | §6 | 직접 시험(§6과 한 벤치) | §6 | P3 |
| Perses | v0.55.0-beta.2 (2026-09-18), 정식 [미확인] | Apache-2.0 | `persesdev/perses` | 직접 시험(대시보드-as-code, 1.0 전) | https://github.com/perses/perses/releases | P3 |

## 9. HMI

V1: FUXA `latest` = **1.3.4-2898**(2026-09-09 이미지). 이미 보안 기준선(1.3.4) 충족 → **강제 교체 아님**. 단 ① 기본 보안: `secureEnabled=true`·Node-RED 통합 비활성·태그 고정이 최소선(R03 §0 판정, CVE-2026-25752 무인증 태그 쓰기 등 전례).
시험 순서: ② 운전 화면 표시·C1 조작·알람 표시·확인(F03·F13), 인증 켠 상태(E12) → ③ 화면 갱신 지연·자원 → ④ R01(브로커 정지 중 운전 화면), R11.

| 후보 | 버전(날짜) | 라이선스 | 이미지 | 분류 | 근거(URL) | 우선순위 |
|---|---|---|---|---|---|---|
| **FUXA 1.3.4 태그 고정 + 보안 설정** (같은 제품 최신) | 1.3.4 (2026-08-12, 이미지 2026-08-13) | MIT | `frangoteam/fuxa:1.3.4` | 직접 시험(위생 조치 겸 기준선) | https://github.com/frangoteam/FUXA/releases · https://github.com/frangoteam/FUXA/security/advisories | **P1** |
| FUXA MQTT 구독(폴링 대신 UNS 토픽) | 1.3.4 | MIT | 위와 같음 | 직접 시험 — 구독으로 직접 폴링을 대체할 수 있는지 [미확인] → ②(패턴 P-UNS) | R01 §4-A | P1 |
| Vue(`ai-web`) MQTT over WebSocket 직접 구독 | — | (V1 자체 화면) | V1 빌드 | 직접 시험(§7과 한 벤치, 쓰기는 명령 게이트웨이로만) | R03 §6-B | P1 |
| Node-RED 5 + Dashboard 2.0 | 5.0.4 (2026-07-30) / Dashboard 2 v1.32.0 (2026-09-24 추정) | Apache-2.0 | `nodered/node-red`(5.x 태그 [미확인]) · `flowfuse/node-red:latest-5.0.x` | 직접 시험 | https://flowfuse.com/blog/2026/06/node-red-5-on-flowfuse/ · https://github.com/FlowFuse/node-red-dashboard/releases | P2 |
| ThingsBoard CE | 4.3.1.6 (2026-09-28) | Apache-2.0 | `thingsboard/tb-node` | 직접 시험(알람 ACK/CLEAR 내장) | https://github.com/thingsboard/thingsboard/releases | P2 |
| OpenRemote | 1.31.1 (2026-09-28) | **AGPL-3.0 ⚠** | `openremote/manager:1.31.1` | 직접 시험 | https://github.com/openremote/openremote/releases | P3 |
| Scada-LTS | v2.8.0 (Docker 2025-10-17) | GPL-2.0 ⚠ (저장소 LICENSE [미확인]) | `scadalts/scadalts:v2.8.0` | 직접 시험 — 라이선스 원문 확인 필요 | https://hub.docker.com/r/scadalts/scadalts | P3 |
| Apache StreamPipes (대시보드) | 0.98.0 | Apache-2.0 | `apachestreampipes/ui` | 직접 시험 — 관리자 탈취 취약점 CVE·수정판 [미확인] → ① 기본 보안 재확인 | https://www.techrepublic.com/article/news-apache-streampipes-flaw-lets-anyone-become-admin/ | P3 |
| Grafana + Business Forms | 최신 [미확인] | Apache-2.0(플러그인) / Grafana AGPL ⚠ | Grafana 플러그인 | 직접 시험(읽기 화면 + 제한된 명령) | https://github.com/grafana/business-forms | P3 |
| ioBroker | js-controller 7.2.3 (2026-09-19), Docker v11.1.0 (2026-09-27) | MIT | `iobroker/iobroker` | 직접 시험 | https://github.com/buanet/ioBroker.docker | P3 |
| PyScada | 릴리스 [미확인] | **AGPL-3.0 ⚠** | **[미확인]** | 관문 미결(이미지) | https://github.com/pyscada/PyScada | P3 |
| Rapid SCADA | 6.5.0 (2026-09-07) | Apache-2.0 (Enterprise 상용) | **공식 이미지 없음** | **① 관문 제외**(컨테이너 없음) | https://github.com/RapidScada/scada-v6/issues/58 | — |
| OpenSCADA | 0.9 LTS | GPL-2.0 | **공식 이미지 없음**(커뮤니티 이미지뿐) | **① 관문 제외**(컨테이너 없음) | https://hub.docker.com/r/dudanov/openscada | — |
| Ignition | — | **상용**(Maker 비상업) | — | **① 관문 제외**(기존 결정) | — | — |
| Tago.io | — | **상용 SaaS** | — | **① 관문 제외**(상용) | — | — |

## 10. 그래프 DB / AI 검색 (임베딩 모델 포함)

V1: Neo4j **5.26-community**(LTS 지원 2028-06-06 → **강제 교체 아님**. 단 LTS 일정은 Enterprise 기준, Community 수정 보장 없음 — R03 §0). 에이전트 LangGraph + 외부 LiteLLM 프록시(버전 미확인, QUESTIONS Q4). 임베딩: V1 설정 기본값 `openai:text-embedding-3-small`(API)·Ollama `qwen3-embedding`, 실제 사용 경로 [미확인]. 실험 브랜치 V2 코드는 Ollama `bge-m3`.
고정 조건(QUESTIONS §1 AI 고정·사용자 지시): 그래프 DB 필수, **Neo4j 유지** — 다른 그래프 DB는 참고 측정만. 비교는 V1 대 V2 에이전트(`ontology/v2/PROTOCOL.md`, #68).
시험 순서: ② 적재·벡터 인덱스 생성·CQ01·CQ02 답 동일(F07) → ③ 검색 Recall@k·MRR(사람 라벨 절), CPU 임베딩 지연·메모리 → ④ DB 재시작 후 인덱스 유지, R09.

**10-a. 그래프 DB**

| 후보 | 버전(날짜) | 라이선스 | 이미지 | 분류 | 근거(URL) | 우선순위 |
|---|---|---|---|---|---|---|
| **Neo4j 5.26 LTS CE 최신 패치** (같은 제품 최신 지원) | 5.26.31 (2026-09-21) | **GPLv3 ⚠** | `neo4j:5.26-community` | 직접 시험(기준선 유지 경로) | https://endoflife.date/neo4j | **P1** |
| Neo4j 2026.x CE (CalVer) | 2026.09.0 (2026-09-16/21) | **GPLv3 ⚠** | `neo4j:2026.09-community`(태그명 [미확인]) | 직접 시험. 매월 최신만 지원(마이너 추종). 새 벡터 기능 다수는 Enterprise 전용 | https://neo4j.com/docs/upgrade-migration-guide/current/version-2025-2026/ | P2 |
| APOC Core | 2026.09.0 / 5.26.x | Apache-2.0 | `NEO4J_PLUGINS='["apoc"]'` | 직접 시험(로더 편의) | https://github.com/neo4j/apoc/releases/tag/2026.09.0 | P3 |
| GDS Community | 2026.09.0 / 5.26용 2.x | 공개분 GPLv3, 배포 바이너리 공개+비공개 혼합(CE 무료) | 플러그인 | 직접 시험(선택) — 배포판 약관 전문 [미확인] | https://github.com/neo4j/graph-data-science/blob/master/LICENSE.txt | P3 |
| neosemantics (n10s) | 5.26.0 / 2025.06.1 | Apache-2.0 | 플러그인 jar | 직접 시험(5.26 조합만, 2026.x 호환 [미확인]) | https://github.com/neo4j-labs/neosemantics/releases | P3 |
| Apache AGE (PostgreSQL 확장) | 1.6.0 (2026-01-21), PG18용 1.7.0 | Apache-2.0 | `apache/age` | 참고 측정(사용자 지시로 Neo4j 유지, 패턴 P-3→2′) | https://github.com/apache/age/releases | P3 |
| ArcadeDB · JanusGraph · NebulaGraph CE · HugeGraph · Dgraph · TerminusDB | 26.8.1 / 1.1.0 / 3.8.x[미확인] / [미확인] / v25 / 12.0.7 | Apache-2.0 | 각 공식 이미지 | 참고 측정(Neo4j 유지 지시). 관문 탈락 사실은 없음 | R04 §1-2 | — |
| Oxigraph · Apache Jena Fuseki | 0.5.11 / 6.2.0 (2026-07-27) | MIT/Apache-2.0 · Apache-2.0 | ghcr / Fuseki는 **공식 이미지 없음** | 온톨로지 정합성 검증 보조(운용 DB 아님). Fuseki는 컨테이너 없음 사실 기록 | https://jena.apache.org/documentation/fuseki2/ | — |
| Memgraph Community | — | **BSL 1.1** | `memgraph/memgraph` | **① 관문 제외**(라이선스) | https://flur.ee/blog/neo4j-alternatives | — |
| FalkorDB | — | **SSPLv1** | `falkordb/falkordb` | **① 관문 제외**(라이선스) | https://docs.falkordb.com/References/license.html | — |
| Kuzu | 0.11.3 (2025-10-10) | MIT | 임베디드 | **① 관문 제외** — 2025-10-10 저장소 아카이브 | https://gdotv.com/blog/kuzu-legacy-embedded-graph-database-landscape/ | — |

**10-b. 검색·에이전트 라이브러리**

| 후보 | 버전(날짜) | 라이선스 | 이미지 | 분류 | 근거(URL) | 우선순위 |
|---|---|---|---|---|---|---|
| neo4j-graphrag (`VectorCypherRetriever`) | 1.21.0 (2026-09-23) | Apache-2.0 | pip | 직접 시험(LLM 추출 없이 벡터→Cypher 확장) | https://pypi.org/project/neo4j-graphrag/ | **P1** |
| langchain-neo4j | 0.10.0 (2026-06-10) | MIT | pip | 직접 시험 | https://pypi.org/pypi/langchain-neo4j/json | P2 |
| LangGraph (V1 유지, 같은 제품 최신) | 1.2.12 (2026-09-21) | MIT | pip | 직접 시험(도구 추가만) | https://pypi.org/pypi/langgraph/json | P1 |
| LiteLLM (V1 유지, 같은 제품 최신) | 1.103.0 (2026-09-27) | MIT (`enterprise/` 상용 미사용) | `ghcr.io/berriai/litellm` | 직접 시험 — V1 프록시 버전 확인(Q4) | https://pypi.org/pypi/litellm/json | P1 |
| langchain-mcp-adapters · neo4j/mcp | 0.3.2 (2026-08-06) / v1.6.0 (2026-09-10) | MIT / **GPLv3 ⚠** | pip / Dockerfile(공식 이미지명 [미확인]) | 직접 시험(MCP 채택 시, read 전용 계정) | https://github.com/neo4j/mcp | P3 |
| LlamaIndex PropertyGraphIndex | core 0.14.25 (2026-09-21) | MIT | pip | 직접 시험(스택 중복, 우선순위 낮음) | https://pypi.org/pypi/llama-index-core/json | P3 |
| MS GraphRAG · LightRAG · HippoRAG 2 · nano-graphrag | 3.2.0 / 1.5.7 / 2.0.0a4 / 0.0.8.2 | MIT | pip | 직접 시험(LLM 추출 필수 — 비용은 LLM API 예외 범위. GraphRAG는 유지보수 모드) | R04 §3 | P3 |
| fast-graphrag | 0.0.5 (2025-04) | **[미확인]** | pip | 관문 미결(라이선스) | R04 §3 | P3 |
| mcp-neo4j-cypher (Labs) | 0.6.0 (2026-04-10) | MIT | 컨테이너 안내 | 직접 시험(공식 neo4j/mcp와 한 묶음) | https://github.com/neo4j-contrib/mcp-neo4j | P3 |

**10-c. 로컬 CPU 임베딩·리랭커**

| 후보 | 버전(크기) | 라이선스 | 이미지 | 분류 | 근거(URL) | 우선순위 |
|---|---|---|---|---|---|---|
| V1 임베딩(`text-embedding-3-small` API 또는 Ollama `qwen3-embedding`) | — | API 약관 / Apache-2.0 | 외부 API / Ollama | 기준선 — 실제 사용 경로 [미확인] → §12 | V1 `settings.py` | P1 |
| BAAI/bge-m3 [묶음 bge-m3] | 568M | MIT | Ollama·sentence-transformers | 직접 시험(기준 후보, 1024차원 ≤ CE 2048) | https://huggingface.co/BAAI/bge-m3 | **P1** |
| nlpai-lab/KURE-v1 [묶음 bge-m3] | 567.8M | MIT | 위와 같음 | 직접 시험(한국어 특화) | https://huggingface.co/nlpai-lab/KURE-v1 | P1 |
| dragonkue/BGE-m3-ko [묶음 bge-m3] | 567.8M | Apache-2.0 | 위와 같음 | 직접 시험 | https://huggingface.co/dragonkue/BGE-m3-ko | P2 |
| nlpai-lab/KoE5 [묶음 e5] | 559.9M | MIT | 위와 같음 | 직접 시험 | https://huggingface.co/nlpai-lab/KoE5 | P2 |
| multilingual-e5 large / small / large-instruct [묶음 e5] | 559.9M / 117.7M / 559.9M | MIT | 위와 같음 | 직접 시험(small = 저사양) | https://huggingface.co/intfloat/multilingual-e5-small | P2 |
| Qwen3-Embedding-0.6B | 595.8M | Apache-2.0 | 위와 같음 | 직접 시험 | https://huggingface.co/Qwen/Qwen3-Embedding-0.6B | P2 |
| Snowflake arctic-embed-l-v2.0 | 567.8M | Apache-2.0 | 위와 같음 | 직접 시험 | https://huggingface.co/Snowflake/snowflake-arctic-embed-l-v2.0 | P3 |
| paraphrase-multilingual-MiniLM-L12-v2 | 117.7M | Apache-2.0 | 위와 같음 | 직접 시험(하한 기준선) | https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 | P3 |
| bge-reranker-v2-m3 [묶음 rerank] | 567.8M | Apache-2.0 | 위와 같음 | 직접 시험 | https://huggingface.co/BAAI/bge-reranker-v2-m3 | P2 |
| bge-reranker-v2-m3-ko [묶음 rerank] | 567.8M | Apache-2.0 | 위와 같음 | 직접 시험 | https://huggingface.co/dragonkue/bge-reranker-v2-m3-ko | P2 |
| Qwen3-Reranker-0.6B | 595.8M | Apache-2.0 | 위와 같음 | 직접 시험 | https://huggingface.co/Qwen/Qwen3-Reranker-0.6B | P3 |
| google/embeddinggemma-300m | 302.9M | **Gemma 이용약관**(비OSI) | — | **① 관문 제외**(라이선스) | https://huggingface.co/google/embeddinggemma-300m | — |
| jina-embeddings-v3 | 572.3M | **CC-BY-NC-4.0**(비상업) | — | **① 관문 제외**(라이선스) | https://huggingface.co/jinaai/jina-embeddings-v3 | — |
| jina-reranker-v2-base-multilingual | 278.4M | **CC-BY-NC-4.0** | — | **① 관문 제외**(라이선스) | https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual | — |

실행기: sentence-transformers 6.1.0(Apache-2.0), FlagEmbedding 1.4.2(라이선스 [미확인]), Ollama(딥리서치 미조사 [미확인]). 온톨로지 스키마 재료(IOF-Maint MIT, UWA FMEA MIT)는 부품이 아니라 데이터 — ISO 14224 원문은 유료라 코드 용어만 참조.

---

## 11. 구조 패턴 후보 (구조 축 조립용)

구조 재설계(`QUESTIONS.md` §1 결정 순서 2)에서 쓰는 경로 단축안 — 구조를 먼저 정하고 남는 층의 부품은 §1~10 에서 고른다(#121). 각 패턴은 **① 통과 부품으로만** 구성하고, 판정은 `STRUCTURE.md`(F01~F14 기능 보존, E1~E12)와 `ROBUSTNESS.md`로 한다. "없애는 것"은 V1의 중복·되돌아가는 경로 기준.

| # | 패턴 | 없애는 V1 중복·루프 | 구현 후보(① 통과) | 확인할 점 | 근거 | 우선순위 |
|---|---|---|---|---|---|---|
| P-UNS | 수집기가 MQTT(UNS)에 바로 발행 + FUXA가 같은 토픽 구독 | EdgeX 10컨테이너, **FUXA·EdgeX 이중 폴링** | Telegraf modbus→mqtt, benthos-umh, Neuron, Node-RED, HiveMQ Edge | FUXA MQTT 구독 가능 여부 [미확인], R01에서 운전 화면이 브로커에 종속됨 | R01 §4-A | **P1** |
| P-C | 브로커 내장 Kafka 브리지 | **Telegraf#1(MQTT→Kafka)** | RMQTT(Kafka egress), TBMQ(Integration Executor) | Mosquitto OSS엔 없음(Pro 전용), EMQX는 BSL | R01 §4-C | P1 |
| P-D | Kafka Connect MQTT source | Telegraf#1 | Lenses Stream Reactor | Kafka ≥4.0 | R01 §4-D | P2 |
| P-E | 파이프 도구 하나로 여러 경로 | **Telegraf ×3 → 1** | Telegraf 1대, Redpanda Connect(Apache), Bento, benthos-umh | 경로 간 장애 격리 | R01 §4-E | P1 |
| P-F | 수집기가 DB에 직접 기록 | Kafka→Telegraf#2→InfluxDB 구간 | Telegraf modbus→influxdb_v2/postgresql, Bento·benthos-umh sql | Kafka를 재처리 버퍼로 둘지(E6) | R01 §4-F | P2 |
| P-HMI | HMI(Vue)가 브로커 직접 구독(MQTT over WebSocket) | **알람 되돌림 Kafka→Telegraf#3→MQTT→FUXA(약 8홉 → 3홉)** | Mosquitto 2.1 내장 WS + Dynamic Security ACL | 브라우저 자격증명 노출 → 읽기 전용 계정·`websockets_origin`. 쓰기는 브로커 직결 금지 | R03 §6-B | **P1** |
| P-3→2 | 시계열을 PostgreSQL로(저장소 3 → 2) | **InfluxDB + Telegraf#2→Influx 경로, 백업 대상 1개** | TimescaleDB Apache판, PG18+pg_partman | 압축·연속집계 없음 → `pg_cron`+`drop_chunks`, 장기 조회 성능 실측 | R03 §6-A | P1 |
| P-3→2′ | 그래프까지 PostgreSQL(AGE) | Neo4j | Apache AGE | **사용자 지시로 Neo4j 유지 → 참고 측정만** | R03 §6-A′ | — |
| P-ISA | 알람 수명주기를 DB에(또는 기성 알람 서버) | **화면·DB·Alertmanager 알람 상태 불일치**, 상태 공백 | PostgreSQL 상태 테이블 + LISTEN/NOTIFY·MQTT, Alerta, ThingsBoard | 셸빙 만료·억제·재통지 설계 | R03 §6-C·C′ | P1 |
| P-CMD | 단일 명령 게이트웨이 | **설비 쓰기 경로 3개(FUXA·EdgeX core-command·AI) → 1** | V1 `ai-knowledge` 조치 API 확장(권한·감사·인터록) | FUXA 자체 쓰기·EdgeX command 비활성 필요, G0~G8 | R03 §6-D · V1_FACTS §6 | P1 |
| P-MON | 운영 감시는 인프라 전용 | 공정 알람과 인프라 알림 혼재 | Prometheus+Alertmanager(공정 알람은 P-ISA) | 장기 보관 필요 시 VM/Thanos/Mimir | R03 §6-E | P2 |
| P-EDGE | eKuiper 엣지 규칙(+MQTT 직결) | Kafka·Flink(단순 규칙 한정) 또는 **Python 알람 워커** | eKuiper(SQL 규칙·ONNX 플러그인) | MQTT 재생 불가, 싱크 중복 가능, CEP 문법 없음 | R02 §4-1 · R01 §4-G | P1 |
| P-HYB | 하이브리드: 단순 임계는 eKuiper, CEP·ONNX는 Flink 2.x(HA) | Flink 잡 수·부하 | eKuiper + Flink 2.2/2.3 + ZK | 두 엔진 운영 | R02 §4-6 | P2 |
| P-SDB | 스트림 DB가 MQTT 직독 | 백본 + 탐지 엔진 | RisingWave(MQTT 소스), Arroyo | MQTT 소스 preview·재생 불가 | R02 §4-2 | P3 |
| P-LIB | 백본 유지·처리 경량화 | Flink 클러스터(JM/TM) | Kafka Streams, Quix Streams | CEP 직접 구현 | R02 §4-3 | P2 |
| P-NATS | 백본 경량 교체(MQTT+스트림 한 브로커) | 브로커 + Kafka 두 계층 | NATS JetStream(내장 MQTT) + Flink(Synadia 커넥터) | 커넥터 제3자·ALO | R02 §4-4 | P2 |
| P-EB | 수집기와 브로커 통합 | 수집기 + 브로커 | HiveMQ Edge | 저장 후 전달은 상용 → R02 실측 | R01 §4-B | P2 |
| P-TSDB-rule | 저장층 흡수(트리거·UDF) | 처리층 일부 | Apache IoTDB | 이벤트시간·CEP 표현력 [미확인] | R02 §4-5 | P3 |
| P-ALL | 산업 IoT 올인원 | 수집·처리·저장 분리 | Apache StreamPipes | ONNX·CEP 경로 [미확인] | R02 §4-7 | P3 |
| P-SPB | Sparkplug B 토픽·생사 판정 규격화 | (중복 제거보다 규격화) | Mosquitto 2.1 Sparkplug-aware 플러그인, benthos-umh | Tahu는 라이브러리(이미지 없음) | R01 §4-H | P3 |

---

## 12. 확인 필요 ([미확인] 재확인 목록 — 분류 확정 전)

**12-0. 규칙 해석(사람 확인):** 롤링 지원 제품(Flink 2.x·Telegraf·Prometheus·Neo4j CalVer·InfluxDB 3 Core·RabbitMQ·ClickHouse LTS)은 "마이너 추종" 조건으로 통과시켰다. 엄격 해석(현재 마이너 자체의 종료일이 12개월 안이면 제외)을 쓰면 이 제품들의 모든 버전이 탈락한다.

**12-1. 강제 교체·관문 날짜**
1. EdgeX 4.0 LTS 정확한 종료일(검색 요약 "2027-03", 원문 LTS 페이지 미확인) — 확정 시 V1 4.0.0 강제 교체 + 4.0.2 ① 관문 제외.
2. Flink 1.20 LTS 공식 종료일·연장 여부(FLIP-458 2년만 확인).
3. Alertmanager 0.28.0·Grafana 11.4.0 보안 패치 지속 여부.
4. cAdvisor v0.49.1·kafka-exporter(`latest`) 최신판·지원 상태(딥리서치 미조사).
5. Mosquitto 2.1 계열 공식 지원 기간. EdgeX 내부 Mosquitto 2.0.21 지원 여부(EdgeX 유지 시에만 의미).
6. ClickHouse 26.8 LTS 종료일과 다음 LTS 경로.

**12-2. 이미지·라이선스(관문 미결 → 확인되면 직접 시험, 아니면 제외)**
7. 이미지: Siddhi 러너, Tansu(ghcr), ActiveMQ Artemis 현행 배포 위치·Classic 공식 이미지, RobustMQ, Amlen 고정 태그, alerta-ng, Keep 레지스트리 경로, M3, PyScada, Stream Reactor 권장 Connect 런타임, Vector 현재 이미지명, neo4j/mcp 이미지, `neo4j:2026.09-community` 태그, Node-RED 5.x 태그, BifroMQ(R01·R02 기재 불일치), Neuron 2.14·2.15 이미지.
8. 라이선스: comqtt, fast-graphrag, FlagEmbedding, Scada-LTS LICENSE 원문, GDS 배포판 약관, Hazelcast 필요 기능의 Community License 해당 여부.

**12-3. ② 기동·기능에서 첫 항목으로 볼 것(관문 사실 아님, 기록용)**
9. Flink 2.3용 Kafka 커넥터, Telegraf 1.40 `kafka_consumer`의 Kafka 4.x 소비(#17570), FUXA MQTT 구독의 폴링 대체, ThingsBoard IoT Gateway의 일반 MQTT 출력, RisingWave MQTT 커넥터 무료 여부·MATCH_RECOGNIZE, Proton CEP·onnxruntime UDF, Kapacitor→PostgreSQL, BifroMQ 기본 인증/ACL, StreamPipes CVE 수정판, V1 임베딩 실제 사용 경로, LiteLLM 프록시 버전(Q4).
