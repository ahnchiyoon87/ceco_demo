"""S13 진단: 후보별로 장치당 점수 수열 전체에서 참조값이 어디(몇 번째 틱)에 나타나는지 본다. 판정 도구 아님.
  python /repo/harness/tools/s13_inspect.py --exp EXP-L4 --run s13_2
"""
import argparse
import collections
import json
import pathlib
import sys

sys.path.insert(0, "/repo/harness/tools")
from s13 import read_topic  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--exp", required=True)
ap.add_argument("--run", required=True)
ap.add_argument("--cands", default="flinksql,flink22,cep,python")
a = ap.parse_args()
raw = pathlib.Path(f"/experiments/{a.exp}/raw")
res = json.loads((raw / f"s13_{a.run}.json").read_text(encoding="utf-8"))
ref = json.loads((raw / f"s13_{a.run}_ref.json").read_text(encoding="utf-8"))
prefix = f"{a.run}.{res['token']}-"
refmap = dict(zip(ref["devices"], ref["ref"]))
out = {}
for c in a.cands.split(","):
    seqs = collections.defaultdict(list)
    for kts, s in read_topic(f"exp.l4.score.{c}", prefix):
        seqs[s["device"]].append((s["ts"], kts, s["reconstruction_error"]))
    pos = collections.Counter()
    for dev, r in refmap.items():
        seq = [x[2] for x in sorted(seqs.get(dev, []))]
        hit = next((i for i, v in enumerate(seq) if abs(v - r) <= 1e-6), None)
        pos["none" if hit is None else hit] += 1
    d0 = sorted(seqs)[0] if seqs else None
    first_ts = [sorted(v)[0][0] for v in seqs.values()]
    out[c] = {"devices_scored": len(seqs), "ref_hit_tick_index": dict(pos),
              "sample_device": d0, "sample_seq_head": [round(x[2], 6) for x in sorted(seqs[d0])[:6]] if d0 else None,
              "sample_ref": refmap.get(d0),
              "first_score_span_ms": (max(first_ts) - min(first_ts)) / 1e6 if first_ts else None}
    print(c, json.dumps(out[c], ensure_ascii=False), flush=True)
