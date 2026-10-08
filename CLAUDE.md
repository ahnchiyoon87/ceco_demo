# ceco_demo — 프로젝트 계약 (로컬·클라우드 공통)

공용 헌법(`claude-skills/CLAUDE.md`)을 따른다. 로컬은 `~/.claude/CLAUDE.md`가 불러오고,
클라우드는 `.claude/hooks/cloud-bootstrap.sh`가 세션 시작 때 넣는다. 아래는 이 저장소에만 해당하는 것이다.
AR-100 반응기 라인 한 줄을 OT·DMZ·IT 세 구역으로 돌리는 학생 수준 예시 시스템이다(구성은 `README.md`).

## 1. 시작할 때 읽는 순서

1. `docs/기록/HANDOFF_정비시나리오.md` — 정본. 목표·기준·확정 설계(§3)·현재 상태(§4)·다음 행동(§5)·보호 대상(§6)
2. `docs/기록/QA.md` §0(사용자 지시 원문, 최신이 앞의 것을 대체)·§7(정비 시나리오) — 같은 질문에는 여기 답으로 답한다
3. `docs/데모_진행_안내.md` — 시연 순서. 남에게 설명하는 문서는 `docs/마스터_가이드.html`(PDF 같은 이름) 하나다
4. 결정 경위는 `docs/기록/decision-log.md`, 발화 원문은 `docs/기록/사용자발화_2026-10-06_08.md`

범위는 `ceco_demo`뿐이다. hyd(`hyd-iot-edu`) 스택·파일과 supabase는 건드리지 않는다.
HANDOFF §2(기준)·§3(확정 설계)은 근거 없이 바꾸지 않는다. 문서와 실제 파일·컨테이너가 다르면 실제가 우선이고 문서를 고친다.

## 2. 기록

- 단계마다 HANDOFF §4(상태·근거)와 §5(다음 행동)를 먼저 고치고 다음 일로 간다. 결정은 `decision-log.md`에 다음 번호로, 사용자 질문과 확정 답은 `QA.md`에.
- 실행 원출력은 `experiments/<이름>/`에 남긴다(정비 시나리오는 `experiments/MAINT-SCN/`, 캡처는 `screens/`). 실패는 파일:줄로 적는다.
- 문서를 여러 벌로 퍼뜨리지 않는다. "이렇게 했다가 폐기했다" 같은 경위는 본문에 넣지 않고 decision-log에만 둔다.
- 전체 작업을 마치면 작업보고에 CECO 절을 남긴다(로컬: `D:/work/작업보고/YYYY-MM-DD.md`. 클라우드에는 이 경로가 없으므로 HANDOFF §4에 남기고 사용자에게 알린다).

## 3. 시스템 규칙

- 정본 설정: 서비스 `compose.yml`, 포트·계정 `.env`(데모 기본값이라 추적함), 설비 `shared/registry/equipment.yaml`.
  등록부를 바꾸면 `shared/registry/generate.py`로 태그·흐름·PLC·FUXA·스키마를 다시 만들고 `plc`·`edge`·`dmz-gateway`를 다시 빌드한다(`Makefile` `regen`).
- 기본 기동은 감시 부품을 뺀 구성이다(`docker compose up -d --build`). Grafana·Prometheus 등 감시 부품은 `--profile monitoring`일 때만 뜬다.
  다른 큰 Docker 스택(hyd 등)과 함께 띄우지 않는다. 함께 띄워 hyd가 재시작된 적이 있다.
- LLM은 OpenAI 직접 호출 `gpt-6-luna`(Responses API), 임베딩 `text-embedding-3-small`. 중계 LiteLLM은 쓰지 않는다.
  키는 `5_ai/server/.env.local`의 `OPENAI_API_KEY`에만 있다(.gitignore). 확인은 `grep -c OPENAI_API_KEY= 5_ai/server/.env.local`로 개수만 본다.
- 정비 시나리오 시험 도구 `tests/e2e/maintenance_scenarios.py`는 실제 LLM을 쓰고 경우마다 수 분 걸린다. 한 번에 하나만 돈다(`experiments/MAINT-SCN/.lock`).
  시작 전·중지 뒤에 남은 python 프로세스가 없는지 확인한다. 바꾼 곳에 영향받는 경우만 다시 돌리고, 7개 경우 전부(약 18분)는 먼저 묻는다.
- 완주 판정은 실제 스택·실제 LLM 결과로만 한다. 상시 서비스는 healthy, 1회 도우미(`kafka-init`·`flink-job-submitter`·`fuxa-provisioner`·`graph-seed`·`model-trainer`)는 exit 0, Flink 잡 4개 RUNNING(`curl -s http://localhost:37081/jobs/overview`).
- 고장 주입은 강사 화면 http://localhost:37080/ 이나 `curl`로 한다. 계정은 `.env`의 `INSTRUCTOR_USER`·`INSTRUCTOR_PASSWORD`, 명령 모양은 `Makefile`의 `FAULT`·`scenario-*`·`fault-clear`.
- 먼저 묻는 것: 볼륨 삭제(`docker compose down -v` = `make clean`), 시험으로 쌓인 사건 DB 정리, `experiments/`의 수정 전 사본 정리,
  `docs/기록/src/`의 현재 빌드가 쓰지 않는 이전 판 삭제(목록은 HANDOFF §6). Docker Desktop 재시작은 다른 세션이 쓰는 중이면 하지 않는다.

## 4. 내용 규칙

- 정비 시나리오 3종(주 고장·변형·구분 근거·대안)은 HANDOFF §3이 정본이다. 땜방 금지·근본 수정·해피패스 금지:
  열화 고장은 저절로 낫지 않고 원인에 맞는 현장 정비만 회복시킨다. 틀린 정비에는 정비팀이 "부품 정상" 소견을 내고 계획이 멈춘다.
  손익 1위라도 규칙(인터록 우회·상한 초과 운전 등)에 걸리면 제외된다. 사례마다 같은 증상의 변형과 실제로 밟는 비해피 가지가 있어야 한다.
- 승인 전 AI는 분석·계획만 한다. 실행은 승인 뒤 작업 요청 길(DMZ 게이트웨이 → OT 수신기 → PLC 또는 가상 정비팀, 검사 3겹)로만 간다.
  인터록 리셋은 운전원 몫이고 AI는 기다린다. 결과를 알 수 없는 요청은 다시 보내지 않고 그 단계에서 멈춘다(설계).
- 업무 흐름은 "사건 한 건 = 프로세스 인스턴스 하나, 그 안을 task 단위(시스템·에이전트·규칙·사람·현장·운전원)"로 쓰고 갈림길은 "task N으로 되돌아감"으로 쓴다.
  화면의 단계 이름까지 바꾸는 것은 확인한 뒤에 한다.
- 시스템 문서는 구조와 데이터 리니지(출생 → 변환 → 저장 → 소비, 실패·분기)가 목적이다. 임계·타이머·금액 같은 수치는 관심 밖이지만
  부품·연결·프로토콜·제품 이름은 빠지면 안 되고, 틀린 구조 문장은 고친다. 설명 문서에 코드 식별자를 쓰지 않는다.
- 마스터 가이드 = 아키텍처 그림 한 장 + 하나의 공장 이야기. 이야기 본문(`docs/기록/src/guide_story.py`)에 이야기 밖 표현("이 데모에서"·"시연"·"가상"·"강사" 등)을 넣지 않고 출처는 각주에만 둔다.
  "~다"로만 끝나는 보고서체가 아니라 장면·질문·대사로 쓰고 "왜"(예: PLC가 인터록을 즉시 하는 이유)를 넣는다. 그림(`arch_layers_ceco.py`)의 부품 이름은 실제 구성 이름 그대로 둔다.
  빌드는 `docs/기록/src/master_build.py`(Playwright)이고, 그림 ⊇ compose 요소·이야기 ⊇ 화살표 누락 대조를 통과해야 한다.
- 온톨로지·스키마 결과를 사용자에게 보고할 때는 전문 용어에 비유 한 줄과 "사용자가 스스로 판정할 체크 질문"을 같이 준다.

## 5. 환경 (OS별)

| | 로컬 Windows | 클라우드 Linux |
|---|---|---|
| make | 없다. `Makefile` 타깃 대신 그 안의 `docker compose`·`curl` 명령을 직접 쓴다(`up` = `docker compose up -d --build`, `ps` = `docker compose ps -a --format "table {{.Service}}\t{{.Status}}"`) | 있으면 `make up`·`make ps` 등을 그대로 쓴다 |
| Python | 프로젝트 venv 없음. `PYTHONUTF8=1 python …`(3.14). `python3`는 Windows 스토어 연결용 가짜 실행파일이라 쓰지 않는다 | `python3` |
| 시뮬레이터 시험 | `export MSYS_NO_PATHCONV=1; R="$(pwd -W)"; docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -v "$R/0_plant/simulator:/sim" -w /sim ceco-plant-simulator:base python -m unittest` | Docker가 있으면 같은 명령에 `R="$(pwd)"`. 없으면 `0_plant/simulator/requirements.txt`로 venv를 만들어 그 폴더에서 `python -m unittest`(미검증) |
| 판단 엔진 시험 | 위 `R`로 `docker run --rm -e PYTHONDONTWRITEBYTECODE=1 -e REGISTRY_DIR=/repo/shared/registry/generated -v "$R:/repo:ro" -v "$R/5_ai/server/knowledge/backend:/app/backend:ro" -w /app ceco-ai-knowledge:base sh -c 'uv pip install -q --python /app/.venv/bin/python pytest && python -m pytest -q -p no:cacheprovider /repo/5_ai/server/knowledge/backend/tests/modules/test_maintenance_decision.py'` (이미지에 pytest가 없어 실행 때 넣는다) | Docker가 있으면 같은 명령에 `R="$(pwd)"`. 없으면 "미검증(환경 없음)"으로 남긴다 |
| 정비 시나리오 완주 | 스택을 띄운 뒤 `PYTHONUTF8=1 python tests/e2e/maintenance_scenarios.py s1 s1v s2 s2v s3 s3v s2m [--reject-first 사유]`. 표준 라이브러리만 쓴다 | `.env.local`(키)이 저장소에 없어 실제 LLM 완주를 할 수 없다. "미검증(환경 없음)"으로 남기고 알린다 |
| Docker | Docker Desktop, 메모리 상한 8 GB(`C:\Users\roede\.wslconfig`). 꺼져 있으면 켜고 `docker info` 응답을 기다린다 | Docker가 없을 수 있다. 컨테이너가 필요한 검증은 "미검증(환경 없음)"으로 남기고 알린다 |
| 마스터 가이드 빌드 | `PYTHONUTF8=1 python docs/기록/src/master_build.py` | `python3 docs/기록/src/master_build.py`(Playwright·Chromium 필요, 미검증) |

두 시험 이미지(`ceco-plant-simulator:base`·`ceco-ai-knowledge:base`)가 없으면 `docker compose build plant-sim knowledge`로 만든다. 판단 엔진 시험은 이미지 안 코드가 아니라 작업 트리의 `backend`를 덮어 올려 돌린다.
