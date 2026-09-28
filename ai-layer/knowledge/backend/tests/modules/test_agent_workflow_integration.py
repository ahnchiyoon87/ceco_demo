"""Actual Postgres checkpoint/review integration; investigation is explicitly substituted.

These tests do not establish model quality or a successful real model call.
"""
import asyncio
from uuid import uuid4

import pytest
from fastapi import HTTPException

from backend.tests.modules.test_actions_integration import case
from backend.src.modules.operations import agent, actions
from backend.src.modules.operations.api import connection


def make_run(uid):
    agent.initialize()
    with connection() as conn:
        return conn.execute("INSERT INTO manufacturing_analysis_runs(id,incident_id,status,model) VALUES (%s,%s,'running','substituted-test-investigator') RETURNING *", (uuid4(), uid)).fetchone()


@pytest.mark.parametrize("decision", ["approve", "reject"])
def test_durable_workflow_resumes_review_without_reinvestigating(case, monkeypatch, decision):
    uid, body, evidence, _ = case
    calls, writes = [], []
    async def investigate(state):
        calls.append(state["run_id"])
        proposal = actions.create_proposal(uid, body, evidence, origin=f"ai-run:{state['run_id']}:integration-test")
        return {"proposal_id": str(proposal["id"]), "proposal_summary": body.summary}
    monkeypatch.setattr(agent, "investigate", investigate)
    monkeypatch.setattr(actions, "stop_mixer", lambda _: writes.append(1) or {"status": "stop_verified"})
    run = make_run(uid)
    async def execute():
        await agent.drive(run["id"], uid)
        row = agent.list_runs(uid)["items"][0]
        assert row["status"] == "awaiting_review", row
        assert row["result"]["review"]["options"][0]["label"] == "approve"
        # Simulate process exit before saving the awaiting_review API status.
        with connection() as conn:
            conn.execute("UPDATE manufacturing_analysis_runs SET status='running' WHERE id=%s", (run["id"],))
        agent.mark_interrupted_runs()
        assert agent.list_runs(uid)["items"][0]["status"] == "interrupted"
        recovered = await agent.recover_run(run["id"])
        assert recovered["run"]["status"] == "awaiting_review"
        assert recovered["equipment_command_sent"] is False
        proposal = actions.list_proposals(uid)["items"][0]
        with pytest.raises(HTTPException) as blocked:
            actions.decide_http(proposal["id"], actions.Decision(decision=decision, note="Bypass must fail"))
        assert blocked.value.status_code == 409
        # drive constructs a new graph and a new saver connection each time.
        await agent.resume(run["id"], actions.Decision(decision=decision, note="Integration review"))
        await asyncio.gather(*tuple(agent._tasks))
        completed = agent.list_runs(uid)["items"][0]
        assert completed["status"] == "finished", completed
        assert len(calls) == 1
        assert len(writes) == (1 if decision == "approve" else 0)
        with pytest.raises(HTTPException):
            await agent.resume(run["id"], actions.Decision(decision=decision, note="Duplicate"))
    asyncio.run(execute())


def test_investigation_failure_is_saved_without_a_proposal(case, monkeypatch):
    async def fail(_):
        raise TimeoutError("Simulated provider timeout; not an actual model execution")
    monkeypatch.setattr(agent, "investigate", fail)
    run = make_run(case[0])
    asyncio.run(agent.drive(run["id"], case[0]))
    row = agent.list_runs(case[0])["items"][0]
    assert row["status"] == "failed"
    assert "TimeoutError" in row["error"]
    assert not actions.list_proposals(case[0])["items"]


def test_evidence_needed_ends_without_review_or_equipment(case, monkeypatch):
    outcome = {"status":"needs_evidence", "summary":"Applicable documents are missing.",
               "missing":["Mixer response procedure"], "next_steps":["Register and review the applicable document"],
               "citations":[], "equipment_command_sent":False}
    async def investigate(_):
        return {"result":outcome}
    monkeypatch.setattr(agent, "investigate", investigate)
    monkeypatch.setattr(agent, "review", lambda _: pytest.fail("Insufficient evidence entered approval"))
    monkeypatch.setattr(actions, "stop_mixer", lambda _: pytest.fail("Insufficient evidence sent equipment command"))
    run = make_run(case[0])
    asyncio.run(agent.drive(run["id"], case[0]))
    row = agent.list_runs(case[0])["items"][0]
    assert row["status"] == "needs_evidence"
    assert row["result"]["result"] == outcome
    assert row["result"]["proposal_id"] is None
    assert row["result"]["review"] is None
    assert not actions.list_proposals(case[0])["items"]
    with pytest.raises(HTTPException):
        asyncio.run(agent.resume(run["id"], actions.Decision(decision="approve", note="Must reject")))
    with connection() as conn:
        conn.execute("UPDATE manufacturing_analysis_runs SET status='interrupted' WHERE id=%s", (run["id"],))
    recovered = asyncio.run(agent.recover_run(run["id"]))
    assert recovered["run"]["status"] == "needs_evidence"
    assert recovered["run"]["result"]["result"] == outcome
    assert recovered["equipment_command_sent"] is False


def test_unconfigured_model_rejects_before_starting_job(case, monkeypatch):
    agent.initialize()
    monkeypatch.setattr(agent, "model_status", lambda: {"configured": False})
    with pytest.raises(HTTPException) as exc:
        asyncio.run(agent.analyze(case[0]))
    assert exc.value.status_code == 503
    assert not agent.list_runs(case[0])["items"]


@pytest.mark.parametrize("checkpoint", ["missing", "completed", "other_incident"])
def test_resume_without_matching_pending_checkpoint_never_restarts(case, monkeypatch, checkpoint):
    uid = case[0]
    async def investigate(state):
        if checkpoint == "other_incident":
            return {"incident_id": str(uuid4()), "proposal_id": str(uuid4()),
                    "proposal_summary": "Mismatched incident must not resume"}
        return {"result": {"status": "needs_evidence"}}
    monkeypatch.setattr(agent, "investigate", investigate)
    run = make_run(uid)
    async def exercise():
        if checkpoint != "missing":
            await agent.drive(run["id"], uid)
        async def forbidden(_):
            pytest.fail("Approval restarted investigation or executed a command")
        monkeypatch.setattr(agent, "investigate", forbidden)
        monkeypatch.setattr(agent, "execute", forbidden)
        with connection() as conn:
            conn.execute("UPDATE manufacturing_analysis_runs SET status='awaiting_review' WHERE id=%s", (run["id"],))
        await agent.resume(run["id"], actions.Decision(decision="approve", note="Stale database review state"))
        await asyncio.gather(*tuple(agent._tasks))
        row = agent.list_runs(uid)["items"][0]
        assert row["status"] == "failed", row
        assert row["error"]
        assert not actions.list_proposals(uid)["items"]
    asyncio.run(exercise())
