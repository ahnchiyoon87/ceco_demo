"""Pure-Python implementations behind the read-only ontology MCP tools.

Kept transport-agnostic so they can be unit-tested directly and wrapped by the
FastMCP server in ``server.py``. Every function returns a JSON-serializable dict
and converts underlying failures into ``{"error": ...}`` rather than raising.
"""

from __future__ import annotations

import json
import uuid

from ...shared.kernel.settings import get_settings
from ..ontology.tools import (
    _run_readonly_query,
    entity_search,
    schema_get,
    schema_group_list,
    vector_search,
)
from .sources import NodeRecorder, resolve_sources

# Fields whose (possibly long) text content should be bounded before returning.
_TEXT_FIELDS = ("content", "content_preview", "excerpt", "text", "source_text")


def _load_json(raw):
    """Parse a tool's JSON string result, tolerating already-parsed values."""

    if isinstance(raw, (dict, list)):
        return raw
    try:
        return json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {"error": "failed to parse tool output", "raw": str(raw)[:500]}


def _truncate_text_fields(entity: dict, char_limit: int) -> dict:
    """Return a copy of ``entity`` with known long text fields bounded."""

    bounded = dict(entity)
    for key in _TEXT_FIELDS:
        value = bounded.get(key)
        if isinstance(value, str) and len(value) > char_limit:
            bounded[key] = value[:char_limit] + "…"
    return bounded


def _bound_entities(entities: list, max_results: int, char_limit: int) -> list:
    """Cap the entity list and bound each entity's text fields."""

    capped = entities[:max_results]
    return [_truncate_text_fields(e, char_limit) if isinstance(e, dict) else e for e in capped]


def _final_text(messages) -> str:
    """Extract the last non-empty AI answer text from an agent's messages."""

    from ..agent_session.service import _extract_text_from_content

    for msg in reversed(messages or []):
        is_ai = getattr(msg, "type", "") == "ai" or msg.__class__.__name__.startswith("AIMessage")
        if not is_ai:
            continue
        text = _extract_text_from_content(getattr(msg, "content", ""))
        if text and text.strip():
            return text.strip()
    return ""


# ---------------------------------------------------------------------------
# 1. Natural-language query -> answer text + cited sources
# ---------------------------------------------------------------------------

def _compose_prompt(question: str, schema_hint: str) -> str:
    """Prepend an optional schema hint to the user's question."""

    hint = (schema_hint or "").strip()
    return f"[스키마 힌트] {hint}\n\n{question}" if hint else question


def _parse_sse_event(chunk: str):
    """Parse a single ``event:/data:`` SSE frame into ``(event, data_dict)``."""

    event = None
    data_line = None
    for line in chunk.splitlines():
        if line.startswith("event:"):
            event = line[len("event:"):].strip()
        elif line.startswith("data:"):
            data_line = line[len("data:"):].strip()
    if event is None:
        return None, None
    try:
        data = json.loads(data_line) if data_line else {}
    except (json.JSONDecodeError, TypeError):
        data = {"raw": data_line}
    return event, data


async def ontology_query_stream(question: str, schema_hint: str = "", emit=None) -> dict:
    """Streaming variant of :func:`ontology_query`.

    Drives the *same* answer-agent stream the frontend consumes (``generate_sse``)
    and forwards each progress event to the async ``emit(kind, data)`` callback as
    it happens — status, tool_start, tool_result, referenced nodes, and assistant
    text deltas — so a streamable-HTTP MCP client can show the Deep Agent's search
    progress live. Returns the final ``{answer, sources, meta}`` when complete.
    """

    q = (question or "").strip()
    if not q:
        return {"error": "question is required"}

    from ..agent_session.service import clear_session, generate_sse

    prompt = _compose_prompt(q, schema_hint)
    session_id = f"mcp-{uuid.uuid4().hex[:12]}"
    node_ids: list[str] = []
    final_text = ""
    error = None
    token_buf: list[str] = []

    async def _flush_tokens():
        if token_buf and emit:
            text = "".join(token_buf)
            if text.strip():
                await emit("assistant_delta", {"text": text})
        token_buf.clear()

    try:
        async for chunk in generate_sse(prompt, session_id, "answer", ""):
            event, data = _parse_sse_event(chunk)
            if event is None:
                continue

            if event == "token":
                delta = data.get("text", "")
                token_buf.append(delta)
                # Coalesce token deltas into readable chunks to avoid flooding.
                if emit and (sum(len(t) for t in token_buf) >= 80 or "\n" in delta):
                    await _flush_tokens()
                continue

            # Non-token event: flush pending assistant text first so ordering
            # relative to tool activity is preserved.
            await _flush_tokens()

            if event == "traversed_nodes":
                node_ids.extend(data.get("node_ids", []))
            elif event == "done":
                final_text = data.get("text", "") or final_text
            elif event == "error_event":
                error = data.get("message")

            if emit:
                await emit(event, data)

        await _flush_tokens()

        if error and not final_text:
            return {"error": error}

        sources = resolve_sources(list(dict.fromkeys(node_ids)))
        meta = {
            "session_id": session_id,
            "referenced_node_count": len(sources),
            "streamed": True,
        }
        if not sources:
            meta["note"] = "no node provenance captured"
        return {"answer": final_text, "sources": sources, "meta": meta}
    except Exception as exc:  # pragma: no cover - runtime/model failures
        return {"error": str(exc)}
    finally:
        try:
            clear_session(session_id)
        except Exception:
            pass


def ontology_query(question: str, schema_hint: str = "") -> dict:
    """Answer a natural-language question over the ontology, citing source nodes.

    Runs the studio's read-only answer agent to completion on an ephemeral
    session and returns ``{answer, sources, meta}``. Each source names a
    referenced node (element id, labels, display name, excerpt).
    """

    q = (question or "").strip()
    if not q:
        return {"error": "question is required"}

    from langchain_core.messages import HumanMessage

    from ..agent_session.service import _session_key, clear_session, get_agent

    prompt = _compose_prompt(q, schema_hint)
    session_id = f"mcp-{uuid.uuid4().hex[:12]}"
    recorder = NodeRecorder()

    try:
        agent = get_agent("answer")
        config = {"configurable": {"thread_id": _session_key(session_id, "answer")}}
        result = agent.invoke({"messages": [HumanMessage(content=prompt)]}, config=config)
        messages = result.get("messages", []) if isinstance(result, dict) else []
        recorder.record_messages(messages)
        sources = resolve_sources(recorder.node_ids)
        meta = {"session_id": session_id, "referenced_node_count": len(sources)}
        if not sources:
            meta["note"] = "no node provenance captured"
        return {"answer": _final_text(messages), "sources": sources, "meta": meta}
    except Exception as exc:  # pragma: no cover - runtime/model failures
        return {"error": str(exc)}
    finally:
        try:
            clear_session(session_id)
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 2. Entity-bundle retrieval
# ---------------------------------------------------------------------------

def _fetch_entities_by_labels(classes: list, limit: int) -> list:
    """Return all entities whose class labels intersect ``classes`` (bounded)."""

    if not classes:
        return []
    rows = _run_readonly_query(
        """
        MATCH (n:_Entity)
        WHERE any(lbl IN labels(n) WHERE lbl IN $classes)
        RETURN elementId(n) AS id,
               [l IN labels(n) WHERE l <> '_Entity'] AS labels,
               properties(n) AS properties
        LIMIT $limit
        """,
        {"classes": classes, "limit": limit},
    )
    return [
        {"id": row["id"], "labels": row.get("labels") or [], **(row.get("properties") or {})}
        for row in rows
    ]


def _fetch_schema_entities(schema_name: str, limit: int):
    """Return entities whose class labels belong to a schema group."""

    from ..agent_session.session_store import get_schema_by_name

    schema = get_schema_by_name(schema_name)
    if not schema:
        return None, f"schema group not found: {schema_name}"

    classes = [c["class_name"] for c in schema.get("classes", [])]
    return _fetch_entities_by_labels(classes, limit), None


def ontology_list_entities(
    class_name: str | None = None,
    schema_name: str | None = None,
    criteria: str | None = None,
    semantic_query: str | None = None,
    limit: int | None = None,
) -> dict:
    """Return a bounded bundle of entity nodes selected by one of several modes.

    Dispatch priority: ``semantic_query`` -> vector search; ``class_name``
    (optionally with ``criteria``) -> property search; ``schema_name`` ->
    schema-group scope. Each entity carries its properties and any
    ``_source_id`` / ``_parent_source_id`` provenance.
    """

    settings = get_settings()
    max_results = settings.mcp_max_results
    char_limit = settings.mcp_max_excerpt_chars
    effective_limit = max_results if limit is None else max(1, min(int(limit), max_results))

    if semantic_query and semantic_query.strip():
        parsed = _load_json(vector_search(semantic_query.strip(), top_k=effective_limit))
        mode = "semantic"
    elif class_name and class_name.strip():
        if criteria and criteria.strip():
            # Filtered lookup within the class.
            parsed = _load_json(entity_search(class_name.strip(), criteria.strip()))
            mode = "class"
        else:
            # No filter -> return the whole class as a bundle.
            parsed = _fetch_entities_by_labels([class_name.strip()], effective_limit)
            mode = "class"
    elif schema_name and schema_name.strip():
        entities, err = _fetch_schema_entities(schema_name.strip(), effective_limit)
        if err:
            return {"error": err}
        parsed = entities
        mode = "schema"
    elif criteria and criteria.strip():
        return {"error": "criteria requires class_name"}
    else:
        return {
            "error": "at least one selector is required: "
            "class_name, schema_name, criteria, or semantic_query"
        }

    if isinstance(parsed, dict) and "error" in parsed:
        return {"error": parsed["error"]}
    if not isinstance(parsed, list):
        return {"error": "unexpected tool output", "mode": mode}

    bounded = _bound_entities(parsed, effective_limit, char_limit)
    return {
        "entities": bounded,
        "count": len(bounded),
        "mode": mode,
        "limit": effective_limit,
        "truncated": len(parsed) > len(bounded),
    }


# ---------------------------------------------------------------------------
# 3. Schema listing & reading
# ---------------------------------------------------------------------------

def ontology_list_schemas() -> dict:
    """Return the schema-group catalog with classes and per-class entity counts."""

    return _load_json(schema_group_list())


def ontology_get_schema(schema_name: str | None = None) -> dict:
    """Read the aggregated schema, or a single schema group's full definition."""

    if not schema_name or not schema_name.strip():
        return _load_json(schema_get())

    from ..agent_session.session_store import get_schema_by_name

    schema = get_schema_by_name(schema_name.strip())
    if not schema:
        return {"error": f"schema group not found: {schema_name}"}
    return {
        "name": schema.get("name"),
        "description": schema.get("description", ""),
        "classes": schema.get("classes", []),
        "relationships": schema.get("relationships", []),
    }
