"""[측정 도구] 전체 스택 측정(baseline.sh) 증거 파일 → 버전별 요약(보고서·점수표 수치의 정본 계산).
  python harness/tools/summarize_baseline.py <EXP> <이름> <RUN접두사> [--out experiments/<EXP>/summary_<이름>.json]
읽는 것(모두 experiments/<EXP>/raw/):
  robustness_<이름>.jsonl 의 "run"==RUN 행 → 복구(2분 연속 흐름) 초, null = 스스로 복구 안 됨
  r0X_<이름>_<RUN><k>.json(시험 시점 완전성) · 같은 이름 _c2.json(사후 재계산, 있으면) → 유실·중복·최대 공백
  e1_<이름>_{1,2,3}.json → 알람→화면 p95(묶음별), 중앙값 / r09·e7·e12·e3 는 파일이 있으면 그대로
복구 시간 중앙값: 복구 안 됨은 무한대로 보고 중앙값을 낸다(3회 중 2회 복구 안 됨 → 중앙값 = 복구 안 됨).
"""
import argparse, glob, json, math, os, statistics


def med(xs):
    xs = [math.inf if x is None else x for x in xs]
    if not xs:
        return None
    m = statistics.median(xs)
    return None if math.isinf(m) else round(m, 1)


def load(p):
    return json.load(open(p, encoding="utf-8")) if os.path.exists(p) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exp"); ap.add_argument("name"); ap.add_argument("run")
    ap.add_argument("--out")
    a = ap.parse_args()
    raw = f"experiments/{a.exp}/raw"
    rows = [json.loads(l) for l in open(f"{raw}/robustness_{a.name}.jsonl", encoding="utf-8") if l.strip()]
    rows = [r for r in rows if r.get("run") == a.run]
    out = {"exp": a.exp, "name": a.name, "run": a.run, "robustness": {}}
    for test in sorted({r["test"] for r in rows}):
        rs = sorted([r for r in rows if r["test"] == test], key=lambda r: r["k"])
        rec = [r["flow"]["recover_s"] for r in rs]
        comp, comp2 = [], []
        for r in rs:
            base = f"{raw}/{test}_{a.name}_{a.run}{r['k']}"
            for lst, suf in ((comp, ""), (comp2, "_c2")):
                d = load(base + suf + ".json")
                if d:
                    lst.append({k: {kk: d[k][kk] for kk in ("expected", "missing_s_total", "dup_total", "max_gap_s")}
                                for k in ("kafka_raw", "influx_process_raw")})
        def pick(lst, src, key):
            return [c[src][key] for c in lst]
        out["robustness"][test] = {
            "n": len(rs), "recover_s": rec, "recover_median_s": med(rec),
            "unrecovered": sum(x is None for x in rec),
            "at_test": {"raw_missing_tag_s": pick(comp, "kafka_raw", "missing_s_total"), "raw_dup": pick(comp, "kafka_raw", "dup_total"),
                        "store_missing_tag_s": pick(comp, "influx_process_raw", "missing_s_total"),
                        "max_gap_s": pick(comp, "kafka_raw", "max_gap_s")},
            "eventual": {"raw_missing_tag_s": pick(comp2, "kafka_raw", "missing_s_total"), "raw_dup": pick(comp2, "kafka_raw", "dup_total"),
                         "store_missing_tag_s": pick(comp2, "influx_process_raw", "missing_s_total"),
                         "store_dup": pick(comp2, "influx_process_raw", "dup_total"),
                         "max_gap_s": pick(comp2, "kafka_raw", "max_gap_s")} if comp2 else None}
    e1 = []
    for f in sorted(glob.glob(f"{raw}/e1_{a.name}_[0-9].json")):
        d = load(f)
        e1.append({k: v.get("p95") for k, v in (d.get("summary", d) or {}).items() if isinstance(v, dict) and "p95" in v})
    if not e1:   # EXP-001 V1: e1.py 결과 파일이 컨테이너 안에만 쓰여 사라짐(#103) → baseline 로그의 P2 요약 줄(원출력)에서
        log = f"experiments/{a.exp}/baseline_{a.name}.log"
        if os.path.exists(log):
            lines = open(log, encoding="utf-8").read().split("P2 E1")[-1].split("P3")[0].splitlines()
            for l in lines:
                if l.startswith("{") and '"kafka:sensor.alerts"' in l:
                    d = json.loads(l)
                    e1.append({k: v.get("p95") for k, v in d.items() if isinstance(v, dict) and "p95" in v})
            out["e1_source"] = log + " (P2 요약 줄)"
    if e1:
        keys = sorted({k for x in e1 for k in x})
        out["e1_p95_ms"] = {k: {"runs": [x.get(k) for x in e1], "median": med([x.get(k) for x in e1 if x.get(k) is not None])} for k in keys}
    for key, pat in (("r09", f"{raw}/r09_{a.name}.json"), ("e7", f"{raw}/e7_{a.name}.json"), ("e12", f"{raw}/e12_{a.name}.json")):
        d = load(pat)
        if d is not None:
            out[key] = d if key != "r09" else {k: {kk: d[k][kk] for kk in ("expected", "missing_s_total", "dup_total", "max_gap_s")}
                                               for k in ("kafka_raw", "influx_process_raw")}
    for key, pat in (("e11_container", f"{raw}/e11_container_{a.name}{a.run}.json"), ("e11_detector", f"{raw}/e11_detector_{a.name}{a.run}.json")):
        d = load(pat)
        if d is not None:
            out[key] = sorted({x["labels"].get("alertname") for x in d})
    s = json.dumps(out, ensure_ascii=False, indent=1)
    open(a.out or f"experiments/{a.exp}/summary_{a.name}_{a.run or 'base'}.json", "w", encoding="utf-8").write(s)
    print(s)


if __name__ == "__main__":
    main()
