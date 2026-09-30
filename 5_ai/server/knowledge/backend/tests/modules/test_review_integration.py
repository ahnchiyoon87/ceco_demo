"""Real Neo4j transactional publication checks."""
from uuid import uuid4

import pytest
from fastapi import HTTPException
from pydantic import ValidationError

from backend.src.modules.ontology.review import Batch, Publish, publish
from backend.src.modules.ontology.tools import get_driver


def test_publish_retains_text_and_rejects_stale_review():
    uid = f"review-test-{uuid4()}"
    batch = Batch.model_validate({"nodes": [{"id": uid, "class": "VerificationProbe", "properties": {"content": "근거" * 1500}}], "relationships": []})
    digest = batch.digest()
    try:
        with pytest.raises(HTTPException) as error:
            publish(Publish(batch=batch, expected_sha256="0"*64, review_note="검증용 변경된 검토 해시"))
        assert error.value.status_code == 409
        assert publish(Publish(batch=batch, expected_sha256=digest, review_note="검증용 데이터 길이 확인"))["duplicate"] is False
        assert publish(Publish(batch=batch, expected_sha256=digest, review_note="검증용 재전송 확인"))["duplicate"] is True
        with get_driver().session() as session:
            row = session.run("MATCH (n:_Entity {_source_id:$id}) RETURN n.content AS content", id=uid).single()
            assert row["content"] == "근거" * 1500
    finally:
        with get_driver().session() as session:
            session.run("MATCH (n:_Entity {_source_id:$id}) DETACH DELETE n", id=uid).consume()
            session.run("MATCH (b:_ImportBatch {sha256:$digest}) DETACH DELETE b", digest=digest).consume()


def test_invalid_topology_is_rejected_before_writes():
    with pytest.raises(ValidationError, match="endpoint"):
        Batch.model_validate({"nodes": [{"id": "probe", "class": "Asset", "properties": {}}],
                              "relationships": [{"from_id": "probe", "to_id": "missing", "type": "HAS_SENSOR"}]})


def test_reserved_internal_labels_cannot_be_published():
    with pytest.raises(ValidationError, match="Internal graph labels"):
        Batch.model_validate({"nodes": [{"id": "probe", "class": "_ImportBatch", "properties": {}}], "relationships": []})


def test_late_database_failure_rolls_back_earlier_node():
    uid = f"rollback-test-{uuid4()}"
    batch = Batch.model_validate({"nodes": [
        {"id": uid, "class": "VerificationProbe", "properties": {"name": "must rollback"}},
        {"id": uid+"-invalid", "class": "VerificationProbe", "properties": {"oversized_integer": 2**100}},
    ], "relationships": []})
    with pytest.raises((OverflowError, ValueError)):
        publish(Publish(batch=batch, expected_sha256=batch.digest(), review_note="검증용 원자적 실패 확인"))
    with get_driver().session() as session:
        assert session.run("MATCH (n:_Entity {_source_id:$id}) RETURN count(n) AS count", id=uid).single()["count"] == 0
        assert session.run("MATCH (b:_ImportBatch {sha256:$digest}) RETURN count(b) AS count", digest=batch.digest()).single()["count"] == 0


def test_older_document_cannot_replace_published_version():
    uid=f"version-test-{uuid4()}"
    current=Batch.model_validate({"nodes":[{"id":uid,"class":"Document","properties":{"version":3,"content":"Current reviewed version"}}],"relationships":[]})
    older=Batch.model_validate({"nodes":[{"id":uid,"class":"Document","properties":{"version":2,"content":"Older source"}}],"relationships":[]})
    try:
        publish(Publish(batch=current,expected_sha256=current.digest(),review_note="Integration version three"))
        with pytest.raises(HTTPException) as error:
            publish(Publish(batch=older,expected_sha256=older.digest(),review_note="Must reject older source"))
        assert error.value.status_code==409
        with get_driver().session() as session:
            row=session.run("MATCH (n:Document {_source_id:$id}) RETURN n.version AS version,n.content AS content",id=uid).single()
            assert row["version"]==3 and row["content"]=="Current reviewed version"
            assert session.run("MATCH (b:_ImportBatch {sha256:$digest}) RETURN count(b) AS count",digest=older.digest()).single()["count"]==0
    finally:
        with get_driver().session() as session:
            session.run("MATCH (n:_Entity {_source_id:$id}) DETACH DELETE n",id=uid).consume()
            session.run("MATCH (b:_ImportBatch) WHERE b.sha256 IN $digests DETACH DELETE b",digests=[current.digest(),older.digest()]).consume()
