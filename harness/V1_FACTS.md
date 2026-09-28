# V1 사실 대조 (브리프 §4 ↔ 실제 코드)

브리프 §4와 코드가 다르면 코드가 맞다. 기준: `v1-original` (`def56b1`). 코드 읽기로 확인한 사실과, 실행으로 확인할 항목을 구분한다.

## 1. 🔧 입력값 중 코드에서 확정된 것

| # | 항목 | V1 값 | 근거 |
|---|---|---|---|
| I2 | 복합 패턴 창 N | 10초 | `flink/sql/04_tier1_cep.sql` `WITHIN INTERVAL '10' SECOND` |
| I3 | IT-102 상승 기준 | > 9.6 A (정격 8.0 A의 120%) | 같은 파일 `DEFINE OVERCURRENT`, `plant.yaml` usl |
| I3 | VT-101 상승 기준 | > 7.1 mm/s | 같은 파일 `DEFINE VIB`, `plant.yaml` usl |
| I4 | 워터마크 지연 | 5초 | `flink/sql/01_sources.sql` `WATERMARK ... - INTERVAL '5' SECOND` |

## 2. 브리프와 다른 점

| 브리프 서술 | 실제 코드 | 영향 |
|---|---|---|
| §4.1 "냉각 장치는 없다" | HX-102 가상 냉각기 있음: 코일 3 `cooler_enable`, 물리모델 `cooler`, 고장 `heater_stuck`·`cooling_loss`, C3 조치 `enable_cooling` | 시나리오·CQ에 냉각 조치 경로 포함 필요 |
| §4.1 대표 태그 TK-101·R-101 | TK-101·R-101·M-101·HX-101·CV-101은 설비명. 계측 태그 12개는 LT-101/102, TT-101/102, PT-101, FT-101/102, IT-101/102, VT-101, pH-101, CT-101 | 없음(표기만) |
| §11.4 EXP-141 기준선 = Flink DataStream CEP | V1 패턴 탐지는 이미 **Flink SQL MATCH_RECOGNIZE** (`PATTERN (OVERCURRENT OTHER*? VIB)`). 규칙·Z-Score·CEP 모두 SQL 파일, 자바 코드 없음. ONNX 잡만 자바(`flink/onnx-job`) | 기준선 = EXP-142 형태. DataStream CEP는 새 후보가 됨 → §11.4 재배치 필요(QUESTIONS Q1) |
| §4.3 C2 = "Vue → 백엔드 직접 제어" | Vue(`ai-web`) → `ai-knowledge` API `POST /control` (`simulation.py`). C2와 C3가 같은 서비스 | 없음 |
| §4.3 C3 = "Modbus 정지 명령" | 조치 3종: `stop_mixer`(코일 1←0), `enable_cooling`(코일 3←1), `inspect_only`(명령 없음) | S16~S21을 두 쓰기 조치 모두에 적용 |
| §4.3 C3 "알람 → 사건 → 사람이 분석 시작" | 사건 등록은 `consumer.py`가 자동. 분석은 별도 `POST /analyze` 호출 시에만 | 브리프와 일치(자동 분석 아님) |
| §8.6 결과값 FAILED / UNCONFIRMED | V1 상태값: `not_executed` / `uncertain` / `stop_verified` / `cooling_command_verified` / `verified`(C2) / `inspection_requested` | 게이트는 "SUCCESS류(`*_verified`)가 아닌지"로 판정 |
| §8.7 G5 `UNIQUE(approval_id)` 권장 | 제약 대신 행 잠금 + 상태머신: `decide()`가 `FOR UPDATE` 후 `status='executing'` 선점, 재요청은 `replayed`. C2는 `request_id` PK + advisory lock | 방식은 달라도 G5 의도 충족 구조. 실측으로 판정 |
| §8.7 G3 승인 만료 | 대응안 `expires_at = now()+5분`. 승인 시 사건 revision, 명령·인터록 fingerprint, 지식 fingerprint, 현재 이상 재확인. IO 직전에 한 번 더 확인 | 구현됨. 실측으로 판정 |
| (브리프 없음) | EdgeX를 우회하는 경량 경로 `make lite`: 시뮬레이터 → EMQX(`iiot/+/+/+`) → `bridge-lite.conf` | 게이트웨이 후보 비교 시 참고 |
| (브리프 없음) | `plant.yaml` 주석은 EdgeX Store-and-Forward가 "Redis에 적재"라고 하나, EdgeX 4.0은 PostgreSQL 사용(`edgex-postgres`) | 주석이 낡음 |

## 3. 인터페이스 (SCHEMA.md 작성 전 요약)

- MQTT: `edgex/telemetry` (EdgeX export) · `iiot/+/+/+` (lite) · `scada/alerts/{tag}` · `scada/hmi/latest-alert`
- Kafka: `sensor.telemetry.raw` (6파티션, 24h) · `sensor.telemetry.clean` (6, 24h) · `sensor.anomaly.score` (3, 24h) · `sensor.alerts` (3, 7일)
- raw 레코드(Flink 소스 정의 기준): `ts`(µs, BIGINT) · `site` · `device` · `tag` · `value` · `quality`. `trace_id`·발행 시각 필드 없음 → 하니스 쪽에서 추가 필요
- alerts 레코드: `ts, site, device, tag, value, alert_type(THRESHOLD_USL|THRESHOLD_LSL|ZSCORE|CEP_BEARING|ML_AUTOENCODER), severity, detector, detail`
- Modbus: 계측 HR 0~22(float32 2워드) · 코일 0 펌프, 1 교반기, 2 히터, 3 냉각기, 10 알람 확인, 20 인터록(읽기 전용) · HR 100 펌프 속도, 101 밸브 개도, 102 온도 SP×10 · HR 200 seq(UINT32)
- 이상 주입: `POST /fault {"scenario","duration_s"}`, 해제 `POST /fault/clear`. 시나리오 `heater_stuck, cooling_loss, dropout, spike, noise, bearing_wear(lag 6s), drift`
- 인터록: PT-101 > 6.5 barg 펌프 트립, 5.2 barg 해제
- 스캔 주기 1000 ms

## 4. 실험 전에 막아야 할 위험

1. **AI 서비스가 원본 V1 설비 주소를 코드에 고정해 두었다.** `actions.py:232`, `simulation.py:111`이 `host.docker.internal:27002`(원본 시뮬레이터 호스트 포트)로 Modbus 쓰기를 한다. 환경변수로 바꿀 수 없다. 실험 스택에서 ai-layer를 그대로 띄우면 **실험 조치가 지금 실행 중인 원본 V1에 쓰기를 보낸다.** 읽기 쪽 `/state`(27080)·InfluxDB(27086)·Flink(27081)도 기본값이 원본 포트다(환경변수 `SCADA_STATE_URL`·`INFLUX_URL`·`SCADA_FLINK_URL`로 변경 가능). → 실험 브랜치 첫 변경으로 Modbus 주소를 환경변수화하고, 실험 스택은 다른 호스트 포트를 쓴다. 이 변경은 동작 변화가 없는 위생 조치로 `v1-baseline`에 포함한다.
2. 원본과 같은 compose 프로젝트명(`iiot`, `ar100-ai`)과 `container_name`을 쓰면 원본 컨테이너를 교체해 버린다. 실험 스택은 프로젝트명·컨테이너명·포트를 모두 바꾼다.
3. 무시 파일은 worktree에 따라오지 않는다: `ai-layer/.env.local`(LiteLLM 키), `ml/*.onnx`·`ml/model_meta.json`. 키는 커밋하지 않고 복사만 한다.

## 5. 코드로 예상했지만 실행으로 확인할 항목

| 항목 | 코드상 예상 | 관련 |
|---|---|---|
| Flink 재시작 시 유실 | Kafka 소스 `scan.startup.mode = latest-offset`. 세이브포인트 없이 잡을 재제출하면 중단 동안의 이벤트를 건너뛸 수 있음 | S09, G8 |
| C2 범위 밖 입력 기록 | Pydantic 검증(422)에서 거부되어 `manufacturing_operator_commands`에 기록이 남지 않음 | S15 "기록" 기대 |
| C1(FUXA) 인터록 차단 | FUXA는 시뮬레이터에 직접 쓰기. 인터록 중 펌프 기동 차단은 시뮬레이터 물리모델 쪽 동작에 의존 | S16, G1 |
| EdgeX 쓰기 경로 | `edgex-core-command`(27882)가 장치 쓰기 API를 노출. C1~C3 외 쓰기 경로가 될 수 있음 | G7 |
| 모든 Modbus write 로그 | 시뮬레이터가 쓰기 주체·경로를 기록하는지 미확인. 없으면 하니스 훅 필요(§8.3) | G1~G7 |
| LiteLLM 프록시 버전 | Cloud Run `knu-litellm`. 2026-09-28 `/health/readiness` 무응답 | §6.2 |
