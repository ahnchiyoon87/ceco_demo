# AR-100 반응기 라인 — IIoT / SCADA 실시간 파이프라인

`IoT SCADA 파이프라인 아키텍처.pdf` 가 권고한 오픈소스 스택을 **실제로 동작하는
SCADA 예제**로 구현한 것입니다. `docker compose up` 한 번으로 기동하며,
파이프라인 동작은 전부 설정 파일로 제어됩니다.

```text
현재값·제어: 시뮬레이터 ← Modbus 읽기·쓰기 → FUXA
분석·이력: 시뮬레이터 → EdgeX → EMQX → Telegraf bridge → Kafka
                                               → Flink → Kafka 결과
                                               → Telegraf sink → InfluxDB → Grafana
알람 회신: Kafka 알람 → Telegraf 재발행 → EMQX → FUXA 최근 분석 알람
```

처음 보는 분은 [FUXA 화면별 설명과 데이터 여행 이야기](docs/SCADA_화면과_데이터흐름_초보자_설명.md)부터 읽으세요. FUXA의 현재 수치와 제어는 Modbus 직통이고, 분석 알람만 파이프라인을 돌아옵니다.

---

## 빠른 시작

```bash
make up          # 전체 기동 (최초 실행은 빌드+모델학습으로 5~10분)
make urls        # 접속 주소 출력
make verify      # 전 계층 자동 검증
```

| 화면 | 주소 | 용도 |
|---|---|---|
| **FUXA** | http://localhost:27018 | P&ID 공정 관제 **+ 양방향 제어** |
| **Grafana** | http://localhost:27030 | 장기 트렌드 · ML 이상탐지 · 인프라 (admin/admin) |
| **Flink** | http://localhost:27081 | 잡 상태 · 체크포인트 · 백프레셔 |
| **Prometheus** | http://localhost:27090 | 파이프라인 인프라 감시 |
| **EMQX** | http://localhost:27183 | MQTT 브로커 (admin/public) |
| **EdgeX UI** | http://localhost:27040 | 디바이스·프로파일 관리 |
| **시뮬레이터** | http://localhost:27080/state | 공정 상태 · 고장 주입 API |

> 포트는 `.env` 에서 일괄 변경합니다. 개발 머신의 기존 서비스와 충돌하지 않도록
> 27000 대역으로 통일해 두었습니다.

---

## PDF 권고안 대비 구현 결과

| PDF 권고 | 구현 | 비고 |
|---|---|---|
| IoT 미들웨어 존치 (p.13 결론 1) | EdgeX Foundry 4.0 | Modbus→JSON 정규화, Southbound 명령, Store-and-Forward |
| Esper → Flink CEP 대체 (결론 2) | Flink SQL `MATCH_RECOGNIZE` | [04_tier1_cep.sql](flink/sql/04_tier1_cep.sql) |
| 선택적 결측치 보간 (결론 3) | Flink `Interpolator` | 원본 토픽은 무손실 유지, clean 에만 보간 + `quality` 표기 |
| 인라인 ML 추론 서빙 (결론 4) | Flink TaskManager 내 ONNX Runtime | 실측 추론 지연 **0.16~0.18 ms**, 네트워크 홉 0 |
| 저장소·시각화 이원화 (결론 5) | InfluxDB / Prometheus, FUXA / Grafana | Prometheus 에 센서 태그 **0건** |

### PDF 권고 중 오픈소스로 성립하지 않은 것 2가지

| # | PDF 전제 | 실사 결과 | 본 구현의 대안 |
|---|---|---|---|
| 1 | "EMQX 데이터 통합 브리지로 Kafka 적재" (p.10) | **EMQX Kafka Sink 는 Enterprise 전용**. OSS 5.x 에는 Rule Engine 만 있고 Kafka 프로듀서 커넥터가 없음 | **Telegraf** 브리지 (`mqtt_consumer` → `kafka`). PDF 가 Tier 4 에서 이미 Telegraf 를 언급하므로 스택 일관성 유지 |
| 2 | "Flink 내부에 C++ ONNX Runtime 임베디드" (p.10) | PyFlink 로는 불가 — **`apache-flink` 는 linux-aarch64 휠이 없음** (PyPI 에 macosx_arm64 / manylinux_x86_64 만 존재) | **Java Flink Job + `com.microsoft.onnxruntime`** (JNI→네이티브 C++). `linux-aarch64` 네이티브 번들 확인 완료. 원문 의도에 오히려 더 정확히 부합 |

---

## 공정: AR-100 반응기 라인

물리 모델(질량수지·에너지수지·헤드스페이스 압력)을 Python 으로 풀고
**Modbus/TCP 슬레이브**로 노출합니다. FUXA 에서 버튼을 누르면 레지스터가 바뀌고,
물리량이 반응하고, 그 변화가 전 구간을 거쳐 Grafana 트렌드까지 나타납니다.

계측 12점 · 제어 8점의 정의는 전부 [simulator/plant.yaml](simulator/plant.yaml) 한 파일에 있습니다.
이 파일이 EdgeX 디바이스 프로파일과 FUXA 프로젝트의 **단일 출처**입니다.

```bash
make regen-edgex   # plant.yaml 변경 → EdgeX 프로파일 재생성
make regen-fuxa    # plant.yaml 변경 → FUXA 화면 재생성 + 재주입
```

### 안전 인터록

PT-101 이 6.5 barg 이상이면 시뮬레이터 내부의 결정론적 로직이 P-101 공급을 차단합니다.
FUXA 가 아니라 현장 로직이 수행하며, 실제 PLC 처럼 **물리 진값이 아니라 트랜스미터
지시값**을 참조하므로 계기 고장으로도 트립이 발생합니다.

---

## 고장 주입 — 각 시나리오가 특정 탐지 계층을 검증

```bash
make fault-spike     # PT-101 과압   → Tier-1 임계치 + 고압 인터록
make fault-noise     # TT-101 분산↑  → Tier-1 롤링 Z-Score
make fault-bearing   # 전류↑→진동↑   → Flink CEP (MATCH_RECOGNIZE)
make fault-drift     # pH·전도도 상관붕괴 → Tier-2 Autoencoder (임계치로는 탐지 불가)
make fault-dropout   # TT-101 결측   → Flink 결측치 보간
make fault-netdown   # EMQX 30초 정지 → EdgeX Store-and-Forward 무손실
make fault-clear     # 전체 해제
```

`drift` 가 이 예제의 핵심입니다. 정상 상태에서 pH-101 과 CT-101 은 **역상관**
(측정 corr ≈ −0.93) 인데, 이 고장은 둘을 **동시에 상승**시켜 상관 구조를 깨뜨립니다.
각 태그는 규격(USL/LSL) 안에 머무르므로 **단일 임계치로는 절대 탐지되지 않고**,
다변량 Autoencoder 만 잡아냅니다.

학습 직후 자동으로 수행되는 판별력 검증 결과:

| 시나리오 | 평균 재구성오차 | 탐지율 | 담당 계층 |
|---|---|---|---|
| 정상 | 0.021 | **0.5 %** (오탐률) | – |
| drift | 55.8 | **100 %** | Tier-2 ML 전담 |
| bearing_wear | 146.1 | 100 % | Tier-1 CEP + Tier-2 |
| spike | 17.4 | 100 % | Tier-1 규칙이 선행 |
| noise | 0.031 | 3.6 % | Tier-1 Z-Score 전담 (ML 미반응이 정상) |

---

## 데이터 무결성 규약

**보간값은 원본을 절대 덮어쓰지 않습니다.** (PDF p.5)

| 토픽 / measurement | 내용 |
|---|---|
| `sensor.telemetry.raw` / `process_raw` | 무손실 원본. 결측 구간이 공백으로 그대로 남음 |
| `sensor.telemetry.clean` / `process` | 중복제거 + 보간 완료. `quality` 태그로 추정치 명시 |

`quality` 값: `GOOD` · `INTERPOLATED_LOCF` · `INTERPOLATED_LINEAR`

InfluxDB 에도 `quality` 가 태그로 저장되므로, 사고 발생 시 어느 값이 실측이고
어느 값이 추정인지 감사 추적이 성립합니다.

---

## 역할 분리 규약

**Prometheus 는 공정 센서 태그를 단 하나도 저장하지 않습니다.** (PDF p.7)

| | InfluxDB | Prometheus |
|---|---|---|
| 저장 | 12개 공정 태그, 이상 점수, 알람 이력 | 컨슈머 랙, 체크포인트, EMQX 세션, 컨테이너 리소스 |
| 수집 | Push (Line Protocol) | Pull (scrape) |
| 근거 | 나노초 정밀도 · 고카디널리티 대응 | 고카디널리티에 취약 (인덱스 RAM 초과) |

`make verify` 가 Prometheus 메트릭 목록에 공정 태그가 섞이지 않았는지 실제로 검사합니다.

---

## 프로파일

| 명령 | 구성 | 컨테이너 |
|---|---|---|
| `make up` | EdgeX 경유 (기본) | ~29개 |
| `make lite` | EdgeX 우회, 시뮬레이터 → EMQX 직결 | ~20개 |

lite 모드에서도 Kafka 진입 스키마가 동일하므로 **Flink 이후 전 계층이 완전히 동일하게**
동작합니다. 대신 프로토콜 정규화와 Store-and-Forward 시나리오는 검증할 수 없습니다.

---

## 디렉터리

| 경로 | 내용 |
|---|---|
| [simulator/](simulator/) | 물리 모델 · Modbus 슬레이브 · 고장 주입 API |
| [edgex/](edgex/) | 디바이스 프로파일 생성기 (plant.yaml → EdgeX YAML) |
| [emqx/](emqx/) | 브로커 설정 (QoS1 · 세션 영속) |
| [kafka/](kafka/) | 토픽 초기화 |
| [telegraf/](telegraf/) | MQTT→Kafka 브리지 · Kafka→InfluxDB 싱크 · 알람 재발행 |
| [flink/sql/](flink/sql/) | Tier-1 탐지 (선언형 SQL — 임계치·Z-Score·CEP) |
| [flink/onnx-job/](flink/onnx-job/) | Tier-2 탐지 (결측보간 + 임베디드 ONNX) |
| [ml/](ml/) | Autoencoder 오프라인 학습 + 판별력 자가검증 |
| [grafana/](grafana/) | 데이터소스·대시보드 프로비저닝 |
| [fuxa/](fuxa/) | P&ID 화면 생성기 + 자동 주입 |
| [prometheus/](prometheus/) | 스크랩 설정 · 파이프라인 경보 룰 |
| [scripts/verify.py](scripts/verify.py) | 전 계층 자동 검증 |

## 문서

| 문서 | 내용 |
|---|---|
| [ARCHITECTURE.md](ARCHITECTURE.md) | 설계 근거와 as-built 결과 |
| [docs/GOTCHAS.md](docs/GOTCHAS.md) | 구현 중 부딪힌 함정 22건 (요약) |
| [docs/DEMO.md](docs/DEMO.md) | 시연 시나리오 8종 |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | 운영·설정 변경·문제 해결 |
| [docs/VERIFICATION.md](docs/VERIFICATION.md) | 검증 항목과 실측 수치 |
| **[docs/journal/](docs/journal/)** | **구축 전 과정 기록 (교재용 1차 자료)** |

`docs/journal/` 은 PDF 한 편에서 동작하는 파이프라인까지 도달한 과정을
시간 순으로 남긴 것입니다. 성공 경로뿐 아니라 **막힌 지점과 진단 과정**,
실제 명령과 출력, 의사결정 기록(ADR), 실측 수치, 원본 로그를 포함합니다.
