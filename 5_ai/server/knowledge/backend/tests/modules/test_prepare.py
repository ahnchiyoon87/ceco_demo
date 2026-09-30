"""Preparation contract tests; no model inference is claimed."""
import hashlib

import pytest
from fastapi import HTTPException

from backend.src.modules.ontology import prepare


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    monkeypatch.setattr(prepare, "get_local_upload_root", lambda: tmp_path)
    monkeypatch.setattr(prepare, "list_local_upload_files", lambda: list(tmp_path.iterdir()))
    return tmp_path


def test_explicit_config_and_document_structure_with_original_provenance(workspace):
    config = workspace / "plant.yaml"
    config.write_text("""site: TEST
device: line
scan_interval_ms: 1000
tags:
  - {name: TT-101, desc: temperature, unit: C, hr: 0}
commands: {coils: {}, holding: {}}
""", encoding="utf-8")
    doc = workspace / "procedure.md"
    doc.write_text("---\ndocument_id: test-procedure\nversion: 3\n---\n# Check\n\n## Inspect\nRecord evidence.\n", encoding="utf-8")
    result = prepare.prepare(prepare.Prepare(filenames=[config.name, doc.name]))
    nodes = result["batch"]["nodes"]
    assert result["preparation"] == "deterministic-structure-extraction"
    assert not any(node["class"] == "Asset" for node in nodes)
    sensor = next(node for node in nodes if node["class"] == "Sensor")
    assert sensor["properties"]["source_sha256"] == hashlib.sha256(config.read_bytes()).hexdigest()
    assert sensor["properties"]["source_path"] == "uploads/plant.yaml"
    document = next(node for node in nodes if node["class"] == "Document")
    assert document["properties"]["version"] == 3
    assert document["properties"]["content"] == doc.read_text(encoding="utf-8")
    assert any(rel["type"] == "HAS_SECTION" for rel in result["batch"]["relationships"])
    assert result["unresolved"]


@pytest.mark.parametrize("kind", ["unsupported", "malformed", "duplicate_id", "traversal"])
def test_invalid_source_is_explicit_not_silently_omitted(workspace, kind):
    if kind == "traversal":
        names = ["../private.txt"]
    elif kind == "unsupported":
        (workspace / "manual.pdf").write_bytes(b"not a parser-supported input")
        names = ["manual.pdf"]
    elif kind == "malformed":
        (workspace / "broken.yaml").write_text("missing: required_keys", encoding="utf-8")
        names = ["broken.yaml"]
    else:
        for name in ("a.md", "b.md"):
            (workspace / name).write_text("---\ndocument_id: same-id\n---\n# Duplicate", encoding="utf-8")
        names = ["a.md", "b.md"]
    with pytest.raises(HTTPException) as exc:
        prepare.prepare(prepare.Prepare(filenames=names))
    assert exc.value.status_code in {404, 422}
