# HANDOFF — ceco_demo 정비 시나리오 (정본)

갱신 2026-10-08(클라우드 세션: §5-5 완료, 기동은 막힘 — §4). 실제 파일·컨테이너 상태가 이 문서와 다르면 실제가 우선이고, 이 문서를 고친다. 경위는 `docs/기록/decision-log.md` #190~#200.

## 0. 새 세션 시작 순서

1. 이 문서를 끝까지 읽는다. 이어서 `docs/기록/QA.md`의 §0(사용자 원문)과 §7(정비 시나리오 질문)을 읽는다.
2. 시연 순서는 `docs/데모_진행_안내.md`, 남에게 설명하는 문서는 `docs/마스터_가이드.html`(PDF 같은 이름)이다.
3. `docker ps -a`로 상태를 확인한 뒤 §5의 순서대로 기동·문체 정리·남은 검증을 한다. **이 일은 기동하는 새 세션의 몫이다**(사용자 10-08 "핸드오프좀 이거 이제 뛰워야한다면서", "여기서 안할거라서 말이지").

## 1. 목표와 범위

- 목표: 실제 데모 시연에서 정비 시나리오 3종이 문제없이 돈다. 흐름은 이렇다. 이상 발생 버튼 → 감지 → AI 에이전트 원인 분석(첫 경보 시점 값·온톨로지·매뉴얼 RAG·같은 사건 소견) → 판단 엔진(규칙·손익·뒤집힘 조건) → 정비 계획 카드 → 담당자 승인/반려 → 승인하면 단계별 작업 요청으로 **실제 수리**(가상 정비팀) → 회복 확인 30초 → 작업 보고서. 단순 장비 정지가 아니다.
- 범위: `D:\work\study\ceco_demo`만. hyd(`hyd-iot-edu`)는 건드리지 않는다.
- 완료 조건: 아래 §4의 미검증 항목이 실제 기동으로 확인되고, 시연 리허설에서 화면이 마스터 가이드·데모 진행 안내와 맞는다.

## 2. 기준(판정 규칙)

- 땜방 금지, 근본 수정, 해피패스 금지. "되는 것처럼" 만들지 않는다. 결함은 원인을 찾아 설정·코드에서 고친다.
- 완주 판정은 실제 스택에서 실제 LLM으로 돌린 결과로만 한다. 단위 시험·렌더 확인은 완주가 아니다.
- LLM은 OpenAI 직접 호출 `gpt-6-luna`(Responses API), 임베딩 `text-embedding-3-small`이다. 키는 `5_ai/server/.env.local`의 `OPENAI_API_KEY`에만 있다. 값을 출력하거나 커밋하지 않는다. 중계 LiteLLM은 쓰지 않는다.
- 설명 문서는 마스터 가이드 하나다. 이야기는 하나의 공장 이야기로 쓴다. "이 데모에서", "시연에서", "가상" 같은 이야기 밖 표현은 본문에 넣지 않고 출처는 각주에만 둔다. 모든 문장이 "~다"로 끝나는 보고서체가 아니라 장면·질문·대사가 있는 이야기로 쓰고, PLC가 왜 즉시 인터록을 하는지 같은 "왜"를 넣는다. 흐름은 사건 한 건 = 프로세스 인스턴스, task 단위로 맡는 쪽을 적는다. 시스템 문서는 구조·데이터 리니지가 중심이고 수치는 관심 밖이다.
- 메모리: 감시 부품은 `monitoring` 프로필이라 `make up`에서 빠진다(상시 약 3.0~3.3 GB). 다른 큰 스택과 함께 띄우지 않는다. hyd와 함께 띄웠을 때 PC 여유가 0.4 GB까지 떨어져 hyd가 재시작된 적이 있다.
- 10분이 넘는 시험(7개 경우 연속 실행 약 18분)은 사용자에게 먼저 묻는다. 바꾼 곳에 영향받는 경우만 다시 돌리는 것이 기본이다.

## 3. 확정한 설계

| # | 주 고장(이상 발생 버튼) | 헷갈리는 변형 | 구분 근거 | 정비 대안(온톨로지) |
|---|---|---|---|---|
| 1 | strainer_fouling 냉각수 스트레이너 막힘 | jacket_fouling 재킷 스케일 | FT-103·PDT-103·(TT-104−TT-103) | 온라인 전환·세척 / 감속 후 전환 / 정지 화학 세정 / 감속 버티기(규칙 제외) / 전체 점검 |
| 2 | bearing_wear 베어링 마모 | shaft_misalignment 축 정렬 불량 | 전류 선행(CEP) vs 진동만 | 지금 교체 / 배치 후 교체 / 지금 정렬 / 배치 후 정렬 / 둘 다 점검 |
| 3 | pt_drift PT-101 오지시 → 인터록 오트립 | outlet_valve_stick 배출 밸브 고착(실제 고압) | PT-101 vs 독립 PT-102, LT-102·FT-102 | 비교 교정 / 밸브 분해 정비 / 인터록 우회(규칙 제외) / 둘 다 |

- 열화 고장은 저절로 낫지 않는다. 원인에 맞는 현장 정비만 회복시키고, 틀린 정비에는 정비팀이 "부품 정상"(DONE_NO_FAULT) 소견을 낸다.
- 실행 길: 승인 → 계획 단계마다 작업 요청(PostgreSQL → Kafka `request.approved` → IT 수집기 → DMZ 게이트웨이(검사 1) → OT 수신기(검사 2)). OT 수신기가 설비 단계는 PLC(검사 3)로, 현장 단계는 가상 정비팀(가상설비 :8082, 계정은 OT 수신기만)으로 넘긴다. 인터록 리셋은 운전원 몫이고 AI는 기다린다. 결과를 알 수 없는 요청은 다시 보내지 않고 그 단계에서 멈춘다.
- 판단 엔진(결정론) = 온톨로지 손익 식 × 기업 사실값(`enterprise.fact` 20개) × 현재 관측. 규칙 EXCLUDE, 순위, 뒤집힘 조건을 낸다.
- 종결: 회복 기준 30초 유지(온톨로지 recovery) → 작업 보고서 → `enterprise.work_order`. 원인 불일치로 중단되면 정리 단계(LOTO 해제)를 거쳐 설비를 정지 상태로 넘기고, 재분석은 같은 사건의 소견을 근거로 쓴다.
- 자동 분석은 한계 이탈 경보(상·하한·CEP)가 있는 사건만 연다. 새 종류 경보가 15초 동안 더 붙지 않을 때 시작한다. 통계 급변만 있는 사건은 화면에서 "참고 신호"로 숨긴다.

## 4. 현재 상태와 검증 근거

| 항목 | 상태 | 근거 |
|---|---|---|
| 정비 시나리오 7개 경우(주 3·변형 3·불일치 훈련, s2 반려 포함) 실제 LLM 완주 | 검증됨(2026-10-06 15:56~16:18) | `experiments/final_run.log`, 원출력 `experiments/MAINT-SCN/*.json` |
| 가상설비 물리·정비팀 계약 시험 29건, 판단 엔진·실행기 시험 19건 | 검증됨 | `0_plant/simulator/test_*.py`, `5_ai/server/knowledge/backend/tests/modules/test_maintenance_decision.py` |
| 최종 실행 뒤 수정분(10-06 16:20~17:19): `api.py`(사건 목록 한계 경보 표시), `maintenance.py`(보고서의 배치 폐기를 승인 시점 교반기 운전 중일 때만 계산), 화면 `5_ai/web/src/App.vue`·`5_ai/web/src/features/operations/MaintenancePlanCard.vue`·`5_ai/web/src/manufacturing.css`·`5_ai/web/src/features/operations/ScadaLive.vue`(공정 대시보드에 냉각수 계통 FT-103·TT-103·TT-104·PDT-103·PT-102) | **부분 검증**: 단위 시험 19건·화면 빌드·카드 캡처(`experiments/MAINT-SCN/screens/`)까지. 실제 스택 재실행과 대시보드 실데이터는 미검증 | §5 |
| 메모리 | 검증됨: 감시 프로필 끈 ceco 상시 약 3.0~3.3 GB(10-06 실측) | decision-log #192 |
| Docker 메모리 상한 8 GB(`C:\Users\roede\.wslconfig`) | 적용됨(10-08 `docker info` MemTotal 8.3 GB) | — |
| git | 원격 `https://github.com/ahnchiyoon87/ceco_demo`(공개, `main`). 10-08에 10-06 이후 작업까지 커밋·push했다. `.env`(데모 비밀번호·토큰)는 git 에서 빼고 견본 `.env.example`(비밀 자리 `CHANGE_ME`)만 올린다. 지난 이력에서도 `.env`를 지우고 강제 push해 커밋 해시가 모두 바뀌었다(옛 해시로 된 기록은 지금 저장소에 없다) | `git log`, `git ls-remote origin` |
| 컨테이너 | 내려 둔 상태, 볼륨 유지. 다른 스택(hyd) 컨테이너 없음(10-08 확인). `dmz-influx`가 종료 코드 2로 남아 있으나 로그에 오류 없음 | `docker ps -a` |
| 마스터 가이드 | `docs/마스터_가이드.html`·`.pdf`(24쪽, 10-08 클라우드 빌드): 시스템 아키텍처 그림 한 장 + 이야기 「베어링이 닳던 날」(서막·1~11장) + 갈림길·데이터 리니지 요약·알려진 한계·출처. 이야기 밖 표현(데모·시연·가상·강사·훈련·흉내·배속)은 그림 밖 본문에서 0개(10-08 정리, 그림 속 부품 이름은 그대로). **검증됨**: 빌드 검사 ①~④ 통과 | 빌드 `python docs/기록/src/master_build.py`(Playwright). 빌드가 ① 그림 ⊇ compose 서비스·볼륨·망·토픽 ② 이야기 ⊇ 화살표 134개 ③ 치환 잔여·앵커·id ④ 그림 밖 본문에 이야기 밖 표현 0개를 대조(④는 고치기 전 본문으로 실패하는 것을 확인). 클라우드 PDF는 Linux 글꼴이라 로컬 빌드와 쪽 모양이 조금 다를 수 있다 |
| 클라우드 세션 기동(10-08) | **미검증(막힘)**: Docker 데몬·이미지 받기는 되지만, 세션 프록시가 바깥 HTTPS를 자체 CA로 다시 감싸 컨테이너 안 HTTPS(pip·npm·maven·curl 빌드 단계, 실행 중 OpenAI 호출)가 인증서 검증에 실패한다. 이미지 캐시가 비어 직접 만드는 이미지 9종 모두 새 빌드가 필요하다. 기반 이미지에 프록시 CA를 넣는 것은 자동 권한 분류기가 "TLS 약화"로 거부해 사용자 결정을 기다린다. 그래서 §5-2~4·6은 이 세션에서 하지 못했다 | `docker run python:3.12-slim` 안 urllib → pypi·npm·pytorch·maven·debian 5곳 모두 `CERTIFICATE_VERIFY_FAILED`, 호스트 `curl` OpenAI 200 |

실행에서 나온 결함 유형(다음에도 먼저 의심): 시차를 두고 붙는 경보 때문에 분석 중 사건이 바뀜, 회복 과도기 통계 급변이 다음 사건을 흡수, 다른 사건 소견을 지금 고장의 근거로 씀, 요약 통계에 시점 관계가 없음(첫 경보 스냅샷 필요), 계획 중단 뒤 LOTO 잔류, 시험 프로세스가 중지 뒤에도 살아남아 오염(시험 도구는 단일 실행 잠금).

## 5. 다음 행동 — 기동하는 새 세션

명령은 Git Bash 기준이다. 이 PC에는 `make`가 없다. 그래서 `Makefile`·README·`docs/데모_진행_안내.md`의 `make …` 대신 아래 `docker compose` 명령을 쓴다. 파이썬은 `python`으로 부르고, `python3`는 Windows 스토어 연결용 가짜 실행파일이라 쓰지 않는다. 출력이 깨지지 않게 `PYTHONUTF8=1`을 붙인다.

1. **상태 확인**
   ```bash
   cd /d/work/study/ceco_demo
   docker ps -a
   docker info --format "{{.MemTotal}}"
   grep -c OPENAI_API_KEY= 5_ai/server/.env.local   # 1 이면 키가 있다(값은 출력하지 않는다)
   ```
   다른 큰 스택이 떠 있으면 사용자에게 알리고 함께 띄우지 않는다.
2. **기동**: `docker compose up -d --build`(= `make up`, 감시 부품 제외). 바뀐 화면·백엔드 이미지가 다시 빌드되고, 학습기는 기동 때마다 모델을 만든다.
   - 상태: `docker compose ps -a --format "table {{.Service}}\t{{.Status}}"`. 상시 서비스는 healthy, 1회 도우미(`kafka-init`·`flink-job-submitter`·`fuxa-provisioner`·`graph-seed`·`model-trainer`)는 exit 0.
   - Flink 잡 4/4 RUNNING: `curl -s http://localhost:37081/jobs/overview`.
   - healthy가 안 되면 `docker compose logs <서비스>`로 원인을 찾아 근본 수정한다. `dmz-influx`는 지난번에 종료 코드 2로 끝나 있었으므로 healthy가 되는지 특히 본다.
3. **공정 대시보드 실데이터**: http://localhost:38180 공정 대시보드에서 냉각수 계통 5개 값(FT-103·TT-103·TT-104·PDT-103·PT-102)이 실제로 오는지 본다. 정상 운전 기준은 냉각수 약 30 m³/h, 반응기 약 70 °C다. 캡처는 `experiments/MAINT-SCN/screens/`에 둔다.
4. **수정분 실행 재검증**: `PYTHONUTF8=1 python tests/e2e/maintenance_scenarios.py s1 s2 s2m --reject-first "배치 폐기 손실보다 베어링 고착 위험이 더 크다고 봅니다. 진동이 상한을 넘은 채로 배치 끝까지 돌리지 말고, 지금 멈추는 안으로 다시 검토해 주세요."`. `--reject-first`는 s2에만 적용되고(10-06 최종 실행과 같은 조건), 실제 LLM을 쓰며 경우마다 수 분이 걸린다. 시작 전에 `tasklist | grep -i python`으로 앞선 시험 프로세스가 없는지 본다.
   - s1은 대시보드·냉각수, s2와 s2m은 보고서의 배치 폐기 계산과 불일치 정리를 본다.
   - 기대: 세 경우 모두 회복. 시험 도구는 배치 폐기를 판정하지 않으므로 `experiments/MAINT-SCN/<경우>-<시각>.json`의 `report.kpi.actual.batch_scrapped`를 직접 본다(s2m은 `drill_report`와 `report` 둘이 있고 두 번째 계획이 `report`). 규칙(`maintenance.py` 보고서 함수): 대기 단계가 없는 계획이 승인 시점에 돌던 교반기를 멈췄을 때만 참이다. 그래서 반려 뒤 "지금 교체"로 간 s2는 참, 이미 멈춘 뒤 재분석한 s2m 두 번째 계획은 거짓이어야 한다. 반려 없이 돌린 s2("배치 후 교체", 대기 단계 있음)는 거짓이 정상이다. 10-06 최종 로그(`experiments/final_run.log` 끝)에서는 s2m 두 번째 계획이 참으로 나왔다. 이것이 16:26에 고친 결함이며 이번 재실행으로 확인한다.
   - 7개 경우 전부(약 18분)는 사용자에게 먼저 묻는다.
5. **마스터 가이드 이야기 문체 정리** — 10-08 클라우드 세션에서 끝냈다(§4). 이야기 속 이름은 설비 컴퓨터(그림 「반응기 물리 모델」·plant-sim), 고장 주입 창구·계정(그림 「강사 화면 · API」), 정비팀(그림 「가상 정비팀」), 설비 시계의 빠르기(배속)다. 이후 본문을 고치면 빌드 검사 ④가 이야기 밖 표현을 잡는다. 로컬에서 다시 빌드할 때는 `PYTHONUTF8=1 python docs/기록/src/master_build.py`.
6. **리허설**: `docs/데모_진행_안내.md` 순서로 화면에서 시나리오 2를 직접 돌린다.
   - 고장은 강사 화면 http://localhost:37080/ 의 "이상 발생" 버튼이나 `curl`로 넣는다. 계정은 `.env`의 `INSTRUCTOR_USER`·`INSTRUCTOR_PASSWORD`이고, 명령 모양은 `Makefile`의 `FAULT`·`scenario-*`를 본다.
   - 마스터 가이드 이야기 6~10장(첫 경보 값, 손익 −449/−496만 원 순위, 뒤집힘 조건, 정비팀 소견, 회복)과 화면이 같은 장면인지 대조한다. 수치는 실행마다 조금씩 다르다.
   - 장면이 다르면 문서나 코드 중 틀린 쪽을 고친다.
7. **결과 기록**: 이 문서 §4의 상태를 갱신하고, `D:/work/작업보고/<그날>.md`에 CECO 절로 결과를 남긴다.

사용자 확인이 필요한 것:
- 시험으로 쌓인 사건 DB 정리. 데이터 삭제라서 시연 전에 지울지 묻는다.
- `experiments/`의 수정 전 사본(`*.bak-1006`, `master-1007/`) 정리.
- git 커밋·push. 사용자가 요청할 때만 한다. 커밋은 경로를 지정하고 `.env`·`.env.local`은 올리지 않는다.

하지 않는 것: 메모리 2 GB 목표를 위한 구조 변경(Kafka·Flink를 더 가벼운 부품으로 교체). 필요하다는 설명만 했고 사용자가 진행을 지시하지 않았다.

## 6. 보호 대상·넘으면 안 되는 선

- hyd 스택·파일, supabase는 건드리지 않는다. Docker Desktop 재시작은 다른 세션 작업을 끊을 수 있으므로 다른 세션이 쓰는 중이면 하지 않는다.
- `docs/기록/src/`에서 현재 빌드가 쓰는 파일: `master_build.py`, `guide_story.py`, `guide_tpl.html`, `arch_layers.py`, `arch_layers_ceco.py`, `arch_appendix_ceco.py`, `arch_inventory.py`. 나머지 `arch_build.py`·`arch_data.py`·`arch_extra.py`·`arch_fig.py`·`arch_internal.py`·`arch_layers_ceco_text.py`·`arch_lineage.py`·`arch_tpl.html`·`master_tpl.html`·`master_arch_svg.py`는 현재 빌드가 불러오지 않는 이전 판이다. 지우려면 사용자에게 묻는다.
- `D:\다운로드\설비데이터_전체흐름_스택_리니지_가이드.md`는 사용자의 설명용 문서다(10-07 수정, 10-08 시나리오 2 뒤집힘 값을 로그 기준 157.5로 정정. 원본·중간판 사본 `experiments/guide-edit-1007/`). 마스터 가이드와 따로 관리한다.
- 시험 도구는 한 번에 하나만 돈다(`experiments/MAINT-SCN/.lock`). 중지한 뒤 `tasklist | grep -i python`으로 남은 프로세스가 없는지 확인하고 다음 시험을 시작한다.

## 7. 경로

| 무엇 | 경로 |
|---|---|
| 질문과 확정 답 | `docs/기록/QA.md` |
| 사용자 발화 대응표(10-06~10-08) | `docs/기록/사용자발화_2026-10-06_08.md` |
| 결정 기록 | `docs/기록/decision-log.md` #190~#199 |
| 시연 순서 | `docs/데모_진행_안내.md` |
| 설명 문서 | `docs/마스터_가이드.html`, `docs/마스터_가이드.pdf` |
| 시나리오 시험 도구 | `tests/e2e/maintenance_scenarios.py` |
| 실행 원출력·캡처 | `experiments/final_run.log`, `experiments/MAINT-SCN/` |
| 기동 명령 | `Makefile`(`up`·`up-full`·`ps`·`jobs`·`scenario-*`), `compose.yml` |
| 온톨로지 정비 판단 층 | `5_ai/ontology/v2/kg/maintenance-decisions.yaml` |
| 기업 사실값 | `4_it/db-postgres/init/30_enterprise.sql` |
| 판단 엔진·실행기 | `5_ai/server/knowledge/backend/src/modules/operations/decision.py`, `maintenance.py` |
