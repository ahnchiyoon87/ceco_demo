"""Build reviewed-import batches for the fault ontology (v2 model, deterministic, no LLM).

  --arm B : failure-knowledge documents (source_kind simulator-physics-fmea or a
            later *-RESPONSE doc named in the ontology) linked to their assets.
  --arm C : ontology graph from 5_ai/ontology/v2/kg/*.yaml — alarm signature →
            symptom → failure mode → cause / check → sensor, command, sections;
            action → procedure sections. Section keys on every document section.

Existing graph nodes are referenced with empty-property stubs (MERGE matches,
nothing is overwritten). New failure types are YAML + documents only; this
script does not change. Output goes to the reviewed preview → publish path.
"""
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

import yaml

root = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(root / "5_ai" / "server" / "knowledge"))
from backend.src.modules.ontology.inventory import export_inventory  # noqa: E402

PREFIX = "AR-100/reactor-line-01"
SITE, DEVICE = "AR-100", "reactor-line-01"
V1_DOCS = {"AR100-ASSET-CONTEXT", "AR100-EVIDENCE-POLICY", "AR100-MIXER-RESPONSE",
           "AR100-SENSOR-CONTEXT", "AR100-THERMAL-RESPONSE"}


def section_key(index, heading):
    """'#본문' for the untitled head, leading number when present, else heading words joined by '-'."""
    if index == 0 or not heading:
        return "본문"
    number = re.match(r"^(\d+)\.", heading)
    return number.group(1) if number else "-".join(heading.split())


def read_doc(path):
    text = path.read_text(encoding="utf-8")
    front = re.match(r"\A---\n(.*?)\n---\n", text, re.S)
    meta = yaml.safe_load(front.group(1)) if front else {}
    body = re.sub(r"\A---\n.*?\n---\n", "", text, count=1, flags=re.S)
    sections = []
    for index, section in enumerate(re.split(r"(?m)^## ", body)):
        heading = section.splitlines()[0].lstrip("# ") if index and section.splitlines() else ""
        sections.append((index, heading, section))
    return text, meta, sections


class Batch:
    def __init__(self):
        self.nodes, self.rels, self.ids = [], [], set()

    def node(self, node_id, cls, props=None):
        if node_id in self.ids:
            return node_id
        self.ids.add(node_id)
        self.nodes.append({"id": node_id, "class": cls, "properties": props or {}})
        return node_id

    def rel(self, a, b, kind):
        if not any(r["from_id"] == a and r["to_id"] == b and r["type"] == kind for r in self.rels):
            self.rels.append({"from_id": a, "to_id": b, "type": kind})

    def asset(self, name):
        # Asset stubs carry identity only; publish locks and matches site/device/name.
        return self.node(f"{PREFIX}/asset/{name}", "Asset", {"site": SITE, "device": DEVICE, "name": name})

    def sensor(self, tag):
        return self.node(f"{PREFIX}/sensor/{tag}", "Sensor")

    def section(self, ref):
        doc, key = ref.split("#", 1)
        for index, heading, _ in read_doc(root / "5_ai" / "manuals" / f"{doc}.md")[2]:
            if section_key(index, heading) == key:
                return self.node(f"{doc}/section/{index}", "DocumentSection", {"section_key": key})
        raise SystemExit(f"절을 찾을 수 없습니다: {ref}")

    def document(self, path):
        text, meta, sections = read_doc(path)
        doc_id = path.stem
        self.node(doc_id, "Document", {"name": doc_id, "source_path": f"5_ai/manuals/{path.name}",
                  "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
                  "version": meta.get("version"), "environment": "simulation", "content": text})
        for index, heading, content in sections:
            sid = self.node(f"{doc_id}/section/{index}", "DocumentSection", {
                "name": heading, "content": content, "document_id": doc_id,
                "source_locator": f"section:{index}", "source_path": f"5_ai/manuals/{path.name}",
                "section_key": section_key(index, heading)})
            self.rel(doc_id, sid, "HAS_SECTION")
        return doc_id, meta

    def dump(self, unresolved):
        return {"schema_version": 1, "status": "candidate", "nodes": self.nodes,
                "relationships": self.rels, "unresolved": unresolved}


def knowledge():
    data = {"components": [], "symptoms": [], "failure_modes": [], "actions": [],
            "kpis": [], "influences": [], "inputs": [], "decisions": []}
    for path in sorted((root / "5_ai/ontology/v2/kg").glob("*.yaml")):
        part = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for key in data:
            data[key].extend(part.get(key, []))
    return data


def new_documents():
    """Fault knowledge documents, each linked to the assets it applies to."""
    return [p for p in sorted((root / "5_ai" / "manuals").glob("*.md")) if p.stem not in V1_DOCS]


def registry_assets():
    reg = yaml.safe_load((root / "shared/registry/equipment.yaml").read_text(encoding="utf-8"))
    return {a["id"] for a in reg["assets"] if a["type"] != "Controller"}


def arm_b():
    batch = Batch()
    assets = registry_assets()
    for path in new_documents():
        doc_id, meta = batch.document(path)
        for target in meta.get("applies_to", []):
            if target in assets:
                batch.rel(batch.asset(target), doc_id, "HAS_PROCEDURE")
    return batch.dump(["교육용 가상설비 고장 지식이며 실물 FMEA 승인 문서가 아님"])


def arm_c():
    batch, kg = Batch(), knowledge()
    assets = {"M-101", "R-101", "P-101", "TK-101"}
    plant_cfg = yaml.safe_load((root / "0_plant/simulator/plant.yaml").read_text(encoding="utf-8"))
    inventory = export_inventory(root / "shared/registry/equipment.yaml")
    points = {n["properties"]["name"]: n for n in inventory["nodes"] if n["class"] == "ControlPoint"}
    aliases = {"temp_sp_c": "temp_sp_x10"}   # 온톨로지 문장은 °C 설정값, 제어점 이름은 temp_sp_x10(등록부 control_point)

    def target(name):
        return batch.asset(name) if name in assets else batch.node(f"v2/component/{name}", "Component")

    def point(name):
        node = points[aliases.get(name, name)]
        pid = batch.node(node["id"], "ControlPoint", node["properties"])
        batch.rel(batch.node(PREFIX, "Device"), pid, "EXPOSES_POINT")
        return pid

    for doc in sorted((root / "5_ai" / "manuals").glob("*.md")):
        for index, heading, _ in read_doc(doc)[2]:
            batch.node(f"{doc.stem}/section/{index}", "DocumentSection", {"section_key": section_key(index, heading)})
    for c in kg["components"]:
        batch.node(f"v2/component/{c['id']}", "Component", {"name": c["id"], "description": c["name"]})
        batch.rel(f"v2/component/{c['id']}", target(c["part_of"]), "PART_OF")
    for s in kg["symptoms"]:
        sid = batch.node(f"v2/symptom/{s['id']}", "Symptom", {"symptom_id": s["id"], "name": s["name"]})
        batch.rel(sid, batch.asset(s["observed_on"]), "OBSERVED_ON")
        batch.rel(sid, batch.section(s["section"]), "DOCUMENTED_IN")
        for ref in s.get("investigation", []):
            batch.rel(sid, batch.section(ref), "INVESTIGATED_BY")
        for sig in s["signatures"]:
            gid = batch.node(f"v2/signature/{sig['alert_type']}/{sig['tag']}", "AlarmSignature",
                             {"alert_type": sig["alert_type"], "tag": sig["tag"]})
            batch.rel(gid, batch.sensor(sig["tag"]), "ON_SENSOR")
            batch.rel(gid, sid, "INDICATES")
    for fm in kg["failure_modes"]:
        fid = batch.node(f"v2/fm/{fm['id']}", "FailureMode", {"failure_mode_id": fm["id"], "name": fm["name"]})
        for sym in fm["manifests_as"]:
            batch.rel(fid, f"v2/symptom/{sym}", "MANIFESTS_AS")
        batch.rel(fid, target(fm["affects"]), "AFFECTS")
        batch.rel(fid, batch.section(fm["section"]), "DOCUMENTED_IN")
        for i, cause in enumerate(fm.get("causes", [])):
            batch.rel(fid, batch.node(f"v2/cause/{fm['id']}/{i}", "Cause", {"name": cause}), "HAS_CAUSE")
        for i, check in enumerate(fm.get("checks", [])):
            kid = batch.node(f"v2/check/{fm['id']}/{i}", "Check", {
                "text": check["text"], "observable": bool(check.get("observable")),
                "field_check": check.get("field_check")})
            batch.rel(fid, kid, "CHECKED_BY")
            for tag in check.get("tags", []):
                batch.rel(kid, batch.sensor(tag), "OBSERVES")
            for command in check.get("commands", []):
                batch.rel(kid, point(command), "READS_COMMAND")
    for action in kg["actions"]:
        aid = batch.node(f"v2/action/{action['id']}", "Action", {"action_id": action["id"]})
        for sym in action["mitigates"]:
            batch.rel(aid, f"v2/symptom/{sym}", "MITIGATES")
        for ref in action["procedure"]:
            batch.rel(aid, batch.section(ref), "PROCEDURE")
    decision_layer(batch, kg, inventory, plant_cfg)
    return batch.dump(["고장모드 확인 방법은 판정 규칙이 아니라 근거 설명이다(PROTOCOL §2)",
                       "손익 식의 수치는 기업 시스템 사실값(enterprise.fact)을 이름으로 읽는다. 교육용 가상 기업 데이터"])


NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
FUNCS = {"max", "min", "abs", "round", "and", "or", "not"}


def expr_names(text):
    return {n for n in NAME.findall(str(text)) if n not in FUNCS}


def decision_layer(batch, kg, inventory, plant_cfg):
    """KPI·결정·대안·규칙·단계·회복 기준(BSC·DMN·BPMN 준용). 식은 문자열로 두고 엔진이 사실값으로 계산한다."""
    as_json = lambda v: json.dumps(v, ensure_ascii=False, sort_keys=True)
    facts = {k: i["system"] for i in kg["inputs"] for k in i["keys"]}
    tasks = set(plant_cfg.get("field_tasks", {}))
    wms = {n["properties"]["name"]: n for n in inventory["nodes"] if n["class"] == "WorkMaster"}
    for k in kg["kpis"]:
        kid = batch.node(f"v2/kpi/{k['id']}", "KPI", {"kpi_id": k["id"], "name": k["name"], "unit": k["unit"],
                         "perspective": k["perspective"], "owner": k["owner"], "description": k["description"]})
        dept = batch.node(f"v2/department/{k['owner']}", "Department", {"name": k["owner"]})
        batch.rel(kid, dept, "OWNED_BY")
    for i in kg["influences"]:
        batch.rels.append({"from_id": f"v2/kpi/{i['from']}", "to_id": f"v2/kpi/{i['to']}", "type": "INFLUENCES",
                           "properties": {"sign": i["sign"], "note": i["note"]}})
    for key, system in facts.items():
        batch.node(f"v2/input/{key}", "InputData", {"key": key, "system": system, "source": "enterprise.fact"})

    def check_names(text, where, extra=()):
        for n in expr_names(text):
            ok = (n in facts or n in extra or n.split("_", 1)[0] in {"o", "usl", "lsl", "c", "b", "opt", "d", "a"}
                  or (n.startswith("t_") and n[2:] in tasks) or n in {"i_interlock", "i_maintenance"})
            if not ok:
                raise SystemExit(f"{where}: 알 수 없는 이름 '{n}' (inputs·field_tasks·접두사 규칙 밖)")
        return {n for n in expr_names(text) if n in facts}

    for d in kg["decisions"]:
        did = batch.node(f"v2/decision/{d['id']}", "Decision", {
            "decision_id": d["id"], "name": d["name"], "question": d["question"], "hit_policy": "RANK_TOTAL",
            "recovery_all": as_json(d["recovery"]["all"]), "recovery_hold_s": d["recovery"]["hold_s"],
            "recovery_timeout_s": d["recovery"]["timeout_s"], "shared_derived": as_json(d.get("shared_derived", {}))})
        batch.rel(f"v2/symptom/{d['triggered_by']}", did, "TRIGGERS_DECISION")
        batch.rel(did, batch.section(d["recovery"]["section"]), "VERIFIED_BY")
        used = set()
        for name, text in d.get("shared_derived", {}).items():
            used |= check_names(text, f"{d['id']}.shared_derived.{name}")
        for text in d["recovery"]["all"]:
            used |= check_names(text, f"{d['id']}.recovery")
        for r in d.get("rules", []):
            rid = batch.node(f"v2/rule/{r['id']}", "Rule", {"rule_id": r["id"], "when": r["when"], "then": r["then"],
                                                           "reason": r["reason"]})
            batch.rel(did, rid, "HAS_RULE")
            batch.rel(rid, batch.section(r["policy"]), "ENCODES")
            used |= check_names(r["when"], r["id"])
        for o in d["options"]:
            oid = batch.node(f"v2/option/{o['id']}", "Option", {
                "option_id": o["id"], "name": o["name"], "kind": o["kind"], "params": as_json(o.get("params", {})),
                "derived": as_json(o.get("derived", {}))})
            batch.rel(did, oid, "HAS_OPTION")
            for fm in o["treats"]:
                batch.rel(oid, f"v2/fm/{fm}", "TREATS")
            for ref in o.get("procedure", []):
                batch.rel(oid, batch.section(ref), "PROCEDURE")
            for name, text in o.get("derived", {}).items():
                used |= check_names(text, f"{o['id']}.derived.{name}")
            for kpi, text in o["impacts"].items():
                if f"v2/kpi/{kpi}" not in batch.ids:
                    raise SystemExit(f"{o['id']}: 없는 KPI {kpi}")
                used |= check_names(text, f"{o['id']}.{kpi}")
                batch.rels.append({"from_id": oid, "to_id": f"v2/kpi/{kpi}", "type": "IMPACTS", "properties": {"expr": text}})
            for n, st in enumerate(o.get("steps", []), 1):
                props = {"order": n, "kind": st["kind"], "say": st["say"],
                         "params": as_json(st.get("params", {})), "until": st.get("until"), "hours": st.get("hours"),
                         "timeout_s": st.get("timeout_s"), "abort_on_no_fault": st.get("abort_on_no_fault", True)}
                sid = batch.node(f"v2/step/{o['id']}/{n}", "Step", {k: v for k, v in props.items() if v is not None})
                batch.rel(oid, sid, "HAS_STEP")
                for text in [*st.get("params", {}).values(), st.get("until") or "", st.get("hours") or ""]:
                    used |= check_names(text, f"{o['id']}.step{n}")
                if st["kind"] in ("control", "field"):
                    if st["wm"] not in wms:
                        raise SystemExit(f"{o['id']}.step{n}: 등록부에 없는 작업 정의 {st['wm']}")
                    node = wms[st["wm"]]
                    batch.rel(sid, batch.node(node["id"], "WorkMaster", node["properties"]), "USES_WORK_MASTER")
        for key in sorted(used):
            batch.rel(did, f"v2/input/{key}", "REQUIRES_INPUT")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--arm", choices=["B", "C"], required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = arm_b() if args.arm == "B" else arm_c()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"arm {args.arm}: {len(result['nodes'])} nodes, {len(result['relationships'])} relationships; review required")
