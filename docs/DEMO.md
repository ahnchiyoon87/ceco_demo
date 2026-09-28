# 시연 시나리오

각 시나리오는 PDF 의 특정 주장을 눈으로 확인하도록 구성되어 있습니다.
화면 두 개를 나란히 띄워 두고 진행하세요.

* **FUXA** http://localhost:27018 — P&ID 관제 및 제어
* **Grafana** http://localhost:27030 — 트렌드 · ML · 알람 · 인프라

---

## 0. 정상 운전 확인 (2분)

FUXA 화면에서 펌프·교반기 심볼이 초록색이고 수치가 갱신되는지 봅니다.
Grafana `AR-100 · 공정 트렌드` 에서 12개 태그가 흐르고 있어야 합니다.

```bash
make state      # 시뮬레이터 현재 상태
```

Autopilot 이 4분 주기로 설정치를 바꾸므로 값이 완만히 변동합니다.
이 변동이 오토인코더가 학습한 "정상 운전 영역" 입니다.

---

## 1. 양방향 SCADA 루프 — Grafana 로는 불가능한 것 (PDF p.11)

FUXA 제어 패널에서 **P-101 정지** 를 누릅니다.

관찰할 것:

1. FUXA 의 펌프 심볼이 회색으로 (전류 0A 구간 색상)
2. FT-101 공급유량이 0 으로
3. R-101 레벨이 서서히 하강
4. **Grafana 트렌드에도 3초 내로 같은 변화가 나타남**

4번이 핵심입니다. 제어 명령이 Modbus → 물리모델 → EdgeX → EMQX → Kafka →
Flink → InfluxDB → Grafana 전 구간을 돌아 온 것입니다.

속도 SP 를 85 로 바꾸면 유량과 펌프 전류가 함께 상승합니다.
다시 **기동** 을 눌러 원복하세요.

---

## 2. 안전 인터록 — 결정론적 안전 로직 (PDF p.11)

```bash
make fault-spike     # PT-101 순간 과압
```

관찰할 것:

1. PT-101 이 **6.0 barg를 초과**하면 FUXA 압력 배경이 주황색이고 Grafana 알람 대시보드에 `TIER1_RULE` / `THRESHOLD_USL` 사건이 남는지 확인
2. PT-101 이 실제로 **6.5 barg 이상** 도달한 경우에만 인터록이 1이 되고 공급 유량 `FT-101`이 0으로 떨어지는지 확인
3. 고장이 끝난 뒤 현재 압력·인터록이 돌아와도 `최근 분석 알람` 문구는 마지막 사건으로 남을 수 있음을 설명

스파이크를 주입해도 당시 기본 압력에 따라 6.5 barg에 못 미칠 수 있습니다. 이때 알람은 발생해도 인터록은 0일 수 있습니다. 인터록은 FUXA 가 아니라 현장 로직이 수행합니다. 실제 PLC 처럼 물리 진값이 아니라
**트랜스미터 지시값**을 참조하므로 계기 고장으로도 트립이 발생합니다.
Grafana 플러그인으로는 이런 결정론적 보장을 할 수 없습니다.

---

## 3. 결측치 보간 — 무결성을 지키면서 (PDF p.5)

```bash
make fault-dropout   # TT-101 을 15초간 끊음
```

관찰할 것 — Grafana `데이터 품질: 실측 vs 보간` 패널:

| 토픽 | 결과 |
|---|---|
| `process_raw` (원본) | TT-101 에 **15초 공백이 그대로 남음** |
| `process` (정제) | 공백이 채워지고 `quality=INTERPOLATED_LINEAR` 로 표시 |

원본을 덮어쓰지 않는 것이 요점입니다. 사고 조사 시 어느 값이 실측이고
어느 값이 추정인지 구분할 수 있어야 감사 추적이 성립합니다.

Kafka 에서 직접 확인:

```bash
docker exec kafka /opt/kafka/bin/kafka-console-consumer.sh \
  --bootstrap-server localhost:9092 --topic sensor.telemetry.clean \
  --timeout-ms 20000 2>/dev/null | grep INTERPOLATED | head -5
```

---

## 4. 복합 이벤트 처리 — Esper 를 대체한 Flink CEP (PDF 결론 2)

```bash
make fault-bearing   # 교반기 전류 상승 → 수 초 뒤 진동 상승
```

이 고장은 "모터 전류가 정격의 120% 를 넘은 후 10초 이내에 베어링 진동이
기준치를 상회" 라는 PDF p.8 의 예시를 그대로 재현합니다.

관찰할 것 — Grafana 알람 대시보드에 `TIER1_CEP` 알람:

```
교반기 전류 10.2A (정격 120% 초과) 후 1초 내 진동 7.4mm/s 상회 → 베어링 열화 의심
```

단일 센서 임계치로는 "전류가 높다", "진동이 높다" 두 개의 무관한 알람이 될 뿐입니다.
CEP 는 **시간적 선후관계**를 인과로 묶어 하나의 진단을 냅니다.

해당 SQL 은 [flink/sql/04_tier1_cep.sql](../flink/sql/04_tier1_cep.sql) 한 문장입니다.

---

## 5. 다변량 이상 탐지 — 임계치로는 불가능한 것 (PDF p.9)

이 예제에서 가장 중요한 시나리오입니다.

```bash
make fault-drift     # pH-101 과 CT-101 을 동시에 상승
```

**각 태그는 규격 안에 머무릅니다.** pH-101 은 7.4 → 약 7.95 로 오르지만
USL 8.4 를 넘지 않습니다. 따라서:

* Tier-1 임계치 → **알람 없음**
* Tier-1 Z-Score → **알람 없음** (변화가 완만해서)
* Tier-2 오토인코더 → **탐지**

정상 상태에서 pH 와 전도도는 **역상관**(corr ≈ −0.93)인데 이 고장은 둘을
**같은 방향으로** 움직여 상관 구조를 깨뜨립니다. 오토인코더는 "이 조합은
정상 운전에서 본 적이 없다" 를 재구성 오차로 표현합니다.

Grafana `AR-100 · ML 이상 탐지` 에서:

1. 재구성 오차가 임계선(빨간 점선) 위로 치솟음
2. **이상 기여도 상위 센서** 테이블에 `CT-101`, `pH-101` 이 상위로
3. 추론 지연은 여전히 1ms 미만

3번이 PDF p.10 의 "RPC Callout 지양" 근거입니다. 외부 추론 서버를 호출했다면
네트워크 왕복만으로 수 ms 가 더 들었을 것입니다.

---

## 6. Store-and-Forward — 무손실 수집 (PDF p.4)

```bash
make fault-netdown   # EMQX 를 30초 정지시킨 뒤 복구
```

EdgeX app-service 가 EMQX 로 반출하지 못한 이벤트를 DB 에 적재했다가
복구 시 순서대로 재전송합니다.

```bash
docker compose logs edgex-app-mqtt-export | grep -i "store"
```

`N stored items waiting for retry` 가 증가했다가 복구 후 0 으로 돌아옵니다.
EdgeX 내부 메시지버스는 별도 mosquitto 라서 EMQX 가 멈춰도
device-modbus → core-data 수집은 계속됩니다.

---

## 7. Exactly-once 상태 복구 (PDF p.6)

```bash
docker compose kill flink-taskmanager
docker compose up -d flink-taskmanager
```

Flink UI(http://localhost:27081) 에서 잡이 체크포인트로부터 복구되는 것을 봅니다.
RocksDB 상태(보간용 직전값, Z-Score 윈도우, CEP 부분 매치, 오토인코더 텐서 버퍼)가
그대로 되살아납니다. Esper 같은 단일 JVM 인메모리 엔진으로는 불가능한 부분입니다.

---

## 8. 역할 분리 — Prometheus 에 센서가 없다 (PDF p.7)

Prometheus(http://localhost:27090) 에서 `TT_101` 을 검색해 보세요. **없습니다.**

대신 이런 것들이 있습니다:

```promql
sum by (consumergroup, topic) (kafka_consumergroup_lag)
flink_jobmanager_job_lastCheckpointDuration
emqx_connections_count
```

컨슈머 랙을 인위로 만들어 경보를 확인하려면:

```bash
docker compose pause telegraf-sink     # InfluxDB 적재 중단 → 랙 증가
# Prometheus > Alerts 에서 KafkaConsumerLagHigh 관찰
docker compose unpause telegraf-sink
```

센서 데이터를 Prometheus 에 넣었다면 태그 조합 카디널리티 폭증으로
인덱스가 RAM 을 초과했을 것입니다. 이것이 두 시스템을 이원화하는 이유입니다.

---

## 전체 자동 검증

```bash
make verify
```

위 시나리오들을 스크립트가 순서대로 실행하고 결과를 판정합니다.
소요 시간 약 5분.
