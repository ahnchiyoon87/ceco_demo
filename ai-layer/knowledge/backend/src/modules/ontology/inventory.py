"""Export observed SCADA configuration as reviewable ontology input.

No asset membership or maintenance procedures are inferred from tag names.
Output is a candidate dataset, not a published ontology or live telemetry.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import yaml


def export_inventory(source: Path) -> dict:
    raw = source.read_bytes()
    config = yaml.safe_load(raw)
    site, device = config["site"], config["device"]
    prefix = f"{site}/{device}"
    provenance = {
        "source_path": "simulator/plant.yaml",
        "source_sha256": hashlib.sha256(raw).hexdigest(),
        "review_status": "candidate",
        "environment": "simulation",
    }
    nodes = [{"id": prefix, "class": "Device", "properties": {
        **provenance, "name": device, "site": site,
        "scan_interval_ms": config["scan_interval_ms"],
    }}]
    relationships = []
    seen = set()
    for tag in config["tags"]:
        name = tag["name"]
        if name in seen:
            raise ValueError(f"Duplicate tag: {name}")
        seen.add(name)
        node_id = f"{prefix}/sensor/{name}"
        nodes.append({"id": node_id, "class": "Sensor", "properties": {
            **provenance, "name": name, "description": tag["desc"],
            "unit": tag["unit"], "register": tag["hr"],
            "lsl": tag.get("lsl"), "usl": tag.get("usl"),
            "source_locator": f"tags[name={name}]",
        }})
        relationships.append({"from_id": prefix, "to_id": node_id,
                              "type": "EXPOSES_SENSOR"})
    for space in ("coils", "holding"):
        for name, spec in config["commands"][space].items():
            node_id = f"{prefix}/point/{space}/{name}"
            nodes.append({"id": node_id, "class": "ControlPoint", "properties": {
                **provenance, "name": name, "description": spec["desc"],
                "address_space": space, "address": spec["addr"],
                "readonly": spec.get("readonly", False),
                "source_locator": f"commands.{space}.{name}",
            }})
            relationships.append({"from_id": prefix, "to_id": node_id,
                                  "type": "EXPOSES_POINT"})
    return {
        "schema_version": 1, "status": "candidate",
        "nodes": nodes, "relationships": relationships,
        "unresolved": [
            "Explicit asset-to-sensor membership requires review.",
            "A writable control point does not grant AI execution permission.",
            "Alarm logic is in Flink SQL; tag limits alone are not the alarm contract.",
        ],
    }


