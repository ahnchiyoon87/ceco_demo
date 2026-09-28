"""EXP-AI 채점기 — ontology/v2/PROTOCOL.md §3 규칙 그대로(측정 도구). 정답은 여기서만 읽는다.

  python harness/aibench/score.py            → experiments/EXP-AI/score.json + 표 출력
원인 확정 표현은 기계로 판정하지 않고 후보 문장을 뽑아 사람 확인 목록(confirm_review)으로 남긴다.
"""
import json, re
from collections import defaultdict
from pathlib import Path

import yaml

key = yaml.safe_load(open("ontology/v2/answer-key.yaml", encoding="utf-8"))["scenarios"]
CONFIRM = re.compile(r"[^.。\n]*(원인(은|이)[^.。\n]*(확정|확인되었|확인됐|입니다)|확정(한다|했|됨|되었))[^.。\n]*")
rows = []
for path in sorted(Path("experiments/EXP-AI/raw").glob("*.json")):
    d = json.loads(path.read_text(encoding="utf-8"))
    sc = key[d["scenario"]]
    run = d.get("analysis_run") or {}
    body = (d.get("proposal") or {}).get("body") or {}
    result = (run.get("result") or {}).get("result") or {}
    if d.get("invalid") or run.get("status") in (None, "failed", "interrupted"):
        outcome = "invalid"
    elif body:
        outcome = body.get("action")
    elif run.get("status") == "needs_evidence":
        outcome, body = "needs_evidence", result
    else:
        outcome = run.get("status")
    causes = {c["failure_mode"]: c["status"] for c in body.get("cause_assessment", [])} if body else {}
    expected = sc["causes"]
    cause_score = (sum(causes.get(fm) == st for fm, st in expected.items()), len(expected)) if causes else None
    forbidden_docs = {f.split("#")[0] for f in sc["sections_forbidden"]}
    cited = set(body.get("citations", [])) if body else set()
    tools = [i["payload"].get("tool") for i in (d.get("trace") or {}).get("items", []) if i["kind"] == "agent_tool_started"]
    text = " ".join([body.get("summary", "")] + [c.get("evidence", "") for c in body.get("cause_assessment", [])]) if body else ""
    steps = {s["step"]: s for s in d["steps"]}
    rows.append({
        "run_id": d["run_id"], "arm": d["arm"], "scenario": d["scenario"], "outcome": outcome,
        "action_match": outcome == sc["action"] if outcome != "invalid" else None,
        "cause_score": cause_score, "cause_detail": {fm: [causes.get(fm), st] for fm, st in expected.items()} if causes else None,
        "forbidden_cited": sorted(cited & forbidden_docs), "citations": sorted(cited), "tools": tools,
        "analysis_s": steps.get("analysis_done", {}).get("seconds"), "alarm_wait_s": steps.get("alarm", {}).get("waited_s"),
        "confirm_review": [m.group(0).strip() for m in CONFIRM.finditer(text)][:5],
        "error": run.get("error"),
    })

summary = defaultdict(lambda: {"runs": 0, "valid": 0, "action_ok": 0, "cause_ok": 0, "cause_n": 0, "forbidden": 0, "analysis_s": []})
for r in rows:
    s = summary[(r["arm"], r["scenario"])]
    s["runs"] += 1
    if r["outcome"] == "invalid":
        continue
    s["valid"] += 1
    s["action_ok"] += bool(r["action_match"])
    s["forbidden"] += bool(r["forbidden_cited"])
    if r["analysis_s"] is not None:
        s["analysis_s"].append(r["analysis_s"])
    if r["cause_score"]:
        s["cause_ok"] += r["cause_score"][0]; s["cause_n"] += r["cause_score"][1]
out = {"rows": rows, "summary": {f"{a}|{sc}": v for (a, sc), v in sorted(summary.items())}}
Path("experiments/EXP-AI/score.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
print("팔 | 시나리오 | 유효/전체 | 조치 일치 | 고장모드 상태 일치 | 금지 문서 인용 | 분석 시간 중앙값(s)")
for k, v in out["summary"].items():
    a, sc = k.split("|")
    t = sorted(v["analysis_s"]); med = t[len(t) // 2] if t else None
    cause = f"{v['cause_ok']}/{v['cause_n']}" if v["cause_n"] else "해당 없음"
    print(f"{a} | {sc} | {v['valid']}/{v['runs']} | {v['action_ok']}/{v['valid']} | {cause} | {v['forbidden']} | {med}")
for r in rows:
    if r["confirm_review"]:
        print("확정 표현 후보:", r["run_id"], r["confirm_review"])
