"""[측정 도구] 새 베이스 검증 요약: 증거 파일(experiments/<EXP>/raw)에서 수치를 다시 계산해 한 JSON 으로 낸다.
보고서·BASE_VERIFY.md 의 수치는 이 출력에서 옮긴다(손으로 옮겨 적지 않는다).
  PYTHONUTF8=1 python harness/tools/summarize_base.py BASE-VERIFY > experiments/BASE-VERIFY/summary_base.json
"""
import glob, json, os, statistics as st, sys

EXP = sys.argv[1] if len(sys.argv) > 1 else "BASE-VERIFY"
R = f"experiments/{EXP}/raw"
load = lambda p: json.load(open(p, encoding="utf-8"))
out = {"exp": EXP}

# 재시작 복구: 시험마다 3회 중앙값(복구 = 두 끝단 중 늦은 쪽), 유실·중복 합
if os.path.exists(f"{R}/restart_base.jsonl"):
    by = {}
    for line in open(f"{R}/restart_base.jsonl", encoding="utf-8"):
        d = json.loads(line)
        by.setdefault(d["test"], []).append(d)
    res = {}
    for t, rows in by.items():
        rec = [max(r["flow_dmz"]["recover_s"] or 1e9, r["flow_it"]["recover_s"] or 1e9) for r in rows]
        res[t] = {"n": len(rows), "recover_s": [None if x >= 1e9 else x for x in rec],
                  "recover_median_s": None if any(x >= 1e9 for x in rec) else st.median(rec),
                  "self_recovered": sum(x < 1e9 for x in rec),
                  "dmz_loss_tag_s": [r["complete_dmz"]["influx_process_raw"]["missing_s_total"] for r in rows],
                  "it_loss_tag_s": [r["complete_it"]["influx_process_raw"]["missing_s_total"] for r in rows],
                  "kafka_raw_dup": [r["complete_dmz"]["kafka_raw"]["dup_total"] for r in rows],
                  "dmz_dup": [r["complete_dmz"]["influx_process_raw"]["dup_total"] for r in rows],
                  "flink_running_after": [r["flink_running"] for r in rows]}
    out["restart"] = res

# E1: 묶음별 p95 와 3묶음 중앙(무효 표시가 붙은 파일은 뺀다)
e1 = {}
for p in sorted(glob.glob(f"{R}/e1_e1_base_*.json")):
    if "무효" in p:
        continue
    d = load(p)
    e1[os.path.basename(p)[3:-5]] = {k: {kk: v[kk] for kk in ("n", "missing", "p50", "p95")} for k, v in d["summary"].items()}
runs = [e1[k] for k in ("e1_base_1", "e1_base_2", "e1_base_3") if k in e1]
out["e1"] = {"runs": e1, "median_of_p95": {pt: st.median([r[pt]["p95"] for r in runs if r.get(pt, {}).get("p95") is not None])
                                           for pt in ("kafka:sensor.alerts", "incident") if runs}}

# 고장 → 알람: 고장마다 마지막으로 잰 실행(run3 > run2 > run1)의 최대값
onset = {}
for p in ("onset_base_run1.json", "onset_base_run2.json", "onset_base_run3.json"):
    if os.path.exists(f"{R}/{p}"):
        for f, v in load(f"{R}/{p}")["results"].items():
            onset[f] = {"from": p, "kafka_max_s": v["kafka_max_s"], "screen_max_s": v["screen_max_s"], "screen": v["screen"],
                        "reps": v["reps"], "within_10s": v["within_10s"]}
out["fault_onset"] = onset

for name, p in (("e7", "e7_base.json"), ("s13", "s13_s13_base.json"), ("isolation", "isolation_base.json"),
                ("queue", "queue_base.json"), ("rate", "rate_check.json")):
    if os.path.exists(f"{R}/{p}"):
        d = load(f"{R}/{p}")
        out[name] = {k: v for k, v in d.items() if k not in ("samples", "tests", "per_tag")} if isinstance(d, dict) else d
if os.path.exists(f"{R}/control_base.json"):
    d = load(f"{R}/control_base.json")
    out["control_ot"] = {k: v.get("pass") for k, v in d.items() if isinstance(v, dict) and "pass" in v}
if os.path.exists(f"{R}/control_ai_base.jsonl"):
    out["control_ai"] = {}
    for line in open(f"{R}/control_ai_base.jsonl", encoding="utf-8", errors="replace"):
        d = json.loads(line)
        out["control_ai"][d["step"]] = d.get("pass")
if os.path.exists(f"experiments/{EXP}/e3_base_summary.json"):
    d = load(f"experiments/{EXP}/e3_base_summary.json")
    out["e3"] = {k: d[k] for k in ("containers", "samples", "mem_total_mib_median", "cpu_total_pct_median")}
print(json.dumps(out, ensure_ascii=False, indent=1))
