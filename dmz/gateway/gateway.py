"""DMZ 요청 게이트웨이(1차 검사, HANDOFF §2-1 ⑥) — 자체 코드.

Bento 게이트웨이는 MQTT 3.1.1 로만 발행해 메시지 만료를 붙일 수 없고, 브로커가 멈추면 즉시 거부하지 못해(⑨-6 실측)
같은 역할을 작은 서비스로 만든다. 공장 상태(모드)는 보지 않는다. 검사:
  스키마 · 허용 작업 ID·설비·파라미터 범위 · 요청자·승인자 허용 목록 · 요청 나이(created_at 부터 10 s) · 중복(만료 시간 안의 ID)
통과하면 expires_at(발행 + 30 s)을 붙이고 같은 남은 시간을 MQTT 5 메시지 만료로 붙여 DMZ 요청 토픽에 QoS 1 로 발행한다.
DMZ 브로커로 발행하지 못하면 재시도하지 않고 바로 거부(BROKER_UNAVAILABLE)로 답한다(동기 HTTP 응답 = 첫 겹 ⓐ).
"""
from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import threading
import time

import jsonschema
import paho.mqtt.client as mqtt
from aiohttp import web
from paho.mqtt.packettypes import PacketTypes
from paho.mqtt.properties import Properties

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s gateway | %(message)s")
log = logging.getLogger("gateway")
SCHEMA = json.load(open("/opt/ar100/registry/schemas/job_request.schema.json", encoding="utf-8"))
ALLOW = json.load(open("/opt/ar100/registry/work_masters.allow.json", encoding="utf-8"))
REG = json.load(open("/opt/ar100/registry/tags.json", encoding="utf-8"))
TOPIC = REG["request"]["in_topic"]
TOKEN = os.environ["GATEWAY_CLIENT_TOKEN"]
EXPIRY_S = 30          # 발행부터 만료(17번 E18)
MAX_AGE_S = 10         # 요청 나이 상한(한 PC 안 경로는 1 s 미만, 설계 기본값)
PUBACK_TIMEOUT_S = 2
counters: dict[str, int] = {}
seen: dict[str, float] = {}
lock = threading.Lock()


def count(key: str) -> None:
    with lock:
        counters[key] = counters.get(key, 0) + 1


class Broker:
    """DMZ 브로커 연결. 발행이 확인되지 않으면 클라이언트를 버리고 새로 만든다(내부 대기열의 재전송을 막는다)."""

    def __init__(self):
        self.c = None
        self.new()

    def new(self):
        if self.c is not None:
            try:
                self.c.loop_stop()
                self.c.disconnect()
            except Exception:
                pass
        c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"dmz-gateway-{int(time.time())}", protocol=mqtt.MQTTv5)
        c.username_pw_set("gateway", os.environ["MQTT_GATEWAY_PASSWORD"])
        c.on_connect = lambda cl, u, f, rc, p=None: log.info("DMZ 브로커 연결: %s", rc)
        c.on_disconnect = lambda cl, u, f, rc, p=None: log.warning("DMZ 브로커 끊김: %s", rc)
        c.reconnect_delay_set(1, 5)
        c.max_queued_messages_set(1)
        c.connect_async("dmz-broker", 1883, keepalive=15, clean_start=True)
        c.loop_start()
        self.c = c

    def publish(self, payload: str, expiry: int) -> bool:
        if not self.c.is_connected():
            return False
        props = Properties(PacketTypes.PUBLISH)
        props.MessageExpiryInterval = expiry
        info = self.c.publish(TOPIC, payload, qos=1, properties=props)
        try:
            info.wait_for_publish(timeout=PUBACK_TIMEOUT_S)
        except (RuntimeError, ValueError):
            pass
        if info.is_published():
            return True
        self.new()
        return False


def check(req: dict, now: float) -> str | None:
    try:
        jsonschema.validate(req, SCHEMA)
    except jsonschema.ValidationError:
        return "SCHEMA_INVALID"
    wm = next((w for w in ALLOW["work_masters"] if w["work_master_id"] == req["work_master_id"]), None)
    if wm is None:
        return "NOT_ALLOWED"
    if wm["equipment_id"] != req["equipment_id"]:
        return "EQUIPMENT_MISMATCH"
    for p in wm["parameters"]:
        got = next((x for x in req["job_order_parameters"] if x["id"] == p["id"]), None)
        if got is None:
            return "PARAMETER_MISSING"
        if not (p["min"] <= got["value"] <= p["max"]):
            return "PARAMETER_RANGE"
    if req["requester"] not in ALLOW["requesters"]:
        return "REQUESTER_NOT_ALLOWED"
    if req["approver"] not in ALLOW["approvers"]:
        return "APPROVER_NOT_ALLOWED"
    age = now - float(req["created_at"])
    if age > MAX_AGE_S or age < -2:
        return "TOO_OLD"
    return None


async def handle(request: web.Request) -> web.Response:
    if not hmac.compare_digest(request.headers.get("Authorization", ""), f"Bearer {TOKEN}"):
        count("rejected_UNAUTHORIZED")
        return web.json_response({"status": "REJECTED", "reason": "UNAUTHORIZED"}, status=401)
    now = time.time()
    try:
        req = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError):
        count("rejected_SCHEMA_INVALID")
        return web.json_response({"status": "REJECTED", "reason": "SCHEMA_INVALID"}, status=400)
    reason = check(req, now) if isinstance(req, dict) else "SCHEMA_INVALID"
    jid = req.get("job_order_id") if isinstance(req, dict) else None
    if reason is None:
        with lock:
            for k in [k for k, v in seen.items() if v < now]:
                del seen[k]
            if jid in seen:
                reason = "DUPLICATE"
            else:
                seen[jid] = now + EXPIRY_S + 5
    if reason:
        count(f"rejected_{reason}")
        log.info("거부 %s %s", jid, reason)
        return web.json_response({"status": "REJECTED", "reason": reason, "job_order_id": jid}, status=409 if reason == "DUPLICATE" else 422)
    req["expires_at"] = int(now) + EXPIRY_S
    ok = await asyncio.get_running_loop().run_in_executor(None, BROKER.publish, json.dumps(req, ensure_ascii=False), EXPIRY_S)
    if not ok:
        with lock:
            seen.pop(jid, None)
        count("rejected_BROKER_UNAVAILABLE")
        log.warning("거부 %s BROKER_UNAVAILABLE", jid)
        return web.json_response({"status": "REJECTED", "reason": "BROKER_UNAVAILABLE", "job_order_id": jid}, status=503)
    count("accepted")
    log.info("수용 %s %s → %s (만료 %s)", jid, req["work_master_id"], TOPIC, req["expires_at"])
    return web.json_response({"status": "ACCEPTED", "job_order_id": jid, "expires_at": req["expires_at"]}, status=202)


async def health(_):
    return web.json_response({"status": "ok", "broker": BROKER.c.is_connected()})


async def metrics(_):
    with lock:
        lines = ["# TYPE gateway_requests_total counter"]
        lines += [f'gateway_requests_total{{result="{k}"}} {v}' for k, v in sorted(counters.items())]
    lines += ["# TYPE gateway_broker_connected gauge", f"gateway_broker_connected {1 if BROKER.c.is_connected() else 0}", ""]
    return web.Response(text="\n".join(lines), content_type="text/plain")


if __name__ == "__main__":
    BROKER = Broker()
    app = web.Application()
    app.router.add_post("/requests", handle)
    app.router.add_get("/health", health)
    app.router.add_get("/metrics", metrics)
    web.run_app(app, host="0.0.0.0", port=8088, access_log=None, print=None)
