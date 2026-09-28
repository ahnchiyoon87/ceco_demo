# CECO SCADA·AI UI 요구별 검증 대조

2026-09-23. 교육용 Pilot 제작은 별도 인계 범위다. 제품 UI 목표를 그 과제로 대체하지 않는다.

| 요구 | 구현과 직접 근거 | 판정 / 범위 |
|---|---|---|
| SCADA 자체 UI 개선, 대시보드 첫 화면 | FUXA 공정·제어·계측·설정·최근 알람 구역, Vue 실시간 공정·추세·사건·AI 진행. 27/30 PNG | 데스크톱 확인. FUXA 1280은 11 PNG. 390px FUXA 조작 품질 미달 |
| 실제 값·도구·단계·실패·결과 표시 | browser-analysis-trace.json 실제 모델 실행과 3개 도구, 06/09/13 PNG 실행·결과·재조회. browser-knowledge-build.json 원본 조회와 실패 | 실제 데이터/모델 실행 확인. 근거 부족을 성공·조치로 표시하지 않음 |
| TODO B-4 지식 현재 단계 | KnowledgeReview 단계 요약, 후보 검토 이동·포커스, 26/29 PNG. 출처 확인·검토 의견 없이 게시 비활성 | 원본/후보/사람 검토 구분 확인. 이번 UI 검수에서 그래프 게시 실행 안 함 |
| TODO B-5 설비·단위·알람·통신 | 36개 바인딩, 단위·소수 정정, 실제 MQTT 알람→FUXA 갱신, 16/17/30 PNG | 최근 이벤트 심각도 표시. 서버 단절 배너는 35초 지연, 마지막 값 유지 안내. 현장 Modbus 단절 별도 |
| TODO B-6 빈 상태·처리·실패·재시도·제어 보존 | 03/06/10/14/15/16/17/25 PNG, browser-control.json 가상 교반기 정지·복원, 격리 승인/반려/503 검수 21~24 | 실제 조회 재연결 확인. 지식 생성 실제 재시도 후 실패·버튼 복구·도구 기록 보존 확인(31/32 PNG). 원본 인용 불일치로 게시 차단 |
| 디버깅 기반·발견 버그 보강 | 요청/실행 ID와 도구 추적, dashboard-diagnostics.py, verify-uiux.ps1, validation diagnostics, 알람 파서·토픽 매핑 수정 | 진단·재현 경로 확보. 이전 사건 응답 간섭·로딩 잔류·오류 포커스·날짜·후보 이동 수정 |
| 영향 자동 테스트·실제 브라우저 | backend-tests.xml 154 pass/1 skip, frontend 11 pass, BROWSER-VERIFICATION.md, completion-readback.json 17개 배포 파일 일치 | root 권한상 파일 쓰기 거부 검사 1개 skip. UI 시험 응답을 실제 조치 검증으로 합산하지 않음 |
| ZIP·관련 upstream 확인 | PLAN.md ZIP 내부 소스·선정표, Process-GPT/Vue/Ontology 공식 HEAD와 실제 참고 복사본 | 검토한 범위에서 실행 기록·후보 검토 UX에 반영. private DeepAgents API 404, 전체 최신 소스 확인 아님 |
| WIP·DB 보존, 자율 Docker 기동 | 기존 WIP 유지, 별도 테스트 DB, FUXA 수정 전 백업 및 되읽기, 배포 중 실행 사전 검사 | down -v/DB 초기화 안 함. diagnostics.json 센서 12/12·Flink 4/4 |
| 화면 캡처와 용량 설명 | 화면캡처/README.md 실제 크기·시험 범위, DEPLOYMENT-SIZE.md | 개발 PC VHDX 55.7GiB를 타 PC 최소 사양으로 요구하지 않음. lite+AI·새 PC·다중 사용자 부하 미검증 |

판정: 요청한 CECO 로컬 UI 개선·영향 검사·실제 브라우저 검수·캡처·인계 범위 완료. 새 지식 후보의 정확성/게시 성공, 별도 교육 Pilot, 새 PC 배포, 실제 공장 및 다중 사용자 운영은 검증 완료로 주장하지 않는다. 최신 진단 변경은 실제 재시도 기록의 모델 출력을 저장 원본과 다시 검증해 원본 인용 불일치임을 확인한 뒤, 안전한 고정 오류 문구만 공개하도록 보강했다. 비공개 오류 문자열 차단을 포함한 회귀 검사를 통과했고 배포 해시가 일치한다. 과거 실패 기록은 소급 변경하지 않았다.
