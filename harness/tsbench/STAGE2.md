# 시계열 저장 벤치 ② 준비 (EXP-TS) — 2026-09-29 준비, **미실행**

판정 규칙 `QUESTIONS.md` §1, 후보 `CANDIDATES.md` §6, 비정상 `ROBUSTNESS.md` R06. 결과는 `experiments/EXP-TS/stage2_<engine>.json` 에만.

## 무엇을 재나 (결과 보기 전 고정)
- **적재(fast-load):** V1 측정값 4종을 V1 이름·태그 그대로(`telegraf/sink.conf`): `process_raw`(12태그×1초, 결측 0.47% = 레코드 부재) · `process`(clean, 결측 자리 `INTERPOLATED_LINEAR`) · `anomaly`(1초 1행) · `alerts`(5분 1건, 문자열 `detail` 한글 포함). 24시간 ≈ 2.2M 행, 배치 5000(V1 sink `metric_batch_size`). 잴 것: 행/초, 배치 지연 p95, 쓰기 오류.
- **질의(V1 이 실제로 쓰는 것만, 엔진별 번역):** `evidence`(ai-layer `operations/evidence.py history()`: 4태그·[t−30s, t+15s)·time 정렬·limit 2001, 20시점) · `evidence300`(창 상한 300초) · `current`(`pipeline.py` 최근 30초 12태그) · `trend_1h/24h`(Grafana 01-process mean, 창 10s/60s) · `quality_24h`(품질별 count) · `anomaly_24h`·`anomaly_count`(02-anomaly) · `alerts_last100`·`alerts_rate`(03-alerts). 반복 20회(집계 질의 5회) p50/p95 + 콜드 1회.
- **정답:** 생성기가 결정적 → 모든 질의 기대값을 파이썬으로 계산해 대조(`correct`). 하나라도 틀리면 ② 탈락.
- **F05(72h 초과):** `HOURS=168` 로 7일 적재 → `long_trend_full`·`long_evidence_oldest`·`long_quality_full`. InfluxDB 3 Core 의 쿼리당 Parquet 432파일 한도(≈72h) 실측.
- **가시화 지연(E7 전제):** 12행/초 60초 쓰면서 각 초의 행이 조회에 보일 때까지 ms.
- **디스크:** 빈 상태·적재 직후·60초 뒤 `du -sk <데이터 경로>`. **메모리·CPU:** 적재/질의 구간별(결과의 marks 로 분할).
- **④ R06 훅(`R06=1`):** Telegraf 1.40(V1 telegraf-sink 역할, 버퍼 200000) → 엔진, 12행/초 10분 중 DB 5분 정지 → 저장 유실·중복·재개 시간. 알람·화면 지속은 이 벤치 밖(V1 알람 경로는 InfluxDB 를 거치지 않음 — 구조 벤치에서).
- **자원 한도 없음(09-29 결정 I5):** 컨테이너 메모리·CPU 제한을 두지 않는다 — 실제 사용량 자체가 ③ 효율 측정값. 공정성은 같은 호스트에서 벤치 하나씩(각 stage2.sh 가 같은 벤치 동시 기동 거부, rot 스택과는 가드로 분리). JVM 힙 등 제품 설정은 상류 예시·기본값 그대로. CrateDB 힙도 기본값(`CRATE_HEAP_SIZE` 미설정).

## 후보 → 프로파일

| 후보 | 프로파일 | 이미지 | 적재 경로 / 질의 언어 | V1 재현 방법 | 갭·주의 |
|---|---|---|---|---|---|
| InfluxDB 2.7 (기준 V1, 강제 교체) | `influx27` | `influxdb:2.7` (V1 과 같은 마이너 태그) | LP `/api/v2/write` / **Flux 원문** | V1 Flux 문자열 구조 그대로 | 기준선 |
| **InfluxDB 2.9** (같은 제품 최신, P1) | `influx29` | `influxdb:2.9.1` | 같음 | 같음 — 코드 수정 0 | 2.9.0부터 토큰 해시 저장(이전 절차), 벤치는 새 초기화 |
| InfluxDB 3 Core | `influx3` | `influxdb:3.11.5-core` | LP `/api/v3/write_lp` / SQL | **Flux 미지원 → evidence.py·Grafana 대시보드 전부 SQL 로 재작성 필요(갭)** | 인증 켬(토큰은 stage2.sh 가 `influxdb3 create token --admin`), 432파일 한도 → `HOURS=168` 필수, HA 는 Enterprise(미사용) |
| TimescaleDB Apache판 (P1, P-3→2) | `timescale` | `timescale/timescaledb:2.30.1-pg18-oss` | COPY / SQL `time_bucket` | 같은 열 이름(time, site, device, tag, quality, value) | 압축·연속집계·보존정책 없음(TSL) → 보존은 `drop_chunks`+pg_cron(③), 24h 디스크가 커질 수 있음 |
| PostgreSQL 18 + pg_partman (P1) | `pgpartman` | `bench-pg-partman:18.6` = `postgres:18.6-bookworm` + PGDG `postgresql-18-partman` (빌드) | COPY / SQL `date_bin` | 같음, 일 파티션 | pg_partman 버전은 apt 가 정함 → 결과 `engine_info.extensions` 에 기록(CANDIDATES 5.5.0) |
| QuestDB 10 | `questdb` | `questdb/questdb:10.0.1` | ILP over HTTP / SQL `timestamp_floor` | 태그=SYMBOL | 인증·TLS 는 Enterprise → OSS 는 무인증(① 기본 보안 확인 필요) |
| VictoriaMetrics single | `victoriametrics` | `victoriametrics/victoria-metrics:v1.153.0` | LP `/write` / MetricsQL·export | metric=`<측정값>_<필드>` | **문자열 필드 저장 안 함 → `alerts_last100`(알람 이력 표) 재현 불가(질의가 오류로 기록됨)**. `-search.latencyOffset=30s` 기본값 → 최근 30초 가시화 지연 가능. 다운샘플·Kafka 연동 Enterprise |
| Apache IoTDB | `iotdb` | `apache/iotdb:2.0.11-standalone` | Tablet(테이블 모델) / SQL `date_bin` | TAG(site/device/tag) + FIELD | 기본 시간 정밀도 ms → ns 자리 잘림(V1 ns). R06 은 Telegraf `outputs.iotdb`(트리 모델) → 세는 질의 [미검증] |
| GreptimeDB | `greptime` | `greptime/greptimedb:v1.2.1` | InfluxDB v2 쓰기 호환 / SQL `date_bin` | 시간 열 `greptime_timestamp` | RBAC·감사 Enterprise → OSS 무인증 |
| CrateDB | `cratedb` | `crate/crate:6.4.5` | HTTP `/_sql` bulk / SQL `DATE_BIN` | 일 파티션(생성 열) | 새로고침(`REFRESH`) 전 미가시 → 가시화 지연에 반영. R06 은 `outputs.cratedb` 고정 스키마(tags 객체) |
| ClickHouse 26.8 LTS | `clickhouse` | `clickhouse/clickhouse-server:26.8.14.3` | clickhouse-connect insert / SQL `toStartOfInterval` | MergeTree ORDER BY(tag, ts) | LTS 1년 → 26.8 은 ≈2027-08 종료, 다음 LTS 추종 조건 |
| TDengine TSDB-OSS | `tdengine` | `tdengine/tsdb:3.4.2.8` | taosAdapter InfluxDB 쓰기 호환(스키마리스) / SQL `INTERVAL` | 태그→TAG, 필드→열 | **AGPL-3.0 ⚠ 제품화 시 주의.** `tag`·`value` 이름 백틱 필요 |
| (보조) VictoriaLogs | — | `victoriametrics/victoria-logs:v1.51.1` | — | — | 알람·이벤트 로그 보조 저장 후보(P3) — 이 벤치 범위 밖, VM 의 문자열 갭 보완 조합으로 ③에서 |

## 실행
```bash
harness/tsbench/stage2.sh influx27                    # 기준선 먼저
for e in influx29 influx3 timescale pgpartman questdb victoriametrics iotdb greptime cratedb clickhouse tdengine; do harness/tsbench/stage2.sh $e; done
HOURS=168 harness/tsbench/stage2.sh influx3          # F05 · 432파일 한도(다른 엔진도 같은 명령으로)
R06=1 harness/tsbench/stage2.sh influx29             # ④ R06(DB 5분 정지, R06_DOWN_S 로 조정)
```
산출: `experiments/EXP-TS/stage2_<engine>.json`, `raw/<engine>_load24h.json`·`_query24h.json`·`_fresh.json`·`_r06.json`, `raw/disk_*`, `raw/stats_*`, `raw/<engine>_engine.log`.

## 준비 검증(2026-09-29)
- 이미지: 외부 이미지 전부 받음(`experiments/BENCH-PREP/pull_20260929_0258.log`, 실패 0).
- `config -q` 통과, latest 0. 가드 거부 확인(`stage2.sh influx29` → 종료 3).
- 생성기·정답 자체 점검(호스트, 컨테이너 없이): 24h 기준 quality 합계 1,036,800 = 12×86,400, alerts 288건, evidence 45초×4태그 = 180행, 2시간 179,614행 — 정답 계산기가 도는 것만 확인. **엔진 연결·질의 번역은 미실행(미검증).** 엔진별 SQL 방언은 문서 지식으로 작성 → 첫 실행에서 `error` 가 나면 번역 결함인지 엔진 한계인지 구분해 기록.
