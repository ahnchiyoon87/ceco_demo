"""E3 자원 요약(측정 도구): sample_stats.sh CSV → 시점별 합계(메모리 MiB·CPU %)의 중앙값, 처음·마지막 10분 메모리 차(R09 증가율), 컨테이너별 중앙값."""
import csv, json, statistics as st, sys
from collections import defaultdict
rows = list(csv.DictReader(open(sys.argv[1], encoding="utf-8")))
per_t, per_c = defaultdict(lambda: [0.0, 0.0, 0]), defaultdict(lambda: ([], []))
for r in rows:
    t = int(r["t_epoch"]); m = float(r["mem_mib"]); c = float(r["cpu_pct"] or 0)
    per_t[t][0] += m; per_t[t][1] += c; per_t[t][2] += 1
    per_c[r["name"]][0].append(m); per_c[r["name"]][1].append(c)
full = max(v[2] for v in per_t.values())
ts = sorted(t for t, v in per_t.items() if v[2] == full)          # 모든 컨테이너가 잡힌 시점만
mem = [per_t[t][0] for t in ts]; cpu = [per_t[t][1] for t in ts]
first = [per_t[t][0] for t in ts if t < ts[0] + 600]; last = [per_t[t][0] for t in ts if t > ts[-1] - 600]
out = {"samples": len(ts), "containers": full, "duration_s": ts[-1] - ts[0],
       "mem_total_mib_median": round(st.median(mem), 1), "cpu_total_pct_median": round(st.median(cpu), 1),
       "mem_first10_median": round(st.median(first), 1), "mem_last10_median": round(st.median(last), 1),
       "mem_growth_mib_per_h": round((st.median(last) - st.median(first)) / ((ts[-1] - ts[0] - 600) / 3600), 1),
       "per_container_mem_median": {k: round(st.median(v[0]), 1) for k, v in sorted(per_c.items(), key=lambda kv: -st.median(kv[1][0]))}}
print(json.dumps(out, ensure_ascii=False, indent=1))
