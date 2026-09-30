"""S13 ONNX 점수 동일성 + L4-12b 보간 동일성 (tests/scenarios/catalog.yaml S13, tests/situations/L4.md).

입력: V1 시뮬레이터 물리모델(0_plant/simulator/plant.py)로 만든 정상·고장 구간에서 고른 고정 창 100개.
창 k 는 장치 w{k} 하나에 10행(12태그)으로 발행한다. V1 OnnxScorer 는 첫 레코드부터 처리시각 1초마다
최신값을 표본으로 뜨므로, 행 j 를 T0 + 1000j + 500ms(j≥1)에 발행해 틱 n 이 정확히 행 n-1 을 보게 한다(여유 ±500ms).
V1 Interpolator 는 태그 단위 키이므로 모든 장치의 이벤트 시각을 태그별로 엄격히 증가시키고 한 파티션에 순서대로 넣는다.

L4-12b: 장치 g 하나에 60행을 발행하되 일부 태그를 3초·8초·25초 비우고 중복 1건을 넣어 clean 출력을 비교한다.

판정: 각 후보의 첫 점수(창 10행이 찬 첫 틱)를 오프라인 참조(V1 Java 수식, onnxruntime)와 비교 |차| ≤ 1e-6.
      clean 레코드는 기준 후보(첫 후보)와 (ts, tag, value, quality) 가 모두 같아야 한다.

  python /repo/tests/tools/s13.py --exp EXP-L4 --run s13_1 --cands flinksql,flink22,cep,python

새 베이스(K4, 17번): 스코어러가 스캔 순번(seq)·설비 시각(pts)으로 창을 만든다. --mode k4 는 실제 순차 창 10행을
seq 1..10, pts = j × 학습 표본 간격으로 발행하므로 처리 시각과 무관하게 창 k 의 첫 점수가 행 0..9 를 본다.
모델은 기동 때 학습기가 만든 모델 볼륨(--model-dir, 기본 /models)을 읽는다(옛 tests/l4bench/models 는 지웠다).
  python /repo/tests/tools/s13.py --exp BASE-VERIFY --run s13_base --cands base --mode k4 --model-dir /models
"""
import argparse
import json
import pathlib
import random
import sys
import time
import uuid

import numpy as np
import onnxruntime as ort
import yaml
from confluent_kafka import Consumer, Producer, TopicPartition

sys.path.insert(0, "/repo/0_plant/simulator")
from plant import ReactorPlant  # noqa: E402

BOOT = "kafka:9092"
RAW = "exp.l4.raw"
MODEL, META = "/models/model.onnx", "/models/model_meta.json"
SEGMENTS = [None, "bearing_wear", "drift", "heater_stuck"]      # 정상 + 고장 3종, 구간마다 창 25개


def series(scenario, seed, tags, n=130):
    random.seed(seed)
    cfg = yaml.safe_load(open("/repo/0_plant/simulator/plant.yaml", encoding="utf-8"))
    plant = ReactorPlant(cfg)
    for _ in range(1800):
        plant.step(1.0)
    if scenario:
        # process 고장의 지속 시간은 설비 초다. 배속 600 설비의 한 스텝(1 s)은 600 설비 초이므로 n 스텝만큼 걸어 둔다
        # (n 그대로면 첫 스텝에 끝나 고장 창이 정상 창이 된다 — 09-30 첫 k4 실행 ref_anomalies 0, 결함 S6 과 같은 종류)
        plant.inject(scenario, n * getattr(plant, "time_scale", 1.0))
    rows = []
    for _ in range(n):
        r = plant.step(1.0)
        rows.append([float(r[t]) for t in tags])
    for i in range(1, len(rows)):                                   # 통신 불량 센티널은 직전값(train.py validate 와 같음)
        rows[i] = [rows[i - 1][c] if v < -999998.0 else v for c, v in enumerate(rows[i])]
    return rows


def reference(windows, meta):
    """V1 OnnxScorer.onTimer 수식을 그대로: double 로 정규화 → float 캐스트 → ONNX → (float 뺄셈) double 제곱합 / dim."""
    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    sess = ort.InferenceSession(MODEL, so, providers=["CPUExecutionProvider"])
    name = sess.get_inputs()[0].name
    mean = np.array(meta["mean"], dtype=np.float64)
    std = np.array(meta["std"], dtype=np.float64)
    sd = np.where(std > 1e-9, std, 1.0)
    out = []
    for w in windows:
        flat = ((np.array(w, dtype=np.float64) - mean) / sd).astype(np.float32).reshape(1, -1)
        recon = sess.run(None, {name: flat})[0]
        mse = 0.0
        for a, b in zip(flat[0], recon[0]):
            d = float(np.float32(a - b))
            mse += d * d
        out.append(mse / flat.shape[1])
    return out


def read_topic(topic, prefix, timeout_s=120):
    """호출 시점의 파티션 끝 오프셋까지만 읽는다(점수는 매초 계속 나오므로 '유휴 시 종료'는 끝나지 않는다 — s13_1 무효 원인)."""
    c = Consumer({"bootstrap.servers": BOOT, "group.id": f"s13-{uuid.uuid4()}", "enable.auto.commit": False})
    parts = c.list_topics(topic, timeout=10).topics[topic].partitions
    end = {p: c.get_watermark_offsets(TopicPartition(topic, p), timeout=10)[1] for p in parts}
    todo = {p for p, e in end.items() if e > 0}
    c.assign([TopicPartition(topic, p, 0) for p in parts])
    out, t0 = [], time.time()
    while todo and time.time() - t0 < timeout_s:
        m = c.poll(0.5)
        if m is None or m.error():
            continue
        if m.offset() + 1 >= end[m.partition()]:
            todo.discard(m.partition())
        r = json.loads(m.value())
        if str(r.get("device", "")).startswith(prefix):
            out.append((m.timestamp()[1], r))
    c.close()
    if todo:
        raise SystemExit(f"{topic}: {timeout_s}s 안에 끝 오프셋까지 못 읽음 {sorted(todo)}")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--cands", default="flinksql,flink22,cep,python")
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--wait-s", type=float, default=30.0)
    ap.add_argument("--mode", choices=["steady", "sequence", "k4"], default="steady",
                    help="steady(기본, #50): 장치당 1행 → 창=같은 벡터×10 정상상태 점수 비교. sequence: 순차 창(방법 결함으로 무효 처리됨). "
                         "k4: 순차 창을 seq·pts 와 함께 발행(새 베이스 스코어러)")
    ap.add_argument("--model-dir", default="/models")
    a = ap.parse_args()
    global MODEL, META
    MODEL, META = f"{a.model_dir}/model.onnx", f"{a.model_dir}/model_meta.json"
    raw = pathlib.Path(f"/experiments/{a.exp}/raw")
    raw.mkdir(parents=True, exist_ok=True)
    res_path = raw / f"s13_{a.run}.json"
    if res_path.exists():
        raise SystemExit(f"실행 ID 재사용 금지: {res_path}")
    meta = json.load(open(META, encoding="utf-8"))
    tags = meta["tags"]
    cands = a.cands.split(",")
    token = uuid.uuid4().hex[:6]
    prefix = f"{a.run}.{token}-"

    # ── 창 100개 ──
    windows, labels = [], []
    for si, sc in enumerate(SEGMENTS):
        rows = series(sc, a.seed + si, tags)
        for k in range(25):
            s = 20 + k * 4                                           # 고장 전개 구간을 고르게
            windows.append(rows[s:s + 10])
            labels.append(sc or "normal")
    if a.mode == "steady":
        windows = [[w[9]] * 10 for w in windows]                  # 창 = 같은 벡터 ×10 (처리시각 표본과 무관하게 결정적)
    ref = reference(windows, meta)
    devs = [f"{prefix}w{k:03d}" for k in range(len(windows))]

    prod = Producer({"bootstrap.servers": BOOT, "acks": "all", "linger.ms": 0})
    base = time.time_ns()

    def send(ts, dev, tag, v, seq=None, pts=None):
        rec = {"ts": ts, "site": "EXP", "device": dev, "tag": tag, "value": v}
        if seq is not None:
            rec |= {"seq": seq, "pts": pts}
        prod.produce(RAW, partition=0, value=json.dumps(rec))

    t0 = time.time()
    if a.mode == "k4":
        step_s = int(meta.get("sample_interval_s") or 1)
        for j in range(10):
            for k, dev in enumerate(devs):
                for ti, tag in enumerate(tags):
                    send(base + j * 1_000_000_000 + k, dev, tag, windows[k][j][ti], seq=j + 1, pts=j * step_s)
            prod.flush(10)
    for j in range(0 if a.mode == "k4" else (1 if a.mode == "steady" else 10)):
        if j:
            while time.time() < t0 + j + 0.5:
                time.sleep(0.01)
        for k, dev in enumerate(devs):
            for ti, tag in enumerate(tags):
                send(base + j * 1_000_000_000 + k, dev, tag, windows[k][j][ti])
        prod.flush(10)
    emit_s = round(time.time() - t0, 3)

    # ── L4-12b: 장치 g, 60행. 태그 공백 3초·8초·25초 + 중복 1건 ──
    gdev = f"{prefix}g"
    grow = series("bearing_wear", a.seed + 99, tags, n=60)
    holes = {"TT-101": range(10, 13), "PT-101": range(20, 28), "LT-101": range(30, 55)}
    gbase = base + 30 * 1_000_000_000
    gsent = 0
    for j in range(60):
        for ti, tag in enumerate(tags):
            if j in holes.get(tag, ()):
                continue
            send(gbase + j * 1_000_000_000, gdev, tag, grow[j][ti])
            gsent += 1
            if tag == "FT-101" and j == 5:
                send(gbase + j * 1_000_000_000, gdev, tag, grow[j][ti])   # 중복(QoS1 재전송 모사)
                gsent += 1
    prod.flush(10)
    time.sleep(a.wait_s)

    result = {"model_dir": a.model_dir, "sample_interval_s": meta.get("sample_interval_s"), "mode": a.mode, "run": a.run, "token": token, "windows": len(windows), "emit_s": emit_s, "tol": 1e-6,
              "threshold": meta["threshold"], "ref_anomalies": sum(x > meta["threshold"] for x in ref),
              "labels": {l: labels.count(l) for l in set(labels)}, "gap_sent": gsent, "cands": {}}
    clean_base = None
    for c in cands:
        scores = sorted(read_topic(f"exp.l4.score.{c}", prefix), key=lambda x: (x[1]["device"], x[1]["ts"]))
        first = {}
        for _, s in scores:
            if a.mode == "steady":
                first[s["device"]] = s                                # 정상상태: 마지막 점수(정렬 끝)
            else:
                first.setdefault(s["device"], s)
        diffs, anom_mismatch, missing, missing_devs = [], 0, 0, []
        for k, dev in enumerate(devs):
            s = first.get(dev)
            if s is None:
                missing += 1
                missing_devs.append(f"w{k:03d}:{labels[k]}")
                continue
            diffs.append(abs(s["reconstruction_error"] - ref[k]))
            anom_mismatch += int(bool(s["is_anomaly"]) != (ref[k] > meta["threshold"]))
        alerts = [r for _, r in read_topic(f"exp.l4.alerts.{c}", prefix) if r.get("detector") == "TIER2_ML"]
        clean = sorted((r["ts"], r["tag"], r["value"], r["quality"]) for _, r in read_topic(f"exp.l4.clean.{c}", gdev))
        q = {}
        for x in clean:
            q[x[3]] = q.get(x[3], 0) + 1
        entry = {"scored": len(first), "missing": missing, "missing_windows": missing_devs, "max_abs_diff": max(diffs) if diffs else None,
                 "within_tol": sum(d <= 1e-6 for d in diffs), "anomaly_flag_mismatch": anom_mismatch,
                 "ml_alerts_total": len(alerts), "clean_records": len(clean), "clean_quality": q}
        if clean_base is None:
            clean_base = (c, clean)
        else:
            entry["clean_equal_to_" + clean_base[0]] = clean == clean_base[1]
            entry["clean_diff_count"] = len(set(clean) ^ set(clean_base[1]))
        entry["verdict"] = "PASS" if (missing == 0 and diffs and max(diffs) <= 1e-6 and anom_mismatch == 0
                                      and entry.get("clean_equal_to_" + clean_base[0], True)) else "FAIL"
        result["cands"][c] = entry
        print(c, json.dumps(entry, ensure_ascii=False), flush=True)
    (raw / f"s13_{a.run}_ref.json").write_text(json.dumps({"devices": devs, "labels": labels, "ref": ref}), encoding="utf-8")
    res_path.write_text(json.dumps(result, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "cands"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
