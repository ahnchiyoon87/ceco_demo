## 최신 제출본 — 2026-09-21 시연 검증 반영

전달 파일은 submission/CECO_패널신청자료_시연검증본.docx 및 같은 이름 PDF다. 신청서 2쪽 + 실제 실행 이미지 6장을 넣은 별첨 3쪽, 총 5쪽이다. 이전 동작과정포함 4쪽 파일은 보존된 이전판이다. 지식 후보 검토·게시 그래프, 실제 승인 사건의 저장된 AI 분석과 정지 결과, 별도 반려 사건, 기존 SCADA 재가동을 구분해 설명했다. 검토·결과 영역은 Word 그림 프레임에서 확대했고 원본 픽셀은 보존했다. Word PDF 출력·5쪽 텍스트 및 전체 첫 렌더를 확인했고 확대 변경 후 4·5쪽을 재검수했다. 증거는 submission-qa/verified-1~3.png, focused-4~5.png다. 날짜·담당자·서명은 제출자가 기입한다. 이 문서 전달 완료와 전체 서비스 목표 완료를 구분한다.

# CECO 시연 인수 현황

기준: 2026-09-21. 사용자 목표 전체를 유지한다. 이 표의 ‘검증’은 표시한 경로·조건에 한정하며 전체 목표 완료를 뜻하지 않는다. 과거 시행착오·실패 원문은 기존 기록에 보존한다.

**최신 전달본 변경:** 사용자 요청으로 동작 과정 4장(이상 사건 이력→설비·문서 연결→실제 AI 검토 대기→반려 결과 보존)을 2쪽 별첨에 구성했다. 현재 전달 대상은 `submission/CECO_패널신청자료_동작과정포함.docx`와 동일 이름 PDF, 총 4쪽이다. 기존 파일은 열려 있어 덮어쓰지 않았다. 동일 교반기 사건의 검증된 반려 경로이며, 1번 화면은 처리 후 이력 재조회임을 명시했다. 3·4번은 원본 캡처를 Word 그림 프레임에서 확대 표시했고 픽셀 내용은 변조하지 않았다. Word PDF 렌더 4쪽을 확인했다. 이전 3쪽 버전 전달 안내는 이 버전으로 대체한다.

**센서 조회 후속 검증:** 검증 전용 컨테이너에 pytest를 설치한 뒤 관측·제안 갱신 집중 테스트 7개가 통과했다. 전체 backend/tests 실행도 종료 코드 0으로 끝났다(일부 skip 표시, 최종 개수는 출력에서 확보하지 못해 기재하지 않음). 관측 도구 호출 순간 최근 30초를 다시 조회하며, 실패 시 시작 당시 값을 재사용하지 않는다. 운영 knowledge 배포가 완료됐고 컨테이너 healthy, OpenAPI·사건 조회 HTTP 200, 공정 available을 확인했다. 배포 소스 SHA256 D8C0E45E1BBC7F103CF2DEC8D3258EC6A90785CEC26931CD92AA971F84DC2136이 로컬과 일치한다. 재생성 도중 Docker 엔진 no route to host/500 및 일시적인 Backend unavailable이 관찰됐으며, 중복 실행 없이 원래 compose 작업이 종료 코드 0으로 완료됐다. 배포 후 실제 모델 시연은 아직 미검증이다.

**이전 전달 문서(최신본으로 대체됨):** `submission/CECO_패널신청자료.docx`와 `.pdf`. 신청서 2쪽 + 실제 운영·Asset 필터 그래프 캡처 별첨 1쪽, 총 3쪽이다. Word 내보내기 PDF를 Poppler로 렌더하고 3쪽 모두 직접 확인했다 (`submission-qa/final-1.png`~`final-3.png`). 표 너비와 그림 보존 문제를 수정한 최종본이다. 날짜·담당자·서명은 빈칸이다. 미완료인 승인·정지 전체 UI 리허설을 완료 성과로 표시하지 않았다. 과거 draft/HTML은 이 전달본을 대체하지 않는다.

**그래프 후속:** `manufacturingLayout.js`로 전체 35노드·41관계를 종류별 고정 열에 배치하고, 관계명은 선택 경로 또는 전체 표시 옵션으로 읽는다. 실제 M-101 클릭→상세→이웃 탐색, 문서 클릭→버전 1·source_path·source_sha256·본문 표시를 확인했다. 최신 캡처 `browser-qa/graph-lanes.png`. 전달한 PDF의 실제 캡처는 당시 Asset 필터 화면으로 유지했다.

사용자 우선 전달 요청 반영: `panel-assets/CECO-panel-review.html`에 신청서 원고와 실제 운영·Asset 필터 그래프 캡처, 설명용 구성도를 내장했다. 외부 파일 없이 열리는 검토본이다. 1440×1000 브라우저에서 본문과 이미지 렌더, 이미지 3개 로딩 및 가로 넘침 없음을 확인했다. Word 2쪽 초안은 그대로이며 실제 캡처 삽입본은 아직 아니다. 전체 목표 완료를 의미하지 않는다.

실제 UI 후속 증거: 사건 `1c1f0b3e-c8e7-48c5-9a00-e62d44a5a34c`에서 실제 루나 대응안 생성→빈 의견 차단→사유 입력→반려→브라우저 새로고침→동일 사건의 반려 사유·이력 보존을 확인했다. `browser-qa/AGENT-BROWSER-REVIEW.md`와 `ai-rejection-analysis.json` 참조. 점검 대기에서도 분석 버튼이 활성화되던 UI를 수정했고 실제 비활성화와 관련 SFC 검사 3개 통과를 확인했다. UI 승인·정지 완주는 여전히 남아 있다.

## 2026-09-21 실제 UI 승인·정지 검증

사건 `63887a98-1500-41b5-809d-e31af903b72e`에서 실제 Luna 대응안 생성→검토 의견 입력→승인→정지 확인→브라우저 새로고침→같은 사건 재선택까지 완료했다. 최신 GOOD 관측 약 2.9초, 전류 10.385425 A·진동 8.259866 mm/s를 근거로 정지를 제안했다. 결과는 점검 대기이며 정비 완료로 처리하지 않는다. 새로고침 후 승인 사유·정지 결과·분석 버튼 비활성화를 확인했다. `browser-qa/ui-stop-analysis.json`, `ui-stop-state.json`, 실제 시각 검수한 `ui-stop-persisted.png`가 증거다.

첫 분석 때 현재 이력이 비어 있어 점검 요청을 제안했고 사유를 남겨 반려했다. 마지막 수집 시각 07:10:22Z, Kafka raw 끝 오프셋 정체 및 MQTT bridge inflight 128/enqueued 238을 확인했다. telegraf-bridge만 재시작 후 최근 30초 GOOD 이력 56건 복구를 확인했다. 자동 복구 보장으로 해석하지 않는다. 시연 고장 주입은 해제했으며 교반기는 정지 상태로 유지한다. 강사 재가동 화면 동선 검증은 남아 있다.

## 지식 UI 실측 후속

실제 파일 선택으로 AR100-ASSET-CONTEXT.md를 업로드하고 4개 원본을 선택해 의미 후보 생성을 실행했다. 실행 8c8c129c-5abd-4576-bad7-2a02f7dad3a1은 관계 properties 배열 때문에 StructuredOutputValidationError로 거절됐으며 게시하지 않았다. 원인은 게시 검증의 단일 값 제한이 모델 JSON 스키마에는 누락된 계약 불일치였다. Node/Relationship의 JSON 스키마에 허용 타입을 명시하고 프롬프트에도 반영했다. 기존 런타임 거절 규칙은 유지한다. 의미 후보·실제 Neo4j 게시 관련 13개 테스트 통과 후 배포했고 운영 스키마 반영을 조회했다. 후속 실제 UI 실행 cc1c4064-c010-47cf-9e4a-6e0f71b81670을 시작했다. 후속 실행은 candidate로 완료됐다. 실제 UI에서 후보 검토→M-101 식별자 정리→확인 체크·검토 의견→Neo4j 게시까지 완료했다. 35노드·38관계 후보를 병합한 게시 그래프는 36노드·45관계이며 기존 Asset 2개를 유지했다. 사건 근거 재조회에서도 M-101과 문서 v1/v3/v2 연결을 확인했다. 증거는 browser-qa/ui-knowledge-build.json, ui-knowledge-publications.json, ui-postpublish-evidence.json과 직접 시각 확인한 ui-knowledge-published.png다. 기존 실패 실행도 ui-knowledge-failed-build.json에 보존했다. 검증용 knowledge/graph/work-db 컨테이너는 검사 종료 후 자원 확보를 위해 정지했으며 볼륨은 보존했다.

## 요구와 현재 증거

| 요구 | 판정과 실제 근거 | 남은 확인 |
|---|---|---|
| 기존 SCADA 기반 보존 | 착수 대비 85파일 해시 일치, 현재 공정 API available. `current-acceptance-live-check.json` | 전시 시작·종료 리허설에서 전체 서비스 상태 확인 |
| 최신 제조 1차 자료와 가상 시나리오 | `SOURCES.md`에 INOXPA 문서 개정/페이지, IEC·OPC 공식 공개 범위 기록. 교육용 AR-100 문서 3개 | 현장 실증·제조사 승인·인증으로 표시하지 않기 |
| 온톨로지·Neo4j 필수 | 현재 35노드·41관계, 정책 v3·대응 v2. `current-acceptance-live-check.json` | 실제 그래프 탐색의 시각 품질·조작 검수 |
| 자료에서 지식 구축 | 실제 루나 원본 조회·후보 생성·식별자 검토·게시: `live-luna-reviewed-publish-result.json`, `live-luna-published-retrieval.json` | UI 등록→실제 모델 후보→식별자 검토→게시 완료. 게시 후 사건 근거 조회 확인 |
| 문서 버전·출처 연결 | 원본/등록/게시 해시 일치, 적용 관계 이전 버전 출처 보존. `live-policy-v3-verification.json` | 화면의 문서/관계 원문 표시 확인 |
| 알람 수신·중복·사건 묶음 | Kafka/PG 연결, 원본과 검토 버전 분리. `live-review-version-approval.json`, `live-service-recovery.json` | 관람객 동선에서 사건 선택·원문 확인 |
| 실제 Luna·LiteLLM 사용 | 정상/부족/충돌/불량·오래된 관측에 실제 모델 도구 영수증. `live-policy-v3-stop-approval.json`, `live-stale-observation-v4-result.json` | 최근 출력 안내 변경 후 최종 화면 시연 |
| 승인·반려·조치·확인 | 실제 승인 후 stop_verified/awaiting_maintenance. 시험 후 고장 해제·운전 복구. `live-policy-v3-stop-verification.json` | 실제 UI 승인·반려·정지·새로고침 보존 확인. 강사 재가동 동선 남음 |
| 성공 경로 외 동작 | 문서 누락/충돌/지시 공격/관측 BAD·오래됨/인용·필드 오류/연결·timeout을 시험. `MODEL-DEMO-ACCEPTANCE.md` | 초기 실패와 보완 후 결과를 구분. 모든 공격·모든 모델 출력 보증 아님 |
| 영속성·실패 복구 | Neo4j·PG 장애, Kafka 오프셋, 웹/백엔드 재시작 기록. `live-service-recovery.json`, `live-web-service-verification.json` | PC 재부팅·새 PC 설치까지는 미검증 |
| Process GPT·Ontology 코드 재사용 | `REUSE.md`, 소스 UPSTREAM/해시 기록, 실제 HITL·모델·그래프 경로. 프런트 운영 의존성 25개 라이선스 원문 수집·실제 웹 제공 바이트 일치 (`frontend-notices-verification.json`). 백엔드 91개 중 86개 고지 원문 확보 (`BACKEND-NOTICES.md`) | 설치본·동일 버전 PyPI sdist에서 확보 못한 외부 패키지 4개 원문 및 최종 전달 범위 확인. 컨테이너 재배포 전체 점검 완료로 보지 않음 |
| 두 원본 제품을 별도 서비스로 제공하지 않음 | 단일 제조 웹 제품. 원본 stream 미등록, 독립 제조 API/검토 경로. `current-acceptance-live-check.json` | 최종 화면에서 원본 제품 이동/브랜딩 잔재 점검 |
| BPMN 선택 판단 | `BPMN-DECISION.md`: 현재 업무에는 별도 엔진/편집기 미도입, 영속 상태 흐름 사용 | 추가 구현 필요 없음 |
| CodeGraph·RTK 효율 활용 | 초기 가용성/코드 탐색 기록은 `REUSE.md`, `PLAN.md` | 제조 그래프 수치와 코드 인덱스 수치를 혼동하지 않기 |
| 독자적이고 가독성 높은 UI | 구현·빌드·정적 자산 서비스 확인. 최신/이전 검토 기록 구분 적용. 사건 전환 후 이전 요청이 새 사건 화면을 오염시키는 문제 수정, 실제 Vue SFC 지연 응답 시험 2개 통과 (`incident-request-scope-verification.json`) | **브라우저 렌더·조작·반응형·시각 품질 미검증** |
| 실제 시연 이미지 | Playwright Chromium으로 실제 운영 첫 화면 캡처 및 직접 시각 확인 (`browser-qa/operations-initial.png`, `initial-inspection.json`). 첫 로딩 pageerror 0건 | **그래프·검토/결과 화면 및 최종 전시용 캡처 필요**. 첫 화면만으로 전체 시연 완료를 주장하지 않음 |
| 패널 신청서 내용 | `PANEL-DRAFT.md`를 예시 항목에 맞춤. `build_panel_docx.py`로 편집 가능한 `panel-assets/CECO-panel-application-draft.docx` 생성, 구성도 삽입. LibreOffice 렌더 2쪽 모두 직접 시각 검수 (`panel-assets/render-qa-v3`) | 실제 화면 캡처 삽입·최종 제출 정보 확정 후 재렌더 필요. 현재 검토용 초안 |
| 읽기 좋은 시스템 설명 이미지 | `panel-assets/system-flow.png` 직접 렌더 검수, SVG 원본 동봉 | 실제 화면 사진을 대신하는 용도로 사용하지 않기 |
| 우수 수료생 수준·현업 기준 표현 | 기존 기반 + 제한된 교반기 업무, 원인 미확인·사람 검토·실패 처리 포함 | 강사 전시 리허설 전 난이도/설명 흐름 최종 점검. 실제 학생 제작으로 주장하지 않기 |

## 실제 실행 결과를 해석하는 범위

- 최근 전체 백엔드 검사는 138 passed / 1 skipped(21.09초)였다. 이후 필수 action 설명 변경의 관련 5검사를 통과했다. 이를 전체 139개 통과로 합산하지 않는다.
- pytest는 임시 업무 DB를 사용한다. 실제 모델 시연은 별도 검증 서비스 또는 운영 시뮬레이터에서 수행하며 기록을 구분한다.
- 구조화 응답 실패, 잘못된 인용, 순간 상태와 측정 이력 혼동 등은 실제 발견된 실패다. 최초 실행 성공률이 100%였다고 표현하지 않는다.
- 모델 출력 실패 시 승인·명령 없이 중단하며 거절 원문을 보존한다. 안전한 거절과 모델의 설명 품질은 별도로 평가한다.

## 현재 남은 핵심 작업

1. agent-browser 실제 조작으로 그래프 표시·검색·없는 검색 결과·미선택 실행 차단을 확인했다 (`browser-qa/AGENT-BROWSER-REVIEW.md`). 그래프 라벨 가독성은 아직 미달이다. 통합 UI 전체 조작·반응형·관계 상세 표시 검수를 이어간다.
2. 정상 시나리오와 실패 안내를 UI에서 리허설하고 최종 실제 캡처를 선정한다. 자동 생성한 구성도와 실제 화면 캡처를 명확히 구분한다.
3. 제공된 신청서 형식에 원고·실제 이미지·구성도를 배치하고 문서 렌더를 확인한다.
4. `EXHIBITION-RUNBOOK.md`의 시연 시작/종료·장애 복구 절차를 화면에서 완주한다. 현재 준비 상태 조회는 `runbook-readiness-check.json`으로 확인했으며, 전체 동선·PC 재부팅은 미검증이다. 전달 파일·제3자 고지·민감정보 범위를 최종 점검한다.

CUA는 apps/browsers 빈 목록이지만, 사용자 요청으로 Playwright 실행을 확인해 실제 Chromium 접속·첫 화면 캡처·직접 시각 확인에 성공했다. **브라우저 검수 불가라는 이전 차단 판단은 해소됐다.** 실행 도구는 `D:/work/study/.tools/ceco-browser/inspect.cjs`, Playwright는 같은 경로의 격리된 node_modules에 설치했다. 기존 앱 의존성은 바꾸지 않았다. 첫 화면 로딩 pageerror는 0건이며 전체 사용자 동선·반응형·그래프 검수는 이어서 수행해야 한다. 목표는 아직 완료되지 않았다.

## 운영 화면 가독성 후속

긴 분석문을 읽을 때 왼쪽이 비는 문제를 줄이도록 데스크톱 사건 목록을 화면 높이 안에서 고정했다. 현재 관측·대응안 검토·처리 이력 바로가기를 추가했고, 저장된 조치 결과는 대응안 본문 위에 표시한다. 원문과 승인 사유는 생략하지 않는다. 프로덕션 빌드·웹 재배포 후 실제 승인 사건에서 바로가기를 클릭해 정지 결과·선택 사건 동시 표시를 확인했다 (`browser-qa/ui-review-layout.png`). 390×844에서는 고정을 해제하며 app scrollWidth=390/viewport=390, 바로가기 3개 표시를 확인했다 (`ui-review-mobile.png`). 두 이미지를 직접 검수했고 브라우저 오류 출력은 없었다.

## 기존 SCADA 재가동 검증 및 런타임 바인딩 보정

FUXA 27018에서 표시값이 --.--이고 기동이 반영되지 않던 문제를 발견했다. SQLite readonly 로그는 FUXA 재시작 후 재관찰 대상이며 이것만을 원인으로 확정하지 않는다. 실제 태그 API는 AgitatorRun/IT_102에 값을 반환하지만 HMI의 AR100^~^AgitatorRun/AR100^~^IT_102는 null이었다. ai-layer/repair-fuxa-bindings.py로 유일한 태그 ID의 HMI variableId 30개만 보정했다. 적용 전 전체 프로젝트는 ai-layer/artifacts/fuxa-before-20260921T072954Z.json에 보존했다. 원본 SCADA 코드와 HMI 외 설정은 변경하지 않았다(조회 비교로 확인). 기본 실행은 미리보기이며 --apply로만 반영한다. 재실행 변경 0개, 모호한 중복 ID 보존을 확인했다.

기존 FUXA 화면에서 M-101 기동 버튼을 클릭한 뒤 agitator_run=true, interlock=false, active_faults={} 및 새 GOOD 관측(IT-102 6.27689A, VT-101 2.031618mm/s)을 확인했다. scada-restart-state.json과 직접 검수한 scada-after-restart.png 참조. 가상 공정 재가동이며 정비 완료 선언이나 실제 설비 조작 검증이 아니다.
