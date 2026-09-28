"""[측정 도구] E7 화면 값 = 이력 값. FUXA 는 시뮬레이터 레지스터를 직접 폴링하므로 같은 원천(/state)과
InfluxDB process_raw 의 같은 초 값을 태그별로 60회 비교. 허용오차 = 태그 계측 잡음 σ × 3 (simulator/plant.yaml)."""
import argparse, json, os, re, time, urllib.parse, urllib.request
from datetime import datetime

ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--n", type=int, default=60); a = ap.parse_args()
block = open("simulator/plant.yaml", encoding="utf-8").read().split("\nnoise:", 1)[1].split("\n# ", 1)[0]
noise = {k: float(v) for k, v in re.findall(r"^\s+([A-Za-z]+-\d+):\s*([0-9.]+)", block, re.M)}
def influx(t_ns):
    q = (f'from(bucket:"{os.environ["INFLUX_BUCKET"]}") |> range(start:time(v:{t_ns - 1_500_000_000}), stop:time(v:{t_ns + 1_500_000_000})) '
         '|> filter(fn:(r)=>r._measurement=="process_raw" and r._field=="value") |> keep(columns:["_time","tag","_value"])')
    r = urllib.request.Request("http://influxdb:8086/api/v2/query?" + urllib.parse.urlencode({"org": os.environ["INFLUX_ORG"]}),
        json.dumps({"query": q, "type": "flux"}).encode(), {"Authorization": "Token " + os.environ["INFLUX_TOKEN"], "Content-Type": "application/json", "Accept": "application/csv"})
    rows = {}
    import csv
    for rec in csv.DictReader([l for l in urllib.request.urlopen(r, timeout=10).read().decode().splitlines() if l and not l.startswith("#")]):
        if rec.get("tag") and rec.get("_value") not in (None, "_value"):
            ts = datetime.fromisoformat(rec["_time"].replace("Z", "+00:00")).timestamp() * 1e9
            rows.setdefault(rec["tag"], []).append((abs(ts - t_ns), float(rec["_value"])))
    return {t: min(v)[1] for t, v in rows.items()}
samples = []
for i in range(a.n):
    st = json.load(urllib.request.urlopen("http://plant-simulator:8080/state", timeout=5)); t = time.time_ns()
    time.sleep(8)  # 이력 경로(약 수 초) 도착 대기 후 같은 시각 조회
    hist = influx(t)
    for tag, v in st["readings"].items():
        if tag in hist:
            samples.append({"tag": tag, "screen": v, "history": hist[tag], "ok": abs(v - hist[tag]) <= 3 * noise.get(tag, 0.05) + 1e-6})
    time.sleep(max(0, 1 - 0))
ok = sum(s["ok"] for s in samples)
out = {"pairs": len(samples), "within_tolerance": ok, "rate": round(ok / len(samples), 4) if samples else None, "samples": samples}
json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: out[k] for k in ("pairs", "within_tolerance", "rate")}))
