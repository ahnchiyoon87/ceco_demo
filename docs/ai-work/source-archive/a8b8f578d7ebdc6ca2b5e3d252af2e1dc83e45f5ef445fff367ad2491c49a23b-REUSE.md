# 재사용 조사 및 통합 기록

## 사용자 권한 확인 — 2026-09-21

사용자가 두 제품은 본인 회사 코드이며 교육/전시용 수정·재사용·브랜딩 변경을 허용한다고 명시했다. 회사 소유 브랜딩의 유지 조건을 이번 작업의 제약으로 적용하지 않는다. 아래 표의 공개 조건과 확인 대기는 권한 확인 이전의 조사 기록이며 현재 보류 사항이 아니다. 제3자 라이브러리·번들 스킬의 조건은 별도로 유지한다. Ontology Studio backend와 의존성 정본을 ai-layer/knowledge에 가져왔으며 원본 파일별 해시를 ontology-import-sha256.json에 기록했다.

참조 정본: `D:/work/study/_references/manufacturing-ai`.

후속 연결: ontology/build.py는 원본 ONTOLOGY_BUILD_SYSTEM_PROMPT의 세 소스 패턴과 _init_model을 재사용하고 제조 질문 기반의 의미 후보 생성으로 좁혔다. 임의 실행/직접 적재 대신 선택 원본 읽기와 추출 구조 읽기만 제공하고, 노드·관계 인용을 검증한 뒤 사람 검토 화면으로 보낸다. Process GPT의 입력 조립·HITL·Postgres 연결 코드는 operations/agent.py의 실제 승인 흐름에서 사용한다. 외형만 바꾼 모의 화면이 아니라 DB와 실행 경로를 연결했으나, 실제 LLM 추론과 브라우저 완주 검증은 아직 남아 있다.

| 저장소 | 확인 revision | 관찰한 기능 | 조건/결정 |
|---|---|---|---|
| process-gpt | 3335272b3f6978886e2b661b9977a0acfe7991e9 | 서비스 조합·설치 구조 | 루트 MIT. 하위 독립 저장소에 자동 적용하지 않음 |
| process-gpt-vue3 | f8d6c45baad7078abfaac0d3f233fee6ae2b61ac | 업무 UI | Apache 2.0 + 자체 Commons Clause. 브랜드 표시 유지·상업 제공 제한 명시. 기존 UI 복제를 목표로 하지 않음 |
| process-gpt-deepagents | 1bf79e04546efe9d660ac2da7af13453837ac4fa | MCP 도구 로딩·HITL·Postgres checkpoint·Supabase 업무 저장 | 루트 라이선스 미발견. 하위 bundled skills는 별도 라이선스. 재사용 조건 확인 필요 |
| process-gpt-completion | 621db777c63a652382f9ab3ff5d5322d809a9802 | 업무 실행 엔진 | 의존성·독립 배포 가능 범위 조사 중 |
| process-gpt-bpmn-extractor | aee3efd61deb36317289a1021a8926489719a11b | 문서→작업·역할·분기→정규화→BPMN | 이름은 Neo4jClient지만 이 revision은 Apache AGE 구현. BPMN 채택 아직 미결정 |
| ontology-studio | 6a229be8dcce2aeb533ecdba360b5b4564ffb777 | 관계 구축·Neo4j 적재·검색 MCP·Vue/Cytoscape | 루트 LICENSE 및 package/pyproject 라이선스 선언 미발견. 별도 허락 여부 사용자 확인 중 |

## 확인된 기술 연결

- Ontology Studio `batch_ingest`: nodes의 `id/class/properties`, relationships의 `from_id/to_id/type/properties`. 설정 추출기는 이 입출력 형식을 맞췄으며 원본 함수 구현을 복사하지 않았다.
- 원본 batch ingestion은 노드별 예외를 모아 부분 성공할 수 있고, 문자열 2000자 초과분을 자른다. 통합 시 원문 보존·적재 원자성·관계 누락 검증을 따로 설계해야 한다.
- Process GPT deepagents `core/storage/checkpointer.py`: AsyncPostgresSaver 연결 실패 시 None으로 돌아간다. 제조 승인 경로는 영속성 실패 상태로 승인을 계속 받지 않도록 별도 검증해야 한다.
- Supabase는 단순 SQL DB 대신 업무·스토리지 API로 사용된다. 따라서 PostgreSQL 컨테이너 하나를 Supabase의 드롭인 대체로 주장하지 않는다.
- CodeGraph: ontology-studio 인덱스 99 files, 1,134 nodes, 2,240 edges. `query batch_ingest`로 정의·호출 import를 찾아 실제 파일을 확인했다. 이 숫자는 제조 온톨로지 노드 수가 아니다.

## 실행 증거

- Ontology Studio batch_ingest의 입력 구조를 유지하는 검토/원자적 게시 모듈 `ontology/review.py`를 추가했다. 원본 도구는 아직 공존하므로 전체 지식 구축 경로가 새 검토 절차를 강제한다고 주장하지 않는다. 최종 UI/에이전트 도구 라우팅에서 이 차이를 해결해야 한다.
- Neo4j 통합 검증 3개 통과: 변경된 검토 hash 거부, 긴 원문 보존·동일 게시 멱등성, 후반 쓰기 실패 시 앞선 노드·배치 기록까지 롤백.
- `build_knowledge_bundle.py`는 결정론적 설정/문서 준비 도구이며 LLM 추출 결과가 아니다. 모델 기반 추출은 여전히 연결 전이다.
- 제작자가 교육용 적용 범위와 관계를 검토한 묶음 35노드/41관계를 실제 게시. `knowledge-publish-result.json` 및 Neo4j의 M-101→AR100-MIXER-RESPONSE 질의 결과 확인. 교육용 초안이라는 문서 표시는 유지한다.

- Process GPT의 HITL, input_builder, checkpointer, MCP 로딩 모듈을 `backend/src/modules/process_runtime`에 원형으로 가져왔다. 전체 BPMN/멀티테넌트 서비스를 이미 연결했다고 주장하지 않는다.
- PostgreSQL 17 컨테이너를 별도 27532 포트·work-data 볼륨으로 구성. 이는 Supabase API 대체가 아니라 현재 가져온 Postgres 체크포인터와 신규 제조 업무 데이터의 저장소다.
- 실제 Postgres에서 연결·그래프를 재생성한 HITL 승인/반려/잘못된 응답 검증 3개 통과. 모델·설비 제어 없이 영속화 및 재개만 검증했다.
- Ontology Studio 기존 테스트 43 통과/1 건너뜀. root 실행 권한 관련 테스트의 상세 skip 사유는 후속 확인 대상.
- 신규 제조 사건 API는 원본 SCADA 알람 필드로 사건을 저장하고 동일 원문 재수신을 원자적으로 중복 제거한다. 상이한 관련 알람의 사건 결합, 실제 Kafka 구독, 분석·승인 API는 아직 미구현.

- `ai-layer/bootstrap.ps1`로 독립 Neo4j 기동. Desktop의 7474/7687과 분리된 27474/27687 사용.
- Docker healthcheck 통과 및 실제 `RETURN 1 AS connected` 결과 1 확인.
- `export_inventory.py` 실행: 21 candidate nodes, 20 relationships. 아직 그래프에 게시하거나 문서/AI 추출을 실행한 것은 아님.
- 해피패스 금지: DB 기동 성공은 지식 구축·승인·조치 흐름 완료의 증거가 아니다.
# 제조 앱의 원본 API 노출 범위

2026-09-21: Ontology Studio의 그래프 조회·문자열 검색·이웃 탐색·상태 조회를 명시적인 `read_router`로 재사용한다. 제조 호스트는 원본 직접 수정/전체 삭제/자연어 Cypher 실행 API와 원본 `/api/stream` 빌드 에이전트를 등록하지 않는다. 해당 원본 구현은 참조 코드로 보존한다. 실제 지식 변경은 등록 자료 → prepare/build 후보 → preview → publish 경로로 수행한다. 검색 클래스는 Cypher 매개변수로 전달하며, 그래프 조회/검색 실패는 빈 성공 대신 HTTP 503을 반환한다. HTTP 경계 테스트 18개와 재빌드한 실제 서버의 삭제 경로 404·기존 조회 200을 확인했다. 이는 사용자 인증이나 Neo4j 관리자 권한 통제의 검증을 뜻하지 않는다.

## 사용자 확정: 단일 제조 AI 제품

Ontology Studio와 Process GPT 자체를 각각 서비스로 올리는 형태는 금지한다. 참조 clone은 코드 분석용이다. 필요한 모듈을 선별·리팩토링해 우리 제조 AI 업무도우미 내부에 통합한다. 그래프 탐색·지식 구축·업무 검토는 하나의 독자적 UI/사용 흐름으로 제공하며 원본 제품 화면을 오가게 하지 않는다. 내부 DB/백엔드 컨테이너 분리는 별도 제품 제공을 뜻하지 않는다.
