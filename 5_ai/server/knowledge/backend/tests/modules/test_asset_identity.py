import json
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.src.modules.ontology.review import Batch, Publish, publish, reconcile_assets
from backend.src.modules.ontology.tools import get_driver


def candidate(asset_id="old"):
    return Batch.model_validate({"nodes": [
        {"id": "site/device", "class": "Device", "properties": {"site": "site", "name": "device"}},
        {"id": asset_id, "class": "Asset", "properties": {"site": "site", "device": "device", "name": "M-101", "source_excerpt": "Exact original quotation retained."}}
    ], "relationships": [{"from_id": asset_id, "to_id": "site/device", "type": "INSTALLED_IN"}]})


def test_reconcile_preserves_source_and_rewrites_endpoints_without_mutating_original():
    original = candidate()
    result = reconcile_assets(original)
    assert result["identity_changes"] == {"old": "site/device/asset/M-101"}
    assert result["batch"]["relationships"][0]["from_id"] == "site/device/asset/M-101"
    props = result["batch"]["nodes"][1]["properties"]
    assert props["source_excerpt"] == original.nodes[1].properties["source_excerpt"]
    assert props["review_original_id"] == "old"
    assert original.nodes[1].id == "old"
    assert reconcile_assets(Batch.model_validate(result["batch"]))["identity_changes"] == {}


def test_reconcile_does_not_guess_missing_device():
    batch = candidate()
    batch.nodes[1].properties["device"] = "unknown"
    with pytest.raises(HTTPException) as error:
        reconcile_assets(batch)
    assert error.value.status_code == 422


def test_concurrent_different_ids_cannot_publish_the_same_asset():
    site = f"identity-test-{uuid4()}"
    batches = [Batch.model_validate({"nodes": [{"id": site+suffix, "class": "Asset",
        "properties": {"site": site, "device": "line", "name": "M-101"}}], "relationships": []}) for suffix in ("/a", "/b")]
    def attempt(batch):
        try:
            publish(Publish(batch=batch, expected_sha256=batch.digest(), review_note="Concurrent identity integration test"))
            return "published"
        except HTTPException as error:
            assert error.status_code == 409
            return "conflict"
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            assert sorted(pool.map(attempt, batches)) == ["conflict", "published"]
        with get_driver().session() as session:
            assert session.run("MATCH (n:Asset {site:$site}) RETURN count(n) AS count", site=site).single()["count"] == 1
    finally:
        with get_driver().session() as session:
            session.run("MATCH (n:Asset {site:$site}) DETACH DELETE n", site=site).consume()
            session.run("MATCH (b:_ImportBatch) WHERE b.sha256 IN $digests DETACH DELETE b", digests=[b.digest() for b in batches]).consume()
            session.run("MATCH (i:_AssetIdentity {key:$key}) DETACH DELETE i", key=json.dumps((site,"line","M-101"), ensure_ascii=False)).consume()
