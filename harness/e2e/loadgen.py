"""[측정 도구] R08 과부하: 실제 장치와 같은 EdgeX 이벤트 형식으로 가상 장치 N대분을 1초마다 추가 발행.
값은 정상 범위(알람 없음). 파이프라인 부하만 늘린다.
  python harness/e2e/loadgen.py --mqtt emqx --topic edgex/telemetry --devices 10 --seconds 600
  --kafka kafka:9092 이면 원시 입구가 Kafka 인 구조(V2: 수집기가 Kafka 에 바로 씀)용 — 같은 장치·같은 값으로 V1 raw 레코드
  ({ts,site,device,tag,value,quality}, 키 = tag)를 sensor.telemetry.raw 에 직접 넣는다(#109). 부하 크기(장치 수 × 12태그/s)는 같다.
"""
import argparse, json, random, time, uuid
import paho.mqtt.client as mqtt

NORMAL = {"LT-101": 80, "LT-102": 55, "TT-101": 72, "TT-102": 76, "PT-101": 3.1, "FT-101": 6.3, "FT-102": 6.2,
          "IT-101": 6.3, "IT-102": 6.8, "VT-101": 2.0, "pH-101": 7.4, "CT-101": 3.3}

ap = argparse.ArgumentParser()
ap.add_argument("--mqtt", default="emqx"); ap.add_argument("--topic", default="edgex/telemetry")
ap.add_argument("--devices", type=int, default=10); ap.add_argument("--seconds", type=int, default=600)
ap.add_argument("--kafka", default=None, help="원시 입구가 Kafka 인 구조: 부트스트랩 주소")
a = ap.parse_args()
if a.kafka:
    from confluent_kafka import Producer
    pr = Producer({"bootstrap.servers": a.kafka, "compression.type": "lz4", "acks": "all"})
else:
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"loadgen-{uuid.uuid4().hex[:6]}")
    c.connect(a.mqtt, 1883); c.loop_start()
sent, t_end, nxt = 0, time.time() + a.seconds, time.time()
while time.time() < t_end:
    now = time.time_ns()
    for d in range(a.devices):
        dev = f"load-{d:02d}"
        if a.kafka:
            for t, v in NORMAL.items():
                pr.produce("sensor.telemetry.raw", key=t, value=json.dumps({"ts": now, "site": "AR-100", "device": dev, "tag": t,
                           "value": float(f"{v * (1 + random.gauss(0, 0.002)):.6e}"), "quality": "GOOD"}))
            pr.poll(0); sent += 1
            continue
        ev = {"apiVersion": "v3", "id": str(uuid.uuid4()), "deviceName": dev, "profileName": "AR100-Reactor-Line",
              "sourceName": "AllSensors", "origin": now,
              "readings": [{"id": str(uuid.uuid4()), "origin": now, "deviceName": dev, "resourceName": t,
                            "profileName": "AR100-Reactor-Line", "valueType": "Float32", "units": "",
                            "value": f"{v * (1 + random.gauss(0, 0.002)):.6e}"} for t, v in NORMAL.items()]}
        c.publish(a.topic, json.dumps(ev), qos=1); sent += 1
    nxt += 1.0
    time.sleep(max(0.0, nxt - time.time()))
if a.kafka:
    pr.flush(30)
else:
    c.loop_stop()
print(json.dumps({"events_sent": sent, "devices": a.devices, "seconds": a.seconds}))
