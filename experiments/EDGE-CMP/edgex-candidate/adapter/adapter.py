"""EdgeX 엣지의 UNS 어댑터 + OT 작업 요청 수신기(엣지 후보 EdgeX 4.0.2 에서 EdgeX 가 기본으로 주지 않는 부분).

EdgeX 가 하는 일: 장치 등록(device-modbus + 프로파일), 읽기(자동 이벤트 250 ms), 명령 창구(core-command),
                 끊김 시 저장 후 전송(app-service mqtt-export → OT 허브 edgex/telemetry).
이 어댑터가 하는 일: edgex/telemetry 의 EdgeX 이벤트를 UNS 토픽(값·품질·순번·설비 시각)·상태·ACK·통신 상태로 바꿔 내고,
                    운전원·외부 요청 명령을 core-command 로 PLC 명령 채널에 쓰고, PLC 시각을 동기하고,
                    OT 작업 요청 수신기(전용 MQTT 계정)를 돈다. 규칙은 Node-RED 후보의 흐름과 같다(edge/nodered/src).
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import jsonschema
import paho.mqtt.client as mqtt

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s | %(message)s")
log = logging.getLogger("edgex-adapter")
REG = json.load(open("/opt/ar100/registry/tags.json", encoding="utf-8"))
WM = json.load(open("/opt/ar100/registry/work_masters.ot.json", encoding="utf-8"))
SCHEMA = json.load(open("/opt/ar100/registry/schemas/job_request.schema.json", encoding="utf-8"))
PLC = REG["plc"]
LINE = REG["line_prefix"]
COMMAND = os.environ.get("EDGEX_COMMAND_URL", "http://edgex-core-command:59882")
DEVICE = PLC["asset"]
counters = {"published": 0, "requests": 0, "rejected": 0, "cmd_errors": 0}
lock = threading.Lock()


def now_ns() -> int:
    return time.time_ns()


def iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime()) + ".%03dZ" % (int(time.time() * 1000) % 1000)


class Edge:
    """수집·명령(edge 계정)."""

    def __init__(self):
        self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="edge-01", clean_session=True)
        self.c.username_pw_set("edge", os.environ["MQTT_EDGE_PASSWORD"])
        node = f"{LINE}/EDGE-01/state/node"
        self.c.will_set(node, json.dumps({"value": False, "quality": "GOOD"}), qos=1, retain=True)
        self.c.on_connect = self.on_connect
        self.c.on_message = self.on_message
        self.last_seq = None
        self.last_pub: dict[str, dict] = {}
        self.status: dict | None = None
        self.status_last: dict[str, object] = {}
        self.full_at = 0.0
        self.hb = (-1, time.time())
        self.op_seq = None
        self.rq_seq = None
        self.op_by_seq: dict[int, dict] = {}
        self.job_by_hash: dict[int, str] = {}
        self.plc_online = None
        self.last_values_at = time.time()

    def start(self):
        self.c.connect_async("ot-hub", 1883, keepalive=15)
        self.c.reconnect_delay_set(1, 5)
        self.c.loop_start()
        threading.Thread(target=self.time_sync, daemon=True).start()
        threading.Thread(target=self.comm_watch, daemon=True).start()

    def on_connect(self, c, u, flags, rc, props=None):
        log.info("OT 허브 연결(edge): %s", rc)
        c.publish(f"{LINE}/EDGE-01/state/node", json.dumps({"value": True, "quality": "GOOD"}), qos=1, retain=True)
        c.subscribe([(REG["legacy_telemetry_topic"], 1), (f"{LINE}/+/cmd/operator", 1), (f"{LINE}/+/cmd/request", 1)])

    def pub(self, topic, payload, retain=False):
        self.c.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1, retain=retain)
        with lock:
            counters["published"] += 1

    def on_message(self, c, u, m):
        try:
            if m.topic == REG["legacy_telemetry_topic"]:
                ev = json.loads(m.payload)
                if ev.get("sourceName") == "Values":
                    self.values(ev)
                elif ev.get("sourceName") == "Status":
                    self.on_status(ev)
            elif m.topic.endswith("/cmd/operator"):
                self.operator(m)
            elif m.topic.endswith("/cmd/request"):
                self.request(m)
        except Exception:
            log.exception("메시지 처리 실패: %s", m.topic)

    # ── 값: EdgeX 이벤트(Values) → UNS ──
    def values(self, ev):
        r = {x["resourceName"]: x["value"] for x in ev.get("readings", [])}
        if "SEQ" not in r or "PTS" not in r:
            return
        seq, pts = int(float(r["SEQ"])), int(float(r["PTS"]))
        if seq == self.last_seq:
            return
        self.last_seq = seq
        self.last_values_at = time.time()
        field_ok = bool(self.status and self.status.get("field_comm") == 1)
        ts = now_ns()
        for t in REG["tags"]:
            raw = r.get(t["tag"])
            v = float(raw) if raw is not None else None
            value = round(v, 4) if v is not None and v > -1000 else None
            quality = "BAD" if value is None else ("GOOD" if field_ok else "STALE")
            lp = self.last_pub.get(t["tag"])
            due = (not lp or lp["quality"] != quality or value is None or lp["value"] is None
                   or abs(value - lp["value"]) >= t["deadband"] or pts < lp["pts"] or pts - lp["pts"] >= t["max_interval_s"])
            if due:
                self.pub(t["topic"], {"ts": ts, "value": value, "quality": quality, "seq": seq, "pts": pts})
                self.last_pub[t["tag"]] = {"value": value, "quality": quality, "pts": pts}

    # ── 상태: EdgeX 이벤트(Status) → UNS 상태·ACK ──
    def on_status(self, ev):
        r = {x["resourceName"]: int(float(x["value"])) for x in ev.get("readings", [])}
        s = {f: r.get(f"ST_{f.upper()}") for f in PLC["read_status"]["fields"]}
        if any(v is None for v in s.values()):
            return
        prev, self.status = self.status, s
        now = time.time()
        if s["heartbeat"] != self.hb[0]:
            self.hb = (s["heartbeat"], now)
        P = f"{LINE}/{DEVICE}"
        values = {f"{P}/status/mode": PLC["modes"].get(str(s["mode"]), "UNKNOWN"),
                  f"{P}/status/maintenance": s["maintenance"] == 1, f"{P}/status/maint_operator": s["maint_operator"],
                  f"{P}/status/interlock": s["interlock"] == 1, f"{P}/status/estop": s["estop"] == 1,
                  f"{P}/status/field_comm": s["field_comm"] == 1,
                  f"{P}/status/run_state": "STOP" if now - self.hb[1] > 2 else "RUN", f"{P}/status/fb_fault": s["fb_fault"]}
        sp = {"P-101/speed_sp": s["sp_pump"], "CV-101/open_sp": s["sp_valve"], "R-101/temp_sp": s["sp_temp_x10"]}
        for c in REG["commands"]:
            key = f'{c["asset"]}/{c["name"]}'
            if key in PLC["outputs_bits"]:
                values[c["status_topic"]] = ((s["outputs"] >> PLC["outputs_bits"][key]) & 1) == 1
            elif key in sp:
                values[c["status_topic"]] = sp[key] / (c.get("scale") or 1)
        full = now - self.full_at >= PLC["state_max_interval_wall_s"]
        if full:
            self.full_at = now
        ts = now_ns()
        for topic, value in values.items():
            if full or self.status_last.get(topic) != value:
                self.pub(topic, {"ts": ts, "value": value, "quality": "GOOD"}, retain=True)
                self.status_last[topic] = value
        if prev is None:
            self.op_seq, self.rq_seq = s["op_ack_seq"], s["rq_ack_seq"]
            return
        codes = PLC["ack_codes"]
        if s["op_ack_seq"] != prev["op_ack_seq"]:
            self.pub(PLC["ack_operator_topic"], {"ts": ts, "source": "plc", "seq": s["op_ack_seq"], "code": s["op_ack_code"],
                                                 "result": codes.get(str(s["op_ack_code"]), "UNKNOWN"),
                                                 "command": self.op_by_seq.get(s["op_ack_seq"])})
        if s["rq_ack_seq"] != prev["rq_ack_seq"]:
            h = s["rq_ack_hash_hi"] * 65536 + s["rq_ack_hash_lo"]
            self.pub(PLC["ack_request_topic"], {"ts": ts, "source": "plc", "seq": s["rq_ack_seq"], "job_hash": h,
                                                "job_order_id": self.job_by_hash.get(h), "code": s["rq_ack_code"],
                                                "result": codes.get(str(s["rq_ack_code"]), "UNKNOWN")})

    # ── 장치 통신 상태(DDEATH 흉내): 이벤트가 2초 넘게 없으면 끊김 ──
    def comm_watch(self):
        while True:
            online = time.time() - self.last_values_at < 2.0
            if online != self.plc_online:
                self.plc_online = online
                ts = now_ns()
                self.pub(PLC["comm_topic"], {"ts": ts, "value": online, "quality": "GOOD"}, retain=True)
                if not online:
                    for t in REG["tags"]:
                        lp = self.last_pub.get(t["tag"])
                        if lp:
                            self.pub(t["topic"], {"ts": ts, "value": lp["value"], "quality": "STALE", "seq": self.last_seq, "pts": lp["pts"]})
                            lp["quality"] = "STALE"
            time.sleep(0.25)

    # ── core-command 로 PLC 레지스터 쓰기 ──
    def put(self, command: str, body: dict) -> bool:
        req = urllib.request.Request(f"{COMMAND}/api/v3/device/name/{DEVICE}/{command}", method="PUT",
                                     data=json.dumps({k: str(v) for k, v in body.items()}).encode(),
                                     headers={"Content-Type": "application/json"})
        try:
            with urllib.request.urlopen(req, timeout=3) as r:
                return 200 <= r.status < 300
        except Exception as exc:
            with lock:
                counters["cmd_errors"] += 1
            log.warning("core-command %s 실패: %s", command, exc)
            return False

    def time_sync(self):
        while True:
            t = int(time.time())
            self.put("TimeSync", {"TIME_HI": t >> 16, "TIME_LO": t & 0xFFFF})
            time.sleep(1 - (time.time() % 1))

    def operator(self, m):
        asset = m.topic.split("/")[3]
        ts = now_ns()

        def reject(result, extra):
            self.pub(PLC["ack_operator_topic"], {"ts": ts, "source": "edge", "result": result, "command": {"topic": m.topic, **extra}})
        try:
            body = json.loads(m.payload)
        except ValueError:
            return reject("BAD_PAYLOAD", {})
        cmd = next((c for c in REG["commands"] if c["asset"] == asset and c["name"] == body.get("command")), None)
        if not cmd:
            return reject("UNKNOWN_COMMAND", {"command": body.get("command")})
        if m.retain:
            return reject("RETAINED_COMMAND", {"command": body["command"]})
        from datetime import datetime
        try:
            age = time.time() - datetime.fromisoformat(body["ts"].replace("Z", "+00:00")).timestamp()
        except Exception:
            age = None
        if age is None or age > 5 or age < -5:
            return reject("STALE_COMMAND", {"command": body["command"], "ts": body.get("ts")})
        kind, raw = cmd["kind"], body.get("value")
        if kind == "switch":
            v = 1 if raw in (True, 1, "1", "true", "on", "ON") else 0
        elif kind == "setpoint":
            v = round(float(raw) * (cmd.get("scale") or 1))
        elif kind == "mode":
            v = {"REMOTE_MANUAL": 1, "REMOTE_AUTO": 2}.get(raw, raw)
        else:
            v = raw
        if not isinstance(v, int):
            return reject("BAD_VALUE", {"command": body["command"], "value": raw})
        self.op_seq = ((self.op_seq or 0) + 1) & 0xFFFF or 1
        self.op_by_seq[self.op_seq] = {"topic": m.topic, "command": body["command"], "value": raw, "ts": body["ts"]}
        if self.put("OpCmd", {"OP_CODE": cmd["code"], "OP_VALUE": v & 0xFFFF}):
            self.put("OpSeq", {"OP_SEQ": self.op_seq})

    def request(self, m):
        if m.retain:
            return
        b = json.loads(m.payload)
        self.rq_seq = ((self.rq_seq or 0) + 1) & 0xFFFF or 1
        self.job_by_hash[b["job_hash"]] = b["job_order_id"]
        e = int(b["expires_at"]) & 0xFFFFFFFF
        if self.put("RqCmd", {"RQ_CODE": b["code"], "RQ_VALUE": b["value"] & 0xFFFF, "RQ_EXP_HI": e >> 16,
                              "RQ_EXP_LO": e & 0xFFFF, "RQ_ACC": 1 if b["operator_accepted"] else 0,
                              "RQ_HASH_HI": b["job_hash"] >> 16, "RQ_HASH_LO": b["job_hash"] & 0xFFFF}):
            self.put("RqSeq", {"RQ_SEQ": self.rq_seq})


class Receiver:
    """OT 작업 요청 수신기(ot-receiver 계정). 규칙은 edge/nodered/src/receiver_*.js 와 같다."""

    def __init__(self):
        self.c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ot-receiver", protocol=mqtt.MQTTv5)
        self.c.username_pw_set("ot-receiver", os.environ["MQTT_RECEIVER_PASSWORD"])
        self.c.on_connect = self.on_connect
        self.c.on_message = self.on_message
        self.plc: dict = {}
        self.pending: dict[str, dict] = {}
        self.seen: dict[str, float] = {}
        self.last_snapshot = None

    def start(self):
        from paho.mqtt.properties import Properties
        from paho.mqtt.packettypes import PacketTypes
        p = Properties(PacketTypes.CONNECT)
        p.SessionExpiryInterval = 3600
        self.c.connect_async("ot-hub", 1883, keepalive=15, clean_start=False, properties=p)
        self.c.reconnect_delay_set(1, 5)
        self.c.loop_start()
        threading.Thread(target=self.timer, daemon=True).start()

    def on_connect(self, c, u, flags, rc, props=None):
        log.info("OT 허브 연결(ot-receiver): %s", rc)
        c.subscribe([(REG["request"]["in_topic"], 1), (f"{LINE}/{DEVICE}/status/+", 1),
                     (REG["request"]["decision_topic"], 1), (PLC["ack_request_topic"], 1)])

    def pub(self, topic, payload, retain=False):
        self.c.publish(topic, json.dumps(payload, ensure_ascii=False), qos=1, retain=retain)

    def resp(self, job_id, stage, status, reason, **extra):
        self.pub(f'{REG["request"]["response_prefix"]}/{job_id}',
                 {"job_order_id": job_id, "stage": stage, "status": status, "reason": reason, "ts": iso(), **extra})

    def pending_msg(self):
        now = time.time()
        items = sorted(self.pending.values(), key=lambda j: j["received_at"])
        h = items[0] if items else None
        snap = {"count": len(items), "head_job": h["job_order_id"] if h else "", "head_wm": h["work_master_id"] if h else "",
                "head_desc": h["desc"] if h else "대기 중인 요청 없음", "head_context": (h.get("context_summary") or "") if h else "",
                "items": [{"job_order_id": i["job_order_id"], "work_master_id": i["work_master_id"], "desc": i["desc"]} for i in items]}
        key = json.dumps(snap, sort_keys=True)
        if items or key != self.last_snapshot:
            snap["head_wait_s"] = round(now - h["received_at"]) if h else 0
            self.pub(REG["request"]["pending_topic"], snap, retain=True)
            self.last_snapshot = key

    def on_message(self, c, u, m):
        try:
            if m.topic == REG["request"]["in_topic"]:
                self.request(m.payload)
            elif "/status/" in m.topic:
                self.plc[m.topic.rsplit("/", 1)[1]] = json.loads(m.payload)["value"]
            elif m.topic == REG["request"]["decision_topic"]:
                self.decision(m)
            elif m.topic == PLC["ack_request_topic"]:
                a = json.loads(m.payload)
                if a.get("job_order_id"):
                    self.resp(a["job_order_id"], "plc", "ACCEPTED" if a["code"] == 0 else "REJECTED", a["result"], plc_ack_code=a["code"])
        except Exception:
            log.exception("수신기 처리 실패: %s", m.topic)

    def request(self, raw: bytes):
        with lock:
            counters["requests"] += 1
        now = time.time()
        try:
            req = json.loads(raw)
            jsonschema.validate(req, SCHEMA)
        except Exception:
            job_id = None
            try:
                job_id = json.loads(raw).get("job_order_id")
            except Exception:
                pass
            with lock:
                counters["rejected"] += 1
            if isinstance(job_id, str) and 8 <= len(job_id) <= 80:
                self.resp(job_id, "receipt", "REJECTED", "SCHEMA_INVALID")
            return
        jid = req["job_order_id"]
        self.seen = {k: v for k, v in self.seen.items() if v >= now}
        if jid in self.seen:
            return
        self.seen[jid] = float(req.get("expires_at") or now) + 60

        def reject(reason):
            with lock:
                counters["rejected"] += 1
            self.resp(jid, "receipt", "REJECTED", reason)
        w = next((x for x in WM if x["work_master_id"] == req["work_master_id"]), None)
        if not w:
            return reject("NOT_ALLOWED")
        if w["equipment_id"] != req["equipment_id"]:
            return reject("EQUIPMENT_MISMATCH")
        value = w["fixed_value"]
        for p in w["parameters"]:
            got = next((x for x in req.get("job_order_parameters", []) if x["id"] == p["id"]), None)
            if not got:
                return reject("PARAMETER_MISSING")
            if not (p["min"] <= got["value"] <= p["max"]):
                return reject("PARAMETER_RANGE")
            value = round(got["value"] * (w.get("scale") or 1))
        if not (float(req.get("expires_at") or 0) > now):
            return reject("EXPIRED")
        plc = self.plc
        if plc.get("run_state") != "RUN" or plc.get("field_comm") is False:
            return reject("PLC_UNAVAILABLE")
        if plc.get("mode") == "LOCAL":
            return reject("LOCAL_MODE")
        if plc.get("maintenance") is True:
            return reject("MAINTENANCE")
        h = int(hashlib.sha256(jid.encode()).hexdigest()[:8], 16) or 1
        job = {"job_order_id": jid, "work_master_id": w["work_master_id"], "equipment_id": w["equipment_id"], "desc": w["desc"],
               "code": w["code"], "value": value, "command_topic": w["command_topic"], "job_hash": h, "received_at": now,
               "expires_at": int(float(req["expires_at"])),
               "context_summary": str((req.get("context") or {}).get("summary", ""))[:120]}
        if plc.get("mode") == "REMOTE_AUTO":
            self.resp(jid, "receipt", "AUTO_ACCEPTED", "REMOTE_AUTO")
            self.pub(w["command_topic"], {"job_order_id": jid, "code": job["code"], "value": value,
                                           "expires_at": job["expires_at"], "operator_accepted": 0, "job_hash": h})
        elif plc.get("mode") == "REMOTE_MANUAL":
            self.pending[jid] = job
            self.resp(jid, "receipt", "OPERATOR_WAIT", "STORED")
            self.pending_msg()
        else:
            reject("MODE_UNKNOWN")

    def decision(self, m):
        if m.retain:
            return
        from datetime import datetime
        d = json.loads(m.payload)
        try:
            age = time.time() - datetime.fromisoformat(str(d["ts"]).replace("Z", "+00:00")).timestamp()
        except Exception:
            return
        if abs(age) > 10:
            return
        job = self.pending.pop(d.get("job_order_id"), None)
        if not job:
            return
        jid = job["job_order_id"]
        if str(d.get("decision")).lower() != "accept":
            self.resp(jid, "operator", "OPERATOR_REJECTED", "OPERATOR")
        elif self.plc.get("mode") != "REMOTE_MANUAL" or self.plc.get("maintenance") is True:
            self.resp(jid, "operator", "REJECTED", "MAINTENANCE" if self.plc.get("maintenance") else f'MODE_{self.plc.get("mode")}')
        else:
            self.resp(jid, "operator", "OPERATOR_ACCEPTED", "OPERATOR")
            self.pub(job["command_topic"], {"job_order_id": jid, "code": job["code"], "value": job["value"],
                                            "expires_at": int(time.time()) + 30, "operator_accepted": 1, "job_hash": job["job_hash"]})
        self.pending_msg()

    def timer(self):
        while True:
            now = time.time()
            for jid, job in list(self.pending.items()):
                if now - job["received_at"] >= 60:
                    self.pending.pop(jid, None)
                    self.resp(jid, "operator", "REJECTED", "OPERATOR_TIMEOUT")
            self.pending_msg()
            time.sleep(1)


class Metrics(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path != "/metrics":
            self.send_response(404)
            self.end_headers()
            return
        with lock:
            body = "".join(f"# TYPE edge_{k}_total counter\nedge_{k}_total {v}\n" for k, v in counters.items())
        body += f"# TYPE edge_plc_online gauge\nedge_plc_online {1 if EDGE.plc_online else 0}\n"
        self.send_response(200)
        self.send_header("Content-Type", "text/plain; version=0.0.4")
        self.end_headers()
        self.wfile.write(body.encode())

    def log_message(self, *a):
        pass


if __name__ == "__main__":
    EDGE = Edge()
    EDGE.start()
    Receiver().start()
    ThreadingHTTPServer(("0.0.0.0", 1880), Metrics).serve_forever()
