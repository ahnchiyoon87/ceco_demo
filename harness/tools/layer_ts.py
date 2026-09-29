"""[측정 도구] 시계열 저장 층 결과표(증거에서 재계산): experiments/EXP-TS/stage2_<엔진>.json → 엔진별 한 줄 + layer_ts.json
  python harness/tools/layer_ts.py
24시간분 적재(행/s·쓰기 오류), 새 값 보이기 지연 p95, 질의 10종 정답 여부·p95, 디스크, 자원.
"""
import glob, json, os


def main():
    rows = {}
    for f in sorted(glob.glob("experiments/EXP-TS/stage2_*.json")):
        e = os.path.basename(f)[7:-5]
        d = json.load(open(f, encoding="utf-8"))
        r = d.get("runs", {})
        ld, q, fr = r.get("load24h") or {}, r.get("query24h") or {}, r.get("fresh") or {}
        qs = q.get("queries") or {}
        res = d.get("resources") or {}
        mem = []
        for v in res.values():
            if isinstance(v, dict):
                for c in v.values():
                    if isinstance(c, dict) and c.get("mem_mib_median") is not None:
                        mem.append(c["mem_mib_median"])
        rows[e] = {"verdict": d.get("stage2_verdict"), "rows_per_s": ld.get("rows_per_s"), "write_errors": ld.get("write_errors"),
                   "visible_p95_ms": (fr.get("visible_ms") or {}).get("p95"), "correct_all": q.get("correct_all"),
                   "wrong": [k for k, v in qs.items() if isinstance(v, dict) and not v.get("correct")],
                   "query_p95_ms": {k: v.get("p95_ms") for k, v in qs.items() if isinstance(v, dict)},
                   "disk_kib_24h": (d.get("disk_kib") or {}).get("after_load_24h_settled"), "mem_mib_median_sum": round(sum(mem), 1) if mem else None,
                   "containers": sum(len(v) for v in res.values() if isinstance(v, dict)) or None}
    json.dump(rows, open("experiments/EXP-TS/layer_ts.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for e, r in rows.items():
        qp = r["query_p95_ms"]
        print(f"{e:16s} {r['verdict'][:10] if r['verdict'] else None} 적재 {r['rows_per_s']}행/s 오류{r['write_errors']} 보이기p95 {r['visible_p95_ms']} "
              f"정답 {r['correct_all']} 틀림{r['wrong']} 근거질의p95 {qp.get('evidence')} 추세24h p95 {qp.get('trend_24h')} 디스크 {r['disk_kib_24h']}KiB mem {r['mem_mib_median_sum']}")


if __name__ == "__main__":
    main()
