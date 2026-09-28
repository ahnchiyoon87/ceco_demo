> 2026-09-23 UI/UX 후속 변경: 대시보드·FUXA·실행 트레이스 배포 및 자동/API 검증은 uiux-20260923/과 HANDOFF.md를 따른다. 아래의 이전 UI 인수·캡처는 이번 변경의 브라우저 검증을 뜻하지 않는다. 실제 브라우저 검수는 연결 대기 중이며 전체 후속 요청은 미완료다.

# CECO 시연 인수 현황

기준: 2026-09-21. 강사 제작·우수 수료생 범위의 가상 제조 시연본이다. 실제 학생 제작, 현장 도입, 제조사 승인, 규격 인증을 주장하지 않는다. 검증 범위는 현재 PC의 로컬 서비스이며 요청한 로컬 교육·전시 시연본 범위의 구현·실행·제출물 인수를 완료했다.

## 지금 전달할 자료

- [제출용 PDF](submission/CECO_패널신청자료_시연검증본.pdf), [수정용 Word](submission/CECO_패널신청자료_시연검증본.docx): 신청서 2쪽 + 실제 화면 6장 별첨 3쪽. 총 5쪽 렌더 검수 완료. 날짜·담당자·서명은 제출자가 기입한다.
- 실제 화면 원본: browser-qa/. 문서의 검토·결과 그림은 원본 픽셀을 유지한 Word 프레임 확대다.
- 실행 안내: [EXHIBITION-RUNBOOK.md](EXHIBITION-RUNBOOK.md). 서비스 http://127.0.0.1:28180/, 기존 FUXA http://127.0.0.1:27018/.

## 요구별 인수 근거

| 요구 | 확인한 구현·실행 근거 | 범위 및 남은 항목 |
|---|---|---|
| 기존 SCADA 핵심 보존 | final-live-audit.json: 착수 파일 85개 해시 동일. 실제 공정·센서 수집·알람 연결 | FUXA 런타임 HMI variableId 30개 보정은 별도 기록. 코드 원본 불변과 런타임 불변을 혼동하지 않음 |
| 제조 현업 1차 자료 | SOURCES.md: 제조사 INOXPA BCI 개정 B/2024-08 p.15, IEC 62682 공식 공개 설명, OPC Machinery 공식 식별 모델 | 가상 AR-100 한계치·절차를 제조사 승인 규격으로 전용하지 않음 |
| 시나리오·문서 | knowledge-docs의 적용 맥락 v1·증거 정책 v3·교반기 대응 v2 | 실제 설비 정비 매뉴얼이 아닌 출처 기반 교육용 작성물 |
| 온톨로지·Neo4j | 실제 36노드·45관계. 센서·제어점·설비·문서·문서 절·알람 규칙, 출처/버전 연결 | final-live-audit.json, browser-qa/final-graph.png |
| 원본→AI 후보→검토→게시 | UI 업로드와 원본 4개 선택, 실제 Luna build cc1c4064, 식별자 정리·검토 의견·게시 | browser-qa/ui-knowledge-build.json, ui-knowledge-publications.json. 게시 후 사건 근거 문서 v1/v3/v2 재조회 확인 |
| 실제 LLM·RAG·업무 보조 | LiteLLM coding 경유 Luna, 알람·그래프 문서·관측 도구를 사용하고 정확한 문서 ID 인용 검증 | 현재 관측 도구는 호출 시점 재조회. 조회 실패 때 이전 값 재사용 없음 |
| 승인·반려·제한 조치·확인 | 실제 UI에서 정지 승인→새 상태 확인→점검 대기→새로고침 보존. 별도 반려 사유·무조치 보존 | browser-qa/ui-stop-analysis.json, ui-stop-state.json, ui-stop-persisted.png, ai-rejection-analysis.json |
| 재가동·다음 체험 | 기존 FUXA M-101 기동 버튼→agitator_run=true→새 GOOD 관측 | scada-restart-state.json, scada-after-restart.png. AI 자동 재가동 권한 없음 |
| 해피패스 외 검증 | 문서 없음·충돌·지시 공격·BAD/오래된 관측·인용 오류·timeout·실행 중단·DB 장애 기록 | MODEL-DEMO-ACCEPTANCE.md, live-service-recovery.json. 모든 공격/모델 출력 보장은 아님 |
| 이번 실제 실패와 복구 | 수집 중단 시 점검 제안·반려, MQTT bridge 단독 재시작 후 최신 관측 복구. 의미 후보 배열 오류는 게시 차단 후 스키마 보완 | 실패 출력 ui-knowledge-failed-build.json 보존. 관련 의미/게시 테스트 13개 통과. 재시도 성공만으로 처음 실패를 지우지 않음 |
| 독자적 통합 UI | 단일 운영·지식 화면, 그래프 탐색/검색/이웃, 사건 바로가기, 결과 우선 표시, 고정 사건 목록 | 1600×1000 및 390×844 실제 캡처 검수. ui-review-layout.png, ui-review-mobile.png. 작은 화면의 전체 그래프 라벨 추가 개선 여지 있음 |
| 기존 두 제품 통합 | REUSE.md 및 UPSTREAM: 코드 선별 재사용·리팩토링. 원본 stream/임의 쓰기 API 미등록 | 제품별 서비스·원본 UI로 이동하는 구성 아님. 회사 코드 재사용·브랜딩 변경 사용자 승인 |
| BPMN | BPMN-DECISION.md: 영속 HITL 상태 흐름 채택, 별도 BPMN 엔진·편집기 미도입 | 선택 이유와 향후 적용 조건 명시 |
| CodeGraph·RTK | REUSE.md·PLAN.md에 가용성/호출 탐색 기록 | 코드 그래프 수치를 제조 관계 수치로 표시하지 않음 |
| 캡처·패널 | 실제 실행 화면 6장, 설명용 구성도, 5쪽 DOCX/PDF 완성 | submission-qa/verified-1~2.png, graph-refined-3.png 및 focused-4~5.png 직접 검수 |
| 운영 준비 | start-service.ps1 실제 재실행 성공, AI 5개 서비스 healthy. 최신 센서 145건·교반기 운전 확인 | PC 재부팅·새 PC 설치·장시간 전시 부하 검증은 미수행 |

## 최종 인수 대조

1. 최종 회귀 검사 완료: 백엔드 143 passed / 1 skipped (26.50초), 프런트엔드 6 passed / 0 skipped. final-backend-tests.txt/.xml, final-frontend-tests.txt에 원문 보존. skip은 root에서 디렉터리 쓰기 거부 조건을 만들 수 없는 로컬 샌드박스 검사이며 통과로 계산하지 않는다. 검증 전용 컨테이너 3개는 검사 후 다시 정지했다.
2. 외부 패키지 4개의 정확한 버전 태그를 커밋으로 고정하여 고지 원문 5개를 확보하고 ZIP 체크섬을 검증했다(BACKEND-NOTICES.md, backend-tagged-notices.zip). 회사 코드 승인과 별도로 보존한다. 전달 범위는 제출 자료·캡처·프로젝트 소스이며 컨테이너 이미지 재배포 조건 충족을 주장하지 않는다.
3. 완료 대조: completion-artifact-audit.json에서 기준 85파일 불변, 실제 모델 후보 35노드/38관계와 사람 검토 후 게시 36노드/45관계, 실제 stop_verified/awaiting_maintenance, 최종 PDF 5쪽 및 해시를 재확인했다. 그래프 라벨 겹침을 수정·재배포하고 실제 이미지와 PDF 3쪽을 다시 검수했다(graph-label-refinement.png, submission-qa/graph-refined-3.png). 현업 근거·재사용·BPMN 결정·실행/실패 기록·UI·제출물을 위 표와 대조했다. 최종 인계는 HANDOFF.md, 일일 작업보고는 D:/work/작업보고/2026-09-21.md.

## 운영상 경계

- 사용자 신원 인증·다중 사용자 권한·실제 PLC 안전 인증은 제공하지 않는다. 로컬 교육용 시뮬레이터 시연이며 공개 산업 운영 서비스로 배포하지 않는다.
- stop_verified는 새 관측으로 정지 명령 반영을 확인한 것이며 정비 완료가 아니다.
- 의미 후보 게시 전에는 사람의 검토가 필요하다. 근거 부족·형식 오류·오래된 관측을 성공으로 대체하지 않는다.
- 모든 DB 볼륨과 실패 기록은 보존한다. 검증용 ar100-verification 컨테이너 5개(입력 fixture 포함)는 현재 정지 상태다.

## 이전 기록

기존 인수표 누적 원문은 [보존본](history/acceptance-before-consolidation-20260921.md)에 있다. 그 안의 미완료 문구는 당시 상태이며 현재 인수표보다 우선하지 않는다. 상세 UI 실행 기록은 browser-qa/AGENT-BROWSER-REVIEW.md를 따른다.

## 최신 Process GPT 검토 후속

2026-09-21: 실제 대기 체크포인트 없는 승인 재개를 차단하도록 보완·배포했다. 최신 백엔드 146 passed / 1 skipped. [변경 판단과 실행 범위](UPSTREAM-REVIEW-20260921.md), upstream-review-tests.xml 참조. 기존 143개 기록은 이전 버전 결과로 보존한다.
