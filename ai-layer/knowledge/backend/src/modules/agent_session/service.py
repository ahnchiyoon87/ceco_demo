"""Agent lifecycle and SSE streaming service."""

from __future__ import annotations

import asyncio
import json
import re
import threading
import time
import traceback
import uuid
from pathlib import Path
from typing import Any, Literal

from langchain_core.messages import AIMessage, AIMessageChunk, HumanMessage, ToolMessage

from ..files.service import ensure_workspace_dirs, list_output_filenames
from ..ontology.tools import (
    batch_ingest,
    entity_create,
    entity_search,
    graph_stats,
    neo4j_cypher,
    neo4j_cypher_readonly,
    relationship_create,
    schema_create_class,
    schema_create_relationship_type,
    schema_get,
    schema_group_create,
    schema_group_list,
    vector_search,
)
from ...shared.logging import SmartLogger, log_agent_event
from ...shared.kernel.model_profiles import (
    resolve_model_profile,
    should_use_openai_responses_api,
)
from ...shared.kernel.settings import get_settings
from .sandbox_tools import (
    ensure_sandbox_ready,
    execute,
    sandbox_ls,
    sandbox_read,
    sandbox_write,
)
from .session_store import (
    delete_session_messages as _db_delete_messages,
    ensure_session as _db_ensure_session,
    init_db as _db_init,
    load_build_context as _db_load_build_context,
    save_build_context as _db_save_build_context,
    touch_session as _db_touch_session,
)

AgentMode = Literal["build", "answer"]

_agents: dict[AgentMode, object] = {}
_sessions: dict[str, list] = {}

# --- SqliteSaver checkpointer (LangGraph native) ---
_DB_PATH = Path(__file__).resolve().parents[3] / "data" / "sessions.db"

def _get_checkpointer():
    """Return a shared SqliteSaver checkpointer backed by SQLite."""
    import sqlite3
    from langgraph.checkpoint.sqlite import SqliteSaver

    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
    conn.execute("PRAGMA journal_mode=WAL")
    return SqliteSaver(conn)

# --- History management constants ---
# Rough chars-to-tokens ratio for Korean text (conservative)
_CHARS_PER_TOKEN = 2.5
_MAX_HISTORY_TOKENS = 12000  # leave headroom for system prompt + new response
_TOOL_RESULT_TRUNCATE_CHARS = 2000  # max chars kept per tool result in history
_TOOL_RESULT_SUMMARY_SUFFIX = "\n... [결과가 잘렸습니다. 필요시 다시 조회하세요.]"

ONTOLOGY_BUILD_SYSTEM_PROMPT = r"""\
한국어로 응답하세요. 당신은 Ontology Studio 에이전트입니다.

## 역할
사용자의 인텐트와 골든 퀘스천을 기반으로 온톨로지를 설계하고,
업로드된 다양한 소스(PDF, Excel, Shapefile 등)에서 데이터를 추출하여
Neo4j 지식그래프를 구축합니다. 검증 후 부족하면 반복합니다.

## 3가지 인제스천 패턴 (소스별로 자동 판별)

**패턴 A — 문서 구조 → 노드** (보험약관, 계약서, 법률)
문서의 계층 구조(관-조-항-호, 장-절 등) 자체가 노드가 됩니다.
전략: 정규식 기반 구조 파싱, 계층(CONTAINS) + 상호참조(REFERENCES) 보존

**패턴 B — 내용 추출 → 엔티티 + 관계** (프로세스 정의, 기술문서)
문장 속에 여러 사실(엔티티, 관계)이 등장하여 의미를 추출해야 합니다.
전략: 문장/단락 단위 NLP식 엔티티·관계 추출

**패턴 C — 구조화 데이터 → 노드** (Excel 설비목록, Shapefile GIS, DB 덤프)
행/레코드가 노드, 컬럼/필드가 속성, ID 컬럼이 관계의 연결고리입니다.
전략: 컬럼/필드 직접 매핑, 물리적 ID·FK로 parent-child 및 관계 연결

하나의 프로젝트에서 여러 패턴이 혼합될 수 있습니다.

## 반복 워크플로우 (Phase 1 → 2 → 3, 검증 실패 시 반복)

### Phase 1: 스키마 설계 (Intent-Driven, Top-Down)
골든 퀘스천이 모든 것을 결정합니다.
1. 인텐트와 골든 퀘스천을 분석합니다.
2. 각 골든 퀘스천에 답하려면 어떤 클래스와 관계가 필요한지 도출합니다.
3. schema_create_class, schema_create_relationship_type으로 스키마를 생성합니다.
4. 각 질문별 예상 그래프 탐색 경로를 설계하고
   /workspace/output/_schema_design.json에 저장합니다:
   {"classes": [...], "relationships": [...],
    "question_paths": [{"question": "Q", "path": "A-[REL]->B", "required_classes": [...]}]}

### Phase 2: 소스 전략 수립 + 실행 (Data-Driven)
1. 업로드된 **모든 파일**을 탐색합니다 (ls → execute로 샘플 추출).
2. 각 파일별로 판단합니다:
   - 파일 타입과 내부 구조 (PDF 계층? Excel 컬럼? Shapefile 레이어?)
   - 어떤 패턴(A/B/C)이 적합한지
   - 어떤 스키마 클래스를 채울 수 있는지
   - 구체적 파싱 전략 (정규식 패턴, 컬럼 매핑, 추출 규칙)
3. 파일별 파서 스크립트를 동적 생성하고 실행합니다:
   - execute로 /workspace/output/_parser_{소스명}.py 작성
   - 실행하여 /workspace/output/_parsed_{소스명}.json 출력
   - 출력 포맷: {"nodes": [{"id","class","properties","parent_id"},...], "relationships": [{"from_id","to_id","type","properties"},...]}
4. batch_ingest 도구로 파싱 결과를 Neo4j에 일괄 적재합니다.

### Phase 3: 검증 + 검색 힌트 생성 (Question-Driven)
1. graph_stats 도구로 전체 그래프 상태를 확인합니다 (클래스별 노드 수, 관계 유형별 수).
2. 각 골든 퀘스천에 대해 **실제 Cypher 쿼리를 neo4j_cypher로 실행**하여 답변 가능 여부를 검증합니다.
3. 검증 결과를 판단합니다:
   - PASS: 질문에 답할 수 있는 노드와 관계가 충분히 존재
   - FAIL: 누락된 클래스, 관계, 또는 데이터를 식별
4. FAIL이 있으면:
   - 스키마 갭 → Phase 1로 돌아가 클래스/관계 추가
   - 데이터 갭 → Phase 2로 돌아가 추가 파싱 또는 파서 수정
   - 최대 3회 반복합니다.
5. **검색 힌트 파일 생성** (질의 응답 모드를 위한 피드백):
   현재 그래프의 스키마와 데이터를 분석하여 execute로 /workspace/output/_search_hints.json 저장:
   {"classes": ["클래스명",...],
    "searchable_properties": {"클래스명": ["title","content","name",...]},
    "sample_queries": [{"description": "설명", "cypher": "MATCH ..."}],
    "keyword_fields": ["title","content","name"]}
   이 파일은 질의 응답 에이전트가 최적 검색 전략을 자동으로 결정하는 데 사용됩니다.
6. 최종 리포트를 출력합니다:
   - 노드/관계 통계
   - 각 골든 퀘스천별 Cypher 쿼리와 답변 경로
   - 검증 결과 (PASS/FAIL)

## 스키마 그룹 관리
- 구축 시작 시 **반드시** schema_group_create(name)으로 스키마 그룹을 생성하세요.
  - 스키마 이름은 구축 의도를 반영 (예: "보험약관 스키마", "리스크절차 스키마")
- schema_create_class 호출 시 schema_name 파라미터로 그룹을 지정하세요.
- schema_create_relationship_type 호출 시에도 schema_name 파라미터를 전달하세요.
- batch_ingest 호출 시에도 schema_name 파라미터를 전달하세요.
- 동일 이름의 클래스가 다른 스키마에 이미 존재하면 사용자에게 병합 여부를 질문하세요.
- target_schema가 build_context에 지정된 경우:
  - 해당 스키마의 기존 클래스만 사용하여 엔티티를 생성하세요.
  - 새로운 클래스를 추가하지 마세요.

## 도구 사용 가이드
- schema_group_create(name, description): 스키마 그룹 생성 (구축 시작 시 필수)
- schema_group_list(): 전체 스키마 그룹 목록 조회
- schema_get(): 현재 온톨로지 스키마 전체 조회 (스키마 그룹 정보 포함)
- schema_create_class(name, description, properties, schema_name): 새 클래스 정의
- schema_create_relationship_type(name, from_class, to_class, description, properties, schema_name): 관계 유형 정의
- entity_search(class_name, search_criteria): 중복 확인을 위한 엔티티 검색
- entity_create(class_name, properties, match_keys): 엔티티 인스턴스 생성 (MERGE)
- relationship_create(from_entity_id, to_entity_id, relationship_type, properties): 관계 생성
- batch_ingest(nodes_json): 파싱 결과 파일 경로(예: "/workspace/output/_parsed_xxx.json")를 전달하면 노드+관계 일괄 생성. JSON 문자열을 직접 전달해도 됩니다. **컨텍스트 절약을 위해 파일 경로 전달을 권장합니다.**
- graph_stats(): 그래프 전체 통계 조회 (검증용)
- neo4j_cypher(query, params): Cypher 쿼리 직접 실행 (검증, 고급 조회)
- execute: Python/bash 코드 실행 (파일 탐색, 파서 스크립트 생성·실행)

## 소스 타입별 파싱 가이드
- PDF: pdfplumber. 먼저 5-10페이지 샘플로 구조 파악 후 전체 파싱
- Excel/XLSX: openpyxl. 헤더 먼저 읽기. 계층 데이터는 ID/Parent 컬럼으로 추적
- Shapefile/DBF: dbfread 또는 struct로 직접 파싱. 속성 테이블→노드, 토폴로지→관계
- Markdown/DOCX: 헤딩 기반 구조 파싱
- PPTX: python-pptx. 슬라이드별 내용 추출

## 파서 작성 필수 규칙 (매우 중요 — 반드시 준수)

### content 수집이 핵심 (가장 중요한 규칙)
**모든 노드에 content 필드가 반드시 채워져야 합니다.** content가 비어있으면 질의 응답 시 해당 노드의 정보를 활용할 수 없습니다.

구현 패턴 (2-pass 방식):
```
Pass 1: 전체 텍스트를 하나의 문자열로 수집 (모든 페이지 합치기)
Pass 2: 정규식으로 구조 단위를 분할하여 각 단위의 본문을 추출

구체적 코드 패턴:
  full_text = ''.join(page.extract_text() for page in pdf.pages)
  # 구조 헤딩 패턴으로 split
  parts = re.split(r'(제\d+조[^\n]*)', full_text)
  # parts = [앞부분, '제1조 목적', 본문1, '제2조 정의', 본문2, ...]
  # 짝수 인덱스 = 본문, 홀수 인덱스 = 헤딩
  for i in range(1, len(parts), 2):
      heading = parts[i]
      body = parts[i+1] if i+1 < len(parts) else ''
      content = (heading + ' ' + body).strip()[:2000]
      # 이 content를 노드에 저장
```

**금지 사항:**
- content를 빈 문자열("")로 생성한 후 "나중에 채우겠다"는 방식 금지
- 노드 생성 시점에 content를 확정하여 전달해야 함
- 하위 노드(항, 호 등)에도 해당 범위의 텍스트를 content로 저장

### 노드 속성 규칙 (매우 중요)
- **모든 노드에 반드시 `name` 속성 필수**: `name`은 그래프에서 노드를 표시하는 기본 레이블입니다.
  - `title`이 아닌 **`name`**을 사용하세요. `name`이 없으면 그래프에서 UUID가 표시됩니다.
  - 예: `{"name": "보험계약대출", "content": "..."}`
  - 예: `{"name": "제33조 보험계약대출", "number": 33, "content": "..."}`
- **제목에서 불필요한 메타정보 제거**: 줄 끝의 페이지 번호, 불필요한 공백
  - 정규식: `re.sub(r'\\s+\\d+\\s*$', '', name).strip()`
- **구조 번호가 있으면 number 속성으로 분리 저장**: `{"name": "보험계약대출", "number": 33}`

### 구조 파싱 원칙 (패턴 A)
- **2-pass 방식 필수**: 먼저 전체 텍스트를 합친 후, 정규식으로 구조 단위를 분할
- **목차 vs 본문 구분**: 목차 페이지(줄 끝에 숫자만)는 건너뛰고, 본문 페이지부터 파싱
  - 목차 판별법: 페이지 내 대부분의 줄이 `제N조 제목 숫자` 패턴이면 목차
- **표(Table) 데이터**: `page.extract_tables()`로 추출하고, 행을 별도 노드로 저장

### 데이터 품질 규칙
- **노드 ID는 의미 있게**: `{타입}_{번호}` 형태
- **관계 속성에 출처 정보 기록**: `{"source_page": 56}`
- **원문에 없는 개념은 노드로 만들지 않음**

### 파서 완성 후 자체 검증 (필수)
파서 실행 후 반드시 execute로 출력 JSON을 검증하세요:
```python
import json
data = json.load(open('/workspace/output/_parsed_xxx.json'))
nodes = data['nodes']
total = len(nodes)
has_content = sum(1 for n in nodes if n['properties'].get('content'))
print(f'Content coverage: {has_content}/{total} ({has_content*100//total}%)')
# content coverage가 80% 미만이면 파서를 수정하세요
```

## 핵심 규칙
- **골든 퀘스천이 모든 것을 결정** — 스키마, 파싱 전략, 검증 기준
- **모든 업로드 파일을 탐색한 후** 전략을 수립 (한 파일에 매몰되지 말 것)
- **검증 시 반드시 실제 Cypher 실행** (경로 설명만으로는 불충분)
- 파서 출력: 반드시 {"nodes": [...], "relationships": [...]} JSON
- 스키마 클래스명: 영문 PascalCase / 관계 유형명: 영문 UPPER_SNAKE_CASE
- content 필드: 2000자 이내로 자르기
- 파일: /workspace/uploads/ 읽기, /workspace/output/ 쓰기
- 각 단계 전에 한국어로 간단히 설명
- 대규모 문서는 페이지/행 범위를 나눠서 처리
- 사용자가 제공한 구축 의도(intent)와 Golden Question을 최우선 목표로 삼으세요
- 사용자가 이전 결과에 대해 틀렸다고 표시한 항목과 피드백을 받으면, 그 이유를 해결하도록 스키마와 추출 전략을 조정하세요

## 최종 응답 형식
- 사람이 읽는 한국어 요약을 먼저 작성하세요
- 마지막에는 아래 형식의 JSON 코드 블록을 반드시 포함하세요

```ontology_build_report
{
  "intent": "사용자 구축 의도",
  "summary": "이번 구축/개선으로 무엇을 맞췄는지 한 줄 요약",
  "next_action": "사용자에게 요청할 다음 검토 액션 또는 남은 한계",
  "golden_questions": [
    {
      "question": "Golden Question 원문",
      "answer": "현재 온톨로지가 제공하도록 만든 답변 또는 답변 초안",
      "status": "answerable | partially_answerable | not_yet_answerable",
      "confidence": "high | medium | low"
    }
  ]
}
```
"""

ONTOLOGY_ANSWER_SYSTEM_PROMPT = """\
한국어로 응답하세요. 당신은 Ontology Studio 질의 응답 에이전트입니다.

## 역할
이미 구축된 온톨로지와 지식그래프를 조회하여, 사용자의 질문에 정확하게 답변합니다.

## 핵심 원칙
- 이 모드는 조회 전용입니다. 스키마, 엔티티, 관계를 생성/수정/삭제하지 마세요.
- 답변 전에 반드시 그래프를 조회하세요.
- 온톨로지에 없는 내용은 추측하지 말고, 정보가 부족하다고 명확히 말하세요.

## 검색 전략 (컨텍스트 절약 — 최소 도구 호출)

### 1단계: 벡터 검색 (가장 먼저, 1회만)
vector_search('질문 핵심 키워드', 3)으로 유사한 노드를 검색합니다.
이것만으로 대부분의 질문에 답할 수 있습니다.

### 2단계: 보완 (벡터 결과가 부족할 때만)
neo4j_cypher_readonly로 CONTAINS 검색:
```cypher
MATCH (n:_Entity) WHERE n.title CONTAINS '키워드' OR n.content CONTAINS '키워드'
RETURN labels(n), n.number, n.title, substring(toString(n.content), 0, 300) LIMIT 3
```

### 중요 규칙
- **도구 호출은 최소화** — 2~3회 이내로 답변 완료
- schema_get/graph_stats는 꼭 필요할 때만 호출 (컨텍스트 소모가 큼)
- 답변에 **근거 노드 번호/이름을 명시**하세요
- content에서 관련 문구를 인용하세요
"""

_SENTINEL = object()
_NEO4J_TOOL_NAMES = {
    "schema_create_class",
    "schema_create_relationship_type",
    "schema_group_create",
    "entity_create",
    "entity_search",
    "relationship_create",
    "neo4j_cypher",
}

_BUILD_MODE_TOOLS = [
    neo4j_cypher,
    schema_create_class,
    schema_create_relationship_type,
    schema_get,
    schema_group_create,
    schema_group_list,
    entity_create,
    entity_search,
    relationship_create,
    batch_ingest,
    graph_stats,
    execute,
    sandbox_ls,
    sandbox_read,
    sandbox_write,
]

_ANSWER_MODE_TOOLS = [
    schema_get,
    entity_search,
    neo4j_cypher_readonly,
    graph_stats,
    vector_search,
    sandbox_read,
]

_BUILD_REPORT_PATTERN = re.compile(
    r"```ontology_build_report\s*(\{.*?\})\s*```",
    re.DOTALL,
)
_TEXT_CONTENT_BLOCK_TYPES = {"text", "output_text"}


def _parse_json_if_possible(value: str) -> Any | None:
    """Best-effort JSON parsing for tool outputs."""

    normalized = value.strip()
    if not normalized or normalized[0] not in "{[":
        return None
    try:
        return json.loads(normalized)
    except json.JSONDecodeError:
        return None


def _detect_tool_failure(content: str) -> str | None:
    """Infer likely tool failures from raw tool output."""

    parsed = _parse_json_if_possible(content)
    if isinstance(parsed, dict):
        error_value = parsed.get("error")
        if error_value:
            return _clean_text(error_value)
        exit_code = parsed.get("exit_code")
        if isinstance(exit_code, int) and exit_code != 0:
            return f"exit_code={exit_code}"
        status_value = _clean_text(parsed.get("status")).lower()
        if status_value in {"error", "failed", "failure", "timeout"}:
            return _clean_text(parsed.get("message")) or status_value

    exit_code_match = re.search(r"\bexit[_ ]code\b[^0-9-]*(-?\d+)", content, re.IGNORECASE)
    if exit_code_match:
        exit_code = int(exit_code_match.group(1))
        if exit_code != 0:
            return f"exit_code={exit_code}"

    lowered = content.lower()
    if "traceback" in lowered:
        return "traceback_detected"
    if "timed out" in lowered:
        return "timeout_detected"
    return None


def _summarize_tool_runs(tool_runs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate tool calls by tool name for end-of-run summaries."""

    aggregated: dict[str, dict[str, Any]] = {}
    for tool_run in tool_runs:
        tool_name = _clean_text(tool_run.get("name")) or "unknown"
        current = aggregated.setdefault(
            tool_name,
            {
                "name": tool_name,
                "count": 0,
                "failure_count": 0,
                "total_duration_ms": 0,
                "max_duration_ms": 0,
            },
        )
        current["count"] += 1
        if tool_run.get("failed"):
            current["failure_count"] += 1
        duration_ms = tool_run.get("duration_ms")
        if isinstance(duration_ms, int):
            current["total_duration_ms"] += duration_ms
            current["max_duration_ms"] = max(current["max_duration_ms"], duration_ms)

    summaries = []
    for item in aggregated.values():
        count = item["count"] or 1
        item["avg_duration_ms"] = int(item["total_duration_ms"] / count)
        summaries.append(item)
    summaries.sort(key=lambda item: item["name"])
    return summaries


def _clean_text(value: Any) -> str:
    """Normalize arbitrary values into stripped strings."""

    if value is None:
        return ""
    return str(value).strip()


def _parse_build_context(raw_context: str | None) -> dict[str, Any]:
    """Parse optional build context provided by the frontend."""

    default_context = {
        "intent": "",
        "golden_questions": [],
        "review_feedback": [],
    }
    if not raw_context:
        return default_context

    try:
        payload = json.loads(raw_context)
    except json.JSONDecodeError:
        return default_context

    golden_questions = [
        _clean_text(item)
        for item in payload.get("golden_questions", [])
        if _clean_text(item)
    ]
    review_feedback = []
    for item in payload.get("review_feedback", []):
        if not isinstance(item, dict):
            continue
        question = _clean_text(item.get("question"))
        if not question:
            continue
        review_feedback.append(
            {
                "question": question,
                "answer": _clean_text(item.get("answer")),
                "status": _clean_text(item.get("status")) or "answerable",
                "verdict": _clean_text(item.get("verdict")),
                "feedback": _clean_text(item.get("feedback")),
            }
        )

    return {
        "intent": _clean_text(payload.get("intent")),
        "golden_questions": golden_questions,
        "review_feedback": review_feedback,
    }


def _compose_build_prompt(prompt: str, build_context: dict[str, Any]) -> str:
    """Inject build intent, golden questions, and review feedback into the prompt."""

    sections = [f"[사용자 작업 요청]\n{prompt.strip()}"]

    if build_context["intent"]:
        sections.append(f"[구축 의도]\n{build_context['intent']}")

    if build_context["golden_questions"]:
        golden_question_lines = "\n".join(
            f"{index}. {question}"
            for index, question in enumerate(build_context["golden_questions"], start=1)
        )
        sections.append(
            "[Golden Question]\n"
            "아래 질문들에 답할 수 있는 온톨로지 스키마와 그래프를 구축하세요.\n"
            f"{golden_question_lines}"
        )

    if build_context["review_feedback"]:
        feedback_lines = []
        for index, item in enumerate(build_context["review_feedback"], start=1):
            feedback_lines.append(
                "\n".join(
                    [
                        f"{index}. 질문: {item['question']}",
                        f"   이전 판정: {item['verdict'] or '미지정'}",
                        f"   이전 상태: {item['status']}",
                        f"   기존 답변: {item['answer'] or '없음'}",
                        f"   사용자 피드백: {item['feedback'] or '없음'}",
                    ]
                )
            )
        sections.append(
            "[이전 결과 검토 피드백]\n"
            "아래 항목에서 사용자가 문제를 지적했습니다. 이를 해결하도록 온톨로지를 개선하세요.\n"
            + "\n".join(feedback_lines)
        )

    sections.append(
        "[완료 기준]\n"
        "- 현재 온톨로지 스키마와 그래프만으로 Golden Question에 답할 수 있어야 합니다.\n"
        "- 최종 응답 마지막에는 ontology_build_report JSON 코드 블록을 반드시 포함하세요.\n"
        "- report의 question은 사용자가 입력한 Golden Question과 동일한 문장을 유지하세요."
    )
    return "\n\n".join(section for section in sections if section.strip())


def _summarize_previous_session(session_id: str, mode: AgentMode) -> str:
    """Build a compact summary of what the previous agent session accomplished."""

    cp = _get_shared_checkpointer()
    thread_id = _session_key(session_id, mode)
    try:
        checkpoint = cp.get({"configurable": {"thread_id": thread_id}})
    except Exception:
        return ""
    if not checkpoint:
        return ""

    msgs = checkpoint.get("channel_values", {}).get("messages", [])
    if not msgs:
        return ""

    # Collect tool calls made and their results (compact)
    schema_actions = []
    data_actions = []
    errors = []

    for msg in msgs:
        if isinstance(msg, AIMessage) and msg.tool_calls:
            for tc in msg.tool_calls:
                name = tc.get("name", "")
                if name.startswith("schema_create"):
                    args = tc.get("args", {})
                    schema_actions.append(f"{name}({args.get('name', '')})")
                elif name in ("execute", "batch_ingest"):
                    data_actions.append(name)
                elif name == "graph_stats":
                    data_actions.append("graph_stats")
        elif isinstance(msg, ToolMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            if '"error"' in content or "exit_code" in content:
                errors.append(f"{msg.name}: {content[:100]}")

    # Extract last AI text (final report/summary)
    last_ai_text = ""
    for msg in reversed(msgs):
        if isinstance(msg, AIMessage) and isinstance(msg.content, str) and len(msg.content) > 50:
            last_ai_text = msg.content[:500]
            break

    lines = []
    if schema_actions:
        lines.append(f"스키마 작업: {', '.join(schema_actions[:10])}")
    if data_actions:
        from collections import Counter
        counts = Counter(data_actions)
        lines.append(f"데이터 작업: {', '.join(f'{k}({v}회)' for k, v in counts.items())}")
    if errors:
        lines.append(f"에러 {len(errors)}건 (예: {errors[0][:80]})")
    lines.append(f"총 메시지 수: {len(msgs)}")
    if last_ai_text:
        lines.append(f"마지막 에이전트 응답 요약: {last_ai_text[:300]}")

    return "\n".join(lines)


def _list_sandbox_output_files() -> list[str]:
    """List files in /workspace/output/ on the active sandbox backend."""

    try:
        return list_output_filenames()
    except Exception:
        return []


def _compose_continuation_prompt(
    prompt: str,
    build_context: dict[str, Any],
    session_id: str,
    mode: AgentMode,
) -> str:
    """Compose a follow-up prompt with mission context, previous session summary, and existing artifacts."""

    sections = [f"[사용자 후속 요청]\n{prompt.strip()}"]

    # 1. Original mission (intent + golden questions)
    if build_context.get("intent"):
        sections.append(f"[최초 구축 의도]\n{build_context['intent']}")
    if build_context.get("golden_questions"):
        gq_lines = "\n".join(
            f"{i}. {q}" for i, q in enumerate(build_context["golden_questions"], 1)
        )
        sections.append(f"[Golden Question]\n{gq_lines}")

    # 2. Review feedback if any
    if build_context.get("review_feedback"):
        feedback_lines = []
        for i, item in enumerate(build_context["review_feedback"], 1):
            feedback_lines.append(
                f"{i}. {item['question']} → 판정: {item.get('verdict', '미지정')}, "
                f"피드백: {item.get('feedback', '없음')}"
            )
        sections.append("[검토 피드백]\n" + "\n".join(feedback_lines))

    # 3. Previous session summary
    summary = _summarize_previous_session(session_id, mode)
    if summary:
        sections.append(f"[이전 에이전트 세션 요약]\n{summary}")

    # 4. Existing artifacts in sandbox
    output_files = _list_sandbox_output_files()
    if output_files:
        sections.append(
            "[기존 산출물 파일 (/workspace/output/)]\n"
            + "\n".join(f"- {f}" for f in output_files)
            + "\n위 파일들을 sandbox_read나 execute로 확인하여 기존 작업을 이어가세요."
        )

    # 5. Current graph stats (compact)
    try:
        from ..ontology.tools import graph_stats as _graph_stats_fn
        stats = _graph_stats_fn()
        sections.append(f"[현재 그래프 상태]\n{stats}")
    except Exception:
        pass

    # 6. Search hints (if generated by previous build)
    if "_search_hints.json" in output_files:
        try:
            from .sandbox_tools import sandbox_read
            hints = sandbox_read("/workspace/output/_search_hints.json", limit=500)
            if hints and not hints.startswith("{\"error"):
                sections.append(f"[검색 힌트]\n{hints[:1000]}")
        except Exception:
            pass

    sections.append(
        "[완료 기준]\n"
        "- 현재 온톨로지 스키마와 그래프만으로 Golden Question에 답할 수 있어야 합니다.\n"
        "- 최종 응답 마지막에는 ontology_build_report JSON 코드 블록을 반드시 포함하세요.\n"
        "- report의 question은 사용자가 입력한 Golden Question과 동일한 문장을 유지하세요."
    )

    return "\n\n".join(s for s in sections if s.strip())


def _normalize_build_report_question(
    item: dict[str, Any],
    fallback_question: str,
) -> dict[str, str]:
    """Normalize a single build report question entry."""

    return {
        "question": _clean_text(item.get("question")) or fallback_question,
        "answer": _clean_text(item.get("answer")),
        "status": _clean_text(item.get("status")) or "answerable",
        "confidence": _clean_text(item.get("confidence")) or "medium",
    }


def _extract_build_report(
    text: str,
    build_context: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    """Split the visible assistant text from the structured build report."""

    if not text:
        return "", None

    match = _BUILD_REPORT_PATTERN.search(text)
    if not match:
        return text.strip(), None

    try:
        payload = json.loads(match.group(1))
    except json.JSONDecodeError:
        cleaned_text = _BUILD_REPORT_PATTERN.sub("", text).strip()
        return cleaned_text, None

    raw_items = payload.get("golden_questions", [])
    normalized_items = []
    fallback_questions = build_context.get("golden_questions", [])
    if isinstance(raw_items, list):
        for index, raw_item in enumerate(raw_items):
            if not isinstance(raw_item, dict):
                continue
            fallback_question = (
                fallback_questions[index] if index < len(fallback_questions) else ""
            )
            normalized_items.append(
                _normalize_build_report_question(raw_item, fallback_question)
            )

    if not normalized_items and fallback_questions:
        normalized_items = [
            {
                "question": question,
                "answer": "",
                "status": "not_yet_answerable",
                "confidence": "low",
            }
            for question in fallback_questions
        ]

    cleaned_text = _BUILD_REPORT_PATTERN.sub("", text).strip()
    return cleaned_text, {
        "intent": _clean_text(payload.get("intent")) or build_context.get("intent", ""),
        "summary": _clean_text(payload.get("summary")),
        "next_action": _clean_text(payload.get("next_action")),
        "golden_questions": normalized_items,
    }


def _extract_text_from_content(content: Any) -> str:
    """Extract assistant-visible text from LangChain/OpenAI content blocks."""

    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(_extract_text_from_content(item) for item in content)
    if isinstance(content, dict):
        block_type = _clean_text(content.get("type"))
        if block_type in _TEXT_CONTENT_BLOCK_TYPES:
            return _extract_text_from_content(content.get("text"))
        if "content" in content:
            nested = _extract_text_from_content(content.get("content"))
            if nested:
                return nested
        if "output" in content:
            nested = _extract_text_from_content(content.get("output"))
            if nested:
                return nested
        if isinstance(content.get("text"), str):
            return content["text"]
        if isinstance(content.get("text"), dict):
            return _extract_text_from_content(content["text"])
    return ""


def _merge_stream_text(current_text: str, incoming_text: str) -> tuple[str, str]:
    """Append only the new delta when updates repeat the full assistant text."""

    if not incoming_text:
        return current_text, ""
    if not current_text:
        return incoming_text, incoming_text
    if incoming_text == current_text or current_text.endswith(incoming_text):
        return current_text, ""
    if incoming_text.startswith(current_text):
        delta = incoming_text[len(current_text) :]
        return incoming_text, delta

    max_overlap = min(len(current_text), len(incoming_text))
    for overlap in range(max_overlap, 0, -1):
        if current_text.endswith(incoming_text[:overlap]):
            delta = incoming_text[overlap:]
            return current_text + delta, delta

    return current_text + incoming_text, incoming_text


def _resolve_agent_model_profile(mode: AgentMode):
    """Resolve the configured model profile for a given agent mode."""

    settings = get_settings()
    if mode == "build":
        return resolve_model_profile(
            purpose="major",
            model_name=settings.major_model,
            reasoning_effort=settings.major_model_reasoning_effort,
            openai_base_url=settings.openai_base_url,
            openai_api_key=settings.openai_api_key,
        )
    return resolve_model_profile(
        purpose="minor",
        model_name=settings.minor_model,
        reasoning_effort=settings.minor_model_reasoning_effort,
        openai_base_url=settings.openai_base_url,
        openai_api_key=settings.openai_api_key,
    )


def _init_model(mode: AgentMode, *, request_timeout: float | None = None, max_retries: int = 2):
    """Create the configured model instance or provider string."""

    profile = _resolve_agent_model_profile(mode)
    if profile.is_openai:
        from langchain_openai import ChatOpenAI

        kwargs = {
            "model": profile.model_name,
            "api_key": profile.api_key,
            "use_responses_api": should_use_openai_responses_api(profile),
            "streaming": False,
            # Set these before ChatOpenAI constructs its HTTP clients. Updating
            # a model copy afterwards leaves the original clients unchanged.
            "timeout": request_timeout,
            "max_retries": max_retries,
        }
        if profile.reasoning_effort and profile.reasoning_effort != "none":
            kwargs["reasoning_effort"] = profile.reasoning_effort
        if profile.base_url:
            kwargs["base_url"] = profile.base_url
        return ChatOpenAI(**kwargs)
    return profile.raw_name


_checkpointer = None

def _get_shared_checkpointer():
    """Return (and cache) the shared SqliteSaver instance."""
    global _checkpointer
    if _checkpointer is None:
        _checkpointer = _get_checkpointer()
    return _checkpointer


def _create_build_agent():
    """Create the ontology construction agent with sandbox access."""

    from langchain.agents import create_agent
    from .tool_call_parser import ToolCallParserMiddleware
    from .history_compression import HistoryCompressionMiddleware

    return create_agent(
        model=_init_model("build"),
        tools=_BUILD_MODE_TOOLS,
        system_prompt=ONTOLOGY_BUILD_SYSTEM_PROMPT,
        checkpointer=_get_shared_checkpointer(),
        middleware=[HistoryCompressionMiddleware(), ToolCallParserMiddleware()],
    )


def _create_answer_agent():
    """Create the question-answering agent with read-only ontology tools."""

    from langchain.agents import create_agent
    from .tool_call_parser import ToolCallParserMiddleware
    from .history_compression import HistoryCompressionMiddleware

    return create_agent(
        model=_init_model("answer"),
        tools=_ANSWER_MODE_TOOLS,
        system_prompt=ONTOLOGY_ANSWER_SYSTEM_PROMPT,
        checkpointer=_get_shared_checkpointer(),
        middleware=[HistoryCompressionMiddleware(), ToolCallParserMiddleware()],
    )


def get_agent(mode: AgentMode = "build"):
    """Return the singleton deep agent instance for the requested mode."""

    if mode not in _agents:
        if mode == "build":
            _agents[mode] = _create_build_agent()
        else:
            _agents[mode] = _create_answer_agent()
    return _agents[mode]


def _has_existing_checkpoint(session_id: str, mode: AgentMode) -> bool:
    """Check if a previous checkpoint exists for this session+mode thread."""
    try:
        cp = _get_shared_checkpointer()
        thread_id = _session_key(session_id, mode)
        checkpoint = cp.get({"configurable": {"thread_id": thread_id}})
        if checkpoint and checkpoint.get("channel_values", {}).get("messages"):
            return len(checkpoint["channel_values"]["messages"]) > 0
        return False
    except Exception:
        return False


def _session_key(session_id: str, mode: AgentMode) -> str:
    """Return the in-memory session key for the mode-specific conversation."""

    return f"{session_id}:{mode}"


def warm_up_agent() -> None:
    """Initialize agent dependencies eagerly on app startup."""

    settings = get_settings()
    _db_init()
    _get_shared_checkpointer().setup()
    try:
        ensure_sandbox_ready()
    except Exception as exc:
        SmartLogger.log(
            "ERROR",
            "DeepAgent sandbox sanity check failed during backend startup",
            category="backend_status",
            params={
                "phase": "startup",
                "container_name": settings.container_name,
                "sandbox_workdir": settings.sandbox_workdir,
                "error": str(exc),
            },
        )
        raise

    SmartLogger.log(
        "INFO",
        "DeepAgent sandbox passed startup sanity check",
        category="backend_status",
        params={
            "phase": "startup",
            "container_name": settings.container_name,
            "sandbox_workdir": settings.sandbox_workdir,
        },
    )
    get_agent("build")
    get_agent("answer")
    ensure_workspace_dirs()


def clear_session(session_id: str) -> None:
    """Drop checkpointed history and session metadata."""

    for mode in ("build", "answer"):
        _sessions.pop(_session_key(session_id, mode), None)
    # Delete session metadata from our sessions table
    _db_delete_messages(session_id)
    # Delete LangGraph checkpointer data for this session's threads
    try:
        cp = _get_shared_checkpointer()
        for m in ("build", "answer"):
            thread_id = _session_key(session_id, m)
            # SqliteSaver stores by thread_id; delete its checkpoints
            cp.conn.execute(
                "DELETE FROM checkpoints WHERE thread_id = ?", (thread_id,)
            )
            cp.conn.execute(
                "DELETE FROM writes WHERE thread_id = ?", (thread_id,)
            )
        cp.conn.commit()
    except Exception:
        pass  # best-effort cleanup


def _format_sse(event: str, data: dict) -> str:
    encoded = json.dumps(data, ensure_ascii=False)
    return f"event: {event}\ndata: {encoded}\n\n"


def _build_preprocessing_todos(current_stage: str) -> list[dict[str, str]]:
    stages = [
        ("ocr", "문서 텍스트 추출"),
        ("embedding", "청크 임베딩 생성"),
        ("neo4j_upsert", "Neo4j 문서 그래프 업로드"),
        ("agent_build", "온톨로지 구축 에이전트 실행"),
    ]
    completed = True
    items = []
    for stage_id, label in stages:
        if stage_id == current_stage:
            items.append({"id": stage_id, "content": label, "status": "in_progress"})
            completed = False
            continue
        if completed:
            items.append({"id": stage_id, "content": label, "status": "completed"})
        else:
            items.append({"id": stage_id, "content": label, "status": "pending"})
    return items


def _resolve_preprocess_stage(detail: dict[str, Any] | None) -> str:
    if not detail:
        return "ocr"
    stage = _clean_text(detail.get("stage"))
    if stage in {"ocr", "embedding", "neo4j_upsert"}:
        return stage
    return "ocr"


def _describe_tool_call(tool_name: str, args: dict[str, Any] | None) -> str:
    """Generate a human-readable Korean description for a tool call."""

    args = args or {}
    if tool_name == "execute":
        cmd = args.get("command", "")
        if "pdfplumber" in cmd:
            return "PDF 문서를 파싱하여 텍스트를 추출합니다"
        if "openpyxl" in cmd:
            return "Excel 파일을 읽어 데이터를 추출합니다"
        if "json.dump" in cmd or "json.dumps" in cmd:
            return "파싱 결과를 JSON 파일로 저장합니다"
        if cmd.startswith("ls ") or cmd.startswith("find "):
            return "파일 시스템을 탐색합니다"
        if "cat " in cmd:
            return "파일 내용을 읽습니다"
        first_line = cmd.split("\n")[0][:60]
        return f"코드를 실행합니다: {first_line}"
    if tool_name == "sandbox_ls":
        return f"{args.get('path', '/workspace')} 디렉토리의 파일 목록을 조회합니다"
    if tool_name == "sandbox_read":
        path = args.get("file_path", "")
        return f"파일을 읽습니다: {Path(path).name}" if path else "파일을 읽습니다"
    if tool_name == "sandbox_write":
        path = args.get("file_path", "")
        return f"파일을 작성합니다: {Path(path).name}" if path else "파일을 작성합니다"
    if tool_name == "schema_get":
        return "현재 온톨로지 스키마를 조회합니다"
    if tool_name == "schema_create_class":
        return f"클래스 '{args.get('name', '')}' 를 생성합니다"
    if tool_name == "schema_create_relationship_type":
        return f"관계 유형 '{args.get('name', '')}' ({args.get('from_class', '')} → {args.get('to_class', '')})를 정의합니다"
    if tool_name == "entity_create":
        return f"'{args.get('class_name', '')}' 엔티티를 생성합니다"
    if tool_name == "entity_search":
        return f"'{args.get('class_name', '')}' 엔티티를 검색합니다"
    if tool_name == "relationship_create":
        return f"관계 '{args.get('relationship_type', '')}' 를 생성합니다"
    if tool_name == "batch_ingest":
        src = args.get("nodes_json", "")
        if src.startswith("/"):
            return f"파싱 결과를 Neo4j에 일괄 적재합니다: {Path(src).name}"
        return "파싱 결과를 Neo4j에 일괄 적재합니다"
    if tool_name == "graph_stats":
        return "그래프 전체 통계를 조회합니다 (노드 수, 관계 수)"
    if tool_name == "neo4j_cypher" or tool_name == "neo4j_cypher_readonly":
        query = args.get("query", "")[:60]
        return f"Cypher 쿼리를 실행합니다: {query}"
    return f"{tool_name} 도구를 실행합니다"


def _emit_tool_side_effects(
    tool_name: str,
    content: str,
    generated_files: list[str],
    seen_refs: set[str],
) -> list[str]:
    events = []

    if tool_name == "write_todos":
        todos = []
        try:
            import ast

            bracket_start = content.find("[")
            if bracket_start >= 0:
                todos = ast.literal_eval(content[bracket_start:])
        except Exception:
            todos = []
        if todos:
            events.append(_format_sse("todos", {"items": todos}))

    if tool_name in ("ls", "read_file", "glob"):
        file_matches = re.findall(r"/workspace/uploads/[^'\"\]\n]+", content)
        for match in file_matches:
            cleaned = match.rstrip(" ,")
            filename = cleaned.split("/workspace/uploads/")[-1]
            if filename and filename not in seen_refs:
                seen_refs.add(filename)
                events.append(_format_sse("ref_file", {"name": filename, "path": cleaned}))

    if "/workspace/output/" in content:
        found = re.findall(r"/workspace/output/[\w\-\.]+", content)
        for file_path in found:
            filename = Path(file_path).name
            if filename not in generated_files:
                generated_files.append(filename)

    if tool_name in _NEO4J_TOOL_NAMES:
        events.append(_format_sse("neo4j_update", {"tool": tool_name}))

    # When a schema group is created, notify frontend with the schema name
    if tool_name == "schema_group_create":
        try:
            data = json.loads(content)
            schema_name = data.get("name", "")
            if schema_name:
                events.append(_format_sse("schema_created", {"schema_name": schema_name}))
        except (json.JSONDecodeError, TypeError):
            pass

    # Extract traversed node IDs for graph visualization (QA tools)
    _QA_NODE_TOOLS = {"entity_search", "neo4j_cypher_readonly", "vector_search"}
    if tool_name in _QA_NODE_TOOLS:
        node_ids = _extract_node_ids(content, tool_name)
        if node_ids:
            events.append(_format_sse("traversed_nodes", {"tool": tool_name, "node_ids": node_ids}))

    return events


def _extract_node_ids(content: str, _tool_name: str = "") -> list[str]:
    """Extract Neo4j node element IDs from tool result JSON."""
    try:
        data = json.loads(content)
    except (json.JSONDecodeError, TypeError):
        return []

    ids = []
    items = data if isinstance(data, list) else [data]
    for item in items:
        if not isinstance(item, dict):
            continue
        # vector_search: has node_id field
        if "node_id" in item:
            ids.append(item["node_id"])
        # _element_id injected by _run_readonly_query for cypher results
        elif "_element_id" in item and isinstance(item["_element_id"], str):
            ids.append(item["_element_id"])
        # entity_search / cypher: has id field (element_id format)
        elif "id" in item and isinstance(item["id"], str) and ":" in item["id"]:
            ids.append(item["id"])
        # cypher results may have nested node dicts (e.g. {"n": {"id": "..."}})
        for val in item.values():
            if isinstance(val, dict):
                if "id" in val and isinstance(val["id"], str) and ":" in val["id"]:
                    ids.append(val["id"])
                elif "_element_id" in val and isinstance(val["_element_id"], str):
                    ids.append(val["_element_id"])
    return list(dict.fromkeys(ids))  # dedupe preserving order


# Stable public seam for out-of-module consumers (e.g. ontology_mcp) that need to
# recover which Neo4j nodes an answer-mode tool result referenced.
def extract_node_ids(content: str, tool_name: str = "") -> list[str]:
    """Extract Neo4j node element IDs from an answer-tool result JSON string."""

    return _extract_node_ids(content, tool_name)


def _estimate_tokens(text: str) -> int:
    """Rough token estimate from character count."""
    return max(1, int(len(text) / _CHARS_PER_TOKEN))


def _truncate_tool_content(content: str, max_chars: int = _TOOL_RESULT_TRUNCATE_CHARS) -> str:
    """Truncate a tool result string to fit within budget."""
    if len(content) <= max_chars:
        return content
    return content[:max_chars] + _TOOL_RESULT_SUMMARY_SUFFIX


def _compress_history(messages: list, max_tokens: int = _MAX_HISTORY_TOKENS) -> list:
    """Compress conversation history to fit within the token budget.

    Strategy:
    1. Always keep the last HumanMessage (current prompt).
    2. Truncate large ToolMessage contents in older messages.
    3. If still over budget, drop oldest message pairs from the front.
    """
    if not messages:
        return messages

    # Step 1: Truncate tool results in all but the last few messages
    compressed = []
    for msg in messages:
        if isinstance(msg, ToolMessage):
            content = msg.content if isinstance(msg.content, str) else str(msg.content)
            truncated = _truncate_tool_content(content)
            if truncated != content:
                compressed.append(ToolMessage(
                    content=truncated,
                    tool_call_id=msg.tool_call_id,
                    name=msg.name,
                ))
            else:
                compressed.append(msg)
        else:
            compressed.append(msg)

    # Step 2: Estimate total tokens and trim from front if needed
    def _total_tokens(msgs):
        total = 0
        for m in msgs:
            c = m.content if isinstance(m.content, str) else str(m.content)
            total += _estimate_tokens(c)
        return total

    while len(compressed) > 1 and _total_tokens(compressed) > max_tokens:
        # Remove the oldest message, but never remove the last one
        compressed.pop(0)

    return compressed


def _run_agent_in_thread(
    prompt: str,
    session_id: str,
    mode: AgentMode,
    run_id: str,
    queue: asyncio.Queue,
    loop: asyncio.AbstractEventLoop,
) -> None:
    """Run the synchronous agent stream on a background thread."""

    try:
        agent = get_agent(mode)
        # Ensure session exists in the metadata DB
        _db_ensure_session(session_id, title=prompt[:80])

        # thread_id combines session_id and mode for checkpointer isolation
        thread_id = _session_key(session_id, mode)

        model_profile = _resolve_agent_model_profile(mode)
        stream_modes = ["messages", "updates"] if not model_profile.uses_custom_base_url else ["updates"]
        log_agent_event(
            "INFO",
            "agent_stream_thread_started",
            run_id=run_id,
            session_id=session_id,
            mode=mode,
            stream_modes=stream_modes,
        )
        # SqliteSaver checkpointer automatically persists and restores history
        # via thread_id — only send the new user message.
        from .tool_call_parser import _extract_tool_calls_from_text

        # For continuation, start a new thread to avoid bloating context
        # with the full previous conversation. The continuation prompt
        # already contains the mission, summary, and artifacts.
        if _has_existing_checkpoint(session_id, mode):
            thread_id = f"{thread_id}:{uuid.uuid4().hex[:8]}"

        config = {"configurable": {"thread_id": thread_id}}
        input_msg = {"messages": [HumanMessage(content=prompt)]}
        max_raw_retries = 10  # prevent infinite loops

        for _retry in range(max_raw_retries):
            for event_mode, payload in agent.stream(
                input_msg,
                config=config,
                stream_mode=stream_modes,
            ):
                loop.call_soon_threadsafe(queue.put_nowait, (event_mode, payload))

            # Check if the last AIMessage contains raw tool calls
            state = agent.get_state(config)
            msgs = state.values.get("messages", [])
            last_ai = None
            for m in reversed(msgs):
                if isinstance(m, AIMessage):
                    last_ai = m
                    break
            if last_ai is None or last_ai.tool_calls:
                break  # normal finish or already has tool_calls

            content = last_ai.content if isinstance(last_ai.content, str) else str(last_ai.content)
            if "<|start|>" not in content:
                break  # no raw tool calls

            cleaned, tool_calls = _extract_tool_calls_from_text(content)
            if not tool_calls:
                break

            # Execute the parsed tool calls and inject results
            tool_results = []
            for tc in tool_calls:
                tool_name = tc["name"]
                tool_args = tc["args"]
                tool_id = tc["id"]
                # Find and execute the tool
                tool_fn = None
                active_tools = _BUILD_MODE_TOOLS if mode == "build" else _ANSWER_MODE_TOOLS
                for t in active_tools:
                    fn_name = getattr(t, "__name__", getattr(t, "name", ""))
                    if fn_name == tool_name:
                        tool_fn = t
                        break
                if tool_fn is None:
                    result_content = json.dumps({"error": f"Tool '{tool_name}' not found"})
                else:
                    try:
                        result_content = tool_fn(**tool_args)
                    except Exception as tool_exc:
                        result_content = json.dumps({"error": str(tool_exc)})

                # Emit tool_start and tool_result SSE events
                loop.call_soon_threadsafe(queue.put_nowait, (
                    "updates",
                    {"tools": {"messages": [ToolMessage(content=result_content, tool_call_id=tool_id, name=tool_name)]}},
                ))
                tool_results.append(ToolMessage(content=result_content, tool_call_id=tool_id, name=tool_name))

            # Update the checkpoint: replace the raw AIMessage + add ToolMessages
            new_ai = AIMessage(content=cleaned, tool_calls=tool_calls)
            agent.update_state(config, {"messages": [new_ai] + tool_results})

            # Continue the loop — agent will process tool results
            input_msg = None  # resume from checkpoint
    except Exception as exc:  # pragma: no cover - passthrough error handling
        log_agent_event(
            "ERROR",
            "agent_stream_thread_error",
            run_id=run_id,
            session_id=session_id,
            mode=mode,
            error=str(exc),
            traceback=traceback.format_exc(),
        )
        loop.call_soon_threadsafe(queue.put_nowait, ("__error__", str(exc)))
    finally:
        log_agent_event(
            "INFO",
            "agent_stream_thread_finished",
            run_id=run_id,
            session_id=session_id,
            mode=mode,
        )
        loop.call_soon_threadsafe(queue.put_nowait, _SENTINEL)


async def generate_sse(
    prompt: str,
    session_id: str,
    mode: AgentMode = "build",
    raw_build_context: str | None = None,
):
    """Yield streaming agent events as SSE messages."""

    build_context = _parse_build_context(raw_build_context if mode == "build" else "")
    has_checkpoint = _has_existing_checkpoint(session_id, mode)
    has_build_context = bool(
        build_context.get("intent") or build_context.get("golden_questions")
    )

    # Save build_context on first request; restore on follow-ups
    if mode == "build" and has_build_context:
        _db_ensure_session(session_id, title=prompt[:80])
        _db_save_build_context(session_id, json.dumps(build_context, ensure_ascii=False))
    elif mode == "build" and not has_build_context:
        # Follow-up (e.g. "계속해") — restore saved context
        saved = _db_load_build_context(session_id)
        if saved:
            build_context = _parse_build_context(saved)
            has_build_context = True

    is_continuation = has_checkpoint
    if mode == "build" and not is_continuation:
        # First request — full build prompt with intent, golden questions
        effective_prompt = _compose_build_prompt(prompt, build_context)
    elif mode == "build" and is_continuation:
        # Follow-up — include mission, previous summary, and existing artifacts
        effective_prompt = _compose_continuation_prompt(
            prompt, build_context, session_id, mode
        )
    else:
        effective_prompt = prompt
    settings = get_settings()
    model_profile = _resolve_agent_model_profile(mode)
    stream_modes = ["messages", "updates"] if not model_profile.uses_custom_base_url else ["updates"]
    run_id = uuid.uuid4().hex
    run_started_at = time.perf_counter()
    queue: asyncio.Queue = asyncio.Queue()
    loop = asyncio.get_running_loop()
    log_agent_event(
        "INFO",
        "agent_run_started",
        run_id=run_id,
        session_id=session_id,
        mode=mode,
        user_prompt=prompt,
        raw_build_context=raw_build_context if mode == "build" else None,
        parsed_build_context=build_context if mode == "build" else None,
        effective_prompt=effective_prompt,
        model_name=model_profile.raw_name,
        using_custom_base_url=model_profile.uses_custom_base_url,
        sandbox_container_name=settings.container_name,
        sandbox_workdir=settings.sandbox_workdir,
        stream_modes=stream_modes,
    )
    generated_files: list[str] = []
    seen_skills: set[str] = set()
    seen_refs: set[str] = set()
    pending_tool_names: dict[str, str] = {}
    emitted_tool_starts: set[str] = set()
    emitted_tool_results: set[str] = set()
    tool_started_at: dict[str, float] = {}
    tool_runs: list[dict[str, Any]] = []
    tool_runs_by_id: dict[str, dict[str, Any]] = {}
    node_update_counts: dict[str, int] = {}
    stream_event_counts = {"messages": 0, "updates": 0}
    last_logged_node = ""
    run_failed = False
    error_message = ""
    assistant_text = ""
    mode_label = "온톨로지 구축" if mode == "build" else "질문 응답"
    if mode == "build":
        if is_continuation:
            yield _format_sse("status", {"message": "이전 대화를 이어서 진행합니다..."})
        else:
            gq_count = len(build_context["golden_questions"]) if build_context["golden_questions"] else 0
            status_message = f"온톨로지 구축 에이전트를 시작합니다... ({gq_count}개 Golden Question)"
            yield _format_sse("status", {"message": status_message})
    else:
        yield _format_sse("status", {"message": f"{mode_label} 모드 실행 시작..."})

    thread = threading.Thread(
        target=_run_agent_in_thread,
        args=(effective_prompt, session_id, mode, run_id, queue, loop),
        daemon=True,
    )
    thread.start()

    def _register_tool_start(
        tool_call_id: str,
        tool_name: str,
        node: str,
        tool_call: Any,
    ) -> bool:
        if tool_call_id and tool_call_id in emitted_tool_starts:
            return False
        if tool_call_id:
            emitted_tool_starts.add(tool_call_id)
            tool_started_at[tool_call_id] = time.perf_counter()

        tool_run = {
            "tool_call_id": tool_call_id,
            "name": tool_name,
            "node": node,
            "started_at_ms": int(time.time() * 1000),
            "duration_ms": None,
            "failed": False,
        }
        tool_runs.append(tool_run)
        if tool_call_id:
            tool_runs_by_id[tool_call_id] = tool_run

        log_agent_event(
            "INFO",
            "tool_start",
            run_id=run_id,
            session_id=session_id,
            mode=mode,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            node=node,
            tool_call=tool_call,
        )
        return True

    def _register_tool_result(
        tool_call_id: str,
        tool_name: str,
        content: str,
        node: str,
    ) -> bool:
        if tool_call_id and tool_call_id in emitted_tool_results:
            return False
        if tool_call_id:
            emitted_tool_results.add(tool_call_id)

        duration_ms = None
        if tool_call_id and tool_call_id in tool_started_at:
            duration_ms = int((time.perf_counter() - tool_started_at.pop(tool_call_id)) * 1000)

        failure_reason = _detect_tool_failure(content)
        tool_run = tool_runs_by_id.get(tool_call_id)
        if tool_run is None:
            tool_run = {
                "tool_call_id": tool_call_id,
                "name": tool_name,
                "node": node,
                "started_at_ms": None,
                "duration_ms": None,
                "failed": False,
            }
            tool_runs.append(tool_run)
            if tool_call_id:
                tool_runs_by_id[tool_call_id] = tool_run

        tool_run["name"] = tool_name or tool_run.get("name", "")
        tool_run["node"] = node or tool_run.get("node", "")
        tool_run["duration_ms"] = duration_ms
        tool_run["completed_at_ms"] = int(time.time() * 1000)
        tool_run["failed"] = failure_reason is not None
        if failure_reason:
            tool_run["failure_reason"] = failure_reason

        log_agent_event(
            "ERROR" if failure_reason else "INFO",
            "tool_result",
            run_id=run_id,
            session_id=session_id,
            mode=mode,
            tool_call_id=tool_call_id,
            tool_name=tool_name,
            node=node,
            duration_ms=duration_ms,
            failed=failure_reason is not None,
            failure_reason=failure_reason,
            content=content,
        )
        return True

    def _record_node_update(node_name: str) -> None:
        nonlocal last_logged_node
        if not node_name:
            return
        node_update_counts[node_name] = node_update_counts.get(node_name, 0) + 1
        if node_name != last_logged_node:
            last_logged_node = node_name
            log_agent_event(
                "INFO",
                "node_update",
                run_id=run_id,
                session_id=session_id,
                mode=mode,
                node=node_name,
                update_count=node_update_counts[node_name],
            )

    while True:
        item = await queue.get()
        if item is _SENTINEL:
            break

        event_mode, payload = item
        if event_mode == "__error__":
            run_failed = True
            error_message = str(payload)
            log_agent_event(
                "ERROR",
                "agent_run_error_event",
                run_id=run_id,
                session_id=session_id,
                mode=mode,
                error=error_message,
                elapsed_ms=int((time.perf_counter() - run_started_at) * 1000),
            )
            yield _format_sse("error_event", {"message": str(payload)})
            break

        if event_mode == "messages":
            stream_event_counts["messages"] += 1
            msg_chunk, metadata = payload
            node = metadata.get("langgraph_node", "")
            _record_node_update(node)

            if isinstance(msg_chunk, AIMessageChunk):
                text = _extract_text_from_content(msg_chunk.content)
                assistant_text, delta = _merge_stream_text(assistant_text, text)
                if delta and not delta.lstrip().startswith("<|"):
                    yield _format_sse("token", {"text": delta, "node": node})

                if msg_chunk.tool_call_chunks:
                    for tool_call in msg_chunk.tool_call_chunks:
                        tool_call_id = tool_call.get("id") or str(tool_call.get("index", ""))
                        if tool_call_id and tool_call.get("name"):
                            pending_tool_names[tool_call_id] = tool_call["name"]
                        if tool_call.get("name") and _register_tool_start(
                            tool_call_id,
                            tool_call["name"],
                            node,
                            tool_call,
                        ):
                            tc_args = tool_call.get("args", {})
                            yield _format_sse(
                                "tool_start",
                                {
                                    "tool_call_id": tool_call_id,
                                    "name": tool_call["name"],
                                    "node": node,
                                    "args": tc_args,
                                    "description": _describe_tool_call(tool_call["name"], tc_args),
                                },
                            )

            elif isinstance(msg_chunk, ToolMessage):
                content = msg_chunk.content if isinstance(msg_chunk.content, str) else str(msg_chunk.content)
                tool_name = msg_chunk.name or pending_tool_names.get(msg_chunk.tool_call_id, "")
                for event in _emit_tool_side_effects(
                    tool_name,
                    content,
                    generated_files,
                    seen_refs,
                ):
                    yield event
                if _register_tool_result(msg_chunk.tool_call_id or "", tool_name, content, node):
                    yield _format_sse(
                        "tool_result",
                        {
                            "tool_call_id": msg_chunk.tool_call_id or "",
                            "name": tool_name,
                            "content": content[:3000],
                            "node": node,
                        },
                    )

        elif event_mode == "updates":
            stream_event_counts["updates"] += 1
            for node_name, node_data in payload.items():
                if node_name.startswith("__"):
                    continue
                _record_node_update(node_name)

                if "SkillsMiddleware" in node_name and node_name not in seen_skills:
                    seen_skills.add(node_name)
                    yield _format_sse("skill_loaded", {"name": "xlsx"})

                if isinstance(node_data, dict) and "messages" in node_data:
                    raw_messages = node_data["messages"]
                    if hasattr(raw_messages, "value"):
                        raw_messages = raw_messages.value
                    if not isinstance(raw_messages, list):
                        raw_messages = [raw_messages] if raw_messages else []

                    for message in raw_messages:
                        if isinstance(message, AIMessage):
                            text = _extract_text_from_content(message.content)
                            assistant_text, delta = _merge_stream_text(assistant_text, text)
                            if delta.strip() and not delta.lstrip().startswith("<|"):
                                yield _format_sse(
                                    "token",
                                    {"text": delta, "node": node_name},
                                )
                            if message.tool_calls:
                                for tool_call in message.tool_calls:
                                    tool_name = tool_call.get("name", "")
                                    tool_call_id = tool_call.get("id", "")
                                    pending_tool_names[tool_call_id] = tool_name
                                    if _register_tool_start(
                                        tool_call_id,
                                        tool_name,
                                        node_name,
                                        tool_call,
                                    ):
                                        tc_args = tool_call.get("args", {})
                                        yield _format_sse(
                                            "tool_start",
                                            {
                                                "tool_call_id": tool_call_id,
                                                "name": tool_name,
                                                "node": node_name,
                                                "args": tc_args,
                                                "description": _describe_tool_call(tool_name, tc_args),
                                            },
                                        )
                        elif isinstance(message, ToolMessage):
                            content = (
                                message.content
                                if isinstance(message.content, str)
                                else str(message.content)
                            )
                            tool_name = message.name or pending_tool_names.get(message.tool_call_id, "")
                            for event in _emit_tool_side_effects(
                                tool_name,
                                content,
                                generated_files,
                                seen_refs,
                            ):
                                yield event
                            if _register_tool_result(
                                message.tool_call_id or "",
                                tool_name,
                                content,
                                node_name,
                            ):
                                yield _format_sse(
                                    "tool_result",
                                    {
                                        "tool_call_id": message.tool_call_id or "",
                                        "name": tool_name,
                                        "content": content[:3000],
                                        "node": node_name,
                                    },
                                )

                yield _format_sse("node_update", {"node": node_name})

    all_files = list_output_filenames() or generated_files
    final_text = assistant_text.strip()

    # If streaming filters removed all text (e.g. <|start|> tokens),
    # recover from the last AIMessage in the checkpoint
    if not final_text:
        try:
            agent = get_agent(mode)
            thread_id = _session_key(session_id, mode)
            state = agent.get_state({"configurable": {"thread_id": thread_id}})
            msgs = state.values.get("messages", [])
            for m in reversed(msgs):
                if isinstance(m, AIMessage) and isinstance(m.content, str) and m.content.strip():
                    # Clean <|start|> tokens from recovered text
                    import re as _re
                    recovered = _re.sub(r"<\|[^|]*\|>", "", m.content).strip()
                    if recovered:
                        final_text = recovered
                        break
        except Exception:
            pass

    build_report = None
    if mode == "build":
        final_text, build_report = _extract_build_report(final_text, build_context)

    # Touch session metadata timestamp (SqliteSaver handles message persistence)
    if not run_failed:
        _db_touch_session(session_id)

    total_elapsed_ms = int((time.perf_counter() - run_started_at) * 1000)
    completed_tool_runs = [
        tool_run for tool_run in tool_runs if tool_run.get("completed_at_ms") is not None
    ]
    unfinished_tool_runs = [
        tool_run for tool_run in tool_runs if tool_run.get("completed_at_ms") is None
    ]
    tool_failure_count = sum(1 for tool_run in tool_runs if tool_run.get("failed"))
    total_tool_duration_ms = sum(
        tool_run["duration_ms"]
        for tool_run in tool_runs
        if isinstance(tool_run.get("duration_ms"), int)
    )
    log_agent_event(
        "ERROR" if run_failed else "INFO",
        "agent_run_finished",
        run_id=run_id,
        session_id=session_id,
        mode=mode,
        elapsed_ms=total_elapsed_ms,
        failed=run_failed,
        error=error_message or None,
        final_text=final_text,
        build_report=build_report,
    )
    log_agent_event(
        "ERROR" if run_failed or tool_failure_count else "INFO",
        "agent_run_summary",
        run_id=run_id,
        session_id=session_id,
        mode=mode,
        elapsed_ms=total_elapsed_ms,
        failed=run_failed,
        error=error_message or None,
        user_prompt=prompt,
        effective_prompt=effective_prompt,
        build_context=build_context if mode == "build" else None,
        generated_files=all_files,
        referenced_uploads=sorted(seen_refs),
        loaded_skills=sorted(seen_skills),
        stream_event_counts=stream_event_counts,
        node_update_counts=node_update_counts,
        tool_count=len(tool_runs),
        completed_tool_count=len(completed_tool_runs),
        unfinished_tool_count=len(unfinished_tool_runs),
        tool_failure_count=tool_failure_count,
        total_tool_duration_ms=total_tool_duration_ms,
        tool_runs=tool_runs,
        tool_summary=_summarize_tool_runs(tool_runs),
        final_text=final_text,
        build_report=build_report,
    )
    if mode == "build" and not run_failed:
        yield _format_sse(
            "todos",
            {
                "items": [
                    {"id": "schema_design", "content": "Phase 1: 스키마 설계", "status": "completed"},
                    {"id": "data_ingest", "content": "Phase 2: 소스 파싱 + 적재", "status": "completed"},
                    {"id": "validation", "content": "Phase 3: 검증", "status": "completed"},
                ]
            },
        )
    yield _format_sse(
        "done",
        {
            "message": "완료!",
            "files": all_files,
            "text": final_text,
            "build_report": build_report,
        },
    )
