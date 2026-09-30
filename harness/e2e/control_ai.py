"""[측정 도구 — 솔루션 부품 아님] 새 베이스 제어·안전 회귀(AI 쪽, LLM 호출 없음). knowledge 컨테이너 안에서 실행:
  docker exec -i rot-base-knowledge-1 python - <step> < harness/e2e/control_ai.py
단계(step): propose | reject | approve2 | stale | count <proposal_id> | pg_down_decide <proposal_id>
전제: 교반기 이상(bearing_wear)이 걸려 있고 그 사건이 AI 사건 표에 있다(control_ai.sh 가 주입·대기).
V1 regression_control.py 와 같은 실제 함수(create_proposal·decide)를 부른다. 새 구조에서 AI 는 설비에 연결이 없고
승인하면 공용 업무 DB workflow 에 작업 요청을 남긴다. 쓰기 횟수 = 그 대응안의 workflow.request 건수.
  S17 반려 → 작업 요청 0건
  S18 대응안 뒤 운전 명령이 바뀜(운전원 길, control_ai.sh 가 FUXA 대역으로 바꿈) → 승인 409, 작업 요청 0건
  S21 같은 승인 두 번(동시) → 작업 요청 정확히 1건
  S22 업무 DB(PostgreSQL) 다운 중 승인 → 실패로 끝나고(작업 요청 없음) 복구 뒤에도 요청이 생기지 않음
결과는 stdout 마지막 줄 JSON.
"""
import json, sys, threading, time
from uuid import UUID

from fastapi import HTTPException
from backend.src.modules.operations.actions import Proposal, Decision, create_proposal, decide
from backend.src.modules.operations.api import connection
from backend.src.modules.operations.evidence import incident_evidence
from backend.src.modules.operations.plant_db import plant_connection

step = sys.argv[1] if len(sys.argv) > 1 else "propose"


def mixer_incident():
    with connection() as conn:
        return conn.execute("""SELECT * FROM manufacturing_incidents WHERE correlation_key LIKE '%%mixer-current-vibration%%'
            AND status IN ('received','awaiting_review','unresolved') ORDER BY last_ts DESC LIMIT 1""").fetchone()


def propose():
    inc = mixer_incident()
    if inc is None:
        raise SystemExit(json.dumps({"error": "교반기 사건 없음"}))
    ev = incident_evidence(str(inc["id"]))
    p = create_proposal(inc["id"], Proposal(
        expected_revision=ev["revision"], summary="회귀 시험용 대응안(측정 도구). AI 진단이 아니다 — 승인·재검사·요청 경로만 확인한다.",
        action="stop_mixer", citations=["AR100-MIXER-RESPONSE"], uncertainties=["회귀 시험: 원인 판정 아님"]), ev, origin="regression-test")
    return p


def requests_for(pid):
    with plant_connection() as pc:
        return pc.execute("SELECT count(*) AS n FROM workflow.request WHERE proposal_id = %s", (str(pid),)).fetchone()["n"]


def try_decide(pid, decision, note):
    try:
        r = decide(UUID(str(pid)), Decision(decision=decision, note=note))
        return {"status": r["proposal"]["status"], "result": (r["proposal"].get("result") or {}).get("status"), "replayed": r["replayed"]}
    except HTTPException as e:
        return {"http": e.status_code, "detail": str(e.detail)[:160]}
    except Exception as e:
        return {"error": f"{type(e).__name__}: {str(e)[:160]}"}


out = {"step": step}
if step == "propose":
    p = propose(); out["proposal_id"] = str(p["id"])
elif step == "reject":
    p = propose()
    r = try_decide(p["id"], "reject", "회귀 S17 반려")
    out |= {"proposal_id": str(p["id"]), "decision": r, "requests": requests_for(p["id"]),
            "pass": r.get("status") == "rejected" and requests_for(p["id"]) == 0}
elif step == "approve2":
    p = propose()
    res = []
    ths = [threading.Thread(target=lambda: res.append(try_decide(p["id"], "approve", "회귀 S21 같은 승인 2회"))) for _ in range(2)]
    [t.start() for t in ths]; [t.join() for t in ths]
    n = requests_for(p["id"])
    # 실제로 나간 한 건: 게이트웨이 수용 뒤 수신 응답(ⓑ)이 5 s 안에 기록됐는가(승인 대기 동안 업무 서비스가 멈추지 않는가)
    with plant_connection() as pc:
        ev = pc.execute("""SELECT e.kind, e.status, extract(epoch FROM e.at)::float8 AS at FROM workflow.request r
                           JOIN workflow.request_event e USING (job_order_id) WHERE r.proposal_id = %s ORDER BY e.id""", (str(p["id"]),)).fetchall()
    acc = next((e["at"] for e in ev if e["kind"] == "gateway_accepted"), None)
    rec = next((e["at"] for e in ev if e["kind"] == "receipt"), None)
    lag = round(rec - acc, 2) if acc and rec else None
    out |= {"proposal_id": str(p["id"]), "decisions": res, "requests": n, "events": [f'{e["kind"]}:{e["status"]}' for e in ev],
            "receipt_after_gateway_s": lag, "pass": n == 1 and lag is not None and lag <= 5}
elif step == "stale":          # 대응안을 만든 뒤 control_ai.sh 가 운전 명령을 바꾸고 decide 단계를 부른다
    pid = sys.argv[2]
    r = try_decide(pid, "approve", "회귀 S18 명령 변경 뒤 승인")
    n = requests_for(pid)
    out |= {"proposal_id": pid, "decision": r, "requests": n, "pass": r.get("http") == 409 and n == 0}
elif step == "count":
    out |= {"proposal_id": sys.argv[2], "requests": requests_for(sys.argv[2])}
print(json.dumps(out, ensure_ascii=False, default=str))
