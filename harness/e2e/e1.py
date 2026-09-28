"""[측정 도구 — 솔루션 부품 아님] E1 알람→화면 지연 (harness/situations/STRUCTURE.md E1).
구조(V1·A·C)마다 인자만 바꿔 같은 방법으로 잰다.

한 회: 고장 해제 → PT-101 알람이 조용해지고 인터록이 풀릴 때까지 대기 → 시뮬레이터 /fault 주입(시각 기록) →
      각 관측 지점에서 '주입 이후 첫 매칭 알람'을 받은 시각(이 프로세스의 수신 시각, 같은 시계).
관측 지점: --kafka-topic(선택, 중간 지점), --mqtt-topics(화면이 구독하는 토픽들, 쉼표).
  python /repo/harness/e2e/e1.py --exp EXP-000 --run e1a --reps 100 --sim http://plant-simulator:8080 \
     --mqtt emqx --kafka kafka:9092 --kafka-topic sensor.alerts \
     --mqtt-topics scada/alerts/PT-101,scada/hmi/latest-alert --match THRESHOLD_USL
"""
import argparse
import json
import pathlib
import statistics
import threading
import time
import urllib.request
import uuid

import paho.mqtt.client as mqtt


def http(url, body=None):
    req = urllib.request.Request(url, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"},
                                 method="POST" if body is not None else "GET")
    return json.load(urllib.request.urlopen(req, timeout=10))


def pct(v, q):
    v = sorted(v)
    return round(v[min(len(v) - 1, int(round(q / 100 * (len(v) - 1))))], 1) if v else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--reps", type=int, default=100)
    ap.add_argument("--sim", required=True)
    ap.add_argument("--mqtt", required=True)
    ap.add_argument("--mqtt-topics", required=True)
    ap.add_argument("--kafka")
    ap.add_argument("--kafka-topic")
    ap.add_argument("--match", default="THRESHOLD_USL")
    ap.add_argument("--tag", default="PT-101")
    ap.add_argument("--scenario", default="spike")
    ap.add_argument("--quiet-s", type=float, default=6.0)
    ap.add_argument("--timeout-s", type=float, default=60.0)
    ap.add_argument("--fault-duration", type=float, default=None, help="스파이크 지속(시뮬레이터 초). 지연 측정값에 영향 없음, 회차 단축용")
    ap.add_argument("--incident-api", default=None, help="AI 사건 목록 API(선택): 새 사건 생성 시각을 'incident' 지점으로 기록")
    a = ap.parse_args()
    raw = pathlib.Path(f"/experiments/{a.exp}/raw")
    raw.mkdir(parents=True, exist_ok=True)
    out = raw / f"e1_{a.run}.json"
    if out.exists():
        raise SystemExit(f"실행 ID 재사용 금지: {out}")

    lock = threading.Lock()
    events = []                                   # (지점, 수신 wall ms)

    def hit(point, text):
        if a.tag in text and a.match in text:
            with lock:
                events.append((point, time.time() * 1000))

    topics = a.mqtt_topics.split(",")
    m = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"e1-{uuid.uuid4().hex[:6]}")
    m.on_connect = lambda c, u, f, rc, p=None: [c.subscribe(t, qos=1) for t in topics]
    m.on_message = lambda c, u, msg: hit("mqtt:" + msg.topic, msg.payload.decode(errors="replace"))
    m.connect(a.mqtt, 1883)
    m.loop_start()

    if a.kafka and a.kafka_topic:
        from confluent_kafka import Consumer
        kc = Consumer({"bootstrap.servers": a.kafka, "group.id": f"e1-{uuid.uuid4().hex[:6]}",
                       "auto.offset.reset": "latest"})
        kc.subscribe([a.kafka_topic])

        def kloop():
            while True:
                msg = kc.poll(0.2)
                if msg is not None and not msg.error():
                    hit("kafka:" + a.kafka_topic, msg.value().decode(errors="replace"))
        threading.Thread(target=kloop, daemon=True).start()
    time.sleep(5)

    points = ([f"kafka:{a.kafka_topic}"] if a.kafka_topic else []) + [f"mqtt:{t}" for t in topics] + (["incident"] if a.incident_api else [])
    if a.incident_api:
        seen = {i["id"] for i in http(a.incident_api)["items"]}

        def iloop():
            while True:
                try:
                    for i in http(a.incident_api)["items"]:
                        if i["id"] not in seen:
                            seen.add(i["id"])
                            if a.tag in json.dumps(i["alarm"]) and a.match in json.dumps(i["alarm"]):
                                with lock:
                                    events.append(("incident", time.time() * 1000))
                except Exception:
                    pass
                time.sleep(0.2)
        threading.Thread(target=iloop, daemon=True).start()
    reps = []
    for i in range(a.reps):
        http(a.sim + "/fault/clear", {})
        t_wait = time.time()
        while True:                                # 직전 회차 잔여 알람·인터록이 끝날 때까지
            with lock:
                last = max((ts for _, ts in events), default=0)
            if time.time() * 1000 - last >= a.quiet_s * 1000 and not http(a.sim + "/state").get("interlock"):
                break
            if time.time() - t_wait > 120:
                break
            time.sleep(0.5)
        t0 = time.time() * 1000
        http(a.sim + "/fault", {"scenario": a.scenario} | ({"duration_s": a.fault_duration} if a.fault_duration else {}))
        got = {}
        while time.time() * 1000 - t0 < a.timeout_s * 1000 and len(got) < len(points):
            with lock:
                for p, ts in events:
                    if ts >= t0 and p not in got:
                        got[p] = round(ts - t0, 1)
            time.sleep(0.05)
        reps.append({"i": i, "t0_ms": t0, "lat_ms": got, "missing": [p for p in points if p not in got]})
        print(i, json.dumps(got), flush=True)
    http(a.sim + "/fault/clear", {})

    summary = {}
    for p in points:
        v = [r["lat_ms"][p] for r in reps if p in r["lat_ms"]]
        summary[p] = {"n": len(v), "missing": a.reps - len(v), "p50": pct(v, 50), "p95": pct(v, 95),
                      "max": max(v) if v else None, "mean": round(statistics.mean(v), 1) if v else None}
    res = {"run": a.run, "reps": a.reps, "args": vars(a), "summary": summary, "reps_detail": reps}
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()
