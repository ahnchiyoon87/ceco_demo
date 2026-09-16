# 4. Tier 3-A · 스트림 처리와 CEP

> 교재 활용: **5차시 — Flink SQL 로 하는 실시간 탐지** / **6차시 — CEP 와 MATCH_RECOGNIZE**

## 4.1 설계 의도

PDF 결론 2 는 명확합니다.

> 레거시 단일 JVM 엔진인 Esper/EQL 대신, Kafka 와 완벽히 결합하여 수평 확장과
> 무손실 상태 복구를 보장하는 Apache Flink(Flink CEP)를 채택해야 한다.

Tier-1 탐지(임계치·Z-Score·CEP) 전체를 **선언형 SQL 로만** 구현해
"Esper 의 EQL 을 Flink SQL 이 대체할 수 있다" 를 실증하기로 했습니다.

```
flink/sql/
├── 01_sources.sql       소스·싱크 정의 (Kafka, CSV, 알람 싱크)
├── 02_tier1_rules.sql   USL/LSL 임계치
├── 03_tier1_zscore.sql  롤링 Z-Score
└── 04_tier1_cep.sql     MATCH_RECOGNIZE 패턴 매칭
```

자바 코드가 한 줄도 없습니다.

---

## 4.2 ① 엔지니어링 임계치

규격은 `plant.yaml` 에서 CSV 로 생성해 Flink 의 filesystem 커넥터로 조인합니다.

```sql
CREATE TABLE tag_limits (
    `tag` STRING, unit STRING, lsl DOUBLE, usl DOUBLE,
    PRIMARY KEY (`tag`) NOT ENFORCED
) WITH ('connector'='filesystem', 'path'='file:///opt/flink/sql/tag_limits.csv',
        'format'='csv', 'csv.ignore-parse-errors'='true');

INSERT INTO alerts
SELECT t.ts, t.site, t.device, t.`tag`, t.`value`,
       CASE WHEN l.usl IS NOT NULL AND t.`value` > l.usl
            THEN 'THRESHOLD_USL' ELSE 'THRESHOLD_LSL' END,
       'CRITICAL', 'TIER1_RULE', CONCAT(...)
FROM telemetry_raw AS t JOIN tag_limits AS l ON t.`tag` = l.`tag`
WHERE (l.usl IS NOT NULL AND t.`value` > l.usl)
   OR (l.lsl IS NOT NULL AND t.`value` < l.lsl);
```

검증:

```
✓ spike → TIER1_RULE — PT-101 = 7.493 barg / 규격 [-, 6.0]
```

---

## 4.3 ② 롤링 Z-Score — 그리고 오탐과의 싸움

### 1차 구현

```sql
SELECT ..., AVG(`value`) OVER w AS mu, STDDEV_SAMP(`value`) OVER w AS sd
FROM telemetry_raw
WINDOW w AS (PARTITION BY `tag` ORDER BY event_time
             ROWS BETWEEN 59 PRECEDING AND CURRENT ROW)
...
WHERE z > 3.0
```

### 문제 발견

정상 운전 중에 알람이 계속 떴습니다.

```
[TIER1_ZSCORE] TT-101 = 71.87803 :: TT-101 z=3.09 (μ=72.319, σ=0.1431)
[TIER1_ZSCORE] TT-101 = 71.6813  :: TT-101 z=3.02 (μ=72.267, σ=0.1941)
```

2분간 8건. 고장을 넣지 않았는데도입니다.

### 원인 분석

autopilot 이 설정치를 완만히 바꾸면 공정값이 **단조 이동**합니다.
그러면 후행 이동평균이 뒤처져서, 통계적으로는 "3σ 이탈" 이지만
실제로는 정상적인 램프일 뿐인 상황이 생깁니다.

```
μ = 72.319,  현재값 = 71.878   → 차이 0.44
σ = 0.143 (윈도우 내 변동, 램프 때문에 부풀려짐)
z = 0.44 / 0.143 = 3.09
```

### 해결 — 지속성 요건

산업 현장의 표준 대응은 **"몇 번 연속으로 위반했는가"** 를 함께 보는 것입니다.

```sql
SUM(viol) OVER (PARTITION BY `tag` ORDER BY event_time
                ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS viol_run
...
WHERE viol_run >= 3    -- 최근 5샘플 중 3회 이상 위반
```

임계치도 3.0 → 3.5 로 올렸습니다.

### 결과

```bash
# 정상 운전 90초간 알람 수
0건
```

> **교육 포인트**: 통계적 이상 탐지를 실제 공정에 붙이면 거의 항상
> 이 문제를 만납니다. 해법은 세 가지 축으로 생각하면 됩니다.
> **(1) 임계치 상향 (2) 지속성/디바운스 (3) 추세 제거(detrending)**.
> 이 프로젝트는 (1)+(2) 를 썼습니다.

---

## 4.4 ③ CEP — MATCH_RECOGNIZE

### PDF 의 예시를 그대로

> "모터 전류가 정격의 120%를 초과한 후 10초 이내에 베어링 진동 센서의
> 진폭이 기준치를 상회하는 경우" (p.8)

```sql
MATCH_RECOGNIZE (
    PARTITION BY device
    ORDER BY event_time
    MEASURES
        LAST(VIB.ts) AS ts, LAST(VIB.site) AS site,
        'VT-101' AS `tag`, LAST(VIB.`value`) AS `value`,
        CONCAT('교반기 전류 ', CAST(ROUND(LAST(OVERCURRENT.`value`),2) AS STRING),
               'A (정격 120% 초과) 후 ',
               CAST(TIMESTAMPDIFF(SECOND, LAST(OVERCURRENT.event_time),
                                          LAST(VIB.event_time)) AS STRING),
               '초 내 진동 ', ..., 'mm/s 상회 → 베어링 열화 의심') AS detail
    ONE ROW PER MATCH
    AFTER MATCH SKIP PAST LAST ROW
    PATTERN (OVERCURRENT OTHER*? VIB) WITHIN INTERVAL '10' SECOND
    DEFINE
        OVERCURRENT AS OVERCURRENT.`tag` = 'IT-102' AND OVERCURRENT.`value` > 9.6,
        VIB         AS VIB.`tag`         = 'VT-101' AND VIB.`value`         > 7.1
)
```

### 함정 1 — PARTITION BY 컬럼을 MEASURES 에 다시 쓰면 안 됨

```
[ERROR] org.apache.flink.table.api.ValidationException: Columns ambiguously defined: {device}
```

`PARTITION BY device` 로 이미 출력에 포함되는데 `'M-101' AS device` 를
추가로 정의한 것이 원인이었습니다. 장비 식별자는 `tag` 필드로 옮겨 해결했습니다.

### 함정 2 — 패턴이 "연속된 두 행" 만 매칭

처음에는 `PATTERN (OVERCURRENT VIB)` 로 썼습니다. 매칭은 되는데 이런 결과가 나왔습니다.

```
교반기 전류 9.8A (정격 120% 초과) 후 0초 내 진동 7.12mm/s 상회
                                    ^^^^
```

**항상 0초**입니다. MATCH_RECOGNIZE 에서 `PATTERN (A B)` 는 A 다음에
**바로 이어지는 행**이 B 여야 합니다. 스트림에는 12개 태그가 1초마다 섞여 들어오므로,
두 조건이 **같은 스캔에서 동시에 참**이 될 때만 매칭됩니다.
이러면 시간 선후관계가 드러나지 않아 단순 AND 와 구별되지 않습니다.

해결: 중간 행을 건너뛸 수 있는 변수를 넣습니다.

```sql
PATTERN (OVERCURRENT OTHER*? VIB) WITHIN INTERVAL '10' SECOND
```

`OTHER` 는 DEFINE 이 없으므로 모든 행에 매칭되고, `*?` 는 reluctant 수량자라
최소한만 소비합니다.

### 시뮬레이터도 함께 고쳐야 했다

패턴을 고쳐도 여전히 0초였습니다. 시뮬레이터에서 전류와 진동이 **같은 열화 변수**를
공유해 거의 동시에 임계를 넘고 있었기 때문입니다. 진동을 별도 누적기로 분리했습니다.

```python
if "bearing_wear" in self.faults:
    f = self.faults["bearing_wear"]
    self.bearing_wear = min(1.0, self.bearing_wear + dt_s / 25.0)   # 전류: 즉시
    if f.elapsed >= f.lag_s:
        self.vib_wear = min(1.0, self.vib_wear + dt_s / 23.0)       # 진동: 지연 + 완만
```

6회 반복 시험으로 안정성 확인:

```
  시행1: IT-102 초과 t=21s → VT-101 초과 t=24s  간격=3s
  시행2: IT-102 초과 t=17s → VT-101 초과 t=23s  간격=6s
  시행3: IT-102 초과 t=21s → VT-101 초과 t=23s  간격=2s
  시행4: IT-102 초과 t=20s → VT-101 초과 t=24s  간격=4s
  시행5: IT-102 초과 t=20s → VT-101 초과 t=23s  간격=3s
  시행6: IT-102 초과 t=19s → VT-101 초과 t=23s  간격=4s
→ CEP 윈도우(10초) 내 순서 성립: 6/6 시행
```

### 최종 결과

```
✓ bearing_wear → TIER1_CEP
  교반기 전류 9.69A (정격 120% 초과) 후 7초 내 진동 7.21mm/s 상회 → 베어링 열화 의심
```

> **교육 포인트**: CEP 를 시연할 때 "패턴이 매칭됐다" 만으로는 부족합니다.
> **시간 간격이 실제로 0이 아닌지** 확인해야 진짜 시간 패턴을 잡은 것입니다.
> 그렇지 않으면 `WHERE a AND b` 로도 되는 일을 CEP 로 한 셈입니다.

---

## 4.5 잡 제출 자동화의 교훈

### "성공했다" 는 보고를 믿지 않기

```bash
# 제출기가 이렇게 보고했지만
▶ Tier-1 규칙 탐지 SQL 제출...
✓ Tier-1 SQL 제출 완료

# 실제로는
$ curl -s localhost:27081/jobs/overview
총 0개 잡
```

원인: sql-client 출력에 ANSI 색상코드가 섞여 `grep "^\[ERROR\]"` 가 매칭되지 않음.

```
\033[31;1m[ERROR] Could not execute SQL statement...
        ^^^^^^^^ 이것 때문에 행 시작 매칭 실패
```

### 수정 — 색상 제거 + 상태 기반 검증

```bash
${SQL_CLIENT} -f "${COMBINED}" 2>&1 | sed -E 's/\x1b\[[0-9;]*m//g' > /tmp/sql.log
grep -qE "^\[ERROR\]" /tmp/sql.log && { echo "✗ SQL 제출 실패"; exit 1; }

submitted=$(grep -c "^Job ID:" /tmp/sql.log)
[ "${submitted}" -lt 3 ] && { echo "✗ ${submitted}/3 만 제출됨"; exit 1; }

# 최종 확인은 텍스트가 아니라 실제 잡 상태로
running=$(curl -sf "http://${JM}/jobs/overview" | grep -o '"state":"RUNNING"' | wc -l)
[ "${running}" -lt 4 ] && { echo "✗ RUNNING ${running}/4"; exit 1; }
```

### 그 밖의 함정

| 증상 | 원인 | 해결 |
|---|---|---|
| `Connection refused` | 서버 config 의 `rest.address: 0.0.0.0` 은 바인드 주소라 클라이언트가 못 씀 | 클라이언트 전용 config 분리 |
| `InaccessibleObjectException` | 이미지 기본 config 를 덮어써 `env.java.opts.all` 이 사라짐 | 해당 옵션을 교체 파일에도 포함 |
| `python3: command not found` | Flink 이미지에 python3 없음 | 셸만으로 검증 로직 재작성 |
| 잡 이름이 전부 동일 | `01_sources.sql` 에 전역 `pipeline.name` 설정 | 파일별로 이름 부여 |

---

## 4.6 장애 복구 전략

TaskManager 하트비트 타임아웃으로 잡이 죽고 **복구되지 않는** 일이 있었습니다.

```
Caused by: java.util.concurrent.TimeoutException:
  The heartbeat of TaskManager with id flink-taskmanager:43157 timed out.
Recovery is suppressed by NoRestartBackoffTimeStrategy
```

Flink 의 기본값은 재시작하지 않는 것입니다. 체크포인트가 있으므로
자동 복구하도록 바꿨습니다.

```yaml
restart-strategy:
  type: exponential-delay
  exponential-delay:
    initial-backoff: 5s
    max-backoff: 2min
    backoff-multiplier: 2.0
heartbeat:
  timeout: 120000
taskmanager:
  memory:
    process:
      size: 4608m        # 3072m 에서 상향
```

> **교육 포인트**: "정확히 한 번(exactly-once)" 은 체크포인트만으로 되지 않습니다.
> **재시작 전략이 있어야 복구가 일어납니다.** 기본값이 `NoRestart` 라는 점을
> 모르면 "체크포인트를 켰는데 왜 복구가 안 되지?" 로 헤매게 됩니다.

---

## 4.7 실습 과제 (교재용)

1. `03_tier1_zscore.sql` 의 지속성 요건을 제거하고 정상 운전 5분간
   오탐 수를 세어 보시오. 임계치를 3.0/3.5/4.0 으로 바꿔 비교하시오.
2. `04_tier1_cep.sql` 에서 `OTHER*?` 를 제거하면 `detail` 의 초 값이
   어떻게 바뀌는지 관찰하고 이유를 설명하시오.
3. `WITHIN INTERVAL '10' SECOND` 를 `'2' SECOND` 로 줄이면 `bearing_wear` 가
   탐지되는지 확인하고, 시뮬레이터의 `lag_s` 와 연결지어 설명하시오.
4. 잡을 하나 강제 종료한 뒤(`docker compose kill flink-taskmanager`)
   체크포인트에서 복구되는 과정을 Flink UI 에서 관찰하시오.
