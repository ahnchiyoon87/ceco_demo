"""승인된 정비 계획 실행기(상태 기계, 1초 틱). 계획 단계를 작업 요청으로 하나씩 보내고 결과를 읽어 다음으로 간다.

  control  PLC 작업 요청(기존 길: 공용 DB 기록 → Kafka 승인 토픽 → IT 발송 → DMZ 게이트웨이 → OT 수신기 → PLC)
  field    현장 정비 작업 요청(같은 길, OT 수신기가 가상 정비팀에게 넘긴다). 결과에 현장 소견이 온다
  operator 운전원만 할 수 있는 일(예: 인터록 리셋). AI 는 하지 않고 조건(until)이 참이 되기를 기다린다
  wait     설비 시간 대기(예: 배치 종료까지 운전)
끝나면 회복 기준(온톨로지)을 hold_s 동안 유지하는지 재관측하고, 작업 보고서를 만들어 CMMS 작업 이력에 남긴다.

상태는 매 전이마다 DB(manufacturing_proposals.result.plan_state)에 남는다. 재시작해도 이어 가며,
이미 보낸 요청은 다시 보내지 않는다(요청 ID 로 결과만 다시 읽는다). 결과가 불명확하면 멈추고 사람에게 넘긴다.
"""
from __future__ import annotations

import asyncio
import copy
import logging
import os
import time
from datetime import datetime, timezone
from uuid import uuid4

from psycopg.types.json import Jsonb

from .decision import MissingValue, environment, evaluate, facts

log = logging.getLogger(__name__)
SCALE = float(os.environ.get("PHYSICS_TIME_SCALE", "600"))
CONTROL_TIMEOUT_S = 60
FIELD_GRACE_S = 60
TERMINAL_FAIL = {"gateway_rejected", "command_disagree", "unconfirmed", "expired_unconfirmed"}


def now() -> float:
    return time.time()


def iso(ts: float | None) -> str | None:
    return datetime.fromtimestamp(ts, timezone.utc).isoformat() if ts else None


def start_state(plan: dict, before: dict, approver: str, note: str) -> dict:
    """승인 시점의 실행 상태. before = 승인 시점 설비 상태(보고서의 '전' 값)."""
    return {"status": "executing_plan", "phase": "steps", "current": 0, "started_at": now(),
            "approver": approver, "approval_note": note, "before": _snapshot(before),
            "steps": copy.deepcopy(plan["steps"]), "verify": None, "report": None,
            "reason": "승인된 정비 계획을 실행합니다."}


def _snapshot(state: dict) -> dict:
    return {"at": state.get("retrieved_at"), "readings": state.get("readings", {}), "commands": state.get("commands", {}),
            "interlock": state.get("interlock"), "maintenance": state.get("maintenance"), "mode": state.get("mode")}


# ── 작업 요청 보내기·읽기 ─────────────────────────────────────────────
def submit(step: dict, proposal: dict, note: str) -> str:
    """작업 요청 한 건을 공용 업무 DB 에 기록하고 승인 토픽에 알린다. 다시 보내지 않는다."""
    from .actions import _announce_approved
    from .plant_db import audit, plant_connection, request_event
    jid = f"ai-{uuid4().hex}"
    approver = os.environ.get("AI_APPROVER_ID", "operator-01")
    context = {"summary": f"{step['say']} — 정비 계획 {proposal['plan']['option_id']} {step['order']}단계",
               "proposal_id": str(proposal["id"]), "plan_step": step["order"]}
    with plant_connection() as pc:
        pc.execute("""INSERT INTO workflow.request(job_order_id, work_master_id, equipment_id, job_order_parameters,
                      requester, requester_type, approver, context, incident_id, proposal_id) VALUES (%s,%s,%s,%s,%s,'ai',%s,%s,%s,%s)""",
                   (jid, step["wm"], step["equipment_id"], Jsonb(step.get("parameters", [])), "ai-ops", approver,
                    Jsonb(context), proposal["incident_id"], proposal["id"]))
        request_event(pc, jid, "approved", "APPROVED", note or None,
                      {"plan_option": proposal["plan"]["option_id"], "plan_step": step["order"]}, "ai-app")
        audit(pc, "ai", "ai-ops", "propose", jid, step["wm"], {"plan_step": step["order"]})
        audit(pc, "human", approver, "approve", jid, step["wm"], {"note": note, "plan": proposal["plan"]["option_id"]})
    if not _announce_approved(jid):
        with plant_connection() as pc:
            request_event(pc, jid, "not_dispatched", "KAFKA_UNAVAILABLE", "승인 토픽에 알리지 못함", {}, "ai-app")
        raise RuntimeError("발송 통로(Kafka)에 알리지 못했습니다.")
    return jid


def request_events(jid: str) -> list[dict]:
    from .plant_db import plant_connection
    with plant_connection() as pc:
        return pc.execute("""SELECT kind, status, reason, detail, extract(epoch FROM at) AS at
                             FROM workflow.request_event WHERE job_order_id=%s ORDER BY id""", (jid,)).fetchall()


def judge_request(step: dict, events: list[dict]) -> tuple[str, dict]:
    """요청 사건 → (done | failed | no_fault | waiting | waiting_operator, 세부)."""
    info = {}
    field = next((e for e in events if e["kind"] == "field"), None)
    if field:
        detail = field.get("detail") or {}
        info = {"field_status": field["status"], "finding": detail.get("finding") or field["reason"],
                "effective": detail.get("effective"), "wall_s": detail.get("wall_s"),
                "plant_duration_s": detail.get("plant_duration_s")}
    for e in events:
        k, st = e["kind"], e["status"]
        if k in TERMINAL_FAIL or (k in ("receipt", "operator", "plc", "field") and st in ("REJECTED", "OPERATOR_REJECTED", "UNKNOWN")):
            return "failed", {**info, "stage": k, "status": st, "reason": e["reason"]}
        if k == "observed":
            if info.get("field_status") == "DONE_NO_FAULT":
                return "no_fault", info
            return "done", {**info, "observed": e["reason"]}
    if any(e["kind"] == "receipt" and e["status"] == "OPERATOR_WAIT" for e in events) and not any(e["kind"] == "operator" for e in events):
        return "waiting_operator", info
    return "waiting", info


# ── 한 계획의 다음 전이 ─────────────────────────────────────────────
def advance(proposal: dict, state: dict, ps: dict, fact_rows: dict) -> dict:
    """한 틱 동안 할 수 있는 만큼 계획을 진행한다. ps(plan_state) 사본을 고쳐 돌려준다."""
    ps = copy.deepcopy(ps)
    plan = proposal["plan"]
    t = now()
    if ps["phase"] in ("steps", "cleanup"):
        if ps["current"] >= len(ps["steps"]):
            if ps["phase"] == "cleanup":   # 중단 정리 끝: 회복 판정 없이 종료(원래 결과 유지)
                ps["phase"] = "done"
                return ps
            ps["phase"] = "verify"
            ps["verify"] = {"started_at": t, "within_since": None, "held_s": 0, "samples": [], "last": None}
            return ps
        step = ps["steps"][ps["current"]]
        if step["status"] == "pending":
            step["started_at"] = t
            if step["kind"] in ("control", "field"):
                try:
                    step["job_order_id"] = submit(step, proposal, ps.get("approval_note", ""))
                    step["status"] = "sent"
                except Exception as exc:
                    step.update(status="failed", reason=f"작업 요청을 보내지 못했습니다({type(exc).__name__}). 다시 보내지 않았습니다.")
                    return fail(ps, step)
            else:
                step["status"] = "running"
            return ps
        if step["kind"] in ("control", "field") and step["status"] == "sent":
            verdict, info = judge_request(step, request_events(step["job_order_id"]))
            step.update({k: v for k, v in info.items() if v is not None})
            budget = CONTROL_TIMEOUT_S if step["kind"] == "control" else step.get("plant_duration_s", 0) / SCALE + FIELD_GRACE_S
            if verdict == "waiting_operator":
                step["waiting_operator"] = True
                budget += 95
            if verdict == "done":
                return complete(ps, step, "done")
            if verdict == "no_fault":
                if step.get("abort_on_no_fault", True):
                    step.update(status="no_fault", finished_at=t,
                                reason="현장 정비 소견: 이 작업의 대상에서 고장을 찾지 못했습니다. 원인 판단이 틀렸을 수 있어 계획을 멈춥니다.")
                    return fail(ps, step, outcome="cause_mismatch")
                return complete(ps, step, "done_no_fault")
            if verdict == "failed":
                step.update(status="failed", finished_at=t,
                            reason=f"{info.get('stage')} 단계 {info.get('status')}: {info.get('reason')}. 다시 보내지 않았습니다.")
                return fail(ps, step)
            if t - step["started_at"] > budget:
                step.update(status="failed", finished_at=t, reason="결과 확인 시간이 지났습니다. 다시 보내지 않았습니다. 요청 사건을 확인하세요.")
                return fail(ps, step)
            return ps
        if step["kind"] == "operator":
            env = environment(state, fact_rows, plan.get("base_commands"))
            try:
                ok = bool(evaluate(step["until"], env))
            except MissingValue:
                ok = False
            step["waiting_operator"] = not ok
            if ok:
                return complete(ps, step, "done", reason="운전원 조치 확인(조건 충족)")
            if t - step["started_at"] > float(step.get("timeout_s") or 180):
                step.update(status="failed", finished_at=t, reason="운전원 조치를 시간 안에 확인하지 못했습니다.")
                return fail(ps, step)
            return ps
        if step["kind"] == "wait":
            need = float(step.get("plant_hours", 0)) * 3600.0 / SCALE
            step["remaining_s"] = round(max(0.0, need - (t - step["started_at"])), 1)
            if t - step["started_at"] >= need:
                return complete(ps, step, "done", reason=f"설비 시간 {step.get('plant_hours')} h 경과")
            return ps
        return ps
    if ps["phase"] == "verify":
        v = ps["verify"]
        rec = plan["recovery"]
        env = environment(state, fact_rows, plan.get("base_commands"))
        results = []
        for text in rec["all"]:
            try:
                results.append({"criterion": text, "ok": bool(evaluate(text, env))})
            except MissingValue as exc:
                results.append({"criterion": text, "ok": False, "missing": exc.args[0]})
        inside = state.get("status") == "available" and all(r["ok"] for r in results)
        if inside:
            v["within_since"] = v["within_since"] or t
        else:
            v["within_since"] = None
        v["held_s"] = round(t - v["within_since"], 1) if v["within_since"] else 0
        v["last"] = {"at": t, "results": results}
        watch = sorted({n[2:] for text in rec["all"] for n in _names(text) if n.startswith("o_")})
        v["samples"] = (v["samples"] + [{"at": t, **{k: env.get(f"o_{k}") for k in watch}}])[-240:]
        if v["held_s"] >= rec["hold_s"]:
            ps["phase"] = "done"
            ps["outcome"] = "recovered"
            ps["reason"] = f"회복 기준을 {rec['hold_s']}초 이상 유지했습니다."
        elif t - v["started_at"] > rec["timeout_s"]:
            ps["phase"] = "done"
            ps["outcome"] = "not_recovered"
            ps["reason"] = f"정비 뒤 {rec['timeout_s']}초 안에 회복 기준을 유지하지 못했습니다. 원인이 남아 있을 수 있습니다."
        return ps
    return ps


def _names(text):
    import re
    return re.findall(r"[A-Za-z_][A-Za-z0-9_]*", text)


def complete(ps, step, status, reason=None):
    step.update(status=status, finished_at=now())
    if reason:
        step["reason"] = reason
    ps["current"] += 1
    return ps


CLEANUP_WM = "WM-FLD-LOTO-RELEASE"


def fail(ps, step, outcome="step_failed"):
    """계획을 멈춘다. 이 계획이 정비 모드(LOTO)를 켰고 아직 풀지 않았으면, 정비팀이 분해 부위를 복구하고 격리를 푸는
    정리 단계를 하고 끝낸다(설비는 정지 상태로 인계 — 원인이 남아 재기동하지 않는다). 정리 중 실패는 다시 정리하지 않는다."""
    ps["outcome"] = ps.get("outcome") or outcome
    ps["reason"] = ps.get("reason") if ps["phase"] == "cleanup" else step.get("reason")
    locked = any(s.get("wm") == "WM-PLC-MAINT-ON" and s["status"].startswith("done") for s in ps["steps"])
    released = any(s.get("wm") == CLEANUP_WM and s["status"].startswith("done") for s in ps["steps"])
    if ps["phase"] == "steps" and locked and not released:
        from .decision import _registry
        _, wms = _registry()
        w = next(w for w in wms if w["work_master_id"] == CLEANUP_WM)
        ps["steps"] = [s for s in ps["steps"] if s["status"] != "pending"]   # 남은 정상 단계는 하지 않는다
        for s in ps["steps"]:
            s.setdefault("finished_at", now())
        ps["steps"].append({"order": len(ps["steps"]) + 1, "kind": "field", "wm": CLEANUP_WM, "equipment_id": w["equipment_id"],
                            "desc": w["desc"], "parameters": [], "plant_duration_s": w["plant_duration_s"], "status": "pending",
                            "abort_on_no_fault": False, "cleanup": True,
                            "say": "중단 정리: 분해 부위 복구·격리(LOTO) 해제 — 설비는 정지 상태로 인계"})
        ps["current"] = len(ps["steps"]) - 1
        ps["phase"] = "cleanup"
        return ps
    ps["phase"] = "done"
    return ps


# ── 보고서 ─────────────────────────────────────────────────────────
PARTS = {"bearing_replace": ("erp_bearing_cost", "교반기 베어링 세트"), "jacket_descale": ("erp_descale_cost", "재킷 세정 약품·폐액"),
         "strainer_clean": ("erp_strainer_kit_cost", "스트레이너 가스켓·소모품"), "cv_repair": ("erp_cv_kit_cost", "배출 밸브 정비 키트")}


def report(proposal: dict, ps: dict, after: dict, fact_rows: dict) -> dict:
    """작업 보고서: 무엇을 했나·현장 소견·전후 값·회복 판정·예상 대비 실적 비용. 숫자는 기록에서만 만든다."""
    plan = proposal["plan"]
    value = lambda k: float(fact_rows[k]["value"]) if k in fact_rows else 0.0
    steps = ps["steps"]
    field_h = sum(float(s.get("plant_duration_s") or 0) for s in steps if s["kind"] == "field" and s["status"].startswith("done")) / 3600
    parts = []
    for s in steps:
        for key, (fact, label) in PARTS.items():
            if s["kind"] == "field" and s.get("field_status") == "DONE" and s.get("effective") and _task_of(s) == key:
                parts.append({"item": label, "cost": value(fact)})
    # 정지 시간(설비 시간 = 벽시계 × 배속): 설비가 멈춘 때부터 재기동 단계 완료까지.
    # 멈춘 때 = 정지 단계 완료, 또는 승인 시점에 이미 멈춰 있었으면(예: 인터록 트립) 계획 시작.
    switch = {"P-101": "pump_run", "M-101": "agitator_run"}
    start = next((s for s in steps if s.get("wm") in ("WM-P101-START", "WM-M101-START")), None)
    equipment = (start or {}).get("equipment_id") or next(
        (s.get("equipment_id") for s in steps if s.get("wm") in ("WM-P101-STOP", "WM-M101-STOP")), None)
    stop = next((s for s in steps if s.get("wm") in ("WM-P101-STOP", "WM-M101-STOP") and s.get("finished_at")), None)
    was_running = (ps["before"].get("commands") or {}).get(switch.get(equipment, ""), True) and not ps["before"].get("interlock")
    down_from = (stop or {}).get("finished_at") if was_running else ps.get("started_at")
    down_to = (start or {}).get("finished_at") or ps.get("finished_at") or now()
    down_h = max(0.0, (down_to - down_from) * SCALE / 3600) if down_from else 0.0
    # 배치 폐기: 이 계획이 돌고 있던 교반기를 배치 도중 멈췄을 때만(앞선 정지로 이미 멈춰 있었으면 이미 폐기된 배치다)
    agitator_was_running = bool((ps["before"].get("commands") or {}).get("agitator_run"))
    scrap = (value("mes_batch_scrap_cost") if stop and stop.get("wm") == "WM-M101-STOP" and agitator_was_running
             and not any(s["kind"] == "wait" for s in steps) else 0.0)
    actual = {"production_loss": round(-(down_h * value("mes_hour_value") + scrap), 1),
              "maint_cost": round(-(field_h * value("cmms_labor_per_h") + sum(p["cost"] for p in parts)), 1),
              "downtime_plant_h": round(down_h, 2), "field_work_plant_h": round(field_h, 2), "parts": parts,
              "batch_scrapped": bool(scrap)}
    # 이상 상태 지속 시간(정비 실행 구간 = 승인 → 종료, 센서 이력): 예상 손익의 hot_h 와 같은 구간이다.
    # 분석·검토에 든 시간은 배속 설비에서 설비 시간으로 부풀려지므로 넣지 않는다(계획이 책임지는 구간만 비교).
    watch = WATCH.get(plan["decision_id"])
    if watch:
        tag, kpis = watch
        over_h, ratio = exceed_hours(tag, ps.get("started_at"), ps.get("finished_at") or now())
        actual["over_limit_tag"] = tag
        actual["over_limit_plant_h"] = None if over_h is None else round(over_h, 2)
        if over_h is not None:
            for kpi, fact in kpis:
                factor = ratio if kpi == "equipment_risk" and tag == "VT-101" else 1.0
                actual[kpi] = round(-over_h * value(fact) * factor, 1)
    chosen = next((o for d in plan.get("evaluation", {}).get("decisions", []) for o in d["options"]
                   if o["option_id"] == plan["option_id"]), None)
    predicted = {i["kpi"]: i["value"] for i in (chosen or {}).get("impacts", [])}
    key_tags = sorted({n[2:].replace("_", "-") for text in plan["recovery"]["all"] for n in _names(text) if n.startswith("o_")})
    before, after_r = ps["before"]["readings"], after.get("readings", {})
    findings = [{"order": s["order"], "say": s["say"], "finding": s.get("finding"), "field_status": s.get("field_status")}
                for s in steps if s["kind"] == "field" and s.get("finding")]
    outcome = ps.get("outcome")
    headline = {"recovered": "정비 완료·회복 확인", "not_recovered": "정비 완료·회복 미확인(조치 실패)",
                "cause_mismatch": "현장 소견이 원인 판단과 다름(계획 중단)", "step_failed": "실행 중단(단계 실패)"}.get(outcome, outcome)
    cleanup = next((s for s in steps if s.get("cleanup")), None)
    return {
        "work_order_id": ps.get("work_order_id"), "headline": headline, "outcome": outcome, "reason": ps.get("reason"),
        "cleanup": cleanup and {"status": cleanup["status"], "finding": cleanup.get("finding"),
                                "note": "정비 모드를 해제하고 설비는 정지 상태로 인계했습니다." if cleanup["status"].startswith("done")
                                        else "격리 해제를 확인하지 못했습니다. 현장에서 정비 모드 상태를 확인하세요."},
        "option": {"id": plan["option_id"], "name": plan["option_name"], "decision": plan["decision_id"]},
        "approver": ps.get("approver"), "approval_note": ps.get("approval_note"),
        "started_at": iso(ps.get("started_at")), "finished_at": iso(ps.get("finished_at")),
        "steps": [{"order": s["order"], "kind": s["kind"], "say": s["say"], "wm": s.get("wm"), "status": s["status"],
                   "job_order_id": s.get("job_order_id"), "finding": s.get("finding"), "reason": s.get("reason"),
                   "wall_s": round(s["finished_at"] - s["started_at"], 1) if s.get("finished_at") and s.get("started_at") else None}
                  for s in steps],
        "findings": findings,
        "before_after": [{"tag": tag, "before": before.get(tag), "after": after_r.get(tag)} for tag in key_tags],
        "recovery": {"criteria": plan["recovery"]["all"], "hold_s": plan["recovery"]["hold_s"],
                     "held_s": (ps.get("verify") or {}).get("held_s"), "last": (ps.get("verify") or {}).get("last")},
        "kpi": {"predicted": predicted, "predicted_total": (chosen or {}).get("total"), "actual": actual},
        "next": _next_step(outcome, findings),
    }


WATCH = {  # 결정 → (상한 초과를 재는 태그, [(실적 KPI, 시간당 사실값)])
    "DEC-COOLING-RECOVERY": ("TT-101", [("quality_loss", "mes_offspec_loss_per_h"), ("equipment_risk", "cmms_overtemp_risk_per_h")]),
    "DEC-AGITATOR-REPAIR": ("VT-101", [("equipment_risk", "cmms_seizure_risk_per_h")]),
}


def exceed_hours(tag, start, stop):
    """[start, stop] 벽시계 구간에서 tag 가 상한을 넘은 설비 시간[h]과 평균 초과 비(값/상한). 이력이 없으면 (None, 1)."""
    from .decision import _registry
    from .evidence import history
    if not start:
        return None, 1.0
    tags, _ = _registry()
    usl = next((t["usl"] for t in tags["tags"] if t["tag"] == tag), None)
    data = history(tags["hierarchy"]["site"], tags["hierarchy"]["line"], [tag], int(start * 1e9), int(stop * 1e9))
    rows = [r for r in data.get("rows", []) if r.get("quality") == "GOOD"]
    if data.get("status") not in ("available", "missing") or usl is None:
        return None, 1.0
    points = [(datetime.fromisoformat(r["time"].replace("Z", "+00:00")).timestamp(), r["value"]) for r in rows]
    points.sort()
    over, weighted = 0.0, 0.0
    for (t0, v0), (t1, _) in zip(points, points[1:] + [(stop, None)]):
        if v0 > usl:
            dt = max(0.0, min(t1, stop) - t0)
            over += dt
            weighted += dt * v0 / usl
    return over * SCALE / 3600, (weighted / over if over else 1.0)


def _task_of(step):
    from .decision import _registry
    _, wms = _registry()
    w = next((w for w in wms if w["work_master_id"] == step.get("wm")), {})
    return w.get("field_task")


def _next_step(outcome, findings):
    if outcome == "recovered":
        return "회복 기준을 유지했습니다. 다음 정기 점검에서 같은 설비의 재발 여부를 확인합니다."
    hint = " ".join(f["finding"] for f in findings if f.get("field_status") == "DONE_NO_FAULT")
    return ("원인이 남아 있습니다. 현장 소견을 근거로 다시 분석하세요." + (f" 소견: {hint}" if hint else "")).strip()


# ── 틱 ───────────────────────────────────────────────────────────
def tick():
    from .actions import connection, event
    from .evidence import live_state
    with connection() as conn:
        pending = conn.execute("""SELECT id FROM manufacturing_proposals
            WHERE status='executing' AND plan IS NOT NULL AND result->>'status'='executing_plan'""").fetchall()
    if not pending:
        return
    state = live_state()
    fact_rows = facts()
    for item in pending:
        with connection() as conn:
            conn.execute("SET LOCAL lock_timeout = '2s'")
            proposal = conn.execute("SELECT * FROM manufacturing_proposals WHERE id=%s FOR UPDATE", (item["id"],)).fetchone()
            if proposal["status"] != "executing" or proposal["result"].get("status") != "executing_plan":
                continue
            ps = proposal["result"]["plan_state"]
            before_phase = ps["phase"]
            updated = advance(proposal, state, ps, fact_rows)
            result = {**proposal["result"], "plan_state": updated}
            if updated["phase"] == "done":
                updated["finished_at"] = now()
                updated["work_order_id"] = f"WO-{datetime.now(timezone.utc):%y%m%d}-{str(proposal['id'])[:8].upper()}"
                rep = report(proposal, updated, live_state(), fact_rows)
                updated["report"] = rep
                final = "resolved" if updated["outcome"] == "recovered" else "unresolved"
                result.update(status=updated["outcome"], reason=updated["reason"], plan_state=updated, report=rep)
                conn.execute("UPDATE manufacturing_proposals SET status=%s,result=%s,completed_at=now() WHERE id=%s",
                             (final, Jsonb(result), proposal["id"]))
                conn.execute("UPDATE manufacturing_incidents SET status=%s,revision=revision+1,review_revision=review_revision+1 WHERE id=%s",
                             (final, proposal["incident_id"]))
                event(conn, proposal["incident_id"], "maintenance_report", {"proposal_id": str(proposal["id"]), **rep})
                _record_work_order(proposal, updated, rep)
                continue
            conn.execute("UPDATE manufacturing_proposals SET result=%s WHERE id=%s", (Jsonb(result), proposal["id"]))
            # 단계 상태가 바뀔 때마다 사건 기록에 남긴다(화면의 진행 표시·감사)
            for old, new in zip(ps["steps"], updated["steps"]):
                if old.get("status") != new.get("status"):
                    event(conn, proposal["incident_id"], "maintenance_progress", {
                        "proposal_id": str(proposal["id"]), "phase": updated["phase"],
                        "step": {k: new.get(k) for k in ("order", "kind", "say", "status", "finding", "job_order_id", "reason")}})
            if updated["phase"] != before_phase:
                event(conn, proposal["incident_id"], "maintenance_progress", {
                    "proposal_id": str(proposal["id"]), "phase": updated["phase"], "step": None})


def _record_work_order(proposal, ps, rep):
    from .plant_db import plant_connection
    try:
        with plant_connection() as pc:
            pc.execute("""INSERT INTO enterprise.work_order(id, incident_id, proposal_id, equipment_id, option_id, status,
                          opened_at, closed_at, approver, report) VALUES (%s,%s,%s,%s,%s,%s,to_timestamp(%s),to_timestamp(%s),%s,%s)
                          ON CONFLICT (id) DO NOTHING""",
                       (ps["work_order_id"], str(proposal["incident_id"]), str(proposal["id"]),
                        next((s.get("equipment_id") for s in ps["steps"] if s.get("equipment_id")), None),
                        proposal["plan"]["option_id"], rep["outcome"], ps["started_at"], ps["finished_at"], ps.get("approver"),
                        Jsonb(rep)))
    except Exception:
        log.exception("CMMS 작업 이력 기록 실패(보고서는 AI 사건 기록에 남았다)")


async def run(stop):
    while not stop.is_set():
        try:
            await asyncio.to_thread(tick)
        except Exception:
            log.exception("정비 계획 진행 실패 — 다음 틱에서 다시 읽는다(보낸 요청은 다시 보내지 않는다)")
        try:
            await asyncio.wait_for(stop.wait(), timeout=1)
        except asyncio.TimeoutError:
            pass
