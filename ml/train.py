"""Autoencoder 오프라인 학습 → ONNX 익스포트 (PDF p.9-10).

정상 운전 데이터로만 학습한다. 공정에 이상이 생기면 학습된 정상 패턴과의
괴리로 재구성 오차가 급증하고, 이를 임계치와 비교해 이상을 판정한다.

산출물
  model.onnx        Flink TaskManager 가 임베디드로 적재할 신경망
  model_meta.json   태그 순서 · 정규화 계수 · 이상 임계치
"""
from __future__ import annotations

import json
import os
import pathlib
import random

import numpy as np
import torch
import torch.nn as nn
import yaml

from plant import ReactorPlant

CFG = yaml.safe_load(open(os.getenv("TRAIN_CONFIG", "/app/train.yaml")))
PLANT_CFG = yaml.safe_load(open("/app/plant.yaml"))


def log(msg: str) -> None:
    print(f"[trainer] {msg}", flush=True)


# ══════════════════════════════════════════════════════════════
# 1. 정상 운전 데이터 생성
# ══════════════════════════════════════════════════════════════
def generate() -> tuple[np.ndarray, list[str]]:
    d = CFG["data"]
    cfg = yaml.safe_load(yaml.safe_dump(PLANT_CFG))
    cfg["autopilot"]["enabled"] = bool(d["autopilot"])

    plant = ReactorPlant(cfg)
    dt = float(d["dt_s"])

    for _ in range(int(d["warmup_s"] / dt)):
        plant.step(dt)

    tags = [t["name"] for t in cfg["tags"]]
    n = int(d["duration_s"] / dt)
    rows = np.empty((n, len(tags)), dtype=np.float32)
    for i in range(n):
        r = plant.step(dt)
        rows[i] = [r[t] for t in tags]

    log(f"정상 운전 데이터 {n:,}행 × {len(tags)}태그 생성 (autopilot={d['autopilot']})")
    return rows, tags


# ══════════════════════════════════════════════════════════════
# 2. 슬라이딩 윈도우 → 평탄화 텐서
# ══════════════════════════════════════════════════════════════
def windows(data: np.ndarray, steps: int) -> np.ndarray:
    n, k = data.shape
    out = np.empty((n - steps + 1, steps * k), dtype=np.float32)
    for i in range(n - steps + 1):
        out[i] = data[i:i + steps].reshape(-1)
    return out


class Autoencoder(nn.Module):
    """Dense Autoencoder. 인코더로 저차원 잠재벡터까지 압축한 뒤 복원한다."""

    def __init__(self, dim: int, hidden: list[int]):
        super().__init__()
        h1, h2 = hidden
        self.encoder = nn.Sequential(
            nn.Linear(dim, h1), nn.ReLU(),
            nn.Linear(h1, h2), nn.ReLU(),
        )
        self.decoder = nn.Sequential(
            nn.Linear(h2, h1), nn.ReLU(),
            nn.Linear(h1, dim),
        )

    def forward(self, x):
        return self.decoder(self.encoder(x))


def main() -> None:
    m = CFG["model"]
    # 물리 모델의 계측 노이즈는 표준 random 모듈을 쓰므로 함께 고정해야
    # 학습 결과(특히 이상 임계치)가 실행마다 재현된다.
    torch.manual_seed(m["seed"])
    np.random.seed(m["seed"])
    random.seed(m["seed"])

    data, tags = generate()

    # ── 정규화 계수는 학습 데이터에서만 산출하고 메타에 보존한다.
    #    Flink 가 추론 시 동일 계수를 적용해야 분포 불일치가 생기지 않는다.
    mean = data.mean(axis=0)
    std = data.std(axis=0)
    std[std < 1e-9] = 1.0
    norm = (data - mean) / std

    X = windows(norm, m["window_steps"])
    dim = X.shape[1]
    log(f"학습 텐서 {X.shape[0]:,} × {dim} (윈도우 {m['window_steps']}스텝 × {len(tags)}태그)")

    idx = np.random.permutation(len(X))
    split = int(len(X) * (1 - m["val_split"]))
    Xtr = torch.from_numpy(X[idx[:split]])
    Xva = torch.from_numpy(X[idx[split:]])

    model = Autoencoder(dim, m["hidden"])
    opt = torch.optim.Adam(model.parameters(), lr=m["learning_rate"])
    lossf = nn.MSELoss()

    for ep in range(m["epochs"]):
        model.train()
        perm = torch.randperm(len(Xtr))
        total = 0.0
        for i in range(0, len(Xtr), m["batch_size"]):
            b = Xtr[perm[i:i + m["batch_size"]]]
            opt.zero_grad()
            loss = lossf(model(b), b)
            loss.backward()
            opt.step()
            total += loss.item() * len(b)
        if (ep + 1) % 10 == 0 or ep == 0:
            model.eval()
            with torch.no_grad():
                val = lossf(model(Xva), Xva).item()
            log(f"  epoch {ep + 1:3d}/{m['epochs']}  train={total / len(Xtr):.6f}  val={val:.6f}")

    # ── 임계치: 정상 데이터 재구성 오차의 상위 백분위 × 여유계수 ──
    model.eval()
    with torch.no_grad():
        err = ((model(Xva) - Xva) ** 2).mean(dim=1).numpy()
    t = CFG["threshold"]
    threshold = float(np.percentile(err, t["percentile"]) * t["safety_factor"])
    log(f"정상 재구성오차: 중앙 {np.median(err):.6f}  p{t['percentile']} {np.percentile(err, t['percentile']):.6f}")
    log(f"이상 임계치 = {threshold:.6f} (여유계수 {t['safety_factor']})")

    # ── ONNX 익스포트 ──
    out = CFG["output"]
    pathlib.Path(out["model"]).parent.mkdir(parents=True, exist_ok=True)
    torch.onnx.export(
        model,
        torch.zeros(1, dim),
        out["model"],
        input_names=["input"],
        output_names=["reconstruction"],
        dynamic_axes={"input": {0: "batch"}, "reconstruction": {0: "batch"}},
        opset_version=17,
    )

    meta = {
        "tags": tags,
        "window_steps": m["window_steps"],
        "input_dim": dim,
        "mean": [float(v) for v in mean],
        "std": [float(v) for v in std],
        "threshold": threshold,
        "train_rows": int(X.shape[0]),
    }
    pathlib.Path(out["meta"]).write_text(json.dumps(meta, indent=2))
    size_mb = pathlib.Path(out["model"]).stat().st_size / 1e6
    log(f"ONNX 저장 완료: {out['model']} ({size_mb:.2f} MB)")
    log(f"메타 저장 완료: {out['meta']}")


# ══════════════════════════════════════════════════════════════
# 3. 자가 검증 — 학습된 모델이 실제로 판별력이 있는지 확인한다.
#    이 검증을 통과하지 못하면 Tier-2 계층 자체가 무의미하므로
#    학습 직후 항상 수행하고 결과를 로그로 남긴다.
# ══════════════════════════════════════════════════════════════
def validate() -> None:
    import onnxruntime as ort

    out = CFG["output"]
    meta = json.loads(pathlib.Path(out["meta"]).read_text())
    tags = meta["tags"]
    mean = np.array(meta["mean"], dtype=np.float32)
    std = np.array(meta["std"], dtype=np.float32)
    steps = meta["window_steps"]
    thr = meta["threshold"]

    sess = ort.InferenceSession(out["model"], providers=["CPUExecutionProvider"])
    iname = sess.get_inputs()[0].name

    def errors(scenario: str | None, seconds: int = 400) -> np.ndarray:
        cfg = yaml.safe_load(yaml.safe_dump(PLANT_CFG))
        plant = ReactorPlant(cfg)
        for _ in range(int(CFG["data"]["warmup_s"])):
            plant.step(1.0)
        if scenario:
            plant.inject(scenario, seconds)
        # 주의: 스캔당 step() 은 정확히 한 번만 호출해야 한다.
        # 태그마다 호출하면 한 행이 서로 다른 시각의 값으로 뒤섞이고
        # 시뮬레이션 시간이 태그 수만큼 빨리 흘러 고장 램프가 왜곡된다.
        rows = np.empty((seconds, len(tags)), dtype=np.float32)
        for i in range(seconds):
            r = plant.step(1.0)
            rows[i] = [r[t] for t in tags]
        # 통신 불량 센티널은 파이프라인에서 걸러지므로 검증에서도 직전값으로 대체
        for i in range(1, len(rows)):
            bad = rows[i] < -999998.0
            rows[i][bad] = rows[i - 1][bad]
        norm = (rows - mean) / std
        X = windows(norm, steps)
        # 고장 효과가 충분히 전개된 후반부만 평가
        X = X[len(X) // 2:]
        recon = sess.run(None, {iname: X})[0]
        return ((recon - X) ** 2).mean(axis=1)

    log("")
    log("═══ 모델 판별력 자가 검증 ═══")
    base = errors(None)
    log(f"  {'정상':14s} 평균오차 {base.mean():.5f}  탐지율 {100 * (base > thr).mean():5.1f}%   (오탐률)")

    expect = {
        "drift": "탐지되어야 함 (단일 임계치로는 불가)",
        "bearing_wear": "탐지되어야 함",
        "noise": "Tier-1 롤링 Z-Score 담당 (ML 은 미반응이 정상)",
        "spike": "Tier-1 이 먼저 잡지만 ML 도 반응",
    }
    for sc, note in expect.items():
        e = errors(sc)
        rate = 100 * (e > thr).mean()
        log(f"  {sc:14s} 평균오차 {e.mean():.5f}  탐지율 {rate:5.1f}%   {note}")
    log(f"  임계치 = {thr:.5f}")


if __name__ == "__main__":
    main()
    validate()
