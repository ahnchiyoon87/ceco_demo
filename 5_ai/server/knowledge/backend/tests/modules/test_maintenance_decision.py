"""정비 판단 엔진·실행기 단위 시험(DB·그래프 없음). 실제 온톨로지 YAML 과 기업 사실값 시드(30_enterprise.sql)를 읽는다.

    docker run --rm -v <repo>:/repo -e REGISTRY_DIR=/repo/shared/registry/generated -w /app \
      ceco-ai-knowledge:base python -m pytest /repo/5_ai/server/knowledge/backend/tests/modules/test_maintenance_decision.py
"""
import json
import os
import re
from pathlib import Path

import pytest
import yaml

REPO = Path(os.environ.get("REPO_ROOT", "/repo"))
os.environ.setdefault("REGISTRY_DIR", str(REPO / "shared/registry/generated"))

from backend.src.modules.operations import decision, maintenance  # noqa: E402

KG = yaml.safe_load((REPO / "5_ai/ontology/v2/kg/maintenance-decisions.yaml").read_text(encoding="utf-8"))


def seed_facts():
    sql = (REPO / "4_it/db-postgres/init/30_enterprise.sql").read_text(encoding="utf-8")
    rows = re.findall(r"\('(\w+)',\s*'(MES|ERP|CMMS)',\s*([\d.]+),\s*'([^']*)',\s*'([^']*)'\)", sql)
    return {k: {"key": k, "system": s, "value": float(v), "unit": u, "description": d, "updated_at": None} for k, s, v, u, d in rows}


def as_loaded(d):
    """load_decisions() 가 그래프에서 돌려주는 모양으로 YAML 결정을 바꾼다."""
    names = set()
    def collect(text):
        names.update(n for n in re.findall(r"[A-Za-z_][A-Za-z0-9_]*", str(text)) if n in FACTS)
    for o in d["options"]:
        for t in [*o["impacts"].values(), *o.get("derived", {}).values()]:
            collect(t)
    for r in d.get("rules", []):
        collect(r["when"])
    for t in d.get("shared_derived", {}).values():
        collect(t)
    return {"decision_id": d["id"], "name": d["name"], "question": d["question"], "recovery_all": d["recovery"]["all"],
            "recovery_hold_s": d["recovery"]["hold_s"], "recovery_timeout_s": d["recovery"]["timeout_s"],
            "recovery_section": d["recovery"]["section"], "shared_derived": d.get("shared_derived", {}),
            "symptoms": [d["triggered_by"]], "inputs": sorted(names),
            "rules": [{"rule_id": r["id"], "when": r["when"], "then": r["then"], "reason": r["reason"], "policy": r["policy"]}
                      for r in d.get("rules", [])],
            "options": [{"option_id": o["id"], "name": o["name"], "kind": o["kind"], "params": o.get("params", {}),
                         "derived": o.get("derived", {}), "treats": o["treats"], "procedure": o.get("procedure", []),
                         "impacts": [{"kpi": k, "name": k, "owner": "", "unit": "만원", "expr": e} for k, e in o["impacts"].items()],
                         "steps": [{"order": n, "kind": s["kind"], "say": s["say"], "params": s.get("params", {}),
                                    "until": s.get("until"), "hours": s.get("hours"), "timeout_s": s.get("timeout_s"),
                                    "abort_on_no_fault": s.get("abort_on_no_fault", True), "wm": s.get("wm")}
                                   for n, s in enumerate(o.get("steps", []), 1)]} for o in d["options"]]}


FACTS = seed_facts()
DECISIONS = {d["id"]: as_loaded(d) for d in KG["decisions"]}


def state(readings, **commands):
    base = {"pump_run": True, "agitator_run": True, "heater_enable": True, "cooler_enable": True,
            "pump_speed_sp": 60.0, "valve_open_sp": 45.0, "temp_sp_c": 72.0}
    return {"status": "available", "readings": readings, "commands": {**base, **commands},
            "interlock": commands.pop("interlock", False) if "interlock" in commands else False, "maintenance": False}


THERMAL_STRAINER = {"TT-101": 103.6, "TT-102": 101.2, "TT-103": 20.0, "TT-104": 59.8, "FT-103": 2.4, "PDT-103": 1.72}
MIXER_BEARING = {"IT-102": 10.22, "VT-101": 8.24, "LT-102": 53.6}
PRESSURE_DRIFT = {"PT-101": 6.8, "PT-102": 3.2, "LT-102": 53.0, "FT-101": 0.0, "FT-102": 5.9, "TT-101": 72.5}


def ranked(did, readings, assessment, facts=None, **cmd):
    env = decision.environment(state(readings, **cmd), facts or FACTS)
    return decision.rank(DECISIONS[did], env, assessment)


def test_every_decision_reads_only_declared_facts_and_seed_has_them():
    declared = {k for i in KG["inputs"] for k in i["keys"]}
    for d in DECISIONS.values():
        assert set(d["inputs"]) <= declared
        assert set(d["inputs"]) <= set(FACTS)


def test_strainer_supported_picks_online_switch_family_and_jacket_options_are_ineligible():
    r = ranked("DEC-COOLING-RECOVERY", THERMAL_STRAINER,
               {"FM-CW-STRAINER-CLOG": "supported", "FM-JACKET-FOULING": "refuted", "FM-HEATER-STUCK-ON": "refuted"})
    by = {o["option_id"]: o for o in r["options"]}
    assert r["recommended"] in {"OPT-CW-SWITCH-ONLINE", "OPT-CW-DERATE-SWITCH"}
    assert not by["OPT-JACKET-DESCALE"]["eligible"]
    assert not by["OPT-COOLING-FULL-INSPECT"]["eligible"]       # 점검형: 원인이 좁혀졌으면(지지 1·반박 1) 자격 없음


def test_overtemp_run_is_excluded_by_policy_even_if_cheaper():
    r = ranked("DEC-COOLING-RECOVERY", {**THERMAL_STRAINER, "FT-103": 30.0, "PDT-103": 0.12, "TT-104": 22.9},
               {"FM-CW-STRAINER-CLOG": "refuted", "FM-JACKET-FOULING": "supported"})
    by = {o["option_id"]: o for o in r["options"]}
    assert by["OPT-JACKET-DERATE-RUN"]["excluded"]
    assert by["OPT-JACKET-DERATE-RUN"]["rules"][0]["policy"] == "AR100-MAINT-POLICY#3"
    assert r["recommended"] == "OPT-JACKET-DESCALE"


def test_descale_needs_chemical_stock():
    facts = {**FACTS, "erp_descale_chem_qty": {**FACTS["erp_descale_chem_qty"], "value": 0.0}}
    r = ranked("DEC-COOLING-RECOVERY", THERMAL_STRAINER, {"FM-JACKET-FOULING": "supported"}, facts)
    assert {o["option_id"]: o for o in r["options"]}["OPT-JACKET-DESCALE"]["excluded"]


def test_bearing_after_batch_wins_until_vibration_reaches_zone_d():
    a = {"FM-MIXER-BEARING-WEAR": "supported", "FM-MIXER-SHAFT-MISALIGNMENT": "refuted"}
    assert ranked("DEC-AGITATOR-REPAIR", MIXER_BEARING, a)["recommended"] == "OPT-BEARING-AFTER-BATCH"
    severe = ranked("DEC-AGITATOR-REPAIR", {**MIXER_BEARING, "VT-101": 11.5}, a)
    by = {o["option_id"]: o for o in severe["options"]}
    assert by["OPT-BEARING-AFTER-BATCH"]["excluded"]
    assert severe["recommended"] == "OPT-BEARING-NOW"


def test_no_spare_bearing_excludes_replacement():
    facts = {**FACTS, "erp_spare_bearing_qty": {**FACTS["erp_spare_bearing_qty"], "value": 0.0}}
    r = ranked("DEC-AGITATOR-REPAIR", MIXER_BEARING, {"FM-MIXER-BEARING-WEAR": "supported"}, facts)
    assert r["recommended"] is None                               # 승인할 교체안 없음 → 근거 보완·조달 판단
    assert all(o["excluded"] for o in r["options"] if "BEARING" in o["option_id"])


def test_unknown_cause_allows_only_inspection_options():
    r = ranked("DEC-AGITATOR-REPAIR", MIXER_BEARING,
               {"FM-MIXER-BEARING-WEAR": "unknown", "FM-MIXER-SHAFT-MISALIGNMENT": "unknown"})
    assert r["recommended"] == "OPT-AGITATOR-INSPECT-BOTH"


def test_interlock_bypass_is_best_money_but_excluded():
    r = ranked("DEC-PRESSURE-RESPONSE", PRESSURE_DRIFT, {"FM-PT101-DRIFT": "supported", "FM-OUTLET-RESTRICTION": "refuted"},
               interlock=True)
    assert r["money_best_but_excluded"] == "OPT-INTERLOCK-BYPASS"
    assert r["recommended"] == "OPT-PT-CALIBRATE"


def test_flip_table_names_the_fact_that_changes_the_bearing_recommendation():
    a = {"FM-MIXER-BEARING-WEAR": "supported"}
    env = decision.environment(state(MIXER_BEARING), FACTS)
    flips = decision.flips(DECISIONS["DEC-AGITATOR-REPAIR"], env, a, FACTS)
    keys = {f["fact"] for f in flips}
    assert {"mes_batch_scrap_cost", "cmms_seizure_risk_per_h"} & keys
    assert all(f["new_recommendation"] != "OPT-BEARING-AFTER-BATCH" for f in flips)


def test_missing_observation_blocks_safety_rule_instead_of_skipping_it():
    r = ranked("DEC-COOLING-RECOVERY", {k: v for k, v in THERMAL_STRAINER.items() if k != "TT-101"},
               {"FM-JACKET-FOULING": "supported"})
    by = {o["option_id"]: o for o in r["options"]}
    assert by["OPT-JACKET-DERATE-RUN"]["errors"]
    assert by["OPT-JACKET-DERATE-RUN"]["total"] is None


def test_expression_evaluator_rejects_code():
    with pytest.raises(ValueError):
        decision.evaluate("__import__('os').system('true')", {})
    with pytest.raises(ValueError):
        decision.evaluate("o_TT_101.real", {"o_TT_101": 1.0})


# ── 실행기 ─────────────────────────────────────────────────────────
def plan_for(option_id, did, readings, **cmd):
    d = DECISIONS[did]
    original = decision.facts
    decision.facts = lambda: FACTS
    try:
        return decision.materialize(d, option_id, state(readings, **cmd))
    finally:
        decision.facts = original


def test_materialized_derate_parameter_is_computed_from_current_speed_and_in_range():
    plan = plan_for("OPT-CW-DERATE-SWITCH", "DEC-COOLING-RECOVERY", THERMAL_STRAINER, pump_speed_sp=70.0)
    first = plan["steps"][0]
    assert first["wm"] == "WM-P101-SPEED" and first["parameters"] == [{"id": "pump_speed_pct", "value": 42.0}]
    assert plan["steps"][-1]["parameters"] == [{"id": "pump_speed_pct", "value": 70.0}]


def test_executor_stops_on_field_no_fault_and_never_resends(monkeypatch):
    plan = plan_for("OPT-BEARING-NOW", "DEC-AGITATOR-REPAIR", MIXER_BEARING)
    proposal = {"id": "p", "incident_id": "i", "plan": plan}
    sent = []
    monkeypatch.setattr(maintenance, "submit", lambda step, p, note: sent.append(step["wm"]) or f"job-{len(sent)}")
    events = {}
    monkeypatch.setattr(maintenance, "request_events", lambda jid: events.get(jid, []))
    ps = maintenance.start_state(plan, state(MIXER_BEARING), "operator-01", "test")
    live = state(MIXER_BEARING)
    for n in range(1, 3):                                            # 정지·정비 모드: 보냄 → 재관측 완료
        ps = maintenance.advance(proposal, live, ps, FACTS)
        assert ps["steps"][n - 1]["status"] == "sent"
        ps = maintenance.advance(proposal, live, ps, FACTS)
        assert ps["steps"][n - 1]["status"] == "sent"                 # 결과가 오기 전에는 다시 보내지 않는다
        events[f"job-{n}"] = [{"kind": "observed", "status": "OK", "reason": "ok", "detail": {}}]
        ps = maintenance.advance(proposal, live, ps, FACTS)
        assert ps["steps"][n - 1]["status"] == "done"
    ps = maintenance.advance(proposal, live, ps, FACTS)              # 베어링 현장 작업
    events["job-3"] = [{"kind": "field", "status": "DONE_NO_FAULT", "reason": "x",
                        "detail": {"finding": "베어링 정상", "effective": False}},
                       {"kind": "observed", "status": "NO_FAULT_FOUND", "reason": "x", "detail": {}}]
    ps = maintenance.advance(proposal, live, ps, FACTS)
    assert ps["phase"] == "cleanup" and ps["outcome"] == "cause_mismatch"   # LOTO 를 켰으니 정리 단계로
    assert ps["steps"][2]["finding"] == "베어링 정상"
    assert [s["wm"] for s in ps["steps"]] == ["WM-M101-STOP", "WM-PLC-MAINT-ON", "WM-FLD-BEARING-REPLACE", "WM-FLD-LOTO-RELEASE"]
    ps = maintenance.advance(proposal, live, ps, FACTS)                     # 정리 단계 보냄
    events["job-4"] = [{"kind": "field", "status": "DONE", "reason": "x", "detail": {"finding": "격리 해제"}},
                       {"kind": "observed", "status": "OK", "reason": "x", "detail": {}}]
    ps = maintenance.advance(proposal, live, ps, FACTS)
    ps = maintenance.advance(proposal, live, ps, FACTS)
    assert ps["phase"] == "done" and ps["outcome"] == "cause_mismatch"     # 재기동은 하지 않는다
    assert sent == ["WM-M101-STOP", "WM-PLC-MAINT-ON", "WM-FLD-BEARING-REPLACE", "WM-FLD-LOTO-RELEASE"]


def test_executor_verifies_recovery_hold_before_closing(monkeypatch):
    plan = plan_for("OPT-CW-SWITCH-ONLINE", "DEC-COOLING-RECOVERY", THERMAL_STRAINER)
    proposal = {"id": "p", "incident_id": "i", "plan": plan}
    ps = maintenance.start_state(plan, state(THERMAL_STRAINER), "operator-01", "test")
    ps.update(phase="verify", current=len(ps["steps"]),
              verify={"started_at": maintenance.now(), "within_since": None, "held_s": 0, "samples": [], "last": None})
    good = state({**THERMAL_STRAINER, "TT-101": 72.4, "FT-103": 30.0})
    ps = maintenance.advance(proposal, good, ps, FACTS)
    assert ps["phase"] == "verify" and ps["verify"]["within_since"]
    ps["verify"]["within_since"] -= 31
    ps = maintenance.advance(proposal, good, ps, FACTS)
    assert ps["phase"] == "done" and ps["outcome"] == "recovered"


def test_report_counts_downtime_from_plan_start_when_interlock_already_stopped_the_line(monkeypatch):
    plan = plan_for("OPT-PT-CALIBRATE", "DEC-PRESSURE-RESPONSE", PRESSURE_DRIFT, pump_run=False)
    plan["evaluation"] = {"decisions": []}
    tripped = state(PRESSURE_DRIFT, pump_run=False)
    tripped["interlock"] = True
    ps = maintenance.start_state(plan, tripped, "operator-01", "test")
    t0 = ps["started_at"]
    for s in ps["steps"]:
        s.update(status="done", started_at=t0, finished_at=t0 + 6)   # 재기동이 계획 시작 6 s 뒤 = 설비 1 h
    ps.update(phase="done", outcome="recovered", finished_at=t0 + 40, verify={"held_s": 30, "last": None})
    rep = maintenance.report({"id": "p", "incident_id": "i", "plan": plan}, ps, state(PRESSURE_DRIFT), FACTS)
    assert rep["kpi"]["actual"]["downtime_plant_h"] == 1.0
    assert rep["kpi"]["actual"]["production_loss"] == -85.0


def test_inspection_option_needs_two_open_candidates():
    narrowed = ranked("DEC-AGITATOR-REPAIR", MIXER_BEARING,
                      {"FM-MIXER-BEARING-WEAR": "supported", "FM-MIXER-SHAFT-MISALIGNMENT": "refuted", "FM-MIXER-CRITICAL-SPEED": "unknown"})
    assert not {o["option_id"]: o for o in narrowed["options"]}["OPT-AGITATOR-INSPECT-BOTH"]["eligible"]
    both = ranked("DEC-AGITATOR-REPAIR", MIXER_BEARING,
                  {"FM-MIXER-BEARING-WEAR": "supported", "FM-MIXER-SHAFT-MISALIGNMENT": "unknown"})
    assert {o["option_id"]: o for o in both["options"]}["OPT-AGITATOR-INSPECT-BOTH"]["eligible"]


def test_inspection_allowed_when_remaining_cause_is_unconfirmed():
    r = ranked("DEC-PRESSURE-RESPONSE", PRESSURE_DRIFT, {"FM-PT101-DRIFT": "refuted", "FM-OUTLET-RESTRICTION": "unknown"},
               interlock=True)
    by = {o["option_id"]: o for o in r["options"]}
    assert by["OPT-PRESSURE-INSPECT-BOTH"]["eligible"]          # 남은 후보가 확인 불가뿐 → 점검형
    assert not by["OPT-CV-REPAIR"]["eligible"]                  # 지지되지 않은 원인에 대한 원인 대응은 안 된다
    supported = ranked("DEC-PRESSURE-RESPONSE", PRESSURE_DRIFT, {"FM-PT101-DRIFT": "refuted", "FM-OUTLET-RESTRICTION": "supported"},
                       interlock=True)
    assert supported["recommended"] == "OPT-CV-REPAIR"
    assert not {o["option_id"]: o for o in supported["options"]}["OPT-PRESSURE-INSPECT-BOTH"]["eligible"]


def test_stopped_agitator_excludes_batch_wait_and_does_not_charge_scrap_twice():
    stopped = {**MIXER_BEARING, "IT-102": 0.02, "VT-101": 0.1}
    r = ranked("DEC-AGITATOR-REPAIR", stopped, {"FM-MIXER-SHAFT-MISALIGNMENT": "supported", "FM-MIXER-BEARING-WEAR": "refuted"},
               agitator_run=False)
    by = {o["option_id"]: o for o in r["options"]}
    assert by["OPT-ALIGN-AFTER-BATCH"]["excluded"]
    assert r["recommended"] == "OPT-ALIGN-NOW"
    assert all(i["value"] > -200 for i in by["OPT-ALIGN-NOW"]["impacts"] if i["kpi"] == "KPI-PRODUCTION-LOSS")


def test_report_does_not_charge_batch_scrap_when_agitator_was_already_stopped():
    stopped = {**MIXER_BEARING, "IT-102": 0.02, "VT-101": 0.1}
    plan = plan_for("OPT-ALIGN-NOW", "DEC-AGITATOR-REPAIR", stopped, agitator_run=False)
    plan["evaluation"] = {"decisions": []}
    ps = maintenance.start_state(plan, state(stopped, agitator_run=False), "operator-01", "test")
    t0 = ps["started_at"]
    for s in ps["steps"]:
        s.update(status="done", started_at=t0, finished_at=t0 + 3)
    ps.update(phase="done", outcome="recovered", finished_at=t0 + 40, verify={"held_s": 30, "last": None})
    rep = maintenance.report({"id": "p", "incident_id": "i", "plan": plan}, ps, state(MIXER_BEARING), FACTS)
    assert rep["kpi"]["actual"]["batch_scrapped"] is False
