# HANDOFF — AR-100 공정 대시보드와 실행 가시성

최종 갱신 2026-09-23 13:29 KST · Codex
**재개용 기록이다. 현재 사용자 지시·현행 계약·실제 상태가 우선한다.**

### 최신 후속 상태 — 이전 항목보다 우선

**13:48 KST 복구 완료:** 아래 장애·미배포 기록은 해결 이력이다. Docker 전용 WSL 종료 후에도 Desktop 정상 종료가 멈춰, 확인한 Docker 설치 경로의 잔여 프로세스만 종료하고 Desktop을 다시 시작했다. 다른 WSL 배포판·데이터 파일은 변경하지 않았다. 기존 서비스 복구 후 WebOnly 배포·healthz 200·HMI 36개 연결을 확인했다. 지식 화면 현재 단계·후보 영역 이동도 실제 브라우저에서 확인했다(26 PNG). Flink 0개를 확인한 뒤 기존 submitter를 한 번 실행해 4개 RUNNING을 복구했다(`uiux-20260923/flink-after-docker-recovery.json`).

- Docker 복구: 엔진 API 500과 backend 로그의 `192.168.65.7:2376: no route to host`를 확인했다. `docker desktop restart --timeout 60`을 수행했으나 정상 종료가 60초 안에 끝나지 않아 CLI는 종료 코드 1이다. 직전 `docker desktop status`는 `stopping`이었다. **재시작 완료 아님.** 다음 행동은 Desktop 상태·해당 프로세스 확인이며, timeout만으로 중복 재시작하거나 다른 WSL 배포판을 종료하지 않는다. 데이터 삭제/초기화는 수행하지 않았다.

- 최신 지식 UI 보강(`KnowledgeReview.vue` 현재 단계 요약·후보 검토 영역 이동)은 프런트 11검사·빌드 통과 후 배포 시도했으나 Docker 엔진의 containers API 500으로 사전 검사에서 중단됐다. **이 변경은 미배포**다. Docker Desktop 프로세스는 살아 있었고 원인 확인 중이며 DB·볼륨 삭제나 강제 종료는 하지 않았다. 엔진 복구 후 진행 중 실행 확인 → WebOnly 배포 → 실제 화면 검증 순서로 재개한다.

- 강의용 Pilot 실물 제작은 별도 세션으로 분리했다. 인계는 `D:/work/study/시스템이해/PILOT_HANDOFF.md`. 이 세션의 범위는 기존 CECO SCADA·AI UI 개선이다.
- 13:29 KST 지식 구축 ValidationError 진단 개선을 실제 backend에 배포했다. 변경 파일 SHA256이 로컬과 실행 컨테이너에서 일치하며 healthz 200이다. 근거: `uiux-20260923/validation-diagnostics-deployment.json`.
- 배포 직전 진행 중 분석/작업 0, 지식 구축 0을 확인했다. 배포 스크립트에 지식 구축 running도 차단 조건으로 추가했다. DB 볼륨을 유지했다.
- 배포 후 FUXA HMI 되읽기·36개 연결 검증, 실제 브라우저 대시보드·지식 스튜디오 진입을 확인했다. 이는 신규 모델 실행과 오류 UI 검증을 대체하지 않는다.
- 진단 변경의 기존 자동 검사는 backend 152 passed / 1 skipped, frontend 11 passed, Vite build 성공이다. 기존 151개 기록은 이전 결과다.
- FUXA 브라우저 통신 단절/복구는 후속 확인했다. 내장 경고 지연은 35초이며 offline 45초에서 빨간 배너, online 복구 후 배너 해제·값 갱신을 확인했다(16/17 PNG). 마지막 값이 유지되므로 HMI 안내를 수정·반영하고 36개 연결을 재확인했다. 조작 버튼 자체는 단절 중에도 남으며 현장 Modbus 단절 시험과는 구분한다.
- 남은 검증: 개선된 오류 표시의 실제 화면, 승인 대기·반려 상태의 브라우저 동선. 기존 브라우저 검수 완료 항목은 BROWSER-VERIFICATION.md에서 확인하고 반복 작업을 피한다.
- 13:35 저장된 승인 결과·이전 반려 카드의 실제 브라우저 표시를 확인했다. 새 pending 승인/반려 클릭은 수행하지 않았다. 여러 날짜 사건이 시각만 표시되던 문제를 고쳐 App.vue/ObservationComparison에 날짜를 추가하고 프런트 11검사·빌드·WebOnly 배포 후 화면 확인했다. 근거는 BROWSER-VERIFICATION.md 후속 절과 19/20 PNG다.
- 후속 격리 브라우저 검수에서 실제 Vue 컴포넌트의 pending→승인/반려·503 오류·모델 실패 표시를 확인했다(21~24 PNG). API는 시험 응답이며 실제 종단 조치로 계산하지 않는다. 오류가 클릭 위치 위로 가려지는 문제를 수정해 오류 안내로 이동·포커스하고 프런트 11검사·빌드를 통과했다. 검증 페이지는 ai-web/tests/review-browser.html, 기록은 BROWSER-VERIFICATION.md 격리 화면 절을 참조한다.

## 0. 30초 브리핑

사용자 요청은 강의 제작과 별개인 SCADA 제품 UI/UX 개선이다. 첫 화면은 공정 대시보드로 확정됐다.
대시보드·FUXA HMI·도구 실행 기록·파이프라인 상태가 로컬 서비스에 반영돼 있다.
자동 회귀와 실제 API/모델 실행에 이어 브라우저 검수도 진행했다. 현재 근거는 uiux-20260923/BROWSER-VERIFICATION.md다. 신규 지식 분석이 ValidationError로 실패하여 원인 조사와 FUXA 통신 단절 경고 검수가 남아 있다.
서비스는 실행 중이며 DB와 기존 자료는 보존돼 있다. 전체 목표를 완료로 표시하지 않는다.

## 1. 배경

사용자는 역동적인 UI, 사용 도구와 처리 과정의 가시성, 버그 검토 및 디버깅 기반을 요청했다.
KNU 제조AI v10 ZIP은 스택과 레포 참고자료이며 강의 시간·커리큘럼 요구는 이번 제품 요구가 아니다.
Docker 등 필요한 로컬 실행을 자율 진행하도록 승인했고 반복 승인 질문을 원하지 않는다.
추가 요청은 Docker 용량 설명·다른 사람의 배포 부담 감소 및 대시보드형 첫 화면이다. 별도 마감은 주어지지 않았다.

## 2. 확정 방향

- 대시보드 → 사건 선택 → 근거·대응안·검토·이력으로 이어진다. 공정과 AI 흐름을 함께 보기 위한 결정이다.
- FUXA 자체 HMI도 개선하며 직접 제어 기능을 보존한다. 새 대시보드는 기존 제어 시스템을 임의 대체하지 않는다.
- 애니메이션은 조회된 운전 상태를 사용하고 진행 표시는 저장된 실행 이벤트를 사용한다. 허구의 진행률을 만들지 않는다.
- 원본·후보·게시와 사람 승인을 구분한다. AI 자동 재가동이나 직접 승인 권한을 추가하지 않는다.
- Docker 전체 개발 디스크를 수신 PC 사양으로 요구하지 않는다. 캐시·다른 프로젝트·실습 검증 DB를 배포 요구와 구분한다.

## 3. 절대 규칙

기존 수정/미추적 파일을 되돌리지 않는다. down -v, DB 초기화, 기존 사건·문서 삭제 금지.
.env 및 .env.local의 키를 출력하거나 자료에 포함하지 않는다. 키 복원·재발급은 이번 범위가 아니다.
네트워크/Device Guard 보안을 우회하지 않는다. 샌드박스 시스템 승인과 사용자가 준 업무 승인은 구분한다.
API 검증·정적 SVG 렌더·실제 브라우저 클릭을 서로 대체하지 않는다.
정지 확인은 정비 완료가 아니다. 기존 승인·반려 기록과 실패 기록을 보존한다.

## 4. 확정 사실

2026-09-23, uiux-20260923/의 원문을 기준으로 한다.

- 서비스: 대시보드 http://127.0.0.1:28180/ , FUXA http://127.0.0.1:27018/ . 배포 웹 index와 참조 자산이 로컬 빌드 해시와 일치한다(deployed-web-readback.json).
- 백엔드 151 passed / 1 skipped, 프런트 11 passed, Vite build 성공. skip은 root 권한에서 쓰기 거부 재현이 불가능한 기존 검사다(backend-tests.xml, frontend-tests.txt).
- 추가 검토에서 사건 목록이 비어질 때 남는 로딩 표시를 수정했다. 조회 실패와 분석 기록 없음도 구분했다. 목록 제거 중 지연 응답 무시와 실패 후 정상 복구를 자동 검사했다.
- FUXA HMI 36개 바인딩 검증 및 저장 후 되읽기 일치, 기존 device 정의 보존(fuxa-deployment.json). fuxa-static-layout.png는 정적 SVG 검토용이며 버튼 HTML이나 실제 브라우저 실행 증거가 아니다.
- 가상 교반기 API 제어: 정지 seq1966, 원래 운전 복원 seq1967(fuxa-control-verification.json). 재부팅 후 실제 브라우저 정지·기동 클릭도 seq302/303으로 확인했다(browser-control.json).
- FUXA 단위 누락·과도한 소수 자릿수와 1280px 제어판 잘림을 수정했다. runtime 규격에 맞는 range.type=1/fractionDigits 및 layout.zoom=autoresize 사용. 실제 01/11 화면 캡처로 재검증했다. 390px HMI는 글자가 작아 휴대전화 조작 품질을 합격 처리하지 않는다.
- 실제 새 모델 실행 e2a61c64-ddf2-44bd-8628-b5d1683ce001: 세 도구 시작/반환, 31~37ms의 도구 소요시간 저장. needs_evidence로 종료, 설비 조치 없음(live-analysis-trace.json). 모델 전체 소요시간과 도구 소요시간은 다르다.
- Docker 재기동 후 Flink 작업 0개를 발견했다. 기존 submitter 재실행으로 SQL 3개+ONNX 1개 RUNNING 복구, 센서 12/12개 15초 이내 GOOD 확인(live-pipeline.json). 새 접수 사건도 확인했다.
- 원래 uv 캐시 188MiB는 UV_NO_CACHE=1 재빌드 후 존재하지 않는다. venv와 LibreOffice는 유지된다(backend-image-components*.txt).
- Docker 용량·메모리의 측정 범위와 배포 대안은 DEPLOYMENT-SIZE.md에 있다. 최신 숫자는 docker-storage.txt와 docker-runtime.txt이며 변경 전 숫자와 혼합하지 않는다.
- 참고 레포 HEAD 및 ZIP 적용 범위는 PLAN.md에 있다. 공개 DeepAgents API 404를 최신 소스 확인 성공으로 표시하지 않는다.

## 5. 폐기된 판단

컨테이너 Up만으로 분석 파이프라인 정상이라고 판단하지 않는다. 실제로 Flink 작업이 0개였다.
빌드 캐시 12.18GB 표시는 그만큼 회수 가능하다는 뜻이 아니었다. 첫 측정 회수 가능은 0B였다.
현재 PC의 55.7GiB VHDX 파일 길이는 SCADA 단독 최소 디스크 요구가 아니다.
과거 HANDOFF의 서비스 중지와 이전 UI 캡처는 이번 배포의 현재 상태가 아니다.

## 6. 미결정

새 PC 최소 사양·lite+AI 완주·장시간 및 다중 사용자 부하는 미검증이다. 해당 환경에서 계측 후 배포 사양을 확정한다.
정적 HMI는 개선했지만 실제 렌더에서 작은 화면의 읽기·모든 제어 배치가 충분한지 브라우저로 판단해야 한다.

## 7. 외부 대기

agent-browser는 일반/사용자 권한 모두 Device Guard 차단이다. CUA inventory는 browsers=[]이며 iab/chrome 생성도 unavailable이다.
2026-09-23 재부팅 이후 agent-browser 실행 및 Chromium 화면 접근이 정상화되었다. 위 차단은 과거 상태이며 현재 캡처 차단이 아니다. 실제 1920×1080 SCADA 및 Vue 대시보드 PNG 4개를 저장했다(프로젝트 루트 화면캡처/README.md). 재부팅 뒤 Flink 0/4도 기존 submitter로 복구하여 UI 4/4를 확인했다. 좁은 화면·제어 버튼·AI 실행/실패 복구 검수는 아래 순서대로 남아 있다.

## 8. 자산 지도

- uiux-20260923/PLAN.md: 이번 요구, 참고 범위, 진행·인수 경계.
- uiux-20260923/DEPLOYMENT-SIZE.md: Docker 실측과 수신 PC 구성 판단.
- scripts/verify-uiux.ps1: 임시 소스/임시 DB 자동 검사. 운영 기록을 테스트 대상으로 사용하지 않는다.
- scripts/dashboard-diagnostics.py: 읽기 전용 상태와 응답시간 수집. 문서 원문과 비밀키를 출력하지 않는다.
- scripts/deploy-uiux.ps1: 처리 중 실행이 없을 때 knowledge/web 재빌드·배포, -WebOnly 지원. 이전 이미지 uiux-before-20260923 태그 보존.
- scripts/apply-fuxa-dashboard.py: 기존 runtime 프로젝트 백업 후 대상 HMI만 교체하고 되읽기 검증.
- uiux-20260923/baseline 및 fuxa-runtime-before-*.json: 변경 전 코드 일부와 실제 HMI 백업. 새 자료로 덮어쓰지 않는다.
- history/handoff-before-dashboard-20260923.md: 기존 시연·제출물·고지·이미지·인계 이력. 현재 서비스/UI 상태를 복원하는 근거로 사용하지 않는다.
- .env와 ai-layer/.env.local: 실행 설정. 읽은 값을 로그·산출물에 공개하지 않는다.

## 9. 다음 행동

1. 브라우저 연결 전에도 diagnostics.json을 현재 서비스와 대조할 수 있다. 서비스가 중지돼 있으면 기존 SCADA와 ai-layer/start-service.ps1을 사용한다. 재기동 후 Flink jobs/overview를 확인하고 작업 0개면 docker start flink-job-submitter로 복구한다. 일부 작업만 존재하면 원인 확인 없이 중복 제출하지 않는다.
2. 연결된 브라우저에서 28180 대시보드, 사건 선택·AI 도구 상세, 지식 구축, 27018 FUXA를 확인한다. 1920×1080 및 좁은 화면에서 잘림/겹침이 없고 빈 상태·실행 중·실패·재연결이 구분되어야 한다. 실제 캡처로 판정한다.
3. FUXA 실제 버튼→가상 상태 반영→원상 복원과 새로고침 후 실행 기록 보존을 확인한다. 앞 API 검증을 브라우저 검수로 계산하지 않는다.
4. 발견 문제만 수정하고 영향 검사를 수행한다. 현재 TODO의 [B] DoD와 대조해 미검증이 해소된 뒤에만 전체 목표와 날짜별 작업보고를 완료 처리한다.

## 10. 갱신 규칙

새 사실은 4절에 근거와 함께 반영하고 해결된 대기는 7절에서 제거한다. 이전 사실은 현재 사실과 혼합하지 않는다.
이 파일 하나를 재개 진입점으로 유지하며 과거 원문은 history에 보존한다.
