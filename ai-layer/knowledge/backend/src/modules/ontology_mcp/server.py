"""FastMCP server assembly for the read-only ontology search tools."""

from __future__ import annotations

import json

from . import adapters

try:  # mcp SDK is optional at import time (only required to actually serve)
    from mcp.server.fastmcp import Context
except ImportError:  # pragma: no cover - SDK absent
    Context = None

# The complete, read-only tool surface. No write, schema-mutation, or sandbox
# tool is ever registered here — this list is the security boundary.
TOOL_NAMES = (
    "ontology_query",
    "ontology_list_entities",
    "ontology_list_schemas",
    "ontology_get_schema",
)


def _describe_args(args) -> str:
    """Compact one-line preview of a tool call's arguments."""

    if not isinstance(args, dict) or not args:
        return ""
    parts = []
    for key, value in args.items():
        text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
        if len(text) > 60:
            text = text[:60] + "…"
        parts.append(f"{key}={text}")
    return ", ".join(parts)


def build_server():
    """Construct and return a FastMCP server with the four read-only tools."""

    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("ontology-studio-search")

    @mcp.tool()
    async def ontology_query(question: str, schema_hint: str = "", ctx: Context = None) -> dict:
        """Answer a natural-language question over the built ontology.

        Streams the Deep Agent's search progress (status, tool calls, referenced
        nodes, and answer text) as MCP log/progress notifications while it runs —
        useful because the search can take a while — then returns the final answer
        plus a ``sources`` array naming every ontology node the answer referenced
        (node id, labels, name, excerpt). Use ``schema_hint`` to steer the query.
        """

        step = 0

        async def emit(kind: str, data: dict) -> None:
            nonlocal step
            if ctx is None:
                return
            try:
                if kind == "status":
                    await ctx.info(f"⏳ {data.get('message', '')}")
                elif kind == "tool_start":
                    desc = data.get("description") or _describe_args(data.get("args"))
                    await ctx.info(f"🔧 {data.get('name', '')} — {desc}".rstrip(" —"))
                    step += 1
                    await ctx.report_progress(progress=step, total=None)
                elif kind == "tool_result":
                    content = data.get("content", "") or ""
                    await ctx.info(f"✅ {data.get('name', '')} 결과 수신 ({len(content)}자)")
                elif kind == "traversed_nodes":
                    n = len(data.get("node_ids", []) or [])
                    if n:
                        await ctx.info(f"🔗 참고 노드 {n}개 확인")
                elif kind == "assistant_delta":
                    text = data.get("text", "")
                    if text.strip():
                        await ctx.info(text)
                elif kind == "error_event":
                    await ctx.warning(f"⚠️ {data.get('message', '')}")
            except Exception:
                pass  # notifications are best-effort; never fail the tool on them

        return await adapters.ontology_query_stream(question, schema_hint, emit)

    @mcp.tool()
    def ontology_list_entities(
        class_name: str = "",
        schema_name: str = "",
        criteria: str = "",
        semantic_query: str = "",
        limit: int = 0,
    ) -> dict:
        """Retrieve a bundle (list) of entity nodes.

        Provide one selector: ``semantic_query`` (semantic search),
        ``class_name`` (+ optional ``criteria`` like ``name:foo``), or
        ``schema_name`` (all entities in a schema group). Entities carry their
        properties including ``_source_id`` provenance.
        """

        return adapters.ontology_list_entities(
            class_name=class_name or None,
            schema_name=schema_name or None,
            criteria=criteria or None,
            semantic_query=semantic_query or None,
            limit=limit or None,
        )

    @mcp.tool()
    def ontology_list_schemas() -> dict:
        """List all schema groups with their classes and entity counts."""

        return adapters.ontology_list_schemas()

    @mcp.tool()
    def ontology_get_schema(schema_name: str = "") -> dict:
        """Read the aggregated schema, or one schema group's full definition."""

        return adapters.ontology_get_schema(schema_name or None)

    return mcp
