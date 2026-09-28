"""수집 층 검사기 (EXP-ING). 측정 도구이며 솔루션 부품이 아니다.

후보 수집기가 MQTT 로 발행한 메시지를 구독하면서, 같은 시간 가상설비 HTTP /state 를 0.1초마다 읽어
"12태그가 매초 도착하는가 · 값이 설비 값과 같은가 · 얼마나 빠른가 · V1 하류가 그대로 받는가"를 잰다.

    python /repo/harness/ingestbench/check_ingest.py --profile telegraf --run r1 --duration 120 \
        --out /experiments/EXP-ING/stage2_telegraf_r1.json

판정 재료(결과 JSON)
- completeness : 태그별 기대 샘플(창 길이 s × 1 Hz) 대비 고유 (tag, origin) 수, 결측(간격 기반), 최대 간격,
                 초 단위 12태그 완전 비율(참고, 폴링 위상 흔들림에 민감), 중복(tag, origin 동일), 근접 중복(0.5 s 안 재폴링)
- values       : 태그 값이 최근 설비 스냅숏(seq) 중 하나와 허용오차 안에서 일치하는 비율, 불일치 예, seq 지연 분포
- latency      : 수신 − origin(수집기 시각) p50/p95, 수신 − 설비 값 변경 최초 관측(값 신선도, 0.1 s 폴링 해상도) p50/p95
- throughput   : MQTT 메시지/s, reading/s
- shape        : V1 EdgeX Event v3 필수 키 충족 여부, 메시지당 reading 수, value 타입(문자열/숫자)
- downstream   : 하류 파서(V1 Telegraf#1 원문 또는 후보별 적응 설정) 출력과 후보 reading 1:1 대조 — "결과 동등"(09-29 결정)
- faults(4단계): --fault-start/--fault-end(호스트 epoch 초) 구간 기준 유실·재전송(backfill)·동결값·센티널·복구 시간·순서 역전
"""
import argparse
import json
import math
import pathlib
import statistics
import threading
import time
import urllib.request

import paho.mqtt.client as mqtt

TAGS = ["LT-101", "LT-102", "TT-101", "TT-102", "PT-101", "FT-101", "FT-102",
        "IT-101", "IT-102", "VT-101", "pH-101", "CT-101"]
TAGSET = set(TAGS)
BAD_QUALITY = -999998.0          # 시뮬레이터 센티널(-999999) 판정선 — V1 Telegraf#1 과 같은 값
EDGEX_EVENT_KEYS = ["apiVersion", "deviceName", "profileName", "sourceName", "origin", "readings"]
EDGEX_READING_KEYS = ["origin", "deviceName", "resourceName", "profileName", "valueType", "value"]


def pct(v, q):
    v = sorted(x for x in v if x is not None)
    return round(v[min(len(v) - 1, int(round(q * (len(v) - 1))))], 2) if v else None


def to_ns(t):
    """origin/timestamp 단위 추정 → ns. 숫자·숫자 문자열만."""
    try:
        t = float(t)
    except (TypeError, ValueError):
        return None
    if t > 1e17:
        return int(t)
    if t > 1e14:
        return int(t * 1e3)        # µs
    if t > 1e11:
        return int(t * 1e6)        # ms
    if t > 1e8:
        return int(t * 1e9)        # s
    return None


def fnum(v):
    try:
        f = float(v)
        return f if math.isfinite(f) else None
    except (TypeError, ValueError):
        return None


# ── 모양별 파서: (readings[(tag, value, origin_ns)], shape_notes{}) ─────────────────────────────
def parse_edgex(topic, d):
    notes = {}
    if not isinstance(d, dict) or not isinstance(d.get("readings"), list):
        return [], {"not_edgex_event": 1}
    for k in EDGEX_EVENT_KEYS:
        if k not in d:
            notes[f"event_missing:{k}"] = 1
    out = []
    ev_origin = to_ns(d.get("origin"))
    for r in d["readings"]:
        if not isinstance(r, dict):
            notes["reading_not_object"] = notes.get("reading_not_object", 0) + 1
            continue
        for k in EDGEX_READING_KEYS:
            if k not in r:
                notes[f"reading_missing:{k}"] = notes.get(f"reading_missing:{k}", 0) + 1
        if "value" in r and not isinstance(r["value"], str):
            notes["value_not_string"] = notes.get("value_not_string", 0) + 1
        out.append((r.get("resourceName"), fnum(r.get("value")), to_ns(r.get("origin")) or ev_origin))
    return out, notes


def parse_neuron(topic, d):
    if not isinstance(d, dict) or not isinstance(d.get("values"), dict):
        return [], {"not_neuron_values": 1}
    ts = to_ns(d.get("timestamp"))
    out = [(k, fnum(v), ts) for k, v in d["values"].items()]
    notes = {"shape": "neuron-values"}
    if d.get("errors"):
        notes["neuron_errors"] = len(d["errors"])
        out += [(k, None, ts) for k in d["errors"]]
    return out, notes


def parse_hivemq_edge(topic, d):
    tag = topic.rsplit("/", 1)[-1]
    if isinstance(d, dict) and "value" in d:
        return [(d.get("tagName", tag), fnum(d["value"]), to_ns(d.get("timestamp")))], {"shape": "hivemq-edge"}
    if isinstance(d, dict) and isinstance(d.get("tags"), list):
        return [(x.get("tagName", tag), fnum(x.get("value")), to_ns(x.get("timestamp"))) for x in d["tags"]], {"shape": "hivemq-edge-tags"}
    return [], {"not_hivemq_edge": 1}


def parse_tbgw(topic, d):
    out = []
    if isinstance(d, dict):
        for dev, rows in d.items():
            for row in rows if isinstance(rows, list) else []:
                ts = to_ns(row.get("ts"))
                vals = row.get("values", row) if isinstance(row, dict) else {}
                out += [(k, fnum(v), ts) for k, v in vals.items() if k in TAGSET]
    return out, ({"shape": "tb-gateway"} if out else {"not_tbgw": 1})


def parse_openremote(topic, d):
    """OpenRemote 속성 이벤트 {ref:{id,name}, value, timestamp(ms)} — 토픽 master/<cid>/attribute/<속성>/<자산>."""
    if isinstance(d, dict) and "value" in d:
        parts = topic.split("/")
        tag = (d.get("ref") or {}).get("name") or (parts[3] if len(parts) >= 5 else None)
        return [(tag, fnum(d["value"]), to_ns(d.get("timestamp")))], {"shape": "openremote"}
    return [], {"not_openremote": 1}


def parse_auto(topic, d):
    """모양을 모를 때(P3 UI 설정 후보): JSON 안에서 태그 이름 키와 수치 값을 찾는다."""
    for p in (parse_edgex, parse_neuron, parse_tbgw, parse_hivemq_edge):
        out, notes = p(topic, d)
        if out and any(t in TAGSET for t, _, _ in out):
            return out, notes
    found, ts = [], None

    def walk(x):
        nonlocal ts
        if isinstance(x, dict):
            for k, v in x.items():
                if k in TAGSET and fnum(v) is not None:
                    found.append((k, fnum(v)))
                elif k.lower() in ("ts", "timestamp", "time", "origin") and ts is None:
                    ts = to_ns(v)
                else:
                    walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(d)
    return [(k, v, ts) for k, v in found], {"shape": "auto"}


PARSERS = {"edgex": parse_edgex, "neuron": parse_neuron, "hivemq-edge": parse_hivemq_edge,
           "tbgw": parse_tbgw, "openremote": parse_openremote, "auto": parse_auto}


class StatePoller(threading.Thread):
    """가상설비 /state 를 주기적으로 읽어 seq → (값, 최초 관측 ns) 기록. 실패(설비 멈춤)도 기록."""

    def __init__(self, url, period):
        super().__init__(daemon=True)
        self.url, self.period = url, period
        self.snaps = {}          # seq -> (readings, first_seen_ns)
        self.order = []          # (first_seen_ns, seq)
        self.errors = []         # ns
        self.stop = threading.Event()

    def run(self):
        while not self.stop.is_set():
            t = time.time()
            try:
                with urllib.request.urlopen(self.url, timeout=1) as r:
                    s = json.loads(r.read())
                seq = s["seq"]
                if seq not in self.snaps:
                    now = time.time_ns()
                    self.snaps[seq] = (s["readings"], now)
                    self.order.append((now, seq))
            except Exception:  # noqa: BLE001 — 설비 멈춤(R11)은 결과로 기록
                self.errors.append(time.time_ns())
            time.sleep(max(0.0, self.period - (time.time() - t)))


def match_value(poller, tag, value, recv_ns, tol_abs, tol_rel, lookback=6):
    """recv 시점까지 관측된 최근 lookback 개 스냅숏 중 일치하는 것. 반환 (matched, seq_lag, age_ms, kind)."""
    import bisect
    idx = bisect.bisect_right(poller.order, (recv_ns + 50_000_000, float("inf")))   # 폴링 해상도 여유 50 ms
    cands = poller.order[max(0, idx - lookback):idx][::-1]
    if not cands:
        return None, None, None, "no_state"
    latest_seq = cands[0][1]
    for first_ns, seq in cands:
        s = poller.snaps[seq][0].get(tag)
        if value is not None and value <= BAD_QUALITY:
            if s is None:
                return True, latest_seq - seq, (recv_ns - first_ns) / 1e6, "sentinel"
            continue
        if s is None or value is None:
            continue
        if abs(value - s) <= max(tol_abs, tol_rel * abs(s)):
            return True, latest_seq - seq, (recv_ns - first_ns) / 1e6, "value"
    return False, None, None, "mismatch"


def read_downstream(path, t0_ns, t1_ns, win):
    """하류 파서 출력(raw 레코드 JSON lines)과 후보 발행 reading 을 1:1 대조 — 09-29 결정 "결과 동등".
    동등 = 창 안 후보 reading(12태그, 센티널 제외)마다 같은 (tag, ts) 레코드가 정확히 1건, 값 차이 ≤ 1e-6 상대, 여분 없음."""
    p = pathlib.Path(path) if path else None
    if not p or not p.exists():
        return {"file": path, "present": False, "equivalent": False}
    recs, bad = {}, 0
    dup = 0
    keys = set()
    for line in p.read_text(encoding="utf-8", errors="replace").splitlines():
        try:
            r = json.loads(line)
        except ValueError:
            bad += 1
            continue
        ts = to_ns(r.get("ts"))
        if ts is None or not (t0_ns <= ts < t1_ns):
            continue
        k = (r.get("tag"), ts)
        dup += k in recs
        recs[k] = r
        keys.add(tuple(sorted(r)))
    want = {(r["tag"], r["t"]): r["value"] for r in win
            if r["tag"] in TAGSET and r["value"] is not None and r["value"] > BAD_QUALITY and r["origin"]}
    missing = [k for k in want if k not in recs]
    extra = [k for k in recs if k not in want]
    vbad = sum(1 for k, v in want.items() if k in recs and abs(float(recs[k].get("value", "nan")) - v) > max(1e-9, 1e-6 * abs(v)))
    schema_bad = sum(1 for r in recs.values() if set(r) != {"ts", "site", "device", "tag", "value", "quality"}
                     or r.get("site") != "AR-100" or r.get("quality") != "GOOD" or r.get("device") != "reactor-line-01")
    per_tag = {}
    for (t, _), _r in recs.items():
        per_tag[t] = per_tag.get(t, 0) + 1
    return {"file": path, "present": True, "records_in_window": len(recs), "expected_from_candidate": len(want),
            "missing": len(missing), "extra": len(extra), "duplicates": dup, "value_mismatch": vbad,
            "schema_mismatch": schema_bad, "record_keys": [list(k) for k in keys], "unparsable_lines": bad,
            "per_tag": per_tag, "missing_examples": [list(map(str, k)) for k in missing[:5]],
            "equivalent": bool(want) and not missing and not extra and not dup and not vbad and not schema_bad,
            "note": "후보 발행에 origin(원천 시각)이 없으면 비교 불가(expected_from_candidate=0) → equivalent=false"}


def analyse(a, msgs, poller, t_start, t_end):
    parser = PARSERS[a.shape]
    t0 = t_start + a.warmup
    t1 = t_end - 2
    t0_ns, t1_ns = int(t0 * 1e9), int(t1 * 1e9)
    notes, rd, unparsable, per_msg_counts = {}, [], 0, []
    for recv_ns, topic, payload in msgs:
        try:
            d = json.loads(payload)
        except ValueError:
            unparsable += 1
            continue
        out, n = parser(topic, d)
        for k, v in n.items():
            if isinstance(v, int):
                notes[k] = notes.get(k, 0) + v
            else:
                notes[k] = v
        per_msg_counts.append(len(out))
        for tag, value, origin in out:
            rd.append({"tag": tag, "value": value, "origin": origin, "recv": recv_ns})
    # 창 안(수신 시각 기준 선택 → origin 기준 버킷). origin 이 없으면 수신 시각을 쓴다.
    win = [r for r in rd if t0_ns <= r["recv"] < t1_ns + 5_000_000_000]
    for r in win:
        r["t"] = r["origin"] if r["origin"] else r["recv"]
    win = [r for r in win if t0_ns <= r["t"] < t1_ns]
    window_s = (t1_ns - t0_ns) / 1e9
    unknown_tags = sorted({str(r["tag"]) for r in win if r["tag"] not in TAGSET})
    per_tag = {}
    for t in TAGS:
        rows = sorted((r for r in win if r["tag"] == t), key=lambda r: r["t"])
        uniq = {}
        for r in rows:
            uniq.setdefault(r["t"], 0)
            uniq[r["t"]] += 1
        ts = sorted(uniq)
        gaps = [(b - x) / 1e9 for x, b in zip(ts, ts[1:])]
        edge = [(ts[0] - t0_ns) / 1e9, (t1_ns - ts[-1]) / 1e9] if ts else [window_s, 0]
        missing = (sum(max(0, round(g) - 1) for g in gaps if g > 1.5) + sum(max(0, math.floor(e + 0.5) - 1) for e in edge if e > 1.5)
                   if ts else round(window_s))
        per_tag[t] = {"unique": len(ts), "expected": round(window_s), "missing_gap_based": int(missing),
                      "duplicates": sum(c - 1 for c in uniq.values()),
                      "near_duplicates": sum(1 for g in gaps if g < 0.5),
                      "max_gap_s": round(max(gaps + edge), 2) if ts else None}
    buckets = {}
    for r in win:
        if r["tag"] in TAGSET:
            buckets.setdefault(r["t"] // 1_000_000_000, set()).add(r["tag"])
    secs = range(t0_ns // 1_000_000_000, t1_ns // 1_000_000_000)
    complete = sum(1 for s in secs if len(buckets.get(s, ())) == 12)
    # 값 비교
    vres = {"checked": 0, "matched": 0, "mismatch": 0, "no_state": 0, "sentinel": 0, "none_value": 0}
    lags, ages, examples = [], [], []
    for r in win:
        if r["tag"] not in TAGSET:
            continue
        if r["value"] is None:
            vres["none_value"] += 1
            continue
        ok, lag, age, kind = match_value(poller, r["tag"], r["value"], r["recv"], a.tol_abs, a.tol_rel)
        vres["checked"] += 1
        if kind == "no_state":
            vres["no_state"] += 1
        elif ok:
            vres["matched"] += 1
            vres["sentinel"] += kind == "sentinel"
            lags.append(lag)
            ages.append(age)
        else:
            vres["mismatch"] += 1
            if len(examples) < 8:
                examples.append({"tag": r["tag"], "value": r["value"], "recv_ns": r["recv"]})
    vres["match_rate"] = round(vres["matched"] / max(1, vres["checked"] - vres["no_state"]), 5)
    vres["seq_lag_hist"] = {str(k): lags.count(k) for k in sorted(set(lags))}
    vres["mismatch_examples"] = examples
    lat = [(r["recv"] - r["origin"]) / 1e6 for r in win if r["origin"]]
    tot_unique = sum(v["unique"] for v in per_tag.values())
    res = {
        "window": {"t0": t0, "t1": t1, "seconds": round(window_s, 1)},
        "throughput": {"messages": sum(1 for m in msgs if t0_ns <= m[0] < t1_ns),
                       "msgs_per_s": round(sum(1 for m in msgs if t0_ns <= m[0] < t1_ns) / window_s, 2),
                       "readings_per_s": round(len(win) / window_s, 2)},
        "completeness": {"expected_samples": 12 * round(window_s), "unique_samples": tot_unique,
                         "missing_gap_based": sum(v["missing_gap_based"] for v in per_tag.values()),
                         "duplicates": sum(v["duplicates"] for v in per_tag.values()),
                         "near_duplicates": sum(v["near_duplicates"] for v in per_tag.values()),
                         "complete_second_ratio": round(complete / max(1, len(secs)), 4),
                         "all_12_tags_present": all(per_tag[t]["unique"] > 0 for t in TAGS),
                         "unknown_tags": unknown_tags, "per_tag": per_tag},
        "values": vres,
        "latency_ms": {"recv_minus_origin": {"p50": pct(lat, .5), "p95": pct(lat, .95), "max": pct(lat, 1),
                                             "n": len(lat), "note": "origin 은 수집기 시각(도커 VM 같은 시계)"},
                       "value_age": {"p50": pct(ages, .5), "p95": pct(ages, .95), "max": pct(ages, 1),
                                     "note": "설비 값 변경 최초 관측(0.1 s 폴링) → MQTT 수신. 폴링 주기 위상 포함"}},
        "shape": {"parser": a.shape, "notes": notes, "unparsable_messages": unparsable,
                  "readings_per_message": {"p50": pct(per_msg_counts, .5), "min": min(per_msg_counts) if per_msg_counts else None,
                                           "max": max(per_msg_counts) if per_msg_counts else None},
                  "v1_edgex_shape": a.shape == "edgex" and not any(k.startswith(("event_missing", "reading_missing", "not_edgex")) for k in notes)},
        "state_poll": {"snapshots": len(poller.snaps), "errors": len(poller.errors)},
        "downstream": read_downstream(a.downstream, t0_ns, t1_ns, win),
    }
    if a.fault_start:
        res["faults"] = fault_analysis(a, rd, poller)
    return res


def fault_analysis(a, rd, poller):
    """4단계: 구간 [fs, fe) 동안의 유실·재전송·동결·센티널·복구."""
    fs, fe = int(a.fault_start * 1e9), int(a.fault_end * 1e9)
    dur = (fe - fs) / 1e9
    out = {"fault_start": a.fault_start, "fault_end": a.fault_end, "seconds": round(dur, 1), "kind": a.fault_kind}
    for r in rd:
        r.setdefault("t", r["origin"] if r["origin"] else r["recv"])
    inwin = [r for r in rd if r["tag"] in TAGSET and fs <= r["t"] < fe]
    uniq = {(r["tag"], r["t"]) for r in inwin}
    backfill = [r for r in inwin if r["recv"] >= fe]
    out["expected_samples_in_fault"] = 12 * round(dur)
    out["unique_samples_with_origin_in_fault"] = len(uniq)
    out["delivered_after_fault_end(backfill)"] = len({(r["tag"], r["t"]) for r in backfill})
    out["lost_estimate"] = max(0, 12 * round(dur) - len(uniq))
    out["sentinel_values_in_fault"] = sum(1 for r in inwin if r["value"] is not None and r["value"] <= BAD_QUALITY)
    # 동결값: 구간 중 발행된 값이 구간 직전 마지막 값과 정확히 같다(설비는 노이즈로 매초 바뀐다)
    frozen = 0
    for t in TAGS:
        pre = [r for r in rd if r["tag"] == t and r["t"] < fs]
        last = max(pre, key=lambda r: r["t"])["value"] if pre else None
        frozen += sum(1 for r in inwin if r["tag"] == t and last is not None and r["value"] == last)
    out["frozen_repeats_in_fault"] = frozen
    # 복구: 구간 끝 이후 설비 최신 값과 일치하는 첫 수신
    after = sorted((r for r in rd if r["tag"] in TAGSET and r["recv"] >= fe and r["value"] is not None), key=lambda r: r["recv"])
    rec = None
    for r in after:
        ok, lag, _, kind = match_value(poller, r["tag"], r["value"], r["recv"], a.tol_abs, a.tol_rel, lookback=2)
        if ok and kind == "value" and lag == 0:
            rec = (r["recv"] - fe) / 1e9
            break
    out["recovery_s_first_fresh_value"] = round(rec, 2) if rec is not None else None
    # 순서: 태그별 수신 순서에서 origin 역전
    inv = 0
    for t in TAGS:
        seq = [r["t"] for r in sorted((r for r in rd if r["tag"] == t), key=lambda r: r["recv"])]
        inv += sum(1 for x, y in zip(seq, seq[1:]) if y < x)
    out["order_inversions"] = inv
    # 수신 공백
    arr = sorted(r["recv"] for r in rd)
    gaps = [(b - x) / 1e9 for x, b in zip(arr, arr[1:])]
    out["max_arrival_gap_s"] = round(max(gaps), 2) if gaps else None
    errs = [e for e in poller.errors if fs - 2e9 <= e < fe + 30e9]
    out["state_poll_errors_near_fault"] = len(errs)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--duration", type=float, default=120)
    ap.add_argument("--warmup", type=float, default=5)
    ap.add_argument("--mqtt-host", default="mosquitto")
    ap.add_argument("--mqtt-port", type=int, default=1883)
    ap.add_argument("--mqtt-user", default="")
    ap.add_argument("--mqtt-pass", default="")
    ap.add_argument("--persistent", action="store_true", help="4단계: 영속 세션(고정 client_id)으로 구독 — 검사기 쪽 유실과 후보 유실을 가른다")
    ap.add_argument("--topic", default="edgex/telemetry")
    ap.add_argument("--shape", default="edgex", choices=sorted(PARSERS))
    ap.add_argument("--state-url", default="http://plant-simulator:8080/state")
    ap.add_argument("--state-period", type=float, default=0.1)
    ap.add_argument("--tol-abs", type=float, default=5e-4, help="/state 는 소수 4자리 반올림 → 5e-5 오차 + float32 여유")
    ap.add_argument("--tol-rel", type=float, default=1e-5)
    ap.add_argument("--downstream", default="", help="하류 파서 출력 파일(raw 레코드 JSON lines)")
    ap.add_argument("--fault-start", type=float, default=0.0, help="호스트 epoch 초(4단계)")
    ap.add_argument("--fault-end", type=float, default=0.0)
    ap.add_argument("--fault-kind", default="")
    ap.add_argument("--fault-file", default="", help="호스트가 쓴 'start end kind' 한 줄 파일(측정 끝에 읽음)")
    a = ap.parse_args()
    out = pathlib.Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise SystemExit(f"{out} 이미 있음 — 새 run ID 로")

    poller = StatePoller(a.state_url, a.state_period)
    poller.start()
    msgs, lock, ok = [], threading.Lock(), threading.Event()

    def on_msg(c, u, m):
        with lock:
            msgs.append((time.time_ns(), m.topic, m.payload))

    def on_conn(c, u, f, rc, p=None):
        if rc == 0:
            c.subscribe(a.topic.replace("{cid}", cid), qos=1)
            ok.set()
    cid = f"ingcheck-{a.profile}-{a.run}"
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=cid,
                    clean_session=not a.persistent, protocol=mqtt.MQTTv311)
    if a.mqtt_user:
        c.username_pw_set(a.mqtt_user, a.mqtt_pass)
    c.on_message, c.on_connect = on_msg, on_conn
    c.reconnect_delay_set(1, 2)
    c.connect_async(a.mqtt_host, a.mqtt_port, keepalive=30)
    c.loop_start()
    t_conn = time.time()
    while not ok.is_set() and time.time() - t_conn < 60:
        time.sleep(0.1)
    if not ok.is_set():
        res = {"error": f"MQTT 접속 실패 {a.mqtt_host}:{a.mqtt_port}"}
    else:
        t_start = time.time()
        while time.time() - t_start < a.duration:
            time.sleep(0.5)
        t_end = time.time()
        c.loop_stop()
        c.disconnect()
        poller.stop.set()
        if a.fault_file and pathlib.Path(a.fault_file).exists():
            parts = pathlib.Path(a.fault_file).read_text().split()
            a.fault_start, a.fault_end = float(parts[0]), float(parts[1])
            a.fault_kind = " ".join(parts[2:]) or a.fault_kind
        with lock:
            snapshot = list(msgs)
        res = analyse(a, snapshot, poller, t_start, t_end)
    res.update({"exp": "EXP-ING", "profile": a.profile, "run": a.run, "duration": a.duration,
                "mqtt": f"{a.mqtt_host}:{a.mqtt_port}", "topic": a.topic, "measured_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")})
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    brief = {k: res.get(k) for k in ("throughput",)}
    if "completeness" in res:
        brief.update({"unique": res["completeness"]["unique_samples"], "expected": res["completeness"]["expected_samples"],
                      "dup": res["completeness"]["duplicates"], "match_rate": res["values"]["match_rate"],
                      "downstream_equivalent": res["downstream"].get("equivalent"),
                      "downstream_records": res["downstream"].get("records_in_window")})
    print(json.dumps(brief, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
