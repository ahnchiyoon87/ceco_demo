"""Export the equipment registry as reviewable ontology input.

소스 = 설비 등록부(registry/equipment.yaml, HANDOFF §2-2 확장). 단위·규격·설명의 정본이 등록부다.
IT 에 있는 지식 그래프에는 Modbus 레지스터 주소를 넣지 않는다(17번 E8: 주소는 IT 에 드러내지 않는다).
No asset membership or maintenance procedures are inferred from tag names.
Output is a candidate dataset, not a published ontology or live telemetry.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

import yaml


def export_inventory(source: Path) -> dict:
    raw = source.read_bytes()
    config = yaml.safe_load(raw)
    h = config["hierarchy"]
    site, device = h["site"], h["line"]
    prefix = f"{site}/{device}"
    provenance = {
        "source_path": "registry/equipment.yaml",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "review_status": "candidate",
        "environment": "simulation",
    }
    nodes = [{"id": prefix, "class": "Device", "properties": {
        **provenance, "name": device, "site": site, "area": h["area"],
    }}]
    relationships = []
    seen = set()
    for asset in config["assets"]:
        for sig in asset.get("signals", []):
            name = sig["tag"]
            if name in seen:
                raise ValueError(f"Duplicate tag: {name}")
            seen.add(name)
            node_id = f"{prefix}/sensor/{name}"
            nodes.append({"id": node_id, "class": "Sensor", "properties": {
                **provenance, "name": name, "description": sig["desc"], "unit": sig["unit"],
                "lsl": sig.get("lsl"), "usl": sig.get("usl"), "equipment_id": asset["id"],
                "source_locator": f"assets[id={asset['id']}].signals[tag={name}]",
            }})
            relationships.append({"from_id": prefix, "to_id": node_id, "type": "EXPOSES_SENSOR"})
        for cmd in asset.get("commands", []):
            if "legacy" not in cmd:
                continue   # 제어기 자체 명령(모드·정비)은 설비 제어점이 아니다
            node_id = f"{prefix}/point/{cmd['legacy']}"
            nodes.append({"id": node_id, "class": "ControlPoint", "properties": {
                **provenance, "name": cmd["legacy"], "description": cmd["desc"], "equipment_id": asset["id"],
                "command": cmd["name"], "readonly": False,
                "source_locator": f"assets[id={asset['id']}].commands[name={cmd['name']}]",
            }})
            relationships.append({"from_id": prefix, "to_id": node_id, "type": "EXPOSES_POINT"})
    for wm in config.get("work_masters", []):
        node_id = f"{prefix}/work-master/{wm['id']}"
        nodes.append({"id": node_id, "class": "WorkMaster", "properties": {
            **provenance, "name": wm["id"], "description": wm["desc"], "equipment_id": wm["equipment_id"],
            "source_locator": f"work_masters[id={wm['id']}]",
        }})
        relationships.append({"from_id": prefix, "to_id": node_id, "type": "OFFERS_WORK"})
    return {
        "schema_version": 1, "status": "candidate",
        "nodes": nodes, "relationships": relationships,
        "unresolved": [
            "Explicit asset-to-sensor membership requires review.",
            "A control point or work master does not grant AI execution permission; requests pass OT acceptance and PLC checks.",
            "Alarm logic is in Flink SQL; tag limits alone are not the alarm contract.",
        ],
    }
