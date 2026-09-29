"""[측정 도구] 구간 알람 집계: sensor.alerts 에서 [start,end] 레코드를 유형·태그·장치별로 센다(S01 정상 운전 알람 수).
  python harness/e2e/alerts_window.py --start-ms A --end-ms B [--device reactor-line-01] --out x.json
"""
import argparse, collections, json
from confluent_kafka import Consumer, TopicPartition

ap = argparse.ArgumentParser()
ap.add_argument("--start-ms", type=int, required=True); ap.add_argument("--end-ms", type=int, required=True)
ap.add_argument("--device", default="reactor-line-01"); ap.add_argument("--out", required=True)
a = ap.parse_args()
c = Consumer({"bootstrap.servers": "kafka:9092", "group.id": "alerts-window", "enable.auto.commit": False})
parts = c.list_topics("sensor.alerts", timeout=10).topics["sensor.alerts"].partitions
tps = c.offsets_for_times([TopicPartition("sensor.alerts", p, a.start_ms) for p in parts], timeout=10)
ends = {tp.partition: c.get_watermark_offsets(TopicPartition("sensor.alerts", tp.partition), timeout=10)[1] for tp in tps}
c.assign(tps)
done, rows = {p for p, e in ends.items() if e <= 0}, []
for tp in tps:
    if tp.offset < 0:
        done.add(tp.partition)
while len(done) < len(ends):
    m = c.poll(1.0)
    if m is None:
        break
    if m.error():
        continue
    if m.offset() >= ends[m.partition()] - 1:
        done.add(m.partition())
    if a.start_ms <= m.timestamp()[1] <= a.end_ms:
        v = json.loads(m.value())
        if v.get("device") == a.device:
            rows.append(v)
c.close()
by = collections.Counter(f'{r.get("alert_type")}:{r.get("tag")}' for r in rows)
out = {"window_ms": [a.start_ms, a.end_ms], "device": a.device, "alerts": len(rows), "by_type_tag": dict(by)}
json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(out, ensure_ascii=False))
