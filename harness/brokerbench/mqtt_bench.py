"""브로커 비교 부하·측정 클라이언트 (MQTT 3.1.1, QoS1 — V1 Telegraf·FUXA 와 같은 조건).

    python /repo/harness/brokerbench/mqtt_bench.py --broker mosquitto --mode normal --exp EXP-130 --run b1

모드
- normal       : 12개 태그 토픽에 초당 RATE 건을 DURATION 초 발행, 영속 세션 구독자가 수신 → 유실·중복·지연
- live_restart : normal 과 같되 도중에 호스트가 브로커를 재시작(harness/brokerbench/run.sh) → 유실·중복·최대 수신 공백
- offline_queue: 구독자 세션 생성 후 끊음 → 600건 발행 + retained 1건 → 호스트가 브로커 재시작 →
                 같은 client_id 로 재접속(재구독 없음)해 받은 건수, 새 클라이언트가 retained 를 받는지
- ws           : WebSocket(8083, /mqtt)으로 발행·구독 왕복 20건
결과: /experiments/<exp>/raw/<broker>_<mode>_<run>.json
"""
import argparse
import json
import pathlib
import statistics
import threading
import time

import paho.mqtt.client as mqtt

TAGS = ["LT-101", "LT-102", "TT-101", "TT-102", "PT-101", "FT-101", "FT-102",
        "IT-101", "IT-102", "VT-101", "pH-101", "CT-101"]


def client(cid, broker, clean=False, transport="tcp"):
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cid, clean_session=clean,
                    protocol=mqtt.MQTTv311, transport=transport)
    if transport == "websockets":
        c.ws_set_options(path="/mqtt")
    c.reconnect_delay_set(1, 2)
    c.max_inflight_messages_set(100)
    return c


def pct(v, q):
    v = sorted(v)
    return round(v[min(len(v) - 1, int(round(q * (len(v) - 1))))], 2) if v else None


def wait_connected(c, flag, timeout=60):
    t = time.time()
    while not flag.is_set() and time.time() - t < timeout:
        time.sleep(0.05)
    return flag.is_set()


def stream(a, restart_note=None):
    base = f"bench/{a.run}"
    got = {}           # seq -> [recv_ns, count]
    arrivals = []
    sub_ok = threading.Event()
    lock = threading.Lock()

    def on_msg(c, u, m):
        now = time.time_ns()
        d = json.loads(m.payload)
        with lock:
            arrivals.append(now)
            if d["seq"] in got:
                got[d["seq"]][1] += 1
            else:
                got[d["seq"]] = [now - d["send_ns"], 1]

    def on_conn(c, u, flags, rc, props=None):
        if rc == 0:
            c.subscribe(f"{base}/#", qos=1)   # 재접속마다 재구독(일반적인 운영 클라이언트 동작)
            sub_ok.set()

    sub = client(f"sub-{a.run}", a.broker)
    sub.on_message, sub.on_connect = on_msg, on_conn
    sub.connect_async(a.broker, 1883)
    sub.loop_start()
    pub_ok = threading.Event()
    pub = client(f"pub-{a.run}", a.broker, clean=True)
    pub.on_connect = lambda c, u, f, rc, p=None: pub_ok.set() if rc == 0 else None
    pub.connect_async(a.broker, 1883)
    pub.loop_start()
    if not (wait_connected(sub, sub_ok) and wait_connected(pub, pub_ok)):
        return {"error": "connect failed"}
    time.sleep(1)
    n = int(a.rate * a.duration)
    t0 = time.time()
    rc_fail = 0
    for seq in range(n):
        target = t0 + seq / a.rate
        d = target - time.time()
        if d > 0:
            time.sleep(d)
        info = pub.publish(f"{base}/plant/{TAGS[seq % 12]}", json.dumps({"seq": seq, "send_ns": time.time_ns()}), qos=1)
        if info.rc not in (mqtt.MQTT_ERR_SUCCESS, mqtt.MQTT_ERR_NO_CONN):
            rc_fail += 1
    deadline = time.time() + 30
    while time.time() < deadline and len(got) < n:
        time.sleep(0.5)
    time.sleep(2)
    for c in (pub, sub):
        c.loop_stop()
        c.disconnect()
    lat = [v[0] / 1e6 for v in got.values()]
    gaps = [(b - x) / 1e6 for x, b in zip(sorted(arrivals), sorted(arrivals)[1:])]
    return {"sent": n, "received_unique": len(got), "lost": n - len(got),
            "duplicates": sum(v[1] - 1 for v in got.values()), "publish_rc_fail": rc_fail,
            "latency_ms": {"p50": pct(lat, .5), "p95": pct(lat, .95), "p99": pct(lat, .99), "max": pct(lat, 1)},
            "max_gap_ms": round(max(gaps), 1) if gaps else None, "note": restart_note}


def offline_queue(a):
    base = f"bench/{a.run}"
    raw = pathlib.Path(f"/experiments/{a.exp}/raw")
    ok = threading.Event()
    sub = client(f"oq-{a.run}", a.broker, clean=False)
    sub.on_connect = lambda c, u, f, rc, p=None: (c.subscribe(f"{base}/q/#", qos=1), ok.set()) if rc == 0 else None
    sub.connect(a.broker, 1883)
    sub.loop_start()
    wait_connected(sub, ok)
    time.sleep(1)
    sub.loop_stop()
    sub.disconnect()                     # 세션만 남기고 오프라인
    pub = client(f"oqp-{a.run}", a.broker, clean=True)
    pub.connect(a.broker, 1883)
    pub.loop_start()
    infos = [pub.publish(f"{base}/q/{TAGS[i % 12]}", json.dumps({"seq": i}), qos=1) for i in range(600)]
    for i in infos:
        i.wait_for_publish(timeout=30)
    acked = sum(1 for i in infos if i.is_published())
    pub.publish(f"{base}/advisory", "RETAINED-ADVISORY", qos=1, retain=True).wait_for_publish(timeout=10)
    pub.loop_stop()
    pub.disconnect()
    (raw / f"{a.broker}_{a.run}.ready").write_text("ready")
    t = time.time()
    while not (raw / f"{a.broker}_{a.run}.restarted").exists() and time.time() - t < 180:
        time.sleep(0.5)
    time.sleep(3)
    got, sp = [], {}
    sub2 = client(f"oq-{a.run}", a.broker, clean=False)
    sub2.on_message = lambda c, u, m: got.append(json.loads(m.payload)["seq"])

    def on_c2(c, u, flags, rc, p=None):
        sp["session_present"] = bool(getattr(flags, "session_present", False))
        sp["rc"] = str(rc)
    sub2.on_connect = on_c2              # 재구독하지 않는다: 브로커가 세션·큐를 보존했는지만 본다
    sub2.connect_async(a.broker, 1883)
    sub2.loop_start()
    time.sleep(15)
    sub2.loop_stop()
    sub2.disconnect()
    ret = []
    r = client(f"ret-{a.run}", a.broker, clean=True)
    r.on_connect = lambda c, u, f, rc, p=None: c.subscribe(f"{base}/advisory", qos=1)
    r.on_message = lambda c, u, m: ret.append(m.payload.decode())
    r.connect_async(a.broker, 1883)
    r.loop_start()
    time.sleep(5)
    r.loop_stop()
    r.disconnect()
    return {"queued_acked": acked, "received_after_restart": len(set(got)), "session_present": sp.get("session_present"),
            "connect_rc": sp.get("rc"), "retained_after_restart": "RETAINED-ADVISORY" in ret}


def ws(a):
    base = f"bench/{a.run}/ws"
    got, ok = [], threading.Event()
    c = client(f"ws-{a.run}", a.broker, clean=True, transport="websockets")
    c.on_connect = lambda cl, u, f, rc, p=None: (cl.subscribe(f"{base}/#", qos=1), ok.set()) if rc == 0 else None
    c.on_message = lambda cl, u, m: got.append(m.payload)
    try:
        c.connect_async(a.broker, 8083)
        c.loop_start()
        if not wait_connected(c, ok, 20):
            return {"ws_connected": False, "roundtrip": 0}
        time.sleep(1)
        for i in range(20):
            c.publish(f"{base}/t", str(i), qos=1)
        time.sleep(3)
        return {"ws_connected": True, "roundtrip": len(got)}
    finally:
        c.loop_stop()
        c.disconnect()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--broker", required=True)
    ap.add_argument("--mode", required=True, choices=["normal", "live_restart", "offline_queue", "ws"])
    ap.add_argument("--exp", default="EXP-130")
    ap.add_argument("--run", required=True)
    ap.add_argument("--rate", type=float, default=120)
    ap.add_argument("--duration", type=float, default=60)
    a = ap.parse_args()
    out = pathlib.Path(f"/experiments/{a.exp}/raw/{a.broker}_{a.mode}_{a.run}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise SystemExit(f"{out} 이미 있음 — 새 run ID 로")
    if a.mode == "normal":
        res = stream(a)
    elif a.mode == "live_restart":
        res = stream(a, "호스트가 발행 시작 약 20초 뒤 브로커 docker restart")
    elif a.mode == "offline_queue":
        res = offline_queue(a)
    else:
        res = ws(a)
    res.update({"broker": a.broker, "mode": a.mode, "run": a.run, "rate": a.rate, "duration": a.duration})
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
