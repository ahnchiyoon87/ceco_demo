"""L4 리플레이어: S02·S04~S08 케이스를 이벤트 시간 그대로 입력 토픽에 발행한다.

    python /repo/harness/tools/replay.py --exp EXP-141 --run r1 [--topic exp.l4.raw]

- 케이스마다 장치 ID 를 따로 준다(CEP 는 device 로 PARTITION). 반복 3회.
- 배경값: plant.yaml 규격 안의 합성 정상값(고정 시드). 실측값 아님 → manifest 에 synthetic 으로 기록.
- 레코드 = harness/SCHEMA.md raw 형식 + trace_id·emit_ns·case (추가 필드).
- 기대결과는 scenarios/catalog.yaml 에서 가져와 manifest 에 함께 기록한다(실행 전에 고정).
"""
import argparse
import json
import pathlib
import random
import time
import uuid

import yaml
from confluent_kafka import Producer

CAT = yaml.safe_load(open("/repo/scenarios/catalog.yaml", encoding="utf-8"))
C = CAT["constants"]
N = C["pattern_window_s"]
IT, VT = C["it102_limit_a"], C["vt101_limit_mms"]
WM = C["watermark_s"]

# 합성 정상값: IT-102 는 정격 8.0A 미만, VT-101 은 base_vibration 2.1 mm/s, 노이즈는 plant.yaml noise 값
NORMAL = {"IT-102": (7.0, 0.025), "VT-101": (2.1, 0.06), "TT-101": (72.0, 0.06)}
HIGH_IT, HIGH_VT, HIGH_TT = IT + 0.3, VT + 0.4, 96.0

WARMUP_S = 20      # 배경만 흘려 윈도·워터마크를 채우는 구간
TAIL_S = 30        # 마지막 이벤트 뒤 워터마크를 밀어내는 구간


def cases():
    """(case, 기대 CEP 건수 또는 None, 이벤트 목록[(event_offset_s, emit_delay_s, tag, value)], 반복 발행 횟수)"""
    lst = [
        ("S02", None, [(0, 0, "TT-101", HIGH_TT)], 1),
        ("S04", 1, [(0, 0, "IT-102", HIGH_IT), (6, 0, "VT-101", HIGH_VT)], 1),
        ("S05", 0, [(0, 0, "VT-101", HIGH_VT), (6, 0, "IT-102", HIGH_IT)], 1),
        ("S06a", 1, [(0, 0, "IT-102", HIGH_IT), (N - 0.5, 0, "VT-101", HIGH_VT)], 1),
        ("S06b", 0, [(0, 0, "IT-102", HIGH_IT), (N + 0.5, 0, "VT-101", HIGH_VT)], 1),
        # 진동 레코드를 이벤트 시간은 유지한 채 워터마크 지연(5s)보다 늦게 발행
        ("S07", "policy", [(0, 0, "IT-102", HIGH_IT), (6, WM + 3, "VT-101", HIGH_VT)], 1),
        ("S08a", 1, [(0, 0, "IT-102", HIGH_IT), (6, 0, "VT-101", HIGH_VT)], 2),
        ("S08b", 1, [(0, 0, "IT-102", HIGH_IT), (6, 0, "VT-101", HIGH_VT)], 1),  # 배경 IT-102 3점 누락
        # S09: S04 와 같은 패턴. 처리기 kill/start 는 harness/s09.sh 가 manifest 의 t0_event_ns 기준으로 수행
        ("S09", 1, [(0, 0, "IT-102", HIGH_IT), (6, 0, "VT-101", HIGH_VT)], 1),
    ]
    return lst


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--topic", default="exp.l4.raw")
    ap.add_argument("--repeat", type=int, default=C["repeat"])
    ap.add_argument("--seed", type=int, default=20260928)
    ap.add_argument("--cases", default="S02,S04,S05,S06a,S06b,S07,S08a,S08b",
                    help="쉼표 구분 케이스 이름 (S09 는 s09.sh 와 함께만 사용)")
    ap.add_argument("--require-jobs", type=int, default=0,
                    help="FLINK_REST 의 RUNNING 잡이 이 수 이상이고 비정상 잡이 없을 때만 발행 (0=점검 안 함)")
    a = ap.parse_args()

    if a.require_jobs:
        import urllib.request
        jobs = json.load(urllib.request.urlopen(__import__("os").environ["FLINK_REST"] + "/jobs/overview", timeout=10))["jobs"]
        states = {j["name"]: j["state"] for j in jobs}
        running = [n for n, s in states.items() if s == "RUNNING"]
        if len(running) < a.require_jobs or len(running) != len(states):
            raise SystemExit(f"사전 점검 실패: 잡 상태 {states} — 발행하지 않음")
        print("사전 점검 통과:", states)

    rng = random.Random(a.seed)
    t0_wall = time.time() + 2
    t0_event = t0_wall + WARMUP_S
    plan = []   # (emit_at_wall, record)
    expected = {}
    last = 0.0
    wanted = set(a.cases.split(","))
    for name, exp_count, events, dup in [c for c in cases() if c[0] in wanted]:
        for rep in range(1, a.repeat + 1):
            device = f"{a.run}-{name}-{rep}"
            expected[device] = {"case": name, "expected_cep": exp_count}
            tags = {tag for _, _, tag, _ in events} | {"IT-102", "VT-101"}
            special = {(off, tag) for off, _, tag, _ in events}
            horizon = WARMUP_S + max(off for off, _, _, _ in events) + TAIL_S
            for sec in range(0, int(horizon) + 1):
                off = sec - WARMUP_S
                for tag in sorted(tags):
                    if (off, tag) in special:
                        continue
                    if name == "S08b" and tag == "IT-102" and off in (-3, -2, -1):
                        continue  # 누락 3점
                    mu, sd = NORMAL[tag]
                    plan.append((t0_wall + sec, make(device, tag, t0_wall + sec, mu + rng.gauss(0, sd), name, "background")))
            for off, delay, tag, value in events:
                ev_t = t0_event + off
                for k in range(dup):
                    plan.append((ev_t + delay + 0.001 * k, make(device, tag, ev_t, value, name, "inject")))
            last = max(last, t0_wall + horizon)

    out = pathlib.Path(f"/experiments/{a.exp}/raw")
    out.mkdir(parents=True, exist_ok=True)
    plan.sort(key=lambda x: x[0])
    manifest = {"exp": a.exp, "run": a.run, "topic": a.topic, "seed": a.seed, "repeat": a.repeat,
                "background": "synthetic (plant.yaml 규격·노이즈 기반, 실측 아님)", "normal": NORMAL,
                "high": {"IT-102": HIGH_IT, "VT-101": HIGH_VT, "TT-101": HIGH_TT},
                "window_s": N, "watermark_s": WM, "t0_event_ns": int(t0_event * 1e9),
                "records": len(plan), "expected": expected}
    (out / f"replay_{a.run}_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=1), encoding="utf-8")

    p = Producer({"bootstrap.servers": __import__("os").environ["BOOTSTRAP"], "acks": "all", "linger.ms": 5})
    log = open(out / f"replay_{a.run}_emitted.jsonl", "w", encoding="utf-8")
    for emit_at, rec in plan:
        wait = emit_at - time.time()
        if wait > 0:
            time.sleep(wait)
        rec["emit_ns"] = time.time_ns()
        body = json.dumps(rec)
        p.produce(a.topic, key=rec["tag"], value=body)
        p.poll(0)
        log.write(body + "\n")
    p.flush(30)
    log.close()
    print(f"emitted {len(plan)} records, devices {len(expected)}, event span {last - t0_wall:.0f}s")


def make(device, tag, t, value, case, kind):
    return {"ts": int(t * 1e9), "site": "AR-100", "device": device, "tag": tag, "value": round(value, 4),
            "quality": "GOOD", "trace_id": str(uuid.uuid4()), "case": case, "kind": kind}


if __name__ == "__main__":
    main()
