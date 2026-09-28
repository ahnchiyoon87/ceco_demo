# Process GPT 최신 변경 영향 검토

2026-09-21 요청: “최신꺼를 기준으로 다시 점검해서 반영할만한거 반영해봐”. 원본 메인 저장소는 최신이지만 하위 저장소 고정 커밋은 각 저장소 HEAD보다 이전이었다. 참조 clone에서 fetch만 수행했으며 checkout과 원본 이력은 변경하지 않았다.

## 기준 및 선택

DeepAgents 사용 기준 1bf79e04546efe9d660ac2da7af13453837ac4fa → 원격 HEAD 747c1f639e2f6dbd22c58bf4cbe86a8db885a34d. 4커밋, 전체 131파일 변경. 직접 가져온 네 모듈 중 checkpointer.py 동일, input_builder.py/hitl.py/mcp.py 변경(127줄 추가·12줄 삭제).

| 변경 | 현재 사용과 결정 |
|---|---|
| 실제 interrupt 대기 확인 후 Command(resume) 실행 | 반영. upstream build_graph_inputs 자체는 호출하지 않지만 operations/agent.py가 직접 Command(resume)를 사용하므로 같은 문제가 적용됨. PostgreSQL 체크포인트에 대기 interrupt와 실행·사건 ID, proposal_id가 존재하는 경우에만 재개. 없으면 실패 기록을 남기며 재조사/조치를 실행하지 않음 |
| 중첩 서브그래프 interrupt 탐색 및 payload 정규화 | 미도입. 현재 흐름은 루트 investigate/review/execute, 루트 결과의 interrupt만 사용. 구조가 바뀌면 다시 검토. 임의 정규화로 잘못된 승인 입력을 보충하지 않음 |
| slash command·agents 전달·폼 메시지 순서 | 미도입. 현재 build_user_message는 제조 사건 설명만 받고 해당 인자를 사용하지 않음 |
| MCP 서버별 tool_filters | 미도입. 제조 AI는 명시한 alarm/documents/observations 도구를 직접 제공하며 원본 범용 MCP 로더를 호출하지 않음 |
| 산출물 SDK 비공개 저장·링크 복구 및 Vue 변경 | 미도입. 독자 제조 UI는 Process GPT Vue 채팅 화면/산출물 SDK를 사용하지 않음. Vue 212커밋 차이를 제조 UI의 누락 기능 수로 해석하지 않음 |

원본 모듈 전체를 최신으로 교체하지 않고 필요한 안전 조건을 제조 경로에 이식했다. 따라서 전체 제품의 최신판 업그레이드로 표시하지 않는다. 회사 코드 재사용 승인과 제3자 고지는 기존 기록 유지. 의존성 변경 없음.

## 검증과 배포

- 실제 PostgreSQL 체크포인터/DB를 쓰는 대상 통합 검사 8 passed. 조사와 설비 어댑터는 대체하므로 이번 검사를 실제 LLM·설비 시험으로 표현하지 않음.
- 추가 3조건: 체크포인트 없음, 완료된 체크포인트, 다른 사건의 대기 체크포인트. 승인 요청 후 failed 저장, 조사/execute 진입 및 대응안 생성 없음.
- 기존 정상 approve/reject와 재시작 복구 검사 유지. 전체 백엔드 146 passed / 1 skipped, 21.74초. JUnit: upstream-review-tests.xml. root에서 디렉터리 쓰기 거부를 재현할 수 없는 1개 skip은 통과 아님.
- 운영 running/resuming 분석 0개 확인 후 knowledge 이미지 빌드·재생성. 운영 컨테이너 agent.py와 작업 파일 SHA256 일치: 4ee82fdda1c212576a6fac1402d8aeaae93e9aa0ef33e4d9812e2a9e8a945bea.
- 웹 경유 모델 상태 및 사건 API 모두 HTTP 200. 검증 전용 컨테이너 3개는 다시 정지, 볼륨 보존. 이 변경 후 실제 유료 모델 시연을 새로 반복하지는 않았으며 이전 시연 기록과 이번 재개 경계 회귀를 구분한다.
