# 시연 서비스 실행 구조

검증(2026-09-21): `start-service.ps1`로 실행 완료. 실제 HTTP로 정적 빌드/자산/API 제공, 없는 자산 404, knowledge 중단 시 정적 화면 파일 유지와 API JSON 503, knowledge 복구 후 API 재연결, web 재시작 후 게시 이력 조회를 확인했다. 증거는 `live-web-service-verification.json`이다. 브라우저 렌더·사용자 조작·PC 재부팅 시험은 미검증이다.

화면·API 접속 주소는 `http://127.0.0.1:28180/`이다. 기존 `28173`은 Vite 개발 서버이며 시연 서비스와 구분한다. Docker의 web 컨테이너가 빌드된 Vue 파일을 제공하고 `/api/`를 knowledge로 전달한다. Node/Vite 프로세스를 켜 둘 필요가 없다. 기존 SCADA 서비스와 데이터 볼륨은 유지한다.

기존 SCADA가 실행되고 `ai-layer/.env.local`의 DB·Influx 설정이 준비된 상태에서 프로젝트 루트에서 실행한다.

```powershell
powershell -ExecutionPolicy Bypass -File ai-layer/start-service.ps1 -Build
```

코드 변경이 없다면 `-Build`를 생략한다. 최초 DB 준비 도구는 `ai-layer/bootstrap.ps1`이며, Influx 연결값과 모델 연결값을 자동으로 만들어 주지는 않는다. 모델 미설정 상태에서도 근거 조회가 가능하지만 실제 AI 분석 완료를 주장할 수 없다. 전체 신규 PC 설치 절차는 별도 검증이 남아 있다.

web의 `/healthz`는 정적 웹 서버만 확인한다. API·DB·모델 성공을 뜻하지 않는다. 백엔드 연결이 끊기면 프록시는 JSON 오류와 HTTP 503을 반환한다. 승인 요청은 자동 재전송하지 않는다. 결과가 불명확하면 사건 기록을 조회해 실행 여부를 먼저 확인한다. Docker 서비스 주소를 다시 조회해 백엔드 컨테이너 교체에 대응한다. 설정 근거: [NGINX proxy 모듈 공식 문서](https://nginx.org/en/docs/http/ngx_http_proxy_module.html).

모든 AI 컨테이너는 `unless-stopped`로 재시작한다. Docker 자체가 시작돼 있어야 하며 명시적으로 중단한 서비스는 위 명령으로 다시 올린다. 중단/복구 시 `down -v`를 사용하지 않는다. 관리자 인증·외부 인터넷 공개·다중 사용자 운영까지 검증한 서비스는 아니며 현재 접속은 로컬 루프백에 제한한다.


## 회귀 검사와 서비스 데이터 분리

backend/tests의 세션 fixture는 설정된 PostgreSQL 서버에 ar100_pytest_<임의 ID> 임시 DB를 만들고 테스트 프로세스의 DB_NAME만 바꾼다. 종료 후 해당 DB만 제거한다. 서버 계정의 DB 생성 권한이 필요하며 실패 시 운영 DB로 대체하지 않는다. 재시작 복구 검사가 실행 중인 시연 사건 상태를 바꾸는 것을 방지한다. 실제 시연 API/모델 검증 기록과 pytest 데이터는 분리한다.

제조 AI 분석과 지식 구축은 HTTP 요청당 90초, 전송 재시도 0회를 SDK 생성 시 적용한다. 전체 워크플로 제한은 별도 240초다. 실제 무응답 HTTP 시험에서 약 90.7초 후 APITimeoutError와 무조치를 확인했다. 이는 브라우저 오류 화면 검증을 대신하지 않는다.
