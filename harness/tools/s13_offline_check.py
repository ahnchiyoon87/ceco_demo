"""S13 사전 점검(오프라인): Python 이식(ml.OnnxScorer)을 틱 단위로 직접 구동해 참조 수식과 비교. Kafka 불필요."""
import json
import sys

sys.path.insert(0, "/repo/candidates/l4-python")
sys.path.insert(0, "/repo/harness/tools")
import ml  # noqa: E402
import s13  # noqa: E402

meta = json.load(open(s13.META, encoding="utf-8"))
tags = meta["tags"]
wins = []
for si, sc in enumerate(s13.SEGMENTS):
    rows = s13.series(sc, 13 + si, tags)
    wins += [rows[20 + k * 4:30 + k * 4] for k in range(25)]
ref = s13.reference(wins, meta)
sc = ml.OnnxScorer(s13.MODEL, s13.META)
got = []
for k, w in enumerate(wins):
    dev = f"w{k}"
    now = 0
    for j, row in enumerate(w):
        for t, v in zip(tags, row):
            sc.process({"device": dev, "tag": t, "value": v, "site": "EXP"}, now)
        now += 1000
        s, _ = sc.fire_due(now)
        if s:
            got.append(s[0]["reconstruction_error"])
d = [abs(a - b) for a, b in zip(got, ref)]
print(json.dumps({"n_ref": len(ref), "n_got": len(got), "max_abs_diff": max(d), "ref_min": min(ref), "ref_max": max(ref),
                  "anomalies": sum(x > meta["threshold"] for x in ref), "threshold": meta["threshold"]}))
