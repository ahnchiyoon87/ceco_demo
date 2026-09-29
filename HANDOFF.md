# HANDOFF — V1 IoT·SCADA·AI 현업 스택 다듬기 (scada-rotation)

최종 갱신 2026-09-29 · 작성 Claude Code(세션 2 종료 — 사용자 급한 인계 요청)
**재개용 기록이다. 현재 사용자 지시·실제 파일·실행 상태와 대조하고, 다르면 실제가 우선이며 이 파일을 고친다.**
**판정 기준의 정본은 `QUESTIONS.md` §1 하나다. 이 파일은 기준을 복제하지 않는다.**

## 0. 30초 브리핑
V1은 현업 수준 시스템이지만 약간 비효율적이고, 중복·빙빙 도는 경로·낡은 스택이 섞여 있다. 여러 회전(V1→V2→…)으로 **전부 검증된 최선 버전**을 만들어 대표님께 실측 근거로 보고한다. 목적(사용자 TODO): 경남대 제조 AI 실습용 — **시연·실습에서 이상→감지→AI 조치가 수 초~수 분 안에** 이어져야 한다.
**끝난 것(세션 2):** 딥리서치·후보표 결과 전 고정(#69·#74) · AI 층 비교 측정 완료(#83·#84, SC3 코드 0줄 #73) · 층별 직접 시험 벤치 10종 **준비만**(실행 0건) · E2(V1 34서비스·알람→화면 12단계) · V2 가상설비 시간 배속 재설계(#88, 단위 시험 통과, 전 파이프라인 실측 전).
**안 끝난 것:** 층별 ② 실행 → 기준 V1 전체 측정(E1·R 시험, 새 배속 설비·수 분 안 설계로 다시) → 구조 재조립 → 회전 확정 v2 → 보고 문서 2개.

## 1. 배경
- 의뢰: 대표님. "사전 스펙이 아니라 빠르게 구현해 모듈별로 실측·비교, 최신 트렌드, 기술선정·온톨로지·시나리오가 개선된 궤적을 가져와라."
- 근거 문서(원문 보관 `docs/research/`): `AGENT_BRIEF_FINAL.md`(절차: OSI·0원·G0~G9·S01~S25·CQ15·회전), `ARCHITECTURE_SIMPLIFICATION.md`(V1 중복·우회 분석, 구조안 A~D, 검증 실험 E1~E12), compass 4종(근거 조사). **사용자 지시가 문서보다 우선.**
- 범위: 프로토타입 확정과 궤적 보고까지. 실라버스·강의는 다른 곳에서 한다. 시킨 것만 한다.
- 사용자 /goal DoD(요약)와 이후 사용자 지시로 바뀐 점:
  | DoD | 내용 | 조정 |
  |---|---|---|
  | 1·2 | L4 후보 실측(정확도·지연·자원·재시작 3시점) → 규칙 판정 | 후보 중 직접 짠 Python은 탈락(직접 제작 금지). Flink 1.20 / 2.2.1 SQL / 2.2.1 CEP / Flink HA로 진행 |
  | 3 | 브로커 EMQX 대체 | Mosquitto 조건부 채택(비정상 상황 추가 시험 남음) |
  | 4 | AI: 그래프 DB 온톨로지(증상→고장모드→원인→점검/절차), CQ15 V1 대비, 베어링·히터 고착 2시나리오 사전 정답 채점, 새 고장 코드 0줄 | 그대로 |
  | 5 | V2 회귀 S01–S25·G0–G10 → 태그 `v2` | 그대로 |
  | 6 | 모든 실행 decision-log, 보고 수치 재계산 | 그대로 |
  | 7 | REPORT.md(V1 대 후보, 점수·약점·판정), 원본 V1 무수정 | "원본 미커밋 76건 그대로"는 원본이 다른 작업으로 계속 바뀌어 판정 불가 → "이 작업이 원본에 쓰지 않았음"으로 판정 |

## 2. 여섯 축 — 무엇을 어떻게 (재개 시 가장 먼저 읽어라)
**진행 원칙(09-29 사용자 확정):**
- **모든 것을 직접 시험한다.** 문헌으로 빼는 것은 라이선스·약관·보안 패치 종료·컨테이너 불가 같은 사실뿐.
- **회전 수는 정하지 않는다. 기준은 회전마다 올라간다:** 1회전은 V1 대비, 확정된 V2가 2회전의 기준, V3는 V2 대비… (QUESTIONS §1 "기준 버전"). 한 회전 = 층·구조 후보 전부 시험 → 승자 조립 → 전체 회귀 → 버전 확정. 다음 회전은 그 버전을 기준으로 새로 드러난 약점·조건부 항목을 다시 돌린다. **한 회전을 돌아도 기준을 통과하는 개선이 없으면 멈춘다** — 그 버전이 검증된 최선.
- **기준 측정은 두 종류:** 층별 기준은 층 벤치마다 V1 부품을 후보와 함께 띄워 동시에 잰다(따로 재지 않음). 전체 기준(알람→화면 전체 경로 시간, 전체 자원, 연쇄 장애)은 구조 비교 직전에 V1 전체 스택으로 한 번 잰다.
- **어쩔 수 없는 교체는 성능과 무관하게 한다:** ① 관문에 걸리거나 12개월 안에 지원 종료가 예정된 부품은 반드시 교체, 가장 덜 나빠지는 후보를 고르고 약점으로 명시(QUESTIONS §1 강제 교체).
- **상식 점검 결과(09-29):** 모든 층의 첫 후보는 같은 제품 최신 버전 · 성능·자원은 3회 이상 반복 중앙값 · ① 관문 → 수 분짜리 기동 확인 → 긴 시험 순으로 빠르게 거름 · 개선 없으면 유지도 결과 · 기본 보안(인증·접근 제어) 확인 · 보고서 맨 앞에 대표님용 한 장 요약(무엇을 바꿨고, 얼마나 나아졌고, 무엇을 잃었나).
- **AI 층은 처음부터 병행한다.** 하부 구조에 기대는 곳은 알람→사건 입구와 센서 이력 조회 두 곳뿐이고 나머지(온톨로지·정답·도구·CQ)는 독립이며 메모리를 거의 쓰지 않는다. 벤치가 돌지 않는 시간에 진행하고 두 입구는 V2 조립 때 연결.

| # | 축 | 어떻게 | 상태 |
|---|---|---|---|
| 1 | **기준 버전 측정** | 층별 기준은 층 벤치에서 후보와 동시에 잰다(축 2). 전체 기준은 구조 비교 직전에 기준 버전 전체 스택(1회전은 격리 V1, §6)으로 정상 E1~E12(`harness/situations/STRUCTURE.md` §3) + 비정상 R01~R11(`ROBUSTNESS.md`)을 잰다 | 스택 기동 검증까지 완료. **측정값 없음**(E3 30분이 중간에 멈춤, 부분 데이터는 사용하지 않음) |
| 2 | **대안 조사·직접 시험(부품)** | 후보표 `harness/situations/CANDIDATES.md`. 2026 기준 딥리서치로 후보 확장(§9-2 방법) → 문헌 제외는 ① 관문(라이선스·약관·EOL·컨테이너)뿐 → 나머지는 층 벤치에서 기준 버전 부품과 함께 직접 ① 기동·기능 → ② 정상 성능 → ③ 비정상, 앞 단계 탈락 시 생략 | 후보표 재고정 ✓(#69·#74). 10개 층 벤치 준비 ✓(f83197f·fe5c9e6, `harness/*bench/STAGE2.md`), **실행 0건** — `harness/run_all_stage2.sh` |
| 3 | **레이어 재조립(구조)** | V1의 빙빙 도는 경로·중복(알람 되돌림 약 8단계, 중계 5중 EMQX·Telegraf×3·Kafka, EdgeX·FUXA 이중 폴링, 설비 쓰기 경로 3개, 저장소 3개)을 줄인 조립안을 실제 전체 스택으로 조립해 축 1과 같은 측정. 검토서 A(보수적)부터, 축 2 승자로 조립 | 미착수. 검토서 C(Kafka·Flink 제거 + 직접 짠 탐지기)는 직접 제작 금지로 본안 제외(#57) |
| 4 | **교체 없는 보강·빈 기능** | Flink HA(JobManager 재시작 시 잡 소멸 = V1 최대 약점), FUXA 보안 버전(1.3.4 이상) 확인, 기본 보안(인증·접근 제어), 이미지 버전 고정, 알람 수명주기(ISA-18.2), 설비 쓰기를 Pilot 관문으로 일원화 | Flink HA 벤치 구성만 커밋(`harness/l4bench` profile `flinkha`), 미실행 |
| 5 | **회전마다 합쳐 전체 회귀 → 버전 확정** | 축 2~4 승자 조립 → S01~S25 + G0~G10 + 축 1 측정 전부 → 통과 시 태그 `v2`, 약해진 수정은 되돌림. 다음 회전 V2→V3 | 미착수 |
| 6 | **AI 온톨로지·시나리오 진화 + 궤적 보고** | V1 에이전트(LLM+LangGraph+가드레일) 유지 + 온톨로지 그래프 원인분석 도구 + 매뉴얼 의미검색(임베딩+그래프). CQ 응답 수 기준 버전 대비, 회전 실패 유형을 시나리오로 추가. 점수표 → `reports/REPORT.md` | **측정 완료:** 프로토콜 #68 · 세 팔 채점 #83(`experiments/EXP-AI/score.json`) · CQ15 #84 · SC3 코드 0줄 #73 · 검색 Recall@3 약점 #70·#72. 남음: 임베딩 후보(KURE·e5·Qwen3·TEI·재순위기) 비교, V2 조립 때 두 입구 연결, 새 배속 설비에서 재확인(DoD 8) |

## 3. 판정 기준 → `QUESTIONS.md` §1 (유일한 정본)
한 줄 요약: ① 쓸 수 있는가(비용 0·상용화 문제 없음·도커·보안 패치·기본 보안·안전)로 거르고, ② 성능·안정성(기준 버전이 하던 일 전부·정확도·속도·복구·비정상 상황, **기준 버전보다** 나빠지면 탈락, 해피패스만 가능 = 무너짐, 3회 이상 중앙값)으로 탈락시키고, ③ 효율(메모리·CPU·용량·복잡도 = 아키텍처가 빙빙 도는 정도·중복)로 고르고, ④ 운영·유지보수는 참고. 예외: ① 관문에 걸리거나 12개월 안 지원 종료 예정인 부품은 강제 교체(가장 덜 나빠지는 후보 + 약점 명시). 직접 짠 코드로 엔진급 기능 대체 금지. 대안은 추론 말고 직접 시험. 개선 없으면 유지도 결과. 판정은 스스로 내리고 기록(사용자 위임). **자세한 규칙은 QUESTIONS §1만 본다.**

## 4. 확정 사실 — 다시 조사하지 마라
- **V1 구성:** 34서비스(SCADA 20 + EdgeX 10 + AI 4). Flink 1.20.1, Kafka 3.9.0(KRaft), EMQX 5.8.6(2026-02-28 EOL), InfluxDB 2.7, FUXA 1.3.x, Neo4j 5.26, Prometheus+Alertmanager → `harness/V1_FACTS.md`, `V1_INVENTORY.md`, `SCHEMA.md`. 흐름: 설비 → EdgeX → EMQX → Telegraf#1 → Kafka → Flink(규칙 SQL 3 + ONNX 잡) → Kafka → Telegraf#2 → InfluxDB / Telegraf#3 → EMQX → FUXA, 알람 워커 → PostgreSQL. 격리 기동 시 텔레메트리 `edgex/telemetry` 약 1.1건/s 정상 확인.
- **V1 약점(실측):** JobManager 재시작 시 잡 소멸 → 유실 11~12(`experiments/EXP-S09`). HA 없는 세션 클러스터 + latest-offset.
- **브로커(`experiments/EXP-130`, 2회):** Mosquitto 2.1.2 정상 p95 1.7ms(EMQX 2.3~2.6), 재시작 유실 0(EMQX 4·69), 재시작 넘어 큐·retained 보존(EMQX ✗), 메모리 약 5MiB(EMQX 약 250MiB), 이미지 13MB(105MB), 설정 9줄(45), 지표는 $SYS(HTTP 없음). **조건부**: 네트워크 단절·과부하·느린 구독자·장시간 미검증. NanoMQ 탈락(구독자 오프라인 600건 수신 0, 재구독해도 0), HiveMQ CE 탈락(재시작 유실 527·569, p95 약 47ms, 지표 없음).
- **이상탐지(`experiments/EXP-L4`):** Flink 1.20 / 2.2.1 SQL / 2.2.1 DataStream CEP 규칙 알람 V1과 동일(4회 70/70), ONNX 점수 동일(S13 정상상태 방식, 차 0), 운영 지표 노출. TaskManager kill 시 중복 3이 가끔(1.20 3회 중 1, 2.2 3회 중 2). 버전 판정 **미정**. 직접 짠 Python은 탈락(#53).
- **V1 ONNX 잡 잠재 결함:** Interpolator 키가 tag(장치 구분 없음) — 다중 장치에서 섞임(보고서 기록 대상).
- **환경:** Docker VM 7.6GB → 무거운 측정은 하나씩. 이 작업 폴더는 체크아웃 때 CRLF로 바뀌어 컨테이너 셸 스크립트가 깨졌음 → 작업 폴더 텍스트 파일을 저장소와 같은 LF로 되돌림(git 내용 변경 없음. `flink/sql/tag_limits.csv`는 저장소 원본도 CRLF라 그대로).
- **측정 함정:** EMQX는 기본 ACL로 `#` 구독을 거부 → 확인 구독은 토픽을 명시하고 SUBACK 코드를 본다. Flink 잡 목록은 CANCELED 이력이 남는다(사전 점검은 취소·완료 제외). ONNX 점수는 처리시각 타이머라 순차 창 비교는 V1 자신도 비결정적(정상상태 방식 사용).

- **AI 층(세션 2):** V1 그래프 = Asset·Sensor·Document·DocumentSection·ControlPoint(원본 볼륨 복사, 검토 게시 8건). V1 에이전트는 도구 3개(알람·연결 문서 전문·센서 통계), 의미검색 미사용. **TT-102(재킷 온도)는 설비 소속이 없어 V1 근거 조회에 안 들어감** → 히터 고착 판별 관측을 못 봄. `cooler_enable` 제어점이 V1 그래프에 없었음. V1 임베딩은 실패 시 0벡터를 조용히 반환(결함). V2 = V1 에이전트 + `trace_fault_ontology`·`search_manual_sections`(neo4j-graphrag 1.21 VectorCypherRetriever) + 고장모드별 평가 출력(확정 상태 없음), 재귀 한도 12→20. 이미지 `rot-ai-knowledge:v2-ai` 1.45GB(V1 1.16GB). 임베딩 Ollama 0.34.4+bge-m3: 기본 3.28GiB → 병렬1·문맥2048 1.25GiB(#71).
- **문헌 사실(딥리서치, 실행 아님):** Neo4j 5.26 LTS 2028-06-06까지, Kafka 3.9 2027-02-19 종료, InfluxDB 지원은 2.9.1·2.8만, Telegraf 패치는 1.39·1.40만, FUXA 1.3.3 미만 High CVE 3건, EMQX 5.9+ BSL. 상세·출처는 `CANDIDATES.md`.

## 5. 이전 세션의 실수와 교정 — 되풀이하지 마라
| 실수 | 교정 |
|---|---|
| 요약 뒤 레이어 재조립 축을 잃고 부품 세부 시험에 매달림 | §2 여섯 축부터 읽는다 |
| 목표를 "가볍게"로 착각, 직접 짠 Python을 밀고 기준이 이를 자동 채택하게 설계 | 목표는 현업 수준 다듬기. 직접 제작 금지 |
| 시험 안 한 층을 "유지"로 씀, 성능 추정으로 후보 제외 | 미시험은 미시험. 문헌 제외는 ① 관문만 |
| 서둘러 측정 실수 반복(CRLF, ACL 오판으로 측정 중단·재기동, 사전 점검 오판, S13 방법 결함, compose에 제어문자 삽입) | 도구·경로를 먼저 한 번 확인하고 본측정. 셸 인용이 복잡하면 스크립트 파일로. 무효도 기록 |
| 질문에 답보다 작업을 앞세움, HANDOFF·기준을 조각으로 덧대 모순 발생 | 질문엔 먼저 답. 기준은 QUESTIONS §1 한 곳, HANDOFF는 §11 규칙으로 절 단위 교체 |
| 폐기: AI 규칙 엔진(`candidates/ai-ontology/`, 순환 평가), 급진안 C 본안, ML 알람을 규칙 비교에 포함, S13 순차 창 방식 | 되살리지 않는다 |

## 6. 현재 실행 상태 (세션 2 종료 시점)
- **떠 있음:** 격리 V1 SCADA `rot-iiot`(시뮬레이터만 V2 배속 이미지 `rot-plant-simulator:v2-ts`로 교체돼 있음, 감시 서비스 포함 29개) + `rot-ai`(V1 이미지·그래프 snap-A). 이어받는 사람이 바로 층별 벤치를 돌리려면 먼저 내린다: `docker compose --env-file .env --env-file .env.rotation stop` / `docker compose -p rot-ai ... stop`(볼륨 보존). 벤치 가드가 rot-* 실행 중이면 거부한다.
- **배치·측정 프로세스 없음**(모두 정지).
- **그래프 스냅샷:** `rot-ai_graph-snap-A`(원본 V1) · `-snap-B` · `-snap-C` · `-snap-C3`(V2 + 과압). 팔 전환은 `harness/aibench/run_batch.sh` switch_arm.
- **가상설비(#87·#88):** 기본 `simulator/plant.yaml physics_time_scale: 600` — 서서히 진행하는 현상은 설비 시계, 순간 사건만 실제 초. 기동: `docker compose --env-file .env --env-file .env.rotation -f docker-compose.yml -f docker-compose.edgex.yml -f docker-compose.timescale.yml up -d --no-deps plant-simulator`. **원본 이미지 `iiot/plant-simulator:1.0` 은 V1 참고 기록용일 뿐 새 측정에 쓰지 않는다(사용자: 저배속 실행 금지).**
- **재기동 주의:** Docker 재시작 뒤 V1 Flink 잡 0개(V1 약점) → `docker start -a rot-flink-job-submitter`. 호스트 RAM 15.7 GB·Docker VM 7.6 GB, 전체 스택+AI 로 엔진 500 오류 사례(#81). Docker Desktop 경로 `C:\Users\roede\AppData\Local\Programs\DockerDesktop\Docker Desktop.exe`, 분리 실행 bash `D:\dev\Git\bin\bash.exe`, Git Bash 컨테이너 경로 인자 `MSYS_NO_PATHCONV=1`.
- **이미지 디스크:** 벤치용 약 60 GB 추가(C: 여유 약 78 GB).

## 7. 미결정 — 무엇을 보고 정하나
- 이상탐지 버전(1.20 vs 2.2.1)과 HA: Flink HA로 JobManager kill 3시점(`harness/s09*.sh` 방식) 유실 실측 → V1(11~12) 대비.
- 층별 대안: 딥리서치로 넓힌 후보를 축 2 절차로 직접 시험.
- 구조안: 축 1 기준값 + 축 2 승자가 나와야 조립·비교 가능.
- AI: V1 모듈 구조 확인 → 온톨로지·도구 설계 → 정답(주입 고장 사실만) 먼저 고정 → V1 대 V2 시나리오당 3회.
- 외부 대기(사람 답): `QUESTIONS.md` §3(LiteLLM 버전, 원본 Flink 잡, Docker Desktop 유료 조건, 기준선 재동결).

## 8. 절대 규칙
- 원본 `D:\work\study\lecture-iiot-scada` 수정 금지, 원본 컨테이너·볼륨·이미지 삭제·덮어쓰기 금지. push 금지.
- 측정 안 한 수치 금지, 벤더 수치를 실측처럼 쓰지 않음. 기준·정답은 결과 전 고정, 순환 평가 금지.
- 무효·실패도 `reports/decision-log.md`에 추가(추가만). 실행 ID 재사용 금지. 출력 숨기기 금지.
- `latest` 태그·BSL·SSPL·TSL·RCL·체험판·상용 금지. 시뮬레이터 `active_faults`·`thermal_model`을 AI에 넘기지 않음. `ai-layer/.env.local` 커밋·출력 금지.
- 무거운 측정은 한 번에 하나. 쓰지 않는 벤치·스택은 바로 정리(벤치 볼륨만 삭제).

## 9. 다음 행동 — 순서대로 (세션 2 종료 시점)
1. **가상설비 실측:** 격리 스택 위에서 `docker run --rm --network rot-iiot -v <repo>:/repo -w /repo e2e-client:1.0 python harness/e2e/fault_onset.py --reps 3 --out /repo/experiments/EXP-000/raw/onset_v2sim_600.json` → 고장 6종 주입→알람 10 s 이내 확인. 넘는 고장은 plant.yaml 의 그 과정의 현실 설비 시간 정의를 점검(배속 손잡이는 하나만). 오토인코더 오경보 증가 여부도 정상 3분 관찰로 확인 → 늘면 model-trainer 재학습이 V2 과제.
2. **측정 재설계(수 분 안, #88):** `harness/e2e/baseline.sh` 의 60분·5분·10분·E1 300회를 판정에 필요한 최소로(정상 3분, E1 20회×3묶음·조용 구간 3 s, 브로커 정지 10 s·단절 10 s·DB 다운 30 s·과부하 60 s). ROBUSTNESS·STRUCTURE 시간 값 변경은 측정 전에 decision-log 에 기록. 그다음 **V1 기준 전체 측정을 V2 배속 설비로** 다시(비교 대상은 같은 배속 설비).
3. **층별 ② 실행(§2 축 2):** 격리 스택 내리고 `sh harness/run_all_stage2.sh`(층 인자 가능: l4 ingest broker pipe alw backbone ts mon alarm hmi). 결과 `experiments/EXP-*/stage2_*.json`, 요약 `experiments/STAGE2_RUNS.log`. 각 벤치 `STAGE2.md` 에 후보·판정 항목. 결정 #77~#80 적용(Feldera 관문 제외, RisingWave 는 ②에서 판정, 문헌으로 닫지 않음 등). 통과 후보만 ③ 정상 성능·④ 비정상(`stage4*`).
4. **구조 재조립(§2 축 3):** 층 승자 + `CANDIDATES.md` §11 구조 패턴(브로커 Kafka 브리지로 Telegraf#1 제거, HMI 직접 구독, 저장소 3→2, 명령 경로 일원화 등)으로 조립 → 같은 측정.
5. **회전 확정(§2 축 5):** S01~S25 + G0~G10 + E·R → 태그 `v2`. AI 두 입구(알람→사건, 센서 이력) 연결 포함. V2 AI 는 `ai-layer/compose.v2.yml`(`rot-ai-knowledge:v2-ai`).
6. **보고 문서 2개(09-29 사양 그대로, 아래 원문 유지):** REPORT(+HTML) 대조 중심 · 쉬운 설명서 최종판. AI 층 표는 `python harness/tools/report_ai.py` 로 증거에서 생성(`reports/_gen/ai_layer.md`).
   - **문서 1 `reports/REPORT.md`(+HTML) 대표님 보고서 — 짧게, 대조 중심:** ① 한 장 요약(무엇을 바꿨고·얼마나 나아졌고·무엇을 잃었나) ② 변경 전후 아키텍처 그림 두 장을 같은 L1~L9 틀로 나란히(제거 부품은 V1 그림에 흐린 점선, 새 부품은 강조, 알람→화면 경로를 같은 색으로 따라가 경유 단계 수 비교) ③ 층별 대조표(원래 → 바뀐 것 → 왜 → 실측, 유지한 층도 이유) ④ 엑셀형 점수표(`harness/tools/scorecard.py`, 미측정 표시, 증거 파일에서 재계산)는 부록.
   - **문서 2 쉬운 시스템 설명서(최종 버전):** `docs/소스코드로_확인한_아주쉬운_시스템설명.html`(V1판, 보존)과 같은 순서(① 설비 → ② 전체 아키텍처 한 장 → ③ "교반기의 떨림 하나가 화면의 경고가 되기까지")와 문체로 새 파일. 바뀐 단계마다 "V1에서는 → 이제는" 상자, L1~L9 가로 레이어, 색 규칙(파랑 데이터·보라 AI·주황 명령), 화살표 교차 없이, 모든 화살표를 실제 코드·설정과 대조.
7. `D:/work/작업보고/2026-09-29.md` 갱신(STUDY 규칙) — 세션 2 에서 아직 안 함.

## 10. 자산 지도
| 위치 | 역할 | 언제 |
|---|---|---|
| `D:\work\study\scada-rotation`(브랜치 `exp/stack-rotation-202609`, 기준 태그 `v1-original`) | 작업 폴더 | 항상 |
| `QUESTIONS.md` §1 | 판정 기준 유일 정본 | 판정 전 |
| `reports/decision-log.md` | 모든 실행·판정 기록(#1~#66, 추가만) | 실행 후 |
| `harness/situations/` STRUCTURE·ROBUSTNESS·CANDIDATES·L4·BROKER | 결과 전 고정한 시험 목록 | 시험 설계·판정 |
| `harness/e2e/`, `l4bench/`, `brokerbench/`, `tools/`, `s09*.sh`, `run_l4_multi.sh`, `l4_10.sh` | 측정 도구(솔루션 부품 아님) | 측정 |
| `candidates/` | 후보 구현(`ai-ontology` 폐기, `l4-python` 탈락 기록용, `l4-flink22-onnx`·`l4-flink-cep`는 jar 빌드 필요 시 `maven:3.9-eclipse-temurin-17`) | 참고·벤치 |
| `experiments/EXP-000`(V1 기준) · `EXP-L4` · `EXP-S09` · `EXP-130` | 증거 원본 | 수치 재계산 |
| `docs/research/` | 원문 8종 | 근거 확인 |
| `scenarios/catalog.yaml` | S01~S25 | 회귀 |
| 원본 `D:\work\study\lecture-iiot-scada` / `_references/` | 읽기만 / 열지 마라 | — |

## 11. 갱신 규칙
- 측정·조사 완료 → §4와 §2 상태 칸. 방향 결정 → §2(+이유), 기준 변경은 `QUESTIONS.md` §1에서만. 틀린 것 → §5. 실행 상태 변화 → §6. 순서 변화 → §9.
- §1·§8 변경은 전제가 흔들린 것이므로 사용자에게 먼저 보고. 조각 덧댐 금지 — 모순이 생기면 해당 절을 통째로 교체.
