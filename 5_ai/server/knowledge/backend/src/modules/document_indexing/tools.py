"""Agent tools for hybrid retrieval over OCR-indexed chunks."""

from __future__ import annotations

import json

from .service import DocumentIndexingService

_service = DocumentIndexingService()

# Max characters per source_text in tool results to conserve context window
_MAX_SOURCE_TEXT_CHARS = 500


def _compact_results(results: list[dict]) -> list[dict]:
    """Trim source_text and remove heavy score fields to save tokens."""
    compacted = []
    for hit in results:
        entry = {
            "chunk_id": hit.get("chunk_id"),
            "chunk_ref": hit.get("chunk_ref"),
            "document_id": hit.get("document_id"),
            "source_page": hit.get("source_page"),
        }
        source_text = hit.get("source_text", "")
        if len(source_text) > _MAX_SOURCE_TEXT_CHARS:
            entry["source_text"] = source_text[:_MAX_SOURCE_TEXT_CHARS] + "…[truncated]"
        else:
            entry["source_text"] = source_text
        compacted.append(entry)
    return compacted


def hybrid_search_chunks(
    query: str,
    top_k: int = 5,
    target_node_ids: str = "[]",
    document_ids: str = "[]",
    chunk_refs: str = "[]",
    source_pages: str = "[]",
) -> str:
    """Return hybrid BM25 + vector chunk search results fused with RRF."""

    try:
        effective_top_k = min(max(1, int(top_k)), 5)
        results = _service.hybrid_search(
            query=query,
            top_k=effective_top_k,
            target_node_ids=json.loads(target_node_ids) if target_node_ids else [],
            document_ids=json.loads(document_ids) if document_ids else [],
            chunk_refs=json.loads(chunk_refs) if chunk_refs else [],
            source_pages=json.loads(source_pages) if source_pages else [],
        )
        return json.dumps(_compact_results(results), ensure_ascii=False, default=str)
    except Exception as exc:  # pragma: no cover - passthrough error handling
        return json.dumps({"error": str(exc)}, ensure_ascii=False)
