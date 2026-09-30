"""Read-only tools on the fault ontology (v2 model): fault tracing and manual section search.

The graph returns candidate failure modes, how each can be checked and the
current observations those checks name. It never evaluates a check or decides
a status; the agent judges from observations (ontology/v2/PROTOCOL.md §2).
New failure types are graph data published through the reviewed import path.
"""
from __future__ import annotations

import os
import time

from fastapi import APIRouter, HTTPException

from ..ontology.tools import _run_query, _run_readonly_query, ensure_vector_index, get_driver
from .evidence import history, live_state

router = APIRouter(prefix="/api/operations/v2", tags=["manufacturing-v2"])
SECTION_INDEX = "section_embedding_v2"
EMBED_MODEL = os.environ.get("EMBEDDING_MODEL", "text-embedding-3-small")


def signatures(detail):
    """Alarm signatures (alert_type, tag) of every stored alarm in the incident."""
    return sorted({(e["payload"]["alert_type"], e["payload"]["tag"]) for e in detail["events"]
                   if e["kind"] in {"alarm_received", "alarm_correlated"}})


def trace(site, device, sigs):
    """Symptom → failure mode → cause → check → sensor/command, with documents and actions."""
    rows = _run_readonly_query("""
        MATCH (sig:AlarmSignature)-[:INDICATES]->(sym:Symptom)
        WHERE any(s IN $sigs WHERE s[0] = sig.alert_type AND s[1] = sig.tag)
        WITH DISTINCT sym
        MATCH (sym)-[:OBSERVED_ON]->(asset:Asset {site:$site, device:$device})
        MATCH (fm:FailureMode)-[:MANIFESTS_AS]->(sym)
        RETURN sym.symptom_id AS symptom, sym.name AS symptom_name, asset.name AS asset,
          COLLECT { MATCH (sym)-[:INVESTIGATED_BY]->(d:DocumentSection) RETURN d.document_id + '#' + d.section_key } AS investigation,
          fm.failure_mode_id AS failure_mode, fm.name AS name,
          COLLECT { MATCH (fm)-[:AFFECTS]->(t) RETURN t.name } AS affects,
          COLLECT { MATCH (fm)-[:HAS_CAUSE]->(c:Cause) RETURN c.name } AS causes,
          COLLECT { MATCH (fm)-[:CHECKED_BY]->(k:Check)
                    RETURN {text: k.text, observable: k.observable, field_check: k.field_check,
                            tags: COLLECT { MATCH (k)-[:OBSERVES]->(s:Sensor) RETURN s.name },
                            commands: COLLECT { MATCH (k)-[:READS_COMMAND]->(p:ControlPoint) RETURN p.name }} } AS checks,
          COLLECT { MATCH (fm)-[:DOCUMENTED_IN]->(d:DocumentSection) RETURN d.document_id + '#' + d.section_key } AS sections,
          COLLECT { MATCH (a:Action)-[:MITIGATES]->(sym)
                    RETURN {action: a.action_id,
                            procedure: COLLECT { MATCH (a)-[:PROCEDURE]->(d:DocumentSection) RETURN d.document_id + '#' + d.section_key }} } AS actions
        ORDER BY symptom, failure_mode""", {"sigs": [list(s) for s in sigs], "site": site, "device": device})
    return rows


def observed_values(site, device, tags):
    """Latest stored observation per tag named by the ontology checks."""
    if not tags:
        return {}
    now = time.time_ns()
    result = history(site, device, sorted(tags), now - 30_000_000_000, now)
    latest = {}
    for row in result.get("rows", []):
        latest[row["tag"]] = row
    limits = {r["tag"]: r for r in _run_readonly_query(
        """MATCH (s:Sensor) WHERE s.name IN $tags RETURN s.name AS tag, s.unit AS unit, s.lsl AS lsl, s.usl AS usl""",
        {"tags": sorted(tags)})}
    return {"status": result.get("status"), "window": "최근 30초", "source": result.get("source"),
            "latest": {tag: {**latest.get(tag, {"value": None, "quality": "MISSING"}), **limits.get(tag, {})}
                       for tag in sorted(tags)}}


def fault_context(site, device, sigs):
    candidates = trace(site, device, sigs)
    tags = {t for c in candidates for k in c["checks"] for t in k["tags"]}
    plant = live_state()
    return {"alarm_signatures": [list(s) for s in sigs], "candidates": candidates,
            "check_observations": observed_values(site, device, tags),
            "plant_commands": plant.get("commands"), "interlock": plant.get("interlock"),
            "plant_status": plant.get("status"), "retrieved_at": plant.get("retrieved_at"),
            "method": ("Graph lookup only. Checks are explanations to apply to the observations; "
                       "the graph does not decide supported/refuted/unknown/not_applicable."),
            "empty_meaning": "No candidates means no failure knowledge is published for these alarm signatures, not that the plant is normal."}


def _embedder():
    """매뉴얼 절 임베딩: OpenAI 호환 API(OPENAI_BASE_URL · EMBEDDING_MODEL)."""
    from neo4j_graphrag.embeddings import OpenAIEmbeddings
    return OpenAIEmbeddings(model=EMBED_MODEL, base_url=os.environ.get("OPENAI_BASE_URL") or None,
                            api_key=os.environ.get("OPENAI_API_KEY"))


def index_sections():
    """(Re)embed DocumentSection text whose content changed; failures raise instead of storing zeros."""
    rows = _run_query("""MATCH (d:DocumentSection) WHERE d.content IS NOT NULL
        AND (d.v2_embedding IS NULL OR d.v2_embedded_hash IS NULL OR d.v2_embedded_hash <> toString(size(d.content)) + ':' + d.name
             OR coalesce(d.v2_embed_model, '') <> $m)
        RETURN elementId(d) AS id, d.name AS name, d.content AS content""", {"m": EMBED_MODEL})
    embedder = _embedder()
    for row in rows:
        vector = embedder.embed_query(f"{row['name']}\n{row['content']}")
        if not vector or not any(vector):
            raise RuntimeError("임베딩 결과가 비었습니다. 색인하지 않았습니다.")
        _run_query("""MATCH (d) WHERE elementId(d)=$id SET d.v2_embedding=$v,
            d.v2_embedded_hash=toString(size(d.content)) + ':' + d.name, d.v2_embed_model=$m""",
                   {"id": row["id"], "v": vector, "m": EMBED_MODEL})
    dims = _run_query("MATCH (d:DocumentSection) WHERE d.v2_embedding IS NOT NULL RETURN size(d.v2_embedding) AS n LIMIT 1")
    if dims:
        ensure_vector_index(SECTION_INDEX, "DocumentSection", "v2_embedding", dims[0]["n"])
    return {"embedded": len(rows), "index": SECTION_INDEX}


RETRIEVAL_QUERY = """
WITH node, score
OPTIONAL MATCH p = (node)<-[:DOCUMENTED_IN|PROCEDURE|INVESTIGATED_BY]-(x)-[:MANIFESTS_AS|MITIGATES*0..1]->(sym:Symptom)
WHERE sym.symptom_id IN $symptoms
RETURN node.document_id + '#' + node.section_key AS section, node.name AS heading,
       node.content AS content, score, count(p) > 0 AS graph_linked
"""


def search(query, symptoms, top_k=3, candidates=10):
    """Vector search over manual sections, then sections linked in the graph to the incident's symptoms first."""
    from neo4j_graphrag.retrievers import VectorCypherRetriever
    from neo4j_graphrag.types import RetrieverResultItem
    retriever = VectorCypherRetriever(get_driver(), index_name=SECTION_INDEX, retrieval_query=RETRIEVAL_QUERY,
                                      embedder=_embedder(),
                                      result_formatter=lambda record: RetrieverResultItem(content=dict(record)))
    found = retriever.search(query_text=query, top_k=candidates, query_params={"symptoms": symptoms})
    rows = [item.content for item in found.items]
    ranked = sorted(rows, key=lambda r: (not r["graph_linked"], -r["score"]))
    return {"query": query, "results": ranked[:top_k], "vector_only": sorted(rows, key=lambda r: -r["score"])[:top_k],
            "method": "vector top-%d, graph-linked sections first, then vector score" % candidates}


@router.post("/index")
def rebuild_index():
    try:
        return index_sections()
    except Exception as exc:
        raise HTTPException(503, f"절 색인 실패 ({type(exc).__name__}). 임베딩 서버와 그래프를 확인하세요.") from exc


@router.get("/trace")
def trace_endpoint(site: str, device: str, alert_type: str, tag: str):
    return fault_context(site, device, [(alert_type, tag)])


@router.get("/search")
def search_endpoint(q: str, symptoms: str = "", top_k: int = 3):
    return search(q, [s for s in symptoms.split(",") if s], top_k)
