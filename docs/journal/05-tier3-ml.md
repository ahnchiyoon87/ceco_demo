# 5. Tier 3-B · 머신러닝과 임베디드 추론

> 교재 활용: **7차시 — 스트림에서의 결측치 처리** / **8차시 — ONNX 임베디드 서빙**

## 5.1 왜 Java 인가 — 설계 변경의 재확인

PDF p.10 은 "Flink 태스크 매니저 프로세스 내부에 C++ 기반 ONNX Runtime 엔진을
임베디드 형태로 직접 로드" 를 권고합니다.

PyFlink 로 가려던 계획은 [1장 실사](01-analysis.md)에서 좌절됐습니다
(linux-aarch64 휠 없음). 대신 Java + `com.microsoft.onnxruntime` 를 썼는데,
이 JNI 는 **C++ 네이티브를 직접 감싸므로** PDF 의 표현에 오히려 더 정확합니다.

```bash
unzip -l onnxruntime-1.20.0.jar | grep linux-aarch64
#  ai/onnxruntime/native/linux-aarch64/libonnxruntime.so      13,648,160
#  ai/onnxruntime/native/linux-aarch64/libonnxruntime4j_jni.so   133,256
```

---

## 5.2 결측치 보간 — 무결성을 지키는 설계

### 핵심 원칙

PDF p.5 는 경고합니다.

> 원천 데이터 레벨에서 인위적으로 계산된 가공치를 덮어쓰게 되면 실제 물리
> 계측치와 추정치 간의 경계가 모호해져 향후 사고 발생 시 감사 추적(Audit Trail)의
> 법적·기술적 신뢰성을 훼손할 수 있다.

이를 **토폴로지로 강제**했습니다.

```
sensor.telemetry.raw    ← 원본. 공백이 공백으로 남는다. 아무도 쓰지 않는다.
        │
        └─ Interpolator ─→ sensor.telemetry.clean   ← 보간값 + quality 표기
```

### 구현

```java
public class Interpolator extends KeyedProcessFunction<String, Reading, Reading> {

    public void processElement(Reading in, Context ctx, Collector<Reading> out) {
        // 멱등 처리: QoS1 재전송 중복 제거
        Long lastTs = lastEmittedTsNs.value();
        if (lastTs != null && in.ts <= lastTs) return;

        Reading prev = lastGood.value();
        if (prev != null) {
            long gapMs = in.millis() - prev.millis();
            if (gapMs > scanIntervalMs * 1.5) {      // 결측 구간 판정
                emitFill(prev, in, gapMs, out);
            }
        }
        out.collect(in);
        lastGood.update(in);
        lastEmittedTsNs.update(in.ts);
    }

    private void emitFill(Reading prev, Reading next, long gapMs, Collector<Reading> out) {
        boolean useLinear = "linear".equalsIgnoreCase(mode) && gapMs <= maxGapMs;
        String quality = useLinear ? "INTERPOLATED_LINEAR" : "INTERPOLATED_LOCF";
        for (int i = 1; i <= cap; i++) {
            double v = useLinear
                ? prev.value + (next.value - prev.value) * ((double) i / (missing + 1))
                : prev.value;
            out.collect(new Reading(tsNs, prev.site, prev.device, prev.tag, v, quality));
        }
    }
}
```

두 방식의 트레이드오프(PDF p.5 표)를 설정으로 노출했습니다.

| 모드 | 방식 | 장점 | 단점 |
|---|---|---|---|
| `locf` | 직전값 유지 | 지연 0 | 추세 단절 |
| `linear` | 공백이 닫힐 때 선형 보간 | 물리적 타당성 | 공백만큼 지연 |

`interpolation.max-gap-ms` 를 넘는 공백은 선형 보간을 포기하고 LOCF 로 대체해
장시간 단절 시 폭주를 막습니다.

### 검증 — 실제 출력

```
clean 토픽 총 660 건
  GOOD: 646건
  INTERPOLATED_LINEAR: 14건
  예시: TT-101 70.132 INTERPOLATED_LINEAR
  예시: TT-101 70.150 INTERPOLATED_LINEAR
  예시: TT-101 70.168 INTERPOLATED_LINEAR
  예시: TT-101 70.186 INTERPOLATED_LINEAR
  예시: TT-101 70.204 INTERPOLATED_LINEAR
```

값이 70.132 → 70.204 로 **균등 증가**합니다. 선형 보간이 정확히 동작합니다.

---

## 5.3 텐서 조립 — 왜 여기서는 LOCF 인가

오토인코더 입력은 **고정 차원의 완전한 행렬**이어야 합니다 (PDF p.5).
`clean` 토픽에서 선형 보간이 늦게 도착하더라도, 추론은 기다릴 수 없습니다.

그래서 텐서 조립 단계에서는 **직전 유효값(LOCF)으로 즉시 채웁니다.**

```java
double[] vec = new double[tagOrder.length];
int seen = 0;
for (int i = 0; i < tagOrder.length; i++) {
    Double v = latest.get(tagOrder[i]);
    if (v != null) { vec[i] = v; seen++; }
    else           { vec[i] = mean[i]; }   // 미관측 태그는 학습 평균
}
if (seen < tagOrder.length) return;        // 전 태그 관측 전에는 추론 안 함
```

> **교육 포인트**: 같은 "결측 처리" 라도 **목적에 따라 다른 방식**을 씁니다.
> 기록용(clean 토픽)은 정확성 우선 → 선형 보간.
> 추론용(텐서)은 지연 우선 → LOCF.
> 하나의 정책을 전 구간에 강제하면 둘 중 하나가 망가집니다.

---

## 5.4 임베디드 ONNX 추론

```java
public void open(Configuration cfg) throws Exception {
    env = OrtEnvironment.getEnvironment();
    OrtSession.SessionOptions opts = new OrtSession.SessionOptions();
    opts.setIntraOpNumThreads(1);   // 슬롯당 1스레드 — 슬롯 간 CPU 경합 방지
    session = env.createSession(modelPath, opts);
}

// onTimer 내부 — TaskManager 프로세스 안에서 직접 호출
try (OnnxTensor tensor = OnnxTensor.createTensor(env, new float[][]{flat});
     OrtSession.Result res = session.run(Map.of(inputName, tensor))) {
    recon = ((float[][]) res.get(0).getValue())[0];
}
```

### 측정된 지연

```
✓ 임베디드 서빙 지연 < 5ms — 평균 0.134ms — TaskManager 내부 직접 호출 (네트워크 홉 0)
```

**0.13~0.18 ms**. 외부 REST/gRPC 추론 서버를 호출했다면 네트워크 왕복만으로
수 밀리초가 추가됐을 것입니다. 이것이 PDF p.10 의 "RPC Callout 지양" 근거입니다.

### 기여 센서 역추적

```java
double mse = 0.0;
double[] perTag = new double[tagOrder.length];
for (int i = 0; i < dim; i++) {
    double d = flat[i] - recon[i];
    mse += d * d;
    perTag[i % tagOrder.length] += d * d;   // 태그 차원별 누적
}
mse /= dim;
// 기여도 상위 3개 태그를 역추적
```

---

## 5.5 오토인코더 학습 — 두 번의 실패

### 실패 1 — 학습할 상관 구조가 없었다

첫 시도에서 설정치를 고정한 정상 데이터로 학습했습니다. 그런데:

```
정상  : pH=7.413 CT=3.384  corr=-0.007   ← 상관이 없다
```

정상 상태에서 모든 태그가 거의 고정값 + 노이즈이므로,
오토인코더가 배울 것은 "각 태그의 평균" 뿐입니다.
그러면 **단일 태그 Z-Score 와 구별되지 않습니다.**

**해결**: 시뮬레이터에 autopilot(생산 스케줄에 따른 설정치 변동)을 추가.

```yaml
autopilot:
  enabled: true
  period_s: 240              # 설정치 재추첨 주기
  ramp_s: 45                 # 목표까지 완만히 이동
  ranges:
    pump_speed_sp: [45, 80]
    valve_open_sp: [35, 60]
    temp_sp_c:     [64, 80]
```

결과 — 물리적으로 타당한 상관 구조 형성:

```
  corr(FT-101, IT-101) = +0.989    유량 ↑ → 펌프 전류 ↑
  corr(TT-101, pH-101) = -0.980    온도 ↑ → pH ↓
  corr(LT-102, PT-101) = +0.936    레벨 ↑ → 헤드스페이스 압력 ↑
  corr(pH-101, CT-101) = -0.934    pH ↑ → 전도도 ↓   ← drift 가 깨뜨릴 대상
  corr(LT-102, IT-102) = +0.764    레벨 ↑ → 교반 부하 ↑
```

### 실패 2 — 판별력 검증이 무의미한 결과를 냄

학습은 잘 됐습니다(val loss 0.0196). 그런데 자가검증 결과가 이랬습니다.

```
═══ 모델 판별력 자가 검증 ═══
  정상             평균오차 0.06669  탐지율  49.0%   (오탐률)
  drift          평균오차 0.05256  탐지율  43.9%
  bearing_wear   평균오차 0.05714  탐지율  50.5%
  noise          평균오차 0.06053  탐지율  53.1%
```

**정상 오탐률 49%, drift 탐지율 43.9%** — 정상보다 낮습니다. 완전히 무용지물입니다.

#### 원인

검증 코드의 한 줄이었습니다.

```python
# 잘못됨 — 태그마다 step() 을 호출
rows = np.array([[plant.step(1.0)[t] for t in tags] for _ in range(seconds)])
```

12개 태그를 순회하며 `plant.step()` 을 **12번** 호출합니다. 그 결과:
- 한 행이 서로 다른 12개 시각의 값으로 조합됨 (상관 구조 파괴)
- 시뮬레이션 시간이 12배속으로 흘러 고장 램프가 왜곡됨

```python
# 올바름 — 스캔당 정확히 한 번
for i in range(seconds):
    r = plant.step(1.0)
    rows[i] = [r[t] for t in tags]
```

#### 수정 후

```
═══ 모델 판별력 자가 검증 ═══
  정상             평균오차 0.02053  탐지율   0.5%   (오탐률)
  drift          평균오차 55.76546  탐지율 100.0%   탐지되어야 함 (단일 임계치로는 불가)
  bearing_wear   평균오차 146.13240 탐지율 100.0%
  noise          평균오차 0.03104  탐지율   3.6%   Tier-1 롤링 Z-Score 담당
  spike          평균오차 17.42750  탐지율 100.0%
  임계치 = 0.07007
```

> **교육 포인트**: **모델 검증 코드의 버그는 모델 버그처럼 보입니다.**
> "모델이 나쁘다" 고 판단하기 전에 데이터 파이프라인부터 의심해야 합니다.
> 이 경우 정상 오탐률이 49% 라는 비정상적으로 높은 값이 단서였습니다
> (모델이 나쁘더라도 보통 이렇게까지 되지는 않습니다).

### 자가검증을 파이프라인에 넣은 이유

`train.py` 는 학습 후 **항상** 판별력을 검증하고 로그로 남깁니다.

```python
if __name__ == "__main__":
    main()       # 학습 + ONNX 익스포트
    validate()   # 판별력 자가검증
```

"학습 완료, val loss 0.0196" 만으로는 모델이 쓸모 있는지 알 수 없습니다.
**정상 오탐률과 시나리오별 탐지율을 함께 봐야** 판단이 가능합니다.

---

## 5.6 drift 시나리오 — 이 예제의 핵심

### 왜 이 시나리오인가

단일 임계치로 잡히는 이상은 ML 이 필요 없습니다.
**규격 안에 머무르면서도 비정상인** 상태여야 Tier-2 의 존재 이유가 생깁니다.

```python
# 정상 상태에서 pH↑ ⇒ CT↓ 이지만, 이 고장은 둘을 동시에 상승시켜
# 센서 간 상관 구조를 붕괴시킨다. 각 태그는 규격 내에 머무른다.
scale = 1.0 if tag == "pH-101" else 1.6
value += f.magnitude * ramp * scale
```

```
정상  : pH=7.413 CT=3.384  corr=-0.934   ← 역상관
drift : pH=7.950 CT=4.246  corr=+0.992   ← 동반 상승, 구조 붕괴
        pH 최대 7.978 (USL 8.4 여유 0.42) → 단일 임계치 무반응 확인
```

### 실제 탐지 결과

```
✓ drift → TIER2_ML
  재구성오차 0.03386 > 임계 0.02913
  기여 상위: CT-101(52%), pH-101(30%), IT-102(8%)
  추론 0.15ms
```

기여도 상위 두 개가 정확히 고장이 건드린 태그입니다.

### 함정 — 직전 시험의 잔여 영향

처음에는 이런 결과가 나왔습니다.

```
기여 상위: VT-101(69%), CT-101(19%), IT-102(3%)
```

VT-101 이 1위인데 drift 는 진동을 건드리지 않습니다.
직전에 실행한 `bearing_wear` 시험의 진동이 아직 회복 중이었습니다.

공정을 90초 안정화한 뒤 재실행하니 정상 결과가 나왔습니다.

> **교육 포인트**: 물리 공정은 상태를 갖습니다. 시험 간 **안정화 시간**을
> 두지 않으면 앞선 시험이 뒤 시험을 오염시킵니다.
> 이는 실제 플랜트 시운전에서도 동일하게 적용되는 원칙입니다.

---

## 5.7 Jackson 의존성 지옥

ONNX 잡이 계속 실패했습니다.

```
Caused by: java.lang.NoSuchMethodError:
  'com.fasterxml.jackson.core.JsonParser$NumberTypeFP
   com.fasterxml.jackson.core.JsonParser.getNumberTypeFP()'
```

### 1차 시도 — relocate

Flink 런타임의 Jackson 과 충돌한다고 보고 셰이드 시 재배치:

```xml
<relocations><relocation>
  <pattern>com.fasterxml.jackson</pattern>
  <shadedPattern>org.uengine.iiot.shaded.jackson</shadedPattern>
</relocation></relocations>
```

결과 — **같은 오류가 재배치된 이름으로 반복**:

```
NoSuchMethodError: 'org.uengine.iiot.shaded.jackson.core.JsonParser$NumberTypeFP ...'
```

즉, 충돌은 셰이드 JAR **내부**에 있었습니다.

### 2차 — 실제 버전 확인

```bash
docker run --rm -v "$PWD":/w -w /w maven:3.9-eclipse-temurin-17 \
  mvn -B dependency:list | grep -E "jackson-(core|databind|annotations):jar"
```

```
com.fasterxml.jackson.core:jackson-annotations:jar:2.17.2:compile
com.fasterxml.jackson.core:jackson-core:jar:2.15.2:compile        ← 불일치!
com.fasterxml.jackson.core:jackson-databind:jar:2.17.2:compile
```

`jackson-core` 만 전이 의존으로 2.15.2 가 선택됐습니다.

### 해결 — BOM

```xml
<dependencyManagement><dependencies><dependency>
  <groupId>com.fasterxml.jackson</groupId>
  <artifactId>jackson-bom</artifactId>
  <version>2.17.2</version><type>pom</type><scope>import</scope>
</dependency></dependencies></dependencyManagement>
```

```
com.fasterxml.jackson.core:jackson-annotations:jar:2.17.2:compile
com.fasterxml.jackson.core:jackson-core:jar:2.17.2:compile
com.fasterxml.jackson.core:jackson-databind:jar:2.17.2:compile
```

> **교육 포인트**: `NoSuchMethodError` 는 **컴파일 시점과 런타임의 클래스가 다르다**는
> 신호입니다. relocate 는 "외부와의 충돌" 을 막을 뿐 "내부 불일치" 는 못 막습니다.
> 두 겹을 구분해서 진단해야 합니다.

---

## 5.8 RocksDB 는 null 을 거부한다

```
Caused by: java.lang.IllegalArgumentException: The record must not be null.
  at org.uengine.iiot.OnnxScorer.onTimer(OnnxScorer.java:153)
```

153행:

```java
for (int i = 0; i < Math.min(n, steps - 1); i++) {
    window.put(i, window.get(i + 1));    // ← 아직 안 쓴 슬롯을 읽으면 null
}
```

윈도우가 차기 전에 좌측 시프트를 하면 `window.get(i+1)` 이 null 이고,
`MapState.put(key, null)` 은 RocksDB 백엔드에서 거부됩니다.

```java
// 수정 — 차기 전에는 덧붙이기만, 가득 찬 뒤에만 시프트
int n = filled.value() == null ? 0 : filled.value();
if (n < steps) {
    window.put(n, vec);
    filled.update(n + 1);
    if (n + 1 < steps) return;
} else {
    for (int i = 0; i < steps - 1; i++) window.put(i, window.get(i + 1));
    window.put(steps - 1, vec);
}
```

---

## 5.9 실습 과제 (교재용)

1. `ml/train.yaml` 의 `autopilot: false` 로 바꿔 재학습하고, 판별력 자가검증
   결과를 비교하시오. 왜 drift 탐지율이 떨어지는가?
2. `interpolation.mode` 를 `locf` 로 바꾸고 `dropout` 을 주입했을 때
   `clean` 토픽의 값 패턴이 어떻게 달라지는지 관찰하시오.
3. `threshold.percentile` 을 99.0 / 99.5 / 99.9 로 바꿔가며
   정상 오탐률과 drift 탐지율의 트레이드오프 곡선을 그리시오.
4. `window.steps` 를 10 → 1 로 줄이면 어떤 종류의 이상을 놓치게 되는가?
