"""[측정 도구] 새 베이스 고장 주입 → 첫 알람 도착 시간(V1 fault_onset.py 와 같은 기대 알람·같은 10초 기준).
V1 과 다른 점은 '화면' 지점뿐이다.
  - Kafka sensor.alerts(+ 결측은 sensor.telemetry.clean 의 비-GOOD 레코드) — V1 과 같은 지점
  - 화면: 공정 고장(스파이크·히터·결측)은 FUXA 공정 알람(/api/alarms, OT 안에서 FUXA 가 직접 판정),
          분석 경고(베어링 CEP·잡음 Z-Score·드리프트 ML)는 FUXA 가 구독하는 OT 허브 표시 토픽(AR-100/alert/display).
    표시 토픽은 같은 설비·규칙의 열린 묶음이 60초 조용해야 새로 뜨므로(17번 F4) 분석 고장은 회차 사이를 --gap-s 로 띄운다.
  base_client python tests/e2e/fault_onset_base.py --reps 3 --out /repo/experiments/<EXP>/raw/onset_base.json
"""
import argparse, base64, json, os, threading, time, urllib.request, uuid
import sys
import paho.mqtt.client as mqtt
from confluent_kafka import Consumer

sys.path.insert(0, "/repo/tests/e2e")
from ot_ops import Operator  # noqa: E402

EXPECT = {   # V1 fault_onset.py 와 같은 기대 알람
    "spike":        lambda a: a["tag"] == "PT-101" and a.get("alert_type") == "THRESHOLD_USL",
    "heater_stuck": lambda a: a["tag"] == "TT-101" and a.get("alert_type") == "THRESHOLD_USL",
    "bearing_wear": lambda a: a["tag"] == "VT-101" and a.get("alert_type") == "CEP_BEARING",
    "noise":        lambda a: a["tag"] == "TT-101" and a.get("alert_type") == "ZSCORE",
    "dropout":      lambda a: a["tag"] == "TT-101" and a.get("quality") not in (None, "GOOD"),
    "drift":        lambda a: a.get("alert_type") == "ML_AUTOENCODER",
}
SCREEN = {   # 화면 지점: ("fuxa", 알람 이름에 든 글자들 중 하나) 또는 ("display", 기대 알람 조건) 또는 None(V1 처럼 화면 판정 제외)
    # 스파이크: 운전원에게 뜨는 공정 알람은 '고압 인터록 발동'(지연 0)이다. PT-101 규격 알람은 ISA-18.2 on-delay 2 s 라
    #           인터록이 펌프를 끄기까지 약 2 s 인 지시값 튐을 거른다(설계). 둘 중 먼저 뜬 것을 화면 도착으로 본다.
    # 결측: 태그 하나의 결측은 화면 알람이 없는 고장이다(V1 fault_onset.py 도 화면 판정 제외, 정제 토픽의 보간 레코드로만 본다).
    "spike": ("fuxa", ("PT-101", "인터록")), "heater_stuck": ("fuxa", ("TT-101",)), "dropout": None,
    "bearing_wear": ("display", EXPECT["bearing_wear"]), "noise": ("display", EXPECT["noise"]), "drift": ("display", EXPECT["drift"]),
}
ap = argparse.ArgumentParser(); ap.add_argument("--reps", type=int, default=3); ap.add_argument("--out", required=True)
ap.add_argument("--limit-s", type=float, default=12.0); ap.add_argument("--faults", default=",".join(EXPECT))
ap.add_argument("--sim", default="http://plant-sim:8080"); ap.add_argument("--fuxa", default="http://fuxa:1881")
ap.add_argument("--broker", default="ot-hub"); ap.add_argument("--display-topic", default="AR-100/alert/display")
ap.add_argument("--gap-s", type=float, default=65.0, help="분석 고장 회차 사이 간격(표시 묶음이 닫히도록)")
a = ap.parse_args()
AUTH = {"Authorization": "Basic " + base64.b64encode(f'{os.environ["SIM_USER"]}:{os.environ["SIM_PASSWORD"]}'.encode()).decode()}


def http(url, body=None, auth=True):
    r = urllib.request.Request(url, json.dumps(body).encode() if body is not None else None,
                               {"Content-Type": "application/json", **(AUTH if auth else {})}, method="POST" if body is not None else "GET")
    return json.load(urllib.request.urlopen(r, timeout=10))


lock, events = threading.Lock(), []
kc = Consumer({"bootstrap.servers": "kafka:9092", "group.id": f"onset-{uuid.uuid4().hex[:6]}", "auto.offset.reset": "latest"})
assigned = threading.Event()
kc.subscribe(["sensor.alerts", "sensor.telemetry.clean"], on_assign=lambda c, parts: assigned.set())


def kloop():
    while True:
        m = kc.poll(0.1)
        if m is not None and not m.error():
            try:
                al = json.loads(m.value())
            except ValueError:
                continue
            if m.topic() == "sensor.telemetry.clean" and al.get("quality") == "GOOD":
                continue
            with lock:
                events.append(("kafka", time.time(), al))


fuxa_active: set = set()


def floop():   # FUXA 활성 알람: FUXA 가 기록한 켜진 시각(ontime)이 새로운 활성만 이벤트로(이미 켜져 있던 것은 세지 않는다)
    global fuxa_active
    seen = set()
    while True:
        try:
            now = {(x.get("name") or "", x.get("ontime")) for x in http(a.fuxa + "/api/alarms", auth=False)
                   if x.get("status") in ("N", "NA")}
            for name, on in now - seen:
                with lock:
                    events.append(("fuxa", time.time(), {"name": name, "ontime": on, "ts": time.time_ns()}))
            seen |= now
            fuxa_active = {n for n, _ in now}
        except Exception:
            pass
        time.sleep(0.2)


def on_mqtt(c, u, msg):
    try:
        al = json.loads(msg.payload)
    except ValueError:
        return
    if isinstance(al, dict) and "alert_type" in al:
        with lock:
            events.append(("display", time.time(), al))


threading.Thread(target=kloop, daemon=True).start(); threading.Thread(target=floop, daemon=True).start()
mc = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"onset-{uuid.uuid4().hex[:6]}")
mc.username_pw_set(os.environ["MQTT_USER"], os.environ["MQTT_PASS"])
mc.on_connect = lambda c, u, f, rc, p=None: c.subscribe(a.display_topic, 1)
mc.on_message = on_mqtt
mc.connect(a.broker, 1883); mc.loop_start()
if not assigned.wait(30):
    raise SystemExit("Kafka 파티션 배정 30 s 안에 안 됨")
time.sleep(2)


def screen_hit(fault, src, al):
    if SCREEN[fault] is None:
        return False
    kind, cond = SCREEN[fault]
    if src != kind:
        return False
    return any(c in al.get("name", "") for c in cond) if kind == "fuxa" else ("tag" in al and cond(al))


OPERATOR = Operator()
results = {}
for fault in a.faults.split(","):
    match, lat = EXPECT[fault], []
    for i in range(a.reps):
        http(a.sim + "/fault/clear", {}); time.sleep(3)
        if SCREEN[fault] and SCREEN[fault][0] == "display":
            # 표시 묶음은 같은 규칙의 alert 가 60 s 조용해야 닫힌다. 고장을 풀어도 ML(10 스캔 창)·Z-Score(60 표본 창) alert 는
            # 한동안 이어지므로 고정 간격이 아니라 '그 규칙의 alert 가 gap_s 동안 없을 때까지' 기다린다(09-30 첫 실행 교훈)
            w0 = time.time()
            while time.time() - w0 < 300:
                with lock:
                    last = max((ts for src, ts, al in events if src == "kafka" and isinstance(al, dict) and "tag" in al and match(al)), default=0)
                if time.time() - max(last, w0 - a.gap_s + 3) >= a.gap_s:
                    break
                time.sleep(1)
        if SCREEN[fault] and SCREEN[fault][0] == "fuxa":
            # 앞 회차의 공정 알람(인터록·규격)이 꺼진 뒤에 주입한다 — 켜진 채면 새 활성이 생기지 않는다
            w0 = time.time()
            while time.time() - w0 < 90 and any(any(c in n for c in SCREEN[fault][1]) for n in fuxa_active):
                time.sleep(0.5)
        t0 = time.time(); http(a.sim + "/fault", {"scenario": fault})
        got = {}
        while time.time() - t0 < a.limit_s and len(got) < (2 if SCREEN[fault] else 1):
            with lock:
                for src, ts, al in events:
                    if ts < t0 or not isinstance(al, dict):
                        continue
                    if src == "kafka" and "kafka" not in got and "tag" in al and (al.get("ts") or 0) / 1e9 >= t0 - 1.0 and match(al):
                        got["kafka"] = round(ts - t0, 2)
                    if "screen" not in got and screen_hit(fault, src, al):
                        got["screen"] = round(ts - t0, 2)
            time.sleep(0.05)
        lat.append(got)
        print(fault, i, got, flush=True)
        if fault == "spike":                      # 인터록 트립 기억: 운전원 리셋·펌프 재기동 뒤 다음 회
            http(a.sim + "/fault/clear", {})
            OPERATOR.recover_interlock()
        if os.environ.get("ONSET_DEBUG"):
            with lock:
                print("  fuxa 이벤트:", [(round(ts - t0, 2), al.get("name")) for src, ts, al in events if src == "fuxa" and ts >= t0 - 5], flush=True)
    http(a.sim + "/fault/clear", {})
    k = [g["kafka"] for g in lat if "kafka" in g]; s = [g["screen"] for g in lat if "screen" in g]
    need_screen = SCREEN[fault] is not None
    results[fault] = {"reps": lat, "screen": SCREEN[fault][0] if need_screen else "제외(V1 과 같음)",
                      "kafka_max_s": max(k) if k else None, "screen_max_s": max(s) if s else None,
                      "missing": sum(1 for g in lat if "kafka" not in g),
                      "within_10s": len(k) == a.reps and max(k) <= 10 and (not need_screen or (len(s) == a.reps and max(s) <= 10))}
    time.sleep(1)
out = {"limit_s": a.limit_s, "results": results, "all_within_10s": all(r["within_10s"] for r in results.values()),
       "physics_time_scale": http(a.sim + "/state").get("physics_time_scale")}
json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({f: (r["kafka_max_s"], r["screen_max_s"], r["within_10s"]) for f, r in results.items()}, ensure_ascii=False), out["all_within_10s"])
