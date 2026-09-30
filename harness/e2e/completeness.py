"""[측정 도구 — 솔루션 부품 아님] 구간 완전성(ROBUSTNESS 정답: 12태그 × 초).

Kafka raw(중복·공백)와 InfluxDB process_raw(저장 공백)를 같은 구간에서 센다. 컨테이너 안(rot-iiot 망)에서 실행.
  docker run --rm --network rot-iiot --env-file .env -v "$PWD:/repo" -w /repo e2e-client:1.0 \
     python harness/e2e/completeness.py --start-ms A --end-ms B --out experiments/EXP-000/raw/x.json
유실 = 태그별로 한 건도 없는 초(bucket) 수. 중복 = 같은 (tag, ts) 가 두 번 이상. 최대 공백 = 연속 도착 간 최대 간격(초, 구간 시작·끝 포함).
설비 장치(--device, 기본 reactor-line-01)만 센다 — R08 과부하 발생기의 다른 장치 레코드를 같은 태그 중복으로 세지 않게(09-29 #103).
"""
import argparse, csv, io, json, os, urllib.parse, urllib.request
from collections import defaultdict

DEVICE = "reactor-line-01"
TAGS = ["LT-101", "LT-102", "TT-101", "TT-102", "PT-101", "FT-101", "FT-102", "IT-101", "IT-102", "VT-101", "pH-101", "CT-101"]


def kafka_rows(bootstrap, topic, start_ms, end_ms):
    from confluent_kafka import Consumer, TopicPartition
    c = Consumer({"bootstrap.servers": bootstrap, "group.id": "completeness", "enable.auto.commit": False})
    parts = c.list_topics(topic, timeout=10).topics[topic].partitions
    tps = c.offsets_for_times([TopicPartition(topic, p, start_ms) for p in parts], timeout=10)
    c.assign(tps)
    ends = {tp.partition: c.get_watermark_offsets(TopicPartition(topic, tp.partition), timeout=10)[1] for tp in tps}
    # 구간 시작 뒤 메시지가 없는 파티션(시작 오프셋 없음 또는 끝 오프셋 이상)은 처음부터 끝난 것으로 둔다.
    # 없으면 그 파티션을 영원히 기다린다(09-30: 리플레이 때만 데이터가 들어간 파티션에서 멈춤)
    done, rows = {tp.partition for tp in tps if tp.offset < 0 or tp.offset >= ends[tp.partition]}, []
    while len(done) < len(ends):
        m = c.poll(1.0)
        if m is None:
            done |= {p for p, e in ends.items() if e <= 0}
            continue
        if m.error():
            continue
        if m.offset() >= ends[m.partition()] - 1 or m.timestamp()[1] > end_ms + 60000:
            done.add(m.partition())
        if start_ms <= m.timestamp()[1] <= end_ms + 60000:
            v = json.loads(m.value())
            if start_ms * 1_000_000 <= v["ts"] < end_ms * 1_000_000 and v.get("device", DEVICE) == DEVICE:
                rows.append((v["tag"], v["ts"]))
    c.close()
    return rows


INFLUX = {"url": "http://influxdb:8086", "bucket_env": "INFLUX_BUCKET", "token_env": "INFLUX_TOKEN", "measurement": "process_raw"}


def influx_rows(start_ms, end_ms):
    q = (f'from(bucket:"{os.environ[INFLUX["bucket_env"]]}") |> range(start:time(v:{start_ms * 1_000_000}), stop:time(v:{end_ms * 1_000_000})) '
         f'|> filter(fn:(r)=>r._measurement=="{INFLUX["measurement"]}" and r._field=="value" and (not exists r.device or r.device=="{DEVICE}")) |> keep(columns:["_time","tag"])')
    req = urllib.request.Request(INFLUX["url"] + "/api/v2/query?" + urllib.parse.urlencode({"org": os.environ["INFLUX_ORG"]}),
                                 json.dumps({"query": q, "type": "flux"}).encode(),
                                 {"Authorization": "Token " + os.environ[INFLUX["token_env"]], "Content-Type": "application/json", "Accept": "application/csv"})
    text = urllib.request.urlopen(req, timeout=60).read().decode()
    lines = [l for l in text.splitlines() if l and not l.startswith("#")]
    from datetime import datetime
    out = []
    for r in csv.DictReader(lines):
        if r.get("_time") in (None, "_time") or not r.get("tag"):
            continue
        t = datetime.fromisoformat(r["_time"].replace("Z", "+00:00"))
        out.append((r["tag"], int(t.timestamp() * 1_000_000_000)))
    return out


def analyse(rows, start_ms, end_ms):
    secs = (end_ms - start_ms) // 1000
    by = defaultdict(list)
    for tag, ts in rows:
        by[tag].append(ts)
    res, total_missing, total_dup, max_gap = {}, 0, 0, 0.0
    for tag in TAGS:
        ts = sorted(by.get(tag, []))
        buckets = {(t // 1_000_000_000) - start_ms // 1000 for t in ts}
        missing = sum(1 for b in range(secs) if b not in buckets)
        dup = len(ts) - len(set(ts))
        edges = [start_ms * 1_000_000] + ts + [end_ms * 1_000_000]
        gap = max((b - a) / 1e9 for a, b in zip(edges, edges[1:]))
        res[tag] = {"n": len(ts), "missing_s": missing, "dup": dup, "max_gap_s": round(gap, 2)}
        total_missing += missing; total_dup += dup; max_gap = max(max_gap, gap)
    return {"expected": 12 * secs, "seconds": secs, "missing_s_total": total_missing, "dup_total": total_dup,
            "max_gap_s": round(max_gap, 2), "per_tag": res}


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--start-ms", type=int, required=True)
    ap.add_argument("--end-ms", type=int, required=True)
    ap.add_argument("--kafka", default="kafka:9092")
    ap.add_argument("--topic", default="sensor.telemetry.raw")
    ap.add_argument("--out", required=True)
    ap.add_argument("--device", default="reactor-line-01")
    # 새 베이스: 저장 지점을 고른다. DMZ 원시 사본 = --influx http://dmz-influx:8086 --bucket-env DMZ_INFLUX_BUCKET --token-env DMZ_INFLUX_TOKEN
    #           IT 결과 = --influx http://it-influx:8086 --bucket-env IT_INFLUX_BUCKET --token-env IT_INFLUX_TOKEN --measurement process
    ap.add_argument("--influx", default=INFLUX["url"]); ap.add_argument("--bucket-env", default=INFLUX["bucket_env"])
    ap.add_argument("--token-env", default=INFLUX["token_env"]); ap.add_argument("--measurement", default=INFLUX["measurement"])
    a = ap.parse_args()
    DEVICE = a.device
    INFLUX.update(url=a.influx, bucket_env=a.bucket_env, token_env=a.token_env, measurement=a.measurement)
    out = {"window_ms": [a.start_ms, a.end_ms],
           "kafka_raw": analyse(kafka_rows(a.kafka, a.topic, a.start_ms, a.end_ms), a.start_ms, a.end_ms),
           "influx_process_raw": analyse(influx_rows(a.start_ms, a.end_ms), a.start_ms, a.end_ms)}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=1)
    print(json.dumps({k: {kk: v[kk] for kk in ("expected", "missing_s_total", "dup_total", "max_gap_s")} for k, v in out.items() if k != "window_ms"}, ensure_ascii=False))
