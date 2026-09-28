# 백엔드 고지 수집 범위

2026-09-21 현재 실행 중인 `ar100-ai-knowledge-1`의 Python 배포 패키지 91개를 조사했다. `backend-python-notices.zip`에는 86개 패키지의 설치된 라이선스·NOTICE·COPYRIGHT 원문과 파일별 SHA256, 버전 목록을 보존했다. PDFium의 별도 LICENSES 및 BUILD_LICENSES 디렉터리에 들어 있는 하위 의존성 고지도 포함한다. 수집 파일의 체크섬은 압축 파일을 다시 열어 검증했다.

수집 도구는 `ai-layer/collect_backend_notices.py`다. 패키지 메타데이터·고지 파일만 읽으며 환경 변수·키·DB·업로드 문서를 포함하지 않는다. 회사 소유 원본 코드는 별도 `UPSTREAM.md`와 사용자 승인 기록을 따른다.

## 설치본에 없었던 원문 보완

설치 배포 파일에 고지가 없었던 항목은 다음과 같다. 2026-09-21 정확한 upstream 버전 태그를 커밋으로 고정하여 추가 확보했다.

| 패키지 | 설치 버전 | 메타데이터 선언 | 상태 |
|---|---|---|---|
| deepagents | 0.5.3 | MIT | 정확한 버전 태그의 원문 확보 |
| langchain-core | 1.2.30 | MIT | 정확한 버전 태그의 원문 확보 |
| langsmith | 0.7.32 | MIT | 정확한 버전 태그의 원문 확보 |
| sqlite-vec | 0.1.9 | MIT License, Apache License, Version 2.0 | 정확한 버전 태그의 원문 확보 |
| ontology-studio-backend | 0.1.0 | 미선언 | 사용자 회사 코드 재사용 승인 및 UPSTREAM 기록 적용 |

위 외부 패키지 중 deepagents·langchain-core·langsmith는 정확한 설치 버전의 sdist를 내려받고 SHA256을 확인했으나 수집 대상 이름의 고지 파일을 발견하지 못했다. sqlite-vec는 해당 버전 PyPI JSON에 sdist 항목이 없었다. 다른 버전 원문으로 임의 대체하지 않았다. 조회 결과는 `backend-source-notices.zip`의 `source-inventory.json`에 남겼으며, 이 ZIP에는 확보한 추가 라이선스 원문이 없다. 도구: `ai-layer/collect_missing_source_notices.py`.

추가 수집본은 `backend-tagged-notices.zip`이다. 4개 패키지의 5개 원문(sqlite-vec는 MIT와 Apache 모두)을 보존했으며 `tagged-inventory.json`에 버전·태그·커밋·다운로드 URL·각 SHA256을 기록했다. 압축 파일을 다시 열어 모든 원문의 체크섬을 검증했다. 수집 도구: `ai-layer/collect_tagged_notices.py`. 기존 sdist 조사 ZIP은 당시 미확보 근거로 보존한다.

추가 ZIP SHA256: `0fa23381c1dfebae38e3ee65a3a51101f6d3255dadafc850753888b427f094d6`.

## 전달할 때

위 ZIP은 내부 수집 증거다. 현재 소스 전달과 컨테이너 이미지 재배포를 구분한다. 전체 이미지 재배포 시에는 Python 외 OS 패키지, Neo4j·PostgreSQL·nginx 등 다른 이미지의 고지도 별도 확인해야 한다. 이 파일은 전체 재배포 조건의 충족을 선언하지 않는다. 현재 전달물은 제출용 PDF/Word·실제 캡처와 로컬 프로젝트 소스이며 컨테이너 이미지 재배포 묶음은 만들지 않는다. Python 패키지 91개는 설치본 고지 86개 + 정확한 태그 원문 4개 + 회사 코드 승인 1개로 구분된다.
