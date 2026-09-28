"""브로커 기동 대기: MQTT CONNECT 가 성공(rc 0)할 때까지 재시도. 실패 시 종료코드 1(② 기동 탈락 근거)."""
import argparse
import os
import sys
import time

import paho.mqtt.client as mqtt

ap = argparse.ArgumentParser()
ap.add_argument("--broker", required=True)
ap.add_argument("--timeout", type=float, default=120)
a = ap.parse_args()
t0 = time.time()
last = None
while time.time() - t0 < a.timeout:
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"wait-{int(time.time()*1000)}", protocol=mqtt.MQTTv311)
    if os.environ.get("BENCH_MQTT_USER"):
        c.username_pw_set(os.environ["BENCH_MQTT_USER"], os.environ.get("BENCH_MQTT_PASS", ""))
    try:
        rc = c.connect(a.broker, 1883, keepalive=10)
        if rc == 0:
            for _ in range(6):
                c.loop(timeout=0.5)
                if c.is_connected():
                    break
            if c.is_connected():
                c.disconnect()
                print(f"ready {a.broker} after {time.time()-t0:.1f}s")
                sys.exit(0)
        last = f"rc={rc}"
    except OSError as e:
        last = f"{type(e).__name__}: {e}"
    time.sleep(3)
print(f"NOT READY {a.broker} in {a.timeout}s: {last}")
sys.exit(1)
