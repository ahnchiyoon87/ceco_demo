"""[측정 도구] FUXA 와 같은 운전원 명령(FUXA 계정, …/cmd/operator)과 PLC 상태 읽기 — 측정 클라이언트 안에서 쓴다.
인터록은 트립을 기억하므로 스파이크 시험 뒤에는 운전원이 리셋하고 펌프를 다시 켜야 다음 회가 정상 운전점에서 시작한다.
    from ot_ops import Operator;  op = Operator();  op.recover_interlock()
"""
import json, os, threading, time, uuid

import paho.mqtt.client as mqtt

REG = json.load(open("registry/generated/tags.json", encoding="utf-8"))
TOPIC = {(c["asset"], c["name"]): c["operator_topic"] for c in REG["commands"]}
ACK = REG["plc"]["ack_operator_topic"]
LINE = REG["line_prefix"]


class Operator:
    def __init__(self, host="ot-hub"):
        self.status, self.acks, self.lock = {}, [], threading.Lock()
        self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"op-{uuid.uuid4().hex[:6]}")
        self.c.username_pw_set("fuxa", os.environ["MQTT_FUXA_PASSWORD"])
        self.c.on_connect = lambda cl, u, f, rc, p=None: [cl.subscribe(t, 1) for t in (f"{LINE}/+/status/+", ACK)]
        self.c.on_message = self._msg
        self.c.connect(host, 1883)
        self.c.loop_start()
        end = time.time() + 10
        while time.time() < end and ("PLC-01", "interlock") not in self.status:
            time.sleep(0.1)

    def _msg(self, cl, u, m):
        try:
            body = json.loads(m.payload)
        except ValueError:
            return
        if m.topic == ACK:
            with self.lock:
                self.acks.append((time.time(), body))
        else:
            p = m.topic.split("/")
            self.status[(p[3], p[5])] = body.get("value")

    def send(self, asset, name, value, timeout=6):
        """명령을 내고 PLC ACK 결과 이름을 돌려준다(없으면 None)."""
        topic, t0 = TOPIC[(asset, name)], time.time()
        ts = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + f".{int(time.time() * 1000) % 1000:03d}Z"
        self.c.publish(topic, json.dumps({"command": name, "value": value, "ts": ts}), qos=1)
        while time.time() - t0 < timeout:
            with self.lock:
                for t, b in self.acks:
                    if t >= t0 and (b.get("command") or {}).get("topic") == topic:
                        return b.get("result")
            time.sleep(0.05)
        return None

    def recover_interlock(self, timeout=120):
        """트립이 걸려 있으면 압력이 내려와 리셋이 받아질 때까지 리셋하고, 펌프를 다시 켠다."""
        out = {"tripped": self.status.get(("PLC-01", "interlock")) is True, "resets": 0}
        if out["tripped"]:
            end = time.time() + timeout
            while time.time() < end and self.status.get(("PLC-01", "interlock")) is True:
                out["resets"] += 1
                out["last_reset_ack"] = self.send("PLC-01", "interlock_reset", 1)
                time.sleep(1)
            out["released"] = self.status.get(("PLC-01", "interlock")) is False
        if self.status.get(("P-101", "run")) is False:
            out["pump_start_ack"] = self.send("P-101", "run", True)
        return out
