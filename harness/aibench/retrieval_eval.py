"""EXP-AI 절 검색 Recall@3 (LLM 없음, 결정적). 질의·채점 규칙은 결과 전 고정(PROTOCOL §3).

질의 = "<alert_type> <tag> <센서 설명> 알람: 원인 확인과 대응 절차" (알람 시그니처만 사용, 정답·고장 이름 미사용)
증상 = 같은 시그니처로 /v2/trace 가 돌려준 증상(그래프 연결). 채점: 상위 3에 필수 절 전부 + 금지 절 없음.
"""
import json, sys, urllib.parse, urllib.request
import yaml

BASE = "http://127.0.0.1:38000/api/operations/v2"
DESC = {"VT-101": "교반기 진동", "IT-102": "교반기 전류", "TT-101": "반응기 온도", "PT-101": "반응기 압력"}
key = yaml.safe_load(open("ontology/v2/answer-key.yaml", encoding="utf-8"))["scenarios"]


def get(path, **q):
    with urllib.request.urlopen(f"{BASE}{path}?{urllib.parse.urlencode(q)}", timeout=120) as r:
        return json.load(r)


def passed(sections, required, forbidden):
    top = sections[:3]
    bad = [s for s in top for f in forbidden if (f.endswith("#*") and s.startswith(f[:-1])) or s == f]
    return all(r in top for r in required) and not bad, bad


out = {"model": sys.argv[1], "scenarios": {}}
for name, sc in key.items():
    trig = sc["alarm_trigger"]
    query = f"{trig['alert_type']} {trig['tag']} {DESC[trig['tag']]} 알람: 원인 확인과 대응 절차"
    trace = get("/trace", site="AR-100", device="reactor-line-01", alert_type=trig["alert_type"], tag=trig["tag"])
    symptoms = sorted({c["symptom"] for c in trace["candidates"]})
    res = get("/search", q=query, symptoms=",".join(symptoms), top_k=3)
    row = {"query": query, "symptoms": symptoms}
    for mode, field in (("hybrid", "results"), ("vector_only", "vector_only")):
        secs = [r["section"] for r in res[field]]
        ok, bad = passed(secs, sc["sections_required"], sc["sections_forbidden"])
        row[mode] = {"top3": secs, "scores": [round(r["score"], 4) for r in res[field]], "pass": ok, "forbidden_hit": bad}
    out["scenarios"][name] = row
print(json.dumps(out, ensure_ascii=False, indent=1))
