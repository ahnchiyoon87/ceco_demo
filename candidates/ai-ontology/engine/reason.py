"""알람 한 건에 대해 그래프로 원인 후보를 추론하고, 조치를 고르고, 조치 매뉴얼 절을 하이브리드로 검색한다.

1) 알람(alert_type, tag) → AlarmSignature → Symptom
2) Symptom ← MANIFESTS_AS ← FailureMode → 각 고장모드의 조건을 관측으로 평가 (supported/refuted/unknown/not_applicable)
   원인을 '확정'하지 않는다: confirmed_cause 는 항상 None.
3) Symptom ← MITIGATES ← Action 중 전제 조건이 모두 참인 조치, 없으면 inspect_only
4) 매뉴얼 절: 그래프가 적용 문서를 좁힘(문서가 알람 설비 계통에 APPLIES_TO + alarm_types 에 알람 유형 포함)
   + 절 임베딩 유사도(벡터 인덱스). 점수 = 유사도 + 적용 문서 가산. 상위 k.
도메인 지식은 그래프 데이터에만 있다.
"""
import json
import os

from .checks import evaluate, judge_failure_mode
from .load import driver, embed, plant_spec

APPLICABLE_BONUS = float(os.environ.get("APPLICABLE_BONUS", "0.15"))


def infer(alarm, history, state, k=3):
    spec = plant_spec()
    ctx = {"history": history, "state": state, "spec": spec}
    with driver() as drv, drv.session() as s:
        sym = s.run("""MATCH (g:AlarmSignature {alert_type:$at, tag:$tag})-[:INDICATES]->(y:Symptom)-[:ON]->(a:Asset)
                       RETURN y.id AS id, y.name AS name, y.description AS description, a.id AS on""",
                    at=alarm["alert_type"], tag=alarm["tag"]).data()
        if not sym:
            return {"alarm": alarm, "symptom": None, "candidates": [], "confirmed_cause": None, "action": "inspect_only",
                    "sections": [], "note": "알람과 연결된 증상이 온톨로지에 없음 — 근거 부족으로 원인 후보를 만들지 않음"}
        y = sym[0]
        fms = s.run("""MATCH (m:FailureMode)-[:MANIFESTS_AS]->(:Symptom {id:$y})
                       OPTIONAL MATCH (m)-[:AFFECTS]->(a:Asset)
                       RETURN m.id AS id, m.name AS name, m.observable AS observable, m.field_check AS field_check,
                              m.conditions AS conditions, a.id AS affects ORDER BY m.id""", y=y["id"]).data()
        candidates = []
        for m in fms:
            fm = {"observable": m["observable"], "field_check": m["field_check"], **json.loads(m["conditions"])}
            status, detail = judge_failure_mode(fm, ctx)
            candidates.append({"id": m["id"], "name": m["name"], "affects": m["affects"], "status": status, "detail": detail})
        actions = s.run("""MATCH (a:Action)-[:MITIGATES]->(:Symptom {id:$y}) RETURN a.id AS id, a.preconditions AS pre""",
                        y=y["id"]).data()
        chosen, action_checks = "inspect_only", {}
        for a in actions:
            res = [evaluate(c, ctx) for c in json.loads(a["pre"])]
            action_checks[a["id"]] = res
            if res and all(r is True for r in res):
                chosen = a["id"]
                break
        # 적용 문서: 증상 설비와 그 상위·하위 설비에 APPLIES_TO, 문서 alarm_types 에 알람 유형 포함
        applicable = {r["id"] for r in s.run("""MATCH (a:Asset {id:$on})
            OPTIONAL MATCH (a)-[:PART_OF*0..3]->(up:Asset) WITH collect(DISTINCT a)+collect(DISTINCT up) AS xs
            UNWIND xs AS x MATCH (d:Document)-[:APPLIES_TO]->(x)
            WHERE $at IN coalesce(d.alarm_types, []) RETURN DISTINCT d.id AS id""", on=y["on"], at=alarm["alert_type"]).data()}
        live = [c["name"] for c in candidates if c["status"] in ("supported", "unknown")]
        query = f"{y['name']}. {y['description']} 원인 후보: {', '.join(live)}. 확인 절차와 대응 조치."
        qv = embed([query])[0]
        hits = s.run("""CALL db.index.vector.queryNodes('section_embedding', 30, $q) YIELD node, score
                        MATCH (node)-[:PART_OF]->(d:Document)
                        RETURN node.sid AS sid, node.heading AS heading, d.id AS doc, d.version AS version, score""", q=qv).data()
    ranked = sorted(({**h, "applicable": h["doc"] in applicable,
                      "final": h["score"] + (APPLICABLE_BONUS if h["doc"] in applicable else 0.0)} for h in hits),
                    key=lambda h: -h["final"])
    return {"alarm": alarm, "symptom": y, "candidates": candidates, "confirmed_cause": None,
            "action": chosen, "action_checks": action_checks, "query": query,
            "applicable_documents": sorted(applicable), "sections": ranked[:k], "sections_top10": ranked[:10]}
