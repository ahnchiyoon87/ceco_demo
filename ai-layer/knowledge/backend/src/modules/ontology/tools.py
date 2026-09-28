"""Neo4j-backed ontology tools and repository helpers."""

from __future__ import annotations

import json
import re
from typing import Any

from neo4j import GraphDatabase, READ_ACCESS

from ...shared.kernel.settings import get_settings

_driver = None
_READONLY_CYPHER_FORBIDDEN = re.compile(
    r"\b(CREATE|MERGE|DELETE|DETACH|SET|REMOVE|DROP|FOREACH|CALL)\b|LOAD\s+CSV",
    re.IGNORECASE,
)
_CYPHER_COMMENT_PATTERN = re.compile(r"//.*?$|/\*.*?\*/", re.MULTILINE | re.DOTALL)


def get_driver():
    """Return a singleton Neo4j driver."""

    global _driver
    if _driver is None:
        settings = get_settings()
        _driver = GraphDatabase.driver(
            settings.neo4j_uri,
            auth=(settings.neo4j_user, settings.neo4j_password),
            connection_timeout=3,
            connection_acquisition_timeout=5,
            max_transaction_retry_time=5,
        )
    return _driver


def _run_query(query: str, params: dict | None = None) -> list[dict]:
    """Execute a Cypher query and return row dictionaries."""

    driver = get_driver()
    with driver.session() as session:
        result = session.run(query, params or {})
        return [record.data() for record in result]


def _run_readonly_query(query: str, params: dict | None = None) -> list[dict]:
    """Execute a read-only Cypher query and return row dictionaries.

    Automatically injects ``_element_id`` for any returned Node values
    so that downstream graph visualisation can highlight them.
    If no full Node is returned, attempts to inject elementId via query rewrite.
    """

    from neo4j.graph import Node

    driver = get_driver()
    with driver.session(default_access_mode=READ_ACCESS) as session:
        result = session.run(query, params or {})
        rows = []
        has_node_obj = False
        for record in result:
            row = record.data()
            for _key, val in record.items():
                if isinstance(val, Node):
                    row["_element_id"] = val.element_id
                    has_node_obj = True
                    break
            rows.append(row)

        # If no Node objects in results but query MATCHes nodes,
        # inject elementId by rewriting the RETURN clause
        if rows and not has_node_obj and "_element_id" not in rows[0]:
            eid_rows = _try_inject_element_ids(query, params, session)
            if eid_rows and len(eid_rows) == len(rows):
                for row, eid_row in zip(rows, eid_rows):
                    if "_element_id" in eid_row:
                        row["_element_id"] = eid_row["_element_id"]
            elif eid_rows:
                # Length mismatch - just use eid_rows to build a lookup
                for eid_row in eid_rows:
                    eid = eid_row.get("_element_id")
                    if eid:
                        # Attach to first row without element_id
                        for row in rows:
                            if "_element_id" not in row:
                                row["_element_id"] = eid
                                break

        return rows


def _try_inject_element_ids(
    query: str, params: dict | None, session
) -> list[dict]:
    """Try to run a companion query that adds elementId to each matched node."""

    import re as _re

    # Find the first node variable in MATCH clause (e.g. MATCH (n:...) )
    match = _re.search(r"MATCH\s*\((\w+)", query, _re.IGNORECASE)
    if not match:
        return []
    node_var = match.group(1)

    # Build a companion query: same MATCH/WHERE but RETURN elementId(n)
    # Find everything before RETURN
    return_idx = _re.search(r"\bRETURN\b", query, _re.IGNORECASE)
    if not return_idx:
        return []

    prefix = query[:return_idx.start()]
    companion = f"{prefix} RETURN elementId({node_var}) AS _element_id"
    # Preserve LIMIT if present
    limit_match = _re.search(r"\bLIMIT\s+\d+", query, _re.IGNORECASE)
    if limit_match:
        companion += f" {limit_match.group(0)}"

    try:
        result = session.run(companion, params or {})
        return [record.data() for record in result]
    except Exception:
        return []


def _node_to_dict(node) -> dict:
    """Convert a Neo4j node into a serializable dictionary."""

    if node is None:
        return {}
    if isinstance(node, dict):
        return dict(node)
    if not hasattr(node, "element_id"):
        try:
            return dict(node)
        except Exception:
            return {"value": node}
    return {"id": node.element_id, "labels": list(node.labels), **dict(node)}


_MAX_TOOL_RESULT_CHARS = 3000  # max chars for serialized tool results


def _serialize_rows(rows: list[dict], max_chars: int = _MAX_TOOL_RESULT_CHARS) -> str:
    """Serialize Neo4j rows into JSON-friendly dictionaries, truncating if needed."""

    serialized = []
    for row in rows:
        serialized_row = {}
        for key, value in row.items():
            if hasattr(value, "element_id"):
                serialized_row[key] = _node_to_dict(value)
            elif hasattr(value, "type"):
                serialized_row[key] = {"type": value.type, **dict(value)}
            else:
                serialized_row[key] = value
        serialized.append(serialized_row)
    result = json.dumps(serialized, ensure_ascii=False, default=str)
    if len(result) > max_chars:
        return result[:max_chars] + '..."truncated"]'
    return result


def _is_readonly_cypher(query: str) -> bool:
    """Return True when the Cypher query avoids mutating clauses."""

    sanitized = re.sub(_CYPHER_COMMENT_PATTERN, " ", query or "")
    return _READONLY_CYPHER_FORBIDDEN.search(sanitized) is None


def neo4j_cypher(query: str, params: str = "{}") -> str:
    """Execute an arbitrary Cypher query against Neo4j."""

    try:
        parsed_params = json.loads(params) if params else {}
        rows = _run_query(query, parsed_params)
        return _serialize_rows(rows)
    except Exception as exc:  # pragma: no cover - passthrough error handling
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def neo4j_cypher_readonly(query: str, params: str = "{}") -> str:
    """Execute a read-only Cypher query against Neo4j."""

    try:
        if not query.strip():
            return json.dumps({"error": "query is required"}, ensure_ascii=False)
        if not _is_readonly_cypher(query):
            return json.dumps(
                {
                    "error": (
                        "읽기 전용 조회만 허용됩니다. "
                        "MATCH, OPTIONAL MATCH, WHERE, WITH, RETURN 중심의 Cypher만 사용하세요."
                    )
                },
                ensure_ascii=False,
            )
        parsed_params = json.loads(params) if params else {}
        rows = _run_readonly_query(query, parsed_params)
        return _serialize_rows(rows)
    except Exception as exc:  # pragma: no cover - passthrough error handling
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def schema_create_class(
    name: str,
    description: str = "",
    properties: str = "[]",
    schema_name: str = "",
) -> str:
    """Create or update an ontology class in SQLite (source of truth). schema_name is required."""

    from ..agent_session.session_store import (
        add_class_to_schema,
        find_schemas_for_class,
        get_schema_by_name,
    )

    try:
        props = json.loads(properties) if properties else []
        result: dict[str, Any] = {"status": "ok", "class": {"name": name, "description": description}}

        # SQLite is the source of truth for schema definitions
        if schema_name:
            schema = get_schema_by_name(schema_name)
            if schema:
                # Check for merge: does this class exist in other schemas?
                existing_schemas = find_schemas_for_class(name)
                other_schemas = [s for s in existing_schemas if s["name"] != schema_name]
                if other_schemas:
                    result["merge_warning"] = (
                        f"클래스 '{name}'이(가) 이미 스키마 "
                        f"'{', '.join(s['name'] for s in other_schemas)}'에 존재합니다. "
                        f"병합되었습니다."
                    )
                add_class_to_schema(
                    schema["id"], name, description,
                    json.dumps(props, ensure_ascii=False),
                )
            else:
                result["warning"] = f"스키마 '{schema_name}'을(를) 찾을 수 없습니다."

        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as exc:  # pragma: no cover - passthrough error handling
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def schema_create_relationship_type(
    name: str,
    from_class: str,
    to_class: str,
    description: str = "",
    properties: str = "[]",
    schema_name: str = "",
) -> str:
    """Define an ontology relationship type in SQLite (source of truth)."""

    from ..agent_session.session_store import (
        add_relationship_to_schema,
        get_schema_by_name,
    )

    try:
        props = json.loads(properties) if properties else []
        result: dict[str, Any] = {
            "status": "ok",
            "relationship_type": {"name": name, "from_class": from_class, "to_class": to_class},
        }

        # SQLite is the source of truth
        if schema_name:
            schema = get_schema_by_name(schema_name)
            if schema:
                add_relationship_to_schema(
                    schema["id"], name, from_class, to_class,
                    description, json.dumps(props, ensure_ascii=False),
                )
            else:
                result["warning"] = f"스키마 '{schema_name}'을(를) 찾을 수 없습니다."

        return json.dumps(result, ensure_ascii=False, default=str)
    except Exception as exc:  # pragma: no cover - passthrough error handling
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def schema_delete_class(name: str) -> str:
    """Delete an ontology class from SQLite and its entity instances from Neo4j."""

    from ..agent_session.session_store import remove_class_from_all_schemas

    try:
        # Delete entity instances from Neo4j
        count_rows = _run_readonly_query(
            f"MATCH (n:_Entity:{name}) RETURN count(n) AS cnt",
            {},
        )
        entity_count = count_rows[0]["cnt"] if count_rows else 0
        if entity_count > 0:
            _run_query(f"MATCH (n:_Entity:{name}) DETACH DELETE n", {})

        # Remove from SQLite (source of truth)
        remove_class_from_all_schemas(name)
        return json.dumps(
            {"status": "ok", "deleted": name, "entities_deleted": entity_count},
            ensure_ascii=False,
        )
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def schema_delete_relationship_type(
    name: str, from_class: str, to_class: str,
) -> str:
    """Delete an ontology relationship type from SQLite."""

    from ..agent_session.session_store import remove_relationship_from_all_schemas

    try:
        remove_relationship_from_all_schemas(name, from_class, to_class)
        return json.dumps({"status": "ok", "deleted": name}, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def schema_get() -> str:
    """Return the full ontology schema from SQLite (source of truth)."""

    from ..agent_session.session_store import list_schemas as _list_schemas

    try:
        sqlite_schemas = _list_schemas()

        # Aggregate all unique classes and relationships across all schemas
        seen_classes: dict[str, dict] = {}
        seen_rels: set[tuple] = set()
        all_relationships: list[dict] = []

        for schema in sqlite_schemas:
            for cls in schema.get("classes", []):
                name = cls["class_name"]
                if name not in seen_classes:
                    seen_classes[name] = {
                        "name": name,
                        "description": cls.get("description", ""),
                        "properties": cls.get("properties", []),
                    }
            for rel in schema.get("relationships", []):
                key = (rel["name"], rel["from_class"], rel["to_class"])
                if key not in seen_rels:
                    seen_rels.add(key)
                    all_relationships.append({
                        "name": rel["name"],
                        "from_class": rel["from_class"],
                        "to_class": rel["to_class"],
                        "description": rel.get("description", ""),
                        "properties": rel.get("properties", []),
                    })

        schema_classes = sorted(seen_classes.values(), key=lambda c: c["name"])
        all_relationships.sort(key=lambda r: r["name"])

        return json.dumps(
            {
                "classes": schema_classes,
                "relationships": all_relationships,
                "schemas": [
                    {"name": s["name"], "description": s["description"],
                     "class_names": [c["class_name"] for c in s.get("classes", [])]}
                    for s in sqlite_schemas
                ],
            },
            ensure_ascii=False,
            default=str,
        )
    except Exception as exc:  # pragma: no cover - passthrough error handling
        return json.dumps(
            {"classes": [], "relationships": [], "schemas": [], "error": str(exc)},
            ensure_ascii=False,
        )


def entity_search(class_name: str, search_criteria: str) -> str:
    """Search existing entities by class and property filters."""

    try:
        raw_criteria = (search_criteria or "").strip()
        use_contains_for_name = False
        if not raw_criteria:
            return json.dumps([], ensure_ascii=False)

        try:
            criteria = json.loads(raw_criteria)
        except json.JSONDecodeError:
            parsed_pairs = {}
            for part in raw_criteria.split(","):
                if ":" not in part:
                    continue
                key, value = part.split(":", maxsplit=1)
                key = key.strip().strip("\"'")
                value = value.strip().strip("\"'")
                if key and value:
                    parsed_pairs[key] = value
            if parsed_pairs:
                criteria = parsed_pairs
            else:
                criteria = {"name": raw_criteria}
                use_contains_for_name = True

        if not criteria:
            return json.dumps([], ensure_ascii=False)

        conditions = []
        for key in criteria:
            if use_contains_for_name and key == "name":
                conditions.append(f"n.{key} CONTAINS ${key}")
            else:
                conditions.append(f"n.{key} = ${key}")
        query = f"""
        MATCH (n:_Entity:{class_name})
        WHERE {' AND '.join(conditions)}
        RETURN n
        LIMIT 10
        """
        rows = _run_query(query, criteria)
        entities = []
        for row in rows:
            node = row["n"]
            entities.append(_node_to_dict(node))
        return json.dumps(entities, ensure_ascii=False, default=str)
    except Exception as exc:  # pragma: no cover - passthrough error handling
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def entity_create(
    class_name: str,
    properties: str,
    match_keys: str = "[]",
) -> str:
    """Create or merge an entity instance."""

    try:
        props = json.loads(properties) if properties else {}
        keys = json.loads(match_keys) if match_keys else []

        merge_props = {key: props.get(key) for key in keys if key in props}
        if not merge_props:
            return json.dumps(
                {
                    "error": "match_keys에 해당하는 속성이 없습니다. "
                    "중복 방지를 위해 최소 1개 이상의 키를 지정하세요."
                },
                ensure_ascii=False,
            )

        set_clause = ", ".join(f"n.{key} = ${key}" for key in props.keys())
        merge_clause = ", ".join(f"{key}: $merge_{key}" for key in merge_props.keys())

        query = f"""
        MERGE (n:_Entity:{class_name} {{ {merge_clause} }})
        ON CREATE SET n.created_at = datetime()
        SET {set_clause},
            n.updated_at = datetime()
        RETURN n
        """

        params: dict[str, Any] = dict(props)
        params.update({f"merge_{key}": value for key, value in merge_props.items()})

        rows = _run_query(query, params)
        if rows:
            node = rows[0]["n"]
            return json.dumps(
                {"status": "ok", "entity": _node_to_dict(node)},
                ensure_ascii=False,
                default=str,
            )
        return json.dumps({"status": "ok"}, ensure_ascii=False)
    except Exception as exc:  # pragma: no cover - passthrough error handling
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def relationship_create(
    from_entity_id: str,
    to_entity_id: str,
    relationship_type: str,
    properties: str = "{}",
) -> str:
    """Create a relationship between two entities."""

    try:
        props = json.loads(properties) if properties else {}
        set_props = ""
        if props:
            assignments = [f"r.{key} = ${key}" for key in props.keys()]
            set_props = ", " + ", ".join(assignments)

        query = f"""
        MATCH (from_n:_Entity) WHERE elementId(from_n) = $from_entity_id
        MATCH (to_n:_Entity) WHERE elementId(to_n) = $to_entity_id
        MERGE (from_n)-[r:{relationship_type}]->(to_n)
        ON CREATE SET r.created_at = datetime()
        SET r.updated_at = datetime(){set_props}
        RETURN from_n, r, to_n
        """
        params = {
            "from_entity_id": from_entity_id,
            "to_entity_id": to_entity_id,
            **props,
        }

        rows = _run_query(query, params)
        if rows:
            rel = rows[0]["r"]
            return json.dumps(
                {"status": "ok", "relationship": {"type": rel.type, **dict(rel)}},
                ensure_ascii=False,
                default=str,
            )
        return json.dumps({"status": "ok"}, ensure_ascii=False)
    except Exception as exc:  # pragma: no cover - passthrough error handling
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def batch_ingest(nodes_json: str, schema_name: str = "") -> str:
    """Batch-ingest nodes and relationships from a parsed JSON file path or JSON string. If schema_name is provided, registers used classes in that SQLite schema group."""

    import os
    from pathlib import Path

    try:
        data_str = nodes_json.strip()

        # If it looks like a file path, read from sandbox or local
        if not data_str.startswith("{") and not data_str.startswith("["):
            file_path = Path(data_str)
            if file_path.exists():
                data_str = file_path.read_text(encoding="utf-8")
            elif data_str.startswith("/workspace/"):
                from ...shared.sandbox import get_sandbox_backend
                download = get_sandbox_backend().download_files([data_str])[0]
                if download.error or download.content is None:
                    return json.dumps({"error": f"파일을 읽을 수 없습니다: {data_str}"}, ensure_ascii=False)
                data_str = download.content.decode("utf-8")
            else:
                return json.dumps({"error": f"파일을 찾을 수 없습니다: {data_str}"}, ensure_ascii=False)

        data = json.loads(data_str)
        nodes = data.get("nodes", [])
        relationships = data.get("relationships", [])

        node_count = 0
        rel_count = 0
        errors = []

        # Ingest nodes
        for node in nodes:
            node_id = node.get("id", "")
            class_name = node.get("class", "")
            props = node.get("properties", {})
            parent_id = node.get("parent_id")

            if not class_name:
                errors.append(f"노드에 class가 없습니다: {node_id}")
                continue

            # Truncate content fields
            for key in list(props.keys()):
                if isinstance(props[key], str) and len(props[key]) > 2000:
                    props[key] = props[key][:2000] + "..."

            props["_source_id"] = node_id
            if parent_id:
                props["_parent_source_id"] = parent_id

            merge_clause = "_source_id: $_source_id"
            set_parts = ", ".join(f"n.{k} = ${k}" for k in props.keys())

            query = f"""
            MERGE (n:_Entity:{class_name} {{ {merge_clause} }})
            ON CREATE SET n.created_at = datetime()
            SET {set_parts}, n.updated_at = datetime()
            RETURN n
            """
            try:
                _run_query(query, props)
                node_count += 1
            except Exception as exc:
                errors.append(f"노드 {node_id}: {exc}")

        # Ingest parent-child CONTAINS relationships
        for node in nodes:
            parent_id = node.get("parent_id")
            if not parent_id:
                continue
            try:
                _run_query(
                    """
                    MATCH (parent:_Entity {_source_id: $parent_id})
                    MATCH (child:_Entity {_source_id: $child_id})
                    MERGE (parent)-[r:CONTAINS]->(child)
                    ON CREATE SET r.created_at = datetime()
                    SET r.updated_at = datetime()
                    """,
                    {"parent_id": parent_id, "child_id": node["id"]},
                )
                rel_count += 1
            except Exception as exc:
                errors.append(f"CONTAINS {parent_id}->{node['id']}: {exc}")

        # Ingest explicit relationships
        for rel in relationships:
            from_id = rel.get("from_id", "")
            to_id = rel.get("to_id", "")
            rel_type = rel.get("type", "RELATED_TO")
            rel_props = rel.get("properties", {})

            set_clause = ""
            if rel_props:
                assignments = [f"r.{k} = ${k}" for k in rel_props.keys()]
                set_clause = ", " + ", ".join(assignments)

            try:
                _run_query(
                    f"""
                    MATCH (a:_Entity {{_source_id: $from_id}})
                    MATCH (b:_Entity {{_source_id: $to_id}})
                    MERGE (a)-[r:{rel_type}]->(b)
                    ON CREATE SET r.created_at = datetime()
                    SET r.updated_at = datetime(){set_clause}
                    """,
                    {"from_id": from_id, "to_id": to_id, **rel_props},
                )
                rel_count += 1
            except Exception as exc:
                errors.append(f"관계 {from_id}-[{rel_type}]->{to_id}: {exc}")

        # Embed nodes and create vector index
        embed_count = 0
        try:
            embed_count = _embed_entity_nodes()
        except Exception as embed_exc:
            errors.append(f"임베딩: {embed_exc}")

        # Register used classes in SQLite schema group
        if schema_name:
            from ..agent_session.session_store import (
                add_class_to_schema,
                get_schema_by_name,
            )
            schema = get_schema_by_name(schema_name)
            if schema:
                used_classes = {n.get("class", "") for n in nodes if n.get("class")}
                for cls_name in used_classes:
                    add_class_to_schema(schema["id"], cls_name)

        result = {
            "status": "ok",
            "nodes_created": node_count,
            "relationships_created": rel_count,
            "nodes_embedded": embed_count,
        }
        if errors:
            result["errors"] = errors[:20]  # limit error output
        return json.dumps(result, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def _embed_entity_nodes(batch_size: int = 20) -> int:
    """Embed all _Entity nodes that don't have an embedding yet."""

    from .embedding import embed_texts, node_text_for_embedding

    # Get nodes without embeddings
    rows = _run_query("""
        MATCH (n:_Entity) WHERE n.embedding IS NULL
        RETURN elementId(n) AS eid,
               n.name AS name, n.title AS title,
               substring(toString(n.content), 0, 1500) AS content
        LIMIT 500
    """)
    if not rows:
        return 0

    # Build texts and embed in batches
    total_embedded = 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        texts = []
        for row in batch:
            parts = []
            if row.get("name"):
                parts.append(str(row["name"]))
            if row.get("title"):
                parts.append(str(row["title"]))
            if row.get("content"):
                parts.append(str(row["content"]))
            texts.append(" ".join(parts) if parts else " ")

        vectors = embed_texts(texts)

        for row, vec in zip(batch, vectors):
            if not vec or all(v == 0.0 for v in vec[:10]):
                continue
            _run_query(
                "MATCH (n:_Entity) WHERE elementId(n) = $eid SET n.embedding = $vec",
                {"eid": row["eid"], "vec": vec},
            )
            total_embedded += 1

    # Create vector index if not exists
    if total_embedded > 0:
        try:
            _run_query(f"""
                CREATE VECTOR INDEX entity_embedding_vector IF NOT EXISTS
                FOR (n:_Entity) ON (n.embedding)
                OPTIONS {{indexConfig: {{
                    `vector.dimensions`: {len(vectors[0])},
                    `vector.similarity_function`: 'cosine'
                }}}}
            """)
        except Exception:
            pass  # index may already exist with different config

    return total_embedded


def graph_stats() -> str:
    """Return graph-wide statistics: node counts by class, relationship counts by type."""

    try:
        node_stats = _run_readonly_query("""
            MATCH (n:_Entity)
            WITH [l IN labels(n) WHERE l <> '_Entity'] AS entity_labels
            UNWIND entity_labels AS label
            RETURN label AS class, count(*) AS count
            ORDER BY count DESC
        """)
        rel_stats = _run_readonly_query("""
            MATCH (:_Entity)-[r]->(:_Entity)
            RETURN type(r) AS type, count(*) AS count
            ORDER BY count DESC
        """)
        total_nodes = _run_readonly_query("MATCH (n:_Entity) RETURN count(n) AS total")
        total_rels = _run_readonly_query("MATCH (:_Entity)-[r]->(:_Entity) RETURN count(r) AS total")

        return json.dumps({
            "total_nodes": total_nodes[0]["total"] if total_nodes else 0,
            "total_relationships": total_rels[0]["total"] if total_rels else 0,
            "nodes_by_class": [{"class": r["class"], "count": r["count"]} for r in node_stats],
            "relationships_by_type": [{"type": r["type"], "count": r["count"]} for r in rel_stats],
        }, ensure_ascii=False)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def schema_group_create(name: str, description: str = "") -> str:
    """Create an ontology schema group in SQLite. Returns the schema metadata."""

    from ..agent_session.session_store import create_schema

    try:
        schema = create_schema(name, description)
        return json.dumps({"status": "ok", "schema": schema}, ensure_ascii=False, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def schema_group_list() -> str:
    """List all ontology schema groups with their classes and entity counts from Neo4j."""

    from ..agent_session.session_store import list_schemas as _list_schemas

    try:
        sqlite_schemas = _list_schemas()
        # Enrich with Neo4j entity counts per class
        for schema in sqlite_schemas:
            total_entities = 0
            for cls in schema.get("classes", []):
                try:
                    rows = _run_readonly_query(
                        f"MATCH (n:_Entity:{cls['class_name']}) RETURN count(n) AS cnt"
                    )
                    cnt = rows[0]["cnt"] if rows else 0
                    cls["entity_count"] = cnt
                    total_entities += cnt
                except Exception:
                    cls["entity_count"] = 0
            schema["total_entity_count"] = total_entities
        return json.dumps({"schemas": sqlite_schemas}, ensure_ascii=False, default=str)
    except Exception as exc:
        return json.dumps({"error": str(exc)}, ensure_ascii=False)


def vector_search(query: str, top_k: int = 3) -> str:
    """Search entity nodes by semantic similarity using HyDE vector embeddings."""

    from .embedding import hyde_embed

    try:
        query_vec = hyde_embed(query)
        if all(v == 0.0 for v in query_vec[:10]):
            return json.dumps({"error": "임베딩 생성 실패"}, ensure_ascii=False)

        rows = _run_readonly_query(
            """
            CALL db.index.vector.queryNodes('entity_embedding_vector', $top_k, $embedding)
            YIELD node, score
            RETURN elementId(node) AS node_id,
                   [l IN labels(node) WHERE l <> '_Entity'] AS classes,
                   node.title AS title,
                   node.name AS name,
                   node.number AS number,
                   substring(toString(node.content), 0, 500) AS content_preview,
                   score
            """,
            {"top_k": top_k, "embedding": query_vec},
        )
        return _serialize_rows(rows, max_chars=2000)
    except Exception as exc:
        error_msg = str(exc)
        if "no such index" in error_msg.lower() or "index not found" in error_msg.lower():
            return json.dumps({"error": "벡터 인덱스가 아직 생성되지 않았습니다. 먼저 온톨로지를 구축하세요."}, ensure_ascii=False)
        return json.dumps({"error": error_msg}, ensure_ascii=False)
