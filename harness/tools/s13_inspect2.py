"""S13 진단 2: 장치 몇 개의 엔진별 점수 수열과, 행 표본 패턴 가설별 참조값을 나란히 출력. 판정 도구 아님."""
import collections
import json
import pathlib
import sys

import numpy as np

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

seqs = {}
for c in ["flinksql", "flink22", "cep", "python"]:
    d = collections.defaultdict(list)
    for _, s in s13.read_topic(f"exp.l4.score.{c}", prefix):
        d[s["device"]].append((s["ts"], s["reconstruction_error"]))
    seqs[c] = {k: [round(x[1], 7) for x in sorted(v)] for k, v in d.items()}

for k in (0, 30, 60, 90):
    dev = f"{prefix}w{k:03d}"
    w = wins[k]
    hyp = {"rows0-9": w, "last_row_x10": [w[9]] * 10, "first_row_x10": [w[0]] * 10,
           "rows1-9+9": w[1:] + [w[9]]}
    href = dict(zip(hyp, s13.reference(list(hyp.values()), meta)))
    print("device", k, {h: round(v, 7) for h, v in href.items()})
    for c in seqs:
        print("  ", c, seqs[c].get(dev, [])[:8])
# 엔진 간 비교: 장치별 점수 '값 집합'이 기준(flinksql)과 같은가
base = seqs["flinksql"]
for c in ["flink22", "cep", "python"]:
    same = sum(1 for dev in base if dev.endswith("g") is False and set(seqs[c].get(dev, [])) == set(base[dev]))
    tail_same = sum(1 for dev in base if seqs[c].get(dev) and base[dev] and seqs[c][dev][-1] == base[dev][-1])
    print(c, "장치별 값집합 동일", same, "/", len(base), "· 마지막 점수 동일", tail_same)
