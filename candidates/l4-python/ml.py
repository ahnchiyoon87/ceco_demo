"""V1 ONNX 잡(flink/onnx-job: Interpolator + OnnxScorer)을 Python 으로 옮긴 것. 의미·수식·키는 V1 과 같다.

- Interpolator: 태그(tag) 단위 키. (tag, ts) 중복 제거, 스캔 주기 1.5배 넘는 공백은 선형 보간(최대 공백 넘으면 LOCF).
  V1 AnomalyJob 이 keyBy(r -> r.tag) 이므로 같은 키를 쓴다.
- OnnxScorer: 장치(device) 단위 키. 첫 레코드부터 처리시각 1초 주기로 12차원 최신값 벡터를 조립해
  10스텝 창을 만들고, 정규화한 120차원 입력의 재구성 오차(MSE)를 임계치와 비교한다.
"""
import json
import time

import numpy as np
import onnxruntime as ort


class Interpolator:
    def __init__(self, mode="linear", max_gap_ms=20000, scan_ms=1000, state=None):
        self.mode, self.max_gap_ms, self.scan_ms = mode, max_gap_ms, max(scan_ms, 1)
        state = state or {}
        self.last_good = state.get("last_good", {})
        self.last_ts = state.get("last_ts", {})

    def state(self):
        return {"last_good": self.last_good, "last_ts": self.last_ts}

    def process(self, r):
        """입력 1건 → clean 레코드 목록(보간값 먼저, 원본 마지막)."""
        tag = r["tag"]
        lt = self.last_ts.get(tag)
        if lt is not None and r["ts"] <= lt:
            return []
        out = []
        prev = self.last_good.get(tag)
        if prev is not None:
            gap = r["ts"] // 1_000_000 - prev["ts"] // 1_000_000
            if gap > self.scan_ms * 1.5:
                out.extend(self._fill(prev, r, gap))
        rec = {"ts": r["ts"], "site": r.get("site"), "device": r.get("device"), "tag": tag,
               "value": r["value"], "quality": r.get("quality") or "GOOD"}
        out.append(rec)
        self.last_good[tag] = rec
        self.last_ts[tag] = r["ts"]
        return out

    def _fill(self, prev, nxt, gap):
        missing = int(np.floor(gap / self.scan_ms + 0.5)) - 1   # Java Math.round
        if missing <= 0:
            return []
        linear = self.mode.lower() == "linear" and gap <= self.max_gap_ms
        q = "INTERPOLATED_LINEAR" if linear else "INTERPOLATED_LOCF"
        cap = min(missing, self.max_gap_ms // self.scan_ms)
        out = []
        for i in range(1, cap + 1):
            v = prev["value"] + (nxt["value"] - prev["value"]) * (i / (missing + 1)) if linear else prev["value"]
            out.append({"ts": prev["ts"] + i * self.scan_ms * 1_000_000, "site": prev["site"], "device": prev["device"],
                        "tag": prev["tag"], "value": v, "quality": q})
        return out


class OnnxScorer:
    def __init__(self, model_path, meta_path, steps=10, infer_ms=1000, threshold=None, state=None):
        meta = json.load(open(meta_path, encoding="utf-8"))
        self.tags = meta["tags"]
        self.mean = np.array(meta["mean"], dtype=np.float64)
        std = np.array(meta["std"], dtype=np.float64)
        self.sd = np.where(std > 1e-9, std, 1.0)
        self.threshold = threshold if threshold is not None else float(meta["threshold"])
        self.steps, self.infer_ms = steps, infer_ms
        so = ort.SessionOptions()
        so.intra_op_num_threads = 1                        # V1: 슬롯당 1스레드
        self.sess = ort.InferenceSession(model_path, so, providers=["CPUExecutionProvider"])
        self.iname = self.sess.get_inputs()[0].name
        self.dev = (state or {}).get("dev", {})           # device → {latest, window, next_fire, site}

    def state(self):
        return {"dev": self.dev}

    def process(self, r, now_ms):
        d = self.dev.setdefault(r["device"], {"latest": {}, "window": [], "next_fire": None, "site": None})
        d["latest"][r["tag"]] = r["value"]
        if d["site"] is None:
            d["site"] = r.get("site")
        if d["next_fire"] is None:
            d["next_fire"] = now_ms + self.infer_ms

    def next_fire_ms(self):
        return min((d["next_fire"] for d in self.dev.values() if d["next_fire"] is not None), default=None)

    def fire_due(self, now_ms):
        """처리시각 타이머 중 기한이 된 것을 모두 실행(밀린 타이머도 한 번씩, Flink 와 같음). → (scores, alerts)"""
        scores, alerts = [], []
        for device, d in self.dev.items():
            while d["next_fire"] is not None and d["next_fire"] <= now_ms:
                d["next_fire"] += self.infer_ms
                s = self._tick(device, d)
                if s:
                    scores.append(s[0])
                    if s[1]:
                        alerts.append(s[1])
        return scores, alerts

    def _tick(self, device, d):
        if any(t not in d["latest"] for t in self.tags):
            return None                                     # 전 태그가 한 번은 관측되기 전에는 추론하지 않는다
        vec = [d["latest"][t] for t in self.tags]
        w = d["window"]
        if len(w) < self.steps:
            w.append(vec)
            if len(w) < self.steps:
                return None
        else:
            w.pop(0)
            w.append(vec)
        flat = ((np.array(w, dtype=np.float64) - self.mean) / self.sd).astype(np.float32).reshape(1, -1)
        t0 = time.perf_counter_ns()
        recon = self.sess.run(None, {self.iname: flat})[0]
        infer_ms = (time.perf_counter_ns() - t0) / 1e6
        diff = (flat[0] - recon[0]).astype(np.float64)      # float 뺄셈 후 double 제곱(Java 와 같음)
        sq = diff * diff
        mse = float(sq.sum() / sq.size)
        per_tag = sq.reshape(self.steps, len(self.tags)).sum(axis=0)
        total = float(per_tag.sum())
        denom = total if total > 1e-12 else 1.0
        order = sorted(range(len(self.tags)), key=lambda i: -per_tag[i])
        top = ", ".join(f"{self.tags[i]}({100.0 * per_tag[i] / denom:.0f}%)" for i in order[:3])
        ts = int(time.time() * 1000) * 1_000_000
        score = {"ts": ts, "site": d["site"], "device": device, "reconstruction_error": mse,
                 "threshold": self.threshold, "is_anomaly": mse > self.threshold,
                 "top_contributors": top, "inference_ms": round(infer_ms * 1000) / 1000.0}
        alert = None
        if score["is_anomaly"]:
            alert = {"ts": ts, "site": d["site"], "device": device, "tag": "MULTIVARIATE", "value": mse,
                     "alert_type": "ML_AUTOENCODER", "severity": "WARNING", "detector": "TIER2_ML",
                     "detail": f"재구성오차 {mse:.5f} > 임계 {self.threshold:.5f} · 기여 상위: {top} · 추론 {infer_ms:.2f}ms"}
        return score, alert
