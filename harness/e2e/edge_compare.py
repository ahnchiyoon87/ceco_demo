"""[측정 도구] 엣지 비교(HANDOFF §2-3 결정 ①) — Node-RED·EdgeX 를 같은 방법으로 잰다.

도구 컨테이너는 ot-net(가상설비 순번 폴링·OT 허브 구독)과 it-net(라우터 → DMZ 브로커로 요청 발행)에 붙는다.
  record   : OT 허브의 계측 토픽 도착을 기록하고, 가상설비 HR24(스캔 순번)를 20 ms 마다 읽어 순번이 나타난 시각을 함께 기록
  analyze  : 기록으로 누락(태그·스캔)·지연(가상설비 스캔 → OT 허브 도착) p50/p95·복구 시간 계산
  command  : FUXA 계정으로 운전원 명령을 내고 PLC ACK·상태 반영까지 왕복 시간(10회)
  receiver : DMZ 브로커에 작업 요청(게이트웨이 계정)을 넣어 OT 수신기의 검사·첫 응답(ⓑ)·PLC 응답을 확인
환경변수: MQTT_VIEWER_PASSWORD, MQTT_FUXA_PASSWORD, MQTT_GATEWAY_PASSWORD
"""
from __future__ import annotations

import argparse
import json
import os
import statistics
import threading
import time
import uuid

import paho.mqtt.client as mqtt
from pymodbus.client import ModbusTcpClient

LINE = "AR-100/reaction/reactor-line-01"
TAGS = ["LT-101", "LT-102", "TT-101", "TT-102", "PT-101", "FT-101", "FT-102", "IT-101", "IT-102", "VT-101", "pH-101", "CT-101"]


def client(user: str, pw_env: str, host: str, cid: str, clean=True, v5=False):
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cid,
                    protocol=mqtt.MQTTv5 if v5 else mqtt.MQTTv311, **({} if v5 else {"clean_session": clean}))
    c.username_pw_set(user, os.environ[pw_env])
    c.connect(host, 1883, 15)
    return c


def record(a):
    """OT 허브 구독(지속 세션, 허브가 재시작해도 세션 유지) + 가상설비 스캔 순번 시각."""
    rows, seqs = [], {}
    stop = time.time() + a.seconds
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"edgecmp-rec-{a.name}", clean_session=False)
    c.username_pw_set("viewer", os.environ["MQTT_VIEWER_PASSWORD"])

    def on_connect(cl, u, f, rc, p=None):
        cl.subscribe(f"{LINE}/+/tag/+", 1)
    c.on_connect = on_connect
    c.on_message = lambda cl, u, m: rows.append((time.time(), m.topic, m.payload))
    c.reconnect_delay_set(1, 2)
    c.connect_async(a.hub, 1883, 15)
    c.loop_start()
    mb = ModbusTcpClient(a.sim, port=502, timeout=1)
    while time.time() < stop:
        try:
            if not mb.connected:
                mb.connect()
            r = mb.read_holding_registers(24, count=2, slave=1)
            if not r.isError():
                s = r.registers[0] * 65536 + r.registers[1]
                seqs.setdefault(s, time.time())
        except Exception:
            pass
        time.sleep(0.02)
    time.sleep(a.drain)
    c.loop_stop()
    out = []
    for t, topic, payload in rows:
        try:
            p = json.loads(payload)
        except ValueError:
            continue
        out.append({"t": t, "tag": topic.rsplit("/", 1)[1], "seq": p.get("seq"), "quality": p.get("quality"), "ts": p.get("ts")})
    json.dump({"arrivals": out, "sim_seq": {str(k): v for k, v in seqs.items()}},
              open(a.out, "w"), ensure_ascii=False)
    print(f"기록 {len(out)}건, 스캔 {len(seqs)}개")


def analyze(a):
    d = json.load(open(a.inp))
    sim = {int(k): v for k, v in d["sim_seq"].items()}
    arr = d["arrivals"]
    lo, hi = min(sim) + 2, max(sim) - 2           # 앞뒤 경계 스캔은 뺀다
    got: dict[tuple, float] = {}
    dup = 0
    for r in arr:
        if r["seq"] is None or r["quality"] == "STALE":
            continue
        key = (r["tag"], r["seq"])
        if key in got:
            dup += 1
            continue
        got[key] = r["t"]
    expected = [(t, s) for s in range(lo, hi + 1) for t in TAGS if s in sim]
    missing = [k for k in expected if k not in got]
    lat = [got[k] - sim[k[1]] for k in expected if k in got and k[1] in sim]
    lat.sort()
    res = {"scans": hi - lo + 1, "expected_tag_scans": len(expected), "missing_tag_scans": len(missing),
           "duplicates": dup, "latency_p50_ms": round(1000 * lat[len(lat) // 2], 1) if lat else None,
           "latency_p95_ms": round(1000 * lat[int(len(lat) * 0.95)], 1) if lat else None}
    ev = json.loads(a.events) if a.events else {}
    if "restart_at" in ev:   # 복구 시간: 재기동 뒤 처음으로 '재기동 시각 이후 스캔' 값이 도착한 때까지
        fresh = [r["t"] for r in arr if r["seq"] is not None and r["seq"] in sim and sim[r["seq"]] >= ev["restart_at"] and r["t"] >= ev["restart_at"]]
        res["recover_s"] = round(min(fresh) - ev["restart_at"], 2) if fresh else None
        win = [(t, s) for (t, s) in expected if ev["stop_at"] - 1 <= sim[s] <= ev["restart_at"] + 10]
        res["outage_window_tag_scans"] = len(win)
        res["outage_missing_tag_scans"] = sum(1 for k in win if k not in got)
    json.dump(res, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(json.dumps(res, ensure_ascii=False))


def command(a):
    """운전원 명령 10회(냉각기 켬/끔 번갈아): 명령 발행 → PLC ACK → 상태 토픽 반영."""
    acks, states = [], []
    c = client("fuxa", "MQTT_FUXA_PASSWORD", a.hub, f"edgecmp-fuxa-{uuid.uuid4().hex[:6]}")
    v = client("viewer", "MQTT_VIEWER_PASSWORD", a.hub, f"edgecmp-view-{uuid.uuid4().hex[:6]}")
    v.subscribe([(f"{LINE}/PLC-01/ack/operator", 1), (f"{LINE}/HX-102/status/enable", 1)])
    v.on_message = lambda cl, u, m: (acks if "/ack/" in m.topic else states).append((time.time(), json.loads(m.payload)))
    v.loop_start(); c.loop_start()
    time.sleep(2)
    res = []
    for i in range(a.reps):
        want = i % 2 == 0
        n_ack, n_st = len(acks), len(states)
        t0 = time.time()
        c.publish(f"{LINE}/HX-102/cmd/operator", json.dumps({"command": "enable", "value": want,
                  "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"}), qos=1)
        ack = st = None
        while time.time() - t0 < 5 and (ack is None or st is None):
            if ack is None and len(acks) > n_ack:
                ack = (acks[n_ack][0] - t0, acks[n_ack][1].get("result"))
            if st is None and any(s[1].get("value") is want for s in states[n_st:]):
                st = next(s[0] for s in states[n_st:] if s[1].get("value") is want) - t0
            time.sleep(0.01)
        res.append({"i": i, "ack_s": round(ack[0], 3) if ack else None, "ack": ack[1] if ack else None,
                    "state_s": round(st, 3) if st else None})
        time.sleep(1.5)
    c.publish(f"{LINE}/HX-102/cmd/operator", json.dumps({"command": "enable", "value": False,
              "ts": time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"}), qos=1)
    time.sleep(1)
    ok = [r for r in res if r["ack"] == "ACCEPTED" and r["state_s"] is not None]
    summary = {"reps": a.reps, "accepted_and_reflected": len(ok),
               "ack_p50_s": statistics.median([r["ack_s"] for r in ok]) if ok else None,
               "state_p50_s": statistics.median([r["state_s"] for r in ok]) if ok else None, "runs": res}
    json.dump(summary, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "runs"}, ensure_ascii=False))


def receiver(a):
    """작업 요청 시험. 경로 = DMZ 브로커(게이트웨이 계정) → 브리지 in → OT 수신기."""
    got: dict[str, list] = {}
    v = client("viewer", "MQTT_VIEWER_PASSWORD", a.hub, f"edgecmp-rv-{uuid.uuid4().hex[:6]}")
    v.subscribe([("AR-100/response/#", 1)])
    v.on_message = lambda cl, u, m: got.setdefault(json.loads(m.payload)["job_order_id"], []).append((time.time(), json.loads(m.payload)))
    v.loop_start()
    gw = client("gateway", "MQTT_GATEWAY_PASSWORD", a.dmz, f"edgecmp-gw-{uuid.uuid4().hex[:6]}", v5=True)
    gw.loop_start()
    fx = client("fuxa", "MQTT_FUXA_PASSWORD", a.hub, f"edgecmp-fx-{uuid.uuid4().hex[:6]}")
    fx.loop_start()
    time.sleep(2)
    iso = lambda: time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + "Z"

    def send(wm="WM-HX102-ENABLE", eq="HX-102", params=None, exp=30, extra=None, raw=None):
        jid = f"edgecmp-{uuid.uuid4().hex[:12]}"
        body = {"job_order_id": jid, "work_master_id": wm, "equipment_id": eq, "job_order_parameters": params or [],
                "requester": "ai-ops", "approver": "operator-01", "created_at": time.time(), "expires_at": time.time() + exp}
        body.update(extra or {})
        t0 = time.time()
        gw.publish("AR-100/request/in", raw if raw is not None else json.dumps(body), qos=1)
        return jid, t0

    def wait(jid, stage, t0, timeout=5.0):
        end = time.time() + timeout
        while time.time() < end:
            for t, p in got.get(jid, []):
                if p["stage"] == stage:
                    return round(t - t0, 3), p["status"], p.get("reason")
            time.sleep(0.01)
        return None, None, None

    def mode(m):
        fx.publish(f"{LINE}/PLC-01/cmd/operator", json.dumps({"command": "mode", "value": m, "ts": iso()}), qos=1)
        time.sleep(1.5)
    out = []

    def case(name, jid, t0, stage, want_status, want_reason=None):
        dt, st, rs = wait(jid, stage, t0)
        ok = st == want_status and (want_reason is None or rs == want_reason)
        out.append({"case": name, "stage": stage, "latency_s": dt, "status": st, "reason": rs, "expected": [want_status, want_reason],
                    "verdict": "PASS" if ok else "FAIL"})
        print(f'{"PASS" if ok else "FAIL"} {name}: {st} {rs} {dt}s')
    mode("REMOTE_MANUAL")
    j, t = send(); case("REMOTE_MANUAL → 운전원 대기", j, t, "receipt", "OPERATOR_WAIT", "STORED")
    fx.publish(f"{LINE}/request/decision", json.dumps({"job_order_id": j, "decision": "accept", "ts": iso()}), qos=1)
    case("운전원 수락 → OPERATOR_ACCEPTED", j, t, "operator", "OPERATOR_ACCEPTED")
    case("운전원 수락 → PLC 수용", j, t, "plc", "ACCEPTED")
    j, t = send(raw=json.dumps({"job_order_id": "edgecmp-bad-schema-01", "work_master_id": "WM-HX102-ENABLE"}))
    case("스키마 오류 거부", "edgecmp-bad-schema-01", t, "receipt", "REJECTED", "SCHEMA_INVALID")
    j, t = send(wm="WM-R101-TEMPSP", eq="R-101", params=[{"id": "temp_sp_c", "value": 95.0}])
    case("파라미터 범위 밖 거부", j, t, "receipt", "REJECTED", "PARAMETER_RANGE")
    j, t = send(extra={"expires_at": time.time() - 1})
    case("만료 거부", j, t, "receipt", "REJECTED", "EXPIRED")
    j, t = send(eq="M-101")
    case("설비 불일치 거부", j, t, "receipt", "REJECTED", "EQUIPMENT_MISMATCH")
    mode("REMOTE_AUTO")
    fx.publish(f"{LINE}/HX-102/cmd/operator", json.dumps({"command": "enable", "value": False, "ts": iso()}), qos=1)
    lat = []
    for i in range(a.reps):
        j, t = send(wm="WM-R101-TEMPSP", eq="R-101", params=[{"id": "temp_sp_c", "value": 70.0 + (i % 5)}])
        case(f"REMOTE_AUTO 자동 수용 {i + 1}", j, t, "receipt", "AUTO_ACCEPTED")
        case(f"REMOTE_AUTO PLC 수용 {i + 1}", j, t, "plc", "ACCEPTED")
        lat.append(out[-2]["latency_s"])
        time.sleep(0.5)
    # 같은 요청을 두 번(QoS 1 재전송 흉내) → 응답은 한 번
    jid = f"edgecmp-dup-{uuid.uuid4().hex[:8]}"
    body = json.dumps({"job_order_id": jid, "work_master_id": "WM-HX102-ENABLE", "equipment_id": "HX-102", "job_order_parameters": [],
                       "requester": "ai-ops", "approver": "operator-01", "created_at": time.time(), "expires_at": time.time() + 30})
    gw.publish("AR-100/request/in", body, qos=1); gw.publish("AR-100/request/in", body, qos=1)
    time.sleep(3)
    n = sum(1 for _, p in got.get(jid, []) if p["stage"] == "receipt")
    out.append({"case": "중복 요청 → 첫 응답 1번", "count": n, "verdict": "PASS" if n == 1 else "FAIL"})
    print(f'{"PASS" if n == 1 else "FAIL"} 중복 요청 첫 응답 {n}번')
    mode("REMOTE_MANUAL")
    fx.publish(f"{LINE}/HX-102/cmd/operator", json.dumps({"command": "enable", "value": False, "ts": iso()}), qos=1)
    lat = sorted(x for x in lat if x is not None)
    summary = {"pass": sum(o["verdict"] == "PASS" for o in out), "fail": sum(o["verdict"] == "FAIL" for o in out),
               "receipt_p95_s": lat[int(len(lat) * 0.95)] if lat else None, "receipt_max_s": max(lat) if lat else None, "cases": out}
    json.dump(summary, open(a.out, "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: v for k, v in summary.items() if k != "cases"}, ensure_ascii=False))


ap = argparse.ArgumentParser()
sub = ap.add_subparsers(dest="cmd", required=True)
r = sub.add_parser("record"); r.add_argument("--seconds", type=float, required=True); r.add_argument("--name", required=True)
r.add_argument("--out", required=True); r.add_argument("--hub", default="ot-hub"); r.add_argument("--sim", default="plant-sim")
r.add_argument("--drain", type=float, default=5)
z = sub.add_parser("analyze"); z.add_argument("--inp", required=True); z.add_argument("--out", required=True)
z.add_argument("--events", default="", help='정지·재기동 시각 JSON {"stop_at":..,"restart_at":..}')
c = sub.add_parser("command"); c.add_argument("--out", required=True); c.add_argument("--hub", default="ot-hub"); c.add_argument("--reps", type=int, default=10)
v = sub.add_parser("receiver"); v.add_argument("--out", required=True); v.add_argument("--hub", default="ot-hub")
v.add_argument("--dmz", default="dmz-broker"); v.add_argument("--reps", type=int, default=10)
args = ap.parse_args()
{"record": record, "analyze": analyze, "command": command, "receiver": receiver}[args.cmd](args)
