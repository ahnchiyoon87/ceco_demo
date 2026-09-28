# L4 이상탐지 ② 기동·기능 벤치 (stage2) — 준비 2026-09-29, 실행 전

판정 규칙은 `QUESTIONS.md` §1, 후보 목록은 `harness/situations/CANDIDATES.md` §1(개정 #74 반영), 시험 항목은 `harness/situations/L4.md`·`ROBUSTNESS.md`.
이 문서는 **준비 상태**다. 벤치 컨테이너는 하나도 기동하지 않았다(메모리 여유 부족으로 실행 금지 조건에서 준비). "문헌" 표시 수치는 문서 값이지 실측이 아니다.
**"오프라인 예비(비판정)"**는 컨테이너 없이 로컬 JVM·Python 에서 엔진 라이브러리를 직접 돌려 본 결과다. ② 판정이 아니며 점수표·결정에 쓰지 않는다 — ② 실행 결과가 나오면 그것으로 대체한다.
준비 중 컨테이너 실행 기록: 2026-09-29 `docker run --rm postgres:17.6-alpine true`(명령 없는 즉시 종료) 1회 — 실수, 영향 없음. 그 밖에 벤치·엔진 컨테이너 기동 없음(이미지 받기·`docker create`/`cp` 로 파일 조사만).

**사람 결정(2026-09-29, 코디네이터 전달):**
1. Feldera → ① 관문 제외(아래 5절).
2. RisingWave → 7.6 GB 에서 그대로 ②. 기동·처리 실패는 ② 실패로 기록(공급사 최소 사양은 관문 사실이 아님).
3. 문헌으로 닫지 않는다(문헌 제외는 라이선스·약관·EOL·컨테이너 없음만). Kafka Streams·Storm·StreamPipes·Beam·Flink HA-B·Flink 2.3 DataStream CEP 도 ② 프로필을 준비하고,
   Quix·RisingWave·Proton·Arroyo 등도 CEP·Z-Score·ONNX 를 **엔진에 실제로 내 보고 엔진 응답을 기록**해 "기능 불가"를 실행으로 확정한다.
4. StreamPipes 는 파이프라인 조립까지 REST 로 자동화한다(준비 부족이 아니라 엔진을 잰다).
5. Kafka Streams·Storm·Beam 에 ONNX 를 이식하지 않는다 — ② 는 CEP 에서 먼저 떨어질 것으로 보고, 앞 단계 탈락 시 뒤 항목은 생략한다(QUESTIONS §1 "빠르게 거르는 순서"). ② 실행이 CEP 실패를 먼저 확정한다.
6. HA-B 는 단독 실행(설정 메모리 약 4.8GB).

## 1. 공통 방법

- 입력 하나: 벤치 Kafka(`apache/kafka:3.9.0`, V1 과 같은 버전) `exp.l4.raw` 에 `harness/tools/replay.py` 로 S02·S04~S08 발행. 후보마다 알람을 자기 토픽 `exp.l4.alerts.<후보>` 에 쓴다.
- **한 번에 한 후보만** 띄운다. 그래서 V1 과 동시 소비 대신 **같은 시드로 돌린 V1 알람 기록과 대조**한다.
  대조 키 = (케이스-반복, alert_type, tag, 이벤트 시각 오프셋 ms). 도구 `harness/tools/stage2_compare.py`
  (정상 입력: EXP-L4 m1 flink22↔flinksql 263=263 동일, m4 cep↔flinksql 259=259 동일 / 깨진 입력: 시드 다른 리플레이는 비교 거부, CEP 1건 삭제·USL 1건 1초 이동 → only_cand 1·only_ref 2 로 검출 — 2026-09-29 확인).
- 기본 리플레이 = `--repeat 10 --jitter --seed 1001` = EXP-L4 **m1** 조건(V1 Flink 1.20.1 알람 `experiments/EXP-L4/raw/alerts_m1_flinksql.jsonl` 이 있음). 3회 반복은 `SEED=1001/2002/4004`(m1·m2·m4, m3 는 자원 무효지만 알람은 유효).
- ML(TIER2_ML) 알람은 처리시각 타이머라 규칙 대조에서 빼고 S13(`harness/tools/s13.py`, 점수 1e-6·clean 보간)으로 따로 잰다(`run_l4_multi.sh` 와 같은 원칙).
- **먼저 V1 재현성**: `harness/l4bench/stage2.sh flinksql` 을 SEED=1001 로 돌려 m1 과 대조한다. 차이가 나면 교차 실행 대조의 잡음 바닥이므로 후보 대조 전에 원인부터 본다.
- **규칙 시도 기록**: 배포 스크립트·앱이 V1 규칙(TH·ZS·CEP·ML)을 엔진에 실제로 내 보고 성공·엔진 오류 원문을 `experiments/EXP-L4/raw/stage2_<run>_attempts.jsonl` 에 남긴다. 결과 JSON 의 `attempts`·`rules_by_execution`(accepted/rejected). 한 규칙이 거부돼도 나머지는 계속 배포한다(임계치조차 안 되면 배포 실패).
  엔진에 시도할 기능 자체가 없는 경우(라이브러리에 해당 API·모듈이 없음)는 "API 조사" 또는 "미시도(사유)"로 기록한다 — 이 경우는 엔진 오류 메시지가 아니므로 결과표에 구분해 적는다.

## 2. 실행기 `harness/l4bench/stage2.sh <profile> [run_id]`

순서: 메모리 가드(`rot-iiot`·`rot-ai` 컨테이너가 있으면 거부, `FORCE=1` 로 무시) → 지난 실행의 후보 상태 볼륨 삭제 → (필요 시) 이미지 빌드 → Kafka+토픽 → 후보 서비스 `up --wait` → 규칙 배포(시도 기록) → 사전 점검(Flink 는 REST 잡 수) → 리플레이 + `sample_stats.sh` 자원 표본 → `evaluate.py` 케이스 판정 → `stage2_compare.py` V1 대조 → (ONNX 경로가 있으면) S13 → (`R05=1` 이면) JobManager kill/start(`s09.sh`) → `experiments/EXP-L4/stage2_<profile>.json` 에 실행 1건 누적 → 후보·Kafka 컨테이너와 상태 볼륨 삭제(`KEEP=1` 이면 유지).
실패도 결과다: 멈춘 단계(`stopped_at`)와 사유를 JSON 에 남긴다(② 탈락 근거). 로그 `experiments/EXP-L4/raw/stage2_<run>.log`.

```bash
cd /d/work/study/scada-rotation
python harness/l4bench/prepare.py                     # generated*/ 재생성(V1 SQL 사본, 토픽·호스트만 교체)
harness/l4bench/stage2.sh flinksql                    # V1 재현성 먼저
SEED=1001 harness/l4bench/stage2.sh flink23           # 후보
R05=1 harness/l4bench/stage2.sh flinkha               # HA 는 전체 재시작 복구까지
```

## 3. 준비한 후보 (profile)

규칙 약어: **TH** L4-01 임계치 · **ZS** L4-02 Z-Score · **CEP** L4-03/04 · **LATE** L4-05 워터마크 5초 · **ML** L4-12/12b ONNX·보간.
"시도" = ②에서 엔진에 실제로 내고 응답을 기록한다(문헌상 미지원이어도).

### 3-1. Flink 계열

| profile | 후보(우선) | 이미지(정확한 태그) | V1 규칙 → 엔진 기능 | 알려진 차이·확인 항목 | 메모리 | 명령 |
|---|---|---|---|---|---|---|
| `flinksql` | **V1 기준** Flink 1.20.1 | `iiot/flink-onnx:1.0`(V1 로컬 빌드), `apache/kafka:3.9.0` | V1 SQL 01~04 무수정 + V1 ONNX 잡 | — | 실측 1242 MiB 평균(EXP-L4 m5, JM+TM) | `harness/l4bench/stage2.sh flinksql` |
| `flink23` | Flink 2.3.0 (P1) | `l4bench-flink23:2.3.0` ← `candidates/l4-flink23/Dockerfile`: `flink:2.3.0-scala_2.12-java17` + `flink-sql-connector-kafka-5.0.0-2.2` + `flink-metrics-prometheus-2.3.0` + ONNX·CEP 잡 2.3 재컴파일(`maven:3.9.16-eclipse-temurin-17`) | V1 SQL 무수정(TH·ZS·CEP·LATE) + V1 ONNX 잡 소스를 2.3.0 API 로(ML) | **2.3 호환 Kafka 커넥터 공식 릴리스 없음**(Maven Central 최신 5.0.0-2.1·5.0.0-2.2) → 비공식 조합. ONNX·CEP 잡 2.3.0 컴파일은 로컬 통과(오프라인 예비) | 설정값 JM 800m + TM 1600m | `harness/l4bench/stage2.sh flink23` |
| `flinkcep23` | Flink 2.3 DataStream CEP (P2) | `l4bench-flink23:2.3.0`(같은 이미지에 `cep-job.jar` 포함) | 01~03 SQL(TH·ZS) + `candidates/l4-flink-cep` 를 2.3.0 으로 빌드한 CEP 잡 + ONNX. 알람 토픽 `cep`(2.2 판과 같음) | 커넥터 비공식 조합은 flink23 과 같음 | 위와 같음 | `harness/l4bench/stage2.sh flinkcep23` |
| `flinkha` | HA-A: ZK HA + 세션 (**P1**) | `zookeeper:3.9.5`, `${FLINKHA_IMAGE:-l4bench-flink22:2.2.1}` | V1 SQL + ONNX 잡(잡 4개). HA 저장소 `checkpoints/ha`(공유 볼륨), JM·TM `restart: unless-stopped` | 고친 것: root 소유 볼륨이라 HA 저장소를 못 쓰던 구성, ONNX 잡 미제출, clean/score 토픽 없음. SQL 클라이언트 잡의 JM 재시작 후 복구는 문서 명시 없음 → `R05=1` 실측 | JM 800m + TM 1600m + ZK | `R05=1 harness/l4bench/stage2.sh flinkha` (2.3 판 `FLINKHA_IMAGE=l4bench-flink23:2.3.0`) |
| `flinkhab` | HA-B: ZK HA + 애플리케이션 모드 (P2) | `l4bench-flinkhab-sql:2.2.1`·`l4bench-flinkhab-onnx:2.2.1` ← `candidates/l4-flinkhab/Dockerfile`(`--target sql/onnx`, BASE 기본 `l4bench-flink22:2.2.1`) | 애플리케이션 클러스터 2개: sql = `standalone-job --job-classname exp.SqlRunner app.sql`(V1 01~04 합본을 StatementSet 잡 1개로 — `candidates/l4-flink-sqlrunner`, 공식 flink-sql-runner-example 과 같은 연결 코드) · onnx = `standalone-job ... AnomalyJob`. 클러스터별 HA cluster-id, 공유 체크포인트 볼륨 | HA 애플리케이션 모드는 클러스터당 잡 1개라 V1 의 SQL 잡 3개가 1개로 묶인다(규칙 내용 동일). Flink 2.2 이미지에 SQL 애플리케이션 실행 진입점이 없어(sql-gateway 의 `ScriptRunner` 는 main 없음, 이미지 jar 조사) 실행기를 만듦. SqlRunner 문장 분리는 V1 SQL 로 12문장 정상(로컬) | **단독 실행 필수(설정 메모리 약 4.8GB)** — JM·TM 2벌 + ZK, 다른 측정·후보와 동시 실행 금지 | `R05=1 harness/l4bench/stage2.sh flinkhab` (2.3 판 `FLINKHAB_BASE=l4bench-flink23:2.3.0 FLINKHAB_FLINK=2.3.0`) |
| `flinkhac` | HA-C: 보존 체크포인트 + 재제출 스크립트 (P2) | `${FLINKHA_IMAGE:-l4bench-flink22:2.2.1}` | V1 SQL·ONNX 잡을 잡별로 제출, 복구 `submit-flinkhac recover` 가 jid 별 최신 `chk-*` 로 재제출 — `recover_hac.sh`(연결 로직) | 자동 복구 아님 | JM 800m + TM 1600m | `R05=1 harness/l4bench/stage2.sh flinkhac` |
| `flinkhad` | HA-D: group-offsets 재개 (P2) | 위와 같음 | SQL 소스만 `group-offsets`(처음 latest) | 윈도·CEP 상태는 잃음. ONNX 잡은 코드상 latest 고정 | 위와 같음 | `R05=1 harness/l4bench/stage2.sh flinkhad` |
| `flink22`·`flinkcep` | 기존(측정 완료 #18 / EXP-111) | `l4bench-flink22:2.2.1` | 변경 없음 | — | 설정값 | `harness/l4bench/stage2.sh flink22` |

### 3-2. 다른 엔진

| profile | 후보(우선) | 이미지(정확한 태그) | TH | ZS | CEP | ML | 알려진 차이·오프라인 예비 | 메모리 | 명령 |
|---|---|---|---|---|---|---|---|---|---|
| `ekuiper` | eKuiper 2.4.2 (P1) | `lfedge/ekuiper:2.4.2-full`(Kafka 는 -full 빌드만), 배포 `l4bench-tools:1.0` | WHERE/CASE 규칙 | 태그별 `COUNTWINDOW(60,1)` + `avg`/`stddevs` → memory → `COUNTWINDOW(5,1)` | 분석 함수 `latest()`/`lag() OVER(PARTITION BY device WHEN …)` 근사 | 시도: `onnx()` 함수 규칙 등록 + 설치 플러그인 목록 | 도착 순서(LATE 차이 예상), 첫 59행 미판정, Kafka `partition` 설정. 배포 스크립트는 가짜 엔진으로 정상·거부 경로 확인 | 문헌 없음 | `harness/l4bench/stage2.sh ekuiper` |
| `quix` | Quix Streams 3.26.0 (P1) | `l4bench-quix:3.26.0`(`python:3.12.8-slim` + `quixstreams==3.26.0` + `onnxruntime==1.20.1`) | `filter`/`apply` | 키(tag) 단위 `sliding_count_window(60).final()` + `Count/Sum/Last` → `(5)` | API 조사(패턴·CEP 메서드 유무) 기록 | 시도: `group_by(device)` → `tumbling_window(1s)` 태그별 `Latest` → 상태 저장 직전값 → `sliding_count_window(10)` `Collect` → onnxruntime → score·ML 알람. V1 은 처리시각 1초 표본이라 S13 steady(장치당 1행)에선 창이 안 닫혀 점수 누락 가능 — ②에서 확인. 보간(L4-12b) 없음 | 오프라인 예비(비판정): 파이프라인 구성은 로컬에서 통과(창 이름 중복 오류를 이 점검으로 찾아 고침), 실행 미검증 | 문헌 없음 | `harness/l4bench/stage2.sh quix` |
| `kstreams` | Kafka Streams 4.3.1 (P2) | `l4bench-kstreams:4.3.1` ← `maven:3.9.16-eclipse-temurin-17` → `eclipse-temurin:17.0.20_8-jre` | `filter` + `mapValues` | 키(tag) 단위 `groupByKey().aggregate()` 로 최근 60행·5행을 KTable 상태에(캐시 0 = 행마다 방출). **경계**: 행 수 창이 DSL 에 없어 창 모양은 집계 함수 안 목록 — 약점 열 표시 | 미시도(DSL 에 패턴 연산 없음, Processor API 는 CEP 엔진 재구현) 기록 | 미시도(결정 5: CEP ② 실패 확정 후 생략) 기록 | **오프라인 예비(비판정)(TopologyTestDriver, V1 m1 입력 9,599건을 발행 순서대로)**: TH 170 = V1 170, ZS 55 vs V1 53(차이 2 = S07 늦은 레코드 — V1 은 워터마크로 버리고 KS 는 도착 순서로 포함), CEP 0 vs 40 | 문헌 없음 | `harness/l4bench/stage2.sh kstreams` |
| `risingwave` | RisingWave v3.1.0 (P2) | `risingwavelabs/risingwave:v3.1.0`(`single_node --total-memory-bytes 3 GiB --parallelism 2`), 배포 `public.ecr.aws/docker/library/postgres:17.6-alpine` | 임시 조인 | ROWS OVER 창 + `EMIT ON WINDOW CLOSE` | 시도: V1 MATCH_RECOGNIZE 그대로(`04_cep_attempt.sql`) | 시도: 내장 Python UDF `import onnxruntime`(`05_onnx_attempt.sql`) | 규칙 파일별 성공·오류 기록(`deploy.sh`). 오류 문자열 JSON 변환은 로컬 sh 로 확인 | **문헌 최소 8 GiB**, 3 GiB 설정은 문서에 없는 값(사람 결정 2) — `RW_TOTAL_MEMORY_BYTES` 로 조정 | `harness/l4bench/stage2.sh risingwave` |
| `proton` | Timeplus Proton 3.0.31 (P2) | `d.timeplus.com/timeplus-io/proton:3.0.31`, 배포 `l4bench-tools:1.0` | 외부 스트림 ↔ `table()` 조인 MV | 시도: ROWS OVER + `stddev_samp` MV | 시도: MATCH_RECOGNIZE MV | 시도: Python UDF `import onnxruntime` | 배포 스크립트 가짜 엔진 정상·거부 확인 | 문헌 0.5 GiB 사례 | `harness/l4bench/stage2.sh proton` |
| `arroyo` | Arroyo 0.15.0 (P3) | `ghcr.io/arroyosystems/arroyo:0.15.0` | CASE 식 파이프라인 | 시도: ROWS OVER 파이프라인 | 시도: MATCH_RECOGNIZE 파이프라인 | 시도: `/udfs/validate` Python `import onnxruntime` | 위와 같음 | 문헌 없음 | `harness/l4bench/stage2.sh arroyo` |
| `storm` | Apache Storm 3.1.0 (P3) | `zookeeper:3.9.5` + `storm:3.1.0`(nimbus·supervisor) + 제출 `l4bench-storm:3.1.0`(`maven:3.9.16-eclipse-temurin-25` 빌드, Storm 3 = Java 25) | 라우팅 볼트 필터 | 태그별 스트림 → 태그별 창 볼트 `Count(60)/Count(1)` → `Count(5)/Count(1)` | 미시도(CEP 모듈 없음, Storm SQL 2.8.2 로 끝) 기록 | 미시도(결정 5) 기록 | 도착 순서, 최소 한 번(중복 가능). 로컬 JDK 25 로 컴파일 통과 | 문헌 없음, `worker.childopts -Xmx768m` | `harness/l4bench/stage2.sh storm` |
| `beam` | Apache Beam 2.76.0 Java + DirectRunner (P3) | `l4bench-beam:2.76.0`(2.77.0 은 RC — Maven Central·PyPI 정식 최신 2.76.0) | SqlTransform | 시도: ROWS OVER SQL(그대로 → 레코드 단위 트리거 창) | 시도: MATCH_RECOGNIZE(그대로 → 트리거 창, WITHIN 포함 → 안 되면 WITHIN 없이) | 미시도(결정 5, Java 에 RunInference 없음) 기록 | **오프라인 예비(비판정)(로컬 JVM, 파이프라인 구성 단계 엔진 응답)**: TH 수용 · ZS 두 형태 모두 거부 `CannotPlanException … convention=BEAM_LOGICAL`(OVER 창 계획 불가) · CEP 그대로는 거부 `GroupByKey cannot be applied to non-bounded PCollection in the GlobalWindow without a trigger`, 트리거 창 + WITHIN 10초 형태는 **수용** → ②에서 실제 매칭 여부 확인(레코드 단위 discarding 트리거에서 패턴이 창을 넘어 매칭되는지가 관건) | 문헌 없음, `-Xmx1g` | `harness/l4bench/stage2.sh beam` |
| `streampipes` | Apache StreamPipes 0.98.0 (P3) | `apachestreampipes/backend:0.98.0`, `apachestreampipes/extensions-all-iiot:0.98.0`, `couchdb:3.3.1`, `nats:2.15.0`, `influxdb:2.6`(공식 installer/compose release/0.98.0 구성, UI 제외), 배포 `l4bench-tools:1.0` | Kafka 어댑터 → 규격마다 파이프라인(숫자+문자 필터 `numericaltextfilter` → 정적 메타데이터로 alert_type 등 추가 → Kafka 싱크), 13개 | 시도: 태그마다 문자 필터 → **Welford 변화 탐지**(누적 평균·분산 CUSUM, 이동 표준편차 요소 없음) → 불리언 필터 → ZSCORE 메타데이터 → 싱크. V1 의미(60행 창·z>3.5·5중 3)와 다름 | 시도: **Siddhi 순서 요소**(`processors.siddhi.sequence`, 입력 2 = 과전류 필터·진동 필터, duration 10). 소스 확인: 이 요소의 Siddhi 문장은 `from every not <입력1> for N sec` 로 둘째 입력을 쓰지 않음 → ②에서 결과로 확인 | 설치 요소 검색(ONNX·모델 요소 없음 예상) | `candidates/l4-streampipes/deploy.py` 가 **REST 자동 조립**: 0.98 의 compact API(`/api/v2/connect/compact-adapters`, `/api/v2/compact-pipelines`, 소스 release/0.98.0 로 형식 확인). 어댑터는 만들 때 토픽 표본으로 스키마를 추정하므로 장치 `sp-warmup` 표본을 흘리며 만든다(판정 장치 아님). 오프라인 예비(비판정): 가짜 백엔드로 정상(파이프라인 26개 요청)·순서 요소 미설치·CEP 거부·어댑터 실패 4경로 확인 — 실제 백엔드가 이 형식을 받는지는 ② 첫 실행 | 문헌 수치 없음("enough memory") — 컨테이너 5개 | `harness/l4bench/stage2.sh streampipes` |

## 4. 규칙별 문헌 근거 (②에서 위 "시도"로 확인할 대상 — 문헌만으로 닫지 않음)

| 후보 | 규칙 | 문헌(2026-09-29) |
|---|---|---|
| eKuiper | CEP 문법 없음, ONNX 는 네이티브 플러그인 | https://github.com/lf-edge/ekuiper/blob/v2.4.2/docs/en_US/sqls/functions/analytic_functions.md · https://github.com/lf-edge/ekuiper/blob/v2.4.2/docs/en_US/guide/ai/onnx.md |
| Quix Streams | CEP·처리시각 타이머 없음 | https://quix.io/docs/quix-streams/windowing.html |
| RisingWave | MATCH_RECOGNIZE 없음, 내장 Python UDF 서드파티 불가 | https://github.com/risingwavelabs/risingwave-docs/blob/main/reference/rw-flink-feature-comparison.mdx · https://github.com/risingwavelabs/risingwave-docs/blob/main/sql/udfs/embedded-python-udfs.mdx |
| Proton | 스트리밍 행 프레임·stddev·MATCH_RECOGNIZE 문서 없음 | https://github.com/timeplus-io/docs/blob/main/docs/functions_for_agg.md |
| Arroyo | 창 함수는 스트리밍 창 필요, MATCH_RECOGNIZE 없음 | https://github.com/ArroyoSystems/arroyo-docs/blob/main/src/content/docs/sql/window-functions.mdx |
| Kafka Streams | 창은 시간 기반뿐, 패턴 연산 없음 | https://kafka.apache.org/43/streams/developer-guide/dsl-api/ |
| Storm | Storm SQL 2.8.2 가 마지막, CEP 모듈 없음 | https://storm.apache.org/2025/08/03/storm282-released.html |
| StreamPipes | 0.98 처리기 목록에 Sequence·ONNX 없음 | https://github.com/apache/streampipes-website/tree/dev/website-v2/versioned_docs/version-0.98.0 |
| Beam | Beam SQL "MATCH_RECOGNIZE: No", "Window functions: No" — **오프라인 예비에서 MATCH_RECOGNIZE 는 트리거 창과 함께 구성 단계를 통과**(문헌과 다름, ②에서 결과 확인) | https://github.com/apache/beam/blob/master/website/www/site/content/en/documentation/dsls/sql/calcite/overview.md |

## 5. ① 관문 제외

| 후보 | 근거(사실·URL·날짜) | 선례 |
|---|---|---|
| **Feldera 0.357.0** (P3) | "Checkpoints & fault tolerance features are only available in Feldera Enterprise Edition" — https://github.com/feldera/feldera/blob/main/docs.feldera.com/docs/pipelines/fault-tolerance.md (2026-09-29 확인). 재시작 복구(R04·R05)가 키로 여는 상용 기능 = QUESTIONS §1 ① "키로 여는 기능" | Hazelcast(#74, 재시작 복구·Jet 무손실 복구 Enterprise 전용) |

## 6. 남은 결정·주의

- **HA-B: 단독 실행 필수(설정 메모리 약 4.8GB).** 다른 측정·후보와 동시에 돌리지 않는다.
- **ONNX 미이식(결정 5)**: Kafka Streams·Storm·Beam 의 L4-12 는 "미시도(결정: CEP ② 실패 확정 후 생략)"로 기록한다. ② 에서 CEP 가 통과하는 경우에만 다시 판단한다.
- **StreamPipes REST 자동화의 한계**: compact API 형식은 0.98.0 소스로 맞췄지만 실제 백엔드에 낸 적은 없다. ② 첫 실행에서 어댑터 스키마 추정·파이프라인 검증이 거부되면 그 응답 원문이 시도 기록에 남는다 — 그때 원인이 우리 요청 형식인지 엔진 제약인지 먼저 가른다(형식 문제면 고쳐 재시도, 엔진 제약이면 ② 결과).

## 7. 이미지 (받아 둔 것, 2026-09-29)

| 이미지 | 용도 | 크기 |
|---|---|---|
| `flink:2.3.0-scala_2.12-java17` | flink23·flinkcep23 기반 | 701 MB |
| `maven:3.9.16-eclipse-temurin-17` | Flink 2.3·HA-B·Kafka Streams·Beam 빌드 | 232 MB |
| `maven:3.9.16-eclipse-temurin-25` | Storm 토폴로지 빌드 | 176 MB |
| `eclipse-temurin:17.0.20_8-jre` | Kafka Streams·Beam 실행 | 109 MB |
| `zookeeper:3.9.5` | flinkha·flinkhab·storm | 117 MB |
| `storm:3.1.0` | storm | 454 MB |
| `lfedge/ekuiper:2.4.2-full` | ekuiper | 143 MB |
| `risingwavelabs/risingwave:v3.1.0` | risingwave | 2,523 MB |
| `public.ecr.aws/docker/library/postgres:17.6-alpine` | risingwave 배포(psql) | 110 MB |
| `d.timeplus.com/timeplus-io/proton:3.0.31` | proton | 342 MB |
| `ghcr.io/arroyosystems/arroyo:0.15.0` | arroyo | 269 MB |
| `apachestreampipes/backend:0.98.0` · `extensions-all-iiot:0.98.0` | streampipes | 247 · 424 MB |
| `couchdb:3.3.1` · `nats:2.15.0` · `influxdb:2.6` | streampipes | 90 · 7 · 98 MB |
| 합계 | | **약 6.0 GB**(이미지 크기 합) |

빌드 이미지(`l4bench-flink23`, `l4bench-flinkhab-sql/onnx`, `l4bench-quix`, `l4bench-kstreams`, `l4bench-storm`, `l4bench-beam`)는 stage2 첫 실행에서 만든다(빌드 컨테이너 메모리 때문에 준비 단계에서 만들지 않음). `candidates/.dockerignore` 가 `target/` 을 빌드 컨텍스트에서 뺀다. `l4bench-tools:1.0` 은 기존 이미지에 태그만 붙였다.

## 8. 검증 상태 (2026-09-29)

| 항목 | 상태 |
|---|---|
| `docker compose -f harness/l4bench/compose.yml --profile '*' config -q` | 검증됨(통과) |
| `bash -n` stage2.sh·recover_hac.sh, `sh -n` risingwave deploy.sh, Python 배포 스크립트 구문 | 검증됨 |
| stage2.sh 메모리 가드(rot 스택 실행 중 거부, 종료 코드 3) | 검증됨 |
| stage2.sh 결과 기록부(기존 m1 파일 + 시도 기록으로 JSON·`rules_by_execution` 생성) | 검증됨 |
| `stage2_compare.py` 정상·깨진 입력 | 검증됨(1절) |
| eKuiper·Proton·Arroyo 배포 스크립트: 가짜 엔진 HTTP 서버로 정상(전 규칙 등록)·거부(CEP·ONNX 거부 시 기록하고 계속, 임계치 거부 시 배포 실패) | 검증됨(로컬, 엔진 아님) |
| Java 컴파일: Flink 2.3 ONNX·CEP 잡, Kafka Streams, Beam, SqlRunner(JDK 17), Storm(JDK 25) | 검증됨(로컬 Maven) |
| Kafka Streams 규칙 = TopologyTestDriver 로 V1 m1 입력 대조 | 오프라인 예비(비판정)(3-2 표) |
| Beam 규칙 = 로컬 JVM 파이프라인 구성 단계 엔진 응답 | 오프라인 예비(비판정)(3-2 표) |
| Quix 파이프라인 구성(Kafka 관리 API 대역) | 오프라인 예비(비판정)(구성 통과, 실행 미검증) |
| StreamPipes 배포 스크립트: 가짜 백엔드 4경로(정상·요소 미설치·CEP 거부·어댑터 실패) | 오프라인 예비(비판정) |
| 모든 후보의 기동·규칙 배포·알람·재시작 | **미검증**(실행 금지 조건). ② 첫 실행에서 확인 |
