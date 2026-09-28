# 카드 선택형 프로세스 작업 공간 · 2026-09-28

## 적용 내용
- ProcessFlow의 5개 단계는 마우스·Enter·Space로 선택 가능. 실제 서버 상태와 사용자가 선택한 카드를 구분한다.
- 서버 단계가 변해도 읽고 있는 카드는 유지한다. 새 사건을 열 때만 현재 단계로 초기화한다.
- Agent 카드는 SSE 도구 기록, 검토 카드는 대응안·출처·검토 폼, 조치/결과 카드는 저장된 전후 관측을 표시한다. 숨겨진 Agent 카드도 SSE 연결을 유지한다.
- SSE 오류 시 읽기 폴링을 재개한다. 명령이나 모델 호출을 자동 재전송하지 않는다.
- 데스크톱 연결선의 각 구간에 화살표를 배치했다. 근거 보완 분기는 명시된 종료 상자로 연결했다.
- 1600px 화면에서 잘리던 마지막 노드를 수정. 큰 화면·충분한 높이에서 프로세스가 스크롤 중 고정된다.
- 작은 화면에서는 그림을 가로로 이동할 수 있고, 별도 버튼으로 5개 카드에 모두 접근할 수 있다.
- 만료된 대응안은 승인 불가·재분석 안내. 반려는 허용한다.

## 확인한 범위
- Vite build 성공, Node/Vue 테스트 21 passed. 실제 컴포넌트 setup으로 카드 선택 유지, 만료 승인 차단/반려 허용, 늦은 응답 격리를 검사했다.
- 배포 브라우저 1600×1100: root scrollWidth 1600, 프로세스 영역 clientWidth/scrollWidth 모두918. 5개 노드가 화면 안에 표시됨.
- 담당자 검토 카드 Enter 선택: 검토 폼 표시, Agent trace 숨김. Agent 선택: trace 표시, 전후 비교 숨김.
- 데스크톱 페이지 스크롤: 프로세스 top8px 고정 확인. 카드 선택 시 프로세스 시작점으로 이동하도록 보정했다.
- 390×844: root/body scrollWidth390, 다이어그램330/720 의도적 내부 스크롤. 모든 카드 선택 버튼 높이64px 이상. Agent 버튼으로 카드 전환 확인.
- 화면 근거: stage-scroll-desktop.png, stage-mobile-audit.png, 화면캡처/03_Agent_업무흐름_저장기록.png.

## 아직 남은 검증·개발
- 이번 브라우저 확인은 과거 실제 실행 기록을 다시 열어 UI를 검증한 것이다. 새 이상 주입부터 승인까지 재실행한 E2E가 아니다.
- 새 실행의 연속 스트림, 네트워크 단절·복구, 장시간 로그 증가 시 스크롤 유지 및 키보드 포커스 가림을 더 검증해야 한다.
- 조치 기록 연계 수정 완료: run trace에 같은 사건·같은 ai-run origin의 proposal_id 이벤트를 포함한다. 임시 DB 3 tests passed (`trace-stage-isolated.xml`), 다른 실행·관계없는 대응안 제외 확인. 배포된 실제 API에서 기존 실행 e1a6d524의 proposal_created/action_authorized/action_result가 조회되고 브라우저 조치 카드에 2개 승인/결과 이벤트 표시 확인. 실제 명령 송신/응답/개별 재관측 시점의 세부 이벤트 추가는 아직 남았다.
- 실제 온도 회복/유지 판정 및 능동 냉각 액추에이터는 미완료. 명령 readback과 공정 회복을 동일시하지 않는다.
- 전체 접근성/화면 폭 조합 검증은 미완료. 최신 03 외 다른 순차 캡처도 변경된 카드 UI로 다시 갱신해야 한다.

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
