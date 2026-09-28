"""Unit tests for the read-only ontology search MCP server."""

from __future__ import annotations

import json

import pytest

from backend.src.modules.ontology_mcp import TOOL_NAMES, adapters
from backend.src.modules.ontology_mcp import sources as sources_mod
from backend.src.shared.kernel import settings as settings_mod

# Write / mutation / sandbox tools that must never be exposed by the MCP server.
_FORBIDDEN_TOOLS = {
    "entity_create",
    "relationship_create",
    "batch_ingest",
    "schema_create_class",
    "schema_create_relationship_type",
    "neo4j_cypher",
    "execute",
    "sandbox_write",
    "sandbox_ls",
    "sandbox_read",
}


@pytest.fixture
def mcp_env(monkeypatch: pytest.MonkeyPatch):
    """Provide small, deterministic MCP result bounds."""

    settings_mod.get_settings.cache_clear()
    monkeypatch.setenv("MCP_MAX_RESULTS", "2")
    monkeypatch.setenv("MCP_MAX_EXCERPT_CHARS", "10")
    yield
    settings_mod.get_settings.cache_clear()


# ---------------------------------------------------------------------------
# 8.1 Read-only tool surface
# ---------------------------------------------------------------------------

def test_tool_names_are_exactly_the_four_readonly_tools() -> None:
    assert set(TOOL_NAMES) == {
        "ontology_query",
        "ontology_list_entities",
        "ontology_list_schemas",
        "ontology_get_schema",
    }


def test_no_write_or_sandbox_tool_is_exposed() -> None:
    assert _FORBIDDEN_TOOLS.isdisjoint(set(TOOL_NAMES))


def test_registered_server_tools_match_tool_names() -> None:
    mcp = pytest.importorskip("mcp")  # noqa: F841 - skip when SDK absent
    from backend.src.modules.ontology_mcp.server import build_server

    server = build_server()
    registered = {t.name for t in server._tool_manager.list_tools()}
    assert registered == set(TOOL_NAMES)
    assert _FORBIDDEN_TOOLS.isdisjoint(registered)


# ---------------------------------------------------------------------------
# 8.2 Schema + entity shapes
# ---------------------------------------------------------------------------

def test_list_schemas_shape(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"schemas": [{"name": "People", "classes": [], "total_entity_count": 3}]}
    monkeypatch.setattr(adapters, "schema_group_list", lambda: json.dumps(payload))
    assert adapters.ontology_list_schemas() == payload


def test_get_schema_aggregated(monkeypatch: pytest.MonkeyPatch) -> None:
    payload = {"classes": [{"name": "Person"}], "relationships": [], "schemas": []}
    monkeypatch.setattr(adapters, "schema_get", lambda: json.dumps(payload))
    assert adapters.ontology_get_schema() == payload


def test_get_schema_single_group(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.src.modules.agent_session import session_store

    schema = {
        "name": "People",
        "description": "d",
        "classes": [{"class_name": "Person"}],
        "relationships": [{"name": "KNOWS"}],
    }
    monkeypatch.setattr(session_store, "get_schema_by_name", lambda name: schema)
    result = adapters.ontology_get_schema("People")
    assert result["name"] == "People"
    assert result["classes"] == [{"class_name": "Person"}]
    assert result["relationships"] == [{"name": "KNOWS"}]


def test_list_entities_semantic_preserves_source_id_and_bounds(
    mcp_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    rows = [
        {"node_id": f"4:x:{i}", "name": f"n{i}", "content_preview": "x" * 50,
         "_source_id": f"doc-{i}"}
        for i in range(5)
    ]
    monkeypatch.setattr(adapters, "vector_search", lambda q, top_k=3: json.dumps(rows))

    result = adapters.ontology_list_entities(semantic_query="hello")
    assert result["mode"] == "semantic"
    assert result["count"] == 2  # capped to MCP_MAX_RESULTS
    assert result["limit"] == 2
    assert result["truncated"] is True
    first = result["entities"][0]
    assert first["_source_id"] == "doc-0"  # provenance preserved
    assert first["content_preview"].endswith("…")  # excerpt bounded
    assert len(first["content_preview"]) <= 11  # 10 chars + ellipsis


def test_list_entities_by_class_with_criteria(mcp_env, monkeypatch: pytest.MonkeyPatch) -> None:
    entities = [{"id": "4:x:1", "labels": ["Person"], "name": "Kim", "_source_id": "s1"}]
    monkeypatch.setattr(
        adapters, "entity_search", lambda cls, crit: json.dumps(entities)
    )
    result = adapters.ontology_list_entities(class_name="Person", criteria="name:Kim")
    assert result["mode"] == "class"
    assert result["entities"][0]["_source_id"] == "s1"


def test_list_entities_by_class_without_criteria_returns_bundle(
    mcp_env, monkeypatch: pytest.MonkeyPatch
) -> None:
    # class_name alone must return the whole class as a bundle, NOT call
    # entity_search (which needs criteria and would return []).
    def _boom(*_a, **_k):  # entity_search must not be used here
        raise AssertionError("entity_search should not be called without criteria")

    monkeypatch.setattr(adapters, "entity_search", _boom)
    monkeypatch.setattr(
        adapters, "_run_readonly_query",
        lambda q, p: [{"id": "4:x:1", "labels": ["Person"],
                       "properties": {"name": "Kim", "_source_id": "s1"}}],
    )
    result = adapters.ontology_list_entities(class_name="Person")
    assert result["mode"] == "class"
    assert result["count"] == 1
    assert result["entities"][0]["_source_id"] == "s1"


def test_list_entities_by_schema(mcp_env, monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.src.modules.agent_session import session_store

    monkeypatch.setattr(
        session_store, "get_schema_by_name",
        lambda name: {"classes": [{"class_name": "Person"}]},
    )
    monkeypatch.setattr(
        adapters, "_run_readonly_query",
        lambda q, p: [{"id": "4:x:1", "labels": ["Person"],
                       "properties": {"name": "Kim", "_source_id": "s1"}}],
    )
    result = adapters.ontology_list_entities(schema_name="People")
    assert result["mode"] == "schema"
    assert result["entities"][0]["_source_id"] == "s1"
    assert result["entities"][0]["labels"] == ["Person"]


# ---------------------------------------------------------------------------
# 8.3 ontology_query (stubbed answer agent)
# ---------------------------------------------------------------------------

class _FakeToolMsg:
    type = "tool"

    def __init__(self, name, content):
        self.name = name
        self.content = content
        self.tool_call_id = "call-1"


class _FakeAIMessage:
    type = "ai"

    def __init__(self, content):
        self.content = content
        self.name = None


class _FakeAgent:
    def __init__(self, messages):
        self._messages = messages

    def invoke(self, _input, config=None):
        return {"messages": self._messages}


def _patch_agent(monkeypatch, messages):
    # ontology_query imports the answer-agent service, which pulls in the full
    # agent stack (deepagents). Skip when that stack is not installed.
    service = pytest.importorskip("backend.src.modules.agent_session.service")

    monkeypatch.setattr(service, "get_agent", lambda mode="answer": _FakeAgent(messages))
    monkeypatch.setattr(service, "clear_session", lambda sid: None)


def test_query_returns_answer_and_sources(monkeypatch: pytest.MonkeyPatch) -> None:
    tool_json = json.dumps([{"node_id": "4:abc:1", "name": "Kim"}])
    messages = [_FakeToolMsg("vector_search", tool_json), _FakeAIMessage("Kim knows Lee.")]
    _patch_agent(monkeypatch, messages)
    monkeypatch.setattr(
        sources_mod, "_run_readonly_query",
        lambda q, p: [{"node_id": "4:abc:1", "labels": ["Person"],
                       "name": "Kim", "content": "Kim is a person."}],
    )

    result = adapters.ontology_query("Who does Kim know?")
    assert result["answer"] == "Kim knows Lee."
    assert len(result["sources"]) == 1
    src = result["sources"][0]
    assert src["node_id"] == "4:abc:1"
    assert src["labels"] == ["Person"]
    assert result["meta"]["referenced_node_count"] == 1


def test_query_empty_sources_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    messages = [_FakeAIMessage("I could not find anything.")]
    _patch_agent(monkeypatch, messages)

    result = adapters.ontology_query("anything?")
    assert result["answer"] == "I could not find anything."
    assert result["sources"] == []
    assert "note" in result["meta"]


def test_query_requires_question() -> None:
    assert "error" in adapters.ontology_query("   ")


# ---------------------------------------------------------------------------
# Streaming query (generate_sse-based)
# ---------------------------------------------------------------------------

def test_parse_sse_event() -> None:
    event, data = adapters._parse_sse_event(
        'event: token\ndata: {"text": "hi", "node": "agent"}\n\n'
    )
    assert event == "token"
    assert data == {"text": "hi", "node": "agent"}

    event, data = adapters._parse_sse_event("event: done\ndata: {}\n\n")
    assert event == "done" and data == {}


def test_query_stream_forwards_events_and_returns_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = pytest.importorskip("backend.src.modules.agent_session.service")

    frames = [
        'event: status\ndata: {"message": "질문 응답 모드 실행 시작..."}\n\n',
        'event: tool_start\ndata: {"name": "vector_search", "description": "의미 검색"}\n\n',
        'event: token\ndata: {"text": "해고 예고는 "}\n\n',
        'event: token\ndata: {"text": "30일 전.\\n"}\n\n',
        'event: tool_result\ndata: {"name": "vector_search", "content": "[...]"}\n\n',
        'event: traversed_nodes\ndata: {"tool": "vector_search", "node_ids": ["4:abc:15"]}\n\n',
        'event: done\ndata: {"text": "해고 예고는 30일 전.", "files": []}\n\n',
    ]

    async def _fake_generate_sse(prompt, session_id, mode, ctx):
        for f in frames:
            yield f

    monkeypatch.setattr(service, "generate_sse", _fake_generate_sse)
    monkeypatch.setattr(service, "clear_session", lambda sid: None)
    monkeypatch.setattr(
        sources_mod, "_run_readonly_query",
        lambda q, p: [{"node_id": "4:abc:15", "labels": ["Article"],
                       "name": "제26조", "content": "…30일 전에 예고…"}],
    )

    captured: list[tuple] = []

    async def _emit(kind, data):
        captured.append((kind, data))

    import asyncio

    result = asyncio.run(
        adapters.ontology_query_stream("해고통보는 몇일내에?", emit=_emit)
    )

    assert result["answer"] == "해고 예고는 30일 전."
    assert result["meta"]["streamed"] is True
    assert len(result["sources"]) == 1
    assert result["sources"][0]["node_id"] == "4:abc:15"

    kinds = [k for k, _ in captured]
    assert "status" in kinds
    assert "tool_start" in kinds
    assert "tool_result" in kinds
    assert "traversed_nodes" in kinds
    assert "assistant_delta" in kinds  # coalesced token text was forwarded


# ---------------------------------------------------------------------------
# 8.4 Error paths
# ---------------------------------------------------------------------------

def test_get_schema_unknown_group(monkeypatch: pytest.MonkeyPatch) -> None:
    from backend.src.modules.agent_session import session_store

    monkeypatch.setattr(session_store, "get_schema_by_name", lambda name: None)
    result = adapters.ontology_get_schema("missing")
    assert "error" in result
    assert "missing" in result["error"]


def test_list_entities_no_selector() -> None:
    result = adapters.ontology_list_entities()
    assert "error" in result


def test_list_entities_criteria_without_class() -> None:
    result = adapters.ontology_list_entities(criteria="name:Kim")
    assert "error" in result
    assert "class_name" in result["error"]


def test_list_entities_vector_index_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        adapters, "vector_search",
        lambda q, top_k=3: json.dumps({"error": "벡터 인덱스가 아직 생성되지 않았습니다."}),
    )
    result = adapters.ontology_list_entities(semantic_query="hello")
    assert "error" in result
    assert "인덱스" in result["error"]
