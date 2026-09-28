# HANDOFF — V1 IoT·SCADA·AI 프로토타입 회전 탐색 (scada-rotation)

최종 갱신 2026-09-28 23:55 KST · 작성 Claude Code(이 세션)
**이 파일은 재개용 기록이다. 현재 사용자 지시·실제 파일·실행 상태와 대조한다. 다르면 실제가 우선이고 이 파일을 고친다.**

## 0. 30초 브리핑
대표님께 "성능이 가장 좋은 구조"를 실측으로 보고하기 위해 V1 프로토타입을 모듈별 대안으로 바꿔 보며 V1→V2(→V3)를 확정하는 작업이다.
L4(이상탐지) 4후보(Flink 1.20 SQL=V1 / Flink 2.2.1 SQL / 2.2.1 DataStream CEP / Python)는 규칙 정확도 동일·재시작 일부 측정까지 끝났고, 동등성 관문의 ONNX·지표 항목을 채우려고 후보를 보강(코드 완료, 벤치 미실행)한 상태다.
브로커 4종은 1차(b) 완료, 반복(c)·BR-03(d) 실행 중. AI는 V1 에이전트 + 온톨로지 도구로 재설계 착수 전(V1 모듈 조사 중).
판정은 사용자에게 묻지 않고 사전 확정 규칙(QUESTIONS Q2·Q2-0·Q2-1·Q2-a)으로 스스로 내리고 decision-log에 남긴다.

## 1. 배경
- 의뢰: 대표님. "사전 스펙으로 평가하지 말고 빠르게 구현해 모듈별로 실측·비교, 최신 트렌드, 기술선정·온톨로지·시나리오가 개선된 궤적을 가져와라." 이번 주(5영업일).
- 기준 문서: **AGENT_BRIEF_FINAL**(OSI·비용 0원·G0~G9 Gate·S01~S25·CQ15) + **ARCHITECTURE_SIMPLIFICATION 검토서**. 두 원문은 채팅으로만 받았고 **디스크에 없다**(§7).
- 목적: 완성된 프로토타입을 만들고 성능을 확인하는 것. **실라버스·강의는 이 작업에서 다루지 않는다.** 시킨 것만 한다.
- 사용자 /goal DoD(요약): ① L4 4후보 정상 10회·지터·시드 2개 이상, 정확도·V1 대비 알람 차이·CEP p95·메모리/CPU, TM·JM·Python kill 3시점 유실/중복 ② 규칙으로 L4 판정 ③ 브로커 EMQX vs Mosquitto 2.1.2·NanoMQ 0.25.6·HiveMQ CE 2026.5: QoS1 유실·중복·p95, 재시작 유실·중복·최대공백, 재시작 후 오프라인 600건·retained, WS 20/20, 메모리·이미지·설정 줄 수 → 최선이 EMQX 대체 ④ AI: 그래프 DB 온톨로지(증상→고장모드→원인→점검/절차), CQ15 V1 대비, 시나리오 2개(베어링·히터 고착)를 사전 고정 정답으로 채점, 새 고장을 코드 0줄로 처리 ⑤ V2 회귀 S01–S25·G0–G10 → 태그 `v2` ⑥ 모든 실행 decision-log, 보고 수치는 증거 파일에서 재계산 ⑦ REPORT.md(V1 대 후보 간결 표), 원본 V1 폴더 무수정.

## 2. 확정된 방향 — 바꾸지 마라
- **가치 중심 구성**, 기술은 교체 수단 — 기술은 해마다 바뀌어 재사용이 안 되므로.
- **AI: 그래프 DB 필수 · 원인 분석은 온톨로지 그래프 추론 · 조치 매뉴얼은 임베딩+그래프로 에이전트가 의미 검색·해석 · 새 설비·고장은 코드 없이 온톨로지·매뉴얼 추가로 확장** — 대표님 방향. 재귀 CTE·임베딩만·LLM 단독은 후보로 올리지 않는다.
- **AI는 V1 에이전트(LLM+LangGraph+가드레일)를 유지하고 온톨로지를 도구로 더한다** — 고도화 구성을 규칙 파이썬으로 대체하면 안 되므로.
- **판정 규칙(정본 QUESTIONS.md):** 관문 G10 Docker 가상화(불가면 폐기)·G9 OSI·비용 0원·G0~G8 → Q2-0 동등성 관문(원래 처리하던 상황 전부, 결과 기준, 상황 목록 `harness/situations/*.md` 결과 전 고정) → Q2-1 수치 경계(약간 하락 = 정확도 하락 0·p95 +5% 이내·재시작 유실 증가 0·중복 ≤ 기준 / 엄청난 이득 = 메모리 또는 CPU 5배 이상 절감 또는 컨테이너 절반 이하) → 성능↑인데 다른 지표↓면 보류 → Q2-a 점수표(최고 5점, 낮을수록 좋은 지표는 5×최고/값, 최저 1, 정확도·복구가 기준보다 나쁘면 0, 약점 열·판정 열).
- **사용자는 결정을 위임했다("스스로 모든 권한을 쥐고")** — 묻지 말고 규칙으로 판정·기록. 설계안 사전 확인 불필요.
- **리소스는 쓰지 않으면 바로 정리한다** — 벤치 끝나면 해당 compose down(-v는 벤치 볼륨만).
- 원본 V1은 `v1-original` 태그로 동결, 실험은 이 폴더(worktree)에서.

## 3. 절대 규칙
- 원본 `D:\work\study\lecture-iiot-scada` 파일 수정 금지, 원본 V1 컨테이너·볼륨·이미지 삭제 금지(읽기 전용 마운트 복사는 허용). push 금지.
- 측정하지 않은 수치를 쓰지 않는다. 벤더 수치를 실측처럼 쓰지 않는다.
- 판정 기준·정답은 결과 보기 전 고정, 이후 변경 금지. 순환 평가 금지.
- 무효·실패 실행도 지우지 않고 `reports/decision-log.md`에 추가(추가만). 실행 ID 재사용 금지. 출력 숨기기 금지.
- `latest` 태그 금지, BSL·TSL·RCL·체험판·상용 금지. 비용은 LLM API만 예외(크레딧 절약).
- 시뮬레이터 `active_faults`·`thermal_model`(고장 정답)을 AI 엔진에 넘기지 않는다.
- `ai-layer/.env.local`(LiteLLM 키) 커밋·출력 금지.
- 측정은 한 번에 하나(무거운 벤치 동시 실행 시 호스트 RAM 고갈 → 결과 오염).

## 4. 확정 사실 — 다시 조사하지 마라
- V1 실구성: Flink 1.20.1, Kafka 3.9.0(KRaft), EMQX 5.8.6(2026-02-28 EOL → 교체 필수), InfluxDB 2.7, FUXA 1.3.4 → `harness/V1_FACTS.md`, `V1_INVENTORY.md`, `SCHEMA.md`.
- 11:52 원본 Flink 잡 소멸 = Docker Desktop 재시작. HA 없는 세션 클러스터 + latest-offset이라 JobManager 재시작 시 잡 소멸·공백 유실.
- 환경: Docker VM 7.6GB. 원본 V1 정지(볼륨 보존). 원본 폴더는 다른 작업이 수정 중 → DoD7은 "이 세션이 원본 무수정"으로 판정.
- G10: 후보 29개 전부 컨테이너 가능 → `harness/G10_CONTAINER.md`.
- **L4 규칙 정확도(m1·m2·m4·m5, 케이스당 10회·지터·시드 1001/2002/4004/5005):** 전 후보 70/70, 알람 집합 V1과 차이 0. p95(s) Python 5.8~5.95 / 2.2 SQL 6.0~6.5 / DS CEP 6.1~6.5 / 1.20 SQL 6.0~8.17(m4). 메모리 Python 16~22MiB, Flink 3종 약 1.2~1.29GiB. CPU는 실행 간 편차 큼(Kafka 유휴 CPU 178% 원인 미확인) → `experiments/EXP-L4/raw/summary_m*.json`, decision-log #39·40. m3는 무효(#38).
- **L4 재시작:** Python kill 3회 0/0. Flink 1.20 TM kill 3회 중 1회 중복 3, 2.2 TM 3회 중 2회 중복 3. JM kill은 1.20·2.2 모두 잡 소멸 유실 11~12. DS CEP 후보는 **미측정** → `experiments/EXP-S09/raw/g8_*.json`.
- **V1 ONNX 잡 구조**(`flink/onnx-job`): raw → keyBy(**tag**, 장치 구분 없음) Interpolator(선형, 최대 공백 20초, 스캔 1초, (tag,ts) 중복 제거) → clean 토픽 → keyBy(device) OnnxScorer(처리시각 1초 타이머, 10스텝×12태그, meta 정규화, MSE>임계 0.03508이면 ML_AUTOENCODER 알람). 모델은 원본 볼륨 `iiot_model-store` 사본 `harness/l4bench/models/`(sha256 f679705c…). keyBy(tag)는 다중 장치에서 섞이는 V1 잠재 결함(후보도 V1과 같게 이식, 보고서에 기록).
- Flink 2.2.1 이미지에는 metrics-prometheus 플러그인이 내장(`/opt/flink/plugins`) → V1 config의 reporter 설정으로 충족 예상(벤치 미확인).
- Python ONNX 이식 오프라인 사전 점검: 창 100개 V1 수식 참조 대비 최대 차 8.5e-14(판정은 벤치 S13에서).
- **브로커 b(1회):** 정상 p95(ms) EMQX 2.6 / Mosquitto 1.66 / NanoMQ 2.01 / HiveMQ 47.4, 유실·중복 0 전원. 재시작 유실/중복/최대공백: 4/0/11.1s · 0/1/1.0s · 4/0/1.0s · 527/5/13.3s. 재시작 넘어 오프라인 600건·retained: 0✗ / 600✓ / 0✗(기본 설정, 영속 없음) / 600✓. WS 20/20 전원 → decision-log #41.
- V1 AI: 그래프는 Asset-HAS_SENSOR-Sensor, Asset-HAS_PROCEDURE/GOVERNED_BY/DESCRIBED_BY-Document만. 원인 판단은 LLM(도구 3개), 조치 규칙 하드코딩. 단 `ai-layer/knowledge/backend/src/modules/ontology/`(build·tools·embedding 등 약 2,200줄)와 `ontology_mcp/`가 존재 — 운영 에이전트와의 연결 여부는 **조사 중**(§6).

## 5. 폐기된 판단 — 되살리지 마라
- **AI 규칙 엔진(`candidates/ai-ontology/`)**: LLM 에이전트를 규칙으로 대체 + 순환 평가. 정답 파일 `ontology/v2/answer-key.yaml`은 주입 고장 사실만으로 재작성해야 한다.
- **"Python L4가 더 낫다"는 결론**: 동등성 관문(ONNX·지표·부하·장시간) 미통과 상태의 좁은 결과.
- 원본 V1 옆에 전체 스택을 하나 더 띄우기: 메모리 부족 → 모듈 벤치.
- "11:52 재시작은 수동": 틀림. FINAL §10 "지연 20%·메모리 30% 악화 허용": 폐기(Q2-1로 대체).
- ML 알람을 규칙 알람 집합 비교에 포함: 처리시각 타이머라 실행마다 시각이 달라 비교 불가 → 규칙 비교에서 제외, S13에서 따로 판정(#43).

## 6. 미결정 — 무엇을 보고 정하나
- **L4 판정:** 보강한 벤치로 S13(ONNX 점수 동일성 1e-6·알람 동일, `harness/tools/s13.py`)·L4-12b(보간 clean 동일)·L4-11(:9249 스크레이프)·L4-10(규칙 변경 무코드)·L4-14 고부하·L4-15 30분 이상 + DS CEP S09 → Q2 규칙.
- **브로커 판정:** c(반복, NanoMQ 영속 설정)·d(BR-03)·BR-07(`harness/brokerbench/br07.py`)·이미지 크기·설정 줄 수 → Q2 규칙. HiveMQ CE는 $SYS·Prometheus가 확장(Apache-2.0) 필요할 수 있음 → 측정 후 필요하면 확장 설치해 재측정.
- **AI V2:** V1 ontology 모듈 조사 결과를 보고 "V1 에이전트 + 그래프 원인 탐색 도구 + 매뉴얼 절 의미 검색(임베딩+그래프)" 설계. 임베딩은 로컬 Ollama bge-m3(MIT) 계획이나 이미지 풀을 사용자가 한 번 거절함 → 필요 시 사유와 함께 재시도 또는 대안. 정답은 주입 고장 사실만. V1 대 V2 시나리오당 3회.

## 7. 외부 대기 — 사용자에게 물을 것
- AGENT_BRIEF_FINAL·ARCHITECTURE_SIMPLIFICATION 원문 파일(→ `docs/research/`에 두기).
- V1 기준선을 최신 원본으로 다시 뜰지(원본이 다른 작업으로 계속 바뀜).
- LiteLLM Cloud Run 프록시 버전, Docker Desktop 유료 조건 — `QUESTIONS.md` Q4·Q6.

## 8. 자산 지도
| 위치 | 역할 | 언제 여나 |
|---|---|---|
| `D:\work\study\scada-rotation` (브랜치 `exp/stack-rotation-202609`) | 작업 폴더 | 항상 |
| `QUESTIONS.md` Q2·Q2-0·Q2-1·Q2-a | 판정 규칙 정본 | 판정 전 |
| `reports/decision-log.md` | 모든 실행·판정 기록(추가만, #1~#43) | 실행 후 추가 |
| `reports/REPORT.md` | 보고서 틀 | 마지막 |
| `harness/situations/L4.md`, `BROKER.md` | 동등성 상황 목록(결과 전 고정) | 판정 시 |
| `harness/l4bench/`(compose·prepare.py·models), `harness/tools/{replay,evaluate,scorecard,s13}.py`, `run_l4_multi.sh`, `s09*.sh` | L4 벤치 | L4 작업 |
| `harness/brokerbench/`(run.sh·run_br03.sh·br07.py·nanomq.conf) | 브로커 벤치 | 브로커 작업 |
| `candidates/l4-python/`(app.py+ml.py), `l4-flink22/`, `l4-flink-cep/`, `l4-flink22-onnx/` | L4 후보(jar는 target/, git 제외) | L4 작업 |
| `experiments/EXP-L4`, `EXP-S09`, `EXP-130` | 증거 원본 | 수치 재계산 |
| `candidates/ai-ontology/`, `harness/aibench/`, `ontology/v2/` | **폐기된 규칙 엔진(§5)** — 참고만 | 재설계 시 참고 |
| `scenarios/catalog.yaml` | S01~S25 | 시나리오 |
| 원본 `D:\work\study\lecture-iiot-scada` | V1 원본(정지) | 읽기만 |
| `_references/`(원본 폴더) | 무관 참고자료 | 열지 마라 |

## 9. 다음 행동
1. 브로커 c·d 완료 확인(`experiments/EXP-130-run_c.log`, `run_d.log`) → br07.py 실행(`docker compose -f harness/brokerbench/compose.yml --profile tools run --rm client python /repo/harness/brokerbench/br07.py --exp EXP-130 --run e`) → 이미지 크기·설정 줄 수 → decision-log → 판정 → brokerbench down. 완료 판정: BROKER.md BR-01~07 각각 후보별 통과/실패 칸.
2. L4 벤치 기동(prepare.py → up flinksql·flink22·flinkcep·python → submit 3종, 잡 4개 RUNNING) → s13.py → :9249 스크레이프 → m6(규칙 회귀, ONNX 동시 가동) → 고부하·30분 → DS CEP S09 3시점. 완료 판정: L4.md 16행 전부 후보별 칸.
3. AI V2 설계·구현·V1 대비 측정(§6).
4. V2 조립·S01–S25·G0–G10 회귀 → 태그 `v2`.
5. scorecard.py → `reports/REPORT.md`, 수치는 증거 파일에서 재계산.

## 10. 갱신 규칙
- 측정·조사 완료 → §4로 승격, §6에서 삭제. 방향 결정 → §2(+이유). 틀린 것으로 밝혀짐 → §5. 사용자 답 → §7에서 §2·§4로.
- §1·§3 변경은 전제가 흔들린 것이므로 사용자에게 먼저 보고.
