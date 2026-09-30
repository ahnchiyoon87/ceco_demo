"""Real PostgreSQL decisions; equipment adapter replaced except in live demo probe."""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime, timezone, timedelta
from uuid import uuid4
import os

import pytest
from fastapi import HTTPException

from backend.src.modules.operations import actions
from backend.src.modules.operations.api import Alarm, ingest, initialize, connection, get_incident


@pytest.fixture
def case(monkeypatch):
    assert os.environ.get('DB_NAME', '').startswith('ar100_pytest_'), 'Action integration requires isolated test database'
    initialize()
    actions.initialize()
    state = dict(status="available", site="AR-100", device="reactor-line-01", seq=123,
                 commands={"agitator_run": True}, interlock=False, readings={})
    monkeypatch.setattr(actions, "live_state", lambda: deepcopy(state))
    # Historical synthetic timestamp separated from actual current production of alarms.
    alarm = Alarm(ts=uuid4().int % 1000000000000 + 1, site="AR-100", device="reactor-line-01",
                  tag="VT-101", value=8, alert_type="verification_"+str(uuid4()),
                  severity="CRITICAL", detector="TEST", detail="Synthetic decision test")
    incident = ingest(alarm)["incident"]
    uid = incident["id"]
    evidence = {"incident_id": str(uid), "revision": 1,
                "graph": {"status": "available", "assets": [{"name": "M-101"}],
                          "documents": [{"document_id": "AR100-MIXER-RESPONSE"}]},
                "history": {"status": "available", "rows": [{"tag": "VT-101", "value": 8}]}}
    evidence["current_history"] = {"status": "available", "truncated": False, "rows": [
        {"tag": tag, "value": {"IT-102":10.1,"VT-101":8,"LT-102":54}[tag], "quality": "GOOD", "time": datetime.now(timezone.utc).isoformat()}
        for tag in ("IT-102", "VT-101", "LT-102")]}
    evidence["graph"]["sensors"] = [
        {"tag":"IT-102","unit":"A","usl":9.6,"source_sha256":"test-source"},
        {"tag":"VT-101","unit":"mm/s","usl":7.1,"source_sha256":"test-source"}]
    monkeypatch.setattr(actions, "incident_evidence", lambda _: deepcopy(evidence))
    body = actions.Proposal(expected_revision=1, summary="Synthetic proposal used only for integration verification",
                            action="stop_mixer", citations=["AR100-MIXER-RESPONSE"], uncertainties=["Not a live diagnosis"])
    yield uid, body, evidence, state
    with connection() as conn:
        if conn.execute("SELECT to_regclass('manufacturing_analysis_runs') AS name").fetchone()["name"]:
            conn.execute("DELETE FROM manufacturing_analysis_runs WHERE incident_id=%s", (uid,))
        conn.execute("DELETE FROM manufacturing_proposals WHERE incident_id=%s", (uid,))
        conn.execute("DELETE FROM manufacturing_events WHERE incident_id=%s", (uid,))
        conn.execute("DELETE FROM manufacturing_alarm_links WHERE incident_id=%s", (uid,))
        conn.execute("DELETE FROM manufacturing_incidents WHERE id=%s", (uid,))


def propose(case):
    uid, body, evidence, _ = case
    return actions.create_proposal(uid, body, evidence, origin="integration-test")


def test_concurrent_approval_writes_once_and_does_not_close_case(case, monkeypatch):
    p = propose(case)
    calls = []
    monkeypatch.setattr(actions, "stop_mixer", lambda state: calls.append(state) or {"status": "stop_verified"})
    decision = actions.Decision(decision="approve", note="Integration approval")
    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(lambda _: actions.decide(p["id"], decision), range(4)))
    assert len(calls) == 1
    assert sum(not result["replayed"] for result in results) == 1
    assert get_incident(str(case[0]))["incident"]["status"] == "awaiting_maintenance"
    with pytest.raises(HTTPException) as exc:
        actions.decide(p["id"], actions.Decision(decision="reject", note="Conflicting review"))
    assert exc.value.status_code == 409


def test_rejection_never_touches_equipment(case, monkeypatch):
    p = propose(case)
    monkeypatch.setattr(actions, "stop_mixer", lambda _: pytest.fail("Rejected proposal sent a command"))
    result = actions.decide(p["id"], actions.Decision(decision="reject", note="Need another inspection"))
    assert result["proposal"]["status"] == "rejected"
    assert get_incident(str(case[0]))["incident"]["status"] == "unresolved"


@pytest.mark.parametrize("change", ["revision", "expired", "state", "setpoint", "unavailable"])
def test_stale_or_unavailable_preconditions_block_action(case, monkeypatch, change):
    p = propose(case)
    monkeypatch.setattr(actions, "stop_mixer", lambda _: pytest.fail("Invalid approval sent a command"))
    with connection() as conn:
        if change == "revision":
            conn.execute("UPDATE manufacturing_incidents SET revision=2,review_revision=2 WHERE id=%s", (case[0],))
        elif change == "expired":
            conn.execute("UPDATE manufacturing_proposals SET expires_at=now()-interval '1 second' WHERE id=%s", (p["id"],))
    if change == "state":
        case[3]["commands"]["agitator_run"] = False
    if change == "setpoint":
        case[3]["commands"]["pump_speed_sp"] = 61.2
    if change == "unavailable":
        case[3]["status"] = "unavailable"
    with pytest.raises(HTTPException) as exc:
        actions.decide(p["id"], actions.Decision(decision="approve", note="Invalid test approval"))
    assert exc.value.status_code in {409, 503}
    assert actions.list_proposals(case[0])["items"][0]["status"] == "pending"


def test_inspection_records_changed_context_without_sending_command(case, monkeypatch):
    case[1].action = "inspect_only"
    p = propose(case)
    case[3]["commands"]["pump_speed_sp"] = 61.2
    monkeypatch.setattr(actions, "stop_mixer", lambda _: pytest.fail("Inspection sent a command"))
    result = actions.decide(p["id"], actions.Decision(decision="approve", note="Record inspection with latest context"))
    assert result["proposal"]["status"] == "awaiting_maintenance"
    actual = result["proposal"]["result"]
    assert actual["status"] == "inspection_requested"
    assert actual["plant_context_changed"] is True
    assert actual["current_plant_state"]["commands"]["pump_speed_sp"] == 61.2


@pytest.mark.parametrize("changed", [False, True])
def test_repeated_observations_preserve_review_but_changed_severity_blocks_it(case, monkeypatch, changed):
    p = propose(case)
    original = get_incident(str(case[0]))["incident"]
    payload = {**original["alarm"], "ts": original["alarm"]["ts"] + 1_000_000_000,
               "value": original["alarm"]["value"] + .2}
    if changed:
        payload["severity"] = "WARNING"
    received = ingest(Alarm(**payload))["incident"]
    assert received["id"] == case[0]
    assert received["revision"] == 2 and received["alarm_count"] == 2
    assert received["review_revision"] == (2 if changed else 1)
    calls = []
    monkeypatch.setattr(actions, "stop_mixer", lambda state: calls.append(state) or {"status":"stop_verified"})
    decision = actions.Decision(decision="approve", note="Review version integration check")
    if changed:
        with pytest.raises(HTTPException) as error:
            actions.decide(p["id"], decision)
        assert error.value.status_code == 409
        assert not calls
    else:
        assert actions.decide(p["id"], decision)["proposal"]["status"] == "awaiting_maintenance"
        assert len(calls) == 1
    events = get_incident(str(case[0]))["events"]
    assert sum(e["kind"] in {"alarm_received", "alarm_correlated"} for e in events) == 2


def test_lost_acknowledgement_is_unresolved_and_not_retried(case, monkeypatch):
    p = propose(case)
    calls = []
    monkeypatch.setattr(actions, "stop_mixer", lambda _: calls.append(1) or {"status": "uncertain", "reason": "Injected lost acknowledgement"})
    decision = actions.Decision(decision="approve", note="Test uncertain outcome")
    assert actions.decide(p["id"], decision)["proposal"]["status"] == "unresolved"
    assert actions.decide(p["id"], decision)["replayed"]
    assert len(calls) == 1


def test_process_crash_after_durable_claim_is_recoverable_without_resending(case, monkeypatch):
    p = propose(case)
    def crash(_):
        raise SystemExit("Simulated process exit during IO")
    monkeypatch.setattr(actions, "stop_mixer", crash)
    decision = actions.Decision(decision="approve", note="Crash test")
    with pytest.raises(SystemExit):
        actions.decide(p["id"], decision)
    assert actions.list_proposals(case[0])["items"][0]["status"] == "executing"
    assert actions.decide(p["id"], decision)["replayed"]
    with connection() as conn:
        conn.execute("UPDATE manufacturing_proposals SET started_at=now()-interval '1 minute' WHERE id=%s", (p["id"],))
    assert actions.recover(p["id"])["proposal"]["result"]["status"] == "uncertain"


def test_nonexistent_citation_cannot_authorize_action(case):
    case[1].citations = ["invented-document"]
    with pytest.raises(HTTPException) as exc:
        propose(case)
    assert exc.value.status_code == 422


@pytest.mark.parametrize("defect", ["healthy", "only_one_signal", "at_limit", "missing_limit", "wrong_unit", "missing_source"])
def test_stop_proposal_requires_current_paired_anomaly_and_reviewed_limits(case, defect):
    evidence = case[2]
    if defect == "healthy":
        for row in evidence["current_history"]["rows"]:
            if row["tag"] in {"IT-102", "VT-101"}:row["value"] = 2
    elif defect == "only_one_signal":
        evidence["current_history"]["rows"][0]["value"] = 6.4
    elif defect == "at_limit":
        evidence["current_history"]["rows"][0]["value"] = 9.6
    elif defect == "missing_limit":
        evidence["graph"]["sensors"][0]["usl"] = None
    elif defect == "wrong_unit":
        evidence["graph"]["sensors"][0]["unit"] = "unknown"
    else:
        evidence["graph"]["sensors"][0]["source_sha256"] = None
    with pytest.raises(HTTPException) as error:
        propose(case)
    assert error.value.status_code == 409
    assert not actions.list_proposals(case[0])["items"]


@pytest.mark.parametrize("defect", ["stale", "missing", "bad_quality", "nonfinite", "changed_document", "current_recovered"])
def test_current_evidence_change_blocks_approved_action(case, monkeypatch, defect):
    p = propose(case)
    monkeypatch.setattr(actions, "stop_mixer", lambda _: pytest.fail("Invalid current evidence sent a command"))
    evidence = case[2]
    if defect == "stale":
        evidence["current_history"]["rows"][0]["time"] = (datetime.now(timezone.utc)-timedelta(minutes=1)).isoformat()
    elif defect == "missing":
        evidence["current_history"]["rows"] = []
    elif defect == "bad_quality":
        evidence["current_history"]["rows"][0]["quality"] = "INTERPOLATED"
    elif defect == "nonfinite":
        evidence["current_history"]["rows"][0]["value"] = float("nan")
    elif defect == "current_recovered":
        evidence["current_history"]["rows"][0]["value"] = 6.4
    else:
        evidence["graph"]["documents"][0]["content"] = "Changed after review"
    with pytest.raises(HTTPException) as exc:
        actions.decide(p["id"], actions.Decision(decision="approve", note="Current evidence rejection test"))
    assert exc.value.status_code == 409
    assert actions.list_proposals(case[0])["items"][0]["status"] == "pending"
