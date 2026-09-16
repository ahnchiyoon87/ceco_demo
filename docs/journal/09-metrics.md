# 9. 실측 수치 전체

> 교재 활용: **평가 기준** — 수강생 구축 결과를 이 수치와 비교

측정 시각: 2026-09-16 20:00 KST
환경: macOS / linux-arm64 (Apple Silicon) / Docker 29.1.2 / 메모리 31GB

## 9.1 컨테이너 구성

```
NAME                    STATUS
alert-republisher       Up 2 hours
alertmanager            Up 3 hours
cadvisor                Up 3 hours (healthy)
edgex-app-mqtt-export   Up 3 hours
edgex-common-config     Up 3 hours
edgex-core-command      Up 3 hours
edgex-core-data         Up 3 hours
edgex-core-keeper       Up 3 hours
edgex-core-metadata     Up 3 hours
edgex-device-modbus     Up 3 hours
edgex-mqtt-broker       Up 3 hours
edgex-postgres          Up 3 hours (healthy)
edgex-ui                Up 3 hours
emqx                    Up 3 hours (healthy)
flink-jobmanager        Up About an hour (healthy)
flink-taskmanager       Up About an hour
fuxa                    Up 2 hours
grafana                 Up 3 hours
influxdb                Up 3 hours (healthy)
kafka                   Up 3 hours (healthy)
kafka-exporter          Up 3 hours
plant-simulator         Up About an hour (healthy)
prometheus              Up 3 hours
telegraf-bridge         Up 3 hours
telegraf-sink           Up 2 hours
```

총 서비스: 29개 (lite 프로파일 19개)

## 9.2 컨테이너별 리소스 (정상 운전, 12건/초)

| 컨테이너 | 메모리 | CPU |
|---|---|---|
| flink-taskmanager | 2.19 GiB | 2.0 % |
| kafka | 2.17 GiB | 2.2 % |
| flink-jobmanager | 1.16 GiB | 0.7 % |
| emqx | 269 MiB | 0.3 % |
| prometheus | 211 MiB | 0.0 % |
| cadvisor | 207 MiB | 3.6 % |
| influxdb | 106 MiB | 0.2 % |
| fuxa | 83 MiB | 0.6 % |
| telegraf-bridge | 81 MiB | 0.1 % |
| grafana | 80 MiB | 0.0 % |
| telegraf-sink | 56 MiB | 0.4 % |
| edgex-postgres | 54 MiB | 0.0 % |
| plant-simulator | 38 MiB | 0.2 % |
| alert-republisher | 26 MiB | 0.1 % |
| edgex-core-data | 18 MiB | 0.1 % |
| edgex-app-mqtt-export | 18 MiB | 0.1 % |
| edgex-device-modbus | 18 MiB | 0.1 % |
| kafka-exporter | 17 MiB | 0.0 % |
| alertmanager | 16 MiB | 0.1 % |
| edgex-core-keeper | 15 MiB | 0.0 % |
| edgex-core-metadata | 11 MiB | 0.0 % |
| edgex-core-command | 10 MiB | 0.0 % |
| edgex-ui | 6 MiB | 0.0 % |
| edgex-mqtt-broker | 1.3 MiB | 0.0 % |

**합계 약 9.1 GiB**, CPU 합계 약 11%.

관찰:
- **Flink(3.35 GiB)와 Kafka(2.17 GiB)가 전체의 60%** 를 차지한다. JVM 힙 설정 때문이며
  12건/초라는 부하 때문이 아니다.
- **EdgeX 9개 서비스 합계가 150 MiB** 에 불과하다. 컨테이너 수는 많지만
  Go 로 작성되어 개별 메모리 사용량은 작다. "컨테이너 수 = 무거움" 이 아니다.
- cadvisor 의 CPU 3.6% 가 전체에서 가장 높다. 감시 도구가 감시 대상보다
  자원을 더 쓰는 흔한 사례.

## 9.3 처리량

| 지표 | 측정값 | 측정 방법 |
|---|---|---|
| 센서 유입 | 12 건/초 | Kafka 오프셋 차분 (252건/20초) |
| EdgeX autoEvent | 1 이벤트/초 (12 리딩 묶음) | core-data `/event/count` 차분 |
| `telemetry.raw` → `clean` | 528 → 528 (40초) | 오프셋 차분, 손실 0 |
| `anomaly.score` | 1.1 건/초 | 오프셋 차분 (44건/40초) |
| 정상 운전 알람 | **0 건/90초** | 오프셋 차분 |

## 9.4 지연

| 구간 | 측정값 |
|---|---|
| **ONNX 추론 (임베디드)** | **0.126 ~ 0.180 ms** |
| Flink 체크포인트 간격 | 10 s (설정) |
| EdgeX 스캔 → Kafka 도달 | 1 s 이내 (육안 확인) |
| FUXA 제어 → 물리 반응 | 1 스캔(1s) 이내 |

## 9.5 이상 탐지 성능

### 오토인코더 판별력 (학습 시 자가검증, 400초 구간)

시드 고정(`model.seed: 42`) 후 **재현 가능**한 값입니다.
2회 연속 실행에서 임계치·오차·탐지율이 전부 동일함을 확인했습니다.

| 시나리오 | 평균 재구성오차 | 탐지율 | 담당 계층 |
|---|---|---|---|
| 정상 | 0.0126 | **0.0 %** | – (오탐률) |
| drift | 47.15 | **100 %** | Tier-2 전담 |
| bearing_wear | 100 % | 100 % | Tier-1 CEP + Tier-2 |
| spike | 100 % | 100 % | Tier-1 규칙 선행 |
| noise | 낮음 | 낮음 | Tier-1 Z-Score 전담 |

임계치 = **0.035081** (정상 재구성오차 p99.5 × 안전계수 1.15)

> 시드를 고정하기 전에는 실행마다 임계치가 0.070 ~ 0.082 로 흔들렸습니다.
> 물리 모델의 계측 노이즈가 표준 `random` 모듈을 쓰는데 `torch`/`numpy` 시드만
> 고정했기 때문입니다. 교재용으로는 세 가지를 모두 고정해야 합니다.

### 계층별 탐지 분담 (실측)

| 시나리오 | 탐지 계층 | 실제 알람 내용 |
|---|---|---|
| spike | `TIER1_RULE` | `PT-101 = 7.493 barg / 규격 [-, 6.0]` |
| bearing_wear | `TIER1_CEP` | `교반기 전류 9.69A (정격 120% 초과) 후 7초 내 진동 7.21mm/s 상회` |
| drift | `TIER2_ML` | `재구성오차 0.03386 > 임계 0.02913 · 기여 상위: CT-101(52%), pH-101(30%)` |

## 9.6 데이터 무결성

| quality | 건수 | 비율 |
|---|---|---|
| `GOOD` | 15,858 | 99.74 % |
| `INTERPOLATED_LINEAR` | 42 | 0.26 % |

dropout 15초 주입 시:
- `raw` 토픽 TT-101: **15.0초 공백** (대조군 LT-102 는 연속)
- `clean` 토픽 TT-101: **14건 보간** (70.132 → 70.204 균등 증가)

## 9.7 역할 분리 검증

```
Prometheus 메트릭 993종 중 공정 태그 0개
스크랩 타깃 7/7 정상: cadvisor, emqx, flink(×2), influxdb, kafka, prometheus
```

## 9.8 물리 모델 상관 구조 (오토인코더가 학습하는 것)

| 태그 쌍 | 상관계수 | 물리적 의미 |
|---|---|---|
| FT-101 ↔ IT-101 | +0.989 | 유량 ↑ → 펌프 부하 ↑ |
| TT-101 ↔ pH-101 | −0.980 | 온도 ↑ → pH ↓ |
| LT-102 ↔ PT-101 | +0.936 | 레벨 ↑ → 헤드스페이스 압축 → 압력 ↑ |
| pH-101 ↔ CT-101 | −0.934 | **drift 고장이 +0.99 로 뒤집는 대상** |
| LT-102 ↔ IT-102 | +0.764 | 레벨 ↑ → 교반 부하 ↑ |

## 9.9 정상 운전점 (50분 수렴)

| 태그 | 값 | 규격 [LSL, USL] |
|---|---|---|
| LT-101 | 82.70 % | [10, 95] |
| LT-102 | 54.31 % | [15, 90] |
| TT-101 | 70.91 °C | [40, 95] |
| TT-102 | 91.97 °C | [–, 125] |
| PT-101 | 3.22 barg | [–, 6.0] |
| FT-101 | 6.17 m³/h | – |
| FT-102 | 6.27 m³/h | – |
| IT-101 | 6.26 A | [–, 14.0] |
| IT-102 | 6.40 A | [–, 9.6] |
| VT-101 | 2.06 mm/s | [–, 7.1] |
| pH-101 | 7.42 | [6.2, 8.4] |
| CT-101 | 3.38 mS/cm | – |

TT-101 이 SP(72°C)에 정확히 닿지 않고 70.9 에 머무는 것은 P 제어의
정상상태 오차(droop)이며 물리적으로 올바른 거동이다.

## 9.10 양방향 제어 응답

| 동작 | FT-101 | IT-101 |
|---|---|---|
| 정상 운전 | 6.12 m³/h | 6.26 A |
| FUXA 에서 펌프 정지 | 0.03 | 0.04 |
| FUXA 에서 재기동 + 속도 85% | 8.79 | 7.88 |

## 9.11 빌드 시간

| 항목 | 최초 | 캐시 후 |
|---|---|---|
| 시뮬레이터 이미지 | ~30 s | 즉시 |
| Flink + ONNX 잡 (Maven 포함) | ~3 분 | 즉시 |
| 학습기 이미지 (PyTorch CPU) | ~2 분 | 즉시 |
| 오토인코더 학습 (6시간 데이터, 60 epoch) | ~90 s | – |
| EdgeX 부트스트랩 | ~60 s | ~40 s |
| **`make up` 전체** | **5~10 분** | **2~3 분** |

## 9.12 검증 실행 결과

```
Tier 1 · 현장 에지                                      3/3 통과
Tier 2 · 수집 & 백본                                    3/3 통과
Tier 3 · 스트림 처리 & ML                               7/7 통과
Tier 3 · 다층 이상 탐지 (spike/bearing_wear/drift)      3/3 통과
Tier 4 · 저장 · 감시 · 관제                             4/4 통과
Tier 4 · 웹 SCADA                                       3/3 통과
────────────────────────────────────────────────────────────────
합계                                                   23/23 통과
```
