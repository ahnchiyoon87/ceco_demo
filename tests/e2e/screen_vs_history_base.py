"""[측정 도구] 새 베이스 E7 화면 값 = 이력 값(V1 screen_vs_history.py 와 같은 판정: 태그 계측 잡음 σ × 3).
V1 은 FUXA 가 시뮬레이터 레지스터를 직접 읽어 /state 를 화면 값으로 썼다. 새 베이스의 FUXA 는 OT 허브 UNS 를 구독하므로
FUXA 자신의 현재 값(/api/daq, from==to)을 화면 값으로 잡고, 같은 시각의 이력 두 곳과 비교한다.
  ① DMZ InfluxDB 원시 사본(process_raw) — V1 의 "화면 대 외부 이력"과 같은 자리
  ② FUXA DAQ(OT 이력, SQLite)
DMZ 이력 값 = 화면 값을 FUXA 가 받은 시각(/api/daq 현재 값의 ts) 이전의 마지막 기록. 화면은 마지막으로 받은 값을 보이므로
그 값이 만들어진 기록과 같은 기록을 고른다(읽은 시각으로 고르면 DMZ 에는 들어갔지만 화면에는 아직 오는 중인 다음 표본이 잡힌다,
09-30 첫 실행 115/120 의 원인).
  base_client python tests/e2e/screen_vs_history_base.py --n 60 --out /repo/experiments/<EXP>/raw/e7_base.json
"""
import argparse, csv, json, os, re, time, urllib.parse, urllib.request
from datetime import datetime

ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True); ap.add_argument("--n", type=int, default=60)
ap.add_argument("--fuxa", default="http://fuxa:1881"); ap.add_argument("--influx", default="http://dmz-influx:8086")
a = ap.parse_args()
block = open("0_plant/simulator/plant.yaml", encoding="utf-8").read().split("\nnoise:", 1)[1].split("\n# ", 1)[0]
noise = {k: float(v) for k, v in re.findall(r"^\s+([A-Za-z]+-\d+):\s*([0-9.]+)", block, re.M)}
TAGS = list(noise)                                   # 12 계측 태그
FID = {t: t.replace("-", "_") for t in TAGS}         # FUXA 태그 id(2_ot/hmi-fuxa/build_project.py)


def fuxa_daq(t_from, t_to):
    q = json.dumps({"sids": [FID[t] for t in TAGS], "from": t_from, "to": t_to})
    return json.load(urllib.request.urlopen(f"{a.fuxa}/api/daq?" + urllib.parse.urlencode({"query": q}), timeout=10))


def influx_before(at_ms: dict):
    """태그별로 at_ms[tag] 이전(포함) 마지막 원시 기록 값."""
    lo, hi = min(at_ms.values()) - 3000, max(at_ms.values()) + 1
    q = (f'from(bucket:"{os.environ["DMZ_INFLUX_BUCKET"]}") |> range(start:time(v:{lo * 1_000_000}), stop:time(v:{hi * 1_000_000}))'
         ' |> filter(fn:(r)=>r._measurement=="process_raw" and r._field=="value") |> keep(columns:["_time","tag","_value"])')
    r = urllib.request.Request(a.influx + "/api/v2/query?" + urllib.parse.urlencode({"org": os.environ["INFLUX_ORG"]}),
                               json.dumps({"query": q, "type": "flux"}).encode(),
                               {"Authorization": "Token " + os.environ["DMZ_INFLUX_TOKEN"], "Content-Type": "application/json", "Accept": "application/csv"})
    best = {}
    for rec in csv.DictReader([l for l in urllib.request.urlopen(r, timeout=10).read().decode().splitlines() if l and not l.startswith("#")]):
        tag = rec.get("tag")
        if tag in at_ms and rec.get("_value") not in (None, "_value"):
            t = datetime.fromisoformat(rec["_time"].replace("Z", "+00:00")).timestamp() * 1000
            if t <= at_ms[tag] and (tag not in best or t > best[tag][0]):
                best[tag] = (t, float(rec["_value"]))
    return {t: v for t, (_, v) in best.items()}


samples = []
for i in range(a.n):
    t_ms = int(time.time() * 1000)
    cur = fuxa_daq(t_ms, t_ms)                      # 현재 값: [[{id, value, ts}], ...]
    screen, at = {}, {}
    for t, row in zip(TAGS, cur):
        v = (row or [{}])[0] or {}
        if v.get("value") is not None:
            screen[t], at[t] = float(v["value"]), int(v.get("ts") or t_ms)
    time.sleep(8)                                   # 이력 경로 도착 대기 뒤 조회
    hist = influx_before(at)
    daq = {}
    # FUXA DAQ 는 받은 값을 1 s 주기로 저장한다 → 화면 값의 기록 = 받은 시각 이후 첫 저장(없으면 그 직전 저장)
    for t, rows in zip(TAGS, fuxa_daq(t_ms - 3000, t_ms + 3000)):
        rows = rows or []
        after = [r for r in rows if r.get("dt", 0) >= at.get(t, t_ms)]
        before = [r for r in rows if r.get("dt", 0) < at.get(t, t_ms)]
        pick = min(after, key=lambda r: r["dt"]) if after else (max(before, key=lambda r: r["dt"]) if before else None)
        if pick:
            daq[t] = float(pick["value"])
    for t, v in screen.items():
        tol = 3 * noise.get(t, 0.05) + 1e-6
        samples.append({"tag": t, "screen": v, "dmz_influx": hist.get(t), "fuxa_daq": daq.get(t),
                        "ok_influx": t in hist and abs(v - hist[t]) <= tol, "ok_daq": t in daq and abs(v - daq[t]) <= tol})
    time.sleep(1)
n = len(samples)
out = {"pairs": n, "influx_within": sum(s["ok_influx"] for s in samples), "daq_within": sum(s["ok_daq"] for s in samples)}
out |= {"rate_influx": round(out["influx_within"] / n, 4) if n else None, "rate_daq": round(out["daq_within"] / n, 4) if n else None,
        "samples": samples}
json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: out[k] for k in ("pairs", "influx_within", "rate_influx", "daq_within", "rate_daq")}))
