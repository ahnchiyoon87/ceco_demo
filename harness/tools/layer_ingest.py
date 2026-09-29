"""[측정 도구] 수집 층 결과표(증거에서 재계산): experiments/EXP-ING/stage2_<후보>.json → 후보별 한 줄 + experiments/EXP-ING/layer_ingest.json
  python harness/tools/layer_ingest.py
정상 시험(약 113 s, 12태그×1 Hz): 도착/기대, 값 일치율, 지연 p95(수집 origin→MQTT 수신), 하류 V1 레코드 동등, 자원·컨테이너.
R02(단절)·R11(설비 통신 끊김)은 stage4 결과 파일이 있으면 함께(`stage4_*` 키).
"""
import glob, json, os


def g(d, *ks):
    for k in ks:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d


def main():
    rows = {}
    for f in sorted(glob.glob("experiments/EXP-ING/stage2_*.json")):
        p = os.path.basename(f)[7:-5]
        d = json.load(open(f, encoding="utf-8"))
        res = g(d, "resources") or {}
        tot = res.get("total") or res.get("summary") or {}
        rows[p] = {"expected": g(d, "completeness", "expected_samples"), "unique": g(d, "completeness", "unique_samples"),
                   "duplicates": g(d, "completeness", "duplicates"), "value_match_rate": g(d, "values", "match_rate"),
                   "p95_ms": g(d, "latency_ms", "recv_minus_origin", "p95"), "value_age_p95_ms": g(d, "latency_ms", "value_age", "p95"),
                   "v1_shape": g(d, "shape", "v1_edgex_shape"), "downstream_equivalent": g(d, "downstream", "equivalent"),
                   "downstream_missing": g(d, "downstream", "missing"), "containers": tot.get("containers"),
                   "mem_mib_median": tot.get("mem_mib_median"), "cpu_pct_median": tot.get("cpu_pct_median")}
    json.dump(rows, open("experiments/EXP-ING/layer_ingest.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for p, r in rows.items():
        print(f"{p:12s} {r['unique']}/{r['expected']} dup={r['duplicates']} 값일치={r['value_match_rate']} p95={r['p95_ms']}ms "
              f"하류동등={r['downstream_equivalent']}(누락 {r['downstream_missing']}) 컨테이너={r['containers']} mem={r['mem_mib_median']} cpu={r['cpu_pct_median']}")


if __name__ == "__main__":
    main()
