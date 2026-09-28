# 제조 AI 시연본 재개 정보

기준: 2026-09-21. 요구별 정본은 [CURRENT-ACCEPTANCE.md](CURRENT-ACCEPTANCE.md). 요청한 로컬 교육·전시 시연본의 인수를 완료했다. completion-artifact-audit.json과 인수표를 근거로 삼는다. 아래 실행 결과는 현재 PC의 교육용 가상 AR-100 시연에 한정한다.

## 목적과 보존 경계

CECO 10월 14~16일 전시를 위한 강사 제작본이다. 우수 수료생이 구현할 범위에서 기존 SCADA 위에 지식 구축·근거 조회·AI 대응안·사람 승인/반려·제한된 시뮬레이터 조치·결과 확인을 연결한다. 실제 학생 제작·제조사 승인·현장 배포로 표현하지 않는다.

- 루트: `D:/work/study/lecture-iiot-scada`. 최초 HEAD `106157f2ce54b7a6f18ec21387968ec7d5700528` 및 기존 WIP는 baseline-status.txt 참조. 기존 수정 파일을 되돌리지 않는다.
- 추가 영역: ai-layer, ai-web, knowledge-docs, docs/ai-work. final-live-audit.json에서 기준 85개 파일 해시 불변 확인.
- FUXA 런타임 HMI 바인딩 30개 보정은 예외로 명시한다. 원본 파일 수정 없이 백업 후 적용했다. `ai-layer/repair-fuxa-bindings.py` 및 EXHIBITION-RUNBOOK.md 참조.
- 회사 소유 Process GPT/Ontology Studio 수정·재사용·브랜딩 변경 승인됨. 로고 허락을 다시 묻지 않는다. 제3자 고지는 별도 보존한다.
- 참조 clone: `D:/work/study/_references/manufacturing-ai`. 코드 선별 통합이며 두 원본 제품을 별도 서비스로 제공하지 않는다. BPMN 엔진은 BPMN-DECISION.md에 따라 도입하지 않는다.

## 바로 전달할 자료

[제출 PDF](submission/CECO_패널신청자료_시연검증본.pdf) / [수정용 Word](submission/CECO_패널신청자료_시연검증본.docx).
신청서 2쪽 + 실제 화면 6장 별첨 3쪽, 총 5쪽. 날짜·담당자·서명은 제출자 기입. 과거 _동작과정포함 및 원래 파일은 이력이며 최신본이 아니다.

화면 원본 browser-qa/, 최종 문서 렌더 submission-qa/verified-1~3.png 및 focused-4~5.png. 그림 3은 승인 후 저장된 AI 검토 내용, 그림 5는 별도 반려 사건이다. 목업을 실제 화면으로 사용하지 않았다.

## 구현과 실제 검증

- 운영 URL http://127.0.0.1:28180/, 기존 SCADA http://127.0.0.1:27018/.
- LiteLLM coding 경유 실제 Luna 사용. 키는 ai-layer/.env.local에 있으며 출력 금지. 폐기된 키 13개를 복원하거나 재발급하지 않는다.
- 지식: 실제 UI 업로드→4개 원본 선택→Luna 후보→식별자 정리→사람 검토→게시. build cc1c4064-c010-47cf-9e4a-6e0f71b81670, 게시 36노드·45관계. 문서 버전 적용 맥락 v1 / 증거 정책 v3 / 교반기 대응 v2. browser-qa/ui-knowledge-*.json.
- 사건 63887a98-1500-41b5-809d-e31af903b72e: 기존 사건을 현재 고장 관측과 함께 분석, 실제 UI 승인→stop_verified→awaiting_maintenance→새로고침 보존. browser-qa/ui-stop-analysis.json, ui-stop-state.json, ui-stop-persisted.png.
- 별도 실제 반려 및 저장 보존: browser-qa/ai-rejection-analysis.json, ai-rejection-persisted.png. 정지는 정비 완료가 아니다.
- SCADA M-101 기동 버튼으로 재가동, 새 GOOD 전류·진동 및 운전 true 확인: browser-qa/scada-restart-state.json, scada-after-restart.png.
- 문서 부족/충돌/주입, BAD/오래된 관측, 모델 연결 실패/90초 timeout, 잘못된 인용, DB 장애, 실행 중단: MODEL-DEMO-ACCEPTANCE.md와 연결된 원문 증거. 실패 기록을 성공으로 덮어쓰지 않았다.
- 최신 UI: 사건 고정 목록, 현재 관측/검토/이력 바로가기, 조치 결과 우선 표시, 지식 그래프 검색·이웃·관계 출처. 1600×1000 및 390×844 실제 렌더 검수.
- 최종 회귀: 백엔드 143 passed / 1 skipped, 프런트엔드 6 passed. final-backend-tests.txt/.xml 및 final-frontend-tests.txt. root 권한 때문에 쓰기 거부 조건 재현 불가한 1개 skip을 통과로 세지 않는다.
- 외부 Python 고지: 설치본 86개 + 정확한 버전 태그 4개(원문 5개) + 회사 코드 승인 1개. BACKEND-NOTICES.md 및 3개 notices ZIP. 태그는 커밋으로 고정, 원문 체크섬 검증.

## 실행·복구

프로젝트 루트에서 `powershell -ExecutionPolicy Bypass -File ai-layer/start-service.ps1`.
기존 SCADA·iiot 네트워크·키 설정이 준비된 PC를 전제로 한다. AI graph 27474/27687, PostgreSQL 27532, backend 28000. Neo4j Desktop 7474/7687은 별개다.

원인 확인 후 영향 서비스만 복구한다. 관측 수집 중단은 telegraf-bridge 단독 재시작으로 복구한 이력이 있으며 오래된 값을 재사용하지 않는다. FUXA --.--는 태그 API와 바인딩을 구분하여 진단한다. 원인 없이 전체 스택을 재시작하지 않는다. down -v, DB 초기화, 기록 삭제 금지.

agent-browser는 사용자 전역 설치, Claude/Codex 사용자 스킬은 같은 원본 Junction이다. study/.tools로 국한되지 않는다. 기존 세션 ceco-ui-review와 ceco-scada-review는 작업 리소스 정리로 종료했다. 후속 검사 때 전역 agent-browser로 별도 이름의 세션을 연다. CUA 연결이나 데스크톱 설치를 다시 요구할 이유가 없다. D:/work에서 전역 CLI로 실제 서비스 접속·제목 조회·세션 종료를 검증했다. study/.tools 중복 설치와 Python 캐시 5개는 C:/Users/roede/AppData/Local/CodexWorkArchives/20260921-ceco-tools로 이동했다. 초기 inspect.cjs는 history/initial-browser-inspect.cjs에 보존했다. Vite 개발 서버는 종료했으며 서비스 URL 28180은 유지한다.

검증용 ar100-verification 컨테이너 5개(입력 fixture 포함)는 정지, 볼륨 보존. 운영 서비스와 검증 DB를 섞지 않는다. 테스트 conftest는 임시 전용 PostgreSQL DB를 만들어 제거한다.

## 다음 행동과 미검증 경계

1. 후속 변경 시 CURRENT-ACCEPTANCE의 해당 요구와 실제 증거를 먼저 확인하고 영향받은 범위를 재검증한다.
2. 최신 제출본은 라벨 겹침을 해소한 final-graph.png가 반영된 5쪽 PDF/Word다. submission-qa/graph-refined-3.png가 최신 3쪽 렌더다. 과거 자료의 미완료 문구는 이력으로 구분한다.
3. 새 PC 설치·PC 재부팅·장시간 전시 부하·학생 수업 완주 시간은 미검증이다. 사용자 인증·멀티테넌트·실제 PLC 안전 인증은 제공하지 않는다. 로컬 교육 시연을 공개 산업 운영 서비스로 주장하지 않는다.

이전 누적 인계는 [보존본](history/handoff-before-consolidation-20260921.md)에 있다. 당시의 모델 미연결·브라우저 미검증·패널 미완료 문구를 현재 상태로 되살리지 않는다.

## 최신 upstream 후속 반영

[UPSTREAM-REVIEW-20260921.md](UPSTREAM-REVIEW-20260921.md): DeepAgents 747c1f63과 비교 후 실제 검토 대기 체크포인트·실행/사건 식별자 검사만 제조 drive에 이식했다. 전체 모듈 버전 교체가 아니다. 최신 백엔드 회귀는 146 passed / 1 skipped(upstream-review-tests.xml), 운영 knowledge 재배포·파일 해시 일치·API 200 확인. 기존 실제 시연 증거는 유지한다.

## 리소스 종료 — 2026-09-21 사용자 요청

사용자가 작업 종료 후 Docker 리소스 정리를 요청하여, 진행 중인 분석(running/resuming) 0건을 확인하고 ar100-ai 5개와 iiot 25개 컨테이너를 종료했다. 종료 명령 성공 후 docker ps 출력이 비어 있어 실행 중인 컨테이너 0개를 확인했다. 검증 컨테이너는 이미 종료 상태였다. 이 프로젝트의 잔류 node 개발 프로세스도 조회되지 않았다.

컨테이너·이미지·네트워크·DB 볼륨·자료는 삭제하지 않았다. 현재 시연 URL은 중지 상태다. 다음 시연에는 기존 SCADA를 먼저 시작한 후 ai-layer/start-service.ps1을 실행한다. Docker Desktop 자체와 다른 사용자 앱은 강제 종료하지 않았다.

## Full HD 이미지 재촬영 — 2026-09-22

사용자 요청으로 실제 서비스를 다시 기동하고 agent-browser의 1920×1080 viewport에서 새 캡처 6장을 촬영했다. 전달 폴더: D:/work/study/CECO_패널_제출이미지_FullHD. 각 무압축 PNG 6,223,997 bytes, 촬영 픽셀과 저장 후 픽셀 동일 확인. 기존 1600×1000 파일을 확대한 것이 아니다. 원본과 manifest는 browser-qa/fullhd-20260922에 보존한다.

구성: 운영 대시보드 / 관계 그래프 / 저장된 AI 분석·승인 결과 / 승인·반려를 포함한 처리 이력 / 원본 자료·지식 구축 화면 / SCADA 공정 감시. AI 분석·승인은 9월 21일의 저장 기록을 9월 22일 다시 연 것이며 새 모델 실행·승인·설비 조작을 수행하지 않았다. 과거 제출본과 동일 장면 6개가 아니라 현재 자료 등록 화면과 운영 대시보드를 포함한 재촬영 구성이다. 이 폴더만 이미지 제출용으로 사용한다.

- 재촬영 후 agent-browser 세션 2개 및 AI/SCADA 컨테이너를 종료했다. docker ps 결과 실행 중 컨테이너 0개 확인. 이미지와 DB 볼륨은 보존했다.

## 후속 사용자 피드백 — 2026-09-22

FullHD 5번 자료 등록·지식 구축 화면과 6번 SCADA 공정 감시 화면은 UI 보강 필수 항목으로 루트 TODO.md에 기록했다. 아직 개선하지 않았다. 사용자는 제출 이미지를 화면 목록이 아니라 AI 도우미가 사건을 확인하고 근거를 조회해 대응안을 제시하고 사람이 승인·결과를 확인하는 작업 과정 중심으로 요청했다. 전체 화면 고정 원칙은 철회하며 핵심 작업 영역의 가독성을 우선한다. 현재 FullHD 폴더는 이전 6장 구성이고, 새로운 작업 과정 구성의 촬영은 아직 미완료다. 이번 확인에서는 컨테이너를 기동하지 않았으며 docker ps는 빈 결과였다.

## 핵심 과정 이미지 전달 — 2026-09-22 (최신)

현재 이미지 전달 정본: D:/work/study/CECO_패널_핵심과정_이미지. 1920×1080 PNG 4장, 각 6,223,976 bytes. 실제 UI 핵심 영역을 발췌하고 제목·단계 설명을 편집한 이미지이며, 편집 없는 전체 화면 원본이나 새로운 AI 실행 증거로 주장하지 않는다. 01 센서 비교는 9월 22일 조회값, 02~04 분석·승인은 9월 21일 저장 기록이다. 그림 안에도 날짜 차이 및 실제 UI 발췌/설명 편집을 명시했다. 이전 FullHD 6장 묶음은 현재 사용자 요청의 정본이 아니다.

제작 원본: browser-qa/focused-20260922/observations.png, proposal.png, timeline-full.png. timeline.png는 빈 화면으로 촬영된 실패 파일이며 사용 금지. build_images.py가 PDF 레이아웃으로 핵심 영역과 설명을 구성하고 PNG 4장을 생성한다. composition-manifest.json에 크기·용량 기록. qa-01~04.png는 동일 픽셀의 압축 검수본이며 모두 실제로 열어 잘림·겹침 및 출처 내용을 확인했다. 부분 이미지의 확대 배치가 포함되어 있으므로 무확대 캡처라고 주장하지 않는다. 5·6번 UI 개선은 아직 미완료.

리소스 상태: 이번 작업에서 iiot 25개 및 ar100-ai 5개 컨테이너를 재기동했고 start-service 완료를 확인했다. agent-browser 세션 ceco-focus를 열었다. 이후 추가 촬영 명령이 자동 승인 검토의 사용량 한도 오류로 거절되었다. 종료는 아직 실행·확인하지 못했으므로 이전의 컨테이너 0개 기록을 현재 상태로 간주하지 않는다. 승인 환경 복구 후 상태를 확인하고 촬영용 세션과 해당 프로젝트 컨테이너만 종료한다. DB 볼륨 삭제 금지.

## 다음 세션용 상세 핸드오프 패키지 — 2026-09-22

다음 세션이 현재 증거에서 바로 재개할 수 있도록 `D:/work/study/CECO_다음세션_핸드오프_20260922` 폴더를 구성했다. 시작 문서, 현재 상태·수용 기준·런북, 검증 근거, 기존 DOCX 삽입 원본 5장, 신규 핵심 과정 편집본 4장, 두 제출 문서 버전, 이미지·문서 재생성 소스를 포함한다. `.env`, `.env.local`, 비밀키, DB 덤프, Docker 볼륨, 전체 저장소는 제외했다. 확정 압축본은 `D:/work/study/CECO_다음세션_핸드오프_20260922_v1.zip`이다. ZIP 내부 `포함목록.json`과 `SHA256SUMS.txt`로 구성 및 파일 무결성을 확인한다.

패키지 제작 과정에서 agent-browser 세션 0개를 확인했다. 촬영을 위해 재기동했던 ar100-ai 5개와 iiot 25개 컨테이너를 모두 종료했고, 종료 후 `docker ps`가 비어 있음을 확인했다. DB 볼륨과 프로젝트 이미지는 보존했다. 재생성 가능한 Docker 빌드 캐시 16.63GB를 회수했다. 정리 후 집계는 이미지 24.58GB, 중지 컨테이너 2.318GB, 로컬 볼륨 4.786GB, 공유 빌드 캐시 12.18GB다. Docker WSL 데이터 디스크 파일 실측은 55.7GB이며, UI에 보이는 190GB는 현재 물리 파일 크기와 동일한 값이 아니다. VHDX 압축과 볼륨 삭제는 수행하지 않았다.
