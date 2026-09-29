"""[측정 도구] 백본 층 결과표(증거에서 재계산): experiments/EXP-BB/stage2_<후보>.json → 후보별 한 줄 + layer_backbone.json
  python harness/tools/layer_backbone.py
변형별(base 12태그×1Hz, x10, scale 10장치, restart 재시작) 유실·중복·키 안 순서 역전·지연 p95, 위치/시각 재생, 자원(base), Telegraf 호환.
"""
import glob, json, os


def main():
    rows = {}
    for f in sorted(glob.glob("experiments/EXP-BB/stage2_*.json")):
        p = os.path.basename(f)[7:-5]
        d = json.load(open(f, encoding="utf-8"))
        runs = d.get("runs", {})
        r = {"verdict": d.get("stage2_verdict"), "startup_s": (runs.get("startup") or {}).get("startup_s")}
        for v in ("base", "x10", "scale", "restart"):
            x = runs.get(v)
            if not x:
                continue
            dl, lat, rp = x.get("delivery") or {}, x.get("latency_ms") or {}, x.get("replay") or {}
            r[v] = {"lost": dl.get("lost"), "dup": dl.get("duplicates"), "reorder": dl.get("reordered_within_key"),
                    "p95_ms": lat.get("p95"), "replay_pos": (rp.get("by_position") or {}).get("ok"), "replay_time": (rp.get("by_time") or {}).get("ok"),
                    "error": x.get("error")}
        res = (d.get("resources") or {}).get("base") or {}
        r["mem_mib_median_base"] = round(sum((c or {}).get("mem_mib_median") or 0 for c in res.values()), 1) if res else None
        r["containers"] = len(res) if res else None
        r["telegraf"] = runs.get("telegraf")
        rows[p] = r
    json.dump(rows, open("experiments/EXP-BB/layer_backbone.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for p, r in rows.items():
        parts = [f"{v}:유실{r[v]['lost']}·중복{r[v]['dup']}·역전{r[v]['reorder']}·p95 {r[v]['p95_ms']}·재생{r[v]['replay_pos']}/{r[v]['replay_time']}"
                 for v in ("base", "x10", "scale", "restart") if v in r]
        print(f"{p:10s} {r['verdict']} | {' | '.join(parts)} | 컨테이너{r['containers']} mem={r['mem_mib_median_base']}")


if __name__ == "__main__":
    main()
