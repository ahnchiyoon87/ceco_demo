# 사람 확인이 필요한 사항

작업 기준: AGENT_BRIEF v2. 각 항목에 막히는 작업과 막히지 않는 작업을 함께 적는다.

## 입력값 (§2)

| # | 항목 | 상태 | 제안 | 막히는 작업 |
|---|---|---|---|---|
| I1 | V1 저장소·실행 | 확정 | `D:\work\study\lecture-iiot-scada`, `make up` + `ai-layer` compose. 실험은 `D:\work\study\scada-rotation` (브랜치 `exp/stack-rotation-202609`) | — |
| I2~I4 | 패턴 창·판정 기준·워터마크 | 코드에서 확정 | N=10초, IT-102>9.6A, VT-101>7.1mm/s, 워터마크 5초 (`harness/V1_FACTS.md` §1) | — |
| I5 | 후보 공통 리소스 제한 | 미정 | 하니스 측정 전까지 제안값을 내겠음(머신 사양 확인 후) | 측정(M5) |
| I6 | 유실·중복 허용치 | 미정 | 기본 0 | G8 판정 |
| I7 | §9 판정 규칙 서명 | 미정 | 아래 Q2 참고 | 후보 채택 결정 |
| I8 | LLM 모델/키 | 부분 확정 | 현재 V1 설정 그대로(LiteLLM Cloud Run, 모델 별칭 `coding`) | — |
| I9 | BSL 제품 사내 PoC 허용 | 미정 | EMQX는 V1이 5.8.6(Apache)이라 해당 없음. Redpanda(EXP-212)·Neuron 상용판만 해당 | EXP-212 |

## 결정 요청

**Q1. L4 실험 구성 재배치 (§11.4)**
V1 패턴 탐지는 이미 Flink SQL `MATCH_RECOGNIZE`다(DataStream CEP 아님). 제안: EXP-141 = V1 그대로(SQL MATCH_RECOGNIZE, Flink 버전만 기록), EXP-142 = Flink DataStream CEP(`followedBy().within()`), EXP-143 = Python 상태머신. "CEP 논쟁" 질문은 그대로 유지된다.

**Q2. §9-4(a) 트렌드 우위 조항**
EdgeX가 '정체'로 판정돼 있어, 대체 후보는 Gate와 비열등만 통과하면 (a)로 자동 채택된다. 의도라면 그대로 서명, 아니면 (a)에 "트렌드 판정 근거가 1차 출처(릴리스 기록)일 것" 같은 조건 추가.

**Q3. 클린시트 C안 (§13.1)**
Kafka 제거 시 CAP-16(replay) 대체 경로가 없으면 G0 실패로 결과가 미리 정해진다. 보고용 구조 비교로만 쓸지, 대체 경로(예: PostgreSQL 이벤트 로그 테이블 재생)를 설계해 판정할지.

**Q4. LiteLLM 프록시 버전**
Cloud Run `knu-litellm` 버전을 로컬에서 확인할 수 없다(2026-09-28 `/health/readiness` 무응답, 배포 소스 로컬에 없음). 배포 이미지 태그를 알려주시거나 GCP 콘솔 확인 필요. 막히는 작업: §6.2 LiteLLM 항목 판정. 나머지는 진행.

**Q5. 브리프·참고 자료 파일 위치**
AGENT_BRIEF v2와 참고 자료 3종(`system-description.html`, `trend-survey-2026.md`, `rotation-guide.md`)이 대화로만 전달되어 디스크에 없다. 원본 파일을 `docs/research/`에 두어 주시면 재개·인용에 쓴다.

## 측정 시간 확보

실험 스택과 원본 V1을 동시에 띄우면 같은 머신 자원을 나눠 써서 M1·M5 측정이 오염된다. 측정 구간에는 원본 V1 스택을 잠시 내려야 한다. 원본을 내리는 시점은 미리 알려 드리고 진행한다.
