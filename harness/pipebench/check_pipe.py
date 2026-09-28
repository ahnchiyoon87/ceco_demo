"""중계 파이프 발생기 + 검사기 (EXP-PIPE). 측정 도구이며 솔루션 부품이 아니다.

같은 입력을 모든 후보에 넣고 V1 세 중계의 결과와 같은지 본다(메시지 충실도·중복·지연).
  입력 A (중계 ①): MQTT edgex/telemetry 에 EdgeX Event v3 를 1 Hz 발행(12 계측 reading, 5건마다 비계측 reading 1개,
                   10건마다 TT-101 센티널 -999999). --shape-in lite 면 V1 lite 경로 모양(iiot/AR-100/reactor-line-01/<tag>, sim.py 와 같은 필드)
  입력 B (중계 ②③): Kafka 에 V1 Flink 출력 모양으로 직접 생산 — clean 12/s, anomaly.score 1/s, alerts --alert-rate/s(detail 에 고유 ID)
  기대(정답은 V1 설정 파일에서 도출):
    ① raw: 계측 12태그 × 이벤트, 센티널·비계측 제외, 레코드 키 정확히 {ts,site,device,tag,value,quality}, ts=reading origin(ns),
           site="AR-100", quality="GOOD", Kafka key = tag
    ② InfluxDB: process(clean)·process_raw(raw)·anomaly·alerts 측정, V1 sink.conf 의 태그·필드 이름과 타입
    ③ MQTT scada/alerts/<tag>: Telegraf JSON {"fields":{"detail","value"},"name":"alert","tags":{6개},"timestamp":ns} 알람당 정확히 1건
       scada/hmi/latest-alert: "MM-DD HH:MM:SS UTC | severity | tag | alert_type" 알람당 1건

    python /repo/harness/pipebench/check_pipe.py --profile v1 --run r1 --duration 120 --out /experiments/EXP-PIPE/stage2_v1.json
"""
import argparse
import bisect
import csv
import io
import json
import pathlib
import threading
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import paho.mqtt.client as mqtt
from confluent_kafka import Consumer, Producer, TopicPartition

TAGS = ["LT-101", "LT-102", "TT-101", "TT-102", "PT-101", "FT-101", "FT-102",
        "IT-101", "IT-102", "VT-101", "pH-101", "CT-101"]
RAW_KEYS = {"ts", "site", "device", "tag", "value", "quality"}
ALERT_TAG_KEYS = ["alert_type", "detector", "device", "severity", "site", "tag"]
INFLUX = "http://influxdb:8086"
TOKEN = "pipebench-token"


def pct(v, q):
    v = sorted(x for x in v if x is not None)
    return round(v[min(len(v) - 1, int(round(q * (len(v) - 1))))], 2) if v else None


def val(i, k):
    """이벤트 i, 태그 k 의 값 — EdgeX "%.7e" 표기로도 정확히 되돌아오는 8자리 이내 수."""
    return round(10.0 * (k + 1) + (i % 100) * 0.01, 2)


class Gen:
    def __init__(self, a):
        self.a = a
        self.expected_raw = {}          # (tag, ts) -> value
        self.filtered = []              # (tag, ts) 가 raw 에 나오면 안 되는 것(센티널·비계측)
        self.event_pub_ns = {}          # ts -> 발행 시각
        self.alerts = {}                # detail -> (dict, produce_ns)
        self.clean = 0
        self.anomaly = 0
        self.prod_err = []

    def run_mqtt(self, stop):
        a = self.a
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"pipegen-{a.run}", protocol=mqtt.MQTTv311)
        c.connect(a.mqtt_host, 1883)
        c.loop_start()
        i = 0
        t0 = time.time()
        while not stop.is_set():
            ts = time.time_ns()
            if a.shape_in == "edgex":
                rd = []
                for k, t in enumerate(TAGS):
                    v = val(i, k)
                    if t == "TT-101" and i % 10 == 0:
                        v = -999999.0
                        self.filtered.append((t, ts))
                    else:
                        self.expected_raw[(t, ts)] = v
                    rd.append({"origin": ts, "deviceName": "reactor-line-01", "resourceName": t, "profileName": "AR100-Reactor-Line",
                               "valueType": "Float32", "units": "", "value": "%.7e" % v})
                if i % 5 == 0:
                    rd.append({"origin": ts, "deviceName": "reactor-line-01", "resourceName": "PumpSpeedSp",
                               "profileName": "AR100-Reactor-Line", "valueType": "Int16", "value": "60"})
                    self.filtered.append(("PumpSpeedSp", ts))
                ev = {"apiVersion": "v3", "id": f"gen-{a.run}-{i}", "deviceName": "reactor-line-01", "profileName": "AR100-Reactor-Line",
                      "sourceName": "AllSensors", "origin": ts, "readings": rd}
                c.publish("edgex/telemetry", json.dumps(ev), qos=1)
            else:   # V1 lite(sim.py _publish 와 같은 필드: seq 포함, 센티널은 발행 안 함)
                for k, t in enumerate(TAGS):
                    v = val(i, k)
                    self.expected_raw[(t, ts)] = v
                    c.publish(f"iiot/AR-100/reactor-line-01/{t}", json.dumps(
                        {"ts": ts, "site": "AR-100", "device": "reactor-line-01", "tag": t, "value": v, "quality": "GOOD", "seq": i}), qos=1)
            self.event_pub_ns[ts] = time.time_ns()
            i += 1
            time.sleep(max(0.0, t0 + i / a.event_rate - time.time()))
        time.sleep(1)
        c.loop_stop()
        c.disconnect()

    def run_kafka(self, stop):
        a = self.a
        p = Producer({"bootstrap.servers": "kafka:9092", "acks": "all", "linger.ms": 5, "enable.idempotence": True})
        err = lambda e, m: self.prod_err.append(str(e)) if e else None   # noqa: E731
        i = 0
        t0 = time.time()
        sev = ["WARNING", "CRITICAL"]
        types = ["THRESHOLD_USL", "THRESHOLD_LSL", "ZSCORE", "CEP_BEARING", "ML_AUTOENCODER"]
        while not stop.is_set():
            ts = time.time_ns()
            for k, t in enumerate(TAGS):
                p.produce("sensor.telemetry.clean", key=t, value=json.dumps(
                    {"ts": ts + k, "site": "AR-100", "device": "reactor-line-01", "tag": t, "value": val(i, k),
                     "quality": "GOOD" if i % 7 else "INTERPOLATED"}), on_delivery=err)
                self.clean += 1
            p.produce("sensor.anomaly.score", key="reactor-line-01", value=json.dumps(
                {"ts": ts, "site": "AR-100", "device": "reactor-line-01", "reconstruction_error": 0.01 * (i % 50),
                 "threshold": 0.35, "inference_ms": 1.25, "is_anomaly": i % 50 > 35, "top_contributors": "pH-101|CT-101"}), on_delivery=err)
            self.anomaly += 1
            for j in range(a.alert_rate):
                tag = TAGS[(i + j) % 12]
                det = f"gen:{a.run}:{i}:{j}"
                d = {"ts": ts + j, "site": "AR-100", "device": "reactor-line-01", "tag": tag, "value": val(i, j),
                     "alert_type": types[(i + j) % 5], "severity": sev[(i + j) % 2], "detector": "pipebench", "detail": det}
                p.produce("sensor.alerts", key=tag, value=json.dumps(d), on_delivery=err)
                self.alerts[det] = (d, time.time_ns())
            p.poll(0)
            i += 1
            time.sleep(max(0.0, t0 + i - time.time()))
        p.flush(30)


def hmi_text(d):
    t = datetime.fromtimestamp(d["ts"] / 1e9, tz=timezone.utc)
    return f'{t.strftime("%m-%d %H:%M:%S")} UTC | {d["severity"]} | {d["tag"]} | {d["alert_type"]}'


def flux(q):
    req = urllib.request.Request(f"{INFLUX}/api/v2/query?org=bench", data=json.dumps({"query": q, "type": "flux"}).encode(),
                                 headers={"Authorization": f"Token {TOKEN}", "Content-Type": "application/json",
                                          "Accept": "application/csv"})
    with urllib.request.urlopen(req, timeout=30) as r:
        txt = r.read().decode()
    rows = []
    for block in txt.split("\r\n\r\n"):
        lines = [ln for ln in block.splitlines() if ln and not ln.startswith("#")]
        if len(lines) > 1:
            rows += list(csv.DictReader(io.StringIO("\n".join(lines))))
    return rows


def rfc(ns):
    return datetime.fromtimestamp(ns / 1e9, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def analyze_relay1(g, raw_rows):
    seen, dup, bad_schema, key_bad, leaks, extra, lat, examples = {}, 0, 0, 0, 0, 0, [], []
    per_tag_order, inv, ts_inexact = {}, 0, 0
    filt = set(g.filtered)
    import bisect
    by_tag = {}
    for (t, ts) in list(g.expected_raw) + list(g.filtered):
        by_tag.setdefault(t, []).append(ts)
    for t in by_tag:
        by_tag[t].sort()

    def resolve(tag, ts):
        """정확히 같은 (tag, ts) 가 없으면 ±2 µs 안의 발생 ts 로 맞춘다(JSON 숫자를 float64 로 다루면 ns 끝자리가 256 ns 단위로 뭉개짐)."""
        try:
            ts_i = ts if isinstance(ts, int) else int(round(float(ts)))
        except (TypeError, ValueError):
            return (tag, ts), False
        lst = by_tag.get(tag, [])
        j = bisect.bisect_left(lst, ts_i)
        for c in (j - 1, j):
            if 0 <= c < len(lst) and abs(lst[c] - ts_i) <= 2000:
                return (tag, lst[c]), lst[c] != ts_i or not isinstance(ts, int)
        return (tag, ts_i), False
    for recv, part, key, v in raw_rows:
        try:
            d = json.loads(v)
        except (ValueError, TypeError):
            bad_schema += 1
            if len(examples) < 5:
                examples.append({"unparsable": (v or b"")[:200].decode(errors="replace")})
            continue
        if not isinstance(d, dict):
            bad_schema += 1
            continue
        k, inexact = resolve(d.get("tag"), d.get("ts"))
        ts_inexact += inexact
        if set(d) != RAW_KEYS or d.get("site") != "AR-100" or d.get("quality") != "GOOD" or not isinstance(d.get("ts"), int) \
                or not isinstance(d.get("value"), (int, float)):
            bad_schema += 1
            if len(examples) < 5:
                examples.append({"record": {kk: d.get(kk) for kk in list(d)[:10]}, "keys": sorted(d)})
        if key != str(d.get("tag")):
            key_bad += 1
        if k in filt:
            leaks += 1
            continue
        if k not in g.expected_raw:
            extra += 1
            continue
        if k in seen:
            dup += 1
            continue
        seen[k] = recv
        ev_pub = g.event_pub_ns.get(k[1])
        if ev_pub:
            lat.append((recv - ev_pub) / 1e6)
        if abs(float(d["value"]) - g.expected_raw[k]) > 1e-6:
            bad_schema += 1
        last = per_tag_order.get(k[0])
        if last is not None and k[1] < last:
            inv += 1
        per_tag_order[k[0]] = max(last or 0, k[1])
    lost = [k for k in g.expected_raw if k not in seen]
    return {
        "expected": len(g.expected_raw), "received_unique": len(seen), "lost": len(lost), "duplicates": dup,
        "unexpected_records": extra, "filter_leaks(sentinel/non-sensor)": leaks, "schema_or_value_mismatch": bad_schema,
        "kafka_key_not_tag": key_bad, "ts_not_exact_ns(float64 등)": ts_inexact, "order_inversions_per_tag": inv, "partitions_used": sorted({r[1] for r in raw_rows}),
        "latency_ms": {"p50": pct(lat, .5), "p95": pct(lat, .95), "max": pct(lat, 1)}, "examples": examples,
        "raw_records_total": len(raw_rows)}


def analyze_relay3(g, mq_rows):
    per, hmi, bad, topic_bad, lat, examples = {}, [], 0, 0, [], []
    for recv, topic, payload, retain in mq_rows:
        if topic == "scada/hmi/latest-alert":
            hmi.append(payload.decode(errors="replace"))
            continue
        try:
            d = json.loads(payload)
            det = d["fields"]["detail"]
        except (ValueError, KeyError, TypeError):
            bad += 1
            if len(examples) < 5:
                examples.append(payload[:300].decode(errors="replace"))
            continue
        if det not in g.alerts:
            continue
        exp, prod_ns = g.alerts[det]
        per[det] = per.get(det, 0) + 1
        if per[det] == 1:
            lat.append((recv - prod_ns) / 1e6)
        want = {"fields": {"detail": exp["detail"], "value": float(exp["value"])}, "name": "alert",
                "tags": {k: exp[k] for k in ALERT_TAG_KEYS}, "timestamp": exp["ts"]}
        got = {"fields": {"detail": d.get("fields", {}).get("detail"), "value": d.get("fields", {}).get("value")},
               "name": d.get("name"), "tags": d.get("tags"), "timestamp": d.get("timestamp")}
        if got != want or set(d) != {"fields", "name", "tags", "timestamp"}:
            bad += 1
            if len(examples) < 5:
                examples.append({"got": d, "want": want})
        if topic != f"scada/alerts/{exp['tag']}":
            topic_bad += 1
    exp_hmi = sorted(hmi_text(d) for d, _ in g.alerts.values())
    got_hmi = sorted(h for h in hmi if h in set(exp_hmi))
    return {
        "alerts_expected": len(g.alerts), "received_unique": len(per), "lost": len([d for d in g.alerts if d not in per]),
        "duplicates": sum(v - 1 for v in per.values()), "shape_mismatch": bad, "topic_mismatch": topic_bad,
        "hmi_expected": len(exp_hmi), "hmi_matching": len(got_hmi), "hmi_total_received": len(hmi),
        "hmi_examples": hmi[:3], "latency_ms": {"p50": pct(lat, .5), "p95": pct(lat, .95), "max": pct(lat, 1)}, "examples": examples}


def fault_windows(g, raw_rows, mq_rows, fs, fe, kind, influx_found, influx_seen):
    """4단계: 사건 구간 [fs, fe) 에 만들어진 입력의 유실·중복과 사건 뒤 복구(첫 전달까지 초)·최대 전달 공백."""
    fs_ns, fe_ns = int(fs * 1e9), int(fe * 1e9)
    out = {"kind": kind, "start": fs, "end": fe, "seconds": round(fe - fs, 1)}
    # ① raw: 구간에 발행된 이벤트의 계측 레코드
    got = {}
    for recv, _p, _k, v in raw_rows:
        try:
            d = json.loads(v)
        except (ValueError, TypeError):
            continue
        if isinstance(d, dict):
            k = (d.get("tag"), d.get("ts") if isinstance(d.get("ts"), int) else None)
            got.setdefault(k, []).append(recv)
    win_keys = [k for k in g.expected_raw if fs_ns <= g.event_pub_ns.get(k[1], 0) < fe_ns]
    after = sorted(r for r, *_ in raw_rows if r >= fe_ns)
    arr = sorted(r for r, *_ in raw_rows)
    out["relay1"] = {"expected_in_window": len(win_keys), "lost_in_window": sum(1 for k in win_keys if k not in got),
                     "dup_in_window": sum(len(got[k]) - 1 for k in win_keys if k in got),
                     "first_record_after_end_s": round((after[0] - fe_ns) / 1e9, 2) if after else None,
                     "max_arrival_gap_s": round(max((b - x) / 1e9 for x, b in zip(arr, arr[1:])), 2) if len(arr) > 1 else None}
    wa = [d for d, (_a, p) in g.alerts.items() if fs_ns <= p < fe_ns]
    if influx_found is not None:
        f = set(influx_found)
        seen_after = sorted(t for d, t in influx_seen.items() if t >= fe_ns)
        out["relay2"] = {"alerts_in_window": len(wa), "lost_in_window": sum(1 for d in wa if d not in f),
                         "first_seen_after_end_s": round((seen_after[0] - fe_ns) / 1e9, 2) if seen_after else None,
                         "note": "R06: 다운 중 알람이 복구 후 적재됐는가(쓰기 버퍼) = lost_in_window"}
    per = {}
    for recv, topic, payload, _r in mq_rows:
        if topic.startswith("scada/alerts/"):
            try:
                per.setdefault(json.loads(payload)["fields"]["detail"], []).append(recv)
            except (ValueError, KeyError, TypeError):
                pass
    m_after = sorted(t for v in per.values() for t in v if t >= fe_ns)
    out["relay3"] = {"alerts_in_window": len(wa), "lost_in_window": sum(1 for d in wa if d not in per),
                     "dup_in_window": sum(len(per[d]) - 1 for d in wa if d in per),
                     "first_mqtt_after_end_s": round((m_after[0] - fe_ns) / 1e9, 2) if m_after else None}
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--duration", type=float, default=120)
    ap.add_argument("--settle", type=float, default=20, help="발생 종료 후 수집 대기")
    ap.add_argument("--mqtt-host", default="emqx", help="입력 A 발행 + 중계 ③ 구독 브로커(P-C 는 rmqtt/tbmq)")
    ap.add_argument("--shape-in", default="edgex", choices=["edgex", "lite"])
    ap.add_argument("--alert-rate", type=int, default=2)
    ap.add_argument("--relays", default="1,2,3")
    ap.add_argument("--event-rate", type=float, default=1.0, help="입력 A EdgeX 이벤트/s(R08 과부하 = 10)")
    ap.add_argument("--fault-file", default="", help="4단계: 호스트가 쓴 'start end kind' (epoch 초)")
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise SystemExit(f"{out} 이미 있음 — 새 run ID 로")
    relays = set(a.relays.split(","))

    # ── 수집기 준비: raw 소비(시작 시점 끝 오프셋부터), 중계 ③ 구독 ──
    cons = Consumer({"bootstrap.servers": "kafka:9092", "group.id": f"pipecheck-{a.profile}-{a.run}", "enable.auto.commit": False})
    md = cons.list_topics("sensor.telemetry.raw", timeout=10)
    parts = sorted(md.topics["sensor.telemetry.raw"].partitions)
    cons.assign([TopicPartition("sensor.telemetry.raw", p, cons.get_watermark_offsets(TopicPartition("sensor.telemetry.raw", p), timeout=10)[1])
                 for p in parts])
    raw_rows, stop_c = [], threading.Event()

    def consume():
        while not stop_c.is_set():
            m = cons.poll(0.5)
            if m is None or m.error():
                continue
            raw_rows.append((time.time_ns(), m.partition(), (m.key() or b"").decode(errors="replace"), m.value()))
    tc = threading.Thread(target=consume, daemon=True)
    tc.start()

    mq_rows, sub_ok = [], threading.Event()
    s = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"pipecheck-{a.run}", protocol=mqtt.MQTTv311)
    s.reconnect_delay_set(1, 1)          # R01: 브로커 복귀 직후 바로 재구독(재구독 전 발행분은 검사기 쪽 공백 — FUXA 와 같은 조건)
    s.on_connect = lambda c, u, f, rc, p=None: (c.subscribe([("scada/alerts/+", 1), ("scada/hmi/latest-alert", 1)]), sub_ok.set())
    s.on_message = lambda c, u, m: mq_rows.append((time.time_ns(), m.topic, m.payload, m.retain))
    s.connect_async(a.mqtt_host, 1883)
    s.loop_start()
    sub_ok.wait(30)

    influx_seen, stop_i = {}, threading.Event()

    def poll_influx():
        while not stop_i.is_set():
            try:
                rows = flux('from(bucket:"process") |> range(start: -60s) |> filter(fn:(r) => r._measurement == "alerts" and r._field == "detail")'
                            ' |> keep(columns:["_value"])')
                now = time.time_ns()
                for r in rows:
                    influx_seen.setdefault(r.get("_value"), now)
            except Exception:  # noqa: BLE001
                pass
            time.sleep(1)
    ti = threading.Thread(target=poll_influx, daemon=True)
    if "2" in relays:
        ti.start()

    # ── 발생 ──
    g = Gen(a)
    stop_g = threading.Event()
    t_start = time.time_ns()
    th = [threading.Thread(target=g.run_mqtt, args=(stop_g,)), threading.Thread(target=g.run_kafka, args=(stop_g,))]
    for t in th:
        t.start()
    time.sleep(a.duration)
    stop_g.set()
    for t in th:
        t.join()
    t_gen_end = time.time_ns()
    time.sleep(a.settle)
    stop_c.set()
    stop_i.set()
    tc.join(5)
    s.loop_stop()
    s.disconnect()
    cons.close()

    res = {"exp": "EXP-PIPE", "profile": a.profile, "run": a.run, "duration": a.duration, "shape_in": a.shape_in,
           "relays_checked": sorted(relays), "generator": {"events": len(g.event_pub_ns), "expected_raw": len(g.expected_raw),
                                                             "filtered_expected_absent": len(g.filtered), "clean": g.clean,
                                                             "anomaly": g.anomaly, "alerts": len(g.alerts), "producer_errors": g.prod_err[:5]},
           "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}

    # ── 중계 ① ──
    if "1" in relays:
        res["relay1_mqtt_to_kafka_raw"] = analyze_relay1(g, raw_rows)

    # ── 중계 ② ──
    if "2" in relays:
        start, stop = rfc(t_start - 5_000_000_000), rfc(t_gen_end + 5_000_000_000)
        r2 = {}
        try:
            for m in ("process", "process_raw", "anomaly", "alerts"):
                rows = flux(f'from(bucket:"process") |> range(start: {start}, stop: {stop}) |> filter(fn:(r) => r._measurement == "{m}")'
                            ' |> group(columns:["_field"]) |> count()')
                cnt = {r["_field"]: int(r["_value"]) for r in rows}
                keys = flux(f'import "influxdata/influxdb/schema"\nschema.tagKeys(bucket:"process", predicate:(r) => r._measurement == "{m}",'
                            f' start: {start}, stop: {stop})')
                r2[m] = {"field_counts": cnt, "tag_keys": sorted(r["_value"] for r in keys if not r["_value"].startswith("_"))}
            det = flux(f'from(bucket:"process") |> range(start: {start}, stop: {stop}) |> filter(fn:(r) => r._measurement == "alerts"'
                       ' and r._field == "detail") |> keep(columns:["_value","_time","tag","severity","alert_type","detector"])')
            got = {r["_value"]: r for r in det}
            lost = [d for d in g.alerts if d not in got]
            tag_bad = sum(1 for dname, r in got.items() if dname in g.alerts and
                          any(r.get(k) != g.alerts[dname][0][k] for k in ("tag", "severity", "alert_type", "detector")))
            lat = [(influx_seen[d] - g.alerts[d][1]) / 1e6 for d in g.alerts if d in influx_seen]
            raw_count = res.get("relay1_mqtt_to_kafka_raw", {}).get("raw_records_total")
            r2["_found_details"] = sorted(d for d in got if d in g.alerts)
            r2.update({"alerts_expected": len(g.alerts), "alerts_found": len([d for d in got if d in g.alerts]), "alerts_lost": len(lost),
                       "alerts_tag_mismatch": tag_bad, "clean_expected": g.clean, "anomaly_expected": g.anomaly,
                       "process_raw_vs_raw_topic": {"influx_value_count": r2["process_raw"]["field_counts"].get("value"), "raw_topic_records": raw_count},
                       "expected_schema": {"process": {"tags": ["device", "quality", "site", "tag"], "fields": ["value"]},
                                           "anomaly": {"tags": ["device", "site", "top_contributors"],
                                                       "fields": ["inference_ms", "is_anomaly", "reconstruction_error", "threshold"]},
                                           "alerts": {"tags": ["alert_type", "detector", "device", "severity", "site", "tag"], "fields": ["detail", "value"]}},
                       "latency_ms(1s poll)": {"p50": pct(lat, .5), "p95": pct(lat, .95), "max": pct(lat, 1), "n": len(lat)}})
        except Exception as e:  # noqa: BLE001
            r2["error"] = f"{type(e).__name__}: {e}"[:300]
        res["relay2_kafka_to_influx"] = r2

    # ── 중계 ③ ──
    if "3" in relays:
        res["relay3_kafka_to_mqtt"] = analyze_relay3(g, mq_rows)

    if a.fault_file and pathlib.Path(a.fault_file).exists():
        parts = pathlib.Path(a.fault_file).read_text().split()
        res["fault"] = fault_windows(g, raw_rows, mq_rows, float(parts[0]), float(parts[1]), " ".join(parts[2:]),
                                     res.get("relay2_kafka_to_influx", {}).get("_found_details"), influx_seen)
    res.get("relay2_kafka_to_influx", {}).pop("_found_details", None)
    res["event_rate"] = a.event_rate
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    brief = {k: {kk: v.get(kk) for kk in ("expected", "alerts_expected", "received_unique", "alerts_found", "lost", "alerts_lost",
                                          "duplicates", "schema_or_value_mismatch", "shape_mismatch") if kk in v}
             for k, v in res.items() if k.startswith("relay")}
    print(json.dumps(brief, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
