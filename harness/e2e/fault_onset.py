"""[측정 도구] 고장 주입 → 첫 알람 도착 시간(시연·실습 기준: 10초 이하, #88). rot-iiot 망에서 실행.
고장마다 기대 알람(태그·유형)을 Kafka sensor.alerts 와 FUXA 가 구독하는 MQTT 토픽에서 기다린다.
  python harness/e2e/fault_onset.py --reps 3 --out experiments/EXP-000/raw/onset_x.json
"""
import argparse, json, threading, time, urllib.request, uuid
import paho.mqtt.client as mqtt
from confluent_kafka import Consumer

# 고장 → (기대 알람을 가르는 조건) : V1 규칙(flink/sql)이 만드는 알람. cooling_loss 는 냉각 명령이 켜진 경우만 의미가 있어 제외.
EXPECT = {
    "spike":        lambda a: a["tag"] == "PT-101" and a["alert_type"] == "THRESHOLD_USL",
    "heater_stuck": lambda a: a["tag"] == "TT-101" and a["alert_type"] == "THRESHOLD_USL",
    "bearing_wear": lambda a: a["tag"] == "VT-101" and a["alert_type"] == "CEP_BEARING",
    "noise":        lambda a: a["tag"] == "TT-101" and a["alert_type"] == "ZSCORE",
    "dropout":      lambda a: a["tag"] == "TT-101" and a.get("quality") not in (None, "GOOD"),  # V1 은 결측에 알람 대신 보간 → clean 토픽의 비-GOOD 레코드
    "drift":        lambda a: a["alert_type"] == "ML_AUTOENCODER",
}
SIM = "http://plant-simulator:8080"


def http(url, body=None):
    r = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None, {"Content-Type": "application/json"},
                               method="POST" if body is not None else "GET")
    return json.load(urllib.request.urlopen(r, timeout=10))


ap = argparse.ArgumentParser(); ap.add_argument("--reps", type=int, default=3); ap.add_argument("--out", required=True)
ap.add_argument("--limit-s", type=float, default=12.0)
ap.add_argument("--faults", default=",".join(EXPECT))
ap.add_argument("--broker", default="emqx")                    # V2: mqtt
ap.add_argument("--mqtt-topic", default="scada/alerts/#")      # V2: scada/hmi/latest-alert (FUXA 가 구독하는 글자 형식)
a = ap.parse_args()
lock, events = threading.Lock(), []
kc = Consumer({"bootstrap.servers": "kafka:9092", "group.id": f"onset-{uuid.uuid4().hex[:6]}", "auto.offset.reset": "latest"})
kc.subscribe(["sensor.alerts", "sensor.telemetry.clean"])


def kloop():
    while True:
        m = kc.poll(0.1)
        if m is not None and not m.error():
            try:
                al = json.loads(m.value())
                if m.topic() == "sensor.telemetry.clean" and al.get("quality") == "GOOD":
                    continue
                with lock:
                    events.append(("kafka", time.time(), al))
            except ValueError:
                pass
threading.Thread(target=kloop, daemon=True).start()
mc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"onset-{uuid.uuid4().hex[:6]}")
mc.on_connect = lambda c, u, f, rc, p=None: c.subscribe(a.mqtt_topic, 1)
def on_mqtt(c, u, msg):
    try:
        d = json.loads(msg.payload)                       # Telegraf JSON: {"tags": {...}, "fields": {...}, "timestamp": ns}
        al = {**d.get("tags", {}), **d.get("fields", {}), "ts": d.get("timestamp")}
    except ValueError:                                    # 최근알람 글자 형식 "MM-DD HH:MM:SS UTC | 심각도 | 태그 | 유형"
        parts = [x.strip() for x in msg.payload.decode(errors="replace").split("|")]
        if len(parts) < 4:
            return
        al = {"tag": parts[2], "alert_type": parts[3], "severity": parts[1], "ts": time.time_ns()}
    with lock:
        events.append(("mqtt", time.time(), al))
mc.on_message = on_mqtt
mc.connect(a.broker, 1883); mc.loop_start(); time.sleep(5)

results = {}
for fault, match in [(f, EXPECT[f]) for f in a.faults.split(",")]:
    lat = []
    limit = a.limit_s
    for i in range(a.reps):
        http(SIM + "/fault/clear", {}); time.sleep(3)
        t0 = time.time(); http(SIM + "/fault", {"scenario": fault})
        got = {}
        while time.time() - t0 < limit and len(got) < 2:
            with lock:
                for src, ts, al in events:
                    ev_s = (al.get("ts") or 0) / 1e9 if isinstance(al, dict) else 0
                    if ts >= t0 and ev_s >= t0 - 1.0 and src not in got and isinstance(al, dict) and "tag" in al and match(al):
                        got[src] = round(ts - t0, 2)
            time.sleep(0.05)
        lat.append(got)
        print(fault, i, got, flush=True)
    http(SIM + "/fault/clear", {})
    k = [g["kafka"] for g in lat if "kafka" in g]; m = [g["mqtt"] for g in lat if "mqtt" in g]
    results[fault] = {"reps": lat, "kafka_max_s": max(k) if k else None, "mqtt_max_s": max(m) if m else None,
                      "missing": sum(1 for g in lat if "kafka" not in g),
                      "within_10s": bool(k) and len(k) == a.reps and max(k) <= 10 and (fault == "dropout" or (len(m) == a.reps and max(m) <= 10))}
    time.sleep(1)
out = {"limit_s": a.limit_s, "results": results, "all_within_10s": all(r["within_10s"] for r in results.values()),
       "physics_time_scale": http(SIM + "/state").get("physics_time_scale")}
json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({f: (r["kafka_max_s"], r["mqtt_max_s"], r["within_10s"]) for f, r in results.items()}, ensure_ascii=False), out["all_within_10s"])
