"""[측정 도구] 중계 층 결과표(증거에서 재계산): experiments/EXP-PIPE/stage2_<후보>.json → 후보별 한 줄 + layer_pipe.json
  python harness/tools/layer_pipe.py
중계 ①(MQTT→Kafka raw)·②(Kafka→InfluxDB)·③(Kafka alerts→MQTT) 각각 유실·중복·모양/값 불일치·지연 p95, 자원.
V1 값이 기준(V1 Telegraf 1.33 ×3 — 예: ts 가 float 로 나가는 것은 V1 모양).
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
    for f in sorted(glob.glob("experiments/EXP-PIPE/stage2_*.json")):
        p = os.path.basename(f)[7:-5]
        d = json.load(open(f, encoding="utf-8"))
        r1, r2, r3 = d.get("relay1_mqtt_to_kafka_raw") or {}, d.get("relay2_kafka_to_influx") or {}, d.get("relay3_kafka_to_mqtt") or {}
        tot = g(d, "resources", "total") or {}
        rows[p] = {"relays_checked": d.get("relays_checked"),
                   "r1": {k: r1.get(k) for k in ("expected", "received_unique", "lost", "duplicates", "schema_or_value_mismatch", "filter_leaks(sentinel/non-sensor)", "kafka_key_not_tag")} | {"p95_ms": g(r1, "latency_ms", "p95")},
                   "r2": {"alerts_lost": r2.get("alerts_lost"), "alerts_tag_mismatch": r2.get("alerts_tag_mismatch"),
                          "raw_vs_topic": r2.get("process_raw_vs_raw_topic"), "p95_ms": g(r2, "latency_ms(1s poll)", "p95")},
                   "r3": {k: r3.get(k) for k in ("alerts_expected", "received_unique", "lost", "duplicates", "shape_mismatch", "hmi_matching")} | {"p95_ms": g(r3, "latency_ms", "p95")},
                   "containers": tot.get("containers"), "mem_mib_median": tot.get("mem_mib_median"), "cpu_pct_median": tot.get("cpu_pct_median"),
                   "error": d.get("error")}
    json.dump(rows, open("experiments/EXP-PIPE/layer_pipe.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    for p, r in rows.items():
        a, b, c = r["r1"], r["r2"], r["r3"]
        print(f"{p:12s} ①{a.get('received_unique')}/{a.get('expected')} 유실{a.get('lost')} 중복{a.get('duplicates')} 불일치{a.get('schema_or_value_mismatch')} p95={a.get('p95_ms')} | "
              f"②알람유실{b.get('alerts_lost')} raw{b.get('raw_vs_topic')} p95={b.get('p95_ms')} | ③{c.get('received_unique')}/{c.get('alerts_expected')} 중복{c.get('duplicates')} "
              f"모양{c.get('shape_mismatch')} hmi{c.get('hmi_matching')} p95={c.get('p95_ms')} | 컨테이너{r['containers']} mem={r['mem_mib_median']}")


if __name__ == "__main__":
    main()
