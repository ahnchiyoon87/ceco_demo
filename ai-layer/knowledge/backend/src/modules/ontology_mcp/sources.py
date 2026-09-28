"""Provenance helpers: turn referenced Neo4j node ids into cited source records.

The natural-language query tool must report *which nodes were referenced*. During an
answer-agent run, read-only tools (`vector_search`, `entity_search`,
`neo4j_cypher_readonly`) return JSON whose node element ids we recover with the
shared `extract_node_ids` seam. This module resolves those ids back into
lightweight, bounded source dicts for citation.
"""

from __future__ import annotations

from ...shared.kernel.settings import get_settings
from ..ontology.tools import _run_readonly_query


def _excerpt(value, limit: int) -> str:
    """Return a bounded string excerpt of an arbitrary node value."""

    if value is None:
        return ""
    text = value if isinstance(value, str) else str(value)
    if len(text) > limit:
        return text[:limit] + "…"
    return text


def resolve_sources(node_ids, scores: dict | None = None) -> list[dict]:
    """Resolve Neo4j element ids into cited source records.

    Each record: ``{node_id, labels, name, excerpt, score?}``. Deduplicated by
    element id (order preserved). Excerpts are bounded by ``mcp_max_excerpt_chars``.
    Unknown or unresolvable ids are skipped rather than fabricated.
    """

    settings = get_settings()
    limit = settings.mcp_max_excerpt_chars
    scores = scores or {}

    unique_ids = list(dict.fromkeys([nid for nid in (node_ids or []) if nid]))
    if not unique_ids:
        return []

    try:
        rows = _run_readonly_query(
            """
            MATCH (n)
            WHERE elementId(n) IN $ids
            RETURN elementId(n) AS node_id,
                   [l IN labels(n) WHERE l <> '_Entity'] AS labels,
                   coalesce(n.name, n.title, toString(n.number)) AS name,
                   coalesce(toString(n.content), toString(n.title), toString(n.name), '') AS content
            """,
            {"ids": unique_ids},
        )
    except Exception:
        return []

    by_id = {row["node_id"]: row for row in rows}
    sources: list[dict] = []
    for nid in unique_ids:
        row = by_id.get(nid)
        if not row:
            continue
        record = {
            "node_id": nid,
            "labels": row.get("labels") or [],
            "name": row.get("name") or "",
            "excerpt": _excerpt(row.get("content"), limit),
        }
        if nid in scores:
            record["score"] = scores[nid]
        sources.append(record)
    return sources


class NodeRecorder:
    """Accumulates node element ids referenced by answer-tool results during a run.

    Walk the final agent messages (or feed tool outputs incrementally) and this
    recorder recovers every referenced node id using the shared extraction seam,
    preserving first-seen order.
    """

    def __init__(self) -> None:
        self._ids: list[str] = []
        self._seen: set[str] = set()

    def record(self, content: str, tool_name: str = "") -> None:
        """Record node ids surfaced by a single tool result string."""

        from ..agent_session.service import extract_node_ids

        for nid in extract_node_ids(content, tool_name):
            if nid not in self._seen:
                self._seen.add(nid)
                self._ids.append(nid)

    def record_messages(self, messages) -> None:
        """Record node ids from every ToolMessage in an agent result."""

        for msg in messages or []:
            content = getattr(msg, "content", None)
            name = getattr(msg, "name", "") or ""
            # ToolMessages carry a name; only they hold tool JSON worth scanning.
            if content is None or getattr(msg, "type", "") not in ("tool", "ToolMessage"):
                # Fall back to duck-typing: a ToolMessage has a tool_call_id.
                if not hasattr(msg, "tool_call_id"):
                    continue
            text = content if isinstance(content, str) else str(content)
            self.record(text, name)

    @property
    def node_ids(self) -> list[str]:
        return list(self._ids)
