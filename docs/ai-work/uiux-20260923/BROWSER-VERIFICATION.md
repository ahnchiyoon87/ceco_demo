# 실제 브라우저 검수 — 2026-09-23

재부팅 후 agent-browser 0.38.1 Chromium 실행 정상. 이전 Device Guard 차단은 현재 차단이 아니다. 전용 세션 scada-verify-20260923으로 검수했다. 화면은 프로젝트 루트 `화면캡처/`에 저장했다.

| 항목 | 실제 관찰과 판정 | 근거 |
|---|---|---|
| 기본 화면 | Vue 대시보드·FUXA HMI·지식 스튜디오 렌더 확인 | 01~04, 12 PNG |
| Vue 좁은 화면 | 390×844, body/root 너비 모두 390. 메뉴·파이프라인 카드 줄바꿈, 가로 넘침 없음 | 05 PNG |
| FUXA 수치 | 단위 누락 및 소수 5자리 발견. 배포된 runtime getUnit/getDigits 규격을 확인하여 range.type=1, fractionDigits 적용. 실제 값에서 단위와 소수 2자리 확인 | 최신 01 PNG |
| FUXA 좁은 데스크톱 | 1280×800에서 우측 제어판 잘림 발견. HMI layout.zoom=autoresize 적용 후 전체 공정·제어·센서 표시 | 11 PNG |
| FUXA 휴대전화 | 390px에서는 전체 HMI가 축소되어 글자·버튼이 작다. 휴대전화 조작 품질 합격으로 판단하지 않음 | 08 PNG |
| 실제 제어 | 기존 운전·인터록 미발동 확인 후 브라우저 교반기 정지 클릭→seq302에서 정지→기동 클릭→seq303 복원. 가상 AR-100 한정 | browser-control.json, 07 PNG |
| AI 실행 | 브라우저 대응안 작성 클릭. 7a2a5455-36d2-44ef-92c4-a3667442fef2 분석 중→needs_evidence. 도구 3개, 29/27/32ms, 조회원·결과 표시. 설비 명령 없음 | browser-analysis-trace.json, 06/09 PNG |
| 새로고침 보존 | 페이지 재진입 후 동일 사건 재선택, 같은 run ID와 도구 실행 기록 표시 | 13 PNG |
| 통신 실패·재연결 | Vue에서 Chromium offline on → Failed to fetch 표시. offline off → 공정 상태 수신 중으로 자동 복구 | 10 PNG |
| 지식 분석 진행 | 원본 4개 선택 후 의미 관계 제안. 실행 도중 read_registered_source 4회와 read_extracted_structure 기록을 UI에서 확인 | 14 PNG |
| 지식 분석 실패 | 6498b20c-b24d-41b6-986c-ad06417ee87e가 ValidationError로 failed. 원본 조회 기록 유지, 재실행 버튼 복구, 그래프 미게시. 상세 원인 조사 필요 | browser-knowledge-build.json, 15 PNG |

FUXA 통신 후속 검수: 전용 `fuxa-connectivity` 브라우저에서 offline 15초 관찰은 경고 전이었다. 배포된 FUXA 번들의 경고 지연 35초를 확인하고 offline 45초로 다시 시험해 `SERVER CONNECTION FAILED!` 빨간 배너를 확인했다(16 PNG). online 복구 뒤 경고가 사라지고 온도 등 값 갱신이 재개됐다(17 PNG). 서버·설비 서비스는 중지하지 않았다. 브라우저-서버 연결 경고/복구 검증이며 현장 Modbus 단절 시험은 아니다. 단절 중 마지막 값과 조작 버튼이 남는 한계가 있어 HMI 안내를 수정했다. 승인 대기/반려의 브라우저 검사는 여전히 별도이며 앞 신규 모델 결과는 근거 보완 필요다.

이번 수치 포맷·레이아웃 변경은 생성기 실행, 36개 태그 연결 검사, HMI 백업·저장·되읽기, 실제 브라우저 재캡처로 검증했다. DB·기존 device 정의는 보존했다. 백엔드와 Vue 소스는 이 후속 검수에서 변경하지 않았다.

## 13:35 후속 검수

- 기존 사건 `63887a98-1500-41b5-809d-e31af903b72e`의 저장된 실제 모델 대응안을 브라우저에서 열었다. 승인된 정지 결과가 `점검 대기`, `정지 확인 · 정비 완료 아님`, 승인 의견과 함께 표시됐고 이전 반려 대응안을 펼칠 수 있었다(19 PNG). 이번에는 승인/반려 POST나 설비 명령을 실행하지 않았다. 새 검토 대기에서의 실제 버튼 동선 검증과는 구분한다.
- 사건 목록이 여러 날짜의 사건을 시각만으로 표시하는 문제를 발견했다. App.vue 사건·이력 시각과 ObservationComparison 측정 시각에 날짜를 추가했다. 프런트 11개 검사와 Vite 빌드 성공 후 WebOnly 배포·healthz 200, 실제 사건 목록 날짜 표시를 확인했다(20 PNG). 기존 DB 기록은 변경하지 않았다.

## 격리 화면 검수 — 승인·반려·실패

`ai-web/tests/review-browser.html`은 실제 IncidentReview/ExecutionTrace 컴포넌트를 렌더한다. fetch는 시험용 응답으로 대체하고 알 수 없는 요청은 실패시킨다. **실제 모델·설비·DB·승인 API 종단 시험이 아니다.** 기존 실제 DB 통합 검사와 운영 기록 화면 확인을 보완하는 브라우저 UI 검사다.

- 검토 의견이 비어 있으면 승인/반려 비활성. 의견 입력 후 실제 브라우저 클릭으로 각각 반려·점검 대기 결과와 의견 표시 확인(21/22 PNG).
- 각 요청 로그의 POST가 정확히 1개이며 decision·note가 일치함을 검사했다. 로그는 browser-fixture-reject/approve/ambiguous.json.
- 503 응답에서 완료로 표시하지 않고 의견을 보존했다. 오류 안내가 클릭 위치 위로 가려지는 문제를 발견해 실패 안내를 화면으로 이동하고 포커스를 주도록 수정했다. 실제 브라우저의 activeElement role=alert와 화면을 확인했다(23 PNG).
- 모델 연결 오류 상태에 실패 제목·오류·복구 안내가 표시되는 시험 화면을 남겼다(24 PNG).
- 변경 후 프런트 11개 검사·Vite 빌드 통과. 테스트 페이지는 Vite 개발 경로에만 있으며 배포 엔트리에 포함하지 않는다.

## 지식 검토 단계 및 Docker 복구 후 확인

- 운영에 저장된 실패 지식 실행을 다시 열어 실패·미게시 문구와 도구 기록을 확인했다(25 PNG). 과거 실패에 저장된 일반 ValidationError 문구는 소급 수정하지 않았다.
- 기존 실제 모델 생성 후보를 열고 검토 화면으로 진입했다. 35개 노드·38개 관계, 출처와 검토 확인·의견 입력 전 게시 비활성을 확인했다. 게시를 실행하거나 기존 그래프를 변경하지 않았다.
- 후보 검토 클릭 후 아래 영역으로 이동하지 않아 결과를 찾기 어려운 문제를 수정했다. 현재 단계 요약과 검토 영역 이동·포커스를 추가했다. 13:48 배포 후 브라우저에서 `03 사람 검토`와 이동된 후보 화면을 확인했다(26 PNG).
- 배포 중 Docker 내부 엔진 연결이 끊겨 정상 재시작을 시도했지만 종료 대기에 머물렀다. Docker 전용 WSL 종료와 확인된 Docker 프로세스 종료 후 Desktop을 다시 시작했다. DB 볼륨·파일을 삭제하지 않았다. 기존 서비스·healthz 200·FUXA 36개 연결 및 Flink 4개 RUNNING 복구를 확인했다. 최종 작업 상태는 flink-after-docker-recovery.json이다.

## 13:56 실제 알람 전달 복구

- Telegraf json_v2의 빈 object path가 반복 오류를 내던 문제를 명시적 timestamp/tag/field 파싱으로 수정했다.
- 설치된 FUXA MQTT 드라이버는 수신 토픽을 정확한 주소로 찾는다. 와일드카드 구독 메시지가 topicsMap과 일치하지 않아 화면 태그가 갱신되지 않았다.
- 기존 센서별 JSON 출력은 보존하고 화면용 scada/hmi/latest-alert를 추가했다. FUXA ActiveAlert 태그만 정확한 주소·raw 타입으로 변경했다. 백업·전체 프로젝트 되읽기 일치·Modbus/HMI 보존: fuxa-alert-deployment.json.
- 가상 공정에서 자연 발생한 ML_AUTOENCODER/WARNING 알람의 원본 JSON과 화면용 메시지를 동시에 수신해 센서·심각도 일치를 확인했다. 합성 메시지나 설비 명령을 보내지 않았다. 근거: live-alert-mqtt.json.
- 실제 브라우저에 UTC 시각·심각도·센서·유형이 표시되고 시각이 갱신됐다. 30 PNG를 직접 열어 1920px에서 잘림 없이 표시됨을 확인했다. 최근 수신 이벤트이며 현재 활성 목록이나 해제 판정은 아니다.
- 초기 문구를 ‘새 알람 수신 대기 · 정상 판정 아님’으로 바꾸고 생성·36개 연결 검사·백업·저장·되읽기를 통과했다.
- diagnostics.json: 센서 12/12 최근 15초 GOOD, Flink 4/4 RUNNING. completion-readback.json: 배포 웹 17개 파일 모두 로컬 빌드와 SHA256 일치. 프런트 11개 회귀 검사 재통과.
- 출력 형식은 [Telegraf 공식 template serializer 문서](https://docs.influxdata.com/telegraf/v1/data_formats/output/template/)와 설치된 1.33.3의 실제 메시지로 확인했다.

## 14:03 지식 생성 실제 재시도·진단 보강

- 같은 원본 4개·질문으로 브라우저에서 다시 제안했다. 실행 dcef57ae-70fd-4ec0-9874-d431d92db07b가 running→failed로 종료했다. 원본 4개·구조 조회 기록 보존, 현재 단계 실패 표시, 제안 버튼 재활성화를 실제 화면에서 확인했다(31/32 PNG, browser-knowledge-retry.json).
- 저장된 모델 출력과 해당 실행의 원본·구조를 읽기 전용으로 다시 검증해 원본 인용 불일치를 확인했다. 잘못된 관계를 게시하지 않은 정상적인 거부다. 모델이 올바른 후보를 생성했다고 주장하지 않는다.
- ValueError만 보이던 진단을 보강했다. 세 종류의 내부 고정 검증 사유만 노출하고, 그 밖의 오류 내용은 숨긴다. 원본 인용 불일치·비공개 오류 문자열 차단을 회귀 검사에 추가했다.
- 전체 backend 154 pass / 1 skip, frontend 11 pass, Vite 빌드 성공. 실행 중 작업 0을 확인하는 배포 스크립트로 반영했고 backend build.py 해시는 로컬·실행 파일 모두 8930eb3dd410580df32742bd51e9c461bf8bf2d12bf7ccfdba08119bf2d07da0이다. 기존 실패 기록은 소급 변경하지 않았다. 새 문구는 자동 검사와 배포 해시로 확인했으며 실제 모델로 같은 불일치를 다시 유발하지 않았다.
