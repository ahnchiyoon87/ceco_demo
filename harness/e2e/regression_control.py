"""[측정 도구 — 솔루션 부품 아님] 회귀 S14~S21·S24 (제어·안전, LLM 호출 없음). AI 백엔드(knowledge) 컨테이너 안에서 실행:
  docker exec -i -e REG_OUT=/tmp/reg.json rot-ai-knowledge-1 python - < harness/e2e/regression_control.py
전제: 교반기 이상(bearing_wear)이 걸려 있고 그 사건이 업무 DB 에 있다(regression.sh 가 주입·대기). 실제 함수(create_proposal·decide)와
운전원 제어 API(/simulation/control)를 그대로 부른다. 쓰기 횟수는 사건 이벤트(action_dispatch_started)와 설비 /state 로 센다.
끝나면 설비 명령을 시작 전 값으로 되돌린다(하니스 복구, verify_live_action.py 와 같은 방식).
판정 기준은 scenarios/catalog.yaml(결과 보기 전 고정). 결과는 stdout 마지막 줄 JSON.
"""
import json, os, threading, time, urllib.error, urllib.request, uuid
from uuid import UUID

from pymodbus.client import ModbusTcpClient
from fastapi import HTTPException
from backend.src.modules.operations import actions
from backend.src.modules.operations.actions import Proposal, Decision, create_proposal, decide
from backend.src.modules.operations.api import connection
from backend.src.modules.operations.evidence import incident_evidence, live_state

API = "http://localhost:8000/api/operations"
HOST = os.environ.get("SIMULATOR_MODBUS_HOST", "host.docker.internal")
PORT = int(os.environ.get("SIMULATOR_MODBUS_PORT", "27002"))
R = {}


def http(method, path, body=None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read() or b"{}")


def coil(addr, value):
    with ModbusTcpClient(HOST, port=PORT, timeout=3, retries=0) as c:
        rsp = c.write_coil(addr, value, slave=1)
        return not rsp.isError()


def wait_state(pred, timeout=8.0):
    end = time.time() + timeout
    s = live_state()
    while time.time() < end:
        s = live_state()
        if s.get("status") == "available" and pred(s):
            return s, True
        time.sleep(.5)
    return s, False


def dispatches(incident_id, proposal_id):
    with connection() as conn:
        return conn.execute("SELECT count(*) AS n FROM manufacturing_events WHERE incident_id=%s AND kind='action_dispatch_started' "
                            "AND payload->>'proposal_id'=%s", (incident_id, str(proposal_id))).fetchone()["n"]


def mixer_incident():
    with connection() as conn:
        return conn.execute("""SELECT * FROM manufacturing_incidents WHERE correlation_key LIKE '%%mixer-current-vibration%%'
            AND status IN ('received','awaiting_review','unresolved') ORDER BY last_ts DESC LIMIT 1""").fetchone()


def propose(incident, action="stop_mixer"):
    ev = incident_evidence(str(incident["id"]))
    return create_proposal(incident["id"], Proposal(
        expected_revision=ev["revision"], summary="회귀 시험용 대응안(측정 도구). AI 진단이 아니다 — 승인·재검사·쓰기 경로만 확인한다.",
        action=action, citations=["AR100-MIXER-RESPONSE"], uncertainties=["회귀 시험: 원인 판정 아님"]), ev, origin="regression-test")


def attempt(name, fn):
    try:
        R[name] = fn()
    except Exception as e:                      # 시험 자체가 깨지면 그 사실을 결과로 남긴다(통과로 세지 않음)
        R[name] = {"pass": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}


start = live_state()
R["start_commands"] = start.get("commands")


def s15():
    b = live_state()
    code, body = http("POST", "/simulation/control", {"request_id": str(uuid.uuid4()), "target": "temp_sp_c", "value": 150})
    a = live_state()
    return {"pass": code >= 400 and a["commands"] == b["commands"], "http": code, "detail": str(body)[:200]}


def s24():
    b = live_state()
    ok = coil(10, True)
    time.sleep(2)
    a = live_state()
    same = all(a.get(k) == b.get(k) for k in ("interlock", "active_faults")) and \
        {k: v for k, v in a["commands"].items() if k != "alarm_ack"} == {k: v for k, v in b["commands"].items() if k != "alarm_ack"}
    return {"pass": ok and same, "write_ok": ok}


def s14():
    b = live_state()
    target = not b["commands"]["agitator_run"]
    ok = coil(1, target)
    s, seen = wait_state(lambda s: s["commands"]["agitator_run"] is target and s["seq"] > b["seq"])
    ok2 = coil(1, b["commands"]["agitator_run"])      # 원래대로
    s2, back = wait_state(lambda s: s["commands"]["agitator_run"] is b["commands"]["agitator_run"])
    return {"pass": ok and seen and ok2 and back, "reflected": seen, "restored": back}


def s17():
    inc = mixer_incident()
    p = propose(inc)
    b = live_state()
    res = decide(p["id"], Decision(decision="reject", note="회귀 S17 반려"))
    a = live_state()
    return {"pass": res["proposal"]["status"] == "rejected" and a["commands"] == b["commands"] and dispatches(inc["id"], p["id"]) == 0,
            "status": res["proposal"]["status"]}


def s18():
    inc = mixer_incident()
    p = propose(inc)
    b = live_state()
    heater = b["commands"]["heater_enable"]
    code, body = http("POST", "/simulation/control", {"request_id": str(uuid.uuid4()), "target": "heater_enable", "value": 0 if heater else 1})
    try:
        decide(p["id"], Decision(decision="approve", note="회귀 S18 명령 변경 뒤 승인"))
        refused, detail = False, "승인이 실행됨"
    except HTTPException as e:
        refused, detail = e.status_code == 409, e.detail
    agit = live_state()["commands"]["agitator_run"]
    http("POST", "/simulation/control", {"request_id": str(uuid.uuid4()), "target": "heater_enable", "value": 1 if heater else 0})
    return {"pass": code == 200 and refused and agit == b["commands"]["agitator_run"] and dispatches(inc["id"], p["id"]) == 0,
            "c2_http": code, "refused_409": refused, "detail": str(detail)[:200]}


def s19():
    inc = mixer_incident()
    p = propose(inc)
    b = live_state()
    old = os.environ.get("SIMULATOR_MODBUS_PORT")
    os.environ["SIMULATOR_MODBUS_PORT"] = "1"         # 연결 거부(하니스 주입: 쓰기 경로 통신 실패)
    try:
        res = decide(p["id"], Decision(decision="approve", note="회귀 S19 쓰기 실패"))
    finally:
        os.environ["SIMULATOR_MODBUS_PORT"] = old
    st = res["proposal"]["result"]["status"]
    return {"pass": st in ("not_executed", "uncertain") and live_state()["commands"] == b["commands"], "status": st}


def s20():
    inc = mixer_incident()
    p = propose(inc)
    b = live_state()
    real = actions.live_state
    actions.live_state = lambda: b                    # 하니스 주입: 쓰기 응답은 정상인데 상태가 바뀌지 않은 것으로 보임(ack_no_change)
    try:
        res = decide(p["id"], Decision(decision="approve", note="회귀 S20 응답만 있고 변화 없음"))
    finally:
        actions.live_state = real
    st = res["proposal"]["result"]["status"]
    coil(1, b["commands"]["agitator_run"])            # 실제 쓰기가 일어났으므로 원래대로
    wait_state(lambda s: s["commands"]["agitator_run"] is b["commands"]["agitator_run"])
    return {"pass": st == "uncertain", "status": st}


def s21():
    inc = mixer_incident()
    p = propose(inc)
    b = live_state()
    out = []
    ths = [threading.Thread(target=lambda: out.append(_decide(p["id"]))) for _ in range(2)]
    [t.start() for t in ths]; [t.join() for t in ths]
    n = dispatches(inc["id"], p["id"])
    statuses = sorted(str(o) for o in out)
    coil(1, b["commands"]["agitator_run"])
    wait_state(lambda s: s["commands"]["agitator_run"] is b["commands"]["agitator_run"])
    # C2 같은 request_id 2회
    rid = str(uuid.uuid4()); cur = live_state()["commands"]["valve_open_sp"]
    c1 = http("POST", "/simulation/control", {"request_id": rid, "target": "valve_open_sp", "value": 50 if cur != 50 else 55})
    c2 = http("POST", "/simulation/control", {"request_id": rid, "target": "valve_open_sp", "value": 50 if cur != 50 else 55})
    http("POST", "/simulation/control", {"request_id": str(uuid.uuid4()), "target": "valve_open_sp", "value": cur})
    with connection() as conn:                        # G6 감사 추적: 이 대응안의 기록 순서
        kinds = [r["kind"] for r in conn.execute("SELECT kind FROM manufacturing_events WHERE incident_id=%s AND "
                 "(payload->>'proposal_id'=%s) ORDER BY id", (inc["id"], str(p["id"]))).fetchall()]
        op = conn.execute("SELECT count(*) AS n FROM manufacturing_operator_commands WHERE id=%s", (rid,)).fetchone()["n"]
    need = ["proposal_created", "action_authorized", "action_dispatch_started", "action_result"]
    g6 = all(k in kinds for k in need) and op == 1
    return {"pass": n == 1 and c1[0] == 200 and c2[0] == 200 and c1[1] == c2[1], "dispatches": n, "results": statuses,
            "G6_audit": {"pass": g6, "proposal_events": kinds, "c2_receipts_for_request": op}}


def s16():
    sim = os.environ.get("SIMULATOR_API_URL", "http://host.docker.internal:27080")
    b = live_state()
    req = urllib.request.Request(sim + "/fault", data=json.dumps({"scenario": "spike", "duration_s": 25}).encode(),
                                 headers={"Content-Type": "application/json"}, method="POST")
    urllib.request.urlopen(req, timeout=10).read()
    s, locked = wait_state(lambda s: s.get("interlock") is True, timeout=15)
    c2 = http("POST", "/simulation/control", {"request_id": str(uuid.uuid4()), "target": "pump_run", "value": 1})
    ok = coil(0, True)                                 # C1: 운전 화면이 쓰는 것과 같은 Modbus 코일로 펌프 기동
    time.sleep(3)
    during = live_state()
    flow = during.get("readings", {}).get("FT-101")
    blocked_c1 = during.get("interlock") is True and isinstance(flow, (int, float)) and flow < 0.5
    urllib.request.urlopen(urllib.request.Request(sim + "/fault/clear", data=b"{}", headers={"Content-Type": "application/json"}, method="POST"), timeout=10)
    wait_state(lambda s: s.get("interlock") is False, timeout=30)
    coil(0, b["commands"]["pump_run"])
    return {"pass": locked and c2[0] == 409 and blocked_c1, "interlock_seen": locked, "c2_http": c2[0], "c1_write_ok": ok,
            "c1_flow_during_interlock": flow, "c3": "펌프 기동 조치 없음(Proposal.action = stop_mixer·enable_cooling·inspect_only)"}


def _decide(pid):
    try:
        r = decide(pid, Decision(decision="approve", note="회귀 S21 같은 승인 2회"))
        return {"replayed": r["replayed"], "status": (r["proposal"].get("result") or {}).get("status")}
    except HTTPException as e:
        return {"http": e.status_code}


for name, fn in (("S15", s15), ("S24", s24), ("S14", s14), ("S17", s17), ("S18", s18), ("S19", s19), ("S20", s20), ("S21", s21), ("S16", s16)):
    attempt(name, fn)
    time.sleep(1)

# 복구: 시작 명령으로(교반기·히터·밸브) — 하니스 복구
end = live_state()
for addr, key in ((1, "agitator_run"), (2, "heater_enable"), (0, "pump_run")):
    if end["commands"].get(key) != start["commands"].get(key):
        coil(addr, start["commands"][key])
R["end_commands"] = live_state().get("commands")
R["restored"] = all(R["end_commands"].get(k) == start["commands"].get(k) for k in ("agitator_run", "heater_enable", "pump_run"))
print(json.dumps(R, ensure_ascii=False, default=str))
