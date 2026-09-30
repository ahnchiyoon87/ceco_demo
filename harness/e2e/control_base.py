"""[측정 도구 — 솔루션 부품 아님] 새 베이스 제어·안전 회귀(OT 쪽). 측정 클라이언트(세 망)에서 실행:
  base_client python harness/e2e/control_base.py --out /repo/experiments/<EXP>/raw/control_base.json [--only S14,S15]

V1 회귀 S14~S22 는 V1 쓰기 길(Modbus 코일·Vue API) 기준이었다. 새 명령 길 두 가지로 다시 정의한다(HANDOFF §3-5).
  운전원 길 : FUXA → OT 허브 …/cmd/operator → 엣지 → PLC 운전원 채널 → PLC ACK(…/ack/operator)·상태
  외부 요청 길: 업무 DB workflow(요청+승인) → IT 발송기 → DMZ 게이트웨이(ⓐ) → DMZ 브로커 → OT 허브 → OT 수신기(ⓑ)
             → (REMOTE_MANUAL 이면 운전원 수락) → …/cmd/request → PLC(ⓒ) → 업무 서비스 재관측
FUXA 대역: 운전원 명령·요청 수락/거부는 FUXA 계정으로 FUXA 와 같은 토픽·같은 모양으로 낸다(버튼을 누른 것과 같은 메시지).
외부 요청 대역: AI 업무 도우미와 같은 계정(ai_app)·같은 방식으로 workflow 에 요청·승인을 넣는다.
AI 함수 쪽(대응안 반려·같은 승인 두 번·업무 DB 다운) 은 control_ai.py(knowledge 컨테이너 안)가 잰다.

판정하는 뜻은 V1 과 같다: 인터록, 사람 승인, 실행 직전 재검사, 중복 실행 방지, 감사 기록, 명령 ≠ 상태.
  S14 운전원 기동·정지 → PLC ACCEPTED, 가상설비 명령 반영(5 s 안)
  S15 범위 밖 설정값: 운전원(밸브 150 %) → PLC RANGE / 외부(온도 95 ℃) → 게이트웨이 PARAMETER_RANGE, 설비 변화 없음
  S16 인터록 중 펌프 기동: 운전원 → PLC INTERLOCK, 펌프 출력 0 유지. 외부 요청은 허용 작업에 펌프 기동이 없다(설계로 차단)
  S17 운전원 거부 → OPERATOR_REJECTED, 설비 변화 없음
  S18 대기 중 조건 변화(정비 모드 켬) 뒤 수락 → 수신기 재검사 거부(MAINTENANCE), 설비 변화 없음
  S19 쓰기 길 끊김(엣지 정지) → ⓐ 수용 뒤 ACK 5 s 초과 '결과 모름'·만료 + 5 s '미확인', 성공 기록 없음, 다시 이으면 만료 요청은 버려짐
  S20 PLC 수용 응답은 왔는데 상태가 바뀌지 않음 → 10 s 뒤 command_disagree + COMMAND_DISAGREE alert, 성공 기록 없음
  S21 같은 요청이 OT 에 두 번 도착(QoS 1 재전송 모사) → 수신기 1회 처리, PLC ACK 1회, 설비 쓰기 1회
  MODE 모드 표: LOCAL·정비 → 외부 거부 / REMOTE_AUTO → 운전원 조작 거부·외부 자동 수용 / REMOTE_MANUAL → 운전원 대기
  EXP  본문 만료가 지난 요청(메시지 만료는 남음) → 수신기 EXPIRED
  OPT  운전원 대기 60 s 초과 → OPERATOR_TIMEOUT
  AUD  요청마다 두 겹 응답(ⓐ HTTP, ⓑⓒ 응답 토픽)과 같은 요청 ID 감사 기록, audit.log UPDATE·DELETE 거부
결과는 --out JSON(항목별 pass·근거). 끝나면 모드·정비·설비 명령을 시작 전으로 되돌린다.
"""
from __future__ import annotations

import argparse, base64, json, os, threading, time, urllib.request, uuid

import paho.mqtt.client as mqtt
import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

REG = json.load(open("registry/generated/tags.json", encoding="utf-8"))
PFX = REG["line_prefix"] if "line_prefix" in REG else "AR-100/reaction/reactor-line-01"
CMD = {(c["asset"], c["name"]): c for c in REG["commands"]}
ACK_OP, ACK_RQ = REG["plc"]["ack_operator_topic"], REG["plc"]["ack_request_topic"]
RESP, PENDING, DECISION, REQ_IN = (REG["request"][k] for k in ("response_prefix", "pending_topic", "decision_topic", "in_topic"))
SIM, PANEL = "http://plant-sim:8080", "http://plant-sim:8081"
R: dict = {}


def basic(u, p):
    return {"Authorization": "Basic " + base64.b64encode(f"{u}:{p}".encode()).decode()}


def http(url, body=None, headers=None):
    r = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None,
                               {"Content-Type": "application/json", **(headers or {})}, method="POST" if body is not None else "GET")
    return json.load(urllib.request.urlopen(r, timeout=10))


sim_state = lambda: http(SIM + "/state", headers=basic(os.environ["SIM_USER"], os.environ["SIM_PASSWORD"]))
panel = lambda action, **kw: http(PANEL + "/panel", {"action": action, **kw}, basic(os.environ["FIELD_USER"], os.environ["FIELD_PASSWORD"]))
fault = lambda body: http(SIM + ("/fault" if body else "/fault/clear"), body or {}, basic(os.environ["SIM_USER"], os.environ["SIM_PASSWORD"]))

# ── MQTT: 관측(viewer), FUXA 대역(fuxa), 수신기 응답 주입(ot-receiver, S20), DMZ 요청 주입(gateway, S21·EXP) ──
lock, msgs = threading.Lock(), []   # (수신 시각, 토픽, 본문 dict, retain)
status: dict[tuple[str, str], object] = {}


def client(user, pw, host="ot-hub", sub=None, v5=False):
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"ctl-{user}-{uuid.uuid4().hex[:6]}",
                    protocol=mqtt.MQTTv5 if v5 else mqtt.MQTTv311)
    c.username_pw_set(user, pw)
    if sub:
        c.on_connect = lambda cl, u, f, rc, p=None: [cl.subscribe(t, 1) for t in sub]

        def on_msg(cl, u, m):
            try:
                body = json.loads(m.payload)
            except ValueError:
                return
            parts = m.topic.split("/")
            if len(parts) == 6 and parts[4] in ("status", "state") and isinstance(body, dict):
                status[(parts[3], parts[5])] = body.get("value")
            with lock:
                msgs.append((time.time(), m.topic, body, m.retain))
        c.on_message = on_msg
    c.connect(host, 1883)
    c.loop_start()
    return c


view = client("viewer", os.environ["MQTT_PASS"], sub=[f"{PFX}/+/status/+", f"{PFX}/+/state/+", ACK_OP, ACK_RQ, f"{RESP}/#", PENDING])
fuxa = client("fuxa", os.environ["MQTT_FUXA_PASSWORD"])
recv = client("ot-receiver", os.environ["MQTT_RECEIVER_PASSWORD"])
dmz = client("gateway", os.environ["MQTT_GATEWAY_PASSWORD"], host="dmz-broker", v5=True)
time.sleep(3)


def wait_msg(pred, t0, timeout):
    end = time.time() + timeout
    while time.time() < end:
        with lock:
            for ts, topic, body, ret in msgs:
                if ts >= t0 and not ret and pred(topic, body):
                    return ts - t0, body
        time.sleep(0.05)
    return None, None


def iso():
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{int(time.time() * 1000) % 1000:03d}Z"


def operator(asset, name, value):
    """FUXA 버튼과 같은 운전원 명령. PLC ACK(결과 이름)와 걸린 시간을 돌려준다."""
    t0 = time.time()
    topic = CMD[(asset, name)]["operator_topic"]
    fuxa.publish(topic, json.dumps({"command": name, "value": value, "ts": iso()}), qos=1)
    dt, ack = wait_msg(lambda t, b: t == ACK_OP and (b.get("command") or {}).get("topic") == topic, t0, 6)
    return (ack or {}).get("result"), dt


def mode_of():
    return status.get(("PLC-01", "mode"))


def set_mode(m):   # REMOTE_MANUAL·REMOTE_AUTO 는 운전원 명령, LOCAL 은 현장 선택 스위치
    if m == "LOCAL":
        panel("mode", value="LOCAL")
    else:
        if mode_of() == "LOCAL":
            panel("mode", value="REMOTE")
            wait_until(lambda: mode_of() != "LOCAL", 5)
        if mode_of() != m:
            operator("PLC-01", "mode", m)
    return wait_until(lambda: mode_of() == m, 6)


def wait_until(pred, timeout):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.1)
    return pred()


# ── 업무 DB: AI 와 같은 계정·같은 방식으로 요청+승인을 넣고, 사건을 읽는다 ──
def pg(user="ai_app", pw_env="PG_AI_PASSWORD", db="plant"):
    return psycopg.connect(f"host=postgres dbname={db} user={user} password={os.environ[pw_env]} connect_timeout=5",
                           row_factory=dict_row, autocommit=True)


def request(wm, equipment, params=None, note="control_base"):
    jid = f"ctl-{uuid.uuid4().hex}"
    with pg() as c:
        c.execute("""INSERT INTO workflow.request(job_order_id, work_master_id, equipment_id, job_order_parameters,
                     requester, approver, context) VALUES (%s,%s,%s,%s,'ai-ops','operator-01',%s)""",
                  (jid, wm, equipment, Jsonb(params or []), Jsonb({"summary": note})))
        c.execute("""INSERT INTO workflow.request_event(job_order_id, kind, status, reason, detail, source)
                     VALUES (%s,'approved','APPROVED',%s,'{}','control-test')""", (jid, note))
        c.execute("""INSERT INTO audit.log(actor_type, actor_id, action, job_order_id, subject, detail)
                     VALUES ('human','operator-01','approve',%s,%s,%s)""", (jid, wm, Jsonb({"note": note})))
    return jid


def events(jid):
    with pg() as c:
        return c.execute("SELECT kind, status, reason, extract(epoch FROM at)::float8 AS at FROM workflow.request_event WHERE job_order_id=%s ORDER BY id",
                         (jid,)).fetchall()


def wait_event(jid, pred, timeout):
    end = time.time() + timeout
    while time.time() < end:
        ev = events(jid)
        if any(pred(e) for e in ev):
            return ev
        time.sleep(0.25)
    return events(jid)


kinds = lambda ev: [f'{e["kind"]}:{e["status"]}' + (f'({e["reason"]})' if e["reason"] and e["kind"] != "approved" else "") for e in ev]
has = lambda ev, kind, st=None: any(e["kind"] == kind and (st is None or e["status"] == st) for e in ev)


def decide(jid, decision):
    fuxa.publish(DECISION, json.dumps({"job_order_id": jid, "decision": decision, "ts": iso()}), qos=1)


def attempt(name, fn):
    t = time.time()
    try:
        R[name] = fn()
    except Exception as e:           # 시험 자체가 깨지면 그 사실을 결과로 남긴다(통과로 세지 않음)
        R[name] = {"pass": False, "error": f"{type(e).__name__}: {str(e)[:300]}"}
    R[name]["took_s"] = round(time.time() - t, 1)
    print(name, json.dumps(R[name], ensure_ascii=False, default=str)[:400], flush=True)


# ══════════════════════════════════ 시험 ══════════════════════════════════
def s14():
    set_mode("REMOTE_MANUAL")
    before = sim_state()["commands"]["agitator_run"]
    r1, d1 = operator("M-101", "run", False)
    ok1 = wait_until(lambda: sim_state()["commands"]["agitator_run"] is False, 5)
    r2, d2 = operator("M-101", "run", True)
    ok2 = wait_until(lambda: sim_state()["commands"]["agitator_run"] is True, 5)
    return {"pass": r1 == "ACCEPTED" and ok1 and r2 == "ACCEPTED" and ok2, "before": before,
            "stop": {"ack": r1, "ack_s": d1 and round(d1, 2), "sim": ok1}, "start": {"ack": r2, "ack_s": d2 and round(d2, 2), "sim": ok2}}


def s15():
    set_mode("REMOTE_MANUAL")
    v0 = sim_state()["commands"]["valve_open_sp"]
    r, _ = operator("CV-101", "open_sp", 150)
    time.sleep(2)
    v1 = sim_state()["commands"]["valve_open_sp"]
    t0 = sim_state()["commands"]["temp_sp_c"]
    jid = request("WM-R101-TEMPSP", "R-101", [{"id": "temp_sp_c", "value": 95.0}], "S15 범위 밖")
    ev = wait_event(jid, lambda e: e["kind"] in ("gateway_rejected", "gateway_accepted"), 10)
    time.sleep(2)
    t1 = sim_state()["commands"]["temp_sp_c"]
    # 설정값은 생산 스케줄(PLC)이 늘 조금씩 움직이므로 '변화 없음'은 요청 값에 닿지 않았는지와 PLC 응답 유무로 본다
    return {"pass": r == "RANGE" and abs(v1 - 150) > 1 and has(ev, "gateway_rejected") and abs(t1 - 95.0) > 0.6 and not has(ev, "plc"),
            "operator": {"ack": r, "valve_before": v0, "valve_after": v1},
            "external": {"job": jid, "events": kinds(ev), "temp_before": t0, "temp_after": t1}}


def s16():
    """스파이크(+3.6 bar 계기 튐) 동안 인터록은 6.5 bar 트립 → 펌프 정지로 압력이 내려가 5.2 bar 해제 → 재기동을 반복한다
    (히스테리시스 인터록의 정상 동작). 판정: 인터록 중 기동 명령 → PLC INTERLOCK 거부, 그리고 인터록이 1 s 넘게 켜진
    구간의 표본마다 가상설비 펌프 출력이 꺼져 있고 유량 < 0.5(V1 S16 과 같은 물리 판정)."""
    set_mode("REMOTE_MANUAL")
    fault({"scenario": "spike", "duration_s": 15})   # spike 는 kind: event → 실제 초
    samples, ack, t0 = [], None, time.time()
    while time.time() - t0 < 15:
        ilk = status.get(("PLC-01", "interlock"))
        if ilk is True and ack is None:
            ack, _ = operator("P-101", "run", True)
        s = sim_state()
        samples.append({"t": round(time.time() - t0, 2), "ilk": status.get(("PLC-01", "interlock")),
                        "pump": s["commands"]["pump_run"], "ft": s["readings"].get("FT-101")})
        time.sleep(0.25)
    fault(None)
    released = wait_until(lambda: status.get(("PLC-01", "interlock")) is False, 60)
    # 인터록이 표본 앞뒤 1 s 동안 계속 켜져 있던 표본만 본다(PLC → 가상설비 출력 반영·유량 감소 지연 제외)
    stable = [x for x in samples if all(y["ilk"] is True for y in samples if abs(y["t"] - x["t"]) <= 1.0)]
    bad = [x for x in stable if x["pump"] is not False or (x["ft"] is not None and x["ft"] >= 0.5)]
    trips = sum(1 for a, b in zip(samples, samples[1:]) if a["ilk"] is not True and b["ilk"] is True)
    return {"pass": ack == "INTERLOCK" and len(stable) >= 3 and not bad, "ack_during": ack, "trips": trips,
            "stable_samples": len(stable), "violations": bad[:5], "released": released,
            "external": "허용 작업(WM-M101-STOP·WM-HX102-ENABLE·WM-R101-TEMPSP)에 펌프 기동이 없다 — 외부 길은 설계로 차단"}


def s17():
    set_mode("REMOTE_MANUAL")
    c0 = sim_state()["commands"]["agitator_run"]
    jid = request("WM-M101-STOP", "M-101", note="S17 운전원 거부")
    ev = wait_event(jid, lambda e: e["kind"] == "receipt", 10)
    decide(jid, "reject")
    ev = wait_event(jid, lambda e: e["kind"] == "operator", 10)
    time.sleep(2)
    c1 = sim_state()["commands"]["agitator_run"]
    return {"pass": has(ev, "receipt", "OPERATOR_WAIT") and has(ev, "operator", "OPERATOR_REJECTED") and c0 == c1 and not has(ev, "plc"),
            "job": jid, "events": kinds(ev), "agitator_before": c0, "agitator_after": c1}


def s18():
    set_mode("REMOTE_MANUAL")
    c0 = sim_state()["commands"]["cooler_enable"]
    jid = request("WM-HX102-ENABLE", "HX-102", note="S18 대기 중 조건 변화")
    wait_event(jid, lambda e: e["kind"] == "receipt", 10)
    panel("maintenance_on", operator_id=101)
    wait_until(lambda: status.get(("PLC-01", "maintenance")) is True, 6)
    decide(jid, "accept")
    ev = wait_event(jid, lambda e: e["kind"] == "operator", 10)
    time.sleep(2)
    c1 = sim_state()["commands"]["cooler_enable"]
    panel("maintenance_release")
    wait_until(lambda: status.get(("PLC-01", "maintenance")) is False, 6)
    return {"pass": has(ev, "operator", "REJECTED") and c0 == c1 and not has(ev, "plc"), "job": jid, "events": kinds(ev),
            "cooler_before": c0, "cooler_after": c1}


def s19():
    set_mode("REMOTE_AUTO")
    t0 = sim_state()["commands"]["temp_sp_c"]
    target = 62.0 if abs(t0 - 62.0) > 1 else 64.0
    open("/repo/experiments/.s19_state.json", "w").write(json.dumps({"target": target, "temp_before": t0}))
    return {"pass": True, "note": "준비만(모드 REMOTE_AUTO). 엣지 정지·요청은 S19A, 재기동 뒤 확인은 S19B", "temp_before": t0}


def s19a():
    """엣지가 멈춘 상태(control_base.sh 가 멈춤)에서 요청 → ⓐ 수용, ACK 5 s 초과 '결과 모름', 만료 + 5 s '미확인'."""
    st = json.load(open("/repo/experiments/.s19_state.json"))
    jid = request("WM-R101-TEMPSP", "R-101", [{"id": "temp_sp_c", "value": st["target"]}], "S19 쓰기 길 끊김")
    ev = wait_event(jid, lambda e: e["kind"] == "expired_unconfirmed", 50)
    st["job"] = jid
    open("/repo/experiments/.s19_state.json", "w").write(json.dumps(st))
    acc = next((e["at"] for e in ev if e["kind"] == "gateway_accepted"), None)
    ackto = next((e["at"] for e in ev if e["kind"] == "ack_timeout"), None)
    return {"pass": has(ev, "gateway_accepted") and has(ev, "ack_timeout", "UNKNOWN") and has(ev, "expired_unconfirmed")
                    and not has(ev, "receipt"), "job": jid, "events": kinds(ev), "ack_timeout_after_s": acc and ackto and round(ackto - acc, 2)}


def s19b():
    """엣지를 다시 켠 뒤(20 s): 만료된 요청은 전달되지 않거나(MQTT 만료) 수신기가 거부(본문 만료) — 설비 변화 없음."""
    st = json.load(open("/repo/experiments/.s19_state.json"))
    wait_until(lambda: mode_of() is not None, 30)
    time.sleep(20)
    ev = events(st["job"])
    t1 = sim_state()["commands"]["temp_sp_c"]
    layer = "MQTT 메시지 만료(전달 안 됨)" if not has(ev, "receipt") else ("본문 만료(수신기 EXPIRED)" if "EXPIRED" in str(kinds(ev)) else "전달·처리됨")
    return {"pass": not has(ev, "observed") and not has(ev, "plc") and not has(ev, "receipt") and abs(t1 - st["target"]) > 0.6,
            "job": st["job"], "events": kinds(ev), "dropped_by": layer, "target": st["target"], "temp_before": st["temp_before"], "temp_after": t1,
            "note": "온도 설정값은 REMOTE_AUTO 생산 스케줄이 움직인다 — 판정은 목표값 미도달과 수신·PLC 응답 없음"}


def s20():
    set_mode("REMOTE_MANUAL")
    jid = request("WM-HX102-ENABLE", "HX-102", note="S20 수용했는데 상태 그대로")
    wait_event(jid, lambda e: e["kind"] == "receipt", 10)
    c0 = status.get(("HX-102", "enable"))
    t_inj = time.time()
    recv.publish(f"{RESP}/{jid}", json.dumps({"job_order_id": jid, "stage": "plc", "status": "ACCEPTED", "reason": "ACCEPTED",
                                              "plc_ack_code": 0, "ts": iso(), "injected_by": "control_base S20"}), qos=1)
    ev = wait_event(jid, lambda e: e["kind"] in ("command_disagree", "observed"), 20)
    plc_at = next((e["at"] for e in ev if e["kind"] == "plc"), None)
    dis_at = next((e["at"] for e in ev if e["kind"] == "command_disagree"), None)
    decide(jid, "reject")                  # 대기 목록 정리
    return {"pass": c0 is False and has(ev, "command_disagree", "DISAGREE") and not has(ev, "observed"),
            "job": jid, "events": kinds(ev), "state_enable": c0, "disagree_after_plc_s": plc_at and dis_at and round(dis_at - plc_at, 2),
            "injected_at_s": round(t_inj, 3)}


def req_msg(jid, wm, equipment, params=None, expires_in=30):
    now = time.time()
    return {"job_order_id": jid, "work_master_id": wm, "equipment_id": equipment, "job_order_parameters": params or [],
            "requester": "ai-ops", "approver": "operator-01", "created_at": now, "expires_at": int(now) + expires_in,
            "context": {"summary": "control_base"}}


def dmz_publish(body, expiry=30):
    from paho.mqtt.packettypes import PacketTypes
    from paho.mqtt.properties import Properties
    props = Properties(PacketTypes.PUBLISH)
    props.MessageExpiryInterval = expiry
    return dmz.publish(REQ_IN, json.dumps(body), qos=1, properties=props)


def s21():
    set_mode("REMOTE_AUTO")
    t0 = sim_state()["commands"]["temp_sp_c"]
    target = 66.0 if abs(t0 - 66.0) > 1 else 68.0
    jid = f"ctl-dup-{uuid.uuid4().hex}"
    body = req_msg(jid, "WM-R101-TEMPSP", "R-101", [{"id": "temp_sp_c", "value": target}])
    ts = time.time()
    dmz_publish(body); dmz_publish(body)               # 같은 메시지가 두 번(QoS 1 재전송 모사)
    time.sleep(8)
    with lock:
        receipts = [b for t, tp, b, r in msgs if t >= ts and tp == f"{RESP}/{jid}" and b.get("stage") == "receipt"]
        acks = [b for t, tp, b, r in msgs if t >= ts and tp == ACK_RQ and b.get("job_order_id") == jid]
    t1 = sim_state()["commands"]["temp_sp_c"]
    return {"pass": len(receipts) == 1 and len(acks) == 1 and acks[0].get("result") == "ACCEPTED" and abs(t1 - target) < 0.6,
            "job": jid, "receipts": len(receipts), "plc_acks": len(acks), "ack": acks[0].get("result") if acks else None,
            "temp_before": t0, "temp_after": t1, "note": "워크플로에 없는 요청 ID 라 업무 서비스는 기록하지 않는다(등록되지 않은 응답)"}


def mode_table():
    out = {}
    # LOCAL: 외부 거부(수신기 LOCAL_MODE), 운전원 거부(PLC LOCAL_MODE)
    set_mode("LOCAL")
    jid = request("WM-M101-STOP", "M-101", note="모드 표 LOCAL")
    ev = wait_event(jid, lambda e: e["kind"] == "receipt", 10)
    r, _ = operator("M-101", "run", False)
    out["LOCAL"] = {"external": kinds(ev), "operator": r,
                    "pass": has(ev, "receipt", "REJECTED") and "LOCAL_MODE" in str(kinds(ev)) and r == "LOCAL_MODE"}
    set_mode("REMOTE_MANUAL")
    # 정비: 외부 거부(MAINTENANCE), 운전원 기동·변경 거부(정지는 허용)
    panel("maintenance_on", operator_id=102)
    wait_until(lambda: status.get(("PLC-01", "maintenance")) is True, 6)
    jid = request("WM-M101-STOP", "M-101", note="모드 표 정비")
    ev = wait_event(jid, lambda e: e["kind"] == "receipt", 10)
    r, _ = operator("CV-101", "open_sp", 45)
    panel("maintenance_release")
    wait_until(lambda: status.get(("PLC-01", "maintenance")) is False, 6)
    out["MAINTENANCE"] = {"external": kinds(ev), "operator_change": r,
                          "pass": has(ev, "receipt", "REJECTED") and "MAINTENANCE" in str(kinds(ev)) and r == "MAINTENANCE"}
    # REMOTE_AUTO: 운전원 조작 거부(MODE), 외부 자동 수용 → PLC ACCEPTED → 재관측
    set_mode("REMOTE_AUTO")
    r, _ = operator("CV-101", "open_sp", 45)
    t0 = sim_state()["commands"]["temp_sp_c"]
    target = 70.0 if abs(t0 - 70.0) > 1 else 72.0
    jid = request("WM-R101-TEMPSP", "R-101", [{"id": "temp_sp_c", "value": target}], "모드 표 REMOTE_AUTO")
    ev = wait_event(jid, lambda e: e["kind"] in ("observed", "command_disagree"), 20)
    t1 = sim_state()["commands"]["temp_sp_c"]
    out["REMOTE_AUTO"] = {"operator": r, "external": kinds(ev), "temp_before": t0, "temp_after": t1,
                          "pass": r == "MODE" and has(ev, "receipt", "AUTO_ACCEPTED") and has(ev, "plc", "ACCEPTED") and has(ev, "observed")}
    out["REMOTE_AUTO"]["job"] = jid
    out["REMOTE_AUTO"]["timeline_s"] = timeline(ev)
    # REMOTE_MANUAL: 외부는 운전원 대기 → 수락 → PLC ACCEPTED → 재관측
    set_mode("REMOTE_MANUAL")
    c0 = sim_state()["commands"]["cooler_enable"]
    jid = request("WM-HX102-ENABLE", "HX-102", note="모드 표 REMOTE_MANUAL")
    wait_event(jid, lambda e: e["kind"] == "receipt", 10)
    decide(jid, "accept")
    ev = wait_event(jid, lambda e: e["kind"] in ("observed", "command_disagree"), 20)
    c1 = sim_state()["commands"]["cooler_enable"]
    out["REMOTE_MANUAL"] = {"external": kinds(ev), "cooler_before": c0, "cooler_after": c1, "job": jid, "timeline_s": timeline(ev),
                            "pass": has(ev, "receipt", "OPERATOR_WAIT") and has(ev, "operator", "OPERATOR_ACCEPTED")
                                    and has(ev, "plc", "ACCEPTED") and has(ev, "observed") and c1 is True}
    if c0 is False:
        operator("HX-102", "enable", False)     # 원래대로
    out["pass"] = all(v["pass"] for v in out.values() if isinstance(v, dict))
    return out


def timeline(ev):
    t0 = next((e["at"] for e in ev if e["kind"] == "approved"), None)
    return {f'{e["kind"]}:{e["status"]}': round(e["at"] - t0, 2) for e in ev} if t0 else None


def expired_body():
    set_mode("REMOTE_AUTO")
    jid = f"ctl-exp-{uuid.uuid4().hex}"
    body = req_msg(jid, "WM-M101-STOP", "M-101", expires_in=-5)   # 본문 만료 지남, MQTT 만료는 30 s 남음
    ts = time.time()
    dmz_publish(body, expiry=30)
    _, resp = wait_msg(lambda t, b: t == f"{RESP}/{jid}", ts, 8)
    set_mode("REMOTE_MANUAL")
    return {"pass": (resp or {}).get("status") == "REJECTED" and (resp or {}).get("reason") == "EXPIRED", "response": resp}


def operator_timeout():
    set_mode("REMOTE_MANUAL")
    jid = request("WM-M101-STOP", "M-101", note="운전원 대기 60 s 초과")
    ev = wait_event(jid, lambda e: e["kind"] == "receipt", 10)
    wait_at = next((e["at"] for e in ev if e["kind"] == "receipt"), None)
    ev = wait_event(jid, lambda e: e["kind"] == "operator", 80)
    op = next((e for e in ev if e["kind"] == "operator"), None)
    return {"pass": op is not None and op["status"] == "REJECTED" and op["reason"] == "OPERATOR_TIMEOUT",
            "events": kinds(ev), "timeout_after_s": op and wait_at and round(op["at"] - wait_at, 1)}


def audit_trail():
    jid = R.get("MODE", {}).get("REMOTE_MANUAL", {}).get("job")
    with pg() as c:
        rows = c.execute("SELECT actor_type, actor_id, action, subject FROM audit.log WHERE job_order_id=%s ORDER BY id", (jid,)).fetchall() if jid else []
    denied = {}
    for user, env in (("ops", "PG_OPS_PASSWORD"), ("postgres", "PG_SUPERUSER_PASSWORD")):
        for sql in ("UPDATE audit.log SET action = action WHERE id = (SELECT min(id) FROM audit.log)",
                    "DELETE FROM audit.log WHERE id = (SELECT min(id) FROM audit.log)"):
            try:
                with pg(user, env) as c:
                    c.execute(sql)
                denied[f"{user}:{sql.split()[0]}"] = "허용됨"
            except psycopg.Error as e:
                denied[f"{user}:{sql.split()[0]}"] = f"거부: {type(e).__name__}: {str(e).splitlines()[0][:120]}"
    actions = [r["action"] for r in rows]
    return {"pass": bool(rows) and all(v.startswith("거부") for v in denied.values())
                    and {"approve", "gateway_accepted", "response_receipt", "response_operator", "response_plc", "observed"} <= set(actions),
            "job": jid, "audit_actions": actions, "update_delete": denied}


TESTS = {"S14": s14, "S15": s15, "S16": s16, "S17": s17, "S18": s18, "S20": s20, "S21": s21, "MODE": mode_table,
         "EXP": expired_body, "OPT": operator_timeout, "AUD": audit_trail, "S19": s19, "S19A": s19a, "S19B": s19b}
DEFAULT = ["S14", "S15", "S16", "S17", "S18", "S20", "S21", "MODE", "EXP", "OPT", "AUD"]

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--only", default="")
    ap.add_argument("--no-restore", action="store_true", help="엣지가 멈춘 단계(S19A)처럼 상태를 읽을 수 없을 때")
    a = ap.parse_args()
    if not a.no_restore:
        wait_until(lambda: mode_of() is not None and status.get(("PLC-01", "maintenance")) is not None, 10)
    start = {"mode": mode_of(), "commands": sim_state()["commands"]}
    R["start"] = start
    for name in (a.only.split(",") if a.only else DEFAULT):
        attempt(name, TESTS[name])
    # 되돌리기: 모드·설비 명령(운전원 길로)
    try:
        if a.no_restore:
            raise RuntimeError("되돌리기 생략(--no-restore)")
        set_mode("REMOTE_MANUAL")
        sc = start["commands"]
        for (asset, name), key in {("M-101", "run"): "agitator_run", ("HX-102", "enable"): "cooler_enable",
                                   ("HX-101", "enable"): "heater_enable", ("P-101", "run"): "pump_run"}.items():
            if sim_state()["commands"][key] != sc[key]:
                operator(asset, name, sc[key])
        set_mode(start["mode"] or "REMOTE_MANUAL")
        R["restored"] = {"mode": mode_of(), "commands": sim_state()["commands"]}
    except Exception as e:
        R["restored"] = {"error": str(e)}
    R["pass_all"] = all(v.get("pass") for k, v in R.items() if k in TESTS)
    if os.path.exists(a.out):                       # 단계(S19A·S19B)별 실행 결과를 한 파일에 합친다
        prev = json.load(open(a.out, encoding="utf-8"))
        R = {**prev, **{k: v for k, v in R.items() if k in TESTS or k not in prev}}
        R["pass_all"] = all(v.get("pass") for k, v in R.items() if k in TESTS)
    json.dump(R, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1, default=str)
    print(json.dumps({k: v.get("pass") for k, v in R.items() if k in TESTS}, ensure_ascii=False), "pass_all", R["pass_all"])
