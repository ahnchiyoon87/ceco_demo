"""[측정 도구] 브로커 층 결과표(증거 파일에서 재계산): experiments/EXP-130/raw 의 mqtt_bench·br07·stats 파일 → 브로커별 한 줄.
  python harness/tools/layer_broker.py [--out experiments/EXP-130/layer_broker.json]
모드: normal(BR-01 정상 120 msg/s·60 s) · live_restart(BR-02 발행 중 브로커 재시작) · offline_queue(BR-04·05 재시작 넘어 오프라인 큐)
      · offline_queue 재시작 없음(BR-03, run 이름 끝 q0) · ws(BR-06) · br07(지표). 실행이 여럿이면 값 목록과 중앙값.
기동 실패는 logs_<브로커>_up_*.txt 가 있고 normal 파일이 없는 경우.
"""
import argparse, csv, glob, json, os, re, statistics

RAW = "experiments/EXP-130/raw"


def med(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(statistics.median(xs), 2) if xs else None


def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--out", default="experiments/EXP-130/layer_broker.json")
    a = ap.parse_args()
    brokers = sorted({re.match(r"(.+?)_(normal|live_restart|offline_queue|ws)_", os.path.basename(f)).group(1)
                      for f in glob.glob(f"{RAW}/*_*_*.json") if re.match(r".+?_(normal|live_restart|offline_queue|ws)_", os.path.basename(f))}
                     | {re.match(r"logs_(.+?)_up_", os.path.basename(f)).group(1) for f in glob.glob(f"{RAW}/logs_*_up_*.txt")})
    rows = {}
    for b in brokers:
        r = {"broker": b}
        n = [json.load(open(f, encoding="utf-8")) for f in sorted(glob.glob(f"{RAW}/{b}_normal_*.json"))]
        if not n:
            r["verdict_stage2"] = "기동·접속 실패"
            r["up_logs"] = sorted(os.path.basename(f) for f in glob.glob(f"{RAW}/logs_{b}_up_*.txt"))
            rows[b] = r; continue
        r["normal"] = {"runs": len(n), "lost": [x["lost"] for x in n], "dup": [x["duplicates"] for x in n],
                       "p95_ms": [x["latency_ms"]["p95"] for x in n], "p95_median_ms": med([x["latency_ms"]["p95"] for x in n])}
        lr = [json.load(open(f, encoding="utf-8")) for f in sorted(glob.glob(f"{RAW}/{b}_live_restart_*.json"))]
        r["live_restart"] = {"lost": [x.get("lost") for x in lr], "dup": [x.get("duplicates") for x in lr],
                             "max_gap_ms": [x.get("max_gap_ms") for x in lr]}
        q = [(os.path.basename(f), json.load(open(f, encoding="utf-8"))) for f in sorted(glob.glob(f"{RAW}/{b}_offline_queue_*.json"))]
        r["offline_queue_restart"] = [{"acked": x.get("queued_acked"), "received": x.get("received_after_restart"),
                                       "session_present": x.get("session_present")} for fn, x in q if not fn.endswith("q0.json")]
        r["offline_queue_no_restart"] = [{"acked": x.get("queued_acked"), "received": x.get("received_after_restart")}
                                         for fn, x in q if fn.endswith("q0.json")]
        w = [json.load(open(f, encoding="utf-8")) for f in sorted(glob.glob(f"{RAW}/{b}_ws_*.json"))]
        r["ws"] = [x.get("ws_connected") for x in w]
        br = [json.load(open(f, encoding="utf-8")) for f in sorted(glob.glob(f"{RAW}/br07_*{b}.json"))]
        r["metrics_br07"] = [x.get(b, x).get("verdict") if isinstance(x.get(b, x), dict) else None for x in br]
        mem, cpu = [], []
        for f in glob.glob(f"{RAW}/stats_{b}_*.csv"):
            per_t = {}
            for row in csv.DictReader(open(f, encoding="utf-8")):
                try:
                    per_t.setdefault(row["t_epoch"], [0.0, 0.0])
                    per_t[row["t_epoch"]][0] += float(row["mem_mib"]); per_t[row["t_epoch"]][1] += float(row["cpu_pct"])
                except (ValueError, KeyError):
                    pass
            mem += [v[0] for v in per_t.values()]; cpu += [v[1] for v in per_t.values()]
        r["mem_mib_median"] = med(mem); r["cpu_pct_median"] = med(cpu)
        img = glob.glob(f"{RAW}/images_{b}.json")
        r["image_mb"] = round(sum(json.load(open(img[0], encoding="utf-8")).values()), 1) if img else None
        rows[b] = r
    json.dump(rows, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for b, r in rows.items():
        if "normal" not in r:
            print(f"{b:12s} {r['verdict_stage2']}"); continue
        print(f"{b:12s} lost={r['normal']['lost']} dup={r['normal']['dup']} p95={r['normal']['p95_median_ms']}ms | 재시작 lost={r['live_restart']['lost']} dup={r['live_restart']['dup']} | "
              f"큐(재시작) {[(x['acked'], x['received']) for x in r['offline_queue_restart']]} 큐(무재시작) {[(x['acked'], x['received']) for x in r['offline_queue_no_restart']]} | "
              f"ws={r['ws']} 지표={r['metrics_br07']} | mem={r['mem_mib_median']}MiB cpu={r['cpu_pct_median']}% img={r['image_mb']}MB")


if __name__ == "__main__":
    main()
