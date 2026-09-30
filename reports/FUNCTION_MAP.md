# 기능 대응표 — V1 → 새 베이스 (HANDOFF §3-4)

V1이 하던 일을 잃지 않았는지, 빼거나 바꾼 부품마다 누가 대신하는지와 실측 근거를 적는다.
근거 파일은 모두 `experiments/`에 있다(BASE-VERIFY = 2026-09-30 새 베이스 검증). V1 기준값은 HANDOFF §5.
판정: **확인** = 새 베이스에서 실행해 확인 / **무수정** = 코드를 바꾸지 않아 V1 판정이 이어짐(다시 재지 않음) / **미검증** = 아직 재지 못함(이유 적음).

## 1. V1 기능(CAP-01~18, `docs/research/AGENT_BRIEF_FINAL.md` §9)

| # | V1 기능 | 새 베이스의 담당 | 판정 | 근거 |
|---|---|---|---|---|
| CAP-01 | 12태그 계측 | 가상설비 → OpenPLC(Modbus 마스터로 읽음) → Node-RED 엣지(PLC를 읽어 UNS로) → OT 허브 | 확인 | 60 s 동안 Kafka 원시·DMZ 사본 모두 태그당 60건(720/720), 유실·중복 0, 최대 공백 1.0 s — `BASE-VERIFY/raw/rate_check.json` |
| CAP-02 | Modbus 읽기·쓰기 | 가상설비와 Modbus로 말하는 것은 PLC 하나. 엣지는 PLC와만 Modbus | 확인 | PLC 계약 시험 50/50(`harness/e2e/plc_contract.py`), 운전원 명령 → PLC ACK 0.2 s → 가상설비 반영(제어 회귀 S14) |
| CAP-03 | 실시간 감시 화면 | FUXA(OT 허브 UNS 구독, 등록부에서 생성한 화면) + Grafana(IT) | 확인 | FUXA 현재값 = DMZ 원시 사본 120/120, = FUXA DAQ 120/120 — `raw/e7_base.json` |
| CAP-04 | 운전원 직접 조작(C1 FUXA, C2 Vue) | C1: FUXA → `…/cmd/operator` → 엣지 → PLC. C2(Vue `/control`)는 없앰 → FUXA가 대신(쓰기 길 하나, §3-2) | 확인 | 제어 회귀 S14(ACCEPTED, 반영), 모드 표 — `raw/control_base.json` |
| CAP-05 | 센서·분석 이력 저장·조회 | OT: FUXA DAQ(SQLite, 7일) / DMZ: InfluxDB 원시 사본 / IT: InfluxDB 결과(정제값·점수·알람) | 확인 | 위 E7, 12태그 저장, Grafana 데이터 원본 3개 정상 |
| CAP-06 | 상·하한 / Z-Score / 순서 패턴 / 모델 이상 탐지 | Flink 2.2.1: SQL 잡 3개(V1 SQL 그대로) + ONNX 잡(입력 창만 스캔 순번·설비 시각, K4) | 확인 | 판정 70/70(`raw/reg_base_l4_eval.txt`), ONNX = Python 100/100·최대 차 0.0(`raw/s13_s13_base.json`), 학습기 자체 검증 드리프트·베어링 100 %(`experiments/ML-K4/train_scale600.log`), 실제 흐름 verify: 스파이크 → 규칙·베어링 → CEP·드리프트 → ML, 결측 → 원시 공백·정제 보간(`BASE-VERIFY/verify_detection.log`) |
| CAP-07 | 알람 화면 표시 | 공정 알람은 FUXA가 OT 안에서 판정(규격·인터록·비상정지·통신), 분석 경고는 IT → DMZ → OT 허브 → FUXA "분석 경고(참고)", AI 화면 | 확인 | 고장→화면: 스파이크 3.01 s, 히터 5.95 s, 베어링 7.13 s, 드리프트 2.09 s(`raw/onset_base_run*.json`) |
| CAP-08 | 알람 → 사건 등록(중복 결합) | 업무 서비스의 AI 사건 접수 스레드(V1 `consumer.persist_message` 그대로) + alert 묶음(ISA-18.2) | 확인 | 교반기 이상 주입 3 s 뒤 사건 생성(`BASE-VERIFY/control_ai.log`) |
| CAP-09 | 운영 지표 감시 | Prometheus 셋(OT agent → DMZ → IT federate), Alertmanager, cAdvisor, kafka-exporter, 브로커 `$SYS` exporter(Bento) | 확인 | IT에서 zone=ot·dmz 대상 up, 규칙 9개 `promtool` 통과. `$SYS` 구독 결함을 고친 뒤 브리지 상태·버린 건수 지표가 나옴 |
| CAP-10 | 설비↔센서↔문서 근거 조회 | Neo4j + 기동 시드(등록부에서 인벤토리) | 확인 | 시드 A·B·C 게시(`graph-seed` 로그) |
| CAP-11 | 사람 승인·반려 | AI 화면 승인(담당자) → 작업 요청 / OT 안 운전원 수락·거부(FUXA "받은 요청") | 확인 | AI S17(반려 → 요청 0), OT S17(운전원 거부 → 설비 변화 없음) |
| CAP-12 | 고압 인터록 | PLC(트립 6.5 barg, 리셋 허용 5.2 barg) + 가상설비 릴리프(7.5 barg). **V1과 달라짐(사용자 결정 2026-09-30):** V1은 압력이 5.2 barg 아래로 내려오면 저절로 풀렸다. 새 베이스는 트립을 기억(래칭)하고 운전원이 FUXA "인터록 리셋"(명령 코드 12, 운전원 출처만)을 눌러야 풀린다. 압력이 5.2 barg를 넘으면 리셋을 거부하고, 풀린 뒤에도 펌프는 운전원이 다시 켤 때까지 꺼져 있다 | 확인 | PLC 계약 시험 60/60(트립 기억·압력 높을 때 리셋 거부·외부 요청 리셋 불가·운전원·현장 패널 리셋), 제어 S16(표본 51개 모두 펌프 꺼짐, 압력이 내려와도 유지, 리셋 뒤 운전원 재기동) — `BASE-VERIFY/raw/plc_contract_r1·r2.json`, `control_s16.json` |
| CAP-13 | 실행 직전 조건 재검사 | AI(대응안 지문) → 수신기(모드·정비·만료) → PLC(범위·모드·인터록·만료·중복) | 확인 | AI S18(명령 바뀜 → 409, 요청 0), OT S18(대기 중 정비 모드 → 수락해도 거부) |
| CAP-14 | 명령 후 실제 상태 재확인 | 업무 서비스 재관측(PLC 수용부터 10 s) → 불일치면 COMMAND_DISAGREE alert | 확인 | 모드 표 REMOTE_AUTO·REMOTE_MANUAL 재관측 OK, S20 불일치 10.44 s |
| CAP-15 | 감사 추적 | PostgreSQL `audit.log`(추가 전용) + Kafka `audit.copy` | 확인 | 요청 1건에 approve → dispatched → gateway_accepted → response_receipt·operator·plc → observed, UPDATE·DELETE는 ops·postgres 모두 거부 |
| CAP-16 | 여러 소비자 독립 소비·재처리 | Kafka 4.3.1(7일·30일 보존), 소비자 그룹 분리 | 확인 | 측정 도구가 시각으로 오프셋을 찾아 지난 구간을 다시 읽음(S01·E1 집계), 운영 그룹(Flink·업무·AI 접수·IT 수집기) 동시 소비 |
| CAP-17 | 관측 사실과 AI 추론 분리 | AI 판단 로직(그래프 AgentRun 링크) | 무수정 | HANDOFF §1: 판단 로직은 고치지 않음. 설비에 닿는 연결만 바꿈 |
| CAP-18 | 장애 시 안전한 실패 | AI: 업무 DB 없으면 승인 저장 안 함 / 엣지·수신기 끊김: 결과 모름·미확인, 재전송 없음 | 확인 | AI S22(503, 복구 뒤 요청 0), S19(ACK 5.38 s 결과 모름 → 만료 미확인, 성공 기록 0) |

## 2. 빼거나 바꾼 V1 부품 — 누가 대신하나

| V1 부품(컨테이너) | 하던 일 | 새 베이스에서 대신하는 것 | 판정·근거 |
|---|---|---|---|
| EdgeX 10개(device-modbus·core-data·core-metadata·core-command·core-keeper·app-mqtt-export·ui·postgres·mqtt-broker) | Modbus 폴링·정규화·명령 API·끊김 저장 | Node-RED 엣지 1개(등록부에서 흐름 생성, 끊김 저장·재전송) + OpenPLC(명령 검사) | 엣지 비교 실측으로 Node-RED 채택(`experiments/EDGE-CMP/summary.json`: 누락 0·명령 10/10 동률, 복구 중복 0 대 12~24, 메모리 77~83 대 144~180 MiB, 등록부 변경 자동 반영) |
| EMQX 5.8.6 | 사이트 브로커 | Mosquitto 2.1.2 둘(OT 허브, DMZ 브로커, 브리지 mqttv50) | EMQX 5.8 지원 종료·5.9+ BSL(관문). 흐름·만료·ACL 확인(⑨ 2·3·4) |
| Telegraf bridge(MQTT → Kafka) | 수집 | IT 수집기(Bento, `dmz_to_kafka`) | 원시 유실·중복 0(CAP-01) |
| Telegraf sink(Kafka → InfluxDB) | 저장 | IT 수집기(Bento, `kafka_to_it_influx`) | IT InfluxDB 적재·quality 태그(verify) |
| alert-republisher(Kafka → MQTT, FUXA 알람 토픽) | 알람을 화면으로 | 업무 서비스(`alerts.display`, 묶음·억제) → IT 수집기 → DMZ → 브리지 in → FUXA "분석 경고" | 드리프트 표시 3/3(≤ 2.09 s), E1 표시 지점 |
| MQTT `scada/alerts/{tag}`·`scada/hmi/latest-alert` | FUXA가 구독하던 알람 글자 | FUXA 공정 알람(OT 판정) + `AR-100/alert/display` | 위와 같음 |
| Kafka 3.9.0 | 백본 | Kafka 4.3.1(KRaft) | 모든 흐름 시험 |
| Flink 1.20.1(HA 없음) | 탐지 | Flink 2.2.1 + ZooKeeper HA, ONNX 체크포인트 | 70/70, 재시작 복구(§3-5) |
| InfluxDB 2.7 하나 | 이력 | InfluxDB 2.9.1 둘(DMZ 원시 사본, IT 결과) | CAP-05 |
| ai-alarm-worker | 알람 → 사건 | 업무 서비스 안 AI 사건 접수 스레드 | CAP-08 |
| ai-work-db(postgres:17) | AI 업무 DB | 공용 PostgreSQL 18.6(DATABASE `ai` + `plant`) | ⑨-7, AI 시험 전부 |
| AI `simulation.py` `/controls`·`/control` | Vue에서 Modbus 직접 조작 | 없앰 → FUXA 운전원 조작 | CAP-04 |
| AI `actions.py` Modbus 쓰기·`/state` 확인 | AI 조치 실행 | 작업 요청(workflow → 발송기 → 게이트웨이 → 수신기 → PLC) + 업무 서비스 재관측 | AI S21(요청 1건, 수신 0.19 s), 모드 표 |
| AI `evidence.py` 가상설비 `/state` 조회 | 현재 상태 근거 | DMZ 원시 사본(InfluxQL 읽기 전용 계정) | `live_state` 12태그·명령·모드 반환 |
| AI 훈련 고장 주입 | 수업용 고장 | 호스트 전용 강사 API(계정 필요), AI·IT에는 자격 증명 없음 | AI·IT 컨테이너에서 강사 API·현장 패널 401 |
| 임베딩 Ollama(`embed` 컨테이너, qwen3-embedding)·매뉴얼 절 검색 bge-m3(`V2_EMBED_URL`) | 온톨로지·매뉴얼 벡터 검색 | GCP LiteLLM(`knu-litellm`)의 `embedding` 모델(text-embedding-3-small, 1536차원) 하나. 호스트·컨테이너 Ollama 없음(사용자 결정 2026-09-30) | 매뉴얼 절 26·개체 113 다시 임베딩, 빠진 벡터 0·0 벡터 0(graph-seed 로그), 이상 → AI 조치 제안 20.54 s(`BASE-VERIFY/raw/cycle_base.json`) |
| Prometheus 규칙 `EMQXDisconnectSpike` | 브로커 끊김 경보 | `MosquittoBridgeDown`·클라이언트 급감·버린 건수 규칙 | 규칙 통과, `$SYS` 지표 확인 |
| `make lite`(EdgeX 없이 시뮬레이터 → EMQX) | 가벼운 기동 | 새 베이스 자체(엣지 1컨테이너) | 별도 경로 없음 — 대체 |
| FUXA 가 Modbus 로 가상설비 직접 읽기·쓰기(이중 폴링) | 화면·조작 | FUXA는 UNS 구독·운전원 명령 발행만 | 이중 폴링 제거(현업 근거 없음, §2-1 V1과 비교) |

## 3. 사람이 쓰는 기능

| 기능 | 새 베이스 | 판정 |
|---|---|---|
| MQTT 실시간 계측 `edgex/telemetry`(수업·시연 자료) | 엣지가 같은 EdgeX 이벤트 모양으로 초당 1건 발행(정본은 UNS). OT 허브 공개 포트에서 읽기 계정 `viewer`로 구독 | 확인(이벤트 1건에 12종) |
| `scripts/verify.py` | 새 길로 다시 씀(정규화·제어 반응·흐름·저장·역할 분리·화면 표시는 그대로). 바뀐 항목: EdgeX 이벤트 수 → UNS·`edgex/telemetry`, Modbus 코일 쓰기 → 운전원 명령(FUXA 계정), InfluxDB 하나 → IT 결과 + DMZ 사본, 감시 구역 연결·FUXA 로그인 없는 쓰기 거부 추가 | 결과는 §3-5 보고 |
| Grafana 대시보드 4개(공정·ML·알람·인프라) | 그대로. 인프라 화면의 EMQX 패널 → Mosquitto `$SYS` | 확인(데이터 원본 3개 정상) |
| FUXA 화면 | 등록부에서 생성. **로그인 필요:** 보기는 로그인 없이, 운전원 명령은 `operator`, 화면·설정 변경은 `admin`(비밀번호는 `.env`) | 확인(로그인 없는 쓰기 401) |
| EdgeX UI(장치·읽기 목록 보기) | Node-RED 편집 화면(로그인), FUXA 화면 | 대체(보기 방식이 다름) |
| 가상설비 Modbus 포트(호스트 27002) | 열지 않음 — 가상설비에 붙는 것은 PLC 하나(§2-1 ⑤). 수업에서 Modbus를 보려면 PLC 편집 화면·엣지 흐름 | 바뀐 사용법 |
| `docs/DEMO.md` 시연 순서 | V1 명령(EdgeX·EMQX) 그대로라 새 베이스용으로 다시 써야 한다 | 수업 자료 갱신 필요(다음 단계) |

## 4. 잃은 것

없음(2026-09-30 기준). 바뀐 사용법(FUXA 로그인, 강사 API 계정, 가상설비 Modbus 비공개, 포트 번호)은 §3에 적었다.
