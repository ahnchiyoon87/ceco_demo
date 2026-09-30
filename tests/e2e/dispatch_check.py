"""[측정 도구] 발송 경로 확인 — 승인(기록 + request.approved) 뒤 dispatched → gateway_* 사건이 붙는지, 같은 승인을 다시 알려도 다시 보내지 않는지.
    base_client python tests/e2e/dispatch_check.py --out /repo/experiments/<EXP>/raw/dispatch_<이름>.json
사례: 수용(WM-R101-TEMPSP 70 ℃) · 게이트웨이 거부(범위 밖 95 ℃ → PARAMETER_RANGE) · 승인 재알림(사건 수 그대로) · MES 지시(수용·잘못된 작업 422) · 기록 없는 ID 알림(무시).
"""
import argparse, json, os, sys, time, urllib.error, uuid

import psycopg
from confluent_kafka import Producer
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); a = ap.parse_args()
pg = lambda: psycopg.connect(f"host=postgres dbname=plant user=ai_app password={os.environ['PG_AI_PASSWORD']} connect_timeout=5",
                             row_factory=dict_row, autocommit=True)
prod = Producer({"bootstrap.servers": "kafka:9092", "acks": "all"})


def announce(jid):
    prod.produce("request.approved", key=jid, value=json.dumps({"job_order_id": jid})); prod.flush(6)


def approve(value):
    jid = f"disp-{uuid.uuid4().hex}"
    with pg() as c:
        c.execute("""INSERT INTO workflow.request(job_order_id, work_master_id, equipment_id, job_order_parameters, requester, approver, context)
                     VALUES (%s,'WM-R101-TEMPSP','R-101',%s,'ai-ops','operator-01',%s)""",
                  (jid, Jsonb([{"id": "temp_sp_c", "value": value}]), Jsonb({"summary": "발송 경로 확인"})))
        c.execute("INSERT INTO workflow.request_event(job_order_id, kind, status, detail, source) VALUES (%s,'approved','APPROVED','{}','dispatch-check')", (jid,))
    t0 = time.time(); announce(jid)
    return jid, t0


def events(jid):
    with pg() as c:
        return c.execute("SELECT kind, status, reason, detail, extract(epoch FROM at)::float8 AS at FROM workflow.request_event WHERE job_order_id=%s ORDER BY id", (jid,)).fetchall()


def wait(jid, kind_prefix, timeout=15):
    end = time.time() + timeout
    while time.time() < end:
        ev = events(jid)
        if any(e["kind"].startswith(kind_prefix) for e in ev):
            return ev
        time.sleep(0.2)
    return events(jid)


res = []
def case(name, ok, detail):
    res.append({"case": name, "pass": bool(ok), "detail": detail}); print("PASS" if ok else "FAIL", name, json.dumps(detail, ensure_ascii=False, default=str), flush=True)

jid, t0 = approve(70.0)
ev = wait(jid, "gateway_")
g = next((e for e in ev if e["kind"].startswith("gateway_")), None)
case("수용: approved → dispatched → gateway_accepted", [e["kind"] for e in ev][:3] == ["approved", "dispatched", "gateway_accepted"] and g["detail"].get("expires_at"),
     {"kinds": [e["kind"] for e in ev], "detail": g and g["detail"], "approved_to_gateway_s": g and round(g["at"] - t0, 3)})
n_before = len(events(jid)); announce(jid); time.sleep(3)
case("같은 승인 재알림 → 다시 보내지 않음", len([e for e in events(jid) if e["kind"] == "dispatched"]) == 1, {"events_before": n_before, "events_after": len(events(jid))})
jid2, _ = approve(95.0)
ev2 = wait(jid2, "gateway_")
case("게이트웨이 거부 기록(PARAMETER_RANGE, 422)", any(e["kind"] == "gateway_rejected" and e["reason"] == "PARAMETER_RANGE" and e["detail"].get("http_status") == 422 for e in ev2),
     {"kinds": [f'{e["kind"]}:{e["status"]}:{e["reason"]}' for e in ev2]})
# MES 흉내 요청자: 생산 지시 → 기록·승인(mes-01, 종류 mes, 승인자 planner-01) → 같은 발송 길
import urllib.request
t0 = time.time()
r = urllib.request.urlopen(urllib.request.Request("http://it-collector:4195/mes_requester/orders", method="POST",
        data=json.dumps({"work_master_id": "WM-R101-TEMPSP", "equipment_id": "R-101", "job_order_parameters": [{"id": "temp_sp_c", "value": 70.0}],
                         "planner": "planner-01", "summary": "배치 시험 온도 지시"}).encode(), headers={"Content-Type": "application/json"}), timeout=10)
mjid = json.load(r)["job_order_id"]; mcode = r.status
ev3 = wait(mjid, "gateway_")
with pg() as c:
    mrow = c.execute("SELECT requester, requester_type, approver FROM workflow.request WHERE job_order_id=%s", (mjid,)).fetchone()
case("MES 지시: 202 → 요청(mes-01·mes·planner-01) → gateway_accepted", mcode == 202 and mrow == {"requester": "mes-01", "requester_type": "mes", "approver": "planner-01"}
     and any(e["kind"] == "gateway_accepted" for e in ev3), {"http": mcode, "row": mrow, "kinds": [e["kind"] for e in ev3]})
try:
    urllib.request.urlopen(urllib.request.Request("http://it-collector:4195/mes_requester/orders", method="POST",
        data=json.dumps({"work_master_id": "WM-NOPE", "equipment_id": "R-101", "planner": "planner-01"}).encode()), timeout=10); bad = 200
except urllib.error.HTTPError as e:
    bad = e.code
case("MES 지시: 등록부에 없는 작업 → 422(기록 안 함)", bad == 422, {"http": bad})
ghost = f"disp-ghost-{uuid.uuid4().hex}"; announce(ghost); time.sleep(3)
case("기록 없는 ID 알림 → 무시", events(ghost) == [], {"events": len(events(ghost))})
with pg() as c:
    au = c.execute("SELECT action, subject FROM audit.log WHERE job_order_id=%s AND actor_id='it-dispatcher' ORDER BY id", (jid,)).fetchall()
case("감사 기록(dispatched, gateway_accepted)", [r["action"] for r in au] == ["dispatched", "gateway_accepted"], {"audit": au})
json.dump({"results": res, "pass": all(r["pass"] for r in res)}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
print(json.dumps({"pass": all(r["pass"] for r in res), "n": len(res)}))
sys.exit(0 if all(r["pass"] for r in res) else 1)
