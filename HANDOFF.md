# HANDOFF — V1 IoT·SCADA 기반을 회전으로 안정적인 시스템으로 (scada-rotation)

최종 갱신 2026-09-29 15:10 · 작성 Claude Code(세션 3 종료, 새 세션으로 넘김 — 맥락 한계)
**이 문서만 읽고 이 작업을 이어갈 수 있게 쓴다.** 실제 파일·실행 상태·사용자 지시와 다르면 실제가 우선이고 이 파일을 고친다.
**판정 기준의 정본은 `QUESTIONS.md` §1 하나다.** 이 파일은 기준을 복제하지 않고 가리킨다.

---

## 0. 처음 읽는 사람을 위한 순서 (20분)
1. **이 파일 전체**(특히 §1 목표, §2 지시, §3 멈춘 지점). 사용자 원본 목표·DoD 9개는 `D:\work\study\TODO.md`(「SCADA 현업 스택 회전」) — 최종 판정은 그 DoD 로 한다.
2. `QUESTIONS.md` §1 — **결정 순서(구조 먼저)·기능 보존·구조 판정**, 판정 기준(관문 → 성능·안정성 → 효율 → 운영 참고), 시간 원칙, 후보 원칙, 시험 범위. 기준은 여기에만 있고 이 파일은 가리키기만 한다.
3. `reports/STABILITY.md` — 기반 내부 오류 대장(핵심 목표 ② 안정적인 기반의 목록).
4. `reports/CONFIRMED.md` — 지금까지 원래→바뀜 한 장.
5. `harness/situations/CANDIDATES.md` 맨 앞 개정 절(#92·#90·#74) — 후보 목록 규칙. 본문 표보다 개정 절이 우선.
6. `harness/situations/ROBUSTNESS.md`·`STRUCTURE.md` — 비정상(R01~R11)·구조 측정(E1~E12) 목록, 시간 값은 #89 개정.
7. **리서치 원문(`docs/research/`) — 이번에는 전부 끝까지 읽는다(세션 3 은 01~04·FINAL 을 덜 읽고 층별 시험부터 해 이중 작업이 됨).** 반드시: `AGENT_BRIEF_FINAL.md`(회귀 S01~S25·G0~G10 정의·절차), `ARCHITECTURE_SIMPLIFICATION.md`(V1 중복·우회 분석·구조안 = 구조 재조립 근거), `deep-2026-09-29/01~05`(후보별 라이선스·지원 종료 사실과 출처). 참고만: `AGENT_BRIEF.md`·`AGENT_BRIEF_v2.md`(FINAL 에 흡수된 옛 판)·compass 4종 — 충돌하면 FINAL·사용자 지시가 이긴다.
8. 필요할 때만 `reports/decision-log.md` 해당 번호(#1~#98, 추가만). 이 문서가 인용한 번호부터 본다.
9. 시작 전 반드시 `git status`, `docker ps`, 원시 토픽 흐름(§6 명령)으로 실제 상태 대조.

## 1. 목표와 우선순위 (사용자 확정 2026-09-29)
- **출발점:** V1 은 현업에서 컨펌받은 원본이다(기능·흐름은 지킴). 그러나 돌아가는 길·중복·비효율·낡은 스택은 검증되지 않았고, 실제로 돌려 보니 내부 오류가 많다(V1 기준 측정 #97·#103, 대장 S1~S14). 정본 서술: `QUESTIONS.md` §1 "출발점 인식".
- **핵심 목표 두 가지(같은 무게):** ① **효율적인 현업 기준 구조** — 리서치 원문 + 추가 리서치(넓게)를 바탕으로 길·레이어를 다시 설계하고 남는 층의 스택을 조합해, 회전(V1→V2→…)마다 무엇을 왜 바꿨고 얼마나 나아졌는지 **실측 궤적**으로 대표님께 보고. ② **안정적인 기반** — 매 회전 e2e 가 전부 정상이고, 돌리며 드러나는 내부 오류(로그 예외·조용한 정지·유실·중복·오경보)를 `reports/STABILITY.md` 에 올려 **모두 고치거나** 남긴 이유와 재현 근거를 남긴다. 진행 순서의 정본은 `QUESTIONS.md` §1 "결정 순서". 기준을 넘는 개선이 없는 회전에서 멈춘다.
- **결과:** 온톨로지·시나리오가 바뀌어도 흔들리지 않는 **단단한 기반 틀**.
- **담당 범위 = 기반**(수집·브로커·중계·백본·탐지·저장·감시·알람 경로). **AI 층은 별도 — 온톨로지·시나리오 구체화는 담당 밖** — AI 층은 지금까지 만든 것(V2 도구, 비교 측정 #83·#84)에서 멈춘다.
- 쓰임: 경남대 제조 AI 실습·시연. 이상→감지→AI 조치가 **수 초~수 분 안에** 이어져야 한다.
- 원 과제 문서: `docs/research/AGENT_BRIEF_FINAL.md`(절차), `ARCHITECTURE_SIMPLIFICATION.md`(V1 중복·우회·구조안). **사용자 지시가 문서보다 우선.**

## 2. 사용자 확정 지시 — 어기면 신뢰 붕괴 (재론하지 않는다)
1. **질문에는 먼저 자연어로 답한다.** "~하면 안 되나?" 같은 질문을 지시로 받아 바로 바꾸지 않는다(권고로 답하고 결정을 기다림). 답한 뒤에는 묻지 말고 진행. 단계마다 번호 붙은 짧은 중간 보고.
2. **시간:** 가상설비는 **배속이 시스템 기본값**(`simulator/plant.yaml physics_time_scale: 600`, 서서히 진행하는 현상은 하나의 설비 시계, 순간 사건만 실제 초). 그 반대 개념을 가리키는 말은 쓰지 않는다. 이상 주입→알람 10초 이내, 한 사이클(이상→감지→AI 조치 제안) 1분 이내, 전체 흐름 수 분 안. 오래 걸리면 배속·범위부터 줄이고, 소요 시간은 짐작 말고 첫 실행을 재서 말한다(#87~#89·#95).
3. **후보 = 다른 제품만**(A 제품 대 B 제품). 같은 제품은 판·설정 모두 후보가 아니다 → 가장 좋은 지원 판을 번호로 고정(회귀에서 한 번에 확인). 판 얘기는 보고에서도 하지 않는다(#90·#92).
4. **보강 없음**, 예외 하나: **Flink 재시작 복구(HA, Flink 내장 기능 — 설정만)는 켠다**(V1 은 이 기능을 꺼 둔 채 운영해 재시작 때 탐지 잡이 사라짐, #93·#94).
5. **관찰된 내부 오류는 고친다**(근거 있는 수정). 관찰 없이 미리 하는 설정 보강은 하지 않는다(#96).
6. **시험 범위 = 구조가 정한 남는 층에서, 그 제품이 닿는 앞뒤 구간.** 같은 층 후보(결정을 바꿀 수 있는 것만)는 같은 입력으로 나란히(두 줄 동시 실행). 입력은 V1 이 실제로 흘린 데이터(Kafka·MQTT 메시지)를 파일로 한 번 **기록해 재생**(영상 녹화 아님). 전체 스택 측정은 V1 기준 1회·버전 확정 1회(#91).
7. **권한과 작업 방식(처음 지시 + 오늘 확정):** 모든 결정 권한을 위임받았다 — 묻지 말고 QUESTIONS §1 로 스스로 판단·실행·판정하고 근거를 decision-log 에 남긴다. 이 PC 자원은 허락 없이 쓴다: 이미지 받기·빌드, 벤치 기동·삭제, 격리 스택(`.env.rotation` 의 rot-iiot·rot-ai) 기동·정지, Docker 재시작, 서브에이전트 병렬. 효율·상식 우선: 측정 전에 도구·경로를 한 번 확인해 무효 실행을 줄이고, 후보는 빠르게 거르고, 쓰지 않는 벤치는 바로 정리하고, 무거운 Docker 측정은 메모리 관문(`MEMCAP`) 아래에서 한 번에 하나씩(Docker 메모리 7.6GB, 넘치면 엔진 500 — #81), 그동안 가벼운 일(문서·설계)을 병행한다. 이미 유효하게 끝난 측정·작업은 다시 하지 않고 증거를 재사용한다(무효로 판정된 것만 다시). 맥락이 차기 전에 이 파일을 최신으로 유지한다. 넘으면 안 되는 선은 §8.
8. **사실 기반, 추론 금지.** 모든 판단·수치는 실행 결과·로그·파일·1차 출처로 증명 가능해야 한다. "~같다·~로 보인다"로 결론 내리지 않는다 — 확인 못 한 것은 "미확인"과 확인 방법으로 쓴다. 바꾸기 전에 그 변경이 닿는 문서·설정·측정을 모두 찾아 영향을 파악한다(예: #97 은 짐작으로 원인을 잘못 짚었다가 로그·Kafka 오프셋으로 정정).
9. **말은 쉽게.** 사용자·대표님에게는 어려운 용어 없이 무엇을 왜 했는지 쉬운 말로 답한다(예: "Flink 재시작 복구"를 약점처럼 어렵게 설명했다가 지적받음). 결론 먼저, 짧게.

10. **(09-29 세션 3) 구조 먼저, 부품은 그 다음**(기준 정본: `QUESTIONS.md` §1 "결정 순서"). "부품만 바꿔 끼워 봐야 지저분하고 돌아가는 건 여전하면 두 번 일하는 것." → 리서치 원문·후보표·실측 결과를 모두 모아 **길 흐름과 레이어를 먼저 재설계**하고, **남는 층에서만** 제품 조합을 고른다. 없어질 층의 부품 단독 시험은 하지 않는다. 현업 흐름(설비 → 수집 → 전달 → 탐지 → 저장 → 화면 → AI)은 유지한다.
11. **(09-29) 기능 보존**(기준 정본: `QUESTIONS.md` §1 "기능 보존"). 부품을 빼서 기능이 같이 빠지면 안 된다. 빼는 것은 **중복·돌아가는 길·대체가 확인된 것**만. 빼는 부품마다 "그 기능을 누가 대신하는가" 대응표를 만들고 실측으로 확인한다(신중하게).
12. **(09-29) 빠르게·상식적으로.** 틀에 갇히지 말고, 결정을 바꿀 수 있는 측정만 한다. 단 "틀에 갇히지 말라"는 **읽기를 건너뛰라는 뜻이 아니다** — 인계·원문을 다 읽고 나서 상식적으로 판단한다(세션 3 과실, #120).
13. **(09-29) 측정 도구는 먼저 한 번 끝까지.** 새 벤치·실행기는 후보 1개로 결과 파일까지 한 번 돌려 확인한 뒤 일괄 실행한다(문법 검사로 대신하지 않음). 실패하면 로그를 파일로 남기고 컨테이너를 정리한다(세션 3 에 벤치 결함 약 20건 연쇄, #104~#118).

## 3-0. 세션 4 (2026-09-29 15:13~, 진행 중) — 최신 상태 (아래 세션 3 절보다 우선)
- **한 일:** 리서치 원문 전부 통독 → 추가 리서치 06(현업 참조 구조)·07(감시 경량화)·08(부품 안정성) `docs/research/deep-2026-09-29/` → **V1 해부(갈래 16개, 누가 받아 쓰는가를 코드로)** → `reports/V2_DESIGN.md`(갈래 판정·층별 판단·재조립 5개·기능 대응표·조합 3안 중 B 선택·리서치 반영 §7-1) → V2 일괄 반영·확정(커밋 `fd8c3a0`, decision-log #124~#126).
- **고친 내부 오류:** S15 InfluxDB 초기화(이름 없는 `/etc/influxdb2` 볼륨이 V1 설정을 넘겨받음 → `influx-config-v2`), S16 중계기 401 저장 유실(Vector 0.58 환경변수 치환 기본 꺼짐), S17 ONNX 잡 체크포인트 꺼짐(V1 도 같음 → `flink/conf/client-config.v2.yaml`), 수집기 버퍼 경로(`/tmp/telegraf-buffer`), 측정 도구 `baseline.sh` 이름표 덮어쓰기 결함(#125 — 이 결함으로 에이전트 실수 실행 EXP-002 r1_ 이 V1 을 띄움, 무효).
- **V2 에서 뺀 갈래(받는 곳 없음·중복):** lite 수집 길, 알람 태그별 토픽 `scada/alerts/<tag>`, EdgeX core-command, 수집 6단계의 중간 5단계. **대체한 기능:** 브로커 감시(브로커 생존+쓰기 오류, Grafana 04 V2 사본), verify.py EdgeX 단계 → 수집기 `edgex/telemetry` 확인(격리 스택 환경변수 `VERIFY_CN_PREFIX=rot- VERIFY_NETWORK=rot-iiot VERIFY_ENV_FILE=.env.rotation`).
- **측정 진행 중:** `STRUCT=V2 sh harness/e2e/run_full.sh EXP-002 V2 r2_`(전체 측정 P0~P3 → 회귀 S25 포함 → 고장→알람 6종×3 → 내부 오류 → E2), 로그 `experiments/EXP-002/run_full_V2_r2_.log`·`baseline_V2.log`. 도구 확인: fault_onset 스파이크 1회 kafka 1.81 s·화면 1.82 s(`raw/onset_tooltest.json`).
- **다음:** 측정 결과를 V1 기준값(§4)과 대조 → 나빠진 항목·새 내부 오류를 모아 한 번에 수정 → 필요한 항목만 재측정 → `v2` 태그 → REPORT.md(+HTML)·쉬운 설명서 → 작업보고. 그다음 V3 후보는 V2 측정에서 남은 복잡·비효율로 판단.
- **측정 도구 주의(세션 4):** `fault_onset.py` 는 `--broker mqtt --mqtt-topic scada/hmi/latest-alert`(V2), 잡 취소 루프는 `tr -d '\r'` 필수, Vector 설정은 `vector validate` 통과본만 적용.

## 3. 지금 멈춘 지점 (2026-09-29 15:10, 세션 3 종료) — 세션 4 에서 해결된 항목: InfluxDB 2.9.1 초기화(S15), ingest 버퍼 경로, V2 부분 기동
- **실행 상태:** 모든 컨테이너 정지(실행 0). 격리 V1(rot-iiot 의 V1 전용 컨테이너 EdgeX·EMQX·Telegraf×3 등)·rot-ai 는 정지 상태로 남아 있음, 볼륨 전부 보존. **V2 스택을 한 번 띄웠다가 멈춤**(아래 "V2 부분 기동"). 층별 시험·재측정 실행기는 모두 중단(사용자 지시 10).
- **세션 3 에서 끝난 것(근거 decision-log #101~#119, 커밋 `717e0a9`·`ee975be`):**
  - **V1 기준 재측정 완료**(수동 조치 기록 `experiments/EXP-001/manual_actions.log`) — 복구 = 2분 연속 흐름(`harness/e2e/wait_flow.py`). 요약 `experiments/EXP-001/summary_V1_r2_.json`(`harness/tools/summarize_baseline.py EXP-001 V1 r2_`): **R01 브로커 재시작 → 3회 중 2회 수집 스스로 복구 못 함**(Telegraf 1.33 중계기 멈춤, 대장 S2·S12), R02 7.3 s·유실 중앙 120, R03 11.6 s·Kafka 중복 150, R06 3.2 s, R08 유실 0, E11 감지 0/2, E1 p95 FUXA 1.84 s. V1 데이터 기록 `experiments/REC-V1/`.
  - **층별 ② 1차**(요약 `experiments/STAGE2_RUNS.log`, 층 결과 재계산 도구 `harness/tools/layer_{broker,ingest,l4,pipe,backbone,ts}.py` → `experiments/EXP-*/layer_*.json`):
    - 이상탐지: **Flink 2.2.1 + ZooKeeper HA** 70/70·V1 알람과 완전 동일·JobManager kill 뒤 잡 4개 자동 복귀(S1 벤치에서 해결, V2 전체 스택 확인 대기), 약점 CEP 중복 1. Quix·Kafka Streams·Storm·Beam·Proton·Arroyo 는 엔진이 CEP·Z-Score 를 거부해 탈락(원문 #109~#113).
    - 중계: V1 Telegraf×3 = 710 MiB → **Vector 0.58 1개 45 MiB·결과 동일·알람 전달 p95 793→37 ms**(④ 미측정). Bento 는 알람 timestamp 반올림 약점. Kafka Connect·RMQTT 내장 탈락.
    - 수집: EdgeX 기준 1356/1356·p95 9.75 ms·10 컨테이너, **benthos-umh 1356/1356·p95 1.36 ms·1 컨테이너**, Node-RED 통과(JS 어댑터 코드). Telegraf 는 벤치 결함으로 미측정(고침).
    - 저장: InfluxDB 기준(질의 결함 고쳐 재측정 필요), TimescaleDB·pg_partman·QuestDB 질의 정답이나 **디스크 24h 680~1100 MB vs InfluxDB 19 MB**(Timescale 압축은 TSL), VictoriaMetrics 문자열 저장 불가 탈락.
    - 브로커: Mosquitto 재시작 중복 1(2회), RMQTT·LavinMQ·ActiveMQ 0 — 새 구조에서 브로커는 알람→화면만 담당.
    - 알람 워커: V1·Bento·Redpanda Connect 결과 동일, 효율 이득 미미 → V1 워커 유지(#119).
    - 백본: Kafka 3.9 기준선만 유효(모든 부하·재시작 유실 0), 대안 8개는 실행기 결함으로 미측정(#116).
  - **중요 사실:** ① Kafka 4.3.1 에서 Telegraf 1.40.1 `kafka_consumer` 는 `kafka_version = "3.0.0"` 없이는 0건(#114). ② S6(배속 설비 ML 오경보): 재학습하면 드리프트·베어링 탐지율 100→0 % → V1 모델 유지(#109). ③ 벤치 결함 약 20건 수정(실패 뒤 컨테이너 미정리로 연쇄 거부, CRLF, 설정 문법 등 #104~#118).
  - **V2 조립 초안**(검증 안 됨): `docker-compose.v2.yml`(수집 Telegraf 1대 → Kafka 4.3.1 → Flink 2.2.1+HA → Vector(저장·알람 중계) → Mosquitto → FUXA, InfluxDB 2.9.1, 설비 전용망 field, 서비스 이름 V1 과 같음, 볼륨 -v2), `v2/`(telegraf·vector·mosquitto·prometheus), `flink/Dockerfile.v2`(이미지 `rot-flink-onnx:v2` 빌드됨)·`onnx-job-2x`·`conf/config.v2.yaml`. 측정 도구 `STRUCT=V2`(`harness/e2e/struct_V2.sh`), 회귀 `harness/e2e/regression.sh`+`regression_control.py`+`alerts_window.py`(**한 번도 실행 안 함**).
- **V2 부분 기동 결과(15:0x, 1회):** Kafka·Flink(HA)·ZooKeeper·Mosquitto·설비·수집·FUXA·Prometheus 는 기동. **InfluxDB 2.9.1 이 "Error: config name \"default\" already exists" 로 초기 설정 반복·재시작 루프** → Grafana·Vector 는 생성만 됨. 원인 미확인(첫 실행 로그 확인 필요, `/etc/influxdb2` 설정 경로 볼륨 여부 점검).
- **미적용·미검증 변경:** `v2/telegraf/ingest.conf` 에 기능 보존 두 가지를 넣었으나 **검증 전** — ① V1 과 같은 MQTT 계측 흐름(`edgex/telemetry`, EdgeX 이벤트 모양, processors.clone) ② 디스크 버퍼(`buffer_strategy = "disk"`). **`buffer_directory = "/var/lib/telegraf/buffer"` 는 권한 오류로 수집기가 안 뜸(실측) → `/tmp/telegraf-buffer` 로 바꿔야 함(미적용).**
- **문제점(사용자 지적, 세션 3):** HANDOFF 순서대로 "층별 후보 시험 → 조립"을 하다 보니 새 구조에서 없어질 층(수집기→MQTT 모양, MQTT→Kafka 중계, 브로커 신규 12종, 백본 대안)까지 시험해 **이중 작업**이 됐다. 리서치 원문(딥리서치 01~04, FINAL 전체)을 덜 읽고 시작한 탓. → 지시 10·11.
- **바로 다음(새 세션):**
  1. **리서치 원문 전부 통독 + 추가 리서치(넓게, `QUESTIONS.md` §1 결정 순서 1-2)**: `docs/research/ARCHITECTURE_SIMPLIFICATION.md`, `AGENT_BRIEF_FINAL.md` 전체, `deep-2026-09-29/01~05`, `harness/situations/CANDIDATES.md`(§11 구조 패턴 포함), compass 4종은 필요한 절만. 층별 실측은 위 `layer_*.json`·decision-log #101~#119.
  2. **레이어 재설계 문서 1장**(예: `reports/V2_DESIGN.md`): 현업 흐름 유지, 길(데이터 경로) 다시 그리기, **기능 대응표**(빼는 부품마다 기능 → 대체 → 확인 방법). 이미 확인된 대응: EdgeX→Telegraf 수집(Modbus 12태그·센티널 제거·V1 raw 모양 확인), EMQX→Mosquitto(알람→FUXA), Telegraf#1 → 없음(수집기가 Kafka 에 바로), Telegraf#2·#3 → Vector(결과 동일), edgex-postgres → 없음(EdgeX 전용). **빠지면 안 되는 것:** MQTT 실시간 계측 흐름(수업·시연 자료가 `edgex/telemetry` 사용 — `ai-web/public/system-guide.html`, `docs/소스코드로_…설명.html`, `docs/journal/07`), 단절 저장 후 재전송(EdgeX 디스크 → Telegraf 디스크 버퍼로, R02·수집기 재시작으로 실측), 브로커 연결 감시(EMQX 지표·규칙 EMQXDisconnectSpike → 목적은 TelemetryIngestStalled 로 대체되는지 확인), 수업 3차시 EdgeX 프로파일·`scripts/verify.py` EdgeX 확인(강제 교체라 불가피 — 대체 안내 기록), EdgeX core-command 쓰기 API(사용처 없음·인증 없는 쓰기 창구 — 제거가 보안상 이득, E12).
  2-1. **구조 재조립 대상 5개(원 지시, DoD 2 — 각각 제거 또는 남긴 이유를 실측으로):** ① 알람 되돌림(알람이 Kafka→Telegraf#3→EMQX 로 되돌아가 화면까지 12단계) ② 중계 5중(EMQX·Telegraf×3·Kafka) ③ EdgeX·FUXA 설비 이중 폴링 ④ 설비 쓰기 경로 3개(FUXA·EdgeX 명령·AI 조치) ⑤ 저장소 3개(InfluxDB·PostgreSQL·Neo4j, +EdgeX 전용 DB). 패턴 후보 `harness/situations/CANDIDATES.md` §11.
  3. **스택 조합안 2~3개**(예: 보수안 = 제품 유지·길만 정리 / 효율안 = Vector·benthos-umh 등 가벼운 제품 통합) — 컨테이너 수·알람→화면 단계·메모리·기능 보존을 **이미 있는 증거**로 비교해 하나 선택. 모자란 수치만 골라 측정.
  4. 선택안으로 V2 기동(InfluxDB 2.9 초기화 문제·ingest 버퍼 경로 먼저) → `STRUCT=V2 RUN=… sh harness/e2e/baseline.sh EXP-002 V2`(P0~P3, R01~R03 3회) + `fault_onset.py`(고장 10 s 이내) + 회귀(`regression.sh`, V1 도 같은 회귀를 먼저 돌려 기준 확보) → 나빠진 항목만 조합 수정 → 태그 `v2`.
  5. 보고 문서 2개(§9)·작업보고(`D:/work/작업보고/2026-09-29.md`, 세션 2·3 분).

## 4. 확정 사실 — 다시 조사하지 마라
- **판정 기준은 `QUESTIONS.md` §1 에만 있다**: ① 관문(비용 0·OSI 라이선스·컨테이너·지원 종료 12개월 밖·기본 보안·안전 G0~G8) → ② 성능·안정성(정확도·유실·중복은 조금도 나빠지면 탈락, 지연 p95 +5% 이내 = 같음, 복구·비정상 상황, 성능·복구 시간은 3회 중앙값, 미검증 = 조건부) → ③ 효율(메모리·CPU·용량(이미지·디스크)·경유 단계·컨테이너 수·중복 부품 — 5배↓ 또는 컨테이너 절반 이하면 채택, 미묘하면 기준 유지, 강제 교체는 가장 덜 나빠지는 것) → ④ 운영 참고. 구조 판정·시간 조건(고장→알람 10 s, 한 사이클 1분, 전체 수 분)도 §1.
- **넘어야 할 V1 기준값(배속 600 설비, 재계산: `python harness/tools/summarize_baseline.py EXP-001 V1 r2_` → `experiments/EXP-001/summary_V1_r2_.json`, 고장→알람 `experiments/EXP-000/raw/onset_v2sim_600*.json` #95, 탐지 `experiments/EXP-L4` m1, 저장 `experiments/EXP-TS`):**

| 항목 | V1 값 |
|---|---|
| E3 자원 | 메모리 합계 5,918 MiB · CPU 51.2 % · SCADA 컨테이너 29 |
| E1 알람→화면 p95(3묶음 중앙값) | Kafka 1.67 s · FUXA 태그 1.84 s · 최근알람 1.98 s · AI 사건 2.06 s |
| E7 화면값 = 이력값 | 99.17 % |
| E11 감시 | 장애 2종 중 0 감지 |
| E12 보안 | 인증 없이 열린 접점 11 중 10 |
| R01 브로커 10 s 정지 | 3회 중 2회 수집 스스로 복구 못 함(수동 재시작 뒤 Kafka 중복 1,536), 1회 16.0 s·유실 204 |
| R02 수집기 단절 10 s | 복구 중앙 7.3 s · 유실 중앙 120 태그·초 |
| R03 Kafka 재시작 | 복구 중앙 11.6 s · 유실 0 · Kafka 중복 중앙 150(저장 중복 0) |
| R05 탐지기(JobManager) 재시작 | 잡 소멸 · 알람 11~12 유실(사람 재제출) |
| R06 저장 DB 30 s 정지 | 복구 3.2 s · 유실 0 |
| R08 10배 과부하 60 s | 유실 0 · 알람→FUXA p95 2.90 s |
| R09 3분 장시간 | 유실 0 · 중복 0 |
| R11 설비 통신 끊김 5 s | 원시 결측 4 태그·초(보간 대상) |
| 고장→알람 최대 | 스파이크 1.9 · 히터 5.9 · 베어링 8.1 · 결측 5.8 · 드리프트 2.8 s, 잡음(Z-Score) 약 10.8 s(확률적) |
| 탐지 정확도 | 판정 70/70 · 기준 알람 263건(THRESHOLD 170·ZSCORE 53·CEP 40) |
| 저장 용량 | InfluxDB 24시간분 약 19 MB(tsbench) |
- **실행 환경 조건:** Docker VM 메모리 7.6 GB(넘으면 엔진 500 #81), 층 시험은 Docker 전체 4.5~5 GB 이하일 때만 다음 후보 시작, 무거운 측정은 한 번에 하나, 쓰지 않는 벤치는 바로 정리, C: 여유 약 74 GB.

- **V1 구성:** 34서비스(SCADA 29 + AI 5, 일회성 4). 흐름: 설비 → EdgeX(Modbus 폴링, 내부 MQTT) → EMQX(`edgex/telemetry`) → Telegraf#1 → Kafka(`sensor.telemetry.raw`) → Flink(규칙 SQL 3 + ONNX 잡) → Kafka(`sensor.alerts`) → Telegraf#3 → EMQX(`scada/alerts/*`) → FUXA / Telegraf#2 → InfluxDB / 알람 워커 → PostgreSQL. FUXA 는 설비를 Modbus 로 직접도 폴링. **알람→화면 12단계**, 브로커 2·중계 4·저장소 4(E2, `harness/situations/paths.yaml`, `experiments/EXP-000/e2_V1.json`).
- **원래→바뀜(확정):** `reports/CONFIRMED.md`. 요지 — 브로커 EMQX→Mosquitto(조건부: 단절·과부하·느린 구독자·장시간 남음), AI 원인분석·매뉴얼 검색 V2, 가상설비 배속 기본값, Neo4j 유지. 나머지 층 미정.
- **강제 교체 사실(1차 출처, #69·#74):** EMQX 무료판 종료·5.9+ BSL, Kafka 3.9 2027-02 종료, InfluxDB 2.7 지원 밖, EdgeX 4.0 LTS 2027-03 종료 등 → 같은 제품은 지원 판 고정, 제품 계열이 막힌 것(EMQX)만 제품 교체. FUXA V1 = 1.3.4(취약점 판 아님).
- **AI 층 비교(측정 완료, 담당 밖으로 멈춤):** V2 = V1 에이전트 + 온톨로지 원인분석 + 매뉴얼 의미검색. 조치 V2 9/9·V1 7/9, 히터 고착 판별 V2 만, 새 고장 코드 0줄, CQ 9 대 8. 약점: 검색 Recall@3 낮음, 분석 1.5~2배. 증거 `experiments/EXP-AI/`, 표 생성 `python harness/tools/report_ai.py`. 이미지 `rot-ai-knowledge:v2-ai`, `ai-layer/compose.v2.yml`, 그래프 스냅샷 볼륨 `rot-ai_graph-snap-{A,B,C,C3}`.
- **가상설비 V2(#87·#88·#95):** 배속 600, 5 s 소구간 적분, 과정 고장(heater_stuck·cooling_loss·bearing_wear·drift)·생산 스케줄은 설비 시계, 사건(spike·dropout·noise)·운전원 수동 유지는 실제 초, 원료탱크 액위 제어 추가. 단위 시험 `simulator/test_time_scale.py`·`test_thermal_model.py` 11/11. 고장→알람 실측 최대: 스파이크 1.9 s·히터 5.9 s·베어링 8.1 s·결측 보간 5.8 s·드리프트 2.8 s(10 s 이내), 잡음(Z-Score)은 확률적 약 10.8 s(V1 규칙 특성, 대장 S10). 이미지 `rot-plant-simulator:v2-ts`, 덧씌우기 `docker-compose.timescale.yml`.
- **이상탐지 기존 측정(`experiments/EXP-L4`·`EXP-S09`):** Flink 규칙 정확도는 판과 무관하게 동일, JobManager 재시작 시 잡 소멸·유실 11~12(대장 S1). 직접 짠 Python 탐지기는 원칙상 탈락(#53).
- **측정 함정:** EMQX 기본 ACL 은 `#` 구독 거부 → 토픽 명시. Flink 잡 목록은 CANCELED 이력 남음. ONNX 점수는 처리시각 타이머라 입력이 멈춰도 계속 나옴(흐름 확인에 쓰지 말 것). Kafka 원시 토픽 증가(`kafka-get-offsets.sh`)로 흐름을 본다.

## 5. 폐기한 판단 — 되살리지 마라
| 폐기 | 이유 |
|---|---|
| 같은 제품의 판·설정을 후보로 시험(Kafka·Flink·InfluxDB·Prometheus 판 등), 층마다 "같은 제품 최신판이 첫 후보" | 사용자: 의미 없음. 최신 지원 판 고정(#90·#92) |
| 별도 "보강" 단계(규칙 추가·인증 켜기 등 선제 설정) | 사용자: 불필요(#93). 예외 Flink HA(#94), 관찰된 오류 수정은 대장으로(#96) |
| 가상설비를 실시간으로 돌리며 수십 분 대기, 배속을 측정용으로만 쓰기, 고장마다 시간 값을 손으로 맞추기 | 배속이 기본값·하나의 설비 시계(#88) |
| 긴 시험 값(장시간 60분·DB 다운 5분·과부하 10분·E1 300회) | 판정에 필요한 최소로(#89) |
| AI 규칙 엔진(`candidates/ai-ontology/`, 순환 평가), 급진안 C(Kafka·Flink 를 직접 짠 탐지기로), 직접 짠 Python 탐지기 | 순환 평가·엔진급 기능 직접 대체 금지 |
| 온톨로지·시나리오 확장, 임베딩 후보 비교를 이 작업에서 계속 | 담당 밖(#96) |
| "InfluxDB 재시작 뒤 저장기 멈춤" 진단 | 오판 — 실제는 Kafka 재시작 뒤 수집 중계기 정지(#97) |
| 층별 후보를 모든 층에서 먼저 단독 시험하고 나중에 조립(HANDOFF 옛 §3 순서) | 사용자: 없어질 층까지 시험하는 이중 작업. 구조 먼저·남는 층만(지시 10, #120) |
| 재측정 대상 중 선택 가능성 없는 무거운 후보(StreamPipes·OpenRemote·NiFi·TBMQ 통합·Neuron·TB GW·AutoMQ·Pulsar·RocketMQ) | 컨테이너 3~9개라 ③ 에서 1컨테이너 후보를 못 이김(#119) |
| 오토인코더를 배속 설비로 단순 재학습(S6 해결책으로) | 드리프트·베어링 탐지율 100→0 %(#109) |
| 이전 설비·긴 시간 값으로 잰 EXP-000 P1·E1 일부, EXP-AI 의 저속 회차 | 참고 기록만, 판정에 쓰지 않음 |

## 6. 실행 환경·명령
- **재기동(격리 V1):** SCADA `docker compose --env-file .env --env-file .env.rotation up -d --no-build` 후 V2 설비 `docker compose --env-file .env --env-file .env.rotation -f docker-compose.yml -f docker-compose.edgex.yml -f docker-compose.timescale.yml up -d --no-build --no-deps plant-simulator`. AI(V1) `COMPOSE_PATH_SEPARATOR=: docker compose -p rot-ai --env-file ai-layer/.env.local --env-file .env.rotation -f ai-layer/compose.yml -f ai-layer/compose.scada.yml --profile knowledge up -d --no-build`(V2 AI 는 `-f ai-layer/compose.v2.yml` 추가). Docker 재시작 뒤 Flink 잡 0개면 `docker start -a rot-flink-job-submitter`.
- **격리 스택 내림(볼륨 보존):** SCADA `docker compose --env-file .env --env-file .env.rotation stop` / AI `COMPOSE_PATH_SEPARATOR=: docker compose -p rot-ai --env-file ai-layer/.env.local --env-file .env.rotation -f ai-layer/compose.yml -f ai-layer/compose.scada.yml --profile knowledge stop` / V2 `docker compose --env-file .env --env-file .env.rotation -f docker-compose.v2.yml stop`.
- **주의(세션 3):** V2 를 한 번 띄우면서 같은 프로젝트(rot-iiot)·같은 이름의 컨테이너(rot-kafka·rot-influxdb·rot-flink-*·rot-fuxa·rot-grafana·rot-prometheus 등)가 V2 판으로 바뀌었다. V1 재기동 명령을 쓰면 다시 V1 판으로 재생성된다(볼륨은 V1·V2 이름이 달라 서로 안 섞임).
- **층 시험 실행(참고, 구조 재설계 뒤 남는 층에만):** 두 줄 실행기 `sh harness/run_lanes.sh`(PowerShell `Start-Process D:\dev\Git\bin\bash.exe -ArgumentList '-c "cd /d/work/study/scada-rotation && sh harness/run_lanes.sh"'`), 메모리 관문 MEMCAP 4.5 GB, 결과 `experiments/EXP-*/stage2_*.json`·`stage4_*.json`, 요약 `experiments/STAGE2_RUNS.log`. 재측정 목록 `harness/run_retry.sh`. Flink HA 설정 확인 프로필 `harness/l4bench` `flinkha`.
- **흐름 확인:** `docker exec rot-kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server localhost:9092 --topic sensor.telemetry.raw` 를 10초 간격 두 번, 합계 증가 약 144 가 정상.
- **측정 도구(`harness/`, 솔루션 부품 아님):** `e2e/baseline.sh <EXP> <이름>`(PHASES 0~3), `e2e/completeness.py`(유실·중복·공백), `e2e/e1.py`(알람→화면), `e2e/fault_onset.py`(고장→알람), `e2e/security_probe.py`(E12), `e2e/screen_vs_history.py`(E7), `e2e/loadgen.py`(R08), `tools/e2_complexity.py`, `tools/e3_summary.py`, `tools/internal_errors.sh`, `run_all_stage2.sh`·`run_lanes.sh`, 층 벤치 `*bench/stage2*.sh`·`STAGE2.md`, 측정 컨테이너 이미지 `e2e-client:1.0`(망 `rot-iiot`, `--env-file .env`).
- **환경 함정:** 호스트 RAM 15.7 GB·Docker VM 7.6 GB — 전체 스택+AI 로 엔진 500 오류 사례(#81). Docker Desktop 경로 `C:\Users\roede\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe`. 긴 작업은 PowerShell `Start-Process D:\dev\Git\bin\bash.exe`(system32 bash 는 WSL, 도구 백그라운드는 10분에 죽음). Git Bash 에서 컨테이너 경로 인자는 `MSYS_NO_PATHCONV=1`. 모니터는 5~30분에 만료되니 다시 건다. Kafka 콘솔 소비기는 `--max-messages` 없이 쓰면 끝나지 않는다. Python 안 Windows 경로는 raw 문자열. 출력 래퍼(rtk)가 grep 결과를 변형하니 파일은 Python 으로 읽는다. 벤치용 이미지 약 60 GB(C: 여유 약 78 GB) — 층 끝나면 정리.

## 7. 미결정·외부 대기
- **Mosquitto 조건부 4항목**(단절·과부하·느린 구독자·장시간 — `harness/brokerbench/stage4_mosq.sh`, `harness/situations/BROKER.md`) 미실행.
- 레이어 재설계안·스택 조합 선택(§3 다음 2~3), InfluxDB 2.9.1 초기화 오류, ingest 디스크 버퍼 경로, V1·V2 회귀(한 번도 안 돌림), 알람 수명주기(E10: V1 공백 — alarmbench 미실행), 감시 층(monbench 미실행, V1 E11 0/2), S2·S12(Telegraf 1.40.1 에서 해결 여부 — V2 R01·R03 로 확인), S13·S14 확인, 브로커 3회(Mosquitto 중복 1 vs RMQTT 0).
- 사람 답 대기: `QUESTIONS.md` §3(LiteLLM 버전, 원본 Flink 잡, Docker Desktop 유료 조건, 기준선 재동결).

## 8. 넘으면 안 되는 선
- 원본 `D:\work\study\lecture-iiot-scada` 수정 금지, 원본 컨테이너·볼륨·이미지(`iiot*`·`ar100*`) 수정·삭제·덮어쓰기 금지(같은 이름 재빌드 금지, 원본 그래프는 읽기 전용 복사만). push 금지, `latest` 태그 금지. BSL·SSPL·TSL·RCL·체험판·상용 금지.
- `ai-layer/.env.local` 키 출력·커밋 금지. LLM 호출은 필요한 만큼만(크레딧).
- 측정 안 한 수치 금지, 무효 실행도 decision-log 에 추가(추가만), 실행 ID 재사용 금지. 결과 보기 전 기준·정답 고정.
- 무거운 측정은 메모리 대기 장치 아래에서만, 쓰지 않는 벤치는 바로 정리. 서브에이전트에게는 컨테이너 기동·격리 컨테이너 exec 금지를 명시(#80).

## 9. 보고 문서 2개 (실측이 끝난 뒤, 사양 09-29 확정)
- **문서 1 `reports/REPORT.md`(+HTML) 대표님 보고서 — 짧게, 대조 중심:** ① 한 장 요약(무엇을 바꿨고·얼마나 나아졌고·무엇을 잃었나) ② 변경 전후 아키텍처 그림 두 장을 같은 L1~L9 틀로 나란히(제거 부품은 흐린 점선, 새 부품 강조, 알람→화면 경로를 같은 색으로 따라가 단계 수 비교) ③ 층별 대조표(원래 → 바뀐 것 → 왜 → 실측, 유지한 층도 이유) ④ 안정성 궤적(대장의 열림→닫힘, 회전별) ⑤ 엑셀형 점수표(`harness/tools/scorecard.py`, 미측정 표시, 증거에서 재계산) 부록. AI 층 표는 `harness/tools/report_ai.py`.
- **문서 2 쉬운 시스템 설명서(최종 버전):** `docs/소스코드로_확인한_아주쉬운_시스템설명.html`(V1판, 보존)과 같은 순서(① 설비 → ② 전체 아키텍처 한 장 → ③ "교반기의 떨림 하나가 화면의 경고가 되기까지")와 문체로 새 파일. 바뀐 단계마다 "V1에서는 → 이제는" 상자, L1~L9 가로 레이어, 색 규칙(파랑 데이터·보라 AI·주황 명령), 화살표 교차 없이, 모든 화살표를 실제 코드·설정과 대조.
- 사용자 TODO DoD 8(배속 결과 = 배속 도입 전 결과)은 새로 느린 실행을 하지 않고 배속 도입 전 기록(`experiments/EXP-AI` 저속 회차, `EXP-000`)과 같은 시나리오를 대조해 판정한다.
- STUDY 규칙: 작업을 마치면 `D:/work/작업보고/<날짜>.md` 갱신 — 세션 2(2026-09-29) 분은 아직 안 함.

## 10. 자산 지도
| 위치 | 역할 |
|---|---|
| `D:\work\study\scada-rotation`(브랜치 `exp/stack-rotation-202609`, 기준 태그 `v1-original`) | 작업 폴더(원본과 분리된 사본) |
| `QUESTIONS.md` §1 | 판정 기준 정본 |
| `reports/decision-log.md` | 모든 실행·판정(#1~#98, 추가만) |
| `reports/STABILITY.md` · `reports/CONFIRMED.md` | 내부 오류 대장 · 원래→바뀜 |
| `harness/situations/` | 결과 전 고정 시험 목록(CANDIDATES·ROBUSTNESS·STRUCTURE·L4·BROKER·paths.yaml) |
| `harness/` | 측정 도구·층 벤치(층 결과 재계산 `harness/tools/layer_*.py`, 전체 측정 `harness/e2e/baseline.sh`+`struct_V2.sh`, 회귀 `harness/e2e/regression.sh`) |
| `experiments/EXP-*/layer_*.json` · `experiments/STAGE2_RUNS.log` | 층별 후보 실측 요약(세션 3) |
| `docker-compose.v2.yml` · `v2/` · `flink/Dockerfile.v2` | V2 조립 초안(검증 전) — 재설계 문서 `reports/V2_DESIGN.md`(다음 세션에서 작성)에 맞춰 고친다 |
| `experiments/EXP-001`(V1 기준, V2 설비) · `EXP-AI` · `EXP-L4` · `EXP-S09` · `EXP-130` · `EXP-000`(참고) | 증거 원본 |
| `simulator/`(V2 설비) · `ai-layer/`(V2 AI 코드) · `ontology/v2/` · `knowledge-docs/` | 바꾼 부품 |
| `docs/research/`(원문·딥리서치 `deep-2026-09-29/01~05`) | 근거 |
| 원본 `D:\work\study\lecture-iiot-scada` | 읽기만 |

## 11. 갱신 규칙
- 측정·조사 완료 → §3·§4, 방향 결정 → §1·§2(+decision-log), 기준 변경은 `QUESTIONS.md` §1 에서만, 틀린 것 → §5, 실행 상태 → §3·§6, 내부 오류 → `STABILITY.md`.
- 조각 덧댐 금지 — 모순이 생기면 해당 절을 통째로 교체. §1·§2·§8 변경은 사용자 지시로만.
