"""벤치 공통: sample_stats.sh CSV(1초 docker stats)와 이미지 크기 JSON 을 결과 JSON 에 합친다.

    python harness/benchstats.py --result R.json --stats S.csv [--images I.json] [--skip 5]

추가 필드 resources:
  per_container: {name: {cpu_pct_median, cpu_pct_p95, mem_mib_median, mem_mib_max, samples}}
  total: {containers, mem_mib_median(초별 합의 중앙값), mem_mib_max, cpu_pct_median(초별 합의 중앙값), cpu_pct_p95}
  images_mib: {image: MiB}, images_total_mib
호스트(Windows Python) 또는 client 컨테이너 어느 쪽에서도 돈다(표준 라이브러리만).
"""
import argparse
import csv
import json
import pathlib
import statistics


def pct(v, q):
    v = sorted(v)
    return round(v[min(len(v) - 1, int(round(q * (len(v) - 1))))], 2) if v else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--result", required=True)
    ap.add_argument("--stats", required=True)
    ap.add_argument("--images", default="")
    ap.add_argument("--skip", type=int, default=5, help="앞쪽 샘플(초) 제외 — 기동 직후 흔들림")
    ap.add_argument("--only", default="", help="total 에 넣을 컨테이너 이름 정규식(후보 부품만). 나머지는 per_container 에만")
    a = ap.parse_args()
    res_p = pathlib.Path(a.result)
    res = json.loads(res_p.read_text(encoding="utf-8"))
    rows = []
    with open(a.stats, encoding="utf-8") as fh:
        for r in csv.DictReader(fh):
            try:
                rows.append((int(r["t_epoch"]), r["name"], float(r["cpu_pct"]), float(r["mem_mib"])))
            except (ValueError, KeyError):
                continue
    if rows:
        t0 = min(r[0] for r in rows) + a.skip
        rows = [r for r in rows if r[0] >= t0]
    import re
    only = re.compile(a.only) if a.only else None
    per, by_t = {}, {}
    for t, n, cpu, mem in rows:
        per.setdefault(n, []).append((cpu, mem))
        if only and not only.search(n):
            continue
        s = by_t.setdefault(t, [0.0, 0.0])
        s[0] += cpu
        s[1] += mem
    resources = {"per_container": {n: {"cpu_pct_median": round(statistics.median(c for c, _ in v), 2),
                                       "cpu_pct_p95": pct([c for c, _ in v], .95),
                                       "mem_mib_median": round(statistics.median(m for _, m in v), 1),
                                       "mem_mib_max": round(max(m for _, m in v), 1), "samples": len(v)}
                                   for n, v in sorted(per.items())},
                 "total": {"containers": len([n for n in per if not only or only.search(n)]), "only": a.only,
                           "cpu_pct_median": round(statistics.median(s[0] for s in by_t.values()), 2) if by_t else None,
                           "cpu_pct_p95": pct([s[0] for s in by_t.values()], .95),
                           "mem_mib_median": round(statistics.median(s[1] for s in by_t.values()), 1) if by_t else None,
                           "mem_mib_max": round(max(s[1] for s in by_t.values()), 1) if by_t else None},
                 "stats_csv": a.stats}
    if a.images and pathlib.Path(a.images).exists():
        imgs = json.loads(pathlib.Path(a.images).read_text(encoding="utf-8"))
        resources["images_mib"] = imgs
        resources["images_total_mib"] = round(sum(imgs.values()), 1)
    res["resources"] = resources
    res_p.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(resources["total"], ensure_ascii=False))


if __name__ == "__main__":
    main()
