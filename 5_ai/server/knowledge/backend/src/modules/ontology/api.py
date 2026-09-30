"""HTTP API for ontology schema and graph queries."""

from __future__ import annotations

import json

from fastapi import APIRouter, HTTPException, Query

from pydantic import BaseModel

from .tools import (
    get_driver,
    entity_create,
    relationship_create,
    schema_create_class,
    schema_create_relationship_type,
    schema_delete_class,
    schema_delete_relationship_type,
    schema_get,
    _run_query,
)

router = APIRouter(tags=["ontology"])


def _normalize_graph_value(value):
    """Convert Neo4j values into JSON-friendly scalars/collections."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (list, tuple, set)):
        return [_normalize_graph_value(item) for item in value]
    if isinstance(value, dict):
        return {key: _normalize_graph_value(item) for key, item in value.items()}
    return str(value)


def _normalize_graph_properties(entity) -> dict:
    """Normalize graph entity properties for API responses."""

    return {
        key: _normalize_graph_value(value)
        for key, value in dict(entity).items()
    }


def _entity_label(node) -> str:
    """Pick the best display label for a Neo4j entity node."""

    d = dict(node)
    return (
        d.get("name")
        or d.get("title")
        or d.get("_source_id")
        or ""
    )


@router.get("/api/neo4j/status")
async def neo4j_status():
    """Report Neo4j connectivity status."""

    try:
        driver = get_driver()
        driver.verify_connectivity()
        return {"status": "connected"}
    except Exception as exc:  # pragma: no cover - passthrough error handling
        return {"status": "disconnected", "error": str(exc)}


@router.get("/api/schema")
async def get_schema_endpoint():
    """Return the current ontology schema."""

    try:
        result = schema_get()
        return json.loads(result)
    except Exception as exc:  # pragma: no cover - passthrough error handling
        return {"classes": [], "relationships": [], "error": str(exc)}


class ClassBody(BaseModel):
    name: str
    original_name: str = ""
    description: str = ""
    properties: list[dict] = []
    schema_name: str = ""


class RelationshipBody(BaseModel):
    name: str
    from_class: str
    to_class: str
    description: str = ""
    properties: list[dict] = []
    schema_name: str = ""


@router.put("/api/schema/classes")
async def upsert_class(body: ClassBody):
    """Create or update an ontology class. If original_name differs from name, rename the class."""

    from ..agent_session.session_store import rename_class_in_all_schemas

    # If renaming (original_name provided and different from name)
    if body.original_name and body.original_name != body.name:
        rename_class_in_all_schemas(body.original_name, body.name)
        # Rename Neo4j entity labels: remove old label, add new label
        try:
            _run_query(
                f"MATCH (n:_Entity:{body.original_name}) REMOVE n:{body.original_name} SET n:{body.name}",
            )
        except Exception:
            pass  # entities may not exist yet

    result = schema_create_class(
        body.name, body.description,
        json.dumps(body.properties, ensure_ascii=False),
        body.schema_name,
    )
    return json.loads(result)


@router.delete("/api/schema/classes/{class_name:path}")
async def delete_class(class_name: str):
    """Delete an ontology class and its related relationship types."""
    result = schema_delete_class(class_name)
    return json.loads(result)


@router.put("/api/schema/relationships")
async def upsert_relationship(body: RelationshipBody):
    """Create or update a relationship type."""
    result = schema_create_relationship_type(
        body.name, body.from_class, body.to_class,
        body.description,
        json.dumps(body.properties, ensure_ascii=False),
        body.schema_name,
    )
    return json.loads(result)


@router.delete("/api/schema/relationships/{rel_name:path}")
async def delete_relationship(rel_name: str, from_class: str = "", to_class: str = ""):
    """Delete a relationship type."""
    result = schema_delete_relationship_type(rel_name, from_class, to_class)
    return json.loads(result)


class EntityBody(BaseModel):
    class_name: str
    properties: dict = {}
    match_keys: list[str] = ["name"]


class RelInstanceBody(BaseModel):
    from_id: str
    to_id: str
    rel_type: str
    properties: dict = {}


@router.post("/api/graph/entities")
async def create_entity(body: EntityBody):
    """Create a single entity instance."""
    result = entity_create(
        body.class_name,
        json.dumps(body.properties, ensure_ascii=False),
        json.dumps(body.match_keys),
    )
    return json.loads(result)


class EntityUpdateBody(BaseModel):
    properties: dict = {}


@router.patch("/api/graph/entities/{element_id:path}")
async def update_entity(element_id: str, body: EntityUpdateBody):
    """Update properties of an existing entity."""
    try:
        driver = get_driver()
        props = body.properties
        if not props:
            return {"status": "ok"}
        set_clause = ", ".join(f"n.{k} = ${k}" for k in props.keys())
        query = f"MATCH (n) WHERE elementId(n) = $id SET {set_clause}, n.updated_at = datetime() RETURN n"
        params = {"id": element_id, **props}
        with driver.session() as session:
            result = session.run(query, params)
            record = result.single()
            if record:
                node = record["n"]
                return {"status": "ok", "entity": dict(node)}
        return {"status": "not_found"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@router.delete("/api/graph/entities/{element_id:path}")
async def delete_entity(element_id: str):
    """Delete a single entity by Neo4j element ID."""
    try:
        driver = get_driver()
        with driver.session() as session:
            session.run("MATCH (n) WHERE elementId(n) = $id DETACH DELETE n", {"id": element_id})
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "error", "message": str(exc)}


@router.post("/api/graph/relationships")
async def create_relationship_instance(body: RelInstanceBody):
    """Create a relationship between two entities."""
    result = relationship_create(body.from_id, body.to_id, body.rel_type, json.dumps(body.properties, ensure_ascii=False))
    return json.loads(result)


@router.post("/api/neo4j/clear-all")
async def clear_all_neo4j():
    """Delete all ontology schema, entities, relationships, documents, and chunks."""

    try:
        driver = get_driver()
        with driver.session() as session:
            # Delete all relationships first, then all nodes
            session.run("MATCH ()-[r]->() DELETE r")
            session.run("MATCH (n) DETACH DELETE n")
        return {"status": "ok", "message": "Neo4j 데이터가 모두 삭제되었습니다."}
    except Exception as exc:  # pragma: no cover
        return {"status": "error", "error": str(exc)}


@router.get("/api/schemas")
async def list_schemas_endpoint():
    """Return all ontology schema groups with class lists and entity counts."""

    from ..agent_session.session_store import list_schemas

    try:
        schemas = list_schemas()
        # Enrich with Neo4j entity counts
        driver = get_driver()
        for schema in schemas:
            total = 0
            for cls in schema.get("classes", []):
                try:
                    with driver.session() as sess:
                        result = sess.run(
                            f"MATCH (n:_Entity:{cls['class_name']}) RETURN count(n) AS cnt"
                        ).single()
                        cnt = result["cnt"] if result else 0
                        cls["entity_count"] = cnt
                        total += cnt
                except Exception:
                    cls["entity_count"] = 0
            schema["total_entity_count"] = total
        return {"schemas": schemas}
    except Exception as exc:
        return {"schemas": [], "error": str(exc)}


@router.get("/api/schemas/{schema_id}")
async def get_schema_detail(schema_id: str):
    """Return a single schema group detail."""

    from ..agent_session.session_store import get_schema

    schema = get_schema(schema_id)
    if not schema:
        return {"error": "스키마를 찾을 수 없습니다."}
    return schema


class SchemaBriefBody(BaseModel):
    intent: str = ""
    golden_questions: list[str] = []


@router.put("/api/schemas/{schema_id}/brief")
async def update_schema_brief_endpoint(schema_id: str, body: SchemaBriefBody):
    """Update the intent and golden questions for a schema."""
    from ..agent_session.session_store import update_schema_brief
    update_schema_brief(schema_id, body.intent, json.dumps(body.golden_questions, ensure_ascii=False))
    return {"status": "ok"}


@router.delete("/api/schemas/{schema_id}")
async def delete_schema_endpoint(schema_id: str):
    """Delete a schema group (metadata only, entities preserved)."""

    from ..agent_session.session_store import delete_schema

    try:
        delete_schema(schema_id)
        return {"status": "ok"}
    except Exception as exc:
        return {"error": str(exc)}


@router.delete("/api/schemas/{schema_id}/entities")
async def delete_schema_entities(schema_id: str):
    """Delete all Neo4j entities belonging to a schema's classes."""

    from ..agent_session.session_store import get_schema

    try:
        schema = get_schema(schema_id)
        if not schema:
            return {"error": "스키마를 찾을 수 없습니다."}

        class_names = [c["class_name"] for c in schema.get("classes", [])]
        if not class_names:
            return {"status": "ok", "deleted": 0}

        total_deleted = 0
        for cls_name in class_names:
            rows = _run_query(
                f"MATCH (n:_Entity:{cls_name}) DETACH DELETE n RETURN count(n) AS cnt"
            )
            total_deleted += rows[0]["cnt"] if rows else 0

        return {"status": "ok", "deleted": total_deleted}
    except Exception as exc:
        return {"error": str(exc)}


@router.post("/api/schemas/{schema_id}/rebuild")
async def rebuild_schema_in_neo4j(schema_id: str):
    """Schema is now fully in SQLite. This endpoint returns the schema info (no Neo4j rebuild needed)."""

    from ..agent_session.session_store import get_schema

    try:
        schema = get_schema(schema_id)
        if not schema:
            return {"error": "스키마를 찾을 수 없습니다."}
        return {
            "status": "ok",
            "classes": len(schema.get("classes", [])),
            "relationships": len(schema.get("relationships", [])),
        }
    except Exception as exc:
        return {"error": str(exc)}


@router.get("/api/graph")
async def get_graph(class_name: str = "", schema_name: str = "", limit: int = Query(100, ge=1, le=500)):
    """Return graph nodes and edges, optionally filtered by class."""

    try:
        # Resolve schema_name to class list if provided
        filter_classes = []
        if schema_name:
            from ..agent_session.session_store import get_schema_by_name
            schema = get_schema_by_name(schema_name)
            if schema:
                filter_classes = [c["class_name"] for c in schema.get("classes", [])]
            if not filter_classes:
                return {"nodes": [], "edges": []}

        driver = get_driver()
        with driver.session() as session:
            if class_name:
                result = session.run(
                    "MATCH (n:_Entity) WHERE $class IN labels(n) "
                    "OPTIONAL MATCH (n)-[r]->(m:_Entity) "
                    "RETURN n, r, m LIMIT $limit",
                    {"class": class_name, "limit": limit},
                )
            elif filter_classes:
                # Filter by schema's classes
                result = session.run(
                    "MATCH (n:_Entity) WHERE any(lbl IN labels(n) WHERE lbl IN $classes) "
                    "OPTIONAL MATCH (n)-[r]->(m:_Entity) "
                    "RETURN n, r, m LIMIT $limit",
                    {"classes": filter_classes, "limit": limit},
                )
            else:
                result = session.run(
                    "MATCH (n:_Entity) "
                    "OPTIONAL MATCH (n)-[r]->(m:_Entity) "
                    "RETURN n, r, m LIMIT $limit",
                    {"limit": limit},
                )

            nodes = {}
            edges = []
            for record in result:
                node = record["n"]
                if node and node.element_id not in nodes:
                    nodes[node.element_id] = {
                        "id": node.element_id,
                        "label": _entity_label(node),
                        "labels": list(node.labels),
                        "properties": _normalize_graph_properties(node),
                    }

                matched_node = record["m"]
                if matched_node and matched_node.element_id not in nodes:
                    nodes[matched_node.element_id] = {
                        "id": matched_node.element_id,
                        "label": _entity_label(matched_node),
                        "labels": list(matched_node.labels),
                        "properties": _normalize_graph_properties(matched_node),
                    }

                relationship = record["r"]
                if relationship:
                    edges.append(
                        {
                            "from": relationship.start_node.element_id,
                            "to": relationship.end_node.element_id,
                            "type": relationship.type,
                            "properties": _normalize_graph_properties(relationship),
                        }
                    )

        return {"nodes": list(nodes.values()), "edges": edges}
    except Exception as exc:  # pragma: no cover - passthrough error handling
        raise HTTPException(503, "그래프를 조회하지 못했습니다. 연결 상태를 확인하세요.") from exc


@router.get("/api/graph/search")
async def search_graph(q: str = "", class_name: str = "", limit: int = Query(50, ge=1, le=500)):
    """Text search across entity properties (name, title, content, _source_id)."""

    if not q.strip():
        return {"nodes": [], "edges": []}

    try:
        driver = get_driver()
        with driver.session() as session:
            query = """
            MATCH (n:_Entity)
            WHERE ($class = '' OR $class IN labels(n)) AND (
                  toLower(toString(n.name)) CONTAINS toLower($q)
               OR toLower(toString(n.title)) CONTAINS toLower($q)
               OR toLower(toString(n.content)) CONTAINS toLower($q)
               OR toLower(toString(n._source_id)) CONTAINS toLower($q))
            RETURN n LIMIT $limit
            """
            result = session.run(query, {"q": q.strip(), "class": class_name, "limit": limit})
            nodes = {}
            for record in result:
                node = record["n"]
                nodes[node.element_id] = {
                    "id": node.element_id,
                    "label": _entity_label(node),
                    "labels": list(node.labels),
                    "properties": _normalize_graph_properties(node),
                }
            return {"nodes": list(nodes.values()), "edges": []}
    except Exception as exc:
        raise HTTPException(503, "그래프 검색에 실패했습니다. 연결 상태를 확인하세요.") from exc


class NLQueryBody(BaseModel):
    question: str
    schema_hint: str = ""


@router.post("/api/graph/nl-query")
async def nl_to_cypher_query(body: NLQueryBody):
    """Convert natural language to Cypher query using LLM, execute it, return results."""

    import urllib.request as _urllib_request
    from ...shared.kernel.settings import get_settings

    settings = get_settings()

    # Build schema context for LLM
    schema_hint = body.schema_hint
    if not schema_hint:
        try:
            schema_result = json.loads(schema_get())
            classes = schema_result.get("classes", [])
            rels = schema_result.get("relationships", [])
            parts = ["Classes:"]
            for c in classes[:20]:
                props = ", ".join(f"{p['name']}:{p.get('type','string')}" for p in (c.get("properties") or []))
                parts.append(f"  :{c['name']} ({props})")
            parts.append("Relationships:")
            for r in rels[:20]:
                parts.append(f"  (:{r['from_class']})-[:{r['name']}]->(:{r['to_class']})")
            schema_hint = "\n".join(parts)
        except Exception:
            schema_hint = ""

    # Call LLM to generate Cypher
    base_url = settings.openai_base_url or "https://api.openai.com/v1"
    model = settings.minor_model.replace("openai:", "")

    llm_payload = json.dumps({
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a Neo4j Cypher expert. Convert the user's natural language question into a READ-ONLY Cypher query.\n"
                    "All entity nodes have the label _Entity plus their class label (e.g. _Entity:Person).\n"
                    "Return ONLY the Cypher query, no explanation.\n"
                    "Always use RETURN and LIMIT (max 50).\n"
                    f"Schema:\n{schema_hint}"
                ),
            },
            {"role": "user", "content": body.question},
        ],
        "max_tokens": 300,
        "temperature": 0.0,
    }).encode("utf-8")

    req = _urllib_request.Request(
        f"{base_url}/chat/completions",
        data=llm_payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {settings.openai_api_key}",
        },
    )

    try:
        with _urllib_request.urlopen(req, timeout=30) as resp:
            llm_data = json.loads(resp.read().decode("utf-8"))
            cypher = llm_data["choices"][0]["message"]["content"].strip()
            # Clean up markdown code blocks
            if cypher.startswith("```"):
                cypher = "\n".join(cypher.split("\n")[1:])
            if cypher.endswith("```"):
                cypher = cypher[:-3].strip()
    except Exception as exc:
        return {"error": f"LLM 호출 실패: {exc}", "cypher": "", "nodes": [], "edges": []}

    # Validate readonly
    from .tools import _is_readonly_cypher
    if not _is_readonly_cypher(cypher):
        return {"error": "생성된 쿼리가 읽기 전용이 아닙니다.", "cypher": cypher, "nodes": [], "edges": []}

    # Execute
    try:
        driver = get_driver()
        with driver.session() as session:
            result = session.run(cypher)
            nodes = {}
            edges = []
            for record in result:
                for value in record.values():
                    if hasattr(value, 'element_id') and hasattr(value, 'labels'):
                        # Node
                        if value.element_id not in nodes:
                            nodes[value.element_id] = {
                                "id": value.element_id,
                                "label": _entity_label(value),
                                "labels": list(value.labels),
                                "properties": _normalize_graph_properties(value),
                            }
                    elif hasattr(value, 'type') and hasattr(value, 'nodes'):
                        # Relationship
                        edges.append({
                            "from": value.nodes[0].element_id,
                            "to": value.nodes[1].element_id,
                            "type": value.type,
                        })
            return {"cypher": cypher, "nodes": list(nodes.values()), "edges": edges}
    except Exception as exc:
        return {"error": f"Cypher 실행 실패: {exc}", "cypher": cypher, "nodes": [], "edges": []}


@router.get("/api/graph/neighbors")
async def get_neighbors(node_id: str, depth: int = Query(1, ge=1, le=3)):
    """Explore both relationship directions to the requested depth, without APOC.

    Return at most 500 paths and explicitly report truncation. Depth is bounded
    at the API and checked here because it forms part of the Cypher syntax.
    """
    if type(depth) is not int or not 1 <= depth <= 3:
        raise HTTPException(422, "탐색 깊이는 1~3이어야 합니다.")
    try:
        from neo4j import Query as NeoQuery
        driver = get_driver()
        with driver.session() as session:
            records = list(session.run(NeoQuery(
                "MATCH (n:_Entity) WHERE elementId(n) = $node_id "
                f"MATCH p=(n)-[*0..{depth}]-(m:_Entity) "
                "WHERE all(item IN nodes(p) WHERE item:_Entity) "
                "RETURN p LIMIT 501", timeout=10), {"node_id": node_id}))
        nodes, edges = {}, {}
        for record in records[:500]:
            path = record["p"]
            for node in path.nodes:
                nodes[node.element_id] = {
                    "id": node.element_id, "label": _entity_label(node),
                    "labels": list(node.labels),
                    "properties": _normalize_graph_properties(node),
                }
            for rel in path.relationships:
                edges[rel.element_id] = {
                    "id": rel.element_id, "from": rel.start_node.element_id,
                    "to": rel.end_node.element_id, "type": rel.type,
                    "properties": _normalize_graph_properties(rel),
                }
        return {"nodes": list(nodes.values()), "edges": list(edges.values()),
                "depth": depth, "direction": "both", "truncated": len(records) > 500,
                "path_limit": 500}
    except Exception as exc:
        raise HTTPException(503, "인접 관계를 조회하지 못했습니다. 다시 연결한 뒤 조회하세요.") from exc


# Explicit product surface: upstream editing and model-generated Cypher routes
# remain as reference code, but are not registered by the manufacturing host.
# New upstream routes are deliberately not exposed automatically.
read_router = APIRouter(tags=["ontology-read"])
for path, endpoint in (
    ("/api/neo4j/status", neo4j_status),
    ("/api/schema", get_schema_endpoint),
    ("/api/graph", get_graph),
    ("/api/graph/search", search_graph),
    ("/api/graph/neighbors", get_neighbors),
):
    read_router.add_api_route(path, endpoint, methods=["GET"])
