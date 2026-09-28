"""온톨로지 데이터(ontology/v2/data/*.yaml)와 문서(knowledge-docs/*.md, ontology/v2/docs/*.md)를 그래프에 적재한다.

- 설비·센서·제어점·인터록·증상·고장모드·조치: YAML 그대로 노드·관계로
- 센서 단위·lsl·usl: simulator/plant.yaml(정본)에서
- 문서: 머리말(document_id·version·applies_to·alarm_types)과 '## ' 절 단위 Section 노드, 절 임베딩(Ollama)과 벡터 인덱스
파일을 추가하면 적재 대상이 늘어난다(코드 변경 없이 확장).
"""
import glob
import hashlib
import json
import os
import re

import requests
import yaml
from neo4j import GraphDatabase

REPO = os.environ.get("REPO", "/repo")
DATA_GLOB = f"{REPO}/ontology/v2/data/*.yaml"
DOC_GLOBS = [f"{REPO}/knowledge-docs/*.md", f"{REPO}/ontology/v2/docs/*.md"]
OLLAMA = os.environ.get("OLLAMA_URL", "http://ollama:11434")
EMBED_MODEL = os.environ.get("EMBED_MODEL", "bge-m3")


def driver():
    return GraphDatabase.driver(os.environ.get("NEO4J_URI", "bolt://neo4j:7687"),
                                auth=(os.environ.get("NEO4J_USER", "neo4j"), os.environ["NEO4J_PASSWORD"]))


def embed(texts):
    r = requests.post(f"{OLLAMA}/api/embed", json={"model": EMBED_MODEL, "input": texts}, timeout=600)
    r.raise_for_status()
    return r.json()["embeddings"]


def plant_spec():
    p = yaml.safe_load(open(f"{REPO}/simulator/plant.yaml", encoding="utf-8"))
    return {t["name"]: {"unit": t.get("unit"), "lsl": t.get("lsl"), "usl": t.get("usl")} for t in p["tags"]}


def slug(heading):
    m = re.match(r"^(\d+)\.", heading)
    return m.group(1) if m else re.sub(r"\s+", "-", heading.strip())


def parse_doc(path):
    text = open(path, encoding="utf-8").read()
    fm, body = {}, text
    m = re.match(r"^---\n(.*?)\n---\n(.*)$", text, re.S)
    if m:
        fm, body = yaml.safe_load(m.group(1)) or {}, m.group(2)
    doc_id = fm.get("document_id") or os.path.basename(path)[:-3]
    title = (re.search(r"^# (.+)$", body, re.M) or [None, doc_id])[1]
    sections = []
    parts = re.split(r"^## (.+)$", body, flags=re.M)
    intro = parts[0]
    if intro.strip():
        sections.append({"sid": f"{doc_id}#0", "heading": title, "text": intro.strip()})
    for i in range(1, len(parts), 2):
        sections.append({"sid": f"{doc_id}#{slug(parts[i])}", "heading": parts[i].strip(), "text": parts[i + 1].strip()})
    return {"doc_id": doc_id, "version": fm.get("version"), "applies_to": fm.get("applies_to") or [],
            "alarm_types": fm.get("alarm_types") or [], "title": title, "path": os.path.relpath(path, REPO),
            "sha256": hashlib.sha256(text.encode()).hexdigest(), "sections": sections}


def load(reset=True):
    data = {"assets": [], "sensors": [], "control_points": [], "interlocks": [], "symptoms": [], "failure_modes": [], "actions": []}
    for f in sorted(glob.glob(DATA_GLOB)):
        d = yaml.safe_load(open(f, encoding="utf-8")) or {}
        for k in data:
            data[k] += d.get(k, [])
    spec = plant_spec()
    docs = [parse_doc(p) for g in DOC_GLOBS for p in sorted(glob.glob(g))]
    sec_texts = [f"{s['heading']}\n{s['text']}" for d in docs for s in d["sections"]]
    vectors = embed(sec_texts) if sec_texts else []
    dim = len(vectors[0]) if vectors else 0
    with driver() as drv, drv.session() as s:
        if reset:
            s.run("MATCH (n) DETACH DELETE n")
            s.run("DROP INDEX section_embedding IF EXISTS")
        for a in data["assets"]:
            s.run("MERGE (x:Asset {id:$id}) SET x.name=$name, x.level=$level", **a)
        for a in data["assets"]:
            if a.get("part_of"):
                s.run("MATCH (c:Asset {id:$c}),(p:Asset {id:$p}) MERGE (c)-[:PART_OF]->(p)", c=a["id"], p=a["part_of"])
        for x in data["sensors"]:
            sp = spec.get(x["tag"], {})
            s.run("""MERGE (n:Sensor {tag:$tag}) SET n.observes=$obs, n.unit=$unit, n.lsl=$lsl, n.usl=$usl,
                     n.spec_source='simulator/plant.yaml'
                     WITH n MATCH (f:Asset {id:$of}) MERGE (n)-[:OBSERVES {property:$obs}]->(f)""",
                  tag=x["tag"], obs=x["observes"], of=x["of"], unit=sp.get("unit"), lsl=sp.get("lsl"), usl=sp.get("usl"))
            if x.get("owner"):
                s.run("MATCH (a:Asset {id:$o}),(n:Sensor {tag:$t}) MERGE (a)-[:HAS_SENSOR]->(n)", o=x["owner"], t=x["tag"])
            for inf in x.get("influenced_by", []):
                s.run("MATCH (a:Asset {id:$a}),(n:Sensor {tag:$t}) MERGE (a)-[:INFLUENCES]->(n)", a=inf, t=x["tag"])
        for c in data["control_points"]:
            s.run("""MERGE (c:ControlPoint {name:$name}) SET c.kind=$kind, c.addr=$addr
                     WITH c MATCH (a:Asset {id:$controls}) MERGE (c)-[:CONTROLS]->(a)""", **c)
        for i in data["interlocks"]:
            s.run("""MERGE (i:Interlock {id:$id}) SET i.name=$name, i.trip=$trip, i.reset=$reset, i.note=$note
                     WITH i MATCH (n:Sensor {tag:$mon}) MERGE (i)-[:MONITORS]->(n)""",
                  id=i["id"], name=i["name"], trip=i["trip_barg"], reset=i["reset_barg"], note=i.get("note"), mon=i["monitors"])
            for b in i["blocks"]:
                s.run("MATCH (i:Interlock {id:$id}),(c:ControlPoint {name:$b}) MERGE (i)-[:BLOCKS]->(c)", id=i["id"], b=b)
        for y in data["symptoms"]:
            s.run("""MERGE (y:Symptom {id:$id}) SET y.name=$name, y.description=$desc
                     WITH y MATCH (a:Asset {id:$on}) MERGE (y)-[:ON]->(a)""", id=y["id"], name=y["name"], desc=y["description"], on=y["on"])
            for g in y["signatures"]:
                s.run("""MERGE (g:AlarmSignature {alert_type:$at, tag:$tag}) WITH g
                         MATCH (y:Symptom {id:$id}) MERGE (g)-[:INDICATES]->(y)
                         WITH g MATCH (n:Sensor {tag:$tag}) MERGE (g)-[:FROM_SENSOR]->(n)""", at=g["alert_type"], tag=g["tag"], id=y["id"])
        for m in data["failure_modes"]:
            s.run("""MERGE (m:FailureMode {id:$id}) SET m.name=$name, m.observable=$obs, m.field_check=$fc,
                     m.conditions=$cond WITH m MATCH (a:Asset {id:$aff}) MERGE (m)-[:AFFECTS]->(a)""",
                  id=m["id"], name=m["name"], obs=m.get("observable", True), fc=m.get("field_check"), aff=m["affects"],
                  cond=json.dumps({k: m.get(k, []) for k in ("requires", "supports", "refutes")}, ensure_ascii=False))
            for y in m["manifests_as"]:
                s.run("MATCH (m:FailureMode {id:$m}),(y:Symptom {id:$y}) MERGE (m)-[:MANIFESTS_AS]->(y)", m=m["id"], y=y)
        for ac in data["actions"]:
            s.run("MERGE (a:Action {id:$id}) SET a.preconditions=$pre", id=ac["id"],
                  pre=json.dumps(ac.get("preconditions", []), ensure_ascii=False))
            for y in ac.get("mitigates", []):
                s.run("MATCH (a:Action {id:$a}),(y:Symptom {id:$y}) MERGE (a)-[:MITIGATES]->(y)", a=ac["id"], y=y)
        vi = 0
        for d in docs:
            s.run("""MERGE (d:Document {id:$id}) SET d.version=$v, d.title=$t, d.path=$p, d.sha256=$h, d.alarm_types=$at""",
                  id=d["doc_id"], v=d["version"], t=d["title"], p=d["path"], h=d["sha256"], at=d["alarm_types"])
            for a in d["applies_to"]:
                s.run("MATCH (d:Document {id:$d}),(x:Asset {id:$a}) MERGE (d)-[:APPLIES_TO]->(x)", d=d["doc_id"], a=a)
            for sec in d["sections"]:
                s.run("""MERGE (x:Section {sid:$sid}) SET x.heading=$h, x.text=$t, x.embedding=$e
                         WITH x MATCH (d:Document {id:$d}) MERGE (x)-[:PART_OF]->(d)""",
                      sid=sec["sid"], h=sec["heading"], t=sec["text"], e=vectors[vi], d=d["doc_id"])
                vi += 1
        if dim:
            s.run(f"""CREATE VECTOR INDEX section_embedding IF NOT EXISTS FOR (x:Section) ON (x.embedding)
                      OPTIONS {{indexConfig: {{`vector.dimensions`: {dim}, `vector.similarity_function`: 'cosine'}}}}""")
            s.run("CALL db.awaitIndexes(120)")
        counts = s.run("MATCH (n) RETURN labels(n)[0] AS l, count(*) AS c ORDER BY l").data()
    return {"counts": {r["l"]: r["c"] for r in counts}, "docs": [d["doc_id"] for d in docs], "sections": len(sec_texts), "dim": dim}


if __name__ == "__main__":
    print(json.dumps(load(), ensure_ascii=False, indent=1))
