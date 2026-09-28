"""CQ 15 응답 판정(ontology/cq.yaml) — 조회문·판정 조건은 결과 보기 전 고정(측정 도구).

판정: answered = 조회가 실행되고 요구 칸이 모두 채워진 행이 있음 / partial = 행은 있으나 요구 칸 일부만(또는 자유 문장에만 있음)
      / no = 답할 관계·칸이 없음(조회 실패·0행 포함).
승인·명령 계열(CQ08~CQ11)은 이번 EXP-AI 회차에 승인을 실행하지 않았으므로 "기록할 칸이 스키마에 있는가"로 판정한다(capability).
그래프 조회는 현재 rot-ai 그래프(팔 A = snap-A, 팔 C = snap-C3)에 대해 돈다. 업무 DB 는 두 팔 공통이며, 팔 구분은 대응안 origin 과 body 형식으로 한다.
  python harness/aibench/cq_eval.py <A|C>
"""
import json, subprocess, sys

ARM = sys.argv[1]


def cypher(q):
    r = subprocess.run(["docker", "exec", "-i", "rot-ai-graph-1", "sh", "-c",
                        'cypher-shell -u neo4j -p "${NEO4J_AUTH#neo4j/}" --format plain'],
                       input=q, capture_output=True, text=True, encoding="utf-8")
    lines = [l for l in r.stdout.splitlines() if l.strip()]
    return {"ok": r.returncode == 0, "header": lines[:1], "rows": lines[1:], "error": r.stderr.strip()[:300]}


def sql(q):
    r = subprocess.run(["docker", "exec", "rot-ai-work-db-1", "psql", "-U", "ar100", "-d", "ar100_work", "-At", "-F", " | ", "-c", q],
                       capture_output=True, text=True, encoding="utf-8")
    return {"ok": r.returncode == 0, "rows": [l for l in r.stdout.splitlines() if l.strip()], "error": r.stderr.strip()[:300]}


# V1 대응안 = body 에 cause_assessment 없음, V2 = 있음. 팔별로 자기 형식의 대응안만 본다.
FORM = "NOT (p.body ? 'cause_assessment')" if ARM == "A" else "(p.body ? 'cause_assessment')"
CQ = {
 "CQ01": ("graph", "MATCH (a:Asset)-[:HAS_SENSOR]->(s:Sensor {name:'VT-101'}) OPTIONAL MATCH (c)-[:PART_OF]->(a) RETURN a.name, s.description, s.unit, collect(c.name) AS parts;", "설비·측정량·단위(부품은 있으면 추가)"),
 "CQ02": ("graph", "MATCH (r:Asset {name:'R-101'}) OPTIONAL MATCH (x)-[:INSTALLED_IN|PART_OF]->(r) OPTIONAL MATCH (r)-[:HAS_SENSOR]->(s) RETURN collect(DISTINCT x.name) AS members, collect(DISTINCT s.name) AS sensors;", "소속 설비와 센서 둘 다"),
 "CQ03": ("graph", "MATCH (:Asset {name:'M-101'})-[:HAS_PROCEDURE]->(d:Document) RETURN d.name, d.version ORDER BY d.version DESC;", "문서 ID·버전"),
 "CQ04": ("sql", "SELECT e.payload->>'tag', e.payload->>'value', e.payload->>'ts', e.payload->>'quality' FROM manufacturing_events e WHERE kind='alarm_received' ORDER BY id DESC LIMIT 3;", "센서·값·시각·품질(품질은 알람 원문에 있어야 answered)"),
 "CQ05": ("sql", f"SELECT p.id, jsonb_array_length(coalesce(p.body->'cause_assessment','[]')) AS candidates, p.body->'citations', p.evidence->'graph'->'documents'->0->>'version' FROM manufacturing_proposals p WHERE {FORM} ORDER BY created_at DESC LIMIT 3;", "구조화된 원인후보 + 관측 근거 + 문서 버전(요약문에만 있으면 partial)"),
 "CQ06": ("sql", f"SELECT p.id, (p.evidence ? 'history') AS observed, (p.body ? 'summary') AS inferred FROM manufacturing_proposals p WHERE {FORM} LIMIT 3;", "관측(evidence)과 추론(body)이 분리 저장"),
 "CQ07": ("sql", "SELECT r.model, (SELECT string_agg(DISTINCT e.payload->>'tool', ',') FROM manufacturing_events e WHERE e.payload->>'run_id'=r.id::text AND e.kind='agent_tool_started') AS tools, NULL AS prompt_version FROM manufacturing_analysis_runs r ORDER BY created_at DESC LIMIT 3;", "모델·도구·프롬프트 버전"),
 "CQ08": ("sql", "SELECT column_name FROM information_schema.columns WHERE table_name='manufacturing_proposals' AND column_name IN ('decision','completed_at','decided_by');", "결정·사유·시각·결정자 칸(capability)"),
 "CQ09": ("sql", "SELECT column_name FROM information_schema.columns WHERE table_name='manufacturing_proposals' AND column_name IN ('state_fingerprint','result','started_at');", "승인 시점 조건 지문과 실행 직전 재검사 결과 칸(capability)"),
 "CQ10": ("sql", "SELECT column_name FROM information_schema.columns WHERE table_name IN ('manufacturing_proposals','manufacturing_operator_commands') AND column_name='result';", "명령 응답과 상태 반영 확인 결과 칸(capability)"),
 "CQ11": ("sql", "SELECT column_name FROM information_schema.columns WHERE table_name IN ('manufacturing_operator_commands','manufacturing_proposals') AND column_name IN ('blocked_by','path');", "인터록 차단 기록 + 경로 C1/C2/C3 구분 칸(capability)"),
 "CQ12": ("sql", f"SELECT count(*) FILTER (WHERE jsonb_array_length(coalesce(p.body->'citations','[]'))=0) AS without_docs, count(*) AS total FROM manufacturing_proposals p WHERE {FORM};", "근거 문서 없는 원인후보 수를 셀 수 있음"),
 "CQ13": ("sql", "SELECT device, correlation_key, count(*) FROM manufacturing_incidents GROUP BY 1,2 HAVING count(*)>1 ORDER BY 3 DESC LIMIT 3;", "같은 설비 반복 사건"),
 "CQ14": ("graph", "MATCH (i) WHERE i:Interlock OR (i:ControlPoint AND i.name='interlock') OPTIONAL MATCH (i)-[r]-(x) RETURN labels(i), i.name, type(r), x.name;", "인터록 → 막는 명령 관계(문서 절 검색으로만 찾으면 partial)"),
 "CQ15": ("sql", "SELECT column_name FROM information_schema.columns WHERE table_name LIKE 'manufacturing%' AND column_name IN ('ack_state','acknowledged_by','acknowledged_at','shelved');", "ISA-18.2 확인 상태·확인자·시각"),
}
out = {"arm": ARM, "results": {}}
for cq, (kind, q, need) in CQ.items():
    res = cypher(q) if kind == "graph" else sql(q)
    out["results"][cq] = {"kind": kind, "query": q, "need": need, **res}
print(json.dumps(out, ensure_ascii=False, indent=1))
