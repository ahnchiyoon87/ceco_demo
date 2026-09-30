"""[측정 도구] 새 베이스 격리 실습(HANDOFF §2-1 ⑩). isolation_base.sh 가 라우터에서 OT→DMZ 1883 을 끊고 잇는다.
  base_client python harness/e2e/isolation_base.py during --out … --cut-s 60   (끊긴 직후 실행)
  base_client python harness/e2e/isolation_base.py after --out …                (다시 이은 직후 실행)
during: 끊긴 동안 요청 두 건을 넣는다 — ⓐ 정상 요청(업무 DB → 발송기 → 게이트웨이, MQTT 만료 30 s + 본문 만료 30 s)
        ⓑ MQTT 만료를 뺀 요청(DMZ 브로커에 게이트웨이 계정으로 직접, 본문 만료 20 s) — 만료 두 겹을 따로 보려고.
        그리고 OT 안이 계속 도는지 본다: FUXA 현재 값 갱신, FUXA DAQ 증가, 운전원 명령 ACK, 스파이크 → 인터록·펌프 차단.
after : 다시 이은 뒤 ⓐ 는 전달되지 않고(MQTT 만료) ⓑ 는 수신기가 EXPIRED 로 거부하는지, 끊긴 동안 쌓인 값이 DMZ 로 올라오는지.
"""
import argparse, base64, json, os, sys, threading, time, urllib.parse, urllib.request, uuid

sys.path.insert(0, "/repo/harness/e2e")
import paho.mqtt.client as mqtt

ap = argparse.ArgumentParser(); ap.add_argument("phase", choices=["during", "after"]); ap.add_argument("--out", required=True)
ap.add_argument("--cut-s", type=float, default=60)
a = ap.parse_args()
REG = json.load(open("registry/generated/tags.json", encoding="utf-8"))
RESP, REQ_IN = REG["request"]["response_prefix"], REG["request"]["in_topic"]
ACK_OP = REG["plc"]["ack_operator_topic"]
STATE_FILE = "/repo/experiments/.isolation_state.json"
AUTH = {"Authorization": "Basic " + base64.b64encode(f'{os.environ["SIM_USER"]}:{os.environ["SIM_PASSWORD"]}'.encode()).decode()}


def http(url, body=None, headers=None):
    r = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None,
                               {"Content-Type": "application/json", **(headers or {})}, method="POST" if body is not None else "GET")
    return json.load(urllib.request.urlopen(r, timeout=10))


lock, msgs, status = threading.Lock(), [], {}


def on_msg(c, u, m):
    try:
        b = json.loads(m.payload)
    except ValueError:
        return
    p = m.topic.split("/")
    if len(p) == 6 and p[4] == "status":
        status[(p[3], p[5])] = b.get("value")
    with lock:
        msgs.append((time.time(), m.topic, b))


view = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"iso-{uuid.uuid4().hex[:6]}")
view.username_pw_set("viewer", os.environ["MQTT_PASS"])
view.on_connect = lambda c, u, f, rc, p=None: [c.subscribe(t, 1) for t in (f"{RESP}/#", ACK_OP, "AR-100/reaction/+/+/status/+")]
view.on_message = on_msg
view.connect("ot-hub", 1883); view.loop_start()


def fuxa_now(tag="TT_101"):
    q = json.dumps({"sids": [tag], "from": 1, "to": 1})
    return json.load(urllib.request.urlopen("http://fuxa:1881/api/daq?" + urllib.parse.urlencode({"query": q}), timeout=5))[0][0]


def fuxa_daq_count(t_from, t_to, tag="TT_101"):
    q = json.dumps({"sids": [tag], "from": t_from, "to": t_to})
    return len(json.load(urllib.request.urlopen("http://fuxa:1881/api/daq?" + urllib.parse.urlencode({"query": q}), timeout=10))[0])


def iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{int(time.time() * 1000) % 1000:03d}Z"


if a.phase == "during":
    import psycopg
    from psycopg.types.json import Jsonb
    from paho.mqtt.packettypes import PacketTypes
    from paho.mqtt.properties import Properties
    time.sleep(2)
    t_cut = time.time()
    out = {"cut_at": t_cut}
    # ⓐ 정상 요청: AI 와 같은 계정·방식으로 workflow 에 요청+승인
    jid_a = f"iso-a-{uuid.uuid4().hex}"
    with psycopg.connect(f"host=postgres dbname=plant user=ai_app password={os.environ['PG_AI_PASSWORD']}", autocommit=True) as c:
        c.execute("""INSERT INTO workflow.request(job_order_id, work_master_id, equipment_id, job_order_parameters, requester, approver, context)
                     VALUES (%s,'WM-M101-STOP','M-101','[]','ai-ops','operator-01',%s)""", (jid_a, Jsonb({"summary": "격리 실습 ⓐ"})))
        c.execute("INSERT INTO workflow.request_event(job_order_id, kind, status, reason, detail, source) VALUES (%s,'approved','APPROVED','격리 실습','{}','isolation-test')", (jid_a,))
    # ⓑ MQTT 만료 없이 DMZ 브로커에 직접(본문 만료 20 s)
    jid_b = f"iso-b-{uuid.uuid4().hex}"
    dmz = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"iso-dmz-{uuid.uuid4().hex[:6]}", protocol=mqtt.MQTTv5)
    dmz.username_pw_set("gateway", os.environ["MQTT_GATEWAY_PASSWORD"]); dmz.connect("dmz-broker", 1883); dmz.loop_start(); time.sleep(1)
    now = time.time()
    body = {"job_order_id": jid_b, "work_master_id": "WM-M101-STOP", "equipment_id": "M-101", "job_order_parameters": [],
            "requester": "ai-ops", "approver": "operator-01", "created_at": now, "expires_at": int(now) + 20,
            "context": {"summary": "격리 실습 ⓑ(MQTT 만료 없음)"}}
    dmz.publish(REQ_IN, json.dumps(body), qos=1).wait_for_publish(5)   # 속성 없음 = MQTT 만료 없음
    out |= {"job_a": jid_a, "job_b": jid_b, "job_b_expires_at": body["expires_at"]}
    # OT 안이 계속 도는가
    v0 = fuxa_now(); time.sleep(3); v1 = fuxa_now()
    out["fuxa_value_updates"] = v1["ts"] > v0["ts"]
    t0 = time.time()
    topic = next(c["operator_topic"] for c in REG["commands"] if c["asset"] == "CV-101")
    cur = http("http://plant-sim:8080/state", headers=AUTH)["commands"]["valve_open_sp"]
    fux = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2); fux.username_pw_set("fuxa", os.environ["MQTT_FUXA_PASSWORD"])
    fux.connect("ot-hub", 1883); fux.loop_start(); time.sleep(1)
    fux.publish(topic, json.dumps({"command": "open_sp", "value": int(cur), "ts": iso()}), qos=1)
    ack = None
    while time.time() - t0 < 6 and ack is None:
        with lock:
            ack = next((b.get("result") for t, tp, b in msgs if t >= t0 and tp == ACK_OP), None)
        time.sleep(0.1)
    out["operator_ack"] = ack
    http("http://plant-sim:8080/fault", {"scenario": "spike", "duration_s": 8}, AUTH)
    ilk, pump_off = False, False
    t0 = time.time()
    while time.time() - t0 < 8:
        if status.get(("PLC-01", "interlock")) is True:
            ilk = True
            time.sleep(1.2)
            pump_off = http("http://plant-sim:8080/state", headers=AUTH)["commands"]["pump_run"] is False
            break
        time.sleep(0.2)
    http("http://plant-sim:8080/fault/clear", {}, AUTH)
    from ot_ops import Operator                        # 트립 기억: 끊긴 동안에도 OT 안에서 운전원이 리셋·재기동한다
    rec = Operator().recover_interlock()
    out |= {"interlock_seen": ilk, "pump_off_during_interlock": pump_off, "reset_in_ot": rec}
    rest = a.cut_s - (time.time() - t_cut) - 5
    time.sleep(max(0, rest))
    out["fuxa_daq_rows_during_cut"] = fuxa_daq_count(int(t_cut * 1000), int(time.time() * 1000))
    out["during_s"] = round(time.time() - t_cut, 1)
    json.dump(out, open(STATE_FILE, "w"))
    res = {"during": out, "ot_continues": out["fuxa_value_updates"] and out["operator_ack"] == "ACCEPTED" and ilk and pump_off
                                           and out["fuxa_daq_rows_during_cut"] > 0 and rec.get("released") is True}
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))
else:
    st = json.load(open(STATE_FILE))
    t_join = time.time()
    time.sleep(40)                         # 브리지 재연결(백오프 최대 10 s)·쌓인 메시지 전달·수신기 처리 대기
    with lock:
        got = {tp.split("/")[-1]: b for t, tp, b in msgs if tp.startswith(RESP + "/")}
    ra, rb = got.get(st["job_a"]), got.get(st["job_b"])
    import psycopg
    with psycopg.connect(f"host=postgres dbname=plant user=ai_app password={os.environ['PG_AI_PASSWORD']}", autocommit=True) as c:
        ev = [f'{r[0]}:{r[1]}' for r in c.execute("SELECT kind, status FROM workflow.request_event WHERE job_order_id=%s ORDER BY id", (st["job_a"],))]
    res = json.load(open(a.out, encoding="utf-8"))
    res["after"] = {"job_a_response_on_ot": ra, "job_a_events": ev, "job_b_response_on_ot": rb}
    res["mqtt_expiry_dropped"] = ra is None and not any(e.startswith("receipt") for e in ev)
    res["body_expiry_rejected"] = bool(rb) and rb.get("status") == "REJECTED" and rb.get("reason") == "EXPIRED"
    res["pass"] = res["ot_continues"] and res["mqtt_expiry_dropped"] and res["body_expiry_rejected"]
    json.dump(res, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(json.dumps({k: res[k] for k in ("ot_continues", "mqtt_expiry_dropped", "body_expiry_rejected", "pass")}, ensure_ascii=False))
