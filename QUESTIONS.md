# 사람 확인이 필요한 사항

작업 기준: **AGENT_BRIEF_FINAL (2026-09-28)** 단일 문서. 이전 브리프(v1·v2)는 폐기. 각 항목에 막히는 작업을 함께 적는다.

## 입력값 (FINAL §6)

| # | 항목 | 상태 | 값 / 제안 | 막히는 작업 |
|---|---|---|---|---|
| I1 | V1 저장소·실행 | 확정 | 원본 `D:\work\study\lecture-iiot-scada` (`make up` + `ai-layer/start-service.ps1`). 실험 `D:\work\study\scada-rotation` (브랜치 `exp/stack-rotation-202609`) | — |
| I2~I4 | 패턴 창·판정 기준·워터마크 | 코드에서 확정 | N=10초, IT-102>9.6A, VT-101>7.1mm/s, 워터마크 5초 (`harness/V1_FACTS.md` §1) | — |
| I5 | 후보 공통 리소스 제한 | 미정 | Docker 할당 7.6GB 중 원본 V1이 약 4.9GB 사용. 제안: 비교 대상 모듈 컨테이너마다 `mem_limit` 1.5g·`cpus` 2 동일 적용 | M5 비교 |
| I6 | 유실·중복 허용치 | 미정 | 기본 0 | G8 판정 |
| I7 | §10 판정 규칙 서명 | 미정 | 아래 Q2 | 후보 채택 결정 |
| I8 | LLM 모델/키 | 확정(V1 설정) | LiteLLM Cloud Run `knu-litellm`, 모델 별칭 `coding` (`ai-layer/.env.local`) | — |

## 결정 요청

**Q1. L4 기준선 표기 (§11.1)**
V1은 Flink **1.20.1**에서 SQL `MATCH_RECOGNIZE`(filler 패턴 `OVERCURRENT OTHER*? VIB`)를 이미 쓴다. §11.1에 따라 다음으로 기록한다.
- EXP-112a = V1 그대로(Flink 1.20.1 SQL) — 기준선
- EXP-112 = 같은 SQL을 Flink 2.2.1로 올린 것
- EXP-111 = Flink 2.2.1 DataStream CEP(`followedBy().within()`)
- EXP-113 = Python 상태머신
이견 없으면 이대로 진행.

**Q2. §10-5(a) 트렌드 우위 조항**
트렌드 판정만으로 (a)가 성립해 비열등 후보가 자동 채택될 수 있다. 의도라면 그대로 서명, 아니면 "트렌드 근거는 독립 신호(릴리스·커밋·재단) 2개 이상" 조건 추가 제안.

**Q3. 클린시트 EXP-320 (§13.2)**
FINAL은 CAP-16을 NATS JetStream으로 대체하도록 정했다. 추가 결정 없음. 메모리 여유상 원본 V1과 동시 기동 가능(컨테이너 4~6개 예상).

**Q4. LiteLLM 프록시 버전 (§7.2)**
Cloud Run `knu-litellm`의 LiteLLM 버전을 로컬에서 확인할 수 없다(2026-09-28 `/health/readiness` 30초 무응답, 배포 소스 로컬에 없음). 배포 이미지 태그를 알려주시거나 GCP 콘솔 확인 필요. 1.82.7/1.82.8 설치 이력이 있으면 즉시 보고 대상.

**Q5. 원본 V1 Flink 잡 중단 (V1_FACTS §5)**
원본 V1은 2026-09-28 11:52 Kafka·Flink 재시작 이후 이상탐지 잡 0개 상태다. `make jobs`로 재제출할지. 원본 조작이라 결정 대기.

**Q6. Docker Desktop 비용 조건 (G10·비용 0원)**
이 PC는 Docker Desktop 4.87.0(Windows 11 Home + WSL2)이다. Docker Desktop은 직원 250명 초과 또는 연매출 1천만 달러 초과 기업의 업무 사용이 유료다 `[재확인]`. 회사가 기준 이하이면 그대로, 초과이면 WSL2 안에 Docker Engine(오픈소스)을 설치해 전환한다(compose 파일 변경 없음). 회사 규모 판단 필요.

## 원본 V1 영향 구간

장애 시험(S09~S12, S22)과 제어 시험(S14~S21)은 원본 V1을 멈추거나 설비 상태를 바꾼다. 이 구간은 원본을 쓰지 않는 시간에 몰아서 하고, 시작 전에 알린다. 나머지 비교는 원본 옆에 바꾸는 모듈만 붙이는 방식(원본 무영향)으로 한다.
