"""정비 판단 엔진(결정론, LLM 없음): 온톨로지 결정·대안·규칙·손익 식 + 기업 사실값 + 현재 관측 → 대안 순위.

온톨로지(5_ai/ontology/v2/kg/maintenance-decisions.yaml → Neo4j)가 식과 규칙을 갖고, 숫자는 기업 시스템
사실값(공용 업무 DB enterprise.fact)과 현재 관측에서 읽는다. 그래프나 사실값이 바뀌면 결과가 바뀐다.
원인 판단은 하지 않는다: 대안의 자격은 AI 가 관측으로 매긴 고장모드 상태(supported/refuted/unknown)를 입력으로 받는다.
"""
from __future__ import annotations

import ast
import json
import math
import os
from datetime import datetime, timezone

from fastapi import HTTPException

from ..ontology.tools import _run_readonly_query

REGISTRY_DIR = os.environ.get("REGISTRY_DIR", "/opt/ar100/registry")
FUNCS = {"max": max, "min": min, "abs": abs, "round": round}
WEIGHT = {"supported": 1.0, "unknown": 0.5, "refuted": 0.0, "not_applicable": 0.0}
_BIN = {ast.Add: lambda a, b: a + b, ast.Sub: lambda a, b: a - b, ast.Mult: lambda a, b: a * b, ast.Div: lambda a, b: a / b}
_CMP = {ast.Eq: lambda a, b: a == b, ast.NotEq: lambda a, b: a != b, ast.Lt: lambda a, b: a < b,
        ast.LtE: lambda a, b: a <= b, ast.Gt: lambda a, b: a > b, ast.GtE: lambda a, b: a >= b}


class MissingValue(KeyError):
    """식이 읽는 이름의 값이 없다(사실값 누락·관측 없음). 기본값으로 메우지 않는다."""


def evaluate(expr: str, env: dict):
    """사칙연산·비교·and/or/not·max/min/abs/round 만 허용하는 식 계산기."""
    def ev(node):
        if isinstance(node, ast.Expression):
            return ev(node.body)
        if isinstance(node, ast.Constant) and type(node.value) in (int, float):
            return node.value
        if isinstance(node, ast.Name):
            if node.id not in env or env[node.id] is None:
                raise MissingValue(node.id)
            return env[node.id]
        if isinstance(node, ast.BinOp) and type(node.op) in _BIN:
            return _BIN[type(node.op)](ev(node.left), ev(node.right))
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
            return -ev(node.operand)
        if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
            return not ev(node.operand)
        if isinstance(node, ast.BoolOp):
            values = [ev(v) for v in node.values]
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.Compare) and all(type(op) in _CMP for op in node.ops):
            left = ev(node.left)
            for op, comp in zip(node.ops, node.comparators):
                right = ev(comp)
                if not _CMP[type(op)](left, right):
                    return False
                left = right
            return True
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in FUNCS
                and not node.keywords):
            return FUNCS[node.func.id](*[ev(a) for a in node.args])
        raise ValueError(f"허용하지 않는 식: {ast.dump(node)[:80]}")
    return ev(ast.parse(str(expr), mode="eval"))


def _registry():
    with open(os.path.join(REGISTRY_DIR, "tags.json"), encoding="utf-8") as f:
        tags = json.load(f)
    with open(os.path.join(REGISTRY_DIR, "work_masters.ot.json"), encoding="utf-8") as f:
        wms = json.load(f)
    return tags, wms


def var(tag: str) -> str:
    return tag.replace("-", "_")


def facts() -> dict:
    """기업 시스템 사실값(MES·ERP·CMMS). 읽기 실패는 판단 불가다."""
    from .plant_db import plant_connection
    try:
        with plant_connection() as pc:
            rows = pc.execute("SELECT key, system, value, unit, description, updated_at FROM enterprise.fact ORDER BY key").fetchall()
    except Exception as exc:
        raise HTTPException(503, "기업 시스템 사실값(enterprise.fact)을 읽지 못해 대안 손익을 계산하지 않았습니다.") from exc
    return {r["key"]: {**r, "updated_at": r["updated_at"].isoformat() if r["updated_at"] else None} for r in rows}


def environment(state: dict, fact_rows: dict, base_commands: dict | None = None) -> dict:
    """식이 읽는 이름 → 값. 관측이 없으면 그 이름을 비워 두어 식이 MissingValue 로 실패하게 한다."""
    tags, wms = _registry()
    env = {k: float(v["value"]) for k, v in fact_rows.items()}
    for w in wms:
        if w.get("kind") == "field":
            env[f"t_{w['field_task']}"] = float(w["plant_duration_s"]) / 3600.0
    for t in tags["tags"]:
        env[f"usl_{var(t['tag'])}"] = t["usl"]
        env[f"lsl_{var(t['tag'])}"] = t["lsl"]
    for tag, value in (state.get("readings") or {}).items():
        env[f"o_{var(tag)}"] = value
    for name, value in (state.get("commands") or {}).items():
        env[f"c_{name}"] = float(value) if value is not None else None
    for name, value in (base_commands or state.get("commands") or {}).items():
        env[f"b_{name}"] = float(value) if value is not None else None
    if state.get("status") == "available":
        env["i_interlock"] = 1.0 if state.get("interlock") else 0.0
        env["i_maintenance"] = 1.0 if state.get("maintenance") else 0.0
    return env


def load_decisions(symptoms: list[str]) -> list[dict]:
    rows = _run_readonly_query("""
        MATCH (s:Symptom)-[:TRIGGERS_DECISION]->(d:Decision) WHERE s.symptom_id IN $symptoms
        WITH DISTINCT d
        RETURN d.decision_id AS decision_id, d.name AS name, d.question AS question,
          d.recovery_all AS recovery_all, d.recovery_hold_s AS recovery_hold_s, d.recovery_timeout_s AS recovery_timeout_s,
          d.shared_derived AS shared_derived,
          COLLECT { MATCH (d)-[:VERIFIED_BY]->(v:DocumentSection) RETURN v.document_id + '#' + v.section_key } AS recovery_section,
          COLLECT { MATCH (s2:Symptom)-[:TRIGGERS_DECISION]->(d) RETURN s2.symptom_id } AS symptoms,
          COLLECT { MATCH (d)-[:REQUIRES_INPUT]->(i:InputData) RETURN i.key } AS inputs,
          COLLECT { MATCH (d)-[:HAS_RULE]->(r:Rule) OPTIONAL MATCH (r)-[:ENCODES]->(p:DocumentSection)
                    RETURN {rule_id: r.rule_id, when: r.when, then: r.then, reason: r.reason,
                            policy: p.document_id + '#' + p.section_key} } AS rules,
          COLLECT { MATCH (d)-[:HAS_OPTION]->(o:Option)
                    RETURN {option_id: o.option_id, name: o.name, kind: o.kind, params: o.params, derived: o.derived,
                            treats: COLLECT { MATCH (o)-[:TREATS]->(fm:FailureMode) RETURN fm.failure_mode_id },
                            procedure: COLLECT { MATCH (o)-[:PROCEDURE]->(sec:DocumentSection) RETURN sec.document_id + '#' + sec.section_key },
                            impacts: COLLECT { MATCH (o)-[r:IMPACTS]->(k:KPI)
                                               RETURN {kpi: k.kpi_id, name: k.name, owner: k.owner, unit: k.unit, expr: r.expr} },
                            steps: COLLECT { MATCH (o)-[:HAS_STEP]->(st:Step) OPTIONAL MATCH (st)-[:USES_WORK_MASTER]->(w:WorkMaster)
                                             RETURN {order: st.order, kind: st.kind, say: st.say, params: st.params, until: st.until,
                                                     hours: st.hours, timeout_s: st.timeout_s,
                                                     abort_on_no_fault: st.abort_on_no_fault, wm: w.name} ORDER BY st.order }} } AS options
        ORDER BY decision_id""", {"symptoms": sorted(set(symptoms))})
    for d in rows:
        d["recovery_all"] = json.loads(d["recovery_all"] or "[]")
        d["shared_derived"] = json.loads(d["shared_derived"] or "{}")
        d["recovery_section"] = (d["recovery_section"] or [None])[0]
        for o in d["options"]:
            o["params"] = json.loads(o["params"] or "{}")
            o["derived"] = json.loads(o["derived"] or "{}")
            o["steps"] = sorted(o["steps"], key=lambda s: s["order"])
            for s in o["steps"]:
                s["params"] = json.loads(s["params"] or "{}")
        d["options"].sort(key=lambda o: o["option_id"])
    return rows


def kpis() -> list[dict]:
    order = ["재무", "고객", "내부 프로세스", "학습과 성장"]   # BSC 관점 순서
    rows = _run_readonly_query("""MATCH (k:KPI) RETURN k.kpi_id AS kpi, k.name AS name, k.unit AS unit,
        k.perspective AS perspective, k.owner AS owner, k.description AS description ORDER BY k.kpi_id""")
    return sorted(rows, key=lambda k: (order.index(k["perspective"]) if k["perspective"] in order else 9, k["kpi"]))


def eligibility(option: dict, assessment: dict[str, str]) -> tuple[bool, str]:
    statuses = {fm: assessment.get(fm, "unknown") for fm in option["treats"]}
    if option["kind"] == "targeted":
        ok = any(s == "supported" for s in statuses.values())
        why = "치료 대상 고장모드가 관측으로 지지됨" if ok else "치료 대상 고장모드가 지지되지 않음(" + ", ".join(f"{k}={v}" for k, v in statuses.items()) + ")"
    else:
        # 점검형 = 원인을 확정하지 못했을 때: 후보가 둘 이상 남았거나(지지·미확인), 지지된 후보 없이 미확인이 남았을 때.
        # 하나가 지지되고 나머지가 반박됐으면 원인이 좁혀진 것이라 원인 대응(targeted) 대안을 쓴다.
        open_ = [k for k, v in statuses.items() if v in ("supported", "unknown")]
        supported = [k for k, v in statuses.items() if v == "supported"]
        ok = len(open_) >= 2 or (not supported and len(open_) >= 1)
        why = (("점검 대상 중 후보가 둘 이상 남음(" + ", ".join(open_) + ")") if len(open_) >= 2 else
               ("지지된 후보 없이 확인 불가 후보가 남음(" + ", ".join(open_) + ")") if ok else
               "원인이 좁혀짐 — 원인 대응 대안을 쓴다" if supported else "점검 대상 고장모드가 모두 반박됨")
    return ok, why


def score_option(decision: dict, option: dict, env: dict, assessment: dict[str, str]) -> dict:
    local = dict(env)
    for k, v in option["params"].items():
        local[f"opt_{k}"] = float(v)
    for fm in option["treats"]:   # 점검형 대안의 기대 부품 사용량 등: AI 평가의 무게
        local[f"a_{var(fm)}"] = WEIGHT.get(assessment.get(fm, "unknown"), 0.5)
    errors = []
    try:
        for k, text in decision["shared_derived"].items():
            local[f"d_{k}"] = float(evaluate(text, local))
        for k, text in option["derived"].items():
            local[f"d_{k}"] = float(evaluate(text, local))
    except (MissingValue, ValueError, ZeroDivisionError) as exc:
        errors.append(f"파생값 계산 불가: {exc}")
    impacts = []
    for imp in option["impacts"]:
        try:
            value = float(evaluate(imp["expr"], local))
            impacts.append({**imp, "value": round(value, 1)})
        except (MissingValue, ValueError, ZeroDivisionError) as exc:
            errors.append(f"{imp['kpi']} 계산 불가: {exc}")
            impacts.append({**imp, "value": None})
    rules = []
    for r in decision["rules"]:
        try:
            hit = bool(evaluate(r["when"], local))
        except MissingValue as exc:
            if not str(exc.args[0]).startswith("opt_"):
                # 안전 규칙이 읽을 관측·사실이 없으면 규칙을 건너뛰지 않고 이 대안을 계산 불가로 둔다
                errors.append(f"규칙 {r['rule_id']} 판단 불가: {exc.args[0]} 값 없음")
            hit = None   # opt_* 없음 = 이 대안에 해당하지 않는 규칙
        except ValueError as exc:
            errors.append(f"규칙 {r['rule_id']} 계산 불가: {exc}")
            hit = None
        if hit:
            rules.append({k: r[k] for k in ("rule_id", "then", "reason", "policy")})
    eligible, why = eligibility(option, assessment)
    excluded = any(r["then"] == "EXCLUDE" for r in rules)
    total = None if errors else round(sum(i["value"] for i in impacts), 1)
    return {"option_id": option["option_id"], "name": option["name"], "kind": option["kind"], "treats": option["treats"],
            "impacts": impacts, "total": total, "rules": rules, "excluded": excluded, "eligible": eligible,
            "eligibility": why, "errors": errors, "procedure": option["procedure"],
            "derived": {k: round(local[f"d_{k}"], 3) for k in [*decision["shared_derived"], *option["derived"]] if f"d_{k}" in local},
            "executable": bool(option["steps"]),
            "steps": [{"order": s["order"], "kind": s["kind"], "say": s["say"], "wm": s["wm"]} for s in option["steps"]]}


def rank(decision: dict, env: dict, assessment: dict[str, str]) -> dict:
    rows = [score_option(decision, o, env, assessment) for o in decision["options"]]
    candidates = [r for r in rows if r["eligible"] and not r["excluded"] and r["total"] is not None and r["executable"]]
    candidates.sort(key=lambda r: -r["total"])
    for i, r in enumerate(candidates, 1):
        r["rank"] = i
    best_any = max((r for r in rows if r["total"] is not None), key=lambda r: r["total"], default=None)
    return {"decision_id": decision["decision_id"], "name": decision["name"], "question": decision["question"],
            "options": sorted(rows, key=lambda r: (r.get("rank") or 99, -(r["total"] or -1e9))),
            "recommended": candidates[0]["option_id"] if candidates else None,
            "runner_up": candidates[1]["option_id"] if len(candidates) > 1 else None,
            "money_best_but_excluded": (best_any["option_id"] if best_any and best_any["excluded"] else None),
            "recovery": {"all": decision["recovery_all"], "hold_s": decision["recovery_hold_s"],
                         "timeout_s": decision["recovery_timeout_s"], "section": decision["recovery_section"]},
            "inputs": decision["inputs"]}


def flips(decision: dict, env: dict, assessment: dict[str, str], fact_rows: dict) -> list[dict]:
    """뒤집힘 표: 사실값 하나만 바꿨을 때 권고가 바뀌는 가장 가까운 값(배수 탐색). 권고가 무엇에 기대는지 보인다."""
    base = rank(decision, env, assessment)["recommended"]
    if base is None:
        return []
    out = []
    for key in decision["inputs"]:
        if key not in fact_rows:
            continue
        original = env[key]
        found = None
        if key.endswith("_qty"):
            values = [0.0] if original >= 1 else [1.0]
        elif original == 0:
            values = [0.5, 1.0, 2.0, 4.0, 8.0]
        else:
            values = [original * f for f in (0.75, 1.25, 0.5, 1.5, 0.25, 2.0, 0.0, 3.0, 5.0)]
        for value in values:
            trial = dict(env)
            trial[key] = value
            winner = rank(decision, trial, assessment)["recommended"]
            if winner is None:      # 그 값에서는 계산이 성립하지 않는다(0 으로 나눔 등) — 뒤집힘이 아니다
                continue
            if winner != base:
                found = {"fact": key, "system": fact_rows[key]["system"], "current": original,
                         "flip_value": round(trial[key], 2), "unit": fact_rows[key]["unit"],
                         "description": fact_rows[key]["description"], "new_recommendation": winner}
                break
        if found:
            out.append(found)
    return sorted(out, key=lambda f: abs((f["flip_value"] - f["current"]) / (f["current"] or 1)))


def analyze(symptoms: list[str], state: dict, assessment: dict[str, str]) -> dict:
    """증상에 연결된 결정마다 대안 순위·제외 규칙·뒤집힘 표. 모델 도구와 승인 재검사가 같은 함수를 쓴다."""
    fact_rows = facts()
    env = environment(state, fact_rows)
    decisions = load_decisions(symptoms)
    result = []
    for d in decisions:
        missing = [k for k in d["inputs"] if k not in fact_rows]
        if missing:
            raise HTTPException(503, f"기업 사실값이 없어 손익을 계산하지 않았습니다: {', '.join(missing)}")
        ranked = rank(d, env, assessment)
        ranked["flips"] = flips(d, env, assessment, fact_rows)
        ranked["facts_used"] = [{"key": k, **{f: fact_rows[k][f] for f in ("system", "value", "unit", "description", "updated_at")}}
                                for k in d["inputs"]]
        result.append(ranked)
    return {"computed_at": datetime.now(timezone.utc).isoformat(), "assessment": assessment, "decisions": result,
            "kpis": kpis(), "plant_status": state.get("status"),
            "method": ("결정론 계산: 손익 식(온톨로지 IMPACTS) × 사실값(enterprise.fact) × 현재 관측. "
                       "자격 = AI 의 고장모드 평가, 제외 = 규칙(정책 절). 순위는 KPI 합계(만원)가 큰 순.")}


def materialize(decision: dict, option_id: str, state: dict) -> dict:
    """선택한 대안의 단계를 실행 가능한 계획으로 고정한다(파라미터 식을 지금 명령값 b_* 로 계산)."""
    option = next((o for o in decision["options"] if o["option_id"] == option_id), None)
    if option is None or not option["steps"]:
        raise HTTPException(422, "선택한 대안에 실행 단계가 없습니다.")
    fact_rows = facts()
    env = environment(state, fact_rows, base_commands=state.get("commands"))
    for k, v in option["params"].items():
        env[f"opt_{k}"] = float(v)
    _, wms = _registry()
    table = {w["work_master_id"]: w for w in wms}
    steps = []
    for s in option["steps"]:
        step = {"order": s["order"], "kind": s["kind"], "say": s["say"], "wm": s["wm"],
                "abort_on_no_fault": s["abort_on_no_fault"] if s["abort_on_no_fault"] is not None else True,
                "status": "pending"}
        if s["kind"] in ("control", "field"):
            w = table.get(s["wm"])
            if w is None:
                raise HTTPException(422, f"등록부에 없는 작업 정의: {s['wm']}")
            step["equipment_id"] = w["equipment_id"]
            step["desc"] = w["desc"]
            step["parameters"] = []
            for pid, text in s["params"].items():
                value = float(evaluate(text, env))
                spec = next((p for p in w["parameters"] if p["id"] == pid), None)
                if spec is None or not (spec["min"] <= value <= spec["max"]):
                    raise HTTPException(422, f"{s['wm']} 파라미터 {pid}={value} 가 작업 정의 범위를 벗어납니다.")
                step["parameters"].append({"id": pid, "value": value})
            if w.get("kind") == "field":
                step["plant_duration_s"] = w["plant_duration_s"]
        elif s["kind"] == "operator":
            step["until"] = s["until"]
            step["timeout_s"] = s["timeout_s"] or 180
        elif s["kind"] == "wait":
            step["plant_hours"] = round(float(evaluate(s["hours"], env)), 3)
        steps.append(step)
    return {"decision_id": decision["decision_id"], "option_id": option_id, "option_name": option["name"],
            "treats": option["treats"], "procedure": option["procedure"], "steps": steps,
            "recovery": {"all": decision["recovery_all"], "hold_s": decision["recovery_hold_s"],
                         "timeout_s": decision["recovery_timeout_s"], "section": decision["recovery_section"]},
            "base_commands": state.get("commands"), "facts_at_plan": {k: v["value"] for k, v in fact_rows.items()}}


def decision_for(symptoms: list[str], option_id: str) -> dict:
    for d in load_decisions(symptoms):
        if any(o["option_id"] == option_id for o in d["options"]):
            return d
    raise HTTPException(422, "이 사건의 증상에 연결된 결정에 없는 대안입니다.")


def finite(x) -> bool:
    return type(x) in (int, float) and math.isfinite(x)


# ── 화면용 조회 ───────────────────────────────────────────────────
from fastapi import APIRouter  # noqa: E402

router = APIRouter(prefix="/api/operations/maintenance", tags=["manufacturing-maintenance"])


@router.get("/facts")
def facts_endpoint():
    """기업 시스템 사실값(손익 계산의 입력). 조회 전용."""
    return {"items": list(facts().values()), "source": "공용 업무 DB enterprise.fact(가상 MES·ERP·CMMS)"}


@router.get("/work-orders")
def work_orders():
    from .plant_db import plant_connection
    with plant_connection() as pc:
        rows = pc.execute("""SELECT id, incident_id, option_id, status, opened_at, closed_at, approver,
                                    report->>'headline' AS headline FROM enterprise.work_order ORDER BY opened_at DESC LIMIT 50""").fetchall()
    return {"items": rows}
