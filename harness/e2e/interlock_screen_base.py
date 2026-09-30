"""[측정 도구] 짧은 과압(스파이크 2 s)에도 FUXA 공정 알람에 인터록이 뜨고, 트립을 기억하는 동안 켜져 있다가 운전원 리셋 뒤 꺼지는지.
트립 기억 전에는 인터록이 약 0.5 s 만 켜져 FUXA(알람 검사 1 s 주기)가 보지 못했다(BASE_VERIFY §5).
    base_client python harness/e2e/interlock_screen_base.py --reps 3 --out /repo/experiments/<EXP>/raw/interlock_screen.json
"""
import argparse, base64, json, os, sys, time, urllib.request

sys.path.insert(0, "/repo/harness/e2e")
from ot_ops import Operator  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--reps", type=int, default=3); ap.add_argument("--out", required=True)
ap.add_argument("--sim", default="http://plant-sim:8080"); ap.add_argument("--fuxa", default="http://fuxa:1881")
a = ap.parse_args()
AUTH = {"Authorization": "Basic " + base64.b64encode(f'{os.environ["SIM_USER"]}:{os.environ["SIM_PASSWORD"]}'.encode()).decode()}


def http(url, body=None, auth=True):
    r = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None,
                               {"Content-Type": "application/json", **(AUTH if auth else {})}, method="POST" if body is not None else "GET")
    return json.load(urllib.request.urlopen(r, timeout=10))


def ilk_alarm():
    return any("인터록" in (x.get("name") or "") and x.get("status") in ("N", "NA") for x in http(a.fuxa + "/api/alarms", auth=False))


def wait(pred, timeout):
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.2)
    return pred()


op, runs = Operator(), []
for i in range(a.reps):
    http(a.sim + "/fault/clear", {})
    op.recover_interlock()
    wait(lambda: not ilk_alarm(), 30)
    ready = wait(lambda: http(a.sim + "/state")["readings"]["PT-101"] >= 3.0, 180)   # 스파이크(+3.6)가 트립 값을 넘는 운전점
    t0 = time.time(); http(a.sim + "/fault", {"scenario": "spike", "duration_s": 2})
    seen = wait(ilk_alarm, 10); t_seen = round(time.time() - t0, 2) if seen else None
    wait(lambda: time.time() - t0 >= 8, 10)                                          # 스파이크가 끝나고 6 s 뒤
    held = ilk_alarm() and op.status.get(("PLC-01", "interlock")) is True
    rec = op.recover_interlock()
    cleared = wait(lambda: not ilk_alarm(), 15)
    r = {"ready": ready, "alarm_seen_s": t_seen, "held_after_spike": held, "released": rec.get("released"), "alarm_cleared": cleared,
         "pass": ready and seen and held and rec.get("released") is True and cleared}
    runs.append(r); print(i, r, flush=True)
http(a.sim + "/fault/clear", {})
out = {"runs": runs, "pass": all(r["pass"] for r in runs)}
json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({"pass": out["pass"]}))
