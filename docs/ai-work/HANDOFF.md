# HANDOFF — CECO SCADA·AI UI/UX

## 2026-09-28 진행 중 — 통합 관제 고도화 (미완료)

- 모든 탭 동일 UIUX 요청 반영 시작: 지식 스튜디오 상단 자료/그래프/연결현황 전환, KnowledgeReview 원본/생성/검토/게시이력 카드 선택 작업공간 적용·배포. 탭 전환은 v-show로 후보·입력·실행 polling 유지, 생성된 후보를 명시적으로 선택하면 검토 카드로 이동. 가독성·모바일 후보 목록/상세 레이아웃 보강. 브라우저1600 그래프37노드/47관계 표시, 상단3화면 전환, 하위 원본/생성/이력/빈검토 화면 확인. 390px 게시이력/빈검토 root390 넘침없음. 05/06캡처갱신, 14게시이력추가. 실제 후보 편집/게시·원문 상세·모바일 그래프·접근성 전체 검증은 남음.
- 실시간 스트림 안정성: 최신 SSE가 늦은 HTTP 조회로 덮이지 않도록 generation 취소, 이전 실행의 오류 콜백 격리, 잘못된 프레임 재조회. 브라우저 offline 이벤트에서 연결 표시 해제/기록 보존, online에서 읽기 재연결. UI27 tests/build 및 배포. 실제 브라우저 offline/on에서 경고→SSE연결복구, Agent 선택 유지 확인. 별도 새 Agent 실행/승인은 하지 않음.
- 온도 연속관측 결과: 60°C 목표에서 약274초 후60.97°C 범위 진입,298초 마지막60.61°C. 30초 유지 전에 자동운전 목표 변경 감지→관측 종료. 성공으로 표시하지 않음. `thermal-interrupted-browser.json`, `화면캡처/13_자동운전_목표변경_관측중단.png`. 마지막 수치는 종료된 관측이며 현재 목표는 자동운전 값을 다시 조회해야 한다.

- 온도 응답 관측 추가: `ThermalResponse.vue`/`thermalResponse.js`. 직접 temp_sp_c 반영 후 실제 TT101 추세, 교육용 목표±1°C 30초 신선한 관측 유지, 데이터 끊김·목표 변경·설비 재시작·5분 미도달 구분. 화면 관측으로만 명시하고 고장 해결/정비 완료로 부르지 않는다. 화면을 닫으면 종료. 능동 냉각 제어는 현재 모델에 없음을 표시. UI26 tests passed/build. 실제 브라우저60°C 설정 요청은 Modbus readback seq2917→2918, 이전목표66.2/온도65.8486. 읽기 전용13샘플은 seq2949→3034, 84.802초 동안65.1634→63.6644°C. 목표 미도달 상태를 실제 UI에서 확인. `thermal-live-observations.json`, `화면캡처/12_목표온도_실제변화_관측.png`. 이는 운전원 직접 조작/관측 검증이며 이상 감지→AI승인 E2E가 아니다. UI 조작 이후 목표60 상태(자동운전 약5분 뒤 변경 가능), 교반기 정지 유지. 추가로 ScadaLive 좌측 공정그림/센서그리드를 묶어 오른쪽 제어 높이 때문에 생기던 빈 공간 수정; 최신 web 배포 종료0. scada-layout 브라우저1600px에서 공정 하단578.656→센서 상단596.656(간격18px), 가로 넘침 없음 확인; 01 캡처 갱신. 기존 scada-e2e-20260928 세션은 온도 연속관측 유지 중이며 새로고침하지 않았다.

- 최신 카드형 UI: 프로세스의 각 카드를 클릭/Enter/Space로 선택하면 해당 작업 공간만 표시한다. 현재 서버 단계와 사용자 선택을 분리하고 자동 화면 전환을 제거했다. Agent SSE는 숨겨져도 유지한다. desktop 마지막 노드 잘림 수정, 넓고 높은 화면 sticky 프로세스, 모바일 모든 카드 접근 버튼 추가. 만료 대응안 승인 차단/재분석 안내(반려 가능). web 배포 완료, build 및 UI21 tests passed. 브라우저1600/390px 및 카드 전환/키보드/일부 스크롤 확인. `uiux-20260928/stage-workspace-verification.md`에 범위와 미결 기록. 03/09 캡처 갱신. 최신 새 E2E가 아닌 저장 기록 재열람 검증이다.
- action 이벤트 연계 보강 배포 완료: 같은 사건의 같은 ai-run origin proposal_id 이벤트까지 run_trace가 조회. 임시 DB3 tests passed(격리 fixture 실제 실행 확인), UI21 passed/build. 실제 저장 실행 e1a6d524 trace에 proposal_created/action_authorized/action_result 포함·브라우저 조치 카드 2개 이벤트 표시 확인. `화면캡처/11_조치_실행기록_카드.png`와 갤러리 추가. 다음: 개별 명령/응답/재관측 세부 이벤트, 긴 로그/재연결 시 스크롤·포커스, 실제 온도 회복 판정. Flink0 복구 요청 자동검토 거절은 기존 기록대로 유지하며 우회하지 않았다.

- 최신 사용자 추가 범위: ROBO Analyzer NVL 구현 및2026최신 Neo4j 라이브러리 조사, 그래프/BPMN 모든 관계명·정렬·겹침·잘림 꼼꼼한 검토, 행복경로뿐 아니라 온도 조절/냉각 등 실제 이상 해소 검증. 정지 또는 설정값 readback만으로 전체 성공 판정 금지. 이 범위는 아직 미완료.
- ROBO 읽기 전용 조사: `D:/work/robo/project/robo-data-frontend/src/features/code-analysis/components/graph/NvlGraph.vue`에 실제NVL, 캡션/선택/군집분리/가림영역 제외 fit/interaction destroy 구현. package는NVL ^1.0.0. npm 최신조회2.0.0, modified2026-09-23. 공식 https://neo4j.com/docs/nvl/current/ 및 https://neo4j.com/docs/reference/license/nvl/ 확인. 라이선스는 Aura/상용Neo4j 조건이고 우리 compose는5.26-community이므로 무조건 NVL로 교체하지 말 것. ROBO 사용자 경험/레이아웃 기법은 참고하고 라이선스 적합한 경로 검토. ROBO 파일 수정 없음.
- 열응답 검증 추가: `scripts/verify-thermal-response.py`는 실제ReactorPlant를 격리 실행(95C초기,노이즈0,autopilotOFF,1800시뮬레이션초). 유지93.47/목표65하향64.021/히터OFF57.039/히터OFF+유입OFF94.593C,4 assertions passed(`thermal-response-isolated.json`). 현재모델에 능동냉각장치 없음; 열손실/원료유입으로만 식음. 실제 Modbus/Flink E2E 또는 실물안전검증 아님. 냉각 조치 추가 시 물리모델·제어주소·UI·분석/승인·관측후판정까지 설계/검증 필요.
- ProcessFlow 로컬수정: 하나의복합path로 중간단계화살표가 없던 것을 개별path로 분리, 컴포넌트별useId marker, dangling근거부족선을 '보완 필요·실행하지 않음'상자로 연결, 관계명가독성/minwidth1000. frontend19tests/build 통과, 아직배포/렌더검증 전. 그래프 전체 UI검수는 진행중.
- 직전진행: knowledge reviewed 후보를 실제UI로 게시, digest7e54bb9c66563a30f2f7b3a392a3129170a20e540555c3438e1d8d7d2c43e7ae. 기존M101 asset_type agitator보존, P101추가. 실제37nodes47edges, 기존45edges전부유지, P101→IT101/FT101 HAS_SENSOR만2개추가(`knowledge-publish-verification.json`, pre/postpublish-graph.json). 화면캡처05/06및갤러리갱신. 직접제어경로를 설명HTML/생성script에 추가, nginx파일cp반영; 이미지재빌드는 다음web배포때 반영. guide-native-control.png는렌더찍었지만 시각최종검토남음.

- 사용자 요청으로 화면캡처 정리/재촬영 완료: 기존40개 항목은 `docs/ai-work/capture-archive-20260928-120809/`로 이동했다(원본 삭제 없음). 현재 `화면캡처/`에는 새 PNG10장과 `현재_UIUX_모아보기.html`만 있다. 공정/직접 제어/조작 이력/Agent 흐름/검토 카드/승인 결과/센서 문서/지식/모바일을 현재 배포 UI에서 촬영. Agent·승인 결과는 오전11시 저장된 실제 사건의 재조회이며 새 실시간 E2E가 아님을 갤러리에 표시. 검토 카드는 별도11:01 사건, 승인하지 않음. 갤러리 실제 브라우저10/10 이미지 로드 확인. 과거 handoff의 화면캡처 링크는 위 archive 아래 상대경로로 찾을 것.

- 추가 집약/복구 UX 배포: 공정·직접 제어를 대시보드 맨 위로 이동. 실습의 설비 기동·정지 바로가기는 inline 패널로 스크롤/포커스. GET simulation/controls에서 DB 조작 이력20건 복원, 당시 결과와 현재 상태 구분. SimulationControls는 sessionStorage에 주입 시각/사건 ID만 저장하고 새 서버 사건 목록과 대조하여 복원(캐시 상태를 사실로 표시하지 않음). frontend19 passed, build 통과. 실제 UI 교반기 정지 request b832d25c-0095-4c2c-a40f-e84c4096b06f, seq821→822 verified; 현재 교반기 정지. 새로고침 후 이력 복원 확인.
- **테스트 격리 사고/보정**: 이전 operator 테스트의 모의 reply lost 두 기록이 업무 DB에 생겼다. 실제 Modbus는 mock이었으며 명령 전송 없음. IDs5152c1ca-ffee-44e0-a924-d154d138cfc8 / 5517e6be-7358-4b0a-8c02-bdfbcd84c4fc, before.seq10, reason reply lost 조건을 모두 대조해 이 두 건만 삭제했다. 삭제 전 operator-browser-results.json, 후 operator-browser-results-clean.json 보존. 테스트에 DB_NAME ar100_pytest_ 접두어 강제 검증 추가. 이후 `docker exec -w /tmp/scada-20260928 -e PYTHONPATH=/tmp/scada-20260928:/tmp/scada-20260928/test-deps ... /app/.venv/bin/python -m pytest backend/tests/modules/test_simulation_controls.py --confcutdir=backend/tests --setup-show`로 isolated_work_database setup/teardown과20passed 확인(operator-controls-isolated.xml). 앞으로 테스트는 반드시 임시 작업 디렉터리/명시적 confcutdir와 DB 보호 조건을 적용할 것. 이전 실행에서 fixture 누락된 정확 원인은 추가 확인 필요하며 이전20passed를 격리 증거로 쓰지 않는다.
- 소스 기반 설명 후속 반영 필요: 새 Vue 직접 조작→simulation/control→Modbus→HTTP 읽기 경로가 생겼으므로 아키텍처 HTML에도 기존 FUXA 직접 조작과 나란히 명시할 것. 원래 AI 승인 경로와 혼동하지 않는다. 새 지식 후보 원문 일치 관계10개(센서소속7·문서3) 확인했으나 현재 그래프와 충돌/덮어쓰기 검토 및 실제 UI 게시 검증은 아직 남음. Flink 작업은 재조회에도0개, 재등록 차단은 미해소.

- 최신 사용자 요구: 같은 설비의 상태·기동/정지·설정값·반영 결과를 한 대시보드에 집약. 별도 FUXA 창을 기본 조작 동선으로 삼지 않는다. `PlantControls.vue`를 공정 그림 옆에 추가하고 simulation `/control`에서 고정 Modbus 주소로 1회 쓰기 후 새 HTTP 상태를 확인한다. 요청 UUID와 결과는 `manufacturing_operator_commands`에 보존하며 같은 UUID는 재실행하지 않는다. 현재 가상 설비만 대상. 범위·단위·활성 이상/인터록 기동 차단 및 주소/새 seq/중복 요청 시험 20 passed (`uiux-20260928/operator-controls-tests.xml`). knowledge/web 배포 완료. 실제 브라우저 목표온도75→72, seq504→505, request649b1ad1-c2d9-4dfc-bb77-5095fbb37fef verified. `화면캡처/관제개선_20260928/19-inline-control.png`. 캡처 후 버튼 줄바꿈·공정 아래 빈 공간을 수정하고 web 재배포 및 20-inline-control-layout.png 렌더 검증 완료. 기동/정지·나머지 설정값 브라우저 시험은 아직 남음.
- Docker 엔진은 복구됐다. 인용 repair 테스트15 passed(`meaning-repair-tests.xml`), 해당 변경 배포 확인. 실제 새 지식 실행560f88bc-b7d4-45c8-a6db-4e7ab6b6d8ed는 candidate 완료(`knowledge-repaired-candidate.json`), 원문 관계 검토/게시 전이다. 최신 HTML의 제공 응답과 public 파일 SHA256 일치 F7C28B87...39ACF9EC. 아래 Docker 중단/미배포 메모는 과거 상태다.
- 복구 후 Flink jobs 목록이 비어 있음을 확인했다. `docker start flink-job-submitter`를 포함한 명령은 자동 승인 검토에서 blocked by policy로 거부됐다(구체 사유 미제공). 우회 실행하지 않았다. job-submitter는 과거 실행 Exited0, 로그4RUNNING은 과거 근거이므로 현재 정상으로 해석하지 않는다. 이 복구와 전체 E2E 재확인은 남아 있다.

- 최신 사용자 디자인 지시: 제공한 L9~L1 가로 밴드 예시 스타일 그대로, 내용만 현재 시스템으로 변경. `reference-style-architecture.py`로 HTML의 단일 SVG를 9개 가로 색상 레이어로 교체했다. 모든 구성 박스는 레이어 안에 배치, 데이터/AI/제어 색 분리. `guide-reference-layers.png` 확인. 기존 3부 순서(설비 → 그림 하나 → 설명)는 유지한다. 이번 HTML은 로컬/public까지 반영됐으며 Docker 엔진 중단으로 실행 중 웹 반영은 아직 못했다.
- Docker 최신 상태: 물리 메모리 여유 약400MB, Docker top500/API timeout 확인 후 자신의 scada-guide/report/e2e 브라우저만 닫고 Docker Desktop restart를 요청했다. 현재 API pipe가 없음. 재시작 handle86829는 더 이상 조회되지 않으므로 상태를 확인하고 Desktop 기동 복구해야 한다. 다른 세션 capstone 브라우저는 건드리지 않았다. DB/볼륨 삭제 없음. 백엔드 테스트31724 결과 미확인, 인용 repair 변경 미배포. 프런트18 테스트 및 build는 통과. 기존 임시 복사69632는 목적지 디렉터리 소실로 진행되지 않아 해당 cp PID만 종료한 뒤 경로/의존성을 복구했으며 pytest 시작까지 확인했으나 Docker 엔진 장애가 겹쳤다.

- 최신 설명 순서 재확정: 사용자는 설비 설명을 전부 먼저 → 전체 레이어 아키텍처 그림 한 장 → 기술·연결 설명 후 종료를 요구했다. HTML을 이 3부 순서로 다시 배치하고 SVG를 1개로 통합했다. `guide-single-architecture.png`로 실제 렌더 확인. 이전 2개 그림 구성은 폐기됐다. `order-system-guide.py`는 직전 12절 HTML에 적용한 1회 변환이므로 현재 정본에 다시 실행하지 않는다. 정본 HTML을 직접 편집한다.
- 지식 후보 실검증 `fb5d5e42-d351-4b18-b211-c855feb0cfe7` 실패 원인은 원문의 '정지 제안 및 승인'을 AI가 '정지 제안·승인'으로 바꿔 인용한 것. 정확 인용 검증은 유지하고 잘못된 인용 경로를 알려 1회만 수정하는 invoke_grounded를 build.py에 추가했다. 3개 bounded repair 테스트 추가. 아직 배포하지 않았다. 현재 tool exec session69632에서 Docker 복사 및 해당 테스트 명령 진행 중이며 최근 poll에도 terminal이 아님. 중복 실행/재시작하지 말고 같은 핸들 또는 Docker 실제 상태부터 확인한다.

- 사용자 후속 요청 반영: 설명 HTML을 개념 정의 → 쉬운 비유 → 실제 사용·연결 순서로 전면 재구성했다. SCADA와 FUXA, 반응기와 교반기, 센서값과 설정값을 먼저 구분. 각 스택 정의와 연결 이유, 병렬 분석/원본 직접 저장/Modbus 명령/HTTP 상태 확인을 2개 SVG 그림으로 표현했다. 원본은 그대로 HTML이며 public/system-guide.html 및 실행 중 nginx 사본과 동기화. `scripts/rewrite-system-guide.py`는 이번 재구성용이고 이전 HTML은 `uiux-20260928/system-guide-before-definitions.html`에 보존. 이후 HTML 수동 수정 뒤 스크립트를 재실행하면 덮어쓰므로 주의. 두 그림을 실제 브라우저에서 보고 화살표·레이블 겹침을 확인했다. 온톨로지 비교 작업 중 요청을 받아 설명을 우선 수정했으며 아직 새 지식 빌드는 시작하지 않았다.

- 11:23 KST 실제 E2E 추가 완료: 브라우저 버튼 이상 주입 → 사건 `713fda58-751a-4f6f-9705-d8a642689436` 자동 연결 → 수동 AI 분석 → 3개 도구 조회 → 검토안 승인 → 직접 Modbus 정지 → `stop_verified`. 성공 실행 `e1a6d524-fdb4-4891-94cc-1cdb80005f41`. AI 조회 seq1364, 정지 확인 seq1387; 전류10.62→0.00A/진동8.32→0.05mm/s. `uiux-20260928/browser-approved-stop.json`에 실제 proposals/events/trace 저장. 분석 첫 시도 `9bcd5685-7652-4798-a138-831a0a5a80e6`는 추가 알람으로 사건 변경되어 실패했고 재분석 후 성공했다. 시험 후 UI에서 이상을 해제하고 교반기는 정지 상태로 유지했다.
- ProposalFacts/OperatorConsole 및 대비 변경 배포·브라우저 확인 완료. 재분석 흐름도에서 과거 제안을 현재 단계로 표시하지 않도록 run-origin 매칭 수정, 실패한 승인 처리는 warning 표시. 프런트18 tests passed 및 Vite build, web compose wait 종료0. 390px 화면 문서 가로 넘침 없음; 전체 접근성 검증 완료는 아님. `화면캡처/관제개선_20260928/실제동작_순서보기.html`에 실제 캡처를 엮었다. 15/16의 element screenshot은 내부 스크롤러 때문에 일부가 비어 있어 전달 목록에서 제외, 17/18 일반 스크롤 캡처를 사용했다.
- 다음 핵심: 지식 스튜디오 원본 대비 기능·자동 후보 인제스천 검증/보강, 반려·SSE 재연결·모바일/대비 추가 확인, 주입 추적 새로고침 유지. 전체 목표는 미완료이며 아래 11:13 항목의 미배포·정지 미검증은 위 최신 결과로 해소됐다.

- 11:13 KST 추가: 사용자 요청으로 GCP Cloud Run `knu-litellm`의 `coding` 모델 설정을 직접 수정했다. 실제 모델은 `openai/gpt-6-luna`. 도구 호출과 클라이언트 `reasoning_effort=medium` 조합이 400으로 실패하여, 해당 별칭 `litellm_params.extra_body.reasoning_effort=none`으로 upstream 값을 고정했다. `additional_drop_params` 시도는 효과가 없어 빈 목록으로 복원했다. 비밀키는 저장하지 않았다. 근거 `uiux-20260928/gcp-litellm-fix.json`; 수정 스크립트는 다시 실행하면 원래 값 기록이 덮이므로 불필요하게 재실행하지 않는다.
- 실제 SCADA 재검증: 분석 `8bd2cc15-d6b8-4509-8a1f-130fa12e3c57`에서 문서·관측·알람 도구 3개 성공 후 `stop_mixer` 검토안 생성. `uiux-20260928/gcp-fixed-scada-trace.json`, `화면캡처/관제개선_20260928/06-agent-review.png`. 이번 실행의 승인/정지 결과는 아직 검증하지 않았다. 이상 주입은 이미 만료되었으므로 오래된 제안을 그대로 승인하지 말고 새 이상·재분석으로 이어간다.
- 로컬 추가 WIP: `ProposalFacts.vue`의 근거/전후 상태 카드, `OperatorConsole.vue`의 같은 화면 FUXA 제어 dialog, App/SimulationControls/ScadaLive 연결 및 추가 대비 수정은 아직 빌드·배포·브라우저 확인 전이다. 다음에는 이 변경을 검증·배포하고 새 이상 주입부터 승인/Modbus readback까지 캡처한다. 이후 지식 스튜디오 보강 및 실패/복구/접근성 검증이 남았다.

- 사용자 목표: 소스코드 기반의 아주 쉬운 SCADA 설명 HTML을 먼저, 이어 통합 관제·이상 주입·사건 자동 연결·BPMN 형태 실시간 처리도·근거 카드·Modbus 조치 결과·온톨로지 원본 기능 재사용·실제 브라우저 E2E. SpecKit 요청은 다른 세션 메시지라 명시적으로 제외.
- 설명 정본: `docs/소스코드로_확인한_아주쉬운_시스템설명.html`. 코드 위치/제작 메모 제거, IoT SCADA 중심 12단계 상세 설명, AI는 짧은 마지막 절. `ai-web/public/system-guide.html`은 동일 복사본. `build-explanation.mjs`는 HTML 복사만 수행. 이전 MD는 정본 아님.
- 변경: simulation.py의 고정 시뮬레이터 이상 주입/해제 API, SimulationControls의 접수 대기 및 사건 연결, App의 동 화면 IncidentReview·검색/상태필터/근거탭·설명 링크. ProcessFlow는 실제 상태를 BPMN 형태로 표시(별도 BPMN 실행 엔진 아님). agent.py의 읽기 전용 SSE trace + ExecutionTrace 연결. KnowledgeCoverage는 실제 센서 소속 누락 현황 표시.
- 확인된 그래프: 현재 조회 36노드/45관계. 설비2/문서3, 12센서 중 HAS_SENSOR 5개. M-101 IT-102/VT-101 + 적용문서 연결, R-101 LT-102/PT-101/TT-101. 원본 스튜디오 전체 복제 아님. 온톨로지 고도화는 미완료.
- 검사: frontend 16 passed(`uiux-20260928/frontend-tests.txt`), backend 159 passed/1 skipped(`backend-tests.xml`, 격리 임시 DB), Vite build 성공, Python compile 성공. 설명 HTML axe 자동 위반0, 화살표9개 수동 대비 확인 항목.
- Docker 엔진 no route to host/500 발생 후 docker desktop restart로 복구됨. DB/볼륨 삭제 없음. 배포 전 active analysis/knowledge 각0 확인. 기존 이미지 before-20260928 태그 보존. knowledge/web compose up --build --no-deps --wait 종료0, 새 UI 실제 브라우저 접속 확인. Flink0을 확인한 뒤 기존 flink-job-submitter 1회 시작, 4/4 RUNNING 재확인.
- 다음: 배포 후 axe에서 대비21개 검출, CSS 대비 보강/공정 그림 위로 이동은 로컬 추가 수정이며 web 재배포 필요. 실제 대시보드 캡처 `화면캡처/관제개선_20260928/01-dashboard.png`. 브라우저 session scada-e2e-20260928. 실제 이상 주입·사건 연결·AI 제안·승인·Modbus stop_verified를 실행/캡처할 것. 아직 새 UI E2E 성공으로 보고하면 안 됨.
- 추가 남음: 명확한 조치 전후 카드, 같은 화면 설비 제어 동선, SSE 단절/복구와 거절·근거부족·실행실패 검증, 원본 스튜디오 대비 기능 보강 및 실제 인제스천 검증, 최종 접근성·캡처·보고. 기존 Sept23 완료 판정은 그날 범위일 뿐 현재 목표 완료 아님.


## 2026-09-23 후속 요청: 실제 통신 구성도와 순차 시연

- 최신 보고 자료: `프로토타입_아키텍처_보고용.pdf` 2쪽과 `프로토타입_보고메시지.md`. 기존 풀스택 보강본 생성 원본의 디자인을 그대로 재사용했다. Pilot을 하나의 업무 서비스로 설명하며 action 서비스 표기를 내부 ‘승인 후 조치’로 교체. 결정 사항은 세 가지 조치 전달 경로 중 선택, Process-GPT 채택 및 70명 운영 검증. 실라버스 대부분 구성·교재 제작 경험·영상 효율 테스트는 사용자 전달 현황이며 이번 진도 실측 결과가 아니다.

- 사용자 우선순위: 순차 캡처에 앞서 Modbus 직접 통신 구조를 확인하고 기존 풀스택 PDF처럼 시스템 아키텍처를 작성.
- 신규 산출물: 루트 `시스템구성도_실제통신구조_확인본.pdf` 4쪽, `시스템구성도_실제통신구조_확인근거.md`. 기존 보강본 PDF는 보존. 생성기는 `scripts/build-verified-architecture.py`.
- 실행 확인: FUXA 런타임 프로젝트가 `plant-simulator:502`, slaveid 1에 ModbusTCP 연결. EdgeX 수집 프로파일 실행, DIRECT_MQTT_ENABLE=false. AI 컨테이너에서 host.docker.internal:27002 연결 및 coil 1 읽기 [True] 성공.
- 구분: FUXA 직접 제어 / EdgeX 수집 / AI 승인 후 정지 쓰기는 Modbus. Vue 현재값과 AI 정지 확인은 backend를 거친 HTTP /state. Process-GPT 자동 연결은 현재 완료 범위가 아님.
- 후속 순차 캡처 완료: `화면캡처/보고용_순차시연/순서대로보기.html`에 이상 → Agent 도구 조회 → 검토 카드 → 승인 처리 → 정지 결과/FUXA 6장을 순서대로 배치. 보조 캡처와 evidence.json 포함.
- 실제 실행: 사건 2531a2d2-6d9c-4ba4-8102-faedd512e8bd, 분석 be797897-eadb-4695-a9c7-25b58514ef05. 실제 모델의 stop_mixer 제안을 브라우저에서 승인. Modbus 쓰기 후 seq 13544(true) → 13545(false), stop_verified/awaiting_maintenance 저장. FUXA M-101=0, IT-102=0.02 A, VT-101=0.03 mm/s 캡처.
- 시연 후 주입 이상은 /fault/clear로 해제했고 교반기는 결과 확인용 정지 상태로 유지. 별도 초기 선택된 이전 사건 48aaa05b-303e-4a7a-989a-c9be2b610a09에도 분석이 생성됐지만 승인하지 않았음. 보고 모음은 신규 사건만 사용.
- 통신 확인 PDF 4쪽의 ‘순차 시연 후속’은 제작 시점 기록이다. 이후 실제 완주 근거는 위 HTML/evidence.json을 우선한다. Agent 자동 시작과 실물 공장 제어는 여전히 미구현/미검증 범위.

최종 갱신: 2026-09-23 14:05 KST. 기존 코드·실행 상태는 다음 세션에서 다시 확인한다.

## 현재 판정

요청한 로컬 제품 UI 개선·영향 검사·실제 브라우저 검수·화면 캡처·보고 범위 완료.
[요구별 완료 대조](uiux-20260923/COMPLETION-AUDIT.md), [브라우저 검수](uiux-20260923/BROWSER-VERIFICATION.md), [일일 보고](D:/work/작업보고/2026-09-23.md)가 근거다.
교육용 Pilot 제작은 별도 세션의 `D:/work/study/시스템이해/PILOT_HANDOFF.md`를 따른다. 이 완료 판정은 별도 Pilot·모든 LAB 준비를 뜻하지 않는다.

## 구현과 마지막 수정

- Vue 첫 화면은 공정 대시보드. 실제 센서·추세·파이프라인·최근 사건·AI 도구 기록을 표시한다. 요청/실행 ID, 조회원·상태·도구 소요시간·오류를 추적한다.
- FUXA 자체 화면을 공정·제어·계측·설정·최근 분석 알람 구역으로 구성했다. 단위·소수·1280px 맞춤을 수정했다. 36개 바인딩과 가상 교반기 정지/기동 복원을 확인했다.
- 늦은 이전 사건 응답 간섭, 조회 실패 재시도, 빈 목록 로딩 잔류, 오류 포커스, 날짜 표시, 지식 검토 단계·후보 이동을 보강했다.
- Telegraf 알람 파싱의 빈 JSON 경로 오류를 수정했다. FUXA MQTT의 정확한 토픽 매핑에 맞춰 `scada/hmi/latest-alert`를 추가했고 원래 센서별 JSON 출력은 보존했다. 자연 발생 ML 알람이 화면에서 갱신됨을 확인했다.
- 지식 구축 검증 실패의 안전한 원인을 표시한다. 공개 사유는 고정된 내부 검증 문구만 허용하고 임의 provider 오류/거부 원문은 노출하지 않는다.

## 마지막 검증

- backend **154 passed / 1 skipped**, frontend **11 passed**, Vite 빌드 성공. skip은 root 권한에서 파일 쓰기 거부를 재현할 수 없는 기존 검사다.
- `completion-readback.json`: 배포 웹 파일 17개와 로컬 빌드 해시 일치. backend build.py 로컬/실행 해시 `8930eb3dd410580df32742bd51e9c461bf8bf2d12bf7ccfdba08119bf2d07da0` 일치.
- `diagnostics.json`: 센서 12/12 최근 15초 GOOD, Flink 4/4 RUNNING. 모델 설정 상태와 실제 실행 결과를 혼동하지 않는다.
- `live-alert-mqtt.json`: 원본 알람 JSON과 화면용 메시지 실제 동시 수신. `fuxa-alert-deployment.json`: 변경 전 백업, Modbus/HMI 보존, 저장 후 되읽기 확인.
- 실제 AI 실행 7a2a5455-36d2-44ef-92c4-a3667442fef2는 도구 3개 후 needs_evidence. 설비 자동 조치 없음. `browser-analysis-trace.json`.
- 최신 지식 재시도 dcef57ae-70fd-4ec0-9874-d431d92db07b는 원본 인용 불일치로 failed. 원본 4개·구조 조회 기록 보존, 실패 단계·버튼 복구 확인. 저장 모델 출력과 해당 원본을 읽기 전용 재검증해 원인을 확인했다. `browser-knowledge-retry.json`, 31/32 PNG. 그래프 미게시.
- 최신 진단 문구는 위 실행 이후 수정·검사·배포했다. 과거 기록은 소급 수정하지 않았고 동일 모델 실패를 다시 유발하지 않았다.

## 접속·재검증

- 대시보드 http://127.0.0.1:28180/ · FUXA http://127.0.0.1:27018/
- 시뮬레이터 :27080 · backend :28000 · Flink :27081
- `python scripts/dashboard-diagnostics.py`는 읽기 전용 상태 수집이다. Windows는 PYTHONUTF8=1을 설정한다.
- `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify-uiux.ps1`는 별도 소스/임시 작업 DB로 회귀 검사한다.
- 배포는 `scripts/deploy-uiux.ps1`로 진행 중 분석·작업·지식 생성 여부부터 확인한다. FUXA 알람 태그 이행은 `scripts/apply-fuxa-alert-topic.py`; HMI만 반영하는 `apply-fuxa-dashboard.py`와 역할이 다르다.
- 재부팅 뒤 Flink가 0개이면 원인을 확인하고 기존 submitter를 한 번 실행한다. 이미 실행 중인 작업이 있으면 무조건 재제출하지 않는다.

## 검증 한계와 보호 규칙

- 승인/반려 pending 클릭·503 화면은 실제 Vue 컴포넌트+시험 API 응답의 격리 검사다. 저장된 실제 승인 결과 화면과 구분하며 새로운 종단 조치로 계산하지 않는다.
- FUXA 서버 연결 경고는 35초 지연된다. offline 45초와 복구를 실제 확인했다. 마지막 값·조작 버튼은 남는다. 현장 Modbus 단절과 휴대전화 조작 품질은 합격 처리하지 않는다.
- 최근 분석 알람은 수신 이벤트이며 활성 목록/해제 상태가 아니다. 모델 후보 생성 성공·그래프 게시 성공·실물 공장·새 PC/lite+AI·다중 사용자 부하는 이번 완료 주장 밖이다.
- 개발 PC Docker VHDX 55.7GiB를 다른 PC 최소 요구량으로 전달하지 않는다. [용량 근거](uiux-20260923/DEPLOYMENT-SIZE.md)를 따른다.
- 사용자 WIP·미추적 ai-layer/ai-web·기존 DB·문서 보존. reset/clean, down -v, 광범위 prune, DB 초기화 금지. 비밀키 출력 금지.
- 다른 세션의 교육용 서비스가 함께 실행될 수 있다. 기존 CECO 폴더 이름·볼륨·포트를 임의로 바꾸지 않는다.

이전 중간 상태와 해결 이력은 `uiux-20260923/HANDOFF-before-completion.md`에 보존했다. 그 파일의 미배포/장애/남은 검사 문구를 현재 상태로 해석하지 않는다.

## 2026-09-28 그래프 상세 UX 추가
- OntologyGraphPanel: 상세창을 absolute overlay에서 문서 흐름으로 이동해 canvas 가림 제거. 키보드로 선택 가능한 설비/센서/문서 select 추가. 선택 항목의 실제 연결 방향, 인접 항목 이동 버튼, 저장된 관계 근거/속성 details 제공. 닫을 때 강조/overlay도 해제.
- M-101 실제 그래프 연결 7개 브라우저 확인. desktop1600/root1600, mobile390/root390. 상세 top1270 > canvas bottom1202로 겹침 없음. 15_지식그래프_선택관계.png 저장(한국어 관계명/2열 최종 조정 전 캡처이므로 재촬영 필요).
- 후속 미세 조정: 관계명 한국어 표시(원문 title), desktop 관계 카드2열. build pass. 기존 UI27 tests pass. 마지막 deploy session40065 결과 별도 확인.
- 미완: graph 구조모드 select 항목 대응, 최종2열 시각검증, 전체탭 긴 내용/오류/포커스 검증. Flink 재실행 자동검토 거절과 전체E2E 미검증 경계 유지.

## 2026-09-28 지식 메뉴 전환 보존 검증
- App 지식 화면은 최초 방문 후 v-show로 보존. 실제 브라우저 질문 입력→공정→지식 재방문에서 입력과 build 선택 유지 확인. 질문은 원래 값으로 복원, 생성/게시 요청 없음. 새로고침까지 보존한다는 의미는 아님.
- 그래프 schema 모드는 종류 목록, entity 모드는 실제 항목 목록으로 수정. schema Asset 선택 시 실제 관계6개/이웃조회 버튼0 확인. 1600 및390px root width 동일, 가로 넘침 없음. 선택 dropdown/연결 이동 시 상세 시작으로 사용자 요청에 의한 스크롤.
- 한국어 관계명/2열 카드 최종15 캡처 시각 확인, 갤러리에14/15 추가. web 최종deploy5018 exit0, build pass. 상세 raw 속성은 아직 길고 내부 명칭이 노출되어 정리 필요. 전체 E2E는 새로 수행하지 않음.

## 2026-09-28 승인 조치 세부 진행 이벤트
- actions.py: 실제 stop_mixer 어댑터에서 action_connecting / action_dispatch_started / action_acknowledged / action_observed 기록. dispatch는 전송 시작이지 수신 성공이 아님. ack와 새 HTTP/state 관측, 최종stop_verified를 분리. 재전송0 유지.
- ContextVar로 요청별 progress sink 연결/최종reset. 각 이벤트는 별도DB트랜잭션으로 즉시commit. IO구간 incident lock은 FOR NO KEY UPDATE로 변경하여 동시수정 차단을 유지하면서 event FK key-share 허용. progress DB lock2s/statement3s 제한. 저장실패는 기존 예외 분기로 전송전not_executed/전송후uncertain(현 메시지는 통신 실패로 뭉뚱그려져 후속 구분 필요).
- 실제 격리PostgreSQL에서 실행 중 별도reader의 trace 조회 확인. 기존 동시승인/중복방지 포함31 tests pass(action-progress-isolated.xml). 진짜Modbus클라이언트를 대체한 어댑터순서/쓰기1회/새seq 검사, progress실패전 쓰기0 확인. 실행중 DB_NAME ar100_pytest_ 강제. 실설비IO/E2E 시험 아님.
- UI ExecutionTrace/IncidentTimeline 단계 한국어 라벨과 관측seq/교반기값 표시. UI27tests/build pass. backend재시작전 active analysis0/build0 확인. 배포 session79303 결과 확인 필요.
- 다음: 통신/기록 오류 문구 구분, 전송후 기록실패 branch, 실제 새 이벤트 브라우저 시각검증. Flink 재시작 자동검토 거절은 우회하지 않음. 기존완료 사건에는 새세부이벤트를 소급생성하지 않음.

## 2026-09-28 진행 기록 저장 실패 구분
- ActionProgressError로 통신 오류와 기록 저장 오류를 분리했다. connecting/dispatch_started 저장 실패는 not_executed·명령0회, acknowledged/observed 저장 실패는 uncertain·명령1회이며 자동재전송없음.
- test_actions_integration + test_execution_trace 총34 tests pass. 전송후 실제정지값을 조회했더라도 기록실패면 성공으로 올리지 않음을 검사. 증거 action-progress-failures.xml. 모든 IO는 시험어댑터, DB는 ar100_pytest_ 격리. 실제 종단 검증 대체불가.
- 백엔드 배포 전 active analysis0/build0 확인. deploy71861 완료 exit0. 원본 Ontology Studio AppShell.vue 직접 비교 착수: 원본은 구축/질문응답 대화세션, 파일패널, 스키마편집/그래프편집 제공. 현 제조UI는 공개 그래프 read-only와 후보 검토게시로 분리. 원본전체복제라고 설명하지 않는다. build.py는 원본3패턴+모델클라이언트 재사용, 선택원본스냅샷/일치인용 검증/게시분리. 전체기능대조표 및 사용자 문서 최신화는 미완.

## 2026-09-28 읽기 쉬운 그래프 근거
- GraphEvidence.vue를 추가해 설명·단위·기준·문서버전·원본위치·인용·연결이유를 한국어 필드로 우선 표시. 긴 원문은 전체보기, 나머지 ID/해시/검토속성은 접힌 세부정보로 보존. 관계별 근거도 동일 컴포넌트 사용. 없는 출처를 만들어 채우지 않음.
- 실제 게시 M-101에서 원본인용/연결이유/7관계 확인. 1600px 스크린샷15 갱신 및 시각 확인;390px root390/가로넘침0, 세부속성 기본닫힘. web deploy82281 exit0/build pass. 이번 변경은 표시만, 그래프DB 쓰기 없음.
- 원본 AppShell와 현 UI/라우터/build 소스 대조를 ontology-source-comparison.md에 정리. 전체복제가 아닌 재사용/제조용변경/미지원기능 구분. 원본 자체 실행검증이나 새 모델 생성은 수행하지 않음.

## 2026-09-28 시스템 설명 그림 검수
- 설명HTML의 설비→한 장 L9~L1→스택 설명 순서를 확인. 기존 보고서가 아닌 구현 generator와 직접제어/승인코드 경로 기준. diagram의 raw/alerts 저장·접수 선이 중간카드를 관통하던 구간을 카드사이로 우회. 업무DB 연결도 저장구분상자 관통 제거.
- 분석시작 화살표를 접수워커 출발에서 Vue대시보드 출발로 수정: 현 구현은 사람의 분석 시작 요청. 자동기동으로 오해할 연결 제거.
- 설정값 설명에 목표와 실제온도 차이, 현재모델의 별도냉각장치 부재, 자동운전 목표변경시 이전관측종료를 추가. 원문과public미러 동기화.
- 전체viewport 캡처 guide-viewport.png에서 그림 시각 확인. selector 캡처 guide-architecture-final.png는 브라우저 캡처 오류로 빈 그림이므로 증거로 사용하지 않음. DOM169text존재 및 실제viewport에서는 정상렌더. web배포81665 완료 여부 확인.

## 2026-09-28 실제 후보 검토 UI
- 실제 등록4파일 선택→prepare 응답33노드29관계→검토탭에서 VT-101 단위mm/s/상한7.1/plant.yaml출처 확인. 모델생성/그래프게시 하지 않음.
- 후보 준비 후 찾기 어려운 동선 개선: 다른 작업탭에 준비된후보 개수와 검토열기 버튼. 후보 속성과 관계근거에 GraphEvidence 재사용. 선택 항목aria-pressed 추가.
- 브라우저 조건 검사: 체크+2자노트 게시disabled true, 체크+5자이상 false, 체크해제/노트삭제 true. 게시 버튼 클릭 없음. 1440/390px 가로넘침없음. 캡처16 및 갤러리 추가. 원본추출은현재API를실제로호출, 나머지는UI검사.
- UI27 tests/build pass, web86026 exit0. 다음: 편집폼/오류/키보드 경로, 미확인사항 영어문구와 작은글씨 보강. 후보는 scada-layout 메모리에만 유지, 새로고침하면 없어짐. 현재모바일390.

## 2026-09-28 후보 교체 실패 보호
- KnowledgeReview는 JSON파싱/preview/prepare 성공 후에만 현재후보를 교체한다. 실패시 기존후보/선택/검토의견 유지와 명시적안내. 성공한 새후보는 기존체크/의견초기화. 이전 구현은 요청전에 모두지웠음.
- 실제Vue setup 시험2개 통과: malformedJSON 및 prepare503 기존내용보존/정상교체후 동의초기화, 중복관계 로컬거절+POST0. build pass. 기존27테스트는 직전동일기반통과이며 이번추가2개 별도검사.
- 미확인3영어문구를 UI에서만 한국어설명으로 표시(원본후보/hash 변경없음). 편집폼/검토설명13px와42px입력높이, 모바일폼1열. web배포82730 완료 exit0. 브라우저최종재검증은다음.


## 2026-09-28 배포 브라우저 실패경로 확인
- 최신web에서 plant.yaml만 실제prepare→21노드20관계. invalid-candidate-test.json 선택은파싱실패, ready21/20유지 및기존후보보존안내 확인.
- browser offline on→같은prepare버튼→Failed to fetch와기존후보보존 확인. offline off 복구. 서버/DB/그래프 쓰기나 게시 없음. 오류영문상세는추가친절한문구개선여지있음.
-390px에서편집폼모든9컨트롤 좌45/우345/너비300/높이42, 가로넘침없음. mobile-knowledge-form.png 시각확인. 미확인3문구한국어표시확인.
- scada-layout 현재mobile390/원본1개추출후보/검토탭/편집폼열림, 연결복구완료. 후보미게시. 이번턴은새코드없음, 직전배포의실제브라우저검증진전.

## 2026-09-28 쉬운 설명 확대 및 현재 TODO 정리
- 설명 HTML의 설명 영역을 9,060자에서 16,020자로 확대. 쉬운 말과 같은 교반기 사례로 측정→Modbus→EdgeX→MQTT/EMQX→Telegraf→Kafka→분석/저장→화면/제어를 순서대로 연결. 설비→전체 그림→설명 구조 유지. public 미러 반영.
- npm build 통과, web 배포 session73889 종료0. 공개 /system-guide.html HTTP200 및 새 mqtt 절 존재 확인. 1440/390px 문서 가로 넘침 없음. 최신 전체 E2E를 수행했다는 뜻은 아님.
- processState의 resuming 오인 실행 표시와 proposal 없는 종료/미확인 상태 처리 수정도 함께 배포. 관련 시험8개 통과.
- 사용자 요청으로 프로젝트 TODO.md를 현재 현황 정본으로 신설: 30항목 중 완료18/남음12, 분야별 수와 확인 수준 명시. 루트 TODO.md 기존 강의 준비 내용은 보존하고 상단에 SCADA 요약/링크 추가.
- 최신 Flink 조회 jobs=[] 유지. 기존 작업 제출 시작의 자동 승인 거절 우회 없음. 전체 목표 active, 최신 종단 검증/냉각·온도 회복/전체 탭 검수/최종 캡처 남음.

## 2026-09-28 지식 구축 저장 기록 SSE
- ontology/build.py에 GET /builds/{id}/stream 추가. 1초 간격으로 저장 스냅샷을 확인하여 변경시 전송, 동일시 heartbeat, 최종 상태후 종료. 원본 텍스트 노출/모델 재실행 없음. 최초 없는실행404, 저장조회실패 unavailable.
- KnowledgeReview는 선택 실행 SSE를 연결하고 실패시 3초 뒤 HTTP조회/재연결. 선택 변경·컴포넌트 종료시 이전 연결 종료, 오래된 이벤트 무시. 연결/최종/끊김/마지막수신시각과 한국어 도구명 표시. 진행조회가 별도 후보 오류를 지우던 동작도 제거.
- Vue lifecycle 시험 및 기존 후보보호 총3개 통과, 백엔드 스트림 단위3개 통과, build통과. 최신 실제 모델 생성중 스트림은 아직 미검증. 전체 구축 단계를 새로 계측한 것은 아니며 현재 저장되는 도구반환/인용대조/최종상태 전달을 개선.
- 배포 전 실제 active analysis0/build0 확인. 배포 session8775 진행 중, 종료와 브라우저 확인 필요.
- 후속: 배포8775 exit0. 실제 저장 완료 build의 SSE HTTP200/text-event-stream와 최종프레임 종료 확인. 브라우저에서 실제4원본조회+구조조회 기록/한국어도구명/최종수신시각 확인. 1440/root1440. 캡처 knowledge-build-stream-record.png. 신규 모델생성이나 게시/설비IO는 하지 않음.

## 2026-09-28 실제 의미 생성 스트림 검증
- 브라우저에서 등록4자료 선택 후 실제 모델 생성 시작. run852efdf4-848d-42d2-b014-df216265900f. 처리 중 4원본+구조 조회5건이 SSE로 표시됨. 최종 candidate35노드35관계, 미게시. 결과 knowledge-build-live-result.json, 처리중 캡처 knowledge-build-live.png.
- 첫 오프라인 시험은 이미 열린 SSE가 계속 도착하여 끊김을 입증하지 못함. knowledge-build-offline.png는 실제로 최종기록 화면이므로 단절 증거로 쓰지 않는다.
- offline 이벤트에서 SSE종료/진행조회무효화/끊김표시, online에서 동일실행조회 재개 추가. 관련Vue시험3개 및build통과. 배포63203 진행, 실제네트워크 전환 재검증 필요.
- 재검증: web63203 exit0 후 실제 run970ea20d-e32d-4faf-81c4-09468c930371 시작. offline=true/연결끊김/표시도구0 확인. online복구후 동일실행 실시간연결/도구5건 확인. 중복시작없음, 후보게시없음. disconnected-verified/reconnected 캡처와 result JSON 보관. 최초852ef 실행은35노드35관계 후보완료, 두번째실행의 최종상태는result파일 참조.

## 2026-09-28 디자인 일관성 기준
- 사용자 강조: 디자인 일관성이 매우 중요. ai-web/DESIGN.md 및 src/design-tokens.css를 기준으로 글자위계/간격/카드/입력/상태/포커스/스크롤 규칙 기록. 전체탭 통일을 TODO 최우선 조건으로 명시.
- KnowledgeReview/Coverage/GraphEvidence/PlantControls 글자·줄간격 공통변수 적용 시작. 지식 작업의9~12px 기능설명은13px 이상으로 보강. 실행이력/도구기록/모바일 게시폼/포커스 정리. 후보 없는 검토탭에 안내와 원본/생성 이동 버튼 추가.
- 직전배포3159에서 원본/생성/게시이력 모바일390 가로넘침없음과 이력캡처 확인. 공통변수 및 빈상태 포함 최신 build통과, 배포34488 결과와 화면 확인 필요. 전체 디자인통일 완료 아님.
- 후속: 34488 exit0. 실제390px/root390, 공통caption13px 및 탭설명4개13px 적용, 후보없는 검토 안내/이동버튼 표시 확인.

## 2026-09-28 이상 대응 화면 공통 디자인 확대
- 조사/검토/실행/관측비교/이력/파이프라인/온도관측/시뮬레이션/제어콘솔 등10컴포넌트의 본문·보조설명 글자와 줄간격을 공통변수로 전환. 주요 native작업패널 버튼 최소44px, 입력폼 높이/포커스/reduced-motion 규칙 공통화.
- web83254 exit0. 실제과거사건 Agent카드 조회:1440/root1440,390/root390. 작업버튼5개 모두44px, 모바일카드64~66px. 주요본문13px미만 없음. ProcessFlow 모바일 그림설명12px는 아직별도 남음. 실제새AI/설비실행 없이 저장사건 조회로 레이아웃검증.
- 캡처 agent-shared-design-mobile.png. 전체탭/전체상태 디자인검수완료 아님. CSS 색/간격/카드모서리 등의 중복스타일도 추가 정리 필요.

## 2026-09-28 지식 구축 단계 계측
- 실제 invoke/원문대조/후보merge 위치에 model_requested,model_returned,source_quotes_verified,candidate_validation,candidate_validated 저장이벤트 추가. 도구반환과 started상태 구분. 원문불일치 1회수정/최종거절은 기존정책 유지.
- UI는 stage별한국어제목/설명 표시. 이전 모든stage를 인용실패로 간주하던 분기를 명시적 source_quote_validation에 한정. 원문대조통과는 관계정확성승인 아님, 구조통과는 최종저장/게시완료 아님을 표시.
- 격리DB/모델대체 의미구축+스트림18시험, Vue3시험, build통과. 실제 생성중 원본조회 및 오프라인복구는 직전배포에서 검증됨; 이번추가단계의 신규 실제모델 결과는 아직확인전.
- 배포전 active analysis0/build0. 이번배포 종료확인필요.
- 배포45885 exit0, 공개 API HTTP200 확인. 최신 모델 추가단계 실제 화면 검증은 다음 작업.

## 2026-09-28 단계표시 실제 실패 경로
- 최신계측 실제모델 run a7345c00-3d4c-4142-b632-26fc2899ad6c 실행. 모델요청→원본4개/구조조회→모델응답→인용대조통과→후보구조검증시작까지 실제브라우저 표시. 관계의 endpoint가 후보에 없어 검증실패, 미게시. 이를 성공시연으로 바꾸지 않음.
- 원본응답 UTF8로 보존: knowledge-stages-live-failed.json. 모델이 존재하지않는노드ID를 관계에 제안하는 문제는 추가원인분석/보강대상. 임의노드생성/잘못된관계게시로 해결하지 않는다.
- 화면네트워크/시간초과/JSON형식오류를한국어행동안내로변경, 기존후보유지시험포함3개통과/build통과. 긴실행기록말미에도실패사유표시, 세부펼치기이름을처리기록상세로수정. web70996 배포진행.
- 후속: web70996 exit0. 최종오류표시/한국어네트워크문구 최신브라우저 재검수는 다음작업.

## 2026-09-28 의미 후보 ID 오류 보강
- 실패원본응답 조사: 추가노드0개인데 AR-100/M-101 및 문서약칭을 관계endpoint로제안. 실제후보ID를 그대로 사용하지 않은 것이 원인. 원본/응답은 knowledge-stages-live-failed.json.
- topology_issues가 정확한미존재ID/중복노드/중복관계를 검사. 원문인용오류와 합쳐 최대1회수정(총모델호출2회)만 허용. 모델에 실제기존ID/class/name와 오류위치를 전달. 임의ID매핑/누락관계삭제/노드생성은 하지않음. 수정본도원문인용과구조재검증.
- 구조오류수정요청/최종거절은 candidate_structure_validation으로스트리밍표시. 격리DB+대체모델/스트림22시험통과(인용수정후구조오류가나와도추가재시도없음포함). build통과, active0/0 확인후77302배포진행.
- 후속:77302 exit0. 실제run82830a84-a1bf-4fd5-8c54-274219c316ed는수정요청없이후보성공. 실제브라우저에서요청/응답/원문대조/구조검증통과표시및1440가로넘침없음확인. knowledge-idfix-live-result.json/capture보관. 수정/재실패는격리시험검증. 지식진행표시항목완료로TODO19/30,11남음 갱신. 후보미게시.

## 2026-09-28 미연결 센서 근거 보강
- simulator/plant.yaml, plant.py 계산, fuxa/dashboard.py 식별자를 직접 대조. LT-101→TK-101, pH-101/CT-101→R-101 계측대상은 명확. TT-102는jacket_c이며히터본체센서아님, FT-102는valve개도/반응기수위의q_out이며밸브소속증거아님.
- AR100-SENSOR-CONTEXT.md 새근거자료 작성/실제UI업로드(기존자료덮어쓰기없음). 실제장치부착위치/고장원인/제어권한을증명하지않는제약명시.
- 등록5자료로 3센서만관계보강하고나머지2개미확인유지하는모델후보생성 run9c0c5dbc-511f-4201-bf0f-f75777928acf 진행중. 게시안함. 종료시결과검토필요.
- 완료확인:run9c0c... candidate40노드39관계. 새소속LT-101/pH-101/CT-101 및기존R-1013센서의HAS_SENSOR후보. TT-102/FT-102는소속추정없이 unresolved 유지. 원문인용불일치1회→재조회/수정→원문/구조검증통과 실제흐름확인. sensor-context-build.json 보관, UI후보검토열기까지실행. 미게시라현재그래프커버리지7/12는아직변경없음.

## 2026-09-28 실제 게시 차단 버그 수정
- 센서후보의인용/ID를검토하고실제UI게시시도했으나409검토hash불일치. 그래프37/47,7/12 그대로임을확인. 콘텐츠재귀비교동일하지만JS숫자직렬화(10.0→10)로서버저장hash와브라우저payload hash차이.
- 해결: 모델후보열기와구조추출후, 표시/동의전에정확한브라우저전송batch로 /preview 재검증. 그반환batch/hash를검토화면에표시하고기존동의초기화. 게시직전에hash만갱신하거나검증을우회하지않음. 서버기존canonical/과거hash정책은변경없음.
- Vue시험4개통과: 기존후보실패보호,동의초기화,저장원본hash불변,preview외게시요청없음을확인. build통과. web4421배포진행, 실제재검토/게시와그래프보존확인은다음.
- 최종확인:4421 exit0 후 실제후보재열기→새검토hash5e432e5c...→동의초기상태확인→검토의견입력→게시성공. 그래프37/47→43/54,기존37노드47관계전부보존,센서10/12. FT-102/TT-102만미확인유지. before/after/check JSON및coverage캡처보관. 실제게시버그해결검증완료.

## 2026-09-28 공정·사건 카드 디자인 통일 추가
- 공통 surface/border/text/선택 토큰을 추가하고 DashboardActivity의 카드·선택색·여백을 적용. KnowledgeCoverage 카드 모서리/여백/보조글씨도 같은 기준으로 변경.
- ScadaLive의 10~12px 보조글씨를 13px로 변경. 브라우저 기본 small 크기로 남은 직접 조작 이력 시각(10.83px)도 공통 규칙으로 수정.
- dashboard/pipeline/scada 버튼 최소44px 및 키보드 포커스 범위 확대. 어두운 표면은 동일한 밝은 포커스 사용.
- Vite build 통과, web99325/40599 배포 exit0. 실제 브라우저390px에서 root390, scada small최소13px; 사건 버튼100px, 상세열기44px; 사건카드 radius12px 확인. 1440/390 캡처 보관(shared-design-scada-*).
- 남음: 모바일 공정SVG는 축소로 내부 글자가 매우 작음. 확대/팬 또는 모바일 도형 배치 개선 필요. 이번 작업은 스타일 적용/일부 화면 검증이며 전체 탭 및 제어 E2E 완료 아님. 설비 명령 실행하지 않음.

## 2026-09-28 모바일 공정도 확대 접근성
- ScadaLive 전체 연결 그림을 보존하고 크게 보기/전체 보기 토글 추가. 확대시1000px 원본좌표1:1 표시, 내부 가로스크롤만 허용. tabindex/region/설명/pressed상태 및 어두운표면 포커스 추가.
- build통과,web26052 exit0. 실제390px 브라우저: root390,그림viewport332/content1000,SVG CTM scale1. ArrowRight로 scrollLeft40 확인. 캡처 process-zoom-mobile.png 직접시각검토. 최신값 갱신과 확대 상태 분리.
- 전체보기 복귀 확인은 아래 실행기록에 기록. 모바일 화면축소로 작던 글씨는 확대로 읽을 수 있음. 기본전체그림이 자동으로 모바일 배치가 되는 기능은 아님. E2E 및 전체탭검수는 남음.
후속 확인: SCAN8472로 갱신된 뒤에도 확대true/scrollLeft40 유지. 전체보기 복귀시 viewport332/content332/root390,pressedfalse 확인.

## 2026-09-28 그래프 검색 결과 접근성
- OntologyGraphPanel 검색 결과 목록 추가. 서버가 반환한 항목만 표시하며 항목 선택→기존 관계/근거 상세를 연결. 검색 입력/지우기 이름, 상태안내, 버튼높이/포커스 적용.
- 기존검색은 현재canvas에 하나라도 결과가 있으면 나머지 미표시노드를 무시했음. 반환노드중 없는것만 canvas에 추가한 뒤 모든검색결과 강조하도록 수정. 관계를 추론하거나 DB에 쓰지 않음.
- 새검색/초기화/그래프데이터 갱신/모드변경시 오래된 결과목록 제거. generation/canvas검사 유지.
- build 및web18847/85639 exit0. 실제모바일390에서LT-101 검색→3개(센서/문서/문서내용)→센서선택→TK-101 연결/원문인용/출처표시확인. 없는이름검색→결과없음/목록0 확인. root390. graph-search-detail-mobile.png 보관.
- 첫배포 결과문구의 인코딩오류를 발견하고 apply_patch로 한국어복구후 재배포. 마지막문구 재렌더 확인은 다음작업. mixed visible/missing 분기는 코드수정이며 실제대용량검색 검증은 남음. 독립자연어질의/관계편집완료로 세지 않음.

## 2026-09-28 구조/실체 검색 분리와 포커스 검증
- 코드에서 관계구조모드도 entity검색API를 사용하여 실제센서가 schema그림에 섞일 수 있음을확인. schemaSearch.js로 현재표시중인 class설명/속성/관계명 및연결양끝만 검색. entity API는설비모드에서만사용. schema에서는자연어모드제외,탭전환시텍스트모드초기화.
- 순수검색2시험통과: 설명/관계끝점,없는실체/공백/미일치/개수제한. web41708/42300 exit0. 실제schema LT-101검색결과없음, HAS_SENSOR는Asset/Sensor2개만표시. 한국어검색문구3개검색됨실제확인.
- 검색결과/선택기에서상세를열면상세region으로포커스이동,닫으면기존진입버튼으로복귀. 실제LT-101상세focus→닫기→LT-101Sensor버튼복귀/detail0 확인.
- 실제오프라인검색은오류/결과목록0확인. 영문Failed to fetch안내를한국어복구안내로수정하고시간초과/JSON응답오류구분. web76924 재배포. 최종한국어실제오프라인재검증은다음작업. 전체E2E완료아님.

## 2026-09-28 온도·능동 냉각 모델 구현 초안 (운영 미배포)
- 현재 Proposal은 stop_mixer/inspect_only뿐이고, 승인·재검증·UI문구도교반기전용임을소스확인. simulator기존noise는계측교란이며실제열원고장아님.
- simulator plant.py/yaml/sim.py에HX-102가상냉각기 추가:coil3 defaultOFF,목표온도초과시P제어 열제거900kW상한(교육파라미터). /state commands.cooler_enable 및thermal_model heater_kw/cooler_kw로명령과모형효과구분. 기존12센서태그유지.
- heater_stuck실제열원고착(히터명령OFF여도출력지속),cooling_loss명령ON에도열제거0 추가. 냉각은fault제거하지않음. 냉각없는과거설정은0출력호환.
- 5개결정론적물리시험+2개독립Modbus datastore시험=7통과. 실행중plant-simulator의/app을바꾸거나재시작하지않고 /tmp/scada-cooling-model에서독립인스턴스실행. MQTTfalse,실제기동plant/DB에명령안보냄. TCP왕복/E2E검증아님.
- 아직운영미배포. 다음:제어API허용목록/새명령조회·효과표시,Agent온도대응근거/Proposal스키마/재검증/승인IO/회복관측과UI라벨,EdgeX프로파일/FUXA설정동기화,부정경로포함격리TCP및실제E2E. 모델의thermal_model은시뮬레이션진값이며실제센서측정처럼표시하지말것.

## 2026-09-28 냉각 직접 제어 연결 초안 (아직 운영 미배포)
- simulation.py cooler_enable coil3 허용목록/입력모델 추가. runtime commands에bool형cooler_enable없으면쓰기전409. 냉각기기동은heater_stuck/cooling_loss에대한교육용대응만허용,기존고압인터록및다른고장기동차단유지. 주입고장을해제하지않음.
- 명령readback확인문구를온도회복/고장해소와명시구분. 기존request_id단일쓰기/불확실재전송금지그대로.
- PlantControls는실제plantcommands에냉각기가있을때만표시. ThermalResponse는냉각명령반영후현재목표온도관측시작. 명령확인시점의교육용thermal_model은한시점모형계산값으로표시하고실제센서와구분. live_state/AI근거에고장정답·모형열량추가하지않음.
- backend /tmp/scada-cooling 사본과 autouse임시PostgreSQL에서26시험통과. Modbus mapping은대체클라이언트시험이며네트워크실측아님. Vue build통과. 발견한line-height token뒤잘못된5도제거.
- 미배포상태유지. 승인제안·Agent온도근거/승인IO/지속관측,설정동기화,실제TCP검증및통합배포남음. 현재실행화면에냉각기있다고보고하지않음.

## 2026-09-28 냉각 실제 TCP/승인 어댑터 검증 (운영 미배포)
- test_cooling_tcp.py: 분리된Simulator와127.0.0.1:OS할당임시포트의실제pymodbus서버/client. 실제coil3쓰기응답→스캔전미반영→스캔후commandtrue→float32 TT-101register읽기/실제모형온도하강검증. 냉각상실시응답성공/commandtrue에도cooler_kw0/fault유지확인. 네트워크는실제,120스캔은가속모형시험이며실시간120초시연아님.
- 물리/레지스터/TCP 총9시험통과. 기존운영포트27002/설비상태/DB에는접속·명령안함.
- actions.py의고정coil단일쓰기어댑터공통화. stop_mixer와enable_cooling만고정매핑,냉각기미지원시연결전차단. 연결/송신/응답/새상태관측이벤트동일. cooling_command_verified는명령상태확인이며회복아님. 현재Proposal/decide에는아직냉각액션노출안함.
- 실제운영코드와분리된backend사본/임시DB에서execution_trace+actions_integration40시험통과. 냉각·정지양쪽송신전후기록실패/재전송금지/오래된seq거절/새seq확인포함.
- 남음:근거/문서/그래프기반온도조건검증,Proposal냉각등록및승인분기,지속회복관측저장/표시,EdgeX/FUXA정본동기화,통합배포·실제대표사건E2E. enable_cooling어댑터존재를승인냉각완성으로보고하지말것.

## 2026-09-28 근거 기반 냉각 승인 경로 초안 (운영 미배포)
- Proposal에enable_cooling추가. R-101/TT-101소속,단위degC/출처/유일상하한,10초이내GOOD관측,최신이력+현재온도상한초과,지원냉각기OFF/인터록OFF/현재목표범위 확인. 온도이력과실제조회된AR100-THERMAL-RESPONSE인용필수.
- 생성/승인/IO직전재검증. 승인후온도정상화면미실행. 명령/fingerprint변경시재검토. 중복승인은한번만전송. 결과cooling_command_verified는회복이아니며현재unresolved로보관,지속관측연결다음작업.
- Agent지침을온도근거에맞게확장,모형고장정답은근거API에추가안함. thermal절차원본작성(미등록/미게시). sensor조회에lsl추가.
- 검토카드공통actionPresentation으로냉각을점검요청이라고오표시하지않음. 냉각전후표는명령/목표/TT-101/seq. 프로세스는명령단계완료/결과미확인분리.
- 격리DB thermal승인14+기존40=54시험통과. 오래된값/품질/단위/출처/기준/미지원/인터록/현재값변화/중복/반려포함. 웹빌드통과(마지막processState단순분기수정후추가UI검증필요).
- 운영미배포. 절차/관계등록검토,자동온도관측저장·결과상태,UI실제검수,EdgeX/FUXA설정,통합배포와실제E2E남음.

## 2026-09-28 서버 지속 온도 관측 구현 (운영 미배포)
- thermal_observation.py: 승인냉각명령확인후 proposal에영속track 생성,statusobserving. backendlifespan의읽기전용worker가2초간격state조회,동일incident→proposal잠금순서로관측/이벤트저장. 장치명령을보내는코드없음. 다중worker동일seq중복시간/이벤트방지.
- 목표±1°C/새seq30초유지→temperature_stable/awaiting_maintenance. 6초공백/통신실패는유지시간초기화,목표/명령/식별/seq리셋/인터록변경은중단,15분시간초과는unresolved. 재시작은DBtrack으로재개하되공백을유지시간으로인정하지않음. 판정은수리완료아님.
- IncidentReview observing동안GET폴링유지,프로세스결과단계실제관측강조,서버관측차트/시각/seq/유지시간/마지막200표시. 새ThermalObservation.vue. 스트림및이력이벤트명을정지전용에서설비명령으로일반화.
- 격리DB포함backend63시험통과(연속관측16개저장/중복tick추가이벤트없음/조치1회/종료상태포함),UI상태9시험/build통과. 마지막인터록/읽기경과/DBtimeout보강은다음시험에서추가확인필요.
- 운영미배포. 실제브라우저냉각관측/서버재시작검증,원본문서/관계등록검토,EdgeX/FUXA동기화,모델기능포함배포/E2E남음. 현재프로토타입운영완료라고보고하지않음.

## 2026-09-28 냉각 통합 첫 배포와 실제 명령 확인
- 새검토기준(revision)이발생하면기존관측을interrupted로종료하도록보강. 고압인터록/오래된batch조회/DB잠금timeout도검증반영. backend65시험통과. recover_run은observing제안을재실행하지않고finished업무/별도관측으로복구.
- EdgeX/FUXA생성정본갱신: CoolerEnable 실제coil3, FUXA주소4(기존1-based변환),새제어행추가. 생성파일일치확인. **실행중FUXA프로젝트/EdgeX프로파일재등록은아직안함**. 웹통합제어는직접Modbus사용.
- active분석0/지식생성0확인후기존compose경로로simulator만재빌드배포1823 exit0. 가상모델초기화전state pre-cooling-deploy-state.json보관. 배포전교반기OFF를기존operatorAPI로복원verified. 기존목표/연속물리상태는초기화되어이전온도실험과이어지는것아님.
- knowledge+web86012 exit0,현재runtime에냉각모델/승인조건/관측worker/UI배포됨. thermal절차는아직파일만있고등록/게시안됨(그래서실제Agent냉각승인E2E아님).
- 실제브라우저냉각기기동→새seq60→61/commandtrue반영확인. 당시실제온도53.74,목표74.7이라열제거0(정상적인목표초과조건불충족). UI는회복으로표시하지않음. cooling-first-live-command.json에상태보존. 이어정지버튼으로냉각OFF복귀. 모델readings/commands는실제runtime조회,고장정답은Agent근거에노출안함.
- 남음:thermal문서/그래프검토게시,실제고온주입UI/Agent/승인/관측E2E,온도조건실측,재시작/단절실제검증,FUXA실행프로젝트동기화/캡처. Flink재기동차단우회안함.

## 2026-09-28 냉각 절차 실제 게시·근거 조회 확인
- 실제 브라우저 자료 등록 → 구조 추출 → 후보 검토 → 체크/검토 의견 → Neo4j 게시 완료. 문서 AR100-THERMAL-RESPONSE와 기존 R-101 사이 HAS_PROCEDURE를 원문 인용/SHA와 연결. 교육용 작성 절차이며 제조사 절차나 실물 설비 기준이 아님. 앞선 미등록/미게시 상태는 이 기록으로 갱신.
- 게시 SHA abfd2c72b64862c64396827024d406b57691aa770234e64bbd96efdacc21c6d5. 기존43노드/54관계가49노드/60관계로 증가. 노드ID, 관계from/type/to 튜플 대조로 기존 항목 누락0 확인. 기존 R-101에는 name/site/device만 재제시하여 원래 출처 속성 유지.
- 기존 온도 사건75bcecf1-c560-418d-a1f7-3dd5232ef53b의 실제 evidence API에서 thermal문서와 TT-101 단위degC/lsl40/usl95/출처SHA 반환 확인. 현재이력 available. 과거 사건 조회이며 새 고온 발생·Agent 실행·냉각 E2E 검증은 아님.
- 근거: docs/ai-work/uiux-20260928/thermal-{prepared,reviewed-candidate,publication-check,real-evidence}.json 및 graph-before-thermal.json,graph-after-thermal.json,thermal-publication-mobile.png. 모바일 게시 화면 직접 시각 확인. 전체 탭 디자인 검수·고온 E2E·FUXA 실행 설정 반영은 남음.
## 2026-09-28 디자인 일관성·탭 상태·모바일 동선 보강
- App의 공정/이상 대응 탭을 매번 파괴·재생성하던 구조에서 방문 후 숨김 유지로 변경. 탭별 #app 스크롤 저장/복원, 선택 탭 aria-current 추가. 실제 PC 공정620 ↔ 이상 대응853px, 선택 Agent 근거 조사 유지 확인. 다른 탭에서도 공정 관측을 유지하되 자동 설비 명령은 없음.
- 모바일 메뉴를 sticky로 유지하고 scroll-padding160px 적용. 실제 navBottom141.8px, 선택 단계 제목 top159.95px로 가림 없음. 모바일 카드 선택 시 상세 제목으로 이동/포커스, 프로세스 보기 버튼으로 그림 복귀 경로 제공. 실제 마우스 클릭으로 공정360 ↔ 조사2173px 복귀 및 선택 단계 유지 확인. agent-browser semantic click은 sticky 메뉴도 scrollIntoView 하므로 이를 사용자 클릭 검증으로 혼동하지 말 것.
- 공통 본문 보조 크기13px, 메뉴/새로고침/검색 조작 최소44px, 실습 카드 공통 간격/모서리 적용. 외부 FUXA로 가라는 낡은 실습 문구를 위 설비 직접 조작 안내로 변경. 사건 통계/배지/설명/검토 의견/지식 후보/그래프 범례/실행 기록의 낮은 대비를 공통 muted색으로 수정.
- 최종 web80825 배포 exit0. 실제 1440px operations/knowledge/coverage/graph,390px operations/knowledge/investigation 자동 WCAG2A/AA 검사에서 각 실행의 violations0 확인. incomplete1~2 남으며 자동검사만으로 모든 접근성/시각/실패상태 검증 완료 아님.390px root390, 메뉴44px, 내부 선택 상태 유지 확인. 마지막 배포는 ExecutionTrace 대비 변경이며 이전 동일 범위 검사 결과와 구분.
- 증거 docs/ai-work/uiux-20260928/a11y-*-final.json, stage-selected-mobile-final.png, graph-consistency-desktop-final.png. 사진 직접 검토. 그래프 전체맞춤 라벨은 여전히 작고 밀집됨; 확대/검색 상세는 가능하지만 큰 그래프 라벨 개선 완료 아님. 최신 고온 E2E/Flink 복구/FUXA 실행설정/전체 탭 오류·긴내용·재접속 검수 남음.
## 2026-09-28 온도 이상 주입 UI·실제 모델 연결
- SimulationControls에 교반기/반응기 온도 시나리오 선택 카드 추가. 기존 디자인 토큰 사용. thermal-anomaly API는 heater_stuck1200초만 주입하며 명령값을 변경하지 않음. 실제 지원 냉각기OFF/인터록OFF/기존고장없음 재검사. 이전 교반기 API 유지.
- tracking은 실제 같은site/device,주입 이후 시간,TT-101(온도) 또는 교반기 correlation을 요구. 임의 사건/과거 알람/다른 설비를 연결하지 않음. 해제·시나리오 종료+60초 이후 자동 연결 중단. 새 주입이 성공하면 이전 liveIncident를 비워 예전 결과 혼동 방지. 주입 원인으로 확정하지 않고 관련 알람으로 표현.
- backend 격리34시험(새8+기존26), frontend 추적/차단3시험 통과. 실제 분석·지식생성·온도관측 active각0 확인 후 knowledge+web34261 배포exit0. 이후 웹 오류/복구 안내 보강 최종55463 exit0.
- 실제390px UI에서 온도선택→주입→heater_stuck확인. seq1445→1460,TT10169.334→69.5307,교육모형heater_kw700/cooler_kw0 확인. 고온 임계 도달/냉각회복 시연이 아님. 중복POST409,UI버튼disabled 확인. UI해제로active_faults0,알람 대기 종료. 기존 운전 명령 펌프ON/교반기OFF/히터ON/냉각OFF 유지; SP는자동운전으로변함.
- Flink현황jobs[] 재확인. 재시작차단우회안함. 새 알람을 만들거나 감지완료로 표시하지 않음. 실제 온도E2E 및 냉각승인 검증 미완.
- 실제브라우저offline→주입요청실패→상태없음/주입disabled→online후상태재조회 및버튼복구. 요청자동재전송없음,active_faults0 확인. 직전 요청 결과 미확인과 현재 상태 연결복구 문구를 분리. 최종 화면 width390 확인. 실습영역axe14passes/0violations(오류안내 최종소폭변경 전 검사),실제캡처시각검토.
- 증거 docs/ai-work/uiux-20260928/thermal-ui-{before,injected,effect,cleared,after-offline}.json,thermal-injection-pending-mobile.png,thermal-injection-offline-mobile.png,thermal-reconnected-mobile.png,a11y-thermal-controls.json. Agent근거 API에는주입고장정답을추가하지않음.
## 2026-09-28 냉각 구현과 설명·그림 동기화
- lecture-sync 적용. 실제 simulator/plant.py의 목표초과 냉각·cooling_loss·heater_stuck 열수지, actions.py 냉각 조치, thermal_observation.py의±1°C/30초/15분·목표변경/관측단절 조건을 확인한 뒤 HTML 수정. 이전 보고서로 구현을 판정하지 않음.
- 소스코드로_확인한_아주쉬운_시스템설명.html: 설비 표에HX-102역할 추가, 냉각없다는옛문구2곳제거. 명령켜짐/실제열제거/온도안정/고장수리 구분. 직접 브라우저관측과 승인 후 서버 저장관측 차이 설명. 전체고온E2E미검증 표기 유지. 설비설명→레이어그림→기술설명 순서유지.
- explanation원본조각 및 reference-style-architecture.py의 L1장치표시도갱신. 생성기실행으로9레이어SVG/공개system-guide.html동기화. ProcessFlow의 정지전용선라벨을 승인된 조치·새 상태 확인으로 변경하여 냉각에서도거짓라벨없음.
- web72894 exit0. 공개HTTP200,공개내용과로컬정본전체일치. 1440/390px 문서루트넘침없음,모바일본문16px,냉각설비행1개/9레이어확인. guide-cooling-desktop.png,guide-cooling-mobile.png 직접시각확인. 그림전체선끝점/인쇄전수검수는별도남음. 실제냉각E2E검증을이번문서작업으로대체하지않음.
## 2026-09-28 그래프 확대·선택 유지
- OntologyGraphPanel에 확대/축소/확대율/선택 항목과 연결 확대 추가. 실제 Cytoscape 기존 노드·관계로만 동작하며 새 관계 생성/DB 수정 없음. 선택 연결은fit후최소100%로읽고빈곳드래그,전체맞춤으로복귀. 모바일에서는주변연결이화면밖일수있으므로드래그/상세목록사용.
- ResizeObserver의매번fit을처음표시때만fit/이후resize로변경. App에서지식탭재방문마다loadGraph를하지않아선택/확대위치보존. 명시새로고침및게시후조회는유지. 최신조회시각표시유지.
- web64907배포후실제TT101선택→121.52%확대/방향·관계명시각확인. 탭왕복후동일zoom/pan/선택유지,49노드60관계보존. 모바일100%확대/전체30%복귀,root390. graph-focused-desktop.png,graph-focused-mobile.png 직접시각확인.
- 선택상세검사에서기존badge/이웃탐색의낮은대비추가발견. 공통글자크기/녹색으로수정하고내부_Entity배지는제외. 최종web38947 exit0. 실제확대5회→300%/확대버튼disabled,전체보기복귀,모바일overflow없음확인. a11y-graph-zoom-final.json violations0/incomplete2,브라우저오류목록없음(64907검사).
- 모든관계자동충돌회피나대용량그래프성능검증완료가아님. 큰그래프/후보편집·독립질의/최신E2E·실패전수검증은계속남음.
## 2026-09-28 최신 캡처와 갤러리 범위 정리
- 갱신 전 PNG16개와 갤러리는 capture-archive-20260928-before-refresh에 복사·해시 확인하여 보존했다. 최신 UI 캡처9개(01/03/04/05/06/07/08/11/15)를 반영했다.
- 그래프 제목과 전체 배치를 포함한1440×1600 화면, TT-101 실제 연결 확대 화면을 구분했다. 모바일 직접 제어는 고정 메뉴 아래 패널 제목부터 보이도록 재촬영·시각 확인했다. 캡처에 없는 나머지 화면의 품질을 완료로 주장하지 않는다.
- 갤러리 노드/관계49/60으로 정정. 과거 모델 온도 관측/만료 제안/미게시 후보는 이전 검증 기록으로 표시했다. Agent/조치/결과는 기존713fda58 사건을 최신 UI에서 재열람한 것이며 새E2E가 아니다.
- HTML 이미지16개 파일 존재 및 실제 브라우저 로드 확인. 390px 문서 scrollWidth390. 갤러리 카드/링크 모서리·보조글씨 기준도 정리. TODO 최종 연속 캡처는 미완 유지.
