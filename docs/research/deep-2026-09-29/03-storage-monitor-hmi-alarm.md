# 03 · 저장·모니터링·HMI·알람 계층 광역 조사 (2026-09-29 기준)

- 범위: V1의 시계열 저장(InfluxDB 2.7 + PostgreSQL + Neo4j), 모니터링(Prometheus·Alertmanager·Grafana), HMI(FUXA), 알람 처리(ISA-18.2 부재)
- 방법: 공식 문서·GitHub 릴리스/보안권고·Docker Hub 태그 API(2026-09-29 조회)·endoflife.date. docker 실행 없음, 성능은 판정하지 않음.
- 분류 규칙: **직접 시험 대상** = 문헌상 관문 통과(성능 추정으로 제외하지 않음). **① 관문 제외** = 라이선스·약관·EOL·공식 컨테이너 부재 사실이 출처로 확인된 경우만.
- 라이선스 표기: OSI 승인이 아니거나(BSL·SSPL·TSL·ELv2) 네트워크 카피레프트(AGPL)면 **⚠제품화 시 주의**.
- 날짜 주의: GitHub 릴리스 화면은 올해 날짜의 연도를 생략한다. 연도는 Docker Hub 태그 갱신일이나 권고일로 교차 확인했고, 못 한 것은 "추정"으로 적었다.

---

## 0 · V1 구성요소 최신 사실 (가장 먼저 볼 것)

| 구성요소 (V1) | 최신 버전(날짜) | 지원/EOL 사실 | V1에 미치는 영향 | 근거 URL |
|---|---|---|---|---|
| **InfluxDB 2.7** | 2.x 최신 **2.9.1** (Docker 태그 2026-09-19 갱신). 2.8.0, 2.9.0 존재 | v2는 "현재·직전 마이너만 지원" → **2.9·2.8만 지원, 2.7은 지원 종료**. v2 메이저 자체는 EOL 계획 없음 | 2.7 고정 시 보안 패치 없음. 2.9.0부터 토큰 해시 저장 기본(업그레이드 후 원문 토큰 복구 불가) | https://docs.influxdata.com/influxdb/v2/reference/release-notes/supported-release/ · https://docs.influxdata.com/influxdb/v2/reference/release-notes/influxdb/ · https://endoflife.date/influxdb |
| InfluxDB Docker `latest` 태그 | 2026-09-15부터 `influxdb:latest` → **InfluxDB 3 Core** | 공식 공지 | compose가 `influxdb:latest`면 다음 pull에서 메이저가 바뀜. 버전 태그 고정 필요 | 위 supported-release 문서 · Docker Hub `library/influxdb` 태그(`3-core`, `3.11.5-core` 확인) |
| PostgreSQL | 18.6 (18.x 현행), 17.11, 16.15. **19는 Beta 4(2026-09-24)**, GA는 2026-10 예정 | PG14 EOL **2026-11**(12개월 내), PG15 2027-11, PG16 2028-11, PG17 2029-11, PG18 2030-11 | V1이 PG14 이하면 즉시 교체 대상. V1 실제 버전은 [미확인] | https://endoflife.date/postgresql · https://www.postgresql.org/about/news/postgresql-19-beta-4-released-3386/ |
| **Neo4j 5.26 LTS** | 5.26.31 (2026-09-21) | LTS 지원 **2028-06-06까지**. 단 이 일정은 Enterprise 기준이며 Community 수정은 보장 안 됨 | 12개월 내 EOL 아님 | https://endoflife.date/neo4j · https://neo4j.com/blog/developer/neo4j-v5-lts-evolution/ |
| Neo4j 2025.x/2026.x (CalVer) | **2026.09.0** (2026-09-16), Docker `neo4j:community` 2026-09-26 갱신 | CalVer는 **최신 마이너만 지원**(매월 교체) | Community는 GPLv3. 5.26→2025.01+ 는 별도 마이그레이션 가이드 필요 | https://neo4j.com/docs/upgrade-migration-guide/current/version-2025-2026/ · https://hub.docker.com/_/neo4j |
| Prometheus | **3.15** (2026-09-25). LTS **3.13**(2026-07-01) 지원 2027-07-31 | 3.5 LTS는 2026-07-31 종료. 일반 마이너는 6주 주기 | 3.x 2.x 비호환 변경 확인 필요 | https://endoflife.date/prometheus · https://prometheus.io/docs/introduction/release-cycle/ |
| Alertmanager | **v0.34.1** (Docker 2026-09-17) | 0.x 계열, 별도 LTS 없음 | ack 개념 없음(silence·inhibit만) | https://hub.docker.com/r/prom/alertmanager · https://github.com/prometheus/alertmanager/releases |
| Grafana | **13.2.2** (2026-09-15). 13.0 출시 2026-04-21 | `grafana/grafana-oss` 이미지는 13.0.2(2026-06)에서 멈춤 → **`grafana/grafana` 사용** | OSS는 AGPLv3. RBAC·리포팅·SAML은 Enterprise | https://grafana.com/press/2026/04/21/grafana-labs-launches-grafana-13-at-grafanacon-2026-makes-open-observability-easier-to-run-at-scale/ · Docker Hub `grafana/grafana` |
| **FUXA 1.3.x** | **1.3.4** (GitHub 2026-08-12, Docker `frangoteam/fuxa:1.3.4` 2026-08-13). `latest` 2026-09-23 재빌드 | 단일 라인, LTS 없음. 2026년 보안권고 다수 | **1.3.3 미만은 High 권고 3건 해당**. 아래 표 참조 | https://github.com/frangoteam/FUXA/releases · https://github.com/frangoteam/FUXA/security/advisories |

### FUXA 보안권고 (CVE ↔ 수정 버전)

| CVE | 내용 | 영향 버전 | 수정 버전 | 근거 |
|---|---|---|---|---|
| CVE-2025-69970 | `secureEnabled` 기본 주석 처리 → 인증 꺼짐 | 1.2.7 | [미확인] (기본값 문제 — 설정으로 켜야 함) | https://github.com/advisories/GHSA-r5m2-fqcf-qrf7 |
| CVE-2025-69971 | 하드코딩 JWT 대체 비밀키 | [미확인] | 1.2.10 "JWT secret handling improved"와 대응 추정 | https://exploit-intel.com/vuln/CVE-2025-69971 |
| CVE-2025-69981 | `/api/upload` 무인증 파일 업로드 | 1.2.7 | 1.2.10(릴리스 노트 "file upload handling authenticated") 추정 | https://github.com/advisories/GHSA-7g56-fwxj-cm23 |
| CVE-2025-69985 | Referer 헤더 신뢰 인증 우회 | ≤1.2.8 | [미확인] | https://vulners.com/search/vendors/frangoteam/products/fuxa |
| CVE-2026-25751 | 무인증 사용자에게 DB 관리자 자격증명 노출 | <1.2.10 | 1.2.10 | https://www.sentinelone.com/vulnerability-database/cve-2026-25751/ |
| CVE-2026-25752 | WebSocket으로 무인증 태그 **쓰기**(설비 값 변경) | <1.2.10 | 1.2.10 | 위 vulners 목록 |
| CVE-2026-25951 | 경로 순회 → 관리자 권한에서 임의 코드 실행 | <1.2.11 | 1.2.11 | https://app.opencve.io/cve/CVE-2026-25951 |
| CVE-2026-47718 | secure 모드에서 게스트/무효 토큰으로 보호 API 읽기 | 1.3.0-2773 | 1.3.1 | https://github.com/frangoteam/FUXA/security/advisories/GHSA-r9g5-7q8j-958c |
| CVE-2026-47719 | Socket.IO 무인증 SSRF (High, 8.2) | ≤1.3.1 | 1.3.2 | https://github.com/frangoteam/FUXA/security/advisories/GHSA-w86f-rf9w-h3x6 |
| CVE-2026-65984 | 삭제·강등 사용자가 JWT로 관리자 권한 유지 (High) | ≤1.3.2 | 1.3.3 | https://github.com/frangoteam/FUXA/security/advisories/GHSA-rg7m-xwqc-mjw6 |
| CVE-2026-67443 | 게스트 JWT로 내장 Node-RED 관리 접근 → 원격 스크립트 실행 (High) | ≤1.3.2 | 1.3.3 | https://github.com/frangoteam/FUXA/security/advisories/GHSA-5h5x-9h7x-23f4 |
| CVE-2026-67440 | 무인증 Socket.IO 읽기 이벤트(메타데이터 노출) | ≤1.3.2 | 1.3.3 | https://github.com/frangoteam/FUXA/security/advisories/GHSA-rh5p-m38p-2w75 |
| (CVE [미확인]) | 스케줄러 권한 상승, TDengine 커넥터 SQLi(2026-05-29) / 정적 파일 무인증 노출, SSRF 보강, 역할 삭제 논리 결함(2026-07-22) | [미확인] | 1.3.2~1.3.3 추정 | https://github.com/frangoteam/FUXA/security/advisories |
| — | 1.3.4: Socket.IO 관리 응답 범위 제한, `runScript` 권한 바인딩, rate limiter 순서 수정 (CVE 미부여) | — | 1.3.4 | https://github.com/frangoteam/FUXA/releases/tag/v1.3.4 |

> 판정: FUXA를 유지한다면 **1.3.4 + `secureEnabled=true` + Node-RED 통합 비활성** 이 최소선. 게스트 토큰 자동 발급 구조가 여러 권고의 공통 원인이다.

---

## 1 · 시계열·운영 데이터 저장

| 후보 | 최신 버전(날짜) | 라이선스 | 공식 이미지 | EOL/패치 | 무료판 제한 | 분류 | 근거 URL |
|---|---|---|---|---|---|---|---|
| InfluxDB 2.x (현행 V1 계열) | 2.9.1 (2026 상반기, Docker 2026-09-19) | MIT | `influxdb:2.9.1` | 2.7 지원 종료, 2.8·2.9 지원. v2 EOL 계획 없음 | 없음(OSS 전체). 클러스터 없음 | 직접 시험 대상 (2.9로 올리는 경로) | https://docs.influxdata.com/influxdb/v2/reference/release-notes/supported-release/ |
| InfluxDB 3 Core | 3.11.5 (2026-09-17) | MIT/Apache-2.0 | `influxdb:3-core` | 최신 2개 마이너 지원 | **단일 쿼리당 Parquet 432파일 한도**(`--query-file-limit`, 기본 10분 파일 기준 ≈72h). 올릴 수 있으나 Core엔 compactor 없음. 쓰기 시점 제한은 해제됨. HA·read replica는 Enterprise | 직접 시험 대상 (장기 이력 조회는 한도 확인 필수) | https://layerbase.com/blog/influxdb-3-core-72-hour-limit · https://github.com/influxdata/influxdb/pull/25890 · https://docs.influxdata.com/influxdb3/core/ |
| TimescaleDB (Apache 판) | 2.30.1 (2026-09-17) | Apache-2.0 (Apache판) / TSL(커뮤니티판) | `timescale/timescaledb:2.30.1-pg18-oss` (`-oss` 태그가 Apache 전용) | 활발히 패치 | Apache판에 **hypertable·`drop_chunks`·`time_bucket`만**. 보존정책·압축(columnstore)·연속집계·잡 스케줄러·gapfill은 TSL → 보존은 `pg_cron`+`drop_chunks` 등으로 대체 | 직접 시험 대상 (TSL 기능은 제외 유지) | https://www.tigerdata.com/docs/get-started/choose-your-path/timescaledb-editions · https://hub.docker.com/r/timescale/timescaledb |
| PostgreSQL + pg_partman | PG 18.6 / pg_partman 5.5.0 (2026-07-22) | PostgreSQL License (둘 다) | `postgres:18` (+ 확장 설치) | PG18 → 2030-11 | 없음. 압축·집계는 직접 구현 | 직접 시험 대상 | https://github.com/pgpartman/pg_partman/releases · https://endoflife.date/postgresql |
| QuestDB | 10.0.1 (2026-08-24) | Apache-2.0 | `questdb/questdb:10.0.1` | 활발 | OSS: HTTP Basic/PGWire **내장 admin·read-only 사용자**, ILP 토큰. **RBAC·TLS·HA·복제·SSO는 Enterprise** | 직접 시험 대상 | https://questdb.com/docs/guides/architecture/security/ · https://questdb.com/enterprise/ |
| VictoriaMetrics (single) | v1.153.0 (2026-09-25) | Apache-2.0 | `victoriametrics/victoria-metrics:v1.153.0` | LTS 라인 운영(현재 라인 [미확인]) | **다운샘플링·다중 보존·mTLS·Kafka 연동·vmbackupmanager는 Enterprise**. 인증은 vmauth 기본 | 직접 시험 대상 (Prometheus 장기저장·설비 메트릭 겸용) | https://docs.victoriametrics.com/victoriametrics/enterprise/ · https://github.com/VictoriaMetrics/VictoriaMetrics/releases |
| VictoriaLogs | v1.51.1 (2026-08-18) | Apache-2.0 | `victoriametrics/victoria-logs:v1.51.1` | 활발 | Enterprise 이미지 별도 | 직접 시험 대상 (이벤트/알람 로그 보관용 선택지) | https://github.com/VictoriaMetrics/VictoriaLogs/releases |
| Apache IoTDB | 2.0.11 (2026-09-14) | Apache-2.0 | `apache/iotdb:2.0.11-standalone` | ASF 활발. JDK 17 필수 | 상용판 Timecho(`timecho/timechodb`)가 성능·기능 추가. OSS 권한관리 세부 [미확인] | 직접 시험 대상 (설비 트리·테이블 모델, 엣지판) | https://lists.apache.org/thread/oo6gwxzswjr6xjl48qgsn6z6qcp3n8qg · https://iotdb.apache.org/UserGuide/latest-Table/Deployment-and-Maintenance/Docker-Deployment_apache.html |
| GreptimeDB | v1.2.1 (2026-09-16) | Apache-2.0 (open-core) | `greptime/greptimedb:v1.2.1` | 1.x 정식 | OSS: 클러스터·Flow·오브젝트스토리지 포함, **파일 기반 정적 사용자 권한**. RBAC/ACL·LDAP·감사·콘솔·read replica는 Enterprise | 직접 시험 대상 (메트릭·로그·PromQL·SQL 통합) | https://greptime.com/product/enterprise · https://docs.greptime.com/enterprise/user/ |
| TDengine TSDB-OSS | 3.4.2.8 (Docker 2026-08-31) | **AGPL-3.0 ⚠제품화 시 주의** | `tdengine/tsdb:3.4.2.8` (**옛 `tdengine/tdengine`은 2025-06 3.3.6.13에서 멈춤**) | 3.4는 롤링 업그레이드 불가 | OSS에 클러스터 포함. **taosX(OPC/MQTT 무코드 수집)·계층 스토리지·RBAC·감사·IP 화이트리스트·암호화는 Enterprise** | 직접 시험 대상 (AGPL 표기) | https://tdengine.com/feature-comparison/ · https://tdengine.com/tdengine-tsdb-3-4-release-notes/ |
| CrateDB | 6.4.5 (2026-09-16) | Apache-2.0 (4.5부터 전 기능 단일 OSS) | `crate/crate:6.4.5` | 활발 | 없음(엔터프라이즈 라이선스 폐지) | 직접 시험 대상 | https://cratedb.com/blog/farewell-to-the-cratedb-enterprise-license-faq |
| ClickHouse | 26.8 LTS (2026-08-27), 패치 26.8.14 | Apache-2.0 | `clickhouse/clickhouse-server:26.8` | LTS 1년(연 2회) | OSS에 RBAC 포함. 관리형 기능만 Cloud | 직접 시험 대상 (분석·이력 대량 조회용) | https://clickhouse.com/blog/clickhouse-release-26-08 · https://endoflife.date/clickhouse |
| M3 (M3DB) | v1.6.0 (2026-09-25 추정) | Apache-2.0 | 이미지명 [미확인] | 활동 재개 | 대규모 Prometheus 원격저장 지향 | 직접 시험 대상 (규모상 과함 가능 — 성능 추정으로 제외하지 않음) | https://github.com/m3db/m3/releases |
| Grafana Mimir | 3.2.1 (2026-09-10) | **AGPL-3.0 ⚠** | `grafana/mimir:3.2.1` | 활발 | 없음(OSS) | 직접 시험 대상 (AGPL 표기) | https://github.com/grafana/mimir/releases |
| Thanos | v0.42.4 (2026-07-30 추정) | Apache-2.0 | `thanosio/thanos` (quay.io 병행) | CNCF Incubating | 없음 | 직접 시험 대상 | https://github.com/thanos-io/thanos/releases |
| OpenTSDB | 2.4.1 (2021-09-02), 2.5.0-RC1(2021-12) | LGPL-2.1+ | `opentsdb/opentsdb` 최종 2023-11 스냅숏 | Yahoo 유지 2021 종료, 유지보수 모드. 4년+ 정식 릴리스 없음 | — | **① 관문 제외** (사실상 EOL) | https://opentsdb.net/faq.html · https://github.com/OpenTSDB/opentsdb/releases |
| Machbase Neo (국산) | [미확인] | 독자 라이선스 — 라이선스 없이 **평가용만**, 세션당 1억 행 후 입력 중지 | [미확인] | — | 무라이선스 = 평가 전용 | **① 관문 제외** (약관) | https://docs.machbase.com/dbms/install/license/ |
| PostgreSQL (알람 기록, V1) | 18.6 권장 | PostgreSQL | `postgres:18` | 위 0절 | — | 직접 시험 대상 (시계열 통합 시 본체) | https://endoflife.date/postgresql |
| Neo4j Community (온톨로지, V1) | 2026.09.0 / 5.26.31 LTS | **GPLv3** (Enterprise 소스 비공개) | `neo4j:2026.09.0` / `neo4j:5.26-community` | 5.26 LTS 2028-06 (Enterprise 기준) | 단일 인스턴스, 클러스터·RBAC 없음 | 직접 시험 대상 (현행 유지) | https://neo4j.com/blog/news/open-core-licensing-model-neo4j-enterprise-edition/ |

---

## 2 · 모니터링·대시보드

| 후보 | 최신 버전(날짜) | 라이선스 | 공식 이미지 | EOL/패치 | 무료판 제한 | 분류 | 근거 URL |
|---|---|---|---|---|---|---|---|
| Prometheus 3.x | 3.15 (2026-09-25) / LTS 3.13 | Apache-2.0 | `prom/prometheus:v3.15.0` | LTS 3.13 → 2027-07-31 | 없음 | 직접 시험 대상 (현행, **LTS 3.13 고정 권장**) | https://endoflife.date/prometheus |
| Alertmanager | v0.34.1 (2026-09-17) | Apache-2.0 | `prom/alertmanager:v0.34.1` | 0.x 연속 | ack/shelve 상태 없음 | 직접 시험 대상 (알림 라우팅 전용) | https://github.com/prometheus/alertmanager/releases |
| Grafana OSS | 13.2.2 (2026-09-15) | **AGPL-3.0 ⚠** (무수정 내부 사용은 의무 없음) | `grafana/grafana:13.2.2` | 활발 | RBAC·데이터소스 권한·리포팅·SAML·감사는 Enterprise | 직접 시험 대상 | https://grafana.com/docs/learning-hub/which-grafana/02-understand-your-options/04-grafana-enterprise/ |
| Perses | v0.55.0-beta.2 (2026-09-18), 정식 최신 [미확인] | Apache-2.0 | `persesdev/perses` | CNCF Sandbox, 1.0 전 | 없음 | 직접 시험 대상 (대시보드-as-code) | https://github.com/perses/perses/releases |
| VictoriaMetrics vmalert | v1.153.0 | Apache-2.0 | `victoriametrics/vmalert` | 위와 동일 | 멀티테넌트 vmalert는 Enterprise | 직접 시험 대상 (VM 채택 시) | https://docs.victoriametrics.com/victoriametrics/enterprise/ |

---

## 3 · HMI / SCADA 화면

| 후보 | 최신 버전(날짜) | 라이선스 | 공식 이미지 | EOL/패치 | 무료판 제한 | 분류 | 근거 URL |
|---|---|---|---|---|---|---|---|
| FUXA (V1) | 1.3.4 (2026-08-13) | MIT | `frangoteam/fuxa:1.3.4` | 권고 다수 (0절) | 없음. 인증은 `secureEnabled` 수동 | 직접 시험 대상 (1.3.4 필수) | https://github.com/frangoteam/FUXA/releases |
| Node-RED 5 + Dashboard 2.0 | Node-RED 5.0.4 (2026-07-30), Dashboard 2 v1.32.0 (날짜 2026-09-24 추정) | Apache-2.0 | `nodered/node-red` (5.x 태그 [미확인]; 4.1.15 2026-09-09), `flowfuse/node-red:latest-5.0.x` | 활발. Node 22.9+ 필요, 32bit ARM 중단 | 없음 (FlowFuse 관리형은 유료) | 직접 시험 대상 | https://flowfuse.com/blog/2026/06/node-red-5-on-flowfuse/ · https://github.com/FlowFuse/node-red-dashboard/releases |
| ThingsBoard CE | 4.3.1.6 (Docker `tb-node` 2026-09-28) | Apache-2.0 (PE는 상용) | `thingsboard/tb-node` (단일 `tb-postgres`는 4.2.1.1, 2025-12에서 멈춤) | 4.3.1.5에서 CVE-2026-65182 등 수정 | 화이트라벨·일부 위젯·통합은 PE | 직접 시험 대상 (**알람 ACK/CLEAR 수명주기 내장**) | https://thingsboard.io/docs/user-guide/alarms/ · https://github.com/thingsboard/thingsboard/releases |
| OpenRemote | 1.31.1 (2026-09-28) | **AGPL-3.0 ⚠** | `openremote/manager:1.31.1` | 활발, 2026 CVE 수정 이력(알람 일괄삭제 IDOR 등) | 없음 | 직접 시험 대상 (AGPL 표기) | https://github.com/openremote/openremote/releases |
| Apache StreamPipes | 0.98.0 (2025-12-15), 0.99 스냅숏 | Apache-2.0 | `apachestreampipes/backend`, `/ui` | 과거 관리자 권한 탈취 취약점 보도(CVE 번호 [미확인]) | 없음. 기본 메시징 NATS | 직접 시험 대상 (파이프라인+대시보드, OPC UA) | https://streampipes.apache.org/blog/2025/12/15/_release-098/ · https://www.techrepublic.com/article/news-apache-streampipes-flaw-lets-anyone-become-admin/ |
| Scada-LTS | v2.8.0 (Docker 2025-10-17) | GPL-2.0 [저장소 LICENSE 미확인] | `scadalts/scadalts:v2.8.0` | 릴리스 간격 김(2.7.8.1→2.8.0 약 7개월) | 없음 | 직접 시험 대상 | https://hub.docker.com/r/scadalts/scadalts · https://github.com/SCADA-LTS/Scada-LTS |
| ioBroker | js-controller 7.2.3 (2026-09-19), Docker v11.1.0 (2026-09-27) | MIT | `iobroker/iobroker` (buanet 빌드가 공식) | 활발 | 없음 (홈오토메이션 성격) | 직접 시험 대상 (우선순위 낮음) | https://github.com/buanet/ioBroker.docker |
| PyScada | 저장소 갱신 2026-04-03, 릴리스 [미확인] | **AGPL-3.0 ⚠** | [미확인] | — | — | [미확인] (이미지 확인 후 판정) | https://github.com/pyscada/PyScada |
| Grafana + Business Forms (HMI 대용) | Business Forms 최신 [미확인] | Apache-2.0 (플러그인), Grafana AGPL | Grafana 플러그인 | Grafana가 Volkov Labs 인수 후 유지 | 쓰기는 REST 호출로만 | 직접 시험 대상 (읽기 화면 + 제한된 명령) | https://github.com/grafana/business-forms |
| Rapid SCADA | 6.5.0 (2026-09-07) | Apache-2.0 (Enterprise 상용) | **공식 Docker Hub 이미지 없음** — Dockerfile·포럼 안내만(요청 이슈 #58) | 활발 | Enterprise 모듈 별도 | **① 관문 제외** (공식 컨테이너 부재. 자체 빌드 허용 시 재검토) | https://github.com/RapidScada/scada-v6/issues/58 · https://forum.rapidscada.org/?topic=docker-files |
| OpenSCADA | 0.9 LTS (날짜 [미확인]) | GPL-2.0 | **공식 이미지 없음** (dudanov/·sinoptiic/ 커뮤니티 이미지뿐) | — | — | **① 관문 제외** (공식 컨테이너 부재) | https://hub.docker.com/r/dudanov/openscada · http://oscada.org/wiki/Documents/Release_0.9 |
| Ignition | — | 상용 | — | — | — | ① 제외 (사전 확정) | — |
| Tago.io | — | 상용 SaaS | — | — | — | ① 제외 (상용·자가호스팅 불가 [미확인]) | — |

---

## 4 · 알람 관리 (ISA-18.2 수명주기)

| 후보 | 최신 버전(날짜) | 라이선스 | 공식 이미지 | EOL/패치 | 무료판 제한 | 분류 | 근거 URL |
|---|---|---|---|---|---|---|---|
| **Alerta** | 9.1.0 (Docker 2026-03-28) | Apache-2.0 | `alerta/alerta-web:9.1.0` | 포크 alerta-ng는 "상류가 적극 유지되지 않음"이라 명시 → 유지 위험 | 없음 | 직접 시험 대상 — **ISA-18.2 알람 모델 내장**(NORM·UNACK·ACKED·RTNUN·SHLVD·DSUPR·OOSRV, ack/unack/shelve/unshelve). PostgreSQL 백엔드 | https://github.com/alerta/alerta/blob/master/alerta/models/alarms/isa_18_2.py · https://docs.alerta.io/ |
| alerta-ng (포크) | 9.1 계열, 날짜 [미확인] | Apache-2.0 | [미확인] | 활발, drop-in 교체 | 없음 | 직접 시험 대상 (Alerta 유지 위험 대안) | https://github.com/ospo-ionik/alerta-ng |
| Keep | v0.54.3 (2026-09-09 추정) | MIT(코어) + 상용 `ee/` | GHCR/Artifact Registry 이미지 (Docker Hub 없음, 정확 경로 [미확인]) | 활발 | **RBAC·SSO·HA·AIOps 상관분석은 EE** | 직접 시험 대상 (다중 소스 알림 집약·중복제거. ISA-18.2 상태 없음) | https://github.com/keephq/keep · https://github.com/keephq/keep/blob/main/LICENSE |
| ThingsBoard 알람 | 위 3절 | Apache-2.0 | 위 | 위 | — | 직접 시험 대상 (ACTIVE_UNACK/ACK, CLEARED_UNACK/ACK — ISA-18.2 부분집합, shelve 없음) | https://thingsboard.io/docs/user-guide/alarms/ |
| Grafana Alerting (OSS) | Grafana 13.2 | AGPL-3.0 | 위 | — | **알람 ack 기능 없음**(2020 요청 이슈 열림). ack는 Cloud IRM | 직접 시험 대상 (탐지·통지만) | https://github.com/grafana/grafana/issues/24762 |
| Grafana OnCall OSS | 최종판 | AGPL-3.0 | — | **2025-03-11 유지보수 모드 → 2026-03-24 아카이브** | Cloud 연결 기능 중단 | **① 관문 제외** (EOL) | https://grafana.com/docs/oncall/latest/set-up/open-source/ |
| Alertmanager | 0.34.1 | Apache-2.0 | 위 | — | silence만, ack/shelve 상태 없음 | 직접 시험 대상 (통지 계층) | 위 |
| DB 내 자체 ISA-18.2 상태기계 | — | (자체) | PostgreSQL | — | — | 구조 패턴 C 참조 | Alerta 모델 코드(위)를 참조 설계로 사용 가능 |

---

## 5 · 브로커 직결 HMI 관련 (패턴 B의 전제)

| 후보 | 최신 버전(날짜) | 라이선스 | 공식 이미지 | 비고 | 분류 | 근거 URL |
|---|---|---|---|---|---|---|
| Eclipse Mosquitto | 2.1.2 (2026-02-09, 이미지 2026-09-18) | EPL-2.0/EDL-1.0 | `eclipse-mosquitto:2.1.2` | 2.1부터 **내장 WebSocket**(libwebsockets 불필요), `websockets_origin` 강제, Dynamic Security 플러그인(토픽 ACL, %c/%u 패턴) | 직접 시험 대상 | https://mosquitto.org/blog/2026/01/version-2-1-0-released/ |
| EMQX 5.9+ / 6.x | 6.3 (2026-09-17) | **BSL 1.1 ⚠** — 단일 노드 무료, **클러스터는 라이선스 파일 필요**, 상용 호스팅·제품 내장 금지 | `emqx/emqx:6.3` | 2025-05 5.9부터 CE/EE 통합 | **① 관문 제외** (BSL·제품 내장 금지 조항) | https://www.emqx.com/en/content/license-faq |

---

## 6 · 구조 패턴

| 패턴 | 내용 | 줄어드는 것 | 확인할 점 | 근거 |
|---|---|---|---|---|
| **A. 저장소 3개 → 2개** | PostgreSQL 하나에 알람 기록 + 시계열(TimescaleDB Apache판 hypertable 또는 pg_partman 네이티브 파티션). InfluxDB 제거, Neo4j는 온톨로지 전용 유지 | InfluxDB·Telegraf→Influx 경로, 백업 대상 1개 | Apache판엔 압축·연속집계·보존정책 없음 → `drop_chunks`/파티션 drop을 `pg_cron`으로. 집계는 일반 MV 또는 앱. 장기 대량 조회 성능은 시험으로 판정 | §1 TimescaleDB·pg_partman 행 |
| A′. 저장소 3 → 2 (그래프 흡수) | Apache AGE로 PostgreSQL 안에서 그래프까지 | Neo4j | 본 문서 범위 밖(04 문서 영역). 여기선 가능성만 표기 | [미확인] |
| **B. HMI가 브로커 직접 구독** | Vue 화면이 MQTT over WebSocket(Mosquitto 2.1 내장 WS)으로 설비·알람 토픽 구독. Telegraf#3→MQTT→FUXA 우회 제거 | 알람→화면 약 8홉 → 발생기·브로커·화면 3홉 수준 | 브라우저에 브로커 자격증명 노출 → 읽기 전용 사용자 + Dynamic Security 토픽 ACL + `websockets_origin`. **쓰기(명령)는 브로커 직결 금지**, 단일 명령 API로 | §5 Mosquitto |
| **C. 알람 수명주기를 DB에** | `alarm` 테이블에 ISA-18.2 상태(NORM/UNACK/ACKED/RTNUN/SHLVD/DSUPR/OOSRV)와 이벤트 이력, ack/shelve는 API 트랜잭션. 변경 시 `LISTEN/NOTIFY` 또는 MQTT로 화면 갱신 | 상태 불일치(화면·DB·Alertmanager) | 참조 구현으로 Alerta `isa_18_2.py` 상태기계 이용 가능. shelve 만료·억제 규칙·재통지 정책 설계 | §4 Alerta |
| C′. 기성 알람 서버 채택 | Alerta(ISA-18.2 모델) 또는 ThingsBoard 알람 | 자체 구현량 | Alerta 상류 유지 위험 → alerta-ng 병행 검토 | §4 |
| **D. 설비 쓰기 경로 3개 → 1개** | FUXA·EdgeX command·AI 파일럿 게이트웨이의 쓰기를 **하나의 명령 게이트웨이**(권한·감사·인터락)로 통일. HMI와 AI는 호출자일 뿐 | 쓰기 경로 2개 | FUXA를 남기면 FUXA 자체 장치 폴링·쓰기 비활성 필요(CVE-2026-25752 같은 무인증 태그 쓰기 전례) | §0 FUXA 권고 |
| E. 모니터링은 인프라 전용 | Prometheus(LTS 3.13)+Alertmanager는 컨테이너·서비스 건강만, 공정 알람은 C 경로로 분리 | 공정 알람과 인프라 알림 혼재 | 장기 보관 필요 시 VictoriaMetrics/Thanos/Mimir 중 하나 | §2 |

---

## 7 · 확인 못 한 것 [미확인]

- V1이 실제 쓰는 PostgreSQL 메이저 버전 (PG14면 2026-11 EOL로 12개월 내).
- FUXA CVE-2025-69970/69971/69981/69985의 정확한 수정 버전, 2026-05-29·07-22 일부 권고(스케줄러 권한상승·TDengine SQLi·정적 파일 노출·SSRF 보강·역할 삭제)의 CVE 번호 — GitHub API 요청 한도로 일괄 조회 실패.
- CVE-2026-67442(FUXA, CVSS 2 부적절 접근제어)가 어느 권고에 대응하는지.
- VictoriaMetrics 현재 LTS 라인 번호.
- Perses 최신 정식(비베타) 버전, Keep·Node-RED Dashboard 2·Thanos·M3 릴리스의 연도(GitHub 화면 연도 생략 — "추정" 표기).
- Keep 공식 컨테이너 레지스트리 정확 경로, alerta-ng 이미지.
- Apache IoTDB OSS의 사용자·권한 기능 범위, M3 공식 이미지 이름.
- Scada-LTS 저장소 LICENSE 원문(GPL-2.0로 알려짐), OpenSCADA 0.9 LTS 날짜, PyScada 컨테이너 여부.
- Apache StreamPipes 관리자 탈취 취약점 CVE 번호와 수정 버전.
- Machbase Neo 최신 버전·가격(약관상 무라이선스=평가용은 확인).
- Tago.io 자가호스팅 가능 여부.
- Apache AGE(패턴 A′)의 최신 버전·PG18 지원 — 본 문서 범위 밖.
- 성능·완주·실제 기동은 전부 미검증(문헌 조사만, docker 미실행).
