"""Build review candidates from SCADA config and authored teaching documents.

Deterministic preparation, not an LLM extraction result. Semantic mappings are
explicit and reviewable; Ontology Studio's agent remains a separate build path.
"""
import hashlib
import re
import yaml
from pathlib import Path

from export_inventory import export_inventory

root = Path(__file__).resolve().parents[2]
prefix = "AR-100/reactor-line-01"


def build() -> dict:
    """번들 A: 등록부 인벤토리 + 교육 문서(섹션) + 검토한 설비 관계."""
    batch = export_inventory(root / "shared/registry/equipment.yaml")

    for filename in sorted((root / "5_ai" / "manuals").glob("*.md")):
        text = filename.read_text(encoding="utf-8")
        doc_id = filename.stem
        front = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
        metadata = yaml.safe_load(front.group(1)) if front else {}
        batch["nodes"].append({"id": doc_id, "class": "Document", "properties": {
            "name": doc_id, "source_path": f"5_ai/manuals/{filename.name}",
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
                "source_locator": f"section:{index}", "source_path": f"5_ai/manuals/{filename.name}",
            }})
            batch["relationships"].append({"from_id": doc_id, "to_id": section_id, "type": "HAS_SECTION"})

    # 설비 의미 연결: 등록부의 모든 설비(제어기 제외)와 그 신호. 물리 배치(INSTALLED_IN)와 물질 흐름(FEEDS)은 검토한 관계다.
    reg = yaml.safe_load((root / "shared/registry/equipment.yaml").read_text(encoding="utf-8"))
    for asset in reg["assets"]:
        if asset["type"] == "Controller":
            continue
        aid = f"{prefix}/asset/{asset['id']}"
        batch["nodes"].append({"id": aid, "class": "Asset", "properties": {
            "name": asset["id"], "description": asset["name"], "equipment_type": asset["type"], "site": "AR-100",
            "device": "reactor-line-01", "environment": "simulation", "source_path": "shared/registry/equipment.yaml",
        }})
        batch["relationships"].append({"from_id": prefix, "to_id": aid, "type": "EXPOSES_ASSET"})
        for sig in asset.get("signals", []):
            batch["relationships"].append({"from_id": aid, "to_id": f"{prefix}/sensor/{sig['tag']}", "type": "HAS_SENSOR"})
        batch["relationships"].append({"from_id": aid, "to_id": "AR100-ASSET-CONTEXT", "type": "DESCRIBED_BY"})
        batch["relationships"].append({"from_id": aid, "to_id": "AR100-MAINT-POLICY", "type": "GOVERNED_BY"})
    a = lambda name: f"{prefix}/asset/{name}"
    batch["relationships"].extend([
        {"from_id": a("M-101"), "to_id": a("R-101"), "type": "INSTALLED_IN"},
        {"from_id": a("HX-101"), "to_id": a("R-101"), "type": "INSTALLED_IN"},
        {"from_id": a("HX-102"), "to_id": a("R-101"), "type": "INSTALLED_IN"},
        {"from_id": a("ST-103"), "to_id": a("HX-102"), "type": "INSTALLED_IN"},
        {"from_id": a("CV-101"), "to_id": a("R-101"), "type": "INSTALLED_IN"},
        {"from_id": a("TK-101"), "to_id": a("P-101"), "type": "FEEDS"},
        {"from_id": a("P-101"), "to_id": a("R-101"), "type": "FEEDS"},
        {"from_id": a("M-101"), "to_id": "AR100-MIXER-RESPONSE", "type": "HAS_PROCEDURE"},
        {"from_id": a("M-101"), "to_id": "AR100-EVIDENCE-POLICY", "type": "GOVERNED_BY"},
        {"from_id": a("R-101"), "to_id": "AR100-EVIDENCE-POLICY", "type": "GOVERNED_BY"},
    ])
    batch["unresolved"] = ["교육용 절차이며 실물 설비 승인 문서가 아님"]
    return batch
