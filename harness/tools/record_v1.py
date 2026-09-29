"""[측정 도구 — 솔루션 부품 아님] V1 이 실제로 흘린 데이터를 파일로 한 번 기록한다(층별 후보 재생 입력, HANDOFF §3 §1 시험 범위).

rot-iiot 망에서 실행. 정상 --normal-s 초 뒤 고장을 하나씩 주입(--fault-s 초 유지 → 해제 → --gap-s 초)하며
MQTT edgex/telemetry(EdgeX 이벤트 원문)와 Kafka 토픽(raw·clean·alerts·anomaly)을 받은 그대로 기록한다.
  docker run --rm --network rot-iiot --env-file .env -v "$PWD:/repo" -w /repo e2e-client:1.0 \
     python harness/tools/record_v1.py --out experiments/REC-V1
출력: <out>/mqtt_edgex_telemetry.jsonl · kafka_<topic>.jsonl({"rx": 수신 epoch 초, "key", "value"(원문 문자열)}),
      <out>/timeline.json(주입 시각표), <out>/manifest.json(건수·구간).
"""
import argparse, json, pathlib, threading, time, urllib.request, uuid
import paho.mqtt.client as mqtt
from confluent_kafka import Consumer

SIM = "http://plant-simulator:8080"
TOPICS = ["sensor.telemetry.raw", "sensor.telemetry.clean", "sensor.alerts", "sensor.anomaly.score"]
FAULTS = ["spike", "heater_stuck", "bearing_wear", "noise", "dropout", "drift", "cooling_loss"]


def http(url, body=None):
    r = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None,
                               {"Content-Type": "application/json"}, method="POST" if body is not None else "GET")
    return json.load(urllib.request.urlopen(r, timeout=10))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", required=True)
    ap.add_argument("--normal-s", type=int, default=60)
    ap.add_argument("--fault-s", type=int, default=20)
    ap.add_argument("--gap-s", type=int, default=10)
    a = ap.parse_args()
    out = pathlib.Path(a.out); out.mkdir(parents=True, exist_ok=True)
    stop = threading.Event(); lock = threading.Lock(); counts = {}
    files = {}

    def write(name, rec):
        with lock:
            if name not in files:
                files[name] = open(out / f"{name}.jsonl", "w", encoding="utf-8")
            files[name].write(json.dumps(rec, ensure_ascii=False) + "\n")
            counts[name] = counts.get(name, 0) + 1

    kc = Consumer({"bootstrap.servers": "kafka:9092", "group.id": f"rec-{uuid.uuid4().hex[:6]}", "auto.offset.reset": "latest"})
    existing = set(kc.list_topics(timeout=10).topics)
    topics = [t for t in TOPICS if t in existing]
    kc.subscribe(topics)

    def kloop():
        while not stop.is_set():
            m = kc.poll(0.2)
            if m is None or m.error():
                continue
            write("kafka_" + m.topic(), {"rx": time.time(), "ts_ms": m.timestamp()[1], "partition": m.partition(),
                                         "key": m.key().decode() if m.key() else None, "value": m.value().decode()})
    threading.Thread(target=kloop, daemon=True).start()

    mc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"rec-{uuid.uuid4().hex[:6]}")
    mc.on_connect = lambda c, u, f, rc, p=None: c.subscribe([("edgex/telemetry", 1), ("scada/alerts/+", 1), ("scada/hmi/latest-alert", 1)])
    mc.on_message = lambda c, u, m: write("mqtt_" + m.topic.split("/")[0] + "_" + m.topic.split("/")[1].replace("+", ""),
                                          {"rx": time.time(), "topic": m.topic, "value": m.payload.decode(errors="replace")})
    mc.connect("emqx", 1883); mc.loop_start()
    time.sleep(5)

    timeline = []
    t_start = time.time()
    http(SIM + "/fault/clear", {})
    time.sleep(a.normal_s)
    for f in FAULTS:
        t = time.time(); http(SIM + "/fault", {"scenario": f}); time.sleep(a.fault_s)
        http(SIM + "/fault/clear", {}); t_end = time.time()
        timeline.append({"fault": f, "start": t, "clear": t_end})
        print(f, "기록", flush=True)
        time.sleep(a.gap_s)
    stop.set(); time.sleep(1); mc.loop_stop()
    with lock:
        for fh in files.values():
            fh.close()
    (out / "timeline.json").write_text(json.dumps({"start": t_start, "end": time.time(), "faults": timeline}, indent=1), encoding="utf-8")
    (out / "manifest.json").write_text(json.dumps({"topics": topics, "counts": counts, "seconds": round(time.time() - t_start, 1)},
                                                  ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(counts, ensure_ascii=False))


if __name__ == "__main__":
    main()
