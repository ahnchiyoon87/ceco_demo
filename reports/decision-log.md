# 결정 기록부 (Decision Log)

**추가만 하고 지우거나 고치지 않는다.** 정정은 새 항목으로 남긴다.
판정 값: **채택 / 보류 / 탈락 / 무효 / 기록**(판정 없이 사실만)
판정 규칙: `QUESTIONS.md` Q2 (관문 → 성능 악화 0 → 최고 성능 → 자원·단순성은 동점 시. 성능↑·다른 지표↓ = 보류)
수행자: 에이전트 = Claude Code(이 세션). 결정자: 규칙(사전 확정 기준 자동 적용) 또는 사용자.

| # | 시각(KST) | 실험 · 실행 | 대상 | 수행자 | 무엇을 · 어떻게 | 결과 | 판정 | 사유 | 결정자 | 근거 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | 09-28 | Day 0 | V1 원본 | 에이전트 | 실행 중인 원본 작업 트리를 `v1-original` 태그로 동결 | 원본 무변경 | 기록 | — | 사용자(브랜치·별도 폴더 지시) | `harness/V1_INVENTORY.md` |
| 2 | 09-28 | Day 0 | V1 사실 대조 | 에이전트 | 코드 읽기로 I2~I4 확정, 브리프와 다른 점 기록 | N=10s, IT>9.6A, VT>7.1, WM 5s | 기록 | — | — | `harness/V1_FACTS.md` |
| 3 | 09-28 | Day 0 | EMQX 5.8.6 | 에이전트 | 문헌(FINAL §11.3) | 5.8.x 2026-02-28 EOL | **탈락(교체 필수)** | 보안 패치 종료 버전 고정 금지(G9) | 규칙 | `harness/V1_FACTS.md` §2 |
| 4 | 09-28 | Day 0 | V1 원본 Flink | 에이전트 | 원본 Kafka 오프셋·Flink REST 관찰 | 11:52 재시작 후 잡 0개, 탐지 중단 | 기록(V1 약점) | HA 없는 세션 클러스터 + 1회성 제출기 + latest-offset | — | `harness/V1_FACTS.md` §5 |
| 5 | 09-28 | G10 | FINAL 후보 29종 | 에이전트 | 레지스트리 manifest 조회(amd64) | 29/29 이미지 존재 | 기록(전원 통과) | Mosquitto 2.1.x 는 `-alpine` 태그만 존재 | 규칙 | `harness/G10_CONTAINER.md` |
| 6 | 09-28 | EXP-112a · r1 | V1 Flink 1.20.1 SQL | 에이전트 | L4 벤치 리플레이 | CEP 0건 | **무효** | 벤치 설정 오류(TaskManager 슬롯 4, 필요 6) — V1 결함 아님 | 규칙 | `experiments/EXP-112a/raw/INVALID_r1.md` |
| 7 | 09-28 | EXP-112a · r2 | V1 Flink 1.20.1 SQL | 에이전트 | 슬롯 8(V1 동일), 사전 점검 후 리플레이 | 21/21, CEP p95 5.70s, S07 늦은 이벤트 무기록 폐기 | 기록(기준선) | — | — | `experiments/EXP-112a/log.md` |
| 8 | 09-28 | EXP-113 · r3 | Python 서비스(1차) | 에이전트 | 같은 리플레이를 Flink와 동시 소비 | 21/21이나 S07 장치 THRESHOLD 3건 누락 | **무효(후보 결함)** | 늦은 레코드를 임계치에서도 폐기 → V1 기능(CAP-06) 손실. 후보 코드만 수정 | 규칙 | `experiments/EXP-113/raw/NOTE_r3.md` |
| 9 | 09-28 | EXP-113 · r4 | Python 서비스(1차 수정) | 에이전트 | 동시 소비 리플레이 | 21/21, 알람 81=81(차이 0), p95 5.51s vs 5.65s, 메모리 12 vs 1,131 MiB, CPU 0.4 vs 17% | 기록(재시작 미측정) | 재시작(G8) 시험 전이라 판정 불가 | — | `experiments/EXP-113/log.md` |
| 10 | 09-28 | EXP-S09 · r5 | Python 서비스(1차) | 에이전트 | 처리기 kill/start | Python 0/3, Flink(대조) 3/3 | **무효(시험 조건)** + 후보 결함 발견 | 조율 스크립트 cp949 오류로 kill 시점이 패턴 20초 전. 부수 발견: 몰아받기 중 워터마크가 미수신 파티션을 빼고 계산해 과전류 117건 late 폐기 | 규칙 | `experiments/EXP-S09/raw/INVALID_r5.md` |
| 11 | 09-28 | EXP-113b | Python 서비스(2차) | 에이전트 | 후보 재작성: 파티션 직접 할당, Flink식 유휴 규칙, 1초 스냅샷(오프셋+상태) 복구 | — | 기록 | 결함 2건(r3·r5) 수정 | — | `candidates/l4-python/app.py` |
| 12 | 09-28 | EXP-113b · r8 | Python(2차) · Flink | 에이전트 | 동시 소비 리플레이 | 9/21, 알람 162(2배), 지연 음수 | **무효(하니스 결함)** | 실행 ID 충돌: 무응답으로 끝난 줄 안 이전 명령이 실제 실행됨. 하니스 수정(ID 재사용 거부·토큰·시각 필터), 판정 기준 무변경 | 규칙 | `experiments/EXP-113b/raw/INVALID_r8.md` |
| 13 | 09-28 | EXP-113b · r12 | Python(2차) · Flink | 에이전트 | 동시 소비 리플레이 | 둘 다 21/21, 알람 81=81(차이 0), CEP p95 Python 5.56s / Flink 5.68s | 기록 | — | — | `experiments/EXP-113b/raw/result_r12_*.json` |
| 14 | 09-28 | EXP-S09 · r13 | Python(2차) | 에이전트 | 과전류 주입 +3s kill, +8s start(진동 +6s는 다운 중 도착) | Python 3/3(스냅샷에서 재개), Flink(대조) 3/3. 알람 전체 15=15, 중복 0, 유실 0 | 기록 | — | — | `experiments/EXP-S09/raw/result_r13_*.json`, `alerts_r13_*.jsonl`, `s09_r13_actions.log` |
| 15 | 09-28 | EXP-S09 · r14 | V1 Flink 1.20.1 SQL | 에이전트 | 같은 시점에 TaskManager kill/start | CEP 3/3(체크포인트 복구). 알람 18(대조 15): **중복 3**(THRESHOLD 재발행), 유실 0. 잡 3개 RUNNING 복귀 | 기록(G8 중복 발생) | Kafka 싱크 기본(최소 1회) + 체크포인트 이후 재처리 | — | `experiments/EXP-S09/raw/result_r14_*.json`, `alerts_r14_*.jsonl` |
| 16 | 09-28 | EXP-S09 · r15 | V1 Flink 1.20.1 SQL | 에이전트 | 같은 시점에 JobManager+TaskManager kill/start | 재시작 후 잡 0개(`{"jobs":[]}`). CEP 0/3, 알람 3(대조 15): **유실 12** | 기록(G8 유실 발생) | HA 없는 세션 클러스터 — 원본 V1 11:52 사건과 같은 현상 재현 | — | `experiments/EXP-S09/raw/result_r15_*.json`, `r15_jobs_after.json` |
| 17 | 09-28 | L4 중간 판정 | Python(2차) vs V1 Flink SQL | 에이전트 | #13~#16 종합 | 정확도 동일, 지연 동등(p95 5.56 vs 5.68s, n=12), 복구 Python 우세(중복 0·유실 0 vs 중복 3 / 유실 12), 자원·복잡도 Python 우세 | **보류(판정 전)** | 비교 대상 미완: Flink 최선 설정(정확히 1회 싱크·HA), Flink 2.2.1 SQL(EXP-112), DataStream CEP(EXP-111) 미측정. 반복 수 1회(장치 3) | 규칙 | 위 근거 |
| 18 | 09-28 | EXP-112 · r16 | Flink 2.2.1 SQL (V1 SQL 무수정) | 에이전트 | `flink:2.2.1` + Kafka SQL 커넥터 5.0.0-2.2 이미지, V1 SQL 그대로 제출(3잡 RUNNING), Python(공통 기준)과 동시 소비 | 21/21, 알람 81=81(차이 0), CEP p95 5.73s(Python 5.52s), 메모리 평균 1,092 MiB·CPU 24.2%(Python 12 MiB·0.6%), 이미지 1.58 GB | 기록(재시작 미측정) | — | — | `experiments/EXP-112/raw/result_r16_*.json`, `stats_r16.csv` |
| 19 | 09-28 | EXP-S09 · r17, r18 | Flink 2.2.1 SQL | 에이전트 | TM kill / JM+TM kill 시도 | 리플레이 미시작, kill 안 함 | **무효(하니스 결함)** | s09.sh 가 FLINK_REST 미전달 → 사전 점검이 내려 둔 1.20.1 JM 조회 실패. 출력 숨김으로 발견 지연. 수정 후 r19·r20 재측정 | 규칙 | `experiments/EXP-S09/raw/INVALID_r17_r18.md` |
| 20 | 09-28 | EXP-S09 · r19, r20 | Flink 2.2.1 SQL | 에이전트 | TM kill / JM+TM kill 재시도 | 리플레이 미시작, kill 안 함 | **무효(환경 장애)** | Docker Desktop 엔진 500 오류. 호스트 여유 RAM 0.5 GB | 규칙 | `experiments/EXP-S09/raw/INVALID_r19_r20.md` |
| 21 | 09-28 | 정정(#4) | V1 원본 11:52 재시작 원인 | 에이전트 | Docker Desktop 프로세스 시작 시각 확인(Get-Process) | Docker Desktop 시작 11:51:56 = 원본 Kafka·Flink 재시작 11:52 | **정정** | #4의 '수동 재기동으로 보임'은 틀림. Docker Desktop 자체 재시작으로 컨테이너가 다시 떴고 그때 Flink 잡 소멸. 재시작 원인(메모리 부족 추정)은 미확인 | 규칙 | Get-Process 출력(2026-09-28), `harness/V1_FACTS.md` §5 |
