# 04 · AI 층: 그래프 DB · 온톨로지 · GraphRAG · 에이전트 · 평가 (조사 기준일 2026-09-29)

- 범위: 산업 IoT/SCADA 시제품의 AI 층. 고정 조건(재론하지 않음): 그래프 DB 필수, 원인분석 = 온톨로지 그래프 추론(증상 → 고장모드 → 원인 → 점검/관측·조치절차), 매뉴얼 검색 = 임베딩 + 그래프 연결, V1 에이전트(LiteLLM 프록시 + LangGraph + 가드레일) 유지 + 도구 추가, 새 고장유형은 코드 0줄(데이터/온톨로지만) 추가.
- 관문(①): 무료 · OSI 라이선스 · Docker 가능 · 12개월 내 EOL 아님. 하나라도 어긋나면 "① 관문 제외".
- 조사 방법: 웹 검색·공식 페이지·PyPI JSON API·Hugging Face API 조회. **실행·컨테이너 기동·LLM 호출은 하지 않았다** → 아래 모든 항목은 "문서 확인"이며 실측 아님.
- 표기: 날짜는 릴리스/업로드일. `[미확인]` = 이번 조사로 확정 못 함.

---

## 1. 그래프 DB

### 1-1. Neo4j 본체와 플러그인

| 후보 | 최신 버전(날짜) | 라이선스 | 이미지/설치 | EOL | 적합성 메모 | 분류 | 근거 URL |
|---|---|---|---|---|---|---|---|
| Neo4j 5.26 LTS Community (V1 현재) | 5.26 LTS (2024-12-06 출시, 패치 계속) | GPLv3 | `neo4j:5.26-community` | **2028-06-06** 지원 종료 | 12개월 관문 여유. `LIST<FLOAT>` 벡터 인덱스(HNSW) CE 사용 가능. Cypher 25·`SEARCH` 절·VECTOR 타입 등 2025.x 신기능 없음 | 직접 시험 대상 (기준선) | https://endoflife.date/neo4j · https://neo4j.com/developer/kb/neo4j-supported-versions/ |
| Neo4j 2026.x Community (캘린더 버전) | 2026.09.0 (2026-09-21) | GPLv3 | `neo4j:2026.09-community` [태그명 미확인] | 각 월간 릴리스는 **다음 릴리스가 나오면 지원 종료**(예: 2026.08 → 2026-09-21 종료). LTS 아님 | 최신 기능은 있으나 매달 따라 올려야 지원 유지. CE 벡터 제한: VECTOR 네이티브 타입(2025.10+), vector-3.0 프로바이더(2025.09+), 다중 레이블 필터 인덱스(2026.01+), HF 양자화(2026.07+)는 **Enterprise/Aura 전용**. CE는 단일 레이블·단일 속성 `LIST<FLOAT>` ≤ 2048차원 | 직접 시험 대상 (비교용; 운용 기준선은 5.26) | https://endoflife.date/neo4j · https://neo4j.com/docs/cypher-manual/current/indexes/semantic-indexes/vector-indexes/ · https://neo4j.com/blog/graph-database/community-edition/ |
| APOC Core | 2026.09.0 (5.26용 5.26.x 계열 병행) | Apache-2.0 | `NEO4J_PLUGINS='["apoc"]'` | 본체 버전에 연동 | 경로·JSON·배치 로드 유틸. 필수 아님, 로더 편의용 | 직접 시험 대상 | https://github.com/neo4j/apoc/releases/tag/2026.09.0 · https://neo4j.com/docs/apoc/current/installation/ |
| Graph Data Science (GDS) Community | 2026.09.0 (2026-09-21); 5.26용 2.x 계열(2.27.0, 2026-03-06) | 공개분(OpenGDS) GPLv3. 배포 바이너리는 공개+비공개 소스 혼합, CE는 무료 사용 | `NEO4J_PLUGINS='["graph-data-science"]'` | 본체 버전 연동 | CE 제한: 동시성 최대 4, 모델 카탈로그 3개. 원인분석 핵심은 Cypher 경로 탐색으로 충분 → GDS는 선택(PageRank 등 보조 순위) | 직접 시험 대상 (선택) | https://github.com/neo4j/graph-data-science/releases · https://github.com/neo4j/graph-data-science/blob/master/LICENSE.txt · https://neo4j.com/docs/graph-data-science/current/installation/System-requirements/ |
| neosemantics (n10s) | 2025.06.1 (2025-06-16) — **2026.x용 릴리스 없음** | Apache-2.0 | 플러그인 jar 수동 | 5.26용 5.26.0(2024-09) 존재. 2026.x 호환 [미확인] | RDF/OWL/SHACL 가져오기·내보내기·간단 추론. IOF 등 OWL 온톨로지를 그래프로 싣는 데 유용. Neo4j Labs(무보증) | 직접 시험 대상 (5.26 조합만) | https://github.com/neo4j-labs/neosemantics/releases · https://neo4j.com/labs/neosemantics/ |

### 1-2. 대안 (참고용 기록)

| 후보 | 최신 버전(날짜) | 라이선스 | 이미지/설치 | EOL | 적합성 메모 | 분류 | 근거 URL |
|---|---|---|---|---|---|---|---|
| Apache AGE (PostgreSQL 확장) | 1.6.0 (2026-01-21, PG17), PG18용 1.7.0 | Apache-2.0 | `apache/age` | 활성 | openCypher 부분 지원. pgvector와 한 DB 가능. 그래프 기능 폭은 Neo4j보다 좁음 | 참고(대안) | https://github.com/apache/age/releases · https://github.com/apache/age/discussions/2305 |
| ArcadeDB | 26.8.1 (2026-08-03) | Apache-2.0 | `arcadedata/arcadedb` | 활성 | 멀티모델(그래프·벡터·문서), OpenCypher·Gremlin·SQL | 참고(대안) | https://arcadedb.com/blog/arcadedb-26-8-1/ · https://hub.docker.com/r/arcadedata/arcadedb |
| JanusGraph | 1.1.0 (2024-11-09) | Apache-2.0 | `janusgraph/janusgraph` | 릴리스 간격 김 | Gremlin 전용, 백엔드(Cassandra 등) 별도. 시제품엔 과중 | 참고(대안) | https://github.com/JanusGraph/janusgraph/releases |
| NebulaGraph CE | 3.8.x [2026 최신판 미확인] | Apache-2.0 (CE) | `vesoft/nebula-*` | [미확인] | 분산형, nGQL. 시제품엔 과중 | 참고(대안) | https://docs.nebula-graph.io/3.8.0/ · https://github.com/vesoft-inc/nebula |
| Apache HugeGraph | [최신 버전 미확인] | Apache-2.0 | `hugegraph/hugegraph` | [미확인] | Gremlin, Apache TLP | 참고(대안) | https://github.com/apache/hugegraph/releases |
| Dgraph | v25 (Apache-2.0로 전체 전환) | Apache-2.0 | `dgraph/dgraph` | 2025-10 Istari Digital 인수 → 향후 [미확인] | GraphQL/DQL, Cypher 아님 | 참고(대안) | https://hypermode.com/blog/dgraph-v25-preview · https://www.prnewswire.com/news-releases/istari-digital-acquires-dgraph-to-strengthen-data-foundation-for-ai-and-engineering-302593246.html |
| TerminusDB | 12.0.7 (2026-08-10) | Apache-2.0 | `terminusdb/terminusdb-server` | 활성 | 문서+그래프, 버전관리형. 경로 추론 적합성 낮음 | 참고(대안) | https://en.wikipedia.org/wiki/TerminusDB |
| Oxigraph (RDF/SPARQL) | 0.5.11 | MIT / Apache-2.0 이중 | `ghcr.io/oxigraph/oxigraph` | 활성 | SPARQL 1.2. **OWL 추론 없음** | 참고(온톨로지 검증 보조) | https://docs.rs/crate/oxigraph/latest · https://github.com/oxigraph/oxigraph/releases |
| Apache Jena Fuseki | 6.2.0 (2026-07-27), Java 21/25 | Apache-2.0 | 공식 이미지 없음, `jena-fuseki-docker` 빌드 | 활성 | OWL/RDFS 규칙 추론 가능. 운용 DB가 아니라 온톨로지 정합성 검증용 | 참고(온톨로지 검증 보조) | https://whimsy.apache.org/board/minutes/Jena.html · https://jena.apache.org/documentation/fuseki2/ |
| Memgraph Community | — | **BSL 1.1** (OSI 아님) | `memgraph/memgraph` | — | — | ① 관문 제외 (라이선스) | https://arcadedb.com/blog/neo4j-alternatives-in-2026-a-fair-look-at-the-open-source-options/ · https://flur.ee/blog/neo4j-alternatives |
| FalkorDB | — | **SSPLv1** (OSI 아님) | `falkordb/falkordb` | — | — | ① 관문 제외 (라이선스) | https://docs.falkordb.com/References/license.html |
| Kuzu | 0.11.3 (최종, 2025-10-10) | MIT | 임베디드 | **2025-10-10 저장소 아카이브**(Apple 인수) | 유지보수 종료 | ① 관문 제외 (EOL/아카이브) | https://gdotv.com/blog/kuzu-legacy-embedded-graph-database-landscape/ |

---

## 2. 스키마 기반이 될 온톨로지·표준

| 후보 | 최신 버전(날짜) | 라이선스 | 이미지/설치 | EOL | 적합성 메모 (증상/고장모드/원인/조치 구조) | 분류 | 근거 URL |
|---|---|---|---|---|---|---|---|
| IOF Maintenance (iof-maint) | IOF 저장소 `maintenance/Maintenance` [Released] 성숙도; 세부 버전 [미확인] | MIT (저장소) | OWL 파일(n10s로 적재 가능) | 활성 | 20클래스·2관계, BFO/IOF-Core 정렬. 정비작업·고장·고장모드·작업지시 개념. FMEA·정비절차 도메인 온톨로지는 작업 중 | 직접 시험 대상 (상위 스키마 정렬용) | https://github.com/iofoundry/ontology/tree/master/maintenance · https://arxiv.org/abs/2404.05224 |
| UWA CII FMEA 온톨로지 | 논문 부속 아카이브 | MIT | TTL/RDF-XML + OWLReady2 적재 스크립트 | 논문 보관용(갱신 적음) | Component–Function–FailureMode–Effect–Cause–Mechanism, **Symptom 클래스**. 요구 체인과 가장 가까움. FMEA 스프레드시트 → 온톨로지 적재 스크립트 = "코드 0줄 추가" 패턴 참고 | 직접 시험 대상 (스키마 차용) | https://github.com/uwasystemhealth/Paper_Archive_CII_FMEA_Ontology |
| ISO 14224 (고장모드·원인·정비 분류) | ISO 14224:2016 | **유료 ISO 표준** (공개 온톨로지 파일 아님) | — | — | 설비분류·고장모드·고장메커니즘·원인 코드표의 표준 용어. 코드 체계만 참조, 원문 재배포 불가. COPI(OWL, ISO 14224 정렬 설계) 참고 가능 | 참고 (용어 기준; 파일 배포 불가) | https://github.com/INF-UFRGS-Ontologies/COPI |
| ISO 13374 / MIMOSA OSA-CBM | OSA-CBM 3.3.1 (2010-06-29) | MIMOSA License Agreement (OSI 아님, 무료 다운로드) | 사양 문서/UML | 사실상 갱신 정지 | 상태감시 6블록(데이터수집→처리→상태감지→건전성평가→예측→권고) 파이프라인 구분 틀. 증상→원인 온톨로지 자체는 아님 | 참고 (아키텍처 용어) | https://www.mimosa.org/mimosa-osa-cbm/ |
| SAREF4INMA (ETSI TS 103 410-5) | v1.1.2 | ETSI Software License [OSI 여부 미확인] | TTL | 활성 | 공장·설비·품목 추적성 중심. **고장/정비/원인 개념 없음** | 참고 (설비 계층 명칭만) | https://saref.etsi.org/saref4inma/v1.1.2/ |
| AAS(자산관리셸) IDTA 서브모델 템플릿 | 템플릿별 (Predictive Maintenance 1.0, Maintenance Instructions 1.0, Reliability 1.0.1, Service Request Notification 1.0.1 등) | CC-BY-4.0 | JSON/AASX, Eclipse BaSyx 서버 | 활성 | 설비 디지털트윈 표현·정비지시 구조. 증상→원인 추론 그래프는 아님. 설비 식별/정비절차 속성 이름 차용 가능 | 참고 (속성 명명) | https://github.com/admin-shell-io/submodel-templates · https://eclipse.dev/basyx/ |

결론: 추론 체인(Symptom → FailureMode → Cause → Check/Observation → Action)은 **UWA FMEA 온톨로지 구조 + IOF-Maint 상위 정렬 + ISO 14224 용어**로 잡는 것이 가장 근접. 다른 표준은 명칭 참고용.

---

## 3. GraphRAG / 하이브리드 검색

| 후보 | 최신 버전(날짜) | 라이선스 | 이미지/설치 | EOL | 적합성 메모 ("임베딩+그래프 연결", LLM 추출 비용) | 분류 | 근거 URL |
|---|---|---|---|---|---|---|---|
| neo4j-graphrag (python) | 1.21.0 (2026-09-23) | Apache-2.0 | pip | 활성(Neo4j 공식) | `VectorCypherRetriever`: 벡터로 청크 찾고 Cypher로 설비·고장모드 노드까지 확장 → **LLM 추출 없이** 결정적 연결 가능. KG 구축 파이프라인(LLM)은 쓰지 않아도 됨 | 직접 시험 대상 (1순위) | https://pypi.org/project/neo4j-graphrag/ |
| langchain-neo4j | 0.10.0 (2026-06-10) | MIT | pip | 활성 | Neo4jVector·GraphCypherQAChain. LangGraph 도구로 감싸기 쉬움. Text2Cypher는 가드레일 필수 | 직접 시험 대상 | https://pypi.org/pypi/langchain-neo4j/json |
| LlamaIndex PropertyGraphIndex (+graph-stores-neo4j) | core 0.14.25 (2026-09-21), neo4j store 0.8.0 (2026-08-31) | MIT | pip | 활성 | 추출기 기본값이 LLM(SchemaLLMPathExtractor). 비LLM 추출기(Implicit)만으론 이점 적음. V1이 LangGraph라 스택 중복 | 참고 | https://pypi.org/pypi/llama-index-core/json |
| Microsoft GraphRAG | 3.2.0 (2026-09-23) | MIT | pip | **유지보수 모드**(신기능 없음) | 전 문서 LLM 엔티티 추출·커뮤니티 요약 → 인덱싱 비용 큼(공식 경고). 매뉴얼 소량엔 과함 | 참고 (비용·방향 불일치) | https://pypi.org/project/graphrag/ |
| LightRAG (lightrag-hku) | 1.5.7 (2026-09-02) | MIT | pip / Docker 제공 | 활성 | Neo4j 저장 지원. **LLM 엔티티·관계 추출 필수** | 참고 (비용) | https://pypi.org/project/lightrag-hku/ |
| HippoRAG 2 | 2.0.0a4 (2025-06-24, 알파) | MIT | pip | 1년 넘게 PyPI 갱신 없음 | LLM OpenIE 추출 필수, 알파 | 참고 (성숙도·비용) | https://github.com/OSU-NLP-Group/HippoRAG |
| nano-graphrag / fast-graphrag | 0.0.8.2 (2024-10) / 0.0.5 (2025-04) | MIT / [미확인] | pip | 갱신 정체 | LLM 추출 기반 | 참고 | https://pypi.org/pypi/nano-graphrag/json |

### 3-1. 로컬 CPU 임베딩 (한국어 포함)

| 모델 | 크기(파라미터) | 라이선스 | 메모 | 분류 | 근거 URL |
|---|---|---|---|---|---|
| BAAI/bge-m3 | 약 568M (XLM-R large 기반) | MIT | 다국어·8192토큰·dense+sparse+multi-vector. 1024차원 → Neo4j CE 2048 한도 안 | 직접 시험 대상 (기준) | https://huggingface.co/BAAI/bge-m3 |
| nlpai-lab/KURE-v1 | 567.8M (bge-m3 미세조정) | MIT | 한국어 검색 특화 | 직접 시험 대상 | https://huggingface.co/nlpai-lab/KURE-v1 |
| dragonkue/BGE-m3-ko | 567.8M | Apache-2.0 | 한국어 미세조정 | 직접 시험 대상 | https://huggingface.co/dragonkue/BGE-m3-ko |
| nlpai-lab/KoE5 | 559.9M | MIT | multilingual-e5 한국어 미세조정 | 직접 시험 대상 | https://huggingface.co/nlpai-lab/KoE5 |
| intfloat/multilingual-e5-large / -small / -large-instruct | 559.9M / 117.7M / 559.9M | MIT | small은 CPU 경량 대안 | 직접 시험 대상 (small=저사양 대안) | https://huggingface.co/intfloat/multilingual-e5-small |
| Qwen/Qwen3-Embedding-0.6B | 595.8M | Apache-2.0 | 다국어, 지시문 입력 | 직접 시험 대상 | https://huggingface.co/Qwen/Qwen3-Embedding-0.6B |
| Snowflake/snowflake-arctic-embed-l-v2.0 | 567.8M | Apache-2.0 | 다국어 | 직접 시험 대상 | https://huggingface.co/Snowflake/snowflake-arctic-embed-l-v2.0 |
| paraphrase-multilingual-MiniLM-L12-v2 | 117.7M | Apache-2.0 | 가장 가벼움, 검색 품질 낮은 편 | 참고 (하한 기준선) | https://huggingface.co/sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2 |
| google/embeddinggemma-300m | 302.9M | **Gemma 이용약관** (OSI 아님) | — | ① 관문 제외 (라이선스) | https://huggingface.co/google/embeddinggemma-300m |
| jinaai/jina-embeddings-v3 | 572.3M | **CC-BY-NC-4.0** (비상업) | — | ① 관문 제외 (라이선스) | https://huggingface.co/jinaai/jina-embeddings-v3 |

실행기: sentence-transformers 6.1.0 (2026-09-18, Apache-2.0), FlagEmbedding 1.4.2 (2026-08-24, 라이선스 PyPI 표기 없음 [저장소 MIT로 알려짐, 미확인]).

### 3-2. 리랭커

| 모델 | 크기 | 라이선스 | 메모 | 분류 | 근거 URL |
|---|---|---|---|---|---|
| BAAI/bge-reranker-v2-m3 | 567.8M | Apache-2.0 | 다국어 cross-encoder, CPU 가능(지연 큼) | 직접 시험 대상 | https://huggingface.co/BAAI/bge-reranker-v2-m3 |
| dragonkue/bge-reranker-v2-m3-ko | 567.8M | Apache-2.0 | 한국어 미세조정 | 직접 시험 대상 | https://huggingface.co/dragonkue/bge-reranker-v2-m3-ko |
| Qwen/Qwen3-Reranker-0.6B | 595.8M | Apache-2.0 | LLM형 리랭커, CPU 부담 큼 | 직접 시험 대상 (2순위) | https://huggingface.co/Qwen/Qwen3-Reranker-0.6B |
| jina-reranker-v2-base-multilingual | 278.4M | **CC-BY-NC-4.0** | — | ① 관문 제외 (라이선스) | https://huggingface.co/jinaai/jina-reranker-v2-base-multilingual |

---

## 4. 에이전트 프레임워크 · MCP

| 후보 | 최신 버전(날짜) | 라이선스 | 이미지/설치 | EOL | 적합성 메모 | 분류 | 근거 URL |
|---|---|---|---|---|---|---|---|
| LangGraph | 1.2.12 (2026-09-21) | MIT | pip | 활성(1.x) | V1 유지. 도구 추가만: `diagnose(symptoms)`, `search_manual(q, equipment)`, `get_procedure(cause)` 등 **고정 Cypher 템플릿 도구** | 직접 시험 대상 | https://pypi.org/pypi/langgraph/json |
| LiteLLM | 1.103.0 (2026-09-27) | MIT (단, `enterprise/` 디렉터리는 별도 상용 라이선스) | `ghcr.io/berriai/litellm` | 활성 | V1 유지. 엔터프라이즈 기능 비활성 유지 | 직접 시험 대상 (기존) | https://pypi.org/pypi/litellm/json |
| langchain-mcp-adapters | 0.3.2 (2026-08-06) | MIT | pip | 활성 | MCP 서버 도구를 LangGraph 도구로 연결 | 직접 시험 대상 (MCP 채택 시) | https://pypi.org/pypi/langchain-mcp-adapters/json |
| neo4j/mcp (Neo4j 공식 MCP, Go) | v1.6.0 (2026-09-10) | **GPLv3** (NOTICE: Aura/상용 제품과 쓰면 상용 약관 적용) | Dockerfile 제공, 공식 이미지명 [미확인] | 활성 | read-cypher / write-cypher / get-schema / list-gds-procedures. 범용 Cypher 실행 → 가드레일상 **read 전용·전용 계정** 필수 | 직접 시험 대상 | https://github.com/neo4j/mcp/releases · https://github.com/neo4j/mcp |
| mcp-neo4j-cypher (Neo4j Labs) | 0.6.0 (2026-04-10) | MIT | 컨테이너 배포 안내 | Labs(SLA·하위호환 보증 없음) | 공식판 존재로 방향은 neo4j/mcp로 이동 | 참고 | https://github.com/neo4j-contrib/mcp-neo4j |
| mcp-neo4j-memory / data-modeling | 0.4.5 (2026-02-23) / 0.8.2 (2025-12-22) | MIT | pip/uvx | Labs | 본 과제 직접 관련 낮음 | 참고 | https://github.com/neo4j-contrib/mcp-neo4j |

온톨로지 도구(보조): rdflib 7.6.0 (BSD-3), pyshacl 0.40.1 (Apache-2.0) — 새 고장유형 데이터의 SHACL 형상 검증에 사용 가능. owlready2 0.51 (LGPL-3.0-or-later).

---

## 5. 원인분석 답변 평가 (순환 평가 회피)

| 원칙 | 방법 | 근거 URL |
|---|---|---|
| 정답은 그래프 밖에서 만든다 | 시뮬레이터에 **주입한 고장(원인)** 을 정답으로 기록. 그래프에서 역산한 정답으로 그래프 답을 채점하면 순환 | https://arxiv.org/html/2606.27154 (OpenRCA 2.0, 결함 주입 기반 PAVE 라벨) |
| 결과 + 과정 둘 다 채점 | ① 원인 top-1/top-k 정확도, 정확 집합 일치 ② 제시 경로의 모든 노드·엣지가 그래프에 실재하고 Symptom→FailureMode→Cause 순서인지(결정적 검사) ③ 조치절차 ID 일치 | https://arxiv.org/html/2606.27154 · https://github.com/microsoft/OpenRCA |
| 검색은 사람이 표시한 관련 절로 | 매뉴얼 질의별 관련 절 ID를 사전 라벨 → Recall@k·MRR·nDCG. 벡터 단독 vs 벡터+그래프 확장 비교(애블레이션) | https://arxiv.org/pdf/2603.00468 (Cloud-OpsBench, 재현 가능 벤치 설계) |
| 테스트셋 고정·분리 | 온톨로지 작성자와 테스트 케이스 작성자 분리, 케이스 파일 해시 고정. 새 고장유형은 "데이터만 추가 → 기존 코드 그대로 → 새 주입 케이스 통과"를 회귀 시험으로 | — (설계 원칙) |
| LLM 판정은 자유서술에만, 교차 모델로 | 판정 LLM은 생성 모델과 다른 계열, 루브릭 고정, 일부를 사람 판정과 대조해 판정기 자체 검증. 자기선호 편향 보고 있음 | https://arxiv.org/abs/2410.21819 |
| 기준선 포함 | 규칙(그래프 경로만) · 벡터 RAG만 · 그래프+LLM 3조건을 같은 케이스로 비교 | https://arxiv.org/pdf/2607.28545v1 (ORCA-Bench) |

RAGAS 0.4.3 (Apache-2.0)는 LLM 판정 지표 중심 → 정답 기반 결정적 지표의 보조로만.

---

## 6. 분류 요약

- **직접 시험 대상**: Neo4j 5.26 LTS CE(기준), Neo4j 2026.09 CE(비교), APOC, GDS CE(선택), n10s(5.26 조합), IOF-Maint·UWA FMEA 온톨로지, neo4j-graphrag, langchain-neo4j, bge-m3·KURE-v1·BGE-m3-ko·KoE5·multilingual-e5(-small)·Qwen3-Embedding-0.6B·arctic-embed-l-v2.0, bge-reranker-v2-m3(-ko)·Qwen3-Reranker-0.6B, LangGraph·LiteLLM·langchain-mcp-adapters·neo4j/mcp.
- **① 관문 제외**: Memgraph(BSL 1.1), FalkorDB(SSPLv1), Kuzu(2025-10-10 아카이브), embeddinggemma(Gemma 약관), jina-embeddings-v3·jina-reranker-v2(CC-BY-NC).
- **참고(관문 통과하나 방향/비용/성숙도 불일치)**: Apache AGE, ArcadeDB, JanusGraph, NebulaGraph, HugeGraph, Dgraph, TerminusDB, Oxigraph, Jena Fuseki, MS GraphRAG(유지보수 모드·고비용), LightRAG·HippoRAG·nano/fast-graphrag(LLM 추출 필수), LlamaIndex PG, ISO 14224·OSA-CBM·SAREF4INMA·AAS(용어/명명 참고).

---

## 7. 권장 최소 설계 (1문단)

Neo4j **5.26 LTS Community**(2028-06 지원)를 그대로 쓰고, 스키마는 UWA FMEA 온톨로지 구조를 IOF-Maint에 정렬해 `(:Equipment)-[:HAS_FAILURE_MODE]->(:FailureMode)`, `(:Symptom)-[:INDICATES]->(:FailureMode)`, `(:FailureMode)-[:CAUSED_BY]->(:Cause)`, `(:Cause)-[:CHECKED_BY]->(:Check {observation, 기준값})`, `(:Cause)-[:REMEDIED_BY]->(:Procedure)`, `(:Procedure|:FailureMode)-[:DESCRIBED_IN]->(:ManualChunk {embedding})`로 둔다(용어는 ISO 14224 코드 참고). 새 고장유형은 FMEA형 CSV/TTL 한 벌을 추가 → 로더가 MERGE로 적재 → pyshacl로 형상 검증만 하면 되므로 코드 변경이 없다. 원인분석은 LLM이 아니라 **고정 Cypher**(관측 증상 집합과 겹치는 FailureMode를 증상 일치 수·가중치로 순위화 → Cause → Check/Procedure 경로 반환)가 계산하고, 매뉴얼 검색은 bge-m3(또는 KURE-v1) 임베딩을 CE 벡터 인덱스(`LIST<FLOAT>` 1024차원)에 두어 neo4j-graphrag `VectorCypherRetriever`로 청크 → 연결된 설비·고장모드·절차까지 확장한 뒤 bge-reranker-v2-m3로 재정렬한다. V1 LangGraph 에이전트에는 이 두 기능을 **이름 있는 읽기 전용 도구**(`diagnose`, `search_manual`, `get_procedure`)로 추가하고, 범용 Text2Cypher·MCP write는 쓰지 않거나 읽기 전용 계정으로 제한한다. 평가는 시뮬레이터 주입 고장을 정답으로 한 고정 케이스로 결정적 지표(top-k, 경로 실재성, Recall@k)를 먼저 재고 LLM 판정은 교차 모델 보조로만 쓴다.

---

## 8. 확인 못 한 것

- [미확인] Neo4j CE의 실제 벡터 프로바이더 명칭(5.26 CE에서 vector-2.0 사용 가능 여부). 문서 요약은 "CE는 vector-1.0 한정"으로 읽혔으나 원문 대조 필요 — 기능(`LIST<FLOAT>` HNSW 인덱스) 자체는 CE 지원 확인.
- [미확인] `neo4j:2026.09-community` 정확한 Docker 태그 문자열, neo4j/mcp 공식 컨테이너 이미지명.
- [미확인] n10s의 Neo4j 2026.x 호환(2025.06.1 이후 릴리스 없음). 2026.x로 올리면 n10s 대신 rdflib → Cypher 로더로 대체 필요할 수 있음.
- [미확인] GDS 5.26 호환 최신 2.x 버전 번호(2.27.0이 5.26용인지), GDS 배포판 이용약관 전문.
- [미확인] NebulaGraph·HugeGraph 2026 최신 버전, Dgraph 인수 후 로드맵.
- [미확인] IOF-Maint 정확한 릴리스 버전·파일 IRI, SAREF(ETSI Software License)의 OSI 해당 여부.
- [미확인] FlagEmbedding 라이선스(PyPI 표기 없음), fast-graphrag 라이선스.
- [미확인] 모든 임베딩·리랭커의 CPU 지연·한국어 매뉴얼 검색 품질 — 실측 없음, 직접 시험 필요.
- 이번 조사에서 컨테이너 기동·코드 실행·LLM 호출은 하지 않았다(지시에 따름).
