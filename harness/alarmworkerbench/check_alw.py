"""알람 워커 벤치 발생기·검사기 (EXP-ALW). 측정 도구이며 솔루션 부품이 아니다.

    python check_alw.py scenario --tag v1_r1          # 결정적 시나리오 알람을 sensor.alerts 파티션 0 에 차례로 → 처리 대기
    python check_alw.py dump --out /experiments/EXP-ALW/raw/dump_x.json
    python check_alw.py load --tag v1_r1 --n 600 --rate 20 --kill-at 300 --worker alwbench-v1-worker-1   (호스트가 kill)
    python check_alw.py compare --a ref.json --b dump.json --out result.json

정답(09-29 지시): 같은 알람 흐름에 대해 V1 과 같은 사건·상관·이벤트·inbox 상태. 재전달(오프셋 되감기) 뒤에도 상태 불변(V1 inbox 표 + 알람 링크).
비교는 UUID·alarm_key(해시)·오류 문구·시각 열을 빼고 한다(구현마다 다를 수 있고 V1 도 실행마다 다름).
사건 식별 = (correlation_key, first_ts). 시나리오 항목마다 label 이 있어 불일치가 어느 경우에서 났는지 보인다(core / edge 구분).
"""
import argparse
import json
import pathlib
import sys
import time

import psycopg
from confluent_kafka import Producer

DSN = "postgresql://ar100:alwbench@work-db:5432/ar100_work"
T = 1_790_000_000_000_000_000
S = 1_000_000_000
TAGS = ["LT-101", "LT-102", "TT-101", "TT-102", "PT-101", "FT-101", "FT-102", "IT-101", "IT-102", "VT-101", "pH-101", "CT-101"]


def A(tag, typ, t_s, sev="WARNING", det="flink-sql", val=9.9, detail=None, **over):
    d = {"ts": T + int(t_s * S), "site": "AR-100", "device": "reactor-line-01", "tag": tag, "value": val,
         "alert_type": typ, "severity": sev, "detector": det, "detail": detail if detail is not None else f"{tag} {typ} @{t_s}"}
    d.update(over)
    return d


def enc(d):
    return json.dumps(d, ensure_ascii=False).encode()


def scenario():
    """[(label, category, raw bytes)] — 순서가 곧 처리 순서(파티션 0)."""
    s = []
    for i, t in enumerate(TAGS):                                   # A: 단독 사건 12(40 s 간격 → 서로 상관 안 됨)
        s.append((f"A.single.{t}", "core", enc(A(t, "THRESHOLD_USL", i * 40))))
    for k, dt in enumerate([0, 5, 10, 15, 20]):                    # B: 같은 서명 반복 → 한 사건, review 불변
        s.append((f"B.repeat.{k}", "core", enc(A("PT-101", "THRESHOLD_USL", 1000 + dt, val=6.1 + k / 10))))
    s.append(("B.gap_new_incident", "core", enc(A("PT-101", "THRESHOLD_USL", 1100, val=6.7))))
    s.append(("B.exact_duplicate", "core", enc(A("PT-101", "THRESHOLD_USL", 1100, val=6.7))))
    s.append(("B.new_signature_severity", "core", enc(A("PT-101", "THRESHOLD_USL", 1101, sev="CRITICAL", val=6.9))))
    s.append(("C.mixer.it102_usl", "core", enc(A("IT-102", "THRESHOLD_USL", 2000, val=9.8))))   # C: 교반기 상관 묶음
    s.append(("C.mixer.vt101_zscore", "core", enc(A("VT-101", "ZSCORE", 2003, det="flink-zscore", val=7.4))))
    s.append(("C.ml_not_mixer", "core", enc(A("IT-102", "ML_AUTOENCODER", 2004, det="onnx", val=0.61))))
    s.append(("C.mixer.it102_cep", "core", enc(A("IT-102", "CEP_BEARING", 2006, sev="CRITICAL", det="flink-cep", val=9.9))))
    s.append(("C.mixer.out_of_order_earlier", "core", enc(A("VT-101", "THRESHOLD_USL", 1990, val=7.2))))
    s.append(("D.bridge.first", "core", enc(A("TT-101", "ZSCORE", 3000, det="flink-zscore"))))   # D: 순서 의존 상관
    s.append(("D.bridge.second_far", "core", enc(A("TT-101", "ZSCORE", 3050, det="flink-zscore"))))
    s.append(("D.bridge.middle_joins_latest", "core", enc(A("TT-101", "ZSCORE", 3025, det="flink-zscore"))))
    base = A("LT-101", "THRESHOLD_LSL", 4000)                       # E: 검증(거부·lax 수용)
    s.append(("E.reject.not_json", "core", b"garbage{"))
    s.append(("E.reject.empty", "core", b""))
    s.append(("E.reject.array", "core", b"[1,2]"))
    s.append(("E.reject.null", "core", b"null"))
    s.append(("E.reject.missing_detail", "core", enc({k: v for k, v in base.items() if k != "detail"})))
    s.append(("E.reject.extra_field", "core", enc(dict(base, seq=1))))
    s.append(("E.reject.value_text", "core", enc(dict(base, value="abc"))))
    s.append(("E.reject.ts_fraction", "core", enc(dict(base, ts=1.5))))
    s.append(("E.reject.ts_negative", "core", enc(dict(base, ts=-5))))
    s.append(("E.reject.ts_zero", "core", enc(dict(base, ts=0))))
    s.append(("E.reject.site_empty", "core", enc(dict(base, site=""))))
    s.append(("E.reject.tag_number", "core", enc(dict(base, tag=123))))
    s.append(("E.reject.detail_too_long", "core", enc(dict(base, detail="x" * 10001))))
    s.append(("E.reject.value_nan", "core", enc(base).replace(b'"value": 9.9', b'"value": NaN')))
    s.append(("E.reject.value_overflow", "core", enc(base).replace(b'"value": 9.9', b'"value": 1e400')))
    s.append(("E.accept.detail_max", "core", enc(dict(A("LT-101", "THRESHOLD_LSL", 4100), detail="y" * 10000))))
    s.append(("E.accept.unicode_detail", "core", enc(A("LT-102", "THRESHOLD_LSL", 4200, detail="반응기 레벨 저하"))))
    s.append(("E.lax.value_numeric_string", "edge", enc(dict(A("FT-101", "THRESHOLD_USL", 4300), value="12.5"))))
    s.append(("E.lax.ts_numeric_string", "edge", enc(dict(A("FT-102", "THRESHOLD_USL", 4400), ts=str(T + 4400 * S)))))
    s.append(("E.lax.value_bool", "edge", enc(dict(A("CT-101", "THRESHOLD_USL", 4500), value=True))))
    s.append(("E.lax.ts_integral_float_big", "edge", enc(dict(A("pH-101", "THRESHOLD_USL", 4600))).replace(
        str(T + 4600 * S).encode(), f"{T + 4600 * S}.0".encode())))
    s.append(("F.redelivered_content", "core", enc(A("PT-101", "THRESHOLD_USL", 1000, val=6.1))))   # B.repeat.0 과 같은 내용
    return s


def wait_processed(n_expected, timeout=300):
    t0 = time.time()
    last, stable = -1, 0
    while time.time() - t0 < timeout:
        try:
            with psycopg.connect(DSN, connect_timeout=3) as c:
                n = c.execute("SELECT count(*) FROM manufacturing_inbox").fetchone()[0]
        except Exception:  # noqa: BLE001 — V1 은 워커가 표를 만들기 전일 수 있다
            n = 0
        if n >= n_expected:
            stable = stable + 1 if n == last else 0
            if stable >= 3:
                return n, round(time.time() - t0, 1)
        last = n
        time.sleep(1)
    return last, None


def produce(items, partition=0, rate=20.0):
    p = Producer({"bootstrap.servers": "kafka:9092", "acks": "all", "enable.idempotence": True, "linger.ms": 0})
    recs = []

    def cb(err, m):
        recs.append({"err": str(err) if err else None, "partition": m.partition(), "offset": m.offset(), "t": time.time_ns()})
    t0 = time.time()
    for i, (label, cat, raw) in enumerate(items):
        key = None
        try:
            key = json.loads(raw).get("tag")
        except Exception:  # noqa: BLE001
            pass
        p.produce("sensor.alerts", value=raw, key=str(key) if key is not None else None, on_delivery=cb,
                  **({"partition": partition} if partition is not None else {}))
        p.poll(0)
        time.sleep(max(0.0, t0 + (i + 1) / rate - time.time()))
    p.flush(30)
    return recs


def dump():
    with psycopg.connect(DSN) as c:
        inc = c.execute("SELECT id, correlation_key, first_ts, last_ts, status, revision, review_revision, alarm_count, site, device, alarm "
                        "FROM manufacturing_incidents").fetchall()
        ident = {r[0]: f"{r[1]}@{r[2]}" for r in inc}

        def core(a):
            return {"ts": int(a["ts"]), "tag": a["tag"], "alert_type": a["alert_type"], "severity": a["severity"],
                    "detector": a["detector"], "detail": a["detail"], "value": float(a["value"]), "site": a["site"], "device": a["device"]}
        incidents = {ident[r[0]]: {"last_ts": r[3], "status": r[4], "revision": r[5], "review_revision": r[6], "alarm_count": r[7],
                                   "site": r[8], "device": r[9], "alarm": core(r[10])} for r in inc}
        events = {}
        for iid, kind, payload in c.execute("SELECT incident_id, kind, payload FROM manufacturing_events ORDER BY id"):
            events.setdefault(ident[iid], []).append([kind, core(payload)])
        links = {}
        for (iid,) in c.execute("SELECT incident_id FROM manufacturing_alarm_links"):
            links[ident[iid]] = links.get(ident[iid], 0) + 1
        inbox = {f"{t}/{p}/{o}": {"status": s, "incident": ident.get(i), "raw_len": len(raw)}
                 for t, p, o, s, i, raw in c.execute("SELECT topic, partition_id, offset_id, status, incident_id, raw_payload FROM manufacturing_inbox")}
    return {"incidents": incidents, "events": events, "links": links, "inbox": inbox}


def compare(a, b, labels=None):
    out = {}
    for sec in ("incidents", "events", "links", "inbox"):
        A_, B_ = a.get(sec, {}), b.get(sec, {})
        only_a = sorted(set(A_) - set(B_))
        only_b = sorted(set(B_) - set(A_))
        diff = sorted(k for k in set(A_) & set(B_) if A_[k] != B_[k])
        item = {"a": len(A_), "b": len(B_), "only_a": len(only_a), "only_b": len(only_b), "different": len(diff),
                "examples": [{"key": k, "a": A_.get(k), "b": B_.get(k)} for k in (only_a + only_b + diff)[:6]]}
        if sec == "inbox" and labels:
            item["by_label"] = {labels.get(k, k): {"a": A_.get(k), "b": B_.get(k)} for k in (only_a + only_b + diff)}
        out[sec] = item
    out["equivalent"] = all(v["only_a"] == 0 and v["only_b"] == 0 and v["different"] == 0 for v in out.values() if isinstance(v, dict))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["scenario", "dump", "load", "compare"])
    ap.add_argument("--tag", default="x")
    ap.add_argument("--out", default="")
    ap.add_argument("--a", default="")
    ap.add_argument("--b", default="")
    ap.add_argument("--n", type=int, default=600)
    ap.add_argument("--rate", type=float, default=20)
    ap.add_argument("--timeout", type=float, default=300)
    a = ap.parse_args()
    raw = pathlib.Path("/experiments/EXP-ALW/raw")
    raw.mkdir(parents=True, exist_ok=True)
    if a.mode == "scenario":
        items = scenario()
        recs = produce(items, partition=0, rate=a.rate)
        labels = {f"sensor.alerts/{r['partition']}/{r['offset']}": f"{it[0]} [{it[1]}]" for it, r in zip(items, sorted(recs, key=lambda r: r["offset"]))}
        n, secs = wait_processed(len(items), a.timeout)
        (raw / f"labels_{a.tag}.json").write_text(json.dumps(labels, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({"produced": len(items), "producer_errors": sum(1 for r in recs if r["err"]), "inbox_rows": n,
                          "processed_in_s": secs}, ensure_ascii=False), flush=True)
        if secs is None:
            sys.exit(8)
    elif a.mode == "dump":
        pathlib.Path(a.out).write_text(json.dumps(dump(), ensure_ascii=False, indent=1, sort_keys=True), encoding="utf-8")
        print("dump", a.out)
    elif a.mode == "compare":
        A_ = json.loads(pathlib.Path(a.a).read_text(encoding="utf-8"))
        B_ = json.loads(pathlib.Path(a.b).read_text(encoding="utf-8"))
        lab = {}
        for f in raw.glob("labels_*.json"):
            lab.update(json.loads(f.read_text(encoding="utf-8")))
        res = compare(A_, B_, lab)
        res.update({"a": a.a, "b": a.b})
        pathlib.Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps({k: (v if not isinstance(v, dict) else {kk: v[kk] for kk in ("only_a", "only_b", "different")})
                          for k, v in res.items() if k in ("incidents", "events", "links", "inbox", "equivalent")}, ensure_ascii=False))
    else:   # load: 유효 알람 n 건(3 파티션, key=tag)을 rate/s 로 → 지연·유실·중복(호스트가 도중에 워커를 죽였다 살림)
        items = []
        for i in range(a.n):
            t = TAGS[i % 12]
            items.append((f"L.{i}", "load", enc(A(t, "THRESHOLD_USL", 10_000 + i * 31, detail=f"load-{a.tag}-{i}"))))
        with psycopg.connect(DSN) as c:
            before = c.execute("SELECT count(*) FROM manufacturing_inbox").fetchone()[0]
        recs = produce(items, partition=None, rate=a.rate)
        n, secs = wait_processed(before + a.n, a.timeout)
        with psycopg.connect(DSN) as c:
            rows = c.execute("SELECT partition_id, offset_id, extract(epoch from created_at)::float8 FROM manufacturing_inbox").fetchall()
            ev_dup = c.execute("SELECT count(*) - count(DISTINCT payload->>'detail') FROM manufacturing_events "
                               "WHERE payload->>'detail' LIKE %s", (f"load-{a.tag}-%",)).fetchone()[0]
            ev_n = c.execute("SELECT count(DISTINCT payload->>'detail') FROM manufacturing_events WHERE payload->>'detail' LIKE %s",
                             (f"load-{a.tag}-%",)).fetchone()[0]
        at = {(p, o): ts for p, o, ts in rows}
        lat = sorted((at[(r["partition"], r["offset"])] * 1e9 - r["t"]) / 1e6 for r in recs if (r["partition"], r["offset"]) in at)
        q = lambda x: round(lat[min(len(lat) - 1, int(round(x * (len(lat) - 1))))], 1) if lat else None  # noqa: E731
        res = {"sent": a.n, "rate": a.rate, "inbox_rows_for_load": sum(1 for r in recs if (r["partition"], r["offset"]) in at),
               "lost": a.n - ev_n, "duplicate_events": ev_dup, "drained_in_s": secs,
               "latency_ms(produce_ack→inbox commit)": {"p50": q(.5), "p95": q(.95), "max": q(1.0)}}
        pathlib.Path(a.out).write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
