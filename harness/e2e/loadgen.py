"""[측정 도구] R08 과부하: 실제 장치와 같은 EdgeX 이벤트 형식으로 가상 장치 N대분을 1초마다 추가 발행.
값은 정상 범위(알람 없음). 파이프라인 부하만 늘린다.
  python harness/e2e/loadgen.py --mqtt emqx --topic edgex/telemetry --devices 10 --seconds 600
"""
import argparse, json, random, time, uuid
import paho.mqtt.client as mqtt

NORMAL = {"LT-101": 80, "LT-102": 55, "TT-101": 72, "TT-102": 76, "PT-101": 3.1, "FT-101": 6.3, "FT-102": 6.2,
          "IT-101": 6.3, "IT-102": 6.8, "VT-101": 2.0, "pH-101": 7.4, "CT-101": 3.3}

ap = argparse.ArgumentParser()
ap.add_argument("--mqtt", default="emqx"); ap.add_argument("--topic", default="edgex/telemetry")
ap.add_argument("--devices", type=int, default=10); ap.add_argument("--seconds", type=int, default=600)
a = ap.parse_args()
c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"loadgen-{uuid.uuid4().hex[:6]}")
c.connect(a.mqtt, 1883); c.loop_start()
sent, t_end, nxt = 0, time.time() + a.seconds, time.time()
while time.time() < t_end:
    now = time.time_ns()
    for d in range(a.devices):
        dev = f"load-{d:02d}"
        ev = {"apiVersion": "v3", "id": str(uuid.uuid4()), "deviceName": dev, "profileName": "AR100-Reactor-Line",
              "sourceName": "AllSensors", "origin": now,
              "readings": [{"id": str(uuid.uuid4()), "origin": now, "deviceName": dev, "resourceName": t,
                            "profileName": "AR100-Reactor-Line", "valueType": "Float32", "units": "",
                            "value": f"{v * (1 + random.gauss(0, 0.002)):.6e}"} for t, v in NORMAL.items()]}
        c.publish(a.topic, json.dumps(ev), qos=1); sent += 1
    nxt += 1.0
    time.sleep(max(0.0, nxt - time.time()))
c.loop_stop()
print(json.dumps({"events_sent": sent, "devices": a.devices, "seconds": a.seconds}))
