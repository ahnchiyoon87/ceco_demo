"""Reviewed transactional variant of Ontology Studio batch_ingest.

Retains upstream node/relationship contract, replaces partial writes and text
truncation with preflight validation and one Neo4j transaction.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field, model_validator

from .tools import get_driver

router = APIRouter(prefix="/api/knowledge", tags=["knowledge-review"])
Identifier = str
SCALAR_PROPERTIES_SCHEMA = {"additionalProperties": {"anyOf": [
    {"type": "string"}, {"type": "integer"}, {"type": "number"},
    {"type": "boolean"}, {"type": "null"},
]}}


class Node(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    id: str = Field(min_length=1, max_length=300)
    class_name: str = Field(alias="class", pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    properties: dict[str, Any] = Field(json_schema_extra=SCALAR_PROPERTIES_SCHEMA)

    @model_validator(mode="after")
    def valid_properties(self):
        if self.class_name.startswith("_"):
            raise ValueError("Internal graph labels cannot be imported")
        for key, value in self.properties.items():
            if key.startswith("_"):
                raise ValueError("Reserved property name")
            if value is not None and type(value) not in (str, int, float, bool):
                raise ValueError("Only scalar properties are supported in reviewed import")
            if isinstance(value, float):
                import math
                if not math.isfinite(value):
                    raise ValueError("Non-finite property")
        return self


class Relationship(BaseModel):
    model_config = ConfigDict(extra="forbid")
    from_id: str
    to_id: str
    type: str = Field(pattern=r"^[A-Za-z_][A-Za-z0-9_]*$")
    properties: dict[str, Any] = Field(default_factory=dict, json_schema_extra=SCALAR_PROPERTIES_SCHEMA)

    @model_validator(mode="after")
    def valid_properties(self):
        # Apply the same scalar/protected-property contract as nodes.
        Node(id="validation", **{"class": "Validation"}, properties=self.properties)
        return self


class Batch(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int = 1
    status: str = "candidate"
    nodes: list[Node] = Field(min_length=1, max_length=1000)
    relationships: list[Relationship] = Field(max_length=5000)
    unresolved: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def valid_topology(self):
        ids = [node.id for node in self.nodes]
        if len(set(ids)) != len(ids):
            raise ValueError("Duplicate node IDs")
        known = set(ids)
        for rel in self.relationships:
            if rel.from_id not in known or rel.to_id not in known:
                raise ValueError("Every relationship endpoint must be in this reviewed batch")
        if len({(r.from_id, r.to_id, r.type) for r in self.relationships}) != len(self.relationships):
            raise ValueError("Duplicate relationship")
        return self

    def canonical(self):
        return json.dumps(self.model_dump(by_alias=True), sort_keys=True, ensure_ascii=False, separators=(",", ":"))

    def digest(self):
        return hashlib.sha256(self.canonical().encode()).hexdigest()


class Publish(BaseModel):
    batch: Batch
    expected_sha256: str = Field(pattern=r"^[a-f0-9]{64}$")
    review_note: str = Field(min_length=5, max_length=2000)


@router.post("/preview")
def preview(batch: Batch):
    return {"sha256": batch.digest(), "node_count": len(batch.nodes),
            "relationship_count": len(batch.relationships), "unresolved": batch.unresolved,
            "batch": batch.model_dump(by_alias=True)}


@router.post("/reconcile-assets")
def reconcile_assets(batch: Batch):
    """Resolve declared asset identity against this batch's explicit devices, never infer membership."""
    data = batch.model_dump(by_alias=True)
    devices = [n for n in data["nodes"] if n["class"] == "Device"]
    changes = {}
    for node in data["nodes"]:
        if node["class"] != "Asset":
            continue
        props = node["properties"]
        if not all(isinstance(props.get(k), str) and props[k].strip() for k in ("site", "device", "name")):
            raise HTTPException(422, f"{node['id']}: site, device, name을 먼저 확인하세요. 소속을 추정하지 않았습니다.")
        matches = [d for d in devices if (d["properties"].get("site"), d["properties"].get("name")) == (props["site"], props["device"])]
        if len(matches) != 1:
            raise HTTPException(422, f"{node['id']}: 일치하는 상위 Device가 하나여야 합니다. 소속을 확인하세요.")
        canonical = f"{matches[0]['id']}/asset/{props['name']}"
        if node["id"] != canonical:
            changes[node["id"]] = canonical
            props["review_original_id"] = node["id"]
            props["identity_review_method"] = "explicit-site-device-name"
            node["id"] = canonical
    for rel in data["relationships"]:
        rel["from_id"] = changes.get(rel["from_id"], rel["from_id"])
        rel["to_id"] = changes.get(rel["to_id"], rel["to_id"])
    try:
        checked = Batch.model_validate(data)
    except ValueError as exc:
        raise HTTPException(422, "동일한 설비 식별자로 합쳐지는 후보가 있습니다. 속성·관계를 검토해 중복 후보를 정리하세요.") from exc
    return preview(checked) | {"identity_changes": changes}


@router.post("/publish")
def publish(request: Publish):
    batch, digest = request.batch, request.batch.digest()
    if digest != request.expected_sha256:
        raise HTTPException(409, "검토한 내용과 게시할 내용이 달라졌습니다. 다시 검토하세요.")
    driver = get_driver()
    with driver.session() as session:
        for statement in (
            "CREATE CONSTRAINT entity_source_unique IF NOT EXISTS FOR (n:_Entity) REQUIRE n._source_id IS UNIQUE",
            "CREATE CONSTRAINT import_digest_unique IF NOT EXISTS FOR (n:_ImportBatch) REQUIRE n.sha256 IS UNIQUE",
            "CREATE CONSTRAINT asset_identity_unique IF NOT EXISTS FOR (n:_AssetIdentity) REQUIRE n.key IS UNIQUE",
        ):
            # First concurrent publications may race on schema locks. Neo4j's
            # managed transaction retries transient deadlocks; no equipment IO.
            session.execute_write(lambda tx: tx.run(statement).consume())

        def transaction(tx):
            # MERGE obtains a write lock, serializing publication of the same digest.
            record = tx.run("""MERGE (b:_ImportBatch {sha256:$digest})
                ON CREATE SET b.status='pending'
                SET b.locked_at=datetime() RETURN b.status AS status""", digest=digest).single()
            if record["status"] == "published":
                return {"status": "published", "sha256": digest, "duplicate": True}
            identities = set()
            for node in batch.nodes:
                if node.class_name != "Asset":
                    continue
                props = node.properties
                identity = tuple(props.get(k) for k in ("site", "device", "name"))
                if not all(isinstance(v, str) and v.strip() for v in identity):
                    raise HTTPException(422, f"{node.id}: 설비의 site, device, name이 필요합니다.")
                if identity in identities:
                    raise HTTPException(409, "같은 설비를 가리키는 후보가 중복되었습니다. 식별자를 검토하세요.")
                identities.add(identity)
                # Lock the natural identity as well as the batch digest: different
                # simultaneous batches must not create two IDs for one asset.
                tx.run("MERGE (i:_AssetIdentity {key:$key}) SET i.locked_at=datetime()",
                       key=json.dumps(identity, ensure_ascii=False)).consume()
                duplicate = tx.run("""MATCH (a:_Entity:Asset {site:$site,device:$device,name:$name})
                    WHERE a._source_id <> $id RETURN a._source_id AS id LIMIT 1""",
                    site=identity[0], device=identity[1], name=identity[2], id=node.id).single()
                if duplicate:
                    raise HTTPException(409, f"{node.id}: 이미 게시된 동일 설비 {duplicate['id']}가 있습니다. 설비 식별자를 정리한 뒤 다시 검토하세요.")
            for node in batch.nodes:
                if node.class_name == "Document":
                    existing = tx.run("MERGE (n:_Entity:Document {_source_id:$id}) SET n._review_lock=datetime() RETURN n.version AS version", id=node.id).single()
                    old_version = existing["version"] if existing else None
                    new_version = node.properties.get("version")
                    if isinstance(old_version, int) and (not isinstance(new_version, int) or new_version < old_version):
                        raise HTTPException(409, f"{node.id}: 게시된 문서보다 오래되었거나 버전이 없습니다. 최신 원본을 확인하세요.")
                tx.run(f"""MERGE (n:_Entity:{node.class_name} {{_source_id:$id}})
                    SET n += $properties, n._batch_id=$digest, n._review_status='published', n.updated_at=datetime()
                    WITH n MATCH (b:_ImportBatch {{sha256:$digest}})
                    MERGE (b)-[:IMPORTED]->(n)""",
                    id=node.id, properties=node.properties, digest=digest).consume()
            for rel in batch.relationships:
                tx.run(f"""MATCH (a:_Entity {{_source_id:$source}}), (b:_Entity {{_source_id:$target}})
                    MERGE (a)-[r:{rel.type}]->(b) SET r += $properties, r._batch_id=$digest""",
                    source=rel.from_id, target=rel.to_id, properties=rel.properties, digest=digest).consume()
            tx.run("""MATCH (b:_ImportBatch {sha256:$digest}) SET b.status='published',
                b.payload=$payload, b.review_note=$note, b.published_at=datetime()""",
                digest=digest, payload=batch.canonical(), note=request.review_note).consume()
            return {"status": "published", "sha256": digest, "duplicate": False,
                    "nodes": len(batch.nodes), "relationships": len(batch.relationships)}
        return session.execute_write(transaction)


@router.get("/published")
def published():
    try:
        with get_driver().session() as session:
            rows = session.run("""MATCH (b:_ImportBatch {status:'published'})
                RETURN b.sha256 AS sha256, b.review_note AS review_note,
                toString(b.published_at) AS published_at
                ORDER BY b.published_at DESC LIMIT 100""").data()
        return {"items": rows, "limit": 100}
    except Exception as exc:
        raise HTTPException(503, "지식 게시 이력을 조회할 수 없습니다.") from exc


@router.get("/structure")
def structure():
    """Observed class topology of published entities, not an inferred domain standard."""
    try:
        with get_driver().session() as session:
            classes = session.run("""MATCH (n:_Entity) WHERE n._batch_id IS NOT NULL
                UNWIND labels(n) AS label WITH n,label WHERE NOT label STARTS WITH '_'
                RETURN label AS name,count(n) AS count ORDER BY name""").data()
            relationships = session.run("""MATCH (a:_Entity)-[r]->(b:_Entity)
                WHERE r._batch_id IS NOT NULL
                UNWIND labels(a) AS source UNWIND labels(b) AS target
                WITH r,source,target WHERE NOT source STARTS WITH '_' AND NOT target STARTS WITH '_'
                RETURN DISTINCT type(r) AS name,source AS from_class,target AS to_class
                ORDER BY name,from_class,to_class""").data()
        return {"classes": classes, "relationships": relationships,
                "source": "게시된 엔티티와 관계에서 집계한 클래스 구조"}
    except Exception as exc:
        raise HTTPException(503, "게시된 클래스 구조를 조회할 수 없습니다.") from exc
