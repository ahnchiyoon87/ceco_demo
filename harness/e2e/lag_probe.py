"""[측정 도구] 재시작 중 1초마다 두 지점의 '가장 새 값이 현재보다 몇 초 늦었나'를 기록: Kafka raw 도착, InfluxDB process_raw.
  docker run --rm --network rot-iiot --env-file .env -v <repo>:/repo -w /repo e2e-client:1.0 python harness/e2e/lag_probe.py --seconds 70 --out <file>
"""
import argparse, json, os, threading, time, urllib.parse, urllib.request
from confluent_kafka import Consumer
ap = argparse.ArgumentParser(); ap.add_argument("--seconds", type=int, default=70); ap.add_argument("--out", required=True); a = ap.parse_args()
newest = {"kafka": 0.0}
def kloop():
    while True:
        try:
            c = Consumer({"bootstrap.servers": "kafka:9092", "group.id": f"probe-{time.time_ns()}", "auto.offset.reset": "latest"})
            c.subscribe(["sensor.telemetry.raw"])
            while True:
                m = c.poll(0.2)
                if m is not None and not m.error():
                    newest["kafka"] = max(newest["kafka"], json.loads(m.value())["ts"] / 1e9)
        except Exception:
            time.sleep(0.5)
threading.Thread(target=kloop, daemon=True).start()
def influx_newest():
    q = (f'from(bucket:"{os.environ["INFLUX_BUCKET"]}") |> range(start:-120s) '
         '|> filter(fn:(r)=>r._measurement=="process_raw" and r.tag=="TT-101") |> last() |> keep(columns:["_time"])')
    req = urllib.request.Request("http://influxdb:8086/api/v2/query?" + urllib.parse.urlencode({"org": os.environ["INFLUX_ORG"]}),
                                 json.dumps({"query": q, "type": "flux"}).encode(),
                                 {"Authorization": "Token " + os.environ["INFLUX_TOKEN"], "Content-Type": "application/json", "Accept": "application/csv"})
    try:
        rows = [l for l in urllib.request.urlopen(req, timeout=3).read().decode().splitlines() if l.startswith(",_result")]
        t = rows[-1].split(",")[-1].strip()
        import datetime
        return datetime.datetime.fromisoformat(t.replace("Z", "+00:00")).timestamp()
    except Exception:
        return None
rows = []; t0 = time.time()
while time.time() - t0 < a.seconds:
    now = time.time(); inf = influx_newest()
    rows.append({"t": round(now - t0, 1), "kafka_lag_s": round(now - newest["kafka"], 1) if newest["kafka"] else None,
                 "influx_lag_s": round(now - inf, 1) if inf else None})
    time.sleep(max(0, 1 - (time.time() - now)))
json.dump(rows, open(a.out, "w"), indent=0)
print(json.dumps(rows[::3]))
