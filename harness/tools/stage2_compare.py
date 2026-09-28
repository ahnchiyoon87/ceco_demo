"""stage2 알람 집합 대조: 후보 1회 실행의 알람을 같은 시드로 돌린 V1(Flink 1.20.1 flinksql) 실행의 알람과 비교한다.

한 번의 리플레이를 두 후보가 동시에 소비하던 run_l4_multi.sh 와 달리, stage2 는 메모리 때문에 후보를 하나씩 띄운다.
그래서 실행마다 달라지는 값(장치 이름 앞의 run·token, 벽시계 기준 ts)을 지우고 비교한다.
  키 = (케이스-반복, alert_type, tag, round((ts - manifest.t0_event_ns) / 1e6))   # 이벤트 시각 오프셋(ms)
같은 --seed·--repeat·--jitter·--cases 로 만든 리플레이끼리만 비교할 수 있다(manifest 로 확인, 다르면 거부).
ML(TIER2_ML) 알람은 처리시각 타이머라 run_l4_multi.sh 와 같이 뺀다(동일성은 s13.py).

  python harness/tools/stage2_compare.py --cand-dir experiments/EXP-L4/raw --cand-run s2_x --cand-alerts alerts_s2_x.jsonl \
         --ref-dir experiments/EXP-L4/raw --ref-run m1 --ref-alerts alerts_m1_flinksql.jsonl [--out result.json]
"""
import argparse
import collections
import json
import pathlib
import re

SAME = ("seed", "repeat", "jitter", "cases", "window_s", "watermark_s")


def load(d, run, alerts_file):
    d = pathlib.Path(d)
    man = json.loads((d / f"replay_{run}_manifest.json").read_text(encoding="utf-8"))
    t0 = man["t0_event_ns"]
    pre = re.compile(rf"^{re.escape(run)}\.{re.escape(man['token'])}-")
    keys = collections.Counter()
    ml = 0
    for line in open(d / alerts_file, encoding="utf-8"):
        r = json.loads(line)
        if r.get("detector") == "TIER2_ML" or r.get("alert_type") == "ML_AUTOENCODER":
            ml += 1
            continue
        dev = pre.sub("", str(r["device"]))
        keys[(dev, r["alert_type"], r["tag"], round((int(r["ts"]) - t0) / 1e6))] += 1
    return man, keys, ml


def main():
    ap = argparse.ArgumentParser()
    for side in ("cand", "ref"):
        ap.add_argument(f"--{side}-dir", required=True)
        ap.add_argument(f"--{side}-run", required=True)
        ap.add_argument(f"--{side}-alerts", required=True)
    ap.add_argument("--out")
    a = ap.parse_args()
    cm, ck, cml = load(a.cand_dir, a.cand_run, a.cand_alerts)
    rm, rk, rml = load(a.ref_dir, a.ref_run, a.ref_alerts)
    bad = {k: (cm.get(k), rm.get(k)) for k in SAME if cm.get(k) != rm.get(k)}
    if bad:
        raise SystemExit(f"리플레이 조건이 달라 비교 불가: {bad}")
    only_c, only_r = ck - rk, rk - ck
    by_type = lambda c: dict(collections.Counter(k[1] for k in c.elements()))
    out = {"ref": {"dir": a.ref_dir, "run": a.ref_run, "alerts": a.ref_alerts, "count": sum(rk.values()), "types": by_type(rk)},
           "cand": {"run": a.cand_run, "count": sum(ck.values()), "types": by_type(ck), "ml_excluded": cml},
           "only_cand": sum(only_c.values()), "only_ref": sum(only_r.values()),
           "only_cand_types": by_type(only_c), "only_ref_types": by_type(only_r),
           "duplicates_cand": sum(v - 1 for v in ck.values() if v > 1),
           "duplicates_ref": sum(v - 1 for v in rk.values() if v > 1),
           "equal": not only_c and not only_r,
           "sample_only_cand": [list(k) for k in list(only_c)[:10]],
           "sample_only_ref": [list(k) for k in list(only_r)[:10]]}
    txt = json.dumps(out, ensure_ascii=False, indent=1)
    if a.out:
        pathlib.Path(a.out).write_text(txt, encoding="utf-8")
    print(txt)


if __name__ == "__main__":
    main()
