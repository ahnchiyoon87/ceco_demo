# CECO 강사 시연 운영 절차

대상은 현재 준비된 Windows PC의 `lecture-iiot-scada`와 가상 반응기 AR-100이다. 실제 설비 조작 절차가 아니다. 기존 SCADA와 DB·키 설정은 준비된 상태를 전제로 한다. 새 PC 설치와 전시 하루 전체 운영은 아직 검증하지 않았다. 핵심 화면 동선은 아래 실행 기록으로 확인했다.

## 시연 시작 전

PowerShell의 실행 위치를 프로젝트 루트로 맞춘다. Docker Desktop이 실행 중인지 확인한다. 기존 SCADA를 준비한 원래 구성으로 먼저 실행하고 다음 명령으로 AI 계층을 시작한다. 일상적인 시작에는 재빌드하지 않는다.

```powershell
powershell -ExecutionPolicy Bypass -File ai-layer/start-service.ps1
```

명령 실패 시 반복 실행하기 전에 표시된 원인을 확인한다. `iiot` 네트워크가 없으면 기존 SCADA 시작 상태를 확인한다. DB 구성 오류는 `ai-layer/.env.local`의 필요한 설정을 확인하되 화면 공유나 로그에 키를 출력하지 않는다.

```powershell
docker compose --env-file ai-layer/.env.local -f ai-layer/compose.yml -f ai-layer/compose.scada.yml --profile knowledge ps
Invoke-RestMethod http://127.0.0.1:28180/api/operations/model-status
Invoke-RestMethod http://127.0.0.1:28180/api/operations/plant
```

`web`, `knowledge`, `work-db`, `graph`, `alarm-worker`가 실행 중이어야 한다. 상태 확인 URL은 다음과 같이 해석한다.

| 확인 대상 | 정상으로 확인할 내용 | 이 확인만으로 알 수 없는 것 |
|---|---|---|
| `/healthz` | HTTP 200, 웹 서버 응답 | DB·모델·공정 연결 |
| `/api/operations/incidents` | HTTP 200, 사건 조회 가능 | Kafka의 새 알람 유입·AI 성공 |
| `/api/operations/model-status` | `configured: true`, 의도한 모델 설정 | 실제 추론 성공. `configured_unverified`는 고장이 아니라 설정 확인 범위 표시 |
| `/api/operations/plant` | `status: available`, 의도한 site/device와 운전 상태 | 센서 이력의 최신성·품질, 정비 완료 |

실제 모델 준비는 사건 분석의 성공 기록과 근거를 통해 확인한다. 브라우저 주소는 `http://127.0.0.1:28180/`이며 개발용 28173과 구분한다.

## 관람객에게 보여줄 흐름

1. “가상 교반기에서 발생한 알람을 바탕으로 작업자의 자료 조회와 대응안 검토를 돕는 시연”이라고 설명한다. 실제 학생 제작·현장 도입·제조사 승인으로 소개하지 않는다.
2. 시작 상태의 사건·운전 상태를 확인한다. 강사가 가상 이상을 주입한다. 기존에 사용한 입력은 아래와 같다. 이 명령은 실제로 시뮬레이터 상태를 바꾸므로 시연 시작 시에만 실행한다.

   ```powershell
   Invoke-RestMethod -Method Post -Uri http://127.0.0.1:27080/fault -ContentType application/json -Body '{"scenario":"bearing_wear","duration_s":120}'
   ```

3. 새 알람과 사건을 확인하고, 발생 당시 추세·현재 관측·연결된 설비·문서를 살펴본다. 기존 사건과 묶일 수 있으므로 화면의 최신 발생 시각과 원본 알람을 확인한다.
4. 분석을 실행하고 AI가 사용한 문서, 관측 사실, 미확인 원인과 대응안을 검토한다. 분석 중 또는 `NeedsEvidence` 상태에서는 승인할 조치가 있다고 설명하지 않는다.
5. 관람객에게 승인 또는 반려 판단을 보여준다. 반려 이유는 기록한다. 승인하더라도 최신 관측·문서·대상 조건이 달라지면 거절될 수 있음을 설명한다. 고장 지속 시간이 끝났거나 근거가 오래됐으면 정지를 억지로 성사시키지 않는다.
6. 정지했으면 새 관측과 조치 결과를 확인한다. `stop_verified`와 `awaiting_maintenance`는 정지 확인 및 후속 점검 대기이며 원인 제거·정비 완료가 아니다.

이 순서는 API·모델 및 실제 브라우저의 분석·승인/반려·정지 확인·새로고침 보존·SCADA 재가동 기록에 근거한다(browser-qa/AGENT-BROWSER-REVIEW.md). 관람객 설명을 포함한 전체 시연 소요시간은 별도 미측정이다. `verify_live_action.py`는 LLM 없이 검증용 제안을 만드는 도구이므로 AI 시연을 대신하지 않는다.

## 실패했을 때

| 관찰한 문제 | 강사가 먼저 할 일 | 복구 후 확인 |
|---|---|---|
| 웹은 보이나 API 503 | 컨테이너 상태와 DB·knowledge 상태 확인 | 사건·검토 기록 재조회 |
| 모델 연결 실패·시간 초과 | 실패 기록을 열고 중계 설정·연결 확인 | 명령 미실행과 이전 기록 보존 확인 후 새 분석을 명시적으로 시작 |
| 문서 부족·충돌 | 누락 대상·문서 버전·출처 확인 | 자료를 검토·게시하고 다시 분석. 충돌을 임의로 정상 처리하지 않음 |
| BAD·오래된 센서 관측 | 수집 연결과 관측 시각·품질 확인 | 새 GOOD 관측을 확인. 오래된 값을 현재 정상으로 해석하지 않음 |
| 승인 요청 후 화면 응답 불명 | **다시 승인하지 말고** 사건·제안·조치 결과 조회 | 저장된 실행 상태와 현재 공정 확인 후 제공된 복구 흐름 사용 |
| 정지 결과 미확인·실행 중 중단 | 사건과 제안 ID를 보존하고 결과·현재 상태 확인 | 정지 명령을 자동 반복하지 않음. 미확인은 미해결로 유지 |

서비스 복구가 필요하면 원인을 해결한 후 `start-service.ps1`로 다시 시작한다. 데이터 볼륨을 지우는 `down -v`, DB 초기화, 기존 사건 삭제는 복구 방법으로 사용하지 않는다. 원인 확인 없는 전체 스택 재시작도 피한다.

## 다음 체험 준비와 하루 종료

먼저 진행 중인 분석·승인·조치가 없는지 확인하고, 결과가 불명확한 사건은 기록을 보존한다. 강사가 시뮬레이터 고장 주입을 해제한다.

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:27080/fault/clear
Invoke-RestMethod http://127.0.0.1:27080/state
```

`cleared: true`는 고장 주입 해제를 뜻하며 교반기 재가동을 뜻하지 않는다. 정지한 교반기는 강사가 기존 SCADA 조작으로 운전을 복구하고 `/state`의 `commands.agitator_run`, `interlock`, `active_faults`와 새로운 관측을 확인한다. 자동 AI 도구에 재가동을 추가하지 않는다. 재가동은 http://127.0.0.1:27018/ 의 운전원 제어에서 M-101 교반기 행의 기동 버튼을 누른다. 명령 직후 화면 클릭만으로 성공 판정하지 않고 /state의 새 seq와 agitator_run=true 및 새 센서 관측을 확인한다. 2026-09-21 실제 UI 클릭과 상태·관측 확인 완료. 화면 값이 --.--인데 태그 API에서 값이 조회되면 HMI 식별자 형식을 확인한다. 기존 프로비저닝이 예전 바인딩을 다시 넣은 경우 `python ai-layer/repair-fuxa-bindings.py`로 미리보기 후 `--apply`로 백업·보정하고 브라우저를 새로고침한다. 센서 수집 자체가 중단된 상황을 이 보정으로 처리하지 않는다.

같은 날 다음 체험이면 서비스를 유지한다. 하루 종료 시 필요한 사건·화면 기록을 저장하고, 진행 중인 조치가 없음을 확인한 뒤 AI 서비스만 중단한다.

```powershell
docker compose --env-file ai-layer/.env.local -f ai-layer/compose.yml -f ai-layer/compose.scada.yml --profile knowledge stop
```

위 명령은 기존 SCADA를 중단하지 않으며 DB 볼륨을 보존한다. 다음 시작에는 `start-service.ps1`을 사용한다. 기존 SCADA의 종료는 원래 운영 절차를 따른다. PC 재부팅 후 자동 복구와 전시 전체 시작·종료 완주는 아직 미검증이다.

## 검증 범위

2026-09-21 `runbook-readiness-check.json`: 현재 웹·사건 API 응답과 모델 설정·공정 상태를 조회했다. Compose에서 위 5개 AI 서비스의 실행을 확인했다. 실제 승인·정지·복원은 `live-policy-v3-stop-verification.json`, 장애 복구는 `live-service-recovery.json` 및 `live-web-service-verification.json`의 기존 검증 범위를 따른다. 이번 문서 작성 때문에 동일한 고장·모델·정지 시험을 반복하지 않았다.
