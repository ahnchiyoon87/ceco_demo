"""[측정 도구] 이상탐지 층 결과표(증거에서 재계산): experiments/EXP-L4/stage2_<후보>.json(실행 누적 중 마지막) → 후보별 한 줄.
  python harness/tools/layer_l4.py
판정 70건 통과/실패, V1 알람 기록(m1)과의 대조(추가·누락, 유형별), S13 ONNX 점수, R05(JobManager 재시작) 결과, 자원.
멈춘 단계(stopped_at)가 done 이 아니면 그 단계와 사유.
"""
import glob, json, os


def main():
    rows = {}
    for f in sorted(glob.glob("experiments/EXP-L4/stage2_*.json")):
        p = os.path.basename(f)[7:-5]
        d = json.load(open(f, encoding="utf-8"))
        r = d["runs"][-1] if isinstance(d, dict) and "runs" in d else d
        cmp_ = r.get("v1_compare") or {}
        s13 = ((r.get("s13") or {}).get("cands") or {})
        s13v = next(iter(s13.values()), {}) if s13 else {}
        res = r.get("resources") or {}
        rows[p] = {"run": r.get("run"), "stopped_at": r.get("stopped_at"), "status": r.get("status"), "note": r.get("note"),
                   "pass": (r.get("cases") or {}).get("pass"), "fail": (r.get("cases") or {}).get("fail"),
                   "v1_equal": cmp_.get("equal"), "only_cand": cmp_.get("only_cand"), "only_ref": cmp_.get("only_ref"),
                   "only_ref_types": cmp_.get("only_ref_types"), "only_cand_types": cmp_.get("only_cand_types"),
                   "s13": s13v.get("verdict"), "r05": {k: (r.get("r05") or {}).get(k) for k in ("pass", "fail", "jobs_after")} if r.get("r05") else None,
                   "mem_avg_mib": res.get("mem_avg_mib"), "cpu_avg_pct": res.get("cpu_avg_pct")}
    json.dump(rows, open("experiments/EXP-L4/layer_l4.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for p, r in rows.items():
        if r["stopped_at"] != "done":
            print(f"{p:12s} 멈춤={r['stopped_at']} {r['note']}"); continue
        print(f"{p:12s} {r['pass']}/{(r['pass'] or 0) + (r['fail'] or 0)} V1동일={r['v1_equal']} 추가={r['only_cand']}{r['only_cand_types'] or ''} "
              f"누락={r['only_ref']}{r['only_ref_types'] or ''} S13={r['s13']} R05={r['r05']} mem={r['mem_avg_mib']}MiB cpu={r['cpu_avg_pct']}%")


if __name__ == "__main__":
    main()
