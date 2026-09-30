"""Build review candidates from SCADA config and authored teaching documents.

Deterministic preparation, not an LLM extraction result. Semantic mappings are
explicit and reviewable; Ontology Studio's agent remains a separate build path.
"""
import hashlib
import json
import re
import yaml
from pathlib import Path

from export_inventory import export_inventory

root = Path(__file__).resolve().parents[1]
prefix = "AR-100/reactor-line-01"


def build() -> dict:
    """번들 A: 등록부 인벤토리 + 교육 문서(섹션) + 검토한 설비 관계."""
    batch = export_inventory(root / "registry/equipment.yaml")

    for filename in sorted((root / "knowledge-docs").glob("*.md")):
        text = filename.read_text(encoding="utf-8")
        doc_id = filename.stem
        front = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
        metadata = yaml.safe_load(front.group(1)) if front else {}
        batch["nodes"].append({"id": doc_id, "class": "Document", "properties": {
            "name": doc_id, "source_path": f"knowledge-docs/{filename.name}",
            "source_sha256": hashlib.sha256(filename.read_bytes()).hexdigest(),
            "version": metadata.get("version"), "environment": "simulation", "content": text,
        }})
        body = re.sub(r"\A---\n.*?\n---\n", "", text, count=1, flags=re.S)
        sections = re.split(r"(?m)^## ", body)
        for index, section in enumerate(sections):
            heading = section.splitlines()[0].lstrip("# ") if section.splitlines() else doc_id
            section_id = f"{doc_id}/section/{index}"
            batch["nodes"].append({"id": section_id, "class": "DocumentSection", "properties": {
                "name": heading, "content": section, "document_id": doc_id,
                "source_locator": f"section:{index}", "source_path": f"knowledge-docs/{filename.name}",
            }})
            batch["relationships"].append({"from_id": doc_id, "to_id": section_id, "type": "HAS_SECTION"})

    for asset, description, tags in [
        ("M-101", "교반기", ["IT-102", "VT-101"]),
        ("R-101", "반응기", ["LT-102", "TT-101", "PT-101"]),
    ]:
        aid = f"{prefix}/asset/{asset}"
        batch["nodes"].append({"id": aid, "class": "Asset", "properties": {
            "name": asset, "description": description, "site": "AR-100", "device": "reactor-line-01",
            "environment": "simulation", "source_path": "knowledge-docs/AR100-ASSET-CONTEXT.md",
        }})
        batch["relationships"].append({"from_id": prefix, "to_id": aid, "type": "EXPOSES_ASSET"})
        for tag in tags:
            batch["relationships"].append({"from_id": aid, "to_id": f"{prefix}/sensor/{tag}", "type": "HAS_SENSOR"})
        batch["relationships"].append({"from_id": aid, "to_id": "AR100-ASSET-CONTEXT", "type": "DESCRIBED_BY"})
    batch["relationships"].extend([
        {"from_id": f"{prefix}/asset/M-101", "to_id": f"{prefix}/asset/R-101", "type": "INSTALLED_IN"},
        {"from_id": f"{prefix}/asset/M-101", "to_id": "AR100-MIXER-RESPONSE", "type": "HAS_PROCEDURE"},
        {"from_id": f"{prefix}/asset/M-101", "to_id": "AR100-EVIDENCE-POLICY", "type": "GOVERNED_BY"},
    ])
    batch["unresolved"] = ["교육용 절차이며 실물 설비 승인 문서가 아님", "P-101 등 나머지 설비 의미 연결은 미포함"]
    return batch


if __name__ == "__main__":
    batch = build()
    output = root / "docs/ai-work/knowledge-candidates.json"
    output.write_text(json.dumps(batch, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"{len(batch['nodes'])} nodes, {len(batch['relationships'])} relationships; review required")
