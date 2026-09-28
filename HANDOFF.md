# HANDOFF — V1 IoT·SCADA·AI 프로토타입 회전 탐색 (scada-rotation)

최종 갱신 2026-09-28 22:40 KST · 작성 Claude Code(이 세션)
**이 파일은 재개용 기록이다. 현재 사용자 지시·실제 파일·실행 상태와 대조한다. 다르면 실제가 우선이고 이 파일을 고친다.**

## 0. 30초 브리핑
대표님께 "성능이 가장 좋은 구조"를 실측으로 보고하기 위해, V1 프로토타입을 모듈별 대안으로 바꿔 보며 V1→V2(→V3)를 확정하는 작업이다.
원본 V1은 동결·정지, 실험은 별도 worktree. L4(이상탐지)는 Flink 1.20.1 SQL / Flink 2.2.1 SQL / Python 을 정상·재시작 조건에서 측정했고, 판정은 보류다.
브로커·DataStream CEP·AI 온톨로지는 코드만 있고 미실행. 방금 사용자가 판정 기준을 "동등성 관문 + 간소화 이득 대 성능 하락 비교"로 바꿨다(§2).
직전에 만든 AI 규칙 엔진은 "고도화 구성을 간소 파이썬으로 대체 + 순환 평가"라 폐기 대상이다(§5).

## 1. 배경
- 의뢰: 대표님. "사전 스펙으로 평가하지 말고 빠르게 구현해 모듈별로 실측·비교, 최신 트렌드, 기술선정·온톨로지·시나리오가 개선된 궤적을 가져와라." 이번 주(5영업일).
- 기준 문서: **AGENT_BRIEF_FINAL**(OSI·비용 0원·G0~G9 Gate·S01~S25·CQ15) + **ARCHITECTURE_SIMPLIFICATION 검토서**(V1 경로 미로·중복, 대안 A~D, 추천 C=MQTT 단일 백본). 두 원문은 채팅으로만 받았고 **디스크에 없다**(§7).
- 목적: 완성된 프로토타입을 실제로 만들고 성능을 확인하는 것. **실라버스·강의는 이 작업에서 다루지 않는다**(다른 곳에서 한다). 시킨 것만 한다.

## 2. 확정된 방향 — 바꾸지 마라
- **가치 중심 구성**, 기술은 교체 수단 — 기술은 해마다 바뀌어 재사용이 안 되므로.
- **AI: 그래프 DB 필수 · 원인 분석은 온톨로지 그래프 추론 · 조치 매뉴얼은 임베딩+그래프로 에이전트가 의미 검색·해석 · 새 설비·고장은 코드 없이 온톨로지·매뉴얼 추가로 확장** — 대표님 방향. 재귀 CTE·임베딩만·LLM 단독은 후보로 올리지 않는다(정확도를 떨어뜨리는 쪽).
- **AI는 V1 에이전트(LLM+LangGraph+가드레일)를 유지하고 온톨로지를 도구로 더한다** — 고도화 구성을 규칙 파이썬으로 대체하면 안 되므로.
- **판정 규칙(QUESTIONS.md Q2·Q2-0·Q2-a에 기록, 최신 사용자 지시 반영):**
  1. 관문: G10 Docker 가상화(불가면 폐기) · G9 OSI·비용 0원 · 안전 G0~G8.
  2. **동등성 관문:** 원래 구성이 처리하던 상황을 전부 처리해야 한다. 판정은 결과 기준(방식·형태가 달라도 같은 상황을 처리하면 통과), 프로토타입 목적 밖 상황은 범위 밖으로 표시.
  3. **간소화 대안의 성능(처리 능력·결과·안정성)은 더 좋거나 같거나 아주 약간 하락까지 허용.** 판정은 "간소화 이득(자원·복잡도 감소) 대 성능 하락"의 크기 비교: 이득이 엄청 크면 채택, 미묘하면 거르고 원래 유지. 이득이 미묘해도 최신 스택이면 고려.
  4. 보고서는 엑셀처럼: 후보×지표(정확도·지연·복구·CPU·메모리·이미지·컨테이너·줄 수) 실측값+5점 점수+약점(어디가 얼마나 나쁜지)+판정 열.
- 원본 V1은 `v1-original` 태그로 동결, 실험은 worktree에서 — 원본 폴더의 미커밋 작업 76건을 섞지 않기 위해.

## 3. 절대 규칙
- 원본 `D:\work\study\lecture-iiot-scada` 파일 수정 금지(미커밋 변경 76건 그대로). push 금지.
- 측정하지 않은 수치를 쓰지 않는다(`NOT MEASURED`/미측정). 벤더 수치를 실측처럼 쓰지 않는다.
- 판정 기준·정답은 결과 보기 전 고정, 이후 변경 금지. 정답과 판정 조건을 같은 사람이 맞춰 쓰는 순환 평가 금지.
- 무효·실패 실행도 지우지 않고 `reports/decision-log.md`에 원인과 함께 추가(추가만).
- 실행 ID 재사용 금지, 출력 숨기지 않기(`>/dev/null` 금지), `latest` 태그 금지, BSL·TSL·RCL·체험판·상용 금지.
- 측정은 한 번에 하나, 무거운 작업(빌드·이미지 풀)과 겹치지 않게.

## 4. 확정 사실 — 다시 조사하지 마라
- V1 실구성: Flink **1.20.1**, Kafka **3.9.0(이미 KRaft)**, EMQX **5.8.6(2026-02-28 EOL → 교체 필수)**, InfluxDB 2.7, FUXA 1.3.4. 상세·차이 → `harness/V1_FACTS.md`, 이미지·포트 → `harness/V1_INVENTORY.md`, 메시지 형식 → `harness/SCHEMA.md`.
- I2~I4: CEP 창 10초, IT-102>9.6A, VT-101>7.1mm/s, 워터마크 5초(`flink/sql/01·04`).
- 11:52 원본 V1 Flink 잡 소멸 원인 = Docker Desktop 자체 재시작(프로세스 시작 11:51:56). HA 없는 세션 클러스터라 JobManager 재시작 시 잡이 사라지고 latest-offset이라 공백 구간 유실.
- 환경: Windows 11 Home, Docker Desktop 4.87.0, WSL2, Docker 메모리 7.6GB. 원본 V1 29개가 약 4.9GB 사용 → 동시 실행 시 호스트 RAM 고갈로 엔진 500 오류 발생(09-28). **현재 원본 V1은 정지(볼륨 보존)**.
- G10: FINAL 후보 29개 전부 컨테이너 가능(Mosquitto 2.1.x는 `-alpine` 태그만) → `harness/G10_CONTAINER.md`.
- L4 정상 조건(케이스당 10회·간격 무작위·시드 1001/2002, 원본 정지 상태): 3후보 모두 70/70, 알람 집합 V1과 차이 0. CEP p95 Python ≈5.91s, Flink1.20 ≈6.1s, Flink2.2 ≈6.05~6.14s. 메모리 평균 Python 21~22MiB, Flink1.20 1,193~1,237MiB, Flink2.2 1,264~1,289MiB → `experiments/EXP-L4/raw/summary_m1·m2.json`.
- L4 재시작(유실·중복, 대조군 대비): Python kill 3회 모두 0/0. Flink1.20 TaskManager kill 3회 중 1회 중복3. Flink2.2 TaskManager kill 3회 중 2회 중복3. JobManager kill(1.20 2회 유실12·12, 2.2 2회 유실12·11) 모두 잡 소멸로 대량 유실 → `experiments/EXP-S09/raw/g8_*.json`, 행렬 로그 `matrix_y.log`.
- V1 AI 현황(코드 직접 확인): 그래프는 Asset-HAS_SENSOR-Sensor, Asset-HAS_PROCEDURE/GOVERNED_BY/DESCRIBED_BY-Document만. 증상·고장모드·원인 노드 없음. 원인 판단은 LLM(도구 3개: alarm·documents·observations, `operations/agent.py`), 문서는 전체를 관계로 가져옴(절·임베딩 검색 없음, `embedding.py`는 미사용), 조치 규칙이 프롬프트·코드에 하드코딩 → 새 고장 추가에 코드 수정 필요.

## 5. 폐기된 판단 — 되살리지 마라
- **AI 규칙 엔진(`candidates/ai-ontology/`, YAML 조건 + 파이썬 판정):** LLM 에이전트를 규칙으로 대체했고, 정답(`ontology/v2/answer-key.yaml`)과 판정 조건을 같은 사람이 시뮬레이터 코드를 보고 써서 순환 평가다. 통과해도 증명 없음. 에이전트 도구로 다시 설계한다. 정답 파일은 순환 문제 때문에 새 설계에서 재작성 필요(주입 고장 사실만 기준).
- **"Python L4가 더 낫다"는 결론:** 좁은 조건(12태그·합성·짧은 실행) 결과일 뿐. 규칙 변경 방식·Prometheus 지표·ONNX 잡·대량 부하·장시간·부하 중 재시작이 미검증이라 동등성 관문 미통과.
- 원본 V1 옆에 전체 스택을 하나 더 띄우는 방식: 메모리 부족. 모듈 벤치로 대체.
- "11:52 재시작은 수동": 틀림(§4).
- FINAL §10의 "지연 20%·메모리 30% 악화 허용": 폐기(§2 규칙으로 대체).

## 6. 미결정 — 무엇을 보고 정하나
- L4 채택: `harness/situations/L4.md`(아직 없음)에 V1 Flink가 처리하는 상황 목록(규칙 변경·지표 노출·ONNX·부하·장시간·부하 중 재시작·파티션 간 순서)을 고정하고 후보가 전부 처리하는지 + DataStream CEP(EXP-111) 측정 후 §2-3 규칙으로 정한다.
- 브로커: EMQX 대체 후보(Mosquitto 2.1.2-alpine·NanoMQ 0.25.6·HiveMQ CE 2026.5)를 `harness/brokerbench/run.sh`로 측정 후. 먼저 V1 EMQX가 쓰는 기능(WebSocket 8083, 오프라인 세션 2h·큐 10만, Prometheus 지표, retained) 상황 목록 고정.
- AI V2 설계: V1 `investigate()`에 도구 추가(그래프 원인 탐색·매뉴얼 절 의미 검색) — V1 대 V2 에이전트를 같은 사건에 여러 회 비교. 정답은 주입 고장만.

## 7. 외부 대기 — 사용자에게 물을 것
- "아주 약간 하락"·"엄청 큰 이득"의 수치 경계(제안: 지연·처리량 5% 이내, 유실 0 유지 / 자원 10배 이상 절감) — 미확정.
- AI 비교용 LLM 호출 허용 횟수(비용은 회사 부담이나 크레딧 절약 지시 있음).
- AGENT_BRIEF_FINAL·ARCHITECTURE_SIMPLIFICATION 원문 파일(→ `docs/research/`에 두기).
- LiteLLM Cloud Run 프록시 버전(1.82.7/1.82.8 여부), Docker Desktop 유료 조건(회사 규모) — `QUESTIONS.md` Q4·Q6.

## 8. 자산 지도
| 위치 | 역할 | 언제 여나 |
|---|---|---|
| `D:\work\study\scada-rotation` (브랜치 `exp/stack-rotation-202609`) | 작업 폴더 | 항상 |
| `QUESTIONS.md` Q2·Q2-0·Q2-a | 판정 규칙 정본 | 판정 전 |
| `reports/decision-log.md` | 모든 실행·판정 기록(추가만, #1~#26 + y행렬 미기록) | 실행 후 추가 |
| `reports/REPORT.md` | 보고서 틀 | 마지막 |
| `harness/l4bench/`, `harness/tools/{replay,evaluate,scorecard}.py`, `harness/run_l4_multi.sh`, `s09*.sh` | L4 벤치·측정·점수표 | L4 작업 |
| `harness/brokerbench/` | 브로커 벤치(미실행) | 브로커 작업 |
| `candidates/l4-python/`, `l4-flink22/`, `l4-flink-cep/`(jar 미빌드) | L4 후보 | L4 작업 |
| `candidates/ai-ontology/`, `harness/aibench/`, `ontology/v2/` | **폐기된 규칙 엔진(§5)** — 참고만, 그대로 쓰지 마라 | 재설계 시 참고 |
| `scenarios/catalog.yaml` | S01~S25 | 시나리오 |
| 원본 `D:\work\study\lecture-iiot-scada` | V1 원본(정지) | 읽기만. 수정·재기동 전 사용자 확인 |
| `_references/`(원본 폴더, 868MB) | 무관 참고자료 | 열지 마라 |

## 9. 다음 행동
1. (y 행렬 10회 완료, 수치는 §4) decision-log에 y1~y10 행 추가 + 이 세션의 미커밋 변경을 커밋(`git add -A HANDOFF.md QUESTIONS.md candidates harness ontology experiments reports`). 완료 판정: decision-log에 #27 이후 y 행렬 행, `git status` 깨끗.
2. §7 수치 경계를 사용자에게 받는다(막히면 3·4를 먼저).
3. `harness/situations/L4.md` 작성(V1 Flink 상황 목록, 결과 보기 전 커밋) → 후보별 처리 여부 시험 설계. 완료 판정: 목록의 각 상황에 후보별 통과/실패/미검증 칸이 있음.
4. EXP-111 빌드(`docker run maven:3.9-eclipse-temurin-17 ... mvn package` in `candidates/l4-flink-cep`) → `flinkcep` 프로파일 기동 → `CANDIDATES="flinksql flink22 cep python" harness/run_l4_multi.sh EXP-L4 m3|m4 --repeat 10 --jitter --seed 3003|4004`. 완료 판정: summary_m3·m4에 4후보.
5. 브로커 상황 목록 → `harness/brokerbench/run.sh b` 측정.
6. AI V2를 §2 방향으로 재설계(V1 에이전트 + 온톨로지 도구) — 설계안 먼저 사용자 확인.
7. `harness/tools/scorecard.py`로 점수표(md·xlsx) → `reports/REPORT.md`.

## 10. 갱신 규칙
- 측정·조사 완료 → §4로 승격, §6에서 삭제. 방향 결정 → §2(+이유). 틀린 것으로 밝혀짐 → §5. 사용자 답 → §7에서 §2·§4로.
- §1·§3 변경은 전제가 흔들린 것이므로 사용자에게 먼저 보고.
