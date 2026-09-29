# HANDOFF — V1 IoT·SCADA 기반을 회전으로 안정적인 시스템으로 (scada-rotation)

최종 갱신 2026-09-29 11:15 · 작성 Claude Code(세션 2 종료, 새 세션으로 넘김)
**이 문서만 읽고 이 작업을 이어갈 수 있게 쓴다.** 실제 파일·실행 상태·사용자 지시와 다르면 실제가 우선이고 이 파일을 고친다.
**판정 기준의 정본은 `QUESTIONS.md` §1 하나다.** 이 파일은 기준을 복제하지 않고 가리킨다.

---

## 0. 처음 읽는 사람을 위한 순서 (20분)
1. **이 파일 전체**(특히 §1 목표, §2 지시, §3 멈춘 지점).
2. `QUESTIONS.md` §1 — 판정 기준(관문 → 성능·안정성 → 효율 → 운영 참고), 시간 원칙, 후보 원칙, 시험 범위.
3. `reports/STABILITY.md` — 기반 내부 오류 대장(병행 과제의 목록).
4. `reports/CONFIRMED.md` — 지금까지 원래→바뀜 한 장.
5. `harness/situations/CANDIDATES.md` 맨 앞 개정 절(#92·#90·#74) — 후보 목록 규칙. 본문 표보다 개정 절이 우선.
6. `harness/situations/ROBUSTNESS.md`·`STRUCTURE.md` — 비정상(R01~R11)·구조 측정(E1~E12) 목록, 시간 값은 #89 개정.
7. **리서치 원문(`docs/research/`)** — 반드시: `AGENT_BRIEF_FINAL.md`(회귀 S01~S25·G0~G10 정의·절차), `ARCHITECTURE_SIMPLIFICATION.md`(V1 중복·우회 분석·구조안 = 구조 재조립 근거), `deep-2026-09-29/01~05`(후보별 라이선스·지원 종료 사실과 출처). 참고만: `AGENT_BRIEF.md`·`AGENT_BRIEF_v2.md`(FINAL 에 흡수된 옛 판)·compass 4종 — 충돌하면 FINAL·사용자 지시가 이긴다.
8. 필요할 때만 `reports/decision-log.md` 해당 번호(#1~#98, 추가만). 이 문서가 인용한 번호부터 본다.
9. 시작 전 반드시 `git status`, `docker ps`, 원시 토픽 흐름(§6 명령)으로 실제 상태 대조.

## 1. 목표와 우선순위 (사용자 확정 2026-09-29)
- **메인:** V1(현업 수준 프로토타입)을 여러 회전(V1→V2→…)으로 다듬어 **최종 아키텍처를 고르고**, 무엇을 왜 바꿨고 얼마나 나아졌는지 **실측 궤적**으로 대표님께 보고한다. 한 회전 = 층별 후보 시험 → 승자 조립(구조 재조립 포함) → 전체 회귀 → 버전 태그(v2, v3…). 기준은 회전마다 올라가고, 기준을 넘는 개선이 없는 회전에서 멈춘다.
- **병행(부가):** 매 회전 **안정적으로 도는지·e2e 가 전부 정상인지** 꼼꼼히 확인한다. 돌리면서 드러나는 **내부 오류**(로그 예외, 조용한 정지, 유실·중복, 오경보)를 `reports/STABILITY.md` 에 올리고 고친다.
- **결과:** 온톨로지·시나리오가 바뀌어도 흔들리지 않는 **단단한 기반 틀**.
- **담당 범위 = 기반**(수집·브로커·중계·백본·탐지·저장·감시·알람 경로). **온톨로지·시나리오 구체화는 담당 밖** — AI 층은 지금까지 만든 것(V2 도구, 비교 측정 #83·#84)에서 멈춘다.
- 쓰임: 경남대 제조 AI 실습·시연. 이상→감지→AI 조치가 **수 초~수 분 안에** 이어져야 한다.
- 원 과제 문서: `docs/research/AGENT_BRIEF_FINAL.md`(절차), `ARCHITECTURE_SIMPLIFICATION.md`(V1 중복·우회·구조안). **사용자 지시가 문서보다 우선.**

## 2. 사용자 확정 지시 — 어기면 신뢰 붕괴 (재론하지 않는다)
1. **질문에는 먼저 자연어로 답한다.** "~하면 안 되나?" 같은 질문을 지시로 받아 바로 바꾸지 않는다(권고로 답하고 결정을 기다림). 답한 뒤에는 묻지 말고 진행. 단계마다 번호 붙은 짧은 중간 보고.
2. **시간:** 가상설비는 **배속이 시스템 기본값**(`simulator/plant.yaml physics_time_scale: 600`, 서서히 진행하는 현상은 하나의 설비 시계, 순간 사건만 실제 초). 그 반대 개념을 가리키는 말은 쓰지 않는다. 이상 주입→알람 10초 이내, 한 사이클(이상→감지→AI 조치 제안) 1분 이내, 전체 흐름 수 분 안. 오래 걸리면 배속·범위부터 줄이고, 소요 시간은 짐작 말고 첫 실행을 재서 말한다(#87~#89·#95).
3. **후보 = 다른 제품만**(A 제품 대 B 제품). 같은 제품은 판·설정 모두 후보가 아니다 → 가장 좋은 지원 판을 번호로 고정(회귀에서 한 번에 확인). 판 얘기는 보고에서도 하지 않는다(#90·#92).
4. **보강 없음**, 예외 하나: **Flink 재시작 복구(HA, Flink 내장 기능 — 설정만)는 켠다**(V1 은 이 기능을 꺼 둔 채 운영해 재시작 때 탐지 잡이 사라짐, #93·#94).
5. **관찰된 내부 오류는 고친다**(근거 있는 수정). 관찰 없이 미리 하는 설정 보강은 하지 않는다(#96).
6. **시험 범위 = 그 제품이 닿는 앞뒤 구간.** 같은 층 후보는 같은 입력으로 나란히(두 줄 동시 실행), 전체 스택 측정은 V1 기준 1회·버전 확정 1회(#91).
7. 효율 우선, 되돌릴 수 있는 일은 묻지 않고 한다. 넘으면 안 되는 선은 §8.
8. **사실 기반, 추론 금지.** 모든 판단·수치는 실행 결과·로그·파일·1차 출처로 증명 가능해야 한다. "~같다·~로 보인다"로 결론 내리지 않는다 — 확인 못 한 것은 "미확인"과 확인 방법으로 쓴다. 바꾸기 전에 그 변경이 닿는 문서·설정·측정을 모두 찾아 영향을 파악한다(예: #97 은 짐작으로 원인을 잘못 짚었다가 로그·Kafka 오프셋으로 정정).

## 3. 지금 멈춘 지점 (2026-09-29 11:15)
- **실행 중:** 격리 V1 전체(`rot-iiot` SCADA + `rot-ai` AI, 컨테이너 29) — 시뮬레이터만 V2 설비 이미지 `rot-plant-simulator:v2-ts`(배속 600). 측정 프로세스 없음. 원시 토픽 흐름 **정상 재개 확인**(11:10:31, 10초에 144건 = 12태그×약 1.2/s).
- **EXP-001 = V1 기준 전체 측정(V2 설비, 시간 값 #89)** — 결과 #97:
  - **유효:** E3 메모리 합계 5,918 MiB·CPU 51.2 % · R09(3분) 유실 0·중복 0 · E7 99.17 % · E12 인증 없이 열린 접점 10/11 · E1 30회 p95 중앙값 Kafka 1.67 s·FUXA 태그 1.84 s·AI 사건 2.06 s · R01 브로커 10 s 정지 유실 0·복구 14 s · **R02 단절 10 s 유실 132·공백 12 s** · R07 업무 DB 다운 시 명령 거부·설비 불변.
  - **무효:** R03 이후(R03·R06·R08) — **Kafka 재시작 뒤 수집 중계기(Telegraf#1)가 로그 없이 정지**(대장 S2)해 오염. 11:08:39 중계기 수동 재시작(`experiments/EXP-001/manual_actions.log`).
- **바로 다음(순서대로):**
  1. `harness/e2e/baseline.sh` 의 `wait_flow` 를 **"2분 연속 흐름"** 으로 고친다(지금은 Influx 최근 3초만 봐서 잠깐 흘렀다 멈추는 것을 복구로 오판). R01·R02·R07 은 유효하므로 건너뛰는 인자를 넣고 **R03·R06·R08·R11·E11 만** `PHASES=3` 으로 다시(EXP-001 에 새 실행 ID, 분리 실행). S2 가 재현되면 그것이 V1 기준값이다(복구 안 됨 = 수동 필요).
  2. `sh harness/tools/internal_errors.sh 30m experiments/EXP-001/internal_errors_V1.json` → 새 오류를 `reports/STABILITY.md` 에 추가.
  3. EXP-001 최종 결과를 decision-log 에 기록.
  4. 격리 스택 내림: `docker compose --env-file .env --env-file .env.rotation stop` / `COMPOSE_PATH_SEPARATOR=: docker compose -p rot-ai --env-file ai-layer/.env.local --env-file .env.rotation -f ai-layer/compose.yml -f ai-layer/compose.scada.yml --profile knowledge stop`(볼륨 보존).
  5. **층별 후보 ② 실행:** PowerShell `Start-Process D:\dev\Git\bin\bash.exe -ArgumentList '-c "cd /d/work/study/scada-rotation && sh harness/run_lanes.sh"'` — 무거운 줄(l4·backbone·ts)과 가벼운 줄(broker·ingest·pipe·alw·mon·alarm·hmi) 동시, 메모리 4.5 GB 대기 장치. 결과 `experiments/EXP-*/stage2_*.json`, 요약 `experiments/STAGE2_RUNS.log`(실행 시 생성). 첫 몇 후보의 실제 소요를 재고 병목부터 줄인다. 각 후보 뒤 내부 오류 수집. ②에서 떨어지면 뒤 단계 생략, 살아남은 1~2개만 ③ 성능·④ 비정상(`stage4*`). 각 벤치 `STAGE2.md` 에 판정 항목.
  6. 층 승자 + 대장 해결 + 구조 패턴(`CANDIDATES.md` §11: 브로커 Kafka 브리지로 Telegraf#1 제거, HMI 브로커 직접 구독, 저장소 3→2, 명령 경로 일원화 등)으로 **V2 조립** → EXP-001 과 같은 전체 측정 + S01~S25·G0~G10 회귀 → 통과 시 태그 `v2`. Flink HA 설정은 여기서 켠다(`harness/l4bench` profile `flinkha` 로 먼저 확인).
  7. 다음 회전은 대장 "열림"·조건부 층만. 개선 없는 회전에서 멈춤.
  8. 보고 문서 2개(§9).

## 4. 확정 사실 — 다시 조사하지 마라
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
| 이전 설비·긴 시간 값으로 잰 EXP-000 P1·E1 일부, EXP-AI 의 저속 회차 | 참고 기록만, 판정에 쓰지 않음 |

## 6. 실행 환경·명령
- **재기동(격리 V1):** SCADA `docker compose --env-file .env --env-file .env.rotation up -d --no-build` 후 V2 설비 `docker compose --env-file .env --env-file .env.rotation -f docker-compose.yml -f docker-compose.edgex.yml -f docker-compose.timescale.yml up -d --no-build --no-deps plant-simulator`. AI(V1) `COMPOSE_PATH_SEPARATOR=: docker compose -p rot-ai --env-file ai-layer/.env.local --env-file .env.rotation -f ai-layer/compose.yml -f ai-layer/compose.scada.yml --profile knowledge up -d --no-build`(V2 AI 는 `-f ai-layer/compose.v2.yml` 추가). Docker 재시작 뒤 Flink 잡 0개면 `docker start -a rot-flink-job-submitter`.
- **흐름 확인:** `docker exec rot-kafka /opt/kafka/bin/kafka-get-offsets.sh --bootstrap-server localhost:9092 --topic sensor.telemetry.raw` 를 10초 간격 두 번, 합계 증가 약 144 가 정상.
- **측정 도구(`harness/`, 솔루션 부품 아님):** `e2e/baseline.sh <EXP> <이름>`(PHASES 0~3), `e2e/completeness.py`(유실·중복·공백), `e2e/e1.py`(알람→화면), `e2e/fault_onset.py`(고장→알람), `e2e/security_probe.py`(E12), `e2e/screen_vs_history.py`(E7), `e2e/loadgen.py`(R08), `tools/e2_complexity.py`, `tools/e3_summary.py`, `tools/internal_errors.sh`, `run_all_stage2.sh`·`run_lanes.sh`, 층 벤치 `*bench/stage2*.sh`·`STAGE2.md`, 측정 컨테이너 이미지 `e2e-client:1.0`(망 `rot-iiot`, `--env-file .env`).
- **환경 함정:** 호스트 RAM 15.7 GB·Docker VM 7.6 GB — 전체 스택+AI 로 엔진 500 오류 사례(#81). Docker Desktop 경로 `C:\Users\roede\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe`. 긴 작업은 PowerShell `Start-Process D:\dev\Git\bin\bash.exe`(system32 bash 는 WSL, 도구 백그라운드는 10분에 죽음). Git Bash 에서 컨테이너 경로 인자는 `MSYS_NO_PATHCONV=1`. 모니터는 5~30분에 만료되니 다시 건다. Kafka 콘솔 소비기는 `--max-messages` 없이 쓰면 끝나지 않는다. Python 안 Windows 경로는 raw 문자열. 출력 래퍼(rtk)가 grep 결과를 변형하니 파일은 Python 으로 읽는다. 벤치용 이미지 약 60 GB(C: 여유 약 78 GB) — 층 끝나면 정리.

## 7. 미결정·외부 대기
- 층별 승자(§3 다음 5), 구조안(§3 다음 6), 오토인코더 재학습 방법(대장 S6), S2 원인 확정(재현 필요), S8 보안(기반 확정 때 판단), S11 Kafka 유휴 CPU.
- 사람 답 대기: `QUESTIONS.md` §3(LiteLLM 버전, 원본 Flink 잡, Docker Desktop 유료 조건, 기준선 재동결).

## 8. 넘으면 안 되는 선
- 원본 `D:\work\study\lecture-iiot-scada` 수정 금지, 원본 컨테이너·볼륨·이미지(`iiot*`·`ar100*`) 수정·삭제·덮어쓰기 금지(같은 이름 재빌드 금지, 원본 그래프는 읽기 전용 복사만). push 금지, `latest` 태그 금지. BSL·SSPL·TSL·RCL·체험판·상용 금지.
- `ai-layer/.env.local` 키 출력·커밋 금지. LLM 호출은 필요한 만큼만(크레딧).
- 측정 안 한 수치 금지, 무효 실행도 decision-log 에 추가(추가만), 실행 ID 재사용 금지. 결과 보기 전 기준·정답 고정.
- 무거운 측정은 메모리 대기 장치 아래에서만, 쓰지 않는 벤치는 바로 정리. 서브에이전트에게는 컨테이너 기동·격리 컨테이너 exec 금지를 명시(#80).

## 9. 보고 문서 2개 (실측이 끝난 뒤, 사양 09-29 확정)
- **문서 1 `reports/REPORT.md`(+HTML) 대표님 보고서 — 짧게, 대조 중심:** ① 한 장 요약(무엇을 바꿨고·얼마나 나아졌고·무엇을 잃었나) ② 변경 전후 아키텍처 그림 두 장을 같은 L1~L9 틀로 나란히(제거 부품은 흐린 점선, 새 부품 강조, 알람→화면 경로를 같은 색으로 따라가 단계 수 비교) ③ 층별 대조표(원래 → 바뀐 것 → 왜 → 실측, 유지한 층도 이유) ④ 안정성 궤적(대장의 열림→닫힘, 회전별) ⑤ 엑셀형 점수표(`harness/tools/scorecard.py`, 미측정 표시, 증거에서 재계산) 부록. AI 층 표는 `harness/tools/report_ai.py`.
- **문서 2 쉬운 시스템 설명서(최종 버전):** `docs/소스코드로_확인한_아주쉬운_시스템설명.html`(V1판, 보존)과 같은 순서(① 설비 → ② 전체 아키텍처 한 장 → ③ "교반기의 떨림 하나가 화면의 경고가 되기까지")와 문체로 새 파일. 바뀐 단계마다 "V1에서는 → 이제는" 상자, L1~L9 가로 레이어, 색 규칙(파랑 데이터·보라 AI·주황 명령), 화살표 교차 없이, 모든 화살표를 실제 코드·설정과 대조.
- STUDY 규칙: 작업을 마치면 `D:/work/작업보고/<날짜>.md` 갱신 — 세션 2(2026-09-29) 분은 아직 안 함.

## 10. 자산 지도
| 위치 | 역할 |
|---|---|
| `D:\work\study\scada-rotation`(브랜치 `exp/stack-rotation-202609`, 기준 태그 `v1-original`) | 작업 폴더(원본과 분리된 사본) |
| `QUESTIONS.md` §1 | 판정 기준 정본 |
| `reports/decision-log.md` | 모든 실행·판정(#1~#98, 추가만) |
| `reports/STABILITY.md` · `reports/CONFIRMED.md` | 내부 오류 대장 · 원래→바뀜 |
| `harness/situations/` | 결과 전 고정 시험 목록(CANDIDATES·ROBUSTNESS·STRUCTURE·L4·BROKER·paths.yaml) |
| `harness/` | 측정 도구·층 벤치 |
| `experiments/EXP-001`(V1 기준, V2 설비) · `EXP-AI` · `EXP-L4` · `EXP-S09` · `EXP-130` · `EXP-000`(참고) | 증거 원본 |
| `simulator/`(V2 설비) · `ai-layer/`(V2 AI 코드) · `ontology/v2/` · `knowledge-docs/` | 바꾼 부품 |
| `docs/research/`(원문·딥리서치 `deep-2026-09-29/01~05`) | 근거 |
| 원본 `D:\work\study\lecture-iiot-scada` | 읽기만 |

## 11. 갱신 규칙
- 측정·조사 완료 → §3·§4, 방향 결정 → §1·§2(+decision-log), 기준 변경은 `QUESTIONS.md` §1 에서만, 틀린 것 → §5, 실행 상태 → §3·§6, 내부 오류 → `STABILITY.md`.
- 조각 덧댐 금지 — 모순이 생기면 해당 절을 통째로 교체. §1·§2·§8 변경은 사용자 지시로만.
