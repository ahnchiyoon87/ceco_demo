"""Review-bound simulator actions; never accept arbitrary addresses or commands."""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from contextvars import ContextVar
from datetime import datetime, timezone
from typing import Literal
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from psycopg.types.json import Jsonb

from .api import connection
from .evidence import live_state, incident_evidence

router = APIRouter(prefix="/api/operations", tags=["manufacturing-actions"])
_progress_sink = ContextVar("action_progress_sink", default=None)


class ActionProgressError(RuntimeError):
    """Audit persistence failed; distinct from an equipment transport failure."""


def action_progress(kind, payload):
    sink = _progress_sink.get()
    if sink is not None:
        try:
            sink(kind, payload)
        except Exception as exc:
            raise ActionProgressError(kind) from exc


class Proposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    expected_revision: int = Field(gt=0)
    summary: str = Field(min_length=10, max_length=10000)
    action: Literal["stop_mixer", "enable_cooling", "inspect_only"] = Field(
        description='Required explicit action code. Include this field even when summary names the action. '
                    'inspect_only records an inspection request; stop_mixer requests reviewed simulator stopping; '
                    'enable_cooling enables the supported cooler at the reviewed current temperature target.')
    citations: list[str] = Field(min_length=1, max_length=30)
    uncertainties: list[str] = Field(min_length=1, max_length=30)


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    decision: Literal["approve", "reject"]
    note: str = Field(min_length=1, max_length=2000)


def initialize():
    with connection() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS manufacturing_proposals (
            id uuid PRIMARY KEY, incident_id uuid NOT NULL REFERENCES manufacturing_incidents(id),
            status text NOT NULL, incident_revision integer NOT NULL, body jsonb NOT NULL,
            evidence jsonb NOT NULL, state_fingerprint text NOT NULL, origin text NOT NULL,
            decision jsonb, result jsonb, created_at timestamptz NOT NULL DEFAULT now(),
            expires_at timestamptz NOT NULL DEFAULT now()+interval '5 minutes',
            started_at timestamptz, completed_at timestamptz
        )""")


def fingerprint(state):
    # Readings change every second. Bind approval to commands/interlock and exact device,
    # while the incident revision binds it to the alarm/evidence snapshot.
    value = {key: state[key] for key in ("site", "device", "commands", "interlock")}
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def require_plant(state):
    if state.get("status") != "available":
        raise HTTPException(503, "공정 상태를 확인할 수 없습니다. 조치하지 않았습니다.")
    if (state.get("site"), state.get("device")) != ("AR-100", "reactor-line-01"):
        raise HTTPException(409, "허용된 교육용 시뮬레이터와 일치하지 않습니다.")


def event(conn, incident_id, kind, payload):
    conn.execute("INSERT INTO manufacturing_events(incident_id,kind,payload) VALUES (%s,%s,%s)",
                 (incident_id, kind, Jsonb(payload)))


def knowledge_fingerprint(evidence):
    graph = evidence.get("graph", {})
    if graph.get("status") != "available":
        raise HTTPException(503, "현재 적용 문서와 설비 관계를 확인할 수 없습니다.")
    # Compare content as well as declared source hashes: edits through another
    # graph client may not refresh the source_sha256 property.
    basis = {key: sorted(graph.get(key, []), key=lambda item: json.dumps(item, sort_keys=True))
             for key in ("assets", "documents", "sensors")}
    return hashlib.sha256(json.dumps(basis, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def require_current_observations(evidence, tags=("IT-102", "VT-101", "LT-102")):
    current = evidence.get("current_history", {})
    if current.get("status") != "available" or current.get("truncated"):
        raise HTTPException(409, "현재 관측을 충분히 확인하지 못했습니다. 설비 조치를 진행하지 않습니다.")
    now = datetime.now(timezone.utc).timestamp()
    for tag in tags:
        rows = [row for row in current.get("rows", []) if row.get("tag") == tag]
        try:
            recent = [(datetime.fromisoformat(row["time"].replace("Z", "+00:00")).timestamp(), row) for row in rows]
        except (KeyError, ValueError, TypeError) as exc:
            raise HTTPException(409, "관측 시각을 해석할 수 없습니다.") from exc
        if not recent or not (-2 <= now-max(ts for ts, _ in recent) <= 10):
            raise HTTPException(409, f"{tag}의 최신 관측이 없거나 오래되었습니다. 재조회가 필요합니다.")
        if any(row.get("quality") != "GOOD" for ts,row in recent if now-ts <= 10):
            raise HTTPException(409, f"{tag}의 최근 관측 품질을 확인해야 합니다.")
        if any(not isinstance(row.get("value"), (int,float)) or not math.isfinite(row["value"]) for ts,row in recent if now-ts <= 10):
            raise HTTPException(409, f"{tag}의 유효한 측정값이 없습니다.")


def require_current_mixer_anomaly(evidence):
    """Educational stop scope: both mixer signals still exceed reviewed project limits."""
    require_current_observations(evidence)
    for tag, unit in (("IT-102", "A"), ("VT-101", "mm/s")):
        sensors = [s for s in evidence.get("graph", {}).get("sensors", []) if s.get("tag") == tag]
        if len(sensors) != 1:
            raise HTTPException(409, f"{tag}의 적용 기준을 하나로 확인할 수 없습니다.")
        sensor = sensors[0]
        limit = sensor.get("usl")
        if (sensor.get("unit") != unit or not sensor.get("source_sha256")
                or type(limit) not in (int, float) or not math.isfinite(limit)):
            raise HTTPException(409, f"{tag}의 단위·상한·출처를 확인해야 합니다.")
        rows = [r for r in evidence["current_history"]["rows"] if r.get("tag") == tag]
        latest = max(rows, key=lambda r: datetime.fromisoformat(r["time"].replace("Z", "+00:00")))
        if latest["value"] <= limit:
            raise HTTPException(409, f"{tag}의 최신 값이 정지 제안용 프로젝트 상한을 초과하지 않습니다. 점검 또는 근거 보완으로 재검토하세요.")


def require_current_thermal_anomaly(evidence, state):
    require_current_observations(evidence, ("TT-101",))
    graph = evidence.get("graph", {})
    if not any(asset.get("name") == "R-101" for asset in graph.get("assets", [])):
        raise HTTPException(409, "반응기와 온도 센서의 관계를 확인해야 합니다.")
    sensors = [sensor for sensor in graph.get("sensors", []) if sensor.get("tag") == "TT-101"]
    if len(sensors) != 1:
        raise HTTPException(409, "반응기 온도의 적용 기준을 하나로 확인하지 못했습니다.")
    sensor = sensors[0]
    low, high = sensor.get("lsl"), sensor.get("usl")
    numeric = lambda value: type(value) in (int, float) and math.isfinite(value)
    if (sensor.get("unit") != "degC" or not sensor.get("source_sha256")
            or not numeric(low) or not numeric(high) or low >= high):
        raise HTTPException(409, "온도 단위·상하한·출처를 확인해야 합니다.")
    commands = state.get("commands", {})
    target, temperature = commands.get("temp_sp_c"), state.get("readings", {}).get("TT-101")
    if commands.get("cooler_enable") is not False or state.get("interlock") is not False:
        raise HTTPException(409, "냉각기 지원·정지 상태와 인터록을 확인해야 합니다.")
    if not numeric(target) or not low <= target < high:
        raise HTTPException(409, "현재 목표 온도가 출처로 확인한 적용 범위 안에 있어야 합니다.")
    rows = [row for row in evidence["current_history"]["rows"] if row.get("tag") == "TT-101"]
    latest = max(rows, key=lambda row: datetime.fromisoformat(row["time"].replace("Z", "+00:00")))
    if not numeric(temperature) or temperature <= high or latest["value"] <= high:
        raise HTTPException(409, "최신 이력과 현재 반응기 온도에서 상한 초과가 함께 확인되어야 합니다.")


def create_proposal(incident_id: UUID, body: Proposal, evidence: dict, *, origin: str):
    """Called by a grounded agent after tool retrieval, not exposed as an unaudited POST."""
    state = live_state()
    require_plant(state)
    if str(evidence.get("incident_id")) != str(incident_id) or evidence.get("revision") != body.expected_revision:
        raise HTTPException(409, "대응안과 근거의 사건 또는 버전이 다릅니다.")
    graph = evidence.get("graph", {})
    docs = {d["document_id"] for d in graph.get("documents", [])}
    if graph.get("status") != "available" or not set(body.citations) <= docs:
        raise HTTPException(422, "실제 조회된 적용 문서만 인용할 수 있습니다.")
    if body.action == "stop_mixer":
        require_current_mixer_anomaly(evidence)
        if not any(a["name"] == "M-101" for a in graph.get("assets", [])):
            raise HTTPException(422, "이 사건의 교반기 관계가 확인되지 않았습니다.")
        if evidence.get("history", {}).get("status") != "available":
            raise HTTPException(422, "센서 이력 없이 설비 조치를 제안할 수 없습니다.")
        if "AR100-MIXER-RESPONSE" not in body.citations:
            raise HTTPException(422, "교반기 대응 절차가 필요합니다.")
    if body.action == "enable_cooling":
        require_current_thermal_anomaly(evidence, state)
        if evidence.get("history", {}).get("status") != "available" or "AR100-THERMAL-RESPONSE" not in body.citations:
            raise HTTPException(422, "온도 이력과 적용 온도 대응 절차가 필요합니다.")
    with connection() as conn:
        row = conn.execute("SELECT * FROM manufacturing_incidents WHERE id=%s FOR UPDATE", (incident_id,)).fetchone()
        if not row:
            raise HTTPException(404, "사건이 없습니다.")
        if origin.startswith("ai-run:"):
            existing = conn.execute("SELECT * FROM manufacturing_proposals WHERE incident_id=%s AND origin=%s", (incident_id, origin)).fetchone()
            if existing:
                return existing
        if row["review_revision"] != body.expected_revision or row["status"] not in {"received", "awaiting_review", "unresolved"}:
            raise HTTPException(409, "사건이 변경되었습니다. 근거를 다시 조회하세요.")
        if (row["site"], row["device"]) != (state["site"], state["device"]):
            raise HTTPException(409, "사건과 조치 대상이 다릅니다.")
        conn.execute("UPDATE manufacturing_proposals SET status='superseded' WHERE incident_id=%s AND status='pending'", (incident_id,))
        proposal = conn.execute("""INSERT INTO manufacturing_proposals
            (id,incident_id,status,incident_revision,body,evidence,state_fingerprint,origin)
            VALUES (%s,%s,'pending',%s,%s,%s,%s,%s) RETURNING *""",
            (uuid4(), incident_id, row["review_revision"], Jsonb(body.model_dump()), Jsonb(evidence), fingerprint(state), origin)).fetchone()
        conn.execute("UPDATE manufacturing_incidents SET status='awaiting_review' WHERE id=%s", (incident_id,))
        event(conn, incident_id, "proposal_created", {"proposal_id": str(proposal["id"]), "origin": origin})
    return proposal


@router.get("/incidents/{incident_id}/proposals")
def list_proposals(incident_id: UUID):
    with connection() as conn:
        return {"items": conn.execute("SELECT * FROM manufacturing_proposals WHERE incident_id=%s ORDER BY created_at DESC", (incident_id,)).fetchall()}


# ── 조치 실행 = 작업 요청(HANDOFF §2-1 외부 시스템 연결 ④~⑥) ──────────────────────────────
# V1 은 이 자리에서 가상설비 Modbus 코일에 직접 쓰고 HTTP /state 로 다시 읽었다. 새 구조에서 AI(외부 시스템)는
# 명령하지 않고 "작업 요청"만 남긴다: 공용 DB workflow 에 요청·승인을 추가(정본) → IT 발송기가 DMZ 게이트웨이로 보냄(ⓐ)
# → OT 수신기가 받을지 정함(ⓑ) → PLC 가 물리적으로 되는지 검사(ⓒ) → 업무 서비스가 새 상태를 재관측.
# 이 함수는 그 결과 사건을 기다려 읽기만 한다. 설비에 닿는 연결은 없다.
WORK_MASTERS = {"stop_mixer": ("WM-M101-STOP", "M-101", "stop_verified", "교반기 정지"),
                "enable_cooling": ("WM-HX102-ENABLE", "HX-102", "cooling_command_verified", "냉각기 기동")}
WAIT_S = 20


def stop_mixer(before, *, proposal=None, note=""):
    return _request_action(before, "stop_mixer", proposal, note)


def enable_cooling(before, *, proposal=None, note=""):
    """Adapter only; caller must enforce grounded approval and current conditions."""
    if type(before.get("commands", {}).get("cooler_enable")) is not bool:
        return {"status": "not_executed", "reason": "현재 가상 설비의 냉각 기능을 확인하지 못했습니다."}
    return _request_action(before, "enable_cooling", proposal, note)


def _request_action(before, action, proposal, note):
    """승인된 조치를 작업 요청 한 건으로 남기고 결과 사건을 기다린다. 요청은 다시 보내지 않는다."""
    from .plant_db import audit, plant_connection, request_event
    wm, equipment, verified_status, label = WORK_MASTERS[action]
    jid = f"ai-{uuid4().hex}"
    approver = os.environ.get("AI_APPROVER_ID", "operator-01")
    context = {"summary": f"{label} — 사건 {proposal['incident_id']}" if proposal else label,
               "proposal_id": str(proposal["id"]) if proposal else None}
    try:
        with plant_connection() as pc:
            pc.execute("""INSERT INTO workflow.request(job_order_id, work_master_id, equipment_id, job_order_parameters,
                          requester, approver, context, incident_id, proposal_id) VALUES (%s,%s,%s,'[]',%s,%s,%s,%s,%s)""",
                       (jid, wm, equipment, "ai-ops", approver, Jsonb(context),
                        proposal["incident_id"] if proposal else None, proposal["id"] if proposal else None))
            request_event(pc, jid, "approved", "APPROVED", note or None, {"action": action, "before_seq": before.get("seq")}, "ai-app")
            audit(pc, "ai", "ai-ops", "propose", jid, wm, {"action": action})
            audit(pc, "human", approver, "approve", jid, wm, {"note": note})
    except Exception as exc:
        return {"status": "not_executed", "reason": "작업 요청을 공용 업무 DB 에 기록하지 못해 보내지 않았습니다(기록 실패).",
                "error_type": type(exc).__name__}
    action_progress("request_recorded", {"job_order_id": jid, "work_master_id": wm,
                                         "reason": "작업 요청을 기록했습니다. IT 발송기가 DMZ 게이트웨이로 보냅니다."})
    seen, deadline = set(), time.monotonic() + WAIT_S
    stages = {"gateway_accepted": "action_gateway_accepted", "gateway_rejected": "action_gateway_rejected",
              "receipt": "action_ot_receipt", "operator": "action_operator", "plc": "action_plc_ack",
              "ack_timeout": "action_ack_timeout", "observed": "action_observed", "command_disagree": "action_command_disagree"}
    while time.monotonic() < deadline:
        with plant_connection() as pc:
            events = pc.execute("SELECT id, kind, status, reason, at FROM workflow.request_event WHERE job_order_id=%s ORDER BY id",
                                (jid,)).fetchall()
        for e in events:
            if e["id"] in seen:
                continue
            seen.add(e["id"])
            if e["kind"] in stages:
                action_progress(stages[e["kind"]], {"job_order_id": jid, "status": e["status"], "reason": e["reason"]})
            k, st, why = e["kind"], e["status"], e["reason"]
            if k == "gateway_rejected" or (k in ("receipt", "operator", "plc") and st in ("REJECTED", "OPERATOR_REJECTED")):
                return {"status": "not_executed", "job_order_id": jid, "stage": k, "reason": f"{k} 거부: {why}"}
            if k == "receipt" and st == "OPERATOR_WAIT":
                return {"status": "awaiting_operator", "job_order_id": jid,
                        "reason": "공장 안 운전원 확인 대기(REMOTE_MANUAL). FUXA '받은 요청'에서 수락·거부합니다. 결과는 요청 사건으로 이어집니다."}
            if k == "observed":
                return {"status": verified_status, "job_order_id": jid,
                        "reason": f"PLC 가 수용했고 새 상태에서 {label}을 확인했습니다. 원인 제거·정비 완료를 뜻하지 않습니다."}
            if k in ("command_disagree", "expired_unconfirmed", "unconfirmed"):
                return {"status": "uncertain", "job_order_id": jid, "reason": f"{why} 명령을 다시 보내지 않았습니다. 설비 상태를 확인하세요."}
        time.sleep(0.25)
    return {"status": "uncertain", "job_order_id": jid, "reason": "결과 확인 시간(20초)이 지났습니다. 요청은 다시 보내지 않았습니다. 요청 사건에서 결과를 확인하세요."}


def decide(proposal_id: UUID, body: Decision):
    # Lock order is always incident then proposal, matching creation and intake.
    with connection() as conn:
        target = conn.execute("SELECT incident_id FROM manufacturing_proposals WHERE id=%s", (proposal_id,)).fetchone()
        if not target:
            raise HTTPException(404, "대응안이 없습니다.")
        incident = conn.execute("SELECT * FROM manufacturing_incidents WHERE id=%s FOR UPDATE", (target["incident_id"],)).fetchone()
        proposal = conn.execute("SELECT * FROM manufacturing_proposals WHERE id=%s FOR UPDATE", (proposal_id,)).fetchone()
        if proposal["decision"]:
            if proposal["decision"] != body.model_dump():
                raise HTTPException(409, "이미 다른 검토 결과가 저장되어 있습니다.")
            return {"proposal": proposal, "replayed": True}
        if proposal["status"] != "pending":
            raise HTTPException(409, "현재 검토할 수 없는 대응안입니다.")
        if body.decision == "reject":
            proposal = conn.execute("UPDATE manufacturing_proposals SET status='rejected',decision=%s,completed_at=now() WHERE id=%s RETURNING *", (Jsonb(body.model_dump()), proposal_id)).fetchone()
            conn.execute("UPDATE manufacturing_incidents SET status='unresolved',revision=revision+1,review_revision=review_revision+1 WHERE id=%s", (incident["id"],))
            event(conn, incident["id"], "proposal_rejected", {"proposal_id": str(proposal_id), "note": body.note})
            return {"proposal": proposal, "replayed": False}
        if proposal["expires_at"] <= datetime.now(timezone.utc) or proposal["incident_revision"] != incident["review_revision"]:
            raise HTTPException(409, "대응안이 만료되었거나 사건이 변경되었습니다. 재분석이 필요합니다.")
        before = live_state()
        require_plant(before)
        if proposal["body"]["action"] != "inspect_only" and fingerprint(before) != proposal["state_fingerprint"]:
            raise HTTPException(409, "운전 명령 또는 인터록 상태가 변경되었습니다. 재분석이 필요합니다.")
        fresh_evidence = incident_evidence(str(incident["id"]))
        if knowledge_fingerprint(fresh_evidence) != knowledge_fingerprint(proposal["evidence"]):
            raise HTTPException(409, "적용 문서 또는 설비 관계가 변경되었습니다. 재분석이 필요합니다.")
        if proposal["body"]["action"] == "stop_mixer":
            require_current_mixer_anomaly(fresh_evidence)
        elif proposal["body"]["action"] == "enable_cooling":
            require_current_thermal_anomaly(fresh_evidence, before)
        conn.execute("UPDATE manufacturing_proposals SET status='executing',decision=%s,started_at=now() WHERE id=%s", (Jsonb(body.model_dump()), proposal_id))
        conn.execute("UPDATE manufacturing_incidents SET status='executing' WHERE id=%s", (incident["id"],))
        event(conn, incident["id"], "action_authorized", {"proposal_id": str(proposal_id), "note": body.note, "before": before,
              "current_observations": fresh_evidence.get("current_history"), "knowledge_sha256": knowledge_fingerprint(fresh_evidence)})
    # The durable claim precedes IO. A crash from here leaves an uncertain action;
    # another approval request returns the claim and MUST NOT send a second command.
    with connection() as conn:
        # Serialize the short IO interval with incident changes. The earlier claim
        # is already durable if this transaction or the process dies during IO.
        # Still excludes competing incident updates, but permits the FK key-share
        # lock needed by independently committed progress events during IO.
        current = conn.execute("SELECT * FROM manufacturing_incidents WHERE id=%s FOR NO KEY UPDATE", (incident["id"],)).fetchone()
        current_proposal = conn.execute("SELECT * FROM manufacturing_proposals WHERE id=%s FOR UPDATE", (proposal_id,)).fetchone()
        if current_proposal["status"] != "executing":
            return {"proposal": current_proposal, "replayed": True}
        current_state = live_state()
        if (current["review_revision"] != proposal["incident_revision"] or current_state.get("status") != "available"
                or (current_state.get("site"), current_state.get("device")) != (before["site"], before["device"])
                or (proposal["body"]["action"] != "inspect_only" and fingerprint(current_state) != proposal["state_fingerprint"])):
            result = {"status": "not_executed", "reason": "실행 직전 사건 또는 공정 상태가 변경되었습니다."}
        elif proposal["body"]["action"] == "inspect_only":
            result = {"status": "inspection_requested", "reason": "현장 점검 요청을 기록했습니다. 설비 명령은 전송하지 않았습니다.",
                      "plant_context_changed": fingerprint(current_state) != proposal["state_fingerprint"],
                      "current_plant_state": current_state,
                      "context_note": "점검 요청은 설비 제어 승인이 아닙니다. 현재 운전 상태를 함께 기록하며 과거 대응안의 상태가 그대로 유지된다고 간주하지 않습니다."}
        else:
            def save_progress(kind, payload):
                with connection() as progress_conn:
                    progress_conn.execute("SET LOCAL lock_timeout = '2s'")
                    progress_conn.execute("SET LOCAL statement_timeout = '3s'")
                    event(progress_conn, incident["id"], kind, {"proposal_id": str(proposal_id), **payload})
            token = _progress_sink.set(save_progress)
            try:
                if proposal["body"]["action"] == "enable_cooling":
                    try:
                        require_current_thermal_anomaly(fresh_evidence, current_state)
                    except HTTPException as exc:
                        result = {"status": "not_executed", "reason": exc.detail}
                    else:
                        result = enable_cooling(current_state, proposal=proposal, note=body.note)
                else:
                    result = stop_mixer(current_state, proposal=proposal, note=body.note)
            finally:
                _progress_sink.reset(token)
        final = "awaiting_maintenance" if result["status"] in {"stop_verified", "inspection_requested"} else "unresolved"
        if result["status"] == "cooling_command_verified":
            from .thermal_observation import start
            result["thermal_observation"] = start(current_state,time.time())
            result["thermal_observation"]["review_revision"] = current["review_revision"] + 1
            final = "observing"
        proposal = conn.execute("UPDATE manufacturing_proposals SET status=%s,result=%s,completed_at=CASE WHEN %s THEN NULL ELSE now() END WHERE id=%s RETURNING *", (final, Jsonb(result), final=="observing", proposal_id)).fetchone()
        conn.execute("UPDATE manufacturing_incidents SET status=%s,revision=revision+1,review_revision=review_revision+1 WHERE id=%s", (final, incident["id"]))
        event(conn, incident["id"], "action_result", {"proposal_id": str(proposal_id), **result})
    return {"proposal": proposal, "replayed": False}


@router.post("/proposals/{proposal_id}/decision")
def decide_http(proposal_id: UUID, body: Decision):
    with connection() as conn:
        row = conn.execute("SELECT origin FROM manufacturing_proposals WHERE id=%s", (proposal_id,)).fetchone()
    if row and row["origin"].startswith("ai-run:"):
        raise HTTPException(409, "AI 대응안은 해당 분석 실행의 검토 경로로 승인해야 합니다.")
    return decide(proposal_id, body)


@router.post("/proposals/{proposal_id}/recover")
def recover(proposal_id: UUID):
    """Record an interrupted execution as unresolved; never replay the equipment command."""
    with connection() as conn:
        target = conn.execute("SELECT incident_id FROM manufacturing_proposals WHERE id=%s", (proposal_id,)).fetchone()
        if not target:
            raise HTTPException(404, "대응안이 없습니다.")
        conn.execute("SELECT id FROM manufacturing_incidents WHERE id=%s FOR UPDATE", (target["incident_id"],))
        row = conn.execute("""UPDATE manufacturing_proposals SET status='unresolved',completed_at=now(),
            result='{"status":"uncertain","reason":"실행 중단 후 수동 확인 필요. 명령 재전송 없음"}'::jsonb
            WHERE id=%s AND status='executing' AND started_at < now()-interval '30 seconds' RETURNING *""", (proposal_id,)).fetchone()
        if not row:
            raise HTTPException(409, "중단된 실행의 복구 조건에 해당하지 않습니다.")
        conn.execute("UPDATE manufacturing_incidents SET status='unresolved',revision=revision+1,review_revision=review_revision+1 WHERE id=%s", (row["incident_id"],))
        event(conn, row["incident_id"], "execution_recovered", {"proposal_id": str(proposal_id), "result": row["result"]})
    return {"proposal": row}
