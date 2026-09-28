"""브로커 4단계(비정상) 측정 클라이언트 — 역할별로 따로 띄운다(단절 시험에서 한쪽만 끊기 위해).

Mosquitto 2.1.2 조건부 채택(#56)의 미검증 항목: 네트워크 단절 60초(S10/R02), 과부하 10배(R08)·큐 한도, 느린 구독자, 장시간(R09).
기준 버전(EMQX 5.8.6)을 같은 스크립트로 먼저 잰다(QUESTIONS §1 ②).

역할
  sub      영속 세션(clean_session=False, 고정 client_id) 구독자. --slow-ms 로 메시지당 처리 지연(느린 구독자).
           --offline-after/--online-at 으로 "구독 후 끊고 나중에 재접속"(큐 한도 시험).
  pub      QoS1 발행자. --rate 건/s × --duration s. 페이로드 {seq, send_ns, pad}.
  analyze  pub·sub 결과 파일을 합쳐 유실·중복·지연·최대 공백·적체 해소 시간·순서 역전·자원 변화율을 계산.
파일: /experiments/<exp>/raw/stage4_<test>_<broker>_<run>_<role>.json → 합본 /experiments/<exp>/stage4_<test>_<broker>_<run>.json

    python /repo/harness/brokerbench/stage4.py --role pub --broker mosquitto --test overload --run a --rate 1200 --duration 600
"""
import argparse
import csv
import json
import os
import pathlib
import statistics
import threading
import time

import paho.mqtt.client as mqtt

EXPROOT = os.environ.get("BENCH_EXPERIMENTS", "/experiments")   # 시험용 덮어쓰기(기본 컨테이너 경로)
TAGS = ["LT-101", "LT-102", "TT-101", "TT-102", "PT-101", "FT-101", "FT-102",
        "IT-101", "IT-102", "VT-101", "pH-101", "CT-101"]


def pct(v, q):
    v = sorted(v)
    return round(v[min(len(v) - 1, int(round(q * (len(v) - 1))))], 2) if v else None


def mk(cid, broker, clean):
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cid, clean_session=clean, protocol=mqtt.MQTTv311)
    if os.environ.get("BENCH_MQTT_USER"):
        c.username_pw_set(os.environ["BENCH_MQTT_USER"], os.environ.get("BENCH_MQTT_PASS", ""))
    c.reconnect_delay_set(1, 2)
    c.max_inflight_messages_set(100)
    return c


def raw_path(a, role):
    return pathlib.Path(f"{EXPROOT}/{a.exp}/raw/stage4_{a.test}_{a.broker}_{a.run}_{role}.json")


def role_sub(a):
    base = f"bench4/{a.test}/{a.run}"
    got, conn_log, lock = {}, [], threading.Lock()
    order_inv = [0, -1]

    def on_msg(c, u, m):
        now = time.time_ns()
        d = json.loads(m.payload)
        with lock:
            s = d["seq"]
            if s in got:
                got[s][1] += 1
            else:
                got[s] = [now, 1, (now - d["send_ns"]) / 1e6]
                if s < order_inv[1]:
                    order_inv[0] += 1
                order_inv[1] = max(order_inv[1], s)
        if a.slow_ms:
            time.sleep(a.slow_ms / 1000)

    def on_conn(c, u, f, rc, p=None):
        conn_log.append({"t": time.time(), "rc": str(rc), "session_present": bool(getattr(f, "session_present", False))})
        if rc == 0:
            c.subscribe(f"{base}/#", qos=1)

    def on_disc(c, u, f, rc, p=None):
        conn_log.append({"t": time.time(), "disconnect": str(rc)})
    cid = f"s4sub-{a.test}-{a.run}-{a.name}"
    c = mk(cid, a.broker, clean=False)
    c.on_message, c.on_connect, c.on_disconnect = on_msg, on_conn, on_disc
    c.connect_async(a.broker, 1883, keepalive=a.keepalive)
    c.loop_start()
    t0 = time.time()
    if a.offline_after:
        time.sleep(a.offline_after)
        c.loop_stop()
        c.disconnect()                      # 세션만 남기고 오프라인(깨끗한 끊김)
        conn_log.append({"t": time.time(), "offline": True})
        while time.time() - t0 < a.online_at:
            time.sleep(0.2)
        c = mk(cid, a.broker, clean=False)
        c.on_message, c.on_connect, c.on_disconnect = on_msg, on_conn, on_disc
        c.connect_async(a.broker, 1883, keepalive=a.keepalive)
        c.loop_start()
    while time.time() - t0 < a.duration:
        time.sleep(0.5)
    c.loop_stop()
    c.disconnect()
    with lock:
        rows = sorted((s, v[0], v[1], v[2]) for s, v in got.items())
    res = {"role": "sub", "name": a.name, "slow_ms": a.slow_ms, "unique": len(rows),
           "duplicates": sum(r[2] - 1 for r in rows), "order_inversions": order_inv[0], "connections": conn_log,
           "seq": [r[0] for r in rows], "recv_ns": [r[1] for r in rows], "lat_ms": [round(r[3], 2) for r in rows],
           "t0": t0, "t1": time.time()}
    raw_path(a, f"sub-{a.name}").write_text(json.dumps(res), encoding="utf-8")
    print(json.dumps({k: res[k] for k in ("role", "name", "unique", "duplicates", "order_inversions")}), flush=True)


def role_pub(a):
    base = f"bench4/{a.test}/{a.run}"
    ok = threading.Event()
    acks = [0]
    c = mk(f"s4pub-{a.test}-{a.run}", a.broker, clean=True)
    c.max_queued_messages_set(0)            # paho 기본(무제한) — 단절 중 발행자 쪽 보관
    c.on_connect = lambda cl, u, f, rc, p=None: ok.set() if rc == 0 else None
    c.on_publish = lambda cl, u, mid, rc=None, p=None: acks.__setitem__(0, acks[0] + 1)
    c.connect_async(a.broker, 1883, keepalive=a.keepalive)
    c.loop_start()
    t = time.time()
    while not ok.is_set() and time.time() - t < 60:
        time.sleep(0.05)
    time.sleep(a.start_delay)
    n = int(a.rate * a.duration)
    pad = "x" * a.pad
    t0 = time.time()
    rc_fail = 0
    for seq in range(n):
        d = t0 + seq / a.rate - time.time()
        if d > 0:
            time.sleep(d)
        info = c.publish(f"{base}/plant/{TAGS[seq % 12]}", json.dumps({"seq": seq, "send_ns": time.time_ns(), "pad": pad}), qos=1)
        if info.rc not in (mqtt.MQTT_ERR_SUCCESS, mqtt.MQTT_ERR_NO_CONN):
            rc_fail += 1
    t1 = time.time()
    deadline = time.time() + a.ack_wait
    while acks[0] < n and time.time() < deadline:
        time.sleep(0.5)
    c.loop_stop()
    c.disconnect()
    res = {"role": "pub", "sent": n, "acked": acks[0], "publish_rc_fail": rc_fail, "rate": a.rate,
           "duration": a.duration, "t0": t0, "t1": t1, "achieved_rate": round(n / max(1e-9, t1 - t0), 1)}
    raw_path(a, "pub").write_text(json.dumps(res), encoding="utf-8")
    print(json.dumps(res), flush=True)


def mem_trend(stats_csv, pattern):
    """sample_stats CSV 에서 브로커 컨테이너 메모리: 처음·마지막 5분 중앙값과 시간당 증가량(MiB/h)."""
    rows = []
    try:
        with open(stats_csv, encoding="utf-8") as fh:
            for r in csv.DictReader(fh):
                if pattern in r["name"]:
                    rows.append((int(r["t_epoch"]), float(r["mem_mib"]), float(r["cpu_pct"])))
    except (OSError, ValueError, KeyError):
        return None
    if len(rows) < 20:
        return {"samples": len(rows)}
    t0, t1 = rows[0][0], rows[-1][0]
    head = [m for t, m, _ in rows if t < t0 + 300]
    tail = [m for t, m, _ in rows if t > t1 - 300]
    n = len(rows)
    mt = sum(t for t, _, _ in rows) / n
    mm = sum(m for _, m, _ in rows) / n
    var = sum((t - mt) ** 2 for t, _, _ in rows)
    slope = sum((t - mt) * (m - mm) for t, m, _ in rows) / var if var else 0.0
    return {"samples": n, "mem_mib_first5min_median": round(statistics.median(head), 1),
            "mem_mib_last5min_median": round(statistics.median(tail), 1), "mem_mib_max": round(max(m for _, m, _ in rows), 1),
            "mem_growth_mib_per_h(linear)": round(slope * 3600, 2),
            "cpu_pct_median": round(statistics.median(c for _, _, c in rows), 2), "cpu_pct_p95": pct([c for _, _, c in rows], .95)}


def role_analyze(a):
    rawdir = pathlib.Path(f"{EXPROOT}/{a.exp}/raw")
    pub = json.loads(raw_path(a, "pub").read_text(encoding="utf-8"))
    out = {"test": a.test, "broker": a.broker, "run": a.run, "pub": pub, "subs": {}}
    events = []
    ev_file = rawdir / f"stage4_{a.test}_{a.broker}_{a.run}_events.txt"
    if ev_file.exists():
        for line in ev_file.read_text().splitlines():
            p = line.split(maxsplit=1)
            if len(p) == 2:
                events.append({"t": float(p[0]), "what": p[1]})
    out["events"] = events
    for f in sorted(rawdir.glob(f"stage4_{a.test}_{a.broker}_{a.run}_sub-*.json")):
        s = json.loads(f.read_text(encoding="utf-8"))
        seqs, recv, lat = s["seq"], s["recv_ns"], s["lat_ms"]
        arr = sorted(recv)
        gaps = [(y - x) / 1e9 for x, y in zip(arr, arr[1:])]
        sset = set(seqs)
        lost = [q for q in range(pub["sent"]) if q not in sset]
        r = {"unique": len(seqs), "lost": len(lost), "duplicates": s["duplicates"], "order_inversions": s["order_inversions"],
             "lost_first_last": [lost[0], lost[-1]] if lost else None,
             "lost_ranges_sample": _ranges(lost)[:10],
             "latency_ms": {"p50": pct(lat, .5), "p95": pct(lat, .95), "p99": pct(lat, .99), "max": pct(lat, 1)},
             "max_gap_s": round(max(gaps), 2) if gaps else None,
             "drain_after_pub_end_s": round(arr[-1] / 1e9 - pub["t1"], 2) if arr else None,
             "connections": s["connections"], "slow_ms": s["slow_ms"]}
        # 사건(단절 복구 등) 이후 첫 수신·적체 해소
        for ev in events:
            if ev["what"].startswith(("reconnect", "unpause", "start")):
                after = [x / 1e9 for x in arr if x / 1e9 >= ev["t"]]
                r.setdefault("after_events", []).append({"event": ev["what"], "first_recv_s": round(after[0] - ev["t"], 2) if after else None})
        out["subs"][s["name"]] = r
    if a.stats:
        out["broker_resources"] = mem_trend(a.stats, f"brokerbench-{a.broker}")
    dest = pathlib.Path(f"{EXPROOT}/{a.exp}/stage4_{a.test}_{a.broker}_{a.run}.json")
    dest.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({n: {k: v[k] for k in ("unique", "lost", "duplicates", "latency_ms", "drain_after_pub_end_s")} for n, v in out["subs"].items()},
                     ensure_ascii=False), flush=True)


def _ranges(xs):
    out, start, prev = [], None, None
    for x in xs:
        if start is None:
            start = prev = x
        elif x == prev + 1:
            prev = x
        else:
            out.append([start, prev])
            start = prev = x
    if start is not None:
        out.append([start, prev])
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--role", required=True, choices=["sub", "pub", "analyze"])
    ap.add_argument("--broker", required=True)
    ap.add_argument("--test", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--exp", default="EXP-130")
    ap.add_argument("--name", default="main", help="sub 이름(여러 구독자 구분)")
    ap.add_argument("--rate", type=float, default=120)
    ap.add_argument("--duration", type=float, default=60)
    ap.add_argument("--start-delay", type=float, default=3, help="pub: 구독자 준비 대기")
    ap.add_argument("--ack-wait", type=float, default=120)
    ap.add_argument("--pad", type=int, default=0, help="페이로드 덧붙임 바이트(V1 EdgeX 이벤트 ≈1.9 kB 흉내 시)")
    ap.add_argument("--keepalive", type=int, default=60, help="paho 기본 60 — 반쯤 열린 연결 감지 시간에 영향")
    ap.add_argument("--slow-ms", type=float, default=0)
    ap.add_argument("--offline-after", type=float, default=0)
    ap.add_argument("--online-at", type=float, default=0)
    ap.add_argument("--stats", default="")
    a = ap.parse_args()
    pathlib.Path(f"{EXPROOT}/{a.exp}/raw").mkdir(parents=True, exist_ok=True)
    if a.role != "analyze":
        p = raw_path(a, "pub" if a.role == "pub" else f"sub-{a.name}")
        if p.exists():
            raise SystemExit(f"{p} 이미 있음 — 새 run ID 로")
    {"sub": role_sub, "pub": role_pub, "analyze": role_analyze}[a.role](a)


if __name__ == "__main__":
    main()
