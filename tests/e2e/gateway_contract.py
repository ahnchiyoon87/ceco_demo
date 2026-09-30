"""[측정 도구] DMZ 게이트웨이 계약 시험 — 구현(자체 코드·Node-RED)과 상관없이 같은 요청에 같은 답을 내는지.
    base_client python tests/e2e/gateway_contract.py --phase normal  --out /repo/experiments/<EXP>/raw/gw_<이름>_normal.json
    base_client python tests/e2e/gateway_contract.py --phase broker_down --out …   (DMZ 브로커를 멈춘 상태에서)
정상 단계: 인증·형식·허용 목록·범위·나이·중복을 거부 이유로 확인하고, 수용된 요청이 DMZ 요청 토픽에 MQTT 5 만료(30 s)와
본문 expires_at 을 달고 나가는지 DMZ 브로커에서 받아 본다(viewer 계정). 브로커 정지 단계: 즉시(2 s 안) BROKER_UNAVAILABLE.
"""
import argparse, json, os, sys, threading, time, urllib.error, urllib.request, uuid

import paho.mqtt.client as mqtt
from paho.mqtt.packettypes import PacketTypes

REG = json.load(open("shared/registry/generated/tags.json", encoding="utf-8"))
ap = argparse.ArgumentParser()
ap.add_argument("--phase", choices=["normal", "broker_down"], required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--url", default="http://dmz-gateway:8088/requests")
a = ap.parse_args()
TOKEN = os.environ["GATEWAY_CLIENT_TOKEN"]


def body(**kw):
    b = {"job_order_id": f"gwc-{uuid.uuid4().hex}", "work_master_id": "WM-R101-TEMPSP", "equipment_id": "R-101",
         "job_order_parameters": [{"id": "temp_sp_c", "value": 70.0}], "requester": "ai-ops", "approver": "operator-01",
         "created_at": time.time()}
    b.update(kw)
    return b


def send(payload, token=TOKEN, raw=None):
    data = raw if raw is not None else json.dumps(payload).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    t0 = time.time()
    try:
        with urllib.request.urlopen(urllib.request.Request(a.url, data=data, headers=headers, method="POST"), timeout=8) as r:
            code, out = r.status, json.loads(r.read() or b"{}")
    except urllib.error.HTTPError as e:
        code, out = e.code, json.loads(e.read() or b"{}")
    return {"code": code, "reason": out.get("reason") or out.get("status"), "expires_at": out.get("expires_at"),
            "s": round(time.time() - t0, 3)}


results = []


def case(name, want_code, want_reason, got):
    ok = got["code"] == want_code and got["reason"] == want_reason
    results.append({"case": name, "want": [want_code, want_reason], "got": got, "pass": ok})
    print(("PASS" if ok else "FAIL"), name, got, flush=True)


if a.phase == "normal":
    seen = {}
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"gwc-{uuid.uuid4().hex[:6]}", protocol=mqtt.MQTTv5)
    c.username_pw_set(os.environ["MQTT_USER"], os.environ["MQTT_PASS"])

    def on_msg(cl, u, m):
        try:
            p = json.loads(m.payload)
        except ValueError:
            return
        exp = getattr(m.properties, "MessageExpiryInterval", None) if m.properties else None
        seen[p.get("job_order_id")] = {"expires_at": p.get("expires_at"), "mqtt_expiry": exp}

    c.on_message = on_msg
    c.on_connect = lambda cl, u, f, rc, p=None: cl.subscribe(REG["request"]["in_topic"], 1)
    c.connect("dmz-broker", 1883)
    c.loop_start()
    time.sleep(1.5)
    case("토큰 없음", 401, "UNAUTHORIZED", send(body(), token=None))
    case("JSON 아님", 400, "SCHEMA_INVALID", send(None, raw=b"not json"))
    b = body(); b.pop("approver")
    case("스키마(승인자 없음)", 422, "SCHEMA_INVALID", send(b))
    case("허용 목록 밖 작업(스키마의 작업 ID 목록에서 걸림)", 422, "SCHEMA_INVALID", send(body(work_master_id="WM-P101-START", equipment_id="P-101")))
    case("설비 불일치", 422, "EQUIPMENT_MISMATCH", send(body(equipment_id="M-101")))
    case("파라미터 없음", 422, "PARAMETER_MISSING", send(body(job_order_parameters=[])))
    case("파라미터 범위 밖", 422, "PARAMETER_RANGE", send(body(job_order_parameters=[{"id": "temp_sp_c", "value": 95.0}])))
    case("요청자 허용 밖", 422, "REQUESTER_NOT_ALLOWED", send(body(requester="unknown")))
    case("승인자 허용 밖", 422, "APPROVER_NOT_ALLOWED", send(body(approver="nobody")))
    case("오래된 요청", 422, "TOO_OLD", send(body(created_at=time.time() - 60)))
    ok = body()
    got = send(ok)
    case("수용", 202, "ACCEPTED", got)
    t = time.time() + 5
    while time.time() < t and ok["job_order_id"] not in seen:
        time.sleep(0.1)
    m = seen.get(ok["job_order_id"], {})
    exp_ok = m.get("mqtt_expiry") is not None and 25 <= m["mqtt_expiry"] <= 30 and m.get("expires_at") == got.get("expires_at")
    results.append({"case": "DMZ 토픽: MQTT 5 만료·본문 만료", "want": ["mqtt_expiry≈30", "expires_at 같음"], "got": m, "pass": exp_ok})
    print(("PASS" if exp_ok else "FAIL"), "DMZ 토픽 만료", m, flush=True)
    case("중복", 409, "DUPLICATE", send(ok))
    c.loop_stop()
else:
    got = send(body())
    case("브로커 정지 → 즉시 거부", 503, "BROKER_UNAVAILABLE", got)
    results[-1]["pass"] = results[-1]["pass"] and got["s"] <= 2.0
json.dump({"phase": a.phase, "url": a.url, "results": results, "pass": all(r["pass"] for r in results)},
          open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({"pass": all(r["pass"] for r in results), "n": len(results)}))
sys.exit(0 if all(r["pass"] for r in results) else 1)
