"""L4 후보: Quix Streams 3.26.0 으로 V1 규칙(flink/sql/02·03)을 엔진 기능으로 옮긴 것.

엔진 기능만 쓴다(QUESTIONS §1 직접 제작 금지):
  - 입력·출력·상태·재시작 복구: Application(Kafka 소비 그룹, RocksDB 상태 + changelog, processing_guarantee=exactly-once)
  - L4-01 임계치: filter/apply 분기. 규격표는 V1 과 같은 tag_limits.csv 를 시작 시 읽는다(설정 파일 로드 = 연결 코드)
  - L4-02 Z-Score: sliding_count_window(60).final() + 내장 집계 Count/Sum/Last → 두 번째 sliding_count_window(5).final() + Sum
      (창은 메시지 키 단위. 리플레이는 key=tag 로 발행하므로 V1 의 PARTITION BY tag 와 같다.
       .final() = 창이 count 만큼 찼을 때 한 번 = 메시지마다 "현재 포함 최근 N행". .current() 는 겹친 창 N개를 모두 내보내 쓰지 않는다)
      평균·표본표준편차 식은 Flink(Calcite)가 AVG·STDDEV_SAMP 를 줄여 쓰는 식과 같게 SUM·SUM(x²)·COUNT 로 계산한다
  - L4-12 ONNX(시도): group_by(device) 재분할 → tumbling_window(1초, 이벤트 시각) 태그별 Latest → 상태 저장(stateful apply)으로
      빈 태그 직전값 유지 → sliding_count_window(10) Collect → onnxruntime 점수 → exp.l4.score.quix / ML 알람.
      V1 은 처리시각 1초 타이머 표본이라 방식이 다르다(Quix 에 처리시각 타이머 없음). 결과 동일성은 S13 으로 판정.
엔진이 못 하는 것(손으로 만들지 않는다, 시작 시 API 를 조사해 시도 기록 파일에 남긴다):
  - L4-03/04 CEP(패턴 매칭): Quix Streams 에 CEP·패턴 API 없음 → 알람을 내지 않는다
  - L4-12b 보간(clean 스트림): 선형 보간은 뒤 값이 올 때까지 기다리는 처리 — 엔진 기능 없음, 미구현
알려진 차이(②에서 확인): Count 창은 도착 순서(V1 은 이벤트 시각 정렬 + 워터마크 5초 뒤 폐기).
  태그별 처음 59행은 60행 창이 안 차서 판정하지 않는다(V1 은 30행부터). 5행 창도 처음 4행은 판정 없음.
"""
import csv
import json
import os
import time

from quixstreams import Application
from quixstreams.dataframe import StreamingDataFrame
from quixstreams.dataframe.windows import Collect, Count, Last, Latest, Sum

BOOT = os.environ.get("BOOTSTRAP", "kafka:9092")
LIMITS = {}
for row in csv.reader(open(os.environ.get("TAG_LIMITS", "/app/tag_limits.csv"), encoding="utf-8")):
    if len(row) >= 4:
        f = lambda x: float(x) if x.strip() else None
        LIMITS[row[0]] = (row[1], f(row[2]), f(row[3]))

app = Application(
    broker_address=BOOT,
    consumer_group=os.environ.get("GROUP", "quix-l4"),
    auto_offset_reset="latest",                 # V1 scan.startup.mode = latest-offset
    processing_guarantee="exactly-once",
    state_dir=os.environ.get("STATE_DIR", "/state"),
)
raw = app.topic("exp.l4.raw", value_deserializer="json",
                timestamp_extractor=lambda v, headers, ts, ttype: int(v["ts"]) // 1_000_000)   # V1 ts/1000000
alerts = app.topic("exp.l4.alerts.quix", value_serializer="json")


def fmt(x):
    return "-" if x is None else str(x)


def violates(r):
    lim = LIMITS.get(r.get("tag"))
    if not lim:
        return False
    _, lsl, usl = lim
    v = r["value"]
    return (usl is not None and v > usl) or (lsl is not None and v < lsl)


def threshold_alert(r):
    unit, lsl, usl = LIMITS[r["tag"]]
    usl_hit = usl is not None and r["value"] > usl
    return {"ts": r["ts"], "site": r["site"], "device": r["device"], "tag": r["tag"], "value": r["value"],
            "alert_type": "THRESHOLD_USL" if usl_hit else "THRESHOLD_LSL", "severity": "CRITICAL",
            "detector": "TIER1_RULE",
            "detail": f"{r['tag']} = {round(r['value'], 3)} {unit} / 규격 [{fmt(lsl)}, {fmt(usl)}]"}


def zstats(w):
    r, n, s_, s2 = w["row"], w["n"], w["s"], w["s2"]
    mu = s_ / n
    var = (s2 - s_ * s_ / n) / (n - 1) if n > 1 else None
    sd = var ** 0.5 if var is not None and var > 0 else 0.0
    z = abs(r["value"] - mu) / sd if sd > 1e-9 else 0.0
    return {**r, "mu": mu, "sd": sd, "z": z, "viol": 1 if z > 3.5 else 0}


def zscore_alert(w):
    r = w["row"]
    return {"ts": r["ts"], "site": r["site"], "device": r["device"], "tag": r["tag"], "value": r["value"],
            "alert_type": "ZSCORE", "severity": "WARNING", "detector": "TIER1_ZSCORE",
            "detail": f"{r['tag']} z={round(r['z'], 2)} (μ={round(r['mu'], 3)}, σ={round(r['sd'], 4)}, "
                      f"최근5중 {w['viol_run']}회 위반)"}


sdf = app.dataframe(raw)
sdf = sdf.apply(lambda r: {**r, "v2": r["value"] * r["value"]})

# ── L4-01 임계치 ──
sdf.filter(violates).apply(threshold_alert).to_topic(alerts)

# ── L4-02 Z-Score: 최근 60행(현재 포함) → n>=30 → 최근 5행 중 위반 3 이상 ──
z = (sdf.sliding_count_window(60, name="z60")
        .agg(n=Count(), s=Sum("value"), s2=Sum("v2"), row=Last())     # row = 현재(마지막 처리) 메시지
        .final())
z = z.filter(lambda w: w["n"] >= 30).apply(zstats)
zr = (z.sliding_count_window(5, name="z5")
        .agg(viol_run=Sum("viol"), row=Last())
        .final())
zr.filter(lambda w: w["viol_run"] >= 3).apply(zscore_alert).to_topic(alerts)

# ── L4-12 ONNX (시도) ──
MODEL, META = os.environ.get("MODEL", "/opt/models/model.onnx"), os.environ.get("META", "/opt/models/model_meta.json")
ATTEMPTS = f"/experiments/EXP-L4/raw/stage2_{os.environ.get('RUN', 'manual')}_attempts.jsonl"


def attempt(rule, feature, ok, error="", statement=""):
    try:
        with open(ATTEMPTS, "a", encoding="utf-8") as f:
            f.write(json.dumps({"engine": "quix", "rule": rule, "feature": feature, "ok": ok, "error": error[:2000],
                                "statement": statement[:2000], "at": time.time()}, ensure_ascii=False) + chr(10))
    except OSError as e:
        print("attempt log 실패", e, flush=True)


# CEP: 엔진 API 에 패턴 연산이 있는지 실제 설치본에서 조사해 기록
cep_api = [m for m in dir(StreamingDataFrame) if any(k in m.lower() for k in ("pattern", "cep", "match", "sequence"))]
attempt("L4-03/04 CEP", "StreamingDataFrame API 조사", bool(cep_api),
        "" if cep_api else "quixstreams %s: StreamingDataFrame 에 pattern/cep/match/sequence 메서드 없음" %
        __import__("quixstreams").__version__, "dir(StreamingDataFrame)")
attempt("L4-12b 보간", "없음", False, "선형 보간(뒤 값 대기) 연산 없음 — 미구현")

try:
    import numpy as np
    import onnxruntime as ort
    meta = json.load(open(META, encoding="utf-8"))
    TAGS = meta["tags"]
    STEPS = int(meta.get("window_steps", 10))
    MEAN = np.array(meta["mean"], dtype=np.float64)
    SD = np.where(np.array(meta["std"], dtype=np.float64) > 1e-9, np.array(meta["std"], dtype=np.float64), 1.0)
    THR = float(os.environ.get("ANOMALY_THRESHOLD") or meta["threshold"])
    so = ort.SessionOptions(); so.intra_op_num_threads = 1
    SESSION = ort.InferenceSession(MODEL, so, providers=["CPUExecutionProvider"])
    INPUT = SESSION.get_inputs()[0].name
    scores = app.topic("exp.l4.score.quix", value_serializer="json")

    def fill(v, state):                        # 1초 창에 없는 태그는 그 장치의 직전값(엔진 상태 저장소)
        last = state.get("last", {})
        row = [v.get(t) if v.get(t) is not None else last.get(t) for t in TAGS]
        last.update({t: x for t, x in zip(TAGS, row) if x is not None})
        state.set("last", last)
        return {"device": v["device"], "site": v["site"], "row": row}

    def score(w):
        rows = [r["row"] for r in w["rows"]]
        if len(rows) < STEPS or any(x is None for r in rows for x in r):
            return None
        flat = ((np.array(rows, dtype=np.float64) - MEAN) / SD).astype(np.float32).reshape(1, -1)
        t0 = time.perf_counter()
        recon = SESSION.run(None, {INPUT: flat})[0]
        ms = (time.perf_counter() - t0) * 1000
        d = (flat[0] - recon[0]).astype(np.float32).astype(np.float64)
        mse = float((d * d).sum() / flat.shape[1])
        last = w["rows"][-1]
        return {"ts": time.time_ns(), "site": last["site"], "device": last["device"], "reconstruction_error": mse,
                "threshold": THR, "is_anomaly": mse > THR, "top_contributors": "", "inference_ms": round(ms, 3)}

    ml = (sdf.group_by("device")
             .apply(lambda r: {"device": r["device"], "site": r["site"], r["tag"]: r["value"]})
             .tumbling_window(1000, name="ml1s")
             .agg(device=Latest("device"), site=Latest("site"), **{t: Latest(t) for t in TAGS})
             .final())
    ml = ml.apply(fill, stateful=True)
    ml = ml.sliding_count_window(STEPS, name="ml10").agg(rows=Collect()).final().apply(score).filter(lambda x: x is not None)
    ml.to_topic(scores)
    ml.filter(lambda x: x["is_anomaly"]).apply(lambda x: {
        "ts": x["ts"], "site": x["site"], "device": x["device"], "tag": "MULTIVARIATE", "value": x["reconstruction_error"],
        "alert_type": "ML_AUTOENCODER", "severity": "WARNING", "detector": "TIER2_ML",
        "detail": f"재구성오차 {x['reconstruction_error']:.5f} > 임계 {x['threshold']:.5f} · 추론 {x['inference_ms']:.2f}ms"}
    ).to_topic(alerts)
    attempt("L4-12 ONNX", "group_by + tumbling_window(1s) + sliding_count_window(10) + onnxruntime", True, "",
            "이벤트 시각 1초 창(V1 은 처리시각 1초 타이머)")
except Exception as e:                           # 엔진이 파이프라인 구성을 거부하면 그 메시지를 남기고 규칙 알람은 계속 낸다
    attempt("L4-12 ONNX", "group_by + windows + onnxruntime", False, f"{type(e).__name__}: {e}")
    print("ONNX 파이프라인 구성 실패:", e, flush=True)

if __name__ == "__main__":
    app.run()
