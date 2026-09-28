"""시나리오 실행기: 가상설비에 실제로 고장을 주입하고, 1초 관측을 모아, 알람 발생 10초 뒤 추론 엔진을 호출한다.

    python run_scenario.py --scenario SC1_bearing --run a1

- 설정·주입·알람 조건은 ontology/v2/answer-key.yaml 의 plant_setup·inject·alarm_trigger 만 쓴다.
- 엔진에는 /state 에서 active_faults(주입 정답)·thermal_model 을 지운 상태만 넘긴다(V1 evidence.py 와 같은 원칙).
- 결과: /experiments/EXP-AI/raw/<scenario>_<run>.json (관측 원본·추론 결과·소요 시간)
"""
import argparse
import json
import os
import pathlib
import time

import requests
import yaml
from pymodbus.client import ModbusTcpClient

from engine.load import plant_spec
from engine.reason import infer

REPO = os.environ.get("REPO", "/repo")
SIM = os.environ.get("SIM_URL", "http://sim:8080")
SIM_HOST, SIM_PORT = os.environ.get("SIM_MODBUS", "sim:502").split(":")
HIDDEN = ("active_faults", "thermal_model")


def state():
    return requests.get(f"{SIM}/state", timeout=5).json()


def write_commands(setup):
    cfg = yaml.safe_load(open(f"{REPO}/simulator/plant.yaml", encoding="utf-8"))["commands"]
    c = ModbusTcpClient(SIM_HOST, port=int(SIM_PORT), timeout=3)
    assert c.connect(), "Modbus 연결 실패"
    try:
        for name, value in setup.items():
            if name in cfg["coils"]:
                c.write_coil(cfg["coils"][name]["addr"], bool(value), slave=1)
            elif name in cfg["holding"]:
                c.write_register(cfg["holding"][name]["addr"], int(value), slave=1)
    finally:
        c.close()


def triggered(trig, hist, spec, seen):
    if trig["alert_type"] == "CEP_BEARING":      # 전류 usl 초과 후 10초 안에 진동 usl 초과 (V1 04_tier1_cep.sql 과 같은 정의)
        it = [t for t, v in hist.get("IT-102", []) if v > spec["IT-102"]["usl"]]
        vt = [t for t, v in hist.get("VT-101", []) if v > spec["VT-101"]["usl"]]
        return bool(it and vt and any(0 < v - i < 10 for i in it for v in vt))
    tag = trig["tag"]
    rows = hist.get(tag, [])
    return bool(rows) and rows[-1][1] > spec[tag]["usl"]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scenario", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--warmup", type=float, default=40)
    ap.add_argument("--after", type=float, default=10)
    ap.add_argument("--timeout", type=float, default=1200)
    a = ap.parse_args()
    out = pathlib.Path(f"/experiments/EXP-AI/raw/{a.scenario}_{a.run}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        raise SystemExit(f"{out} 이미 있음 — 새 run ID")
    sc = yaml.safe_load(open(f"{REPO}/ontology/v2/answer-key.yaml", encoding="utf-8"))["scenarios"][a.scenario]
    spec = plant_spec()
    requests.post(f"{SIM}/fault/clear", json={}, timeout=5)
    if sc.get("plant_setup"):
        write_commands(sc["plant_setup"])
    hist, t0 = {}, time.time()

    def poll():
        s = state()
        now = time.time() - t0
        for tag, v in s["readings"].items():
            if v is not None:
                hist.setdefault(tag, []).append((round(now, 2), v))
        return s

    while time.time() - t0 < a.warmup:
        poll()
        time.sleep(1)
    inj = requests.post(f"{SIM}/fault", json={"scenario": sc["inject"]["scenario"]}, timeout=5).json()
    t_inj = time.time() - t0
    t_trig = None
    while time.time() - t0 < a.warmup + a.timeout:
        poll()
        if triggered(sc["alarm_trigger"], hist, spec, None):
            t_trig = time.time() - t0
            break
        time.sleep(1)
    if t_trig is None:
        requests.post(f"{SIM}/fault/clear", json={}, timeout=5)
        out.write_text(json.dumps({"scenario": a.scenario, "run": a.run, "error": "alarm not triggered", "injected": inj}, ensure_ascii=False))
        raise SystemExit("알람 조건 미발생")
    end = time.time() + a.after
    while time.time() < end:
        s = poll()
        time.sleep(1)
    visible = {k: v for k, v in s.items() if k not in HIDDEN}
    window = {tag: [(t, v) for t, v in rows if t >= t_trig - 120] for tag, rows in hist.items()}
    alarm = {"alert_type": sc["alarm_trigger"]["alert_type"], "tag": sc["alarm_trigger"]["tag"], "site": s["site"], "device": s["device"]}
    t1 = time.perf_counter()
    result = infer(alarm, window, visible)
    infer_ms = round((time.perf_counter() - t1) * 1000, 1)
    requests.post(f"{SIM}/fault/clear", json={}, timeout=5)
    write_commands({"heater_enable": 1, "cooler_enable": 0, "agitator_run": 1})
    out.write_text(json.dumps({"scenario": a.scenario, "run": a.run, "injected": inj, "t_inject_s": round(t_inj, 1),
                               "t_trigger_s": round(t_trig, 1), "infer_ms": infer_ms, "hidden_from_engine": list(HIDDEN),
                               "engine_state": visible, "result": result, "history_window": window},
                              ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({"scenario": a.scenario, "t_trigger_s": round(t_trig, 1), "infer_ms": infer_ms,
                      "candidates": {c["id"]: c["status"] for c in result["candidates"]},
                      "action": result["action"], "sections": [x["sid"] for x in result["sections"]]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
