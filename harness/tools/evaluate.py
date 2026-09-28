"""L4 판정: 알람 토픽에서 이번 실행(run) 장치의 알람을 모아 기대값(manifest)과 비교한다.

    python /repo/harness/tools/evaluate.py --exp EXP-141 --run r1 --alerts exp.l4.alerts.flinksql [--dropped TOPIC]

판정 기준은 replay 가 실행 전에 기록한 manifest.expected 뿐이다. 이 스크립트는 기준을 바꾸지 않는다.
지연 = 진동 주입 레코드 emit_ns → 알람 레코드 Kafka CreateTime (ms 해상도).
"""
import argparse
import collections
import json
import os
import pathlib
import time
import uuid

from confluent_kafka import Consumer


def read_all(topic, idle_s=8):
    c = Consumer({"bootstrap.servers": os.environ["BOOTSTRAP"], "group.id": f"eval-{uuid.uuid4()}",
                  "auto.offset.reset": "earliest", "enable.auto.commit": False})
    c.subscribe([topic])
    out, last = [], time.time()
    while time.time() - last < idle_s:
        m = c.poll(1.0)
        if m is None or m.error():
            continue
        last = time.time()
        out.append((m.timestamp()[1], json.loads(m.value())))
    c.close()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--alerts", required=True)
    ap.add_argument("--dropped")
    ap.add_argument("--only-cases", help="쉼표 구분. 지정하면 이 케이스만 판정(예: CEP 만 내는 후보는 S02 제외)")
    a = ap.parse_args()
    raw = pathlib.Path(f"/experiments/{a.exp}/raw")
    man = json.loads((raw / f"replay_{a.run}_manifest.json").read_text(encoding="utf-8"))
    emitted = [json.loads(l) for l in open(raw / f"replay_{a.run}_emitted.jsonl", encoding="utf-8")]
    vib_emit = {r["device"]: r["emit_ns"] for r in emitted if r["kind"] == "inject" and r["tag"] == "VT-101"}

    # manifest 에 적힌 장치 + 리플레이 시작 이후 기록된 알람만 센다 (이전 실행과 섞이지 않게)
    devices = set(man["expected"])
    since = man.get("t0_wall_ms", 0)
    alerts = [(ts, r) for ts, r in read_all(a.alerts) if r.get("device") in devices and ts >= since]
    (raw / f"alerts_{a.run}.jsonl").write_text("".join(json.dumps({"kafka_ts_ms": ts, **r}, ensure_ascii=False) + "\n"
                                                    for ts, r in alerts), encoding="utf-8")
    dropped = []
    if a.dropped:
        dropped = [r for ts, r in read_all(a.dropped) if r.get("device") in devices and ts >= since]

    by = collections.defaultdict(collections.Counter)
    first_cep_ms = {}
    for ts, r in alerts:
        by[r["device"]][r["alert_type"]] += 1
        if r["alert_type"] == "CEP_BEARING":
            first_cep_ms.setdefault(r["device"], ts)

    rows, lat = [], []
    only = set(a.only_cases.split(",")) if a.only_cases else None
    for device, e in sorted(man["expected"].items()):
        if only and e["case"] not in only:
            continue
        cep = by[device]["CEP_BEARING"]
        exp = e["expected_cep"]
        if e["case"] == "S02":
            verdict = "PASS" if by[device]["THRESHOLD_USL"] >= 1 else "FAIL"
        elif exp == "policy":
            verdict = f"RECORD(cep={cep}, dropped_logged={sum(1 for d in dropped if d['device'] == device)})"
        else:
            verdict = "PASS" if cep == exp else "FAIL"
        if device in first_cep_ms and device in vib_emit and e["case"] in ("S04", "S06a", "S08a", "S08b"):
            lat.append(first_cep_ms[device] - vib_emit[device] / 1e6)
        rows.append({"device": device, "case": e["case"], "expected_cep": exp, "cep": cep,
                     "types": dict(by[device]), "verdict": verdict})

    def pct(v, q):
        v = sorted(v)
        return round(v[min(len(v) - 1, int(round(q * (len(v) - 1))))], 1) if v else None

    summary = {
        "exp": a.exp, "run": a.run, "alerts_topic": a.alerts,
        "pass": sum(r["verdict"] == "PASS" for r in rows),
        "fail": sum(r["verdict"] == "FAIL" for r in rows),
        "record": [r for r in rows if r["verdict"].startswith("RECORD")],
        "cep_latency_ms": {"n": len(lat), "p50": pct(lat, .5), "p95": pct(lat, .95), "max": pct(lat, 1.0),
                           "note": "진동 주입 emit → 알람 Kafka CreateTime. 워터마크 5s 대기 포함"},
        "rows": rows,
    }
    (raw / f"result_{a.run}.json").write_text(json.dumps(summary, ensure_ascii=False, indent=1), encoding="utf-8")
    for r in rows:
        print(f"{r['case']:5} {r['device']:18} exp={str(r['expected_cep']):6} cep={r['cep']} {r['verdict']}")
    print("PASS", summary["pass"], "FAIL", summary["fail"], "latency", summary["cep_latency_ms"])


if __name__ == "__main__":
    main()
