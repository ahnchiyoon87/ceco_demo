# SCADA UI/UX 개선 — 로컬 검증 완료

## 사용자 요구와 인수조건

- FUXA 공정 감시·제어 화면 자체의 가독성, 계측 구분, 조작 피드백을 개선한다. 실제 태그 값과 제어 연결을 검증한다.
- AI 도구의 이름·입출력·실행 상태·시각·소요시간·실패를 실제 저장 이벤트로 표시한다. 임의 진행률이나 가짜 실행 애니메이션을 사용하지 않는다.
- 사건 전환, 통신 실패, 재연결, 승인 대기, 완료 후 갱신을 검증한다. 진행 중 실행을 과거 실행과 혼합하지 않는다.
- 요청 및 실행 식별자와 재현 가능한 테스트·상태 수집으로 디버깅 기반을 마련한다.
- 최신 Process-GPT 관련 소스와 제공 ZIP을 비교하고 적용 범위·미확인 범위를 기록한다.
- 다른 PC의 배포 구성을 개발 PC의 캐시·다른 프로젝트·검증 DB와 분리하고 실측 기반으로 자원 요구를 설명한다.

## 확인한 현재 상태

- 원본 저장소에 기존 수정과 미추적 AI 코드가 있다. 변경 전 대상 파일은 baseline/에 보존했다.
- 기존 SCADA 25개, AI 5개 컨테이너를 시작했다. DB 볼륨과 기존 기록을 보존한다.
- FUXA 태그 연결·수치 단위·소수 자릿수·1280px 맞춤을 수정하고 36개 연결·실제 버튼·화면을 검증했다.
- 분석 조회 실패 후 읽기 재시도와 사건 전환 시 오래된 응답 무시를 보강했다. 실제 도구 진행·실패/재연결·저장 기록 및 격리 승인/반려 UI 검증을 수행했다.
- 재부팅 후 agent-browser가 정상화돼 실제 캡처 01~26을 생성했다. 현재 결과는 BROWSER-VERIFICATION.md에 있다. 과거 Device Guard 차단을 현재 대기로 취급하지 않는다.

## 참고 근거

- 사용자 ZIP의 06_PRODUCT_RESEARCH: Process-GPT, DeepAgents, ReAct, Ontology Studio 등. 강의 시간/학생 요구는 이번 제품 개선의 요구로 적용하지 않는다.
- GitHub 공식 API 현재 HEAD: process-gpt 3335272b3f6978886e2b661b9977a0acfe7991e9; process-gpt-vue3 fb45ca6b5fa64dbd184e4ae46d256bf5df9fac84; ontology-studio 6a229be8dcce2aeb533ecdba360b5b4564ffb777.
- process-gpt-deepagents 공개 API는 404. ZIP의 fac07db900ca57ecda813c17d20e0b8eb33e6163은 dockerbuild artifact이며 전체 소스 또는 현재 HEAD 확인으로 간주하지 않는다.

## 자원 실측과 경계

2026-09-23 docker_data.vhdx 파일 길이 55.7 GiB. 이는 SCADA 전용 용량이나 신규 PC 최소 요구가 아니다. Docker 전체 이미지에는 capstone-student 6.65GB, supabase/postgres 3GB 등 다른 작업이 포함된다. build cache 12.18GB는 shared=true이므로 단순 합산 또는 전량 회수 주장 금지. 아직 이미지·캐시·볼륨을 삭제하지 않았다.

## 완료 판정과 범위

COMPLETION-AUDIT.md에서 원래 목표와 TODO B-4~6을 대조했다. 실제 알람 전달 오류·실패 진단까지 수정·배포하고 backend 154/1 skip, frontend 11, 실제 브라우저와 캡처를 확인했다. 새 PC·교육 Pilot·실물 설비·FUXA 휴대전화 조작 품질 등 미검증/미달 범위는 대조표에 남겼다.

## 사용자 후속 확정

대시보드를 첫 화면으로 한다. 공정도·실시간 계측·추세, 최근 사건과 AI 도구 진행을 함께 보고 상세 근거/대응안으로 이동한다. 강의 자료 제작과 별개인 제품 개선 범위를 유지한다.
