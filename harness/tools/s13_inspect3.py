"""S13 진단 3: 입력이 멈춘 뒤 정상상태 점수(창 = 마지막 벡터 ×10)를 참조와 비교. 판정 도구 아님."""
import collections
import json
import pathlib
import sys

sys.path.insert(0, "/repo/harness/tools")
import s13  # noqa: E402

run = sys.argv[1]
raw = pathlib.Path("/experiments/EXP-L4/raw")
res = json.loads((raw / f"s13_{run}.json").read_text(encoding="utf-8"))
prefix = f"{run}.{res['token']}-"
meta = json.load(open(s13.META, encoding="utf-8"))
tags = meta["tags"]
wins = []
for si, sc in enumerate(s13.SEGMENTS):
    rows = s13.series(sc, 13 + si, tags)
    wins += [rows[20 + k * 4:30 + k * 4] for k in range(25)]
ref = s13.reference([[w[9]] * 10 for w in wins], meta)
for c in ["flinksql", "flink22", "cep", "python"]:
    d = collections.defaultdict(list)
    for _, s in s13.read_topic(f"exp.l4.score.{c}", prefix):
        d[s["device"]].append((s["ts"], s["reconstruction_error"]))
    diffs = [abs(sorted(d[f"{prefix}w{k:03d}"])[-1][1] - ref[k]) for k in range(100) if d.get(f"{prefix}w{k:03d}")]
    print(c, {"n": len(diffs), "max_abs_diff": max(diffs), "within_1e-6": sum(x <= 1e-6 for x in diffs)})
