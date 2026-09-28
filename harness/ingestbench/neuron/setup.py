"""Neuron 2.13.0 설정(REST). 수집 후보 P2 — stage2.sh 가 neuron 컨테이너 기동 후 client 컨테이너에서 한 번 실행한다.

V1 이 하던 일: EdgeX device-modbus(12태그 float32, 1초) + app-mqtt-export(edgex/telemetry, QoS1, Store-and-Forward)
재현 방법(모두 제품 설정 API, 직접 짠 수집 로직 없음):
  - 남쪽: "Modbus TCP" 드라이버 노드, 그룹 g1(1000 ms), 태그 12개 FLOAT(type 9), 주소 1!4000NN(address_base 1 → HR n = 400001+n), 바이트 순서 ABCD(endianess 1)
  - 북쪽: "MQTT" 앱 노드, QoS1, format 0(values 형식), 업로드 토픽 edgex/telemetry, offline-cache 켬(단절 보관, OSS 기능)
알려진 차이: 페이로드는 Neuron 고정 모양 {"node","group","timestamp"(ms),"values":{tag:v},"errors":{}} —
            EdgeX Event 모양이 아니다 → V1 Telegraf#1 json_v2 설정 변경 필요(검사기는 neuron 파서로 측정).
API 형식 출처: emqx/neuron v2.13-daily tests/ft/neuron/api.py, plugins/mqtt/mqtt.json, plugins/modbus/modbus-tcp.json

    python /repo/harness/ingestbench/neuron/setup.py [--base http://neuron:7000]
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request

TAGS = [("LT-101", 0), ("LT-102", 2), ("TT-101", 4), ("TT-102", 6), ("PT-101", 8), ("FT-101", 10),
        ("FT-102", 12), ("IT-101", 14), ("IT-102", 16), ("VT-101", 18), ("pH-101", 20), ("CT-101", 22)]


def call(base, method, path, body=None, token=None):
    req = urllib.request.Request(base + path, method=method,
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    if token:
        req.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            txt = r.read().decode()
            return r.status, (json.loads(txt) if txt else {})
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def must(step, res):
    code, body = res
    ok = code == 200 and (not isinstance(body, dict) or body.get("error", 0) in (0, None))
    print(f"{'OK ' if ok else 'ERR'} {step}: {code} {str(body)[:200]}", flush=True)
    if not ok:
        sys.exit(f"Neuron 설정 실패: {step}")
    return body


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://neuron:7000")
    ap.add_argument("--topic", default="edgex/telemetry")
    a = ap.parse_args()
    b = a.base
    for _ in range(60):                       # 기동 대기
        try:
            code, _ = call(b, "POST", "/api/v2/login", {"name": "admin", "pass": "0000"})
            if code == 200:
                break
        except OSError:
            pass
        time.sleep(2)
    tok = must("login", call(b, "POST", "/api/v2/login", {"name": "admin", "pass": "0000"}))["token"]

    must("add driver", call(b, "POST", "/api/v2/node", {"name": "modbus", "plugin": "Modbus TCP"}, tok))
    must("driver setting", call(b, "POST", "/api/v2/node/setting", {"node": "modbus", "params": {
        "connection_mode": 0, "transport_mode": 0, "interval": 20, "host": "plant-simulator", "port": 502,
        "timeout": 1000, "max_retries": 0, "retry_interval": 1, "endianess": 1, "endianess_64": 1,
        "address_base": 1, "device_degrade": 0, "degrade_cycle": 1, "degrade_time": 600}}, tok))
    must("add group", call(b, "POST", "/api/v2/group", {"node": "modbus", "group": "g1", "interval": 1000}, tok))
    must("add tags", call(b, "POST", "/api/v2/tags", {"node": "modbus", "group": "g1", "tags": [
        {"name": t, "address": f"1!{400001 + hr}", "attribute": 1, "type": 9} for t, hr in TAGS]}, tok))

    must("add app", call(b, "POST", "/api/v2/node", {"name": "mqtt", "plugin": "MQTT"}, tok))
    must("app setting", call(b, "POST", "/api/v2/node/setting", {"node": "mqtt", "params": {
        "client-id": "neuron-ingest", "qos": 1, "format": 0,
        "write-req-topic": "neuron/ingest/write/req", "write-resp-topic": "neuron/ingest/write/resp",
        "driver-topic-prefix": "neuron/ingest", "upload_drv_state": False,
        "upload_drv_state_topic": "neuron/ingest/state/update", "upload_drv_state_interval": 1,
        "offline-cache": True, "cache-mem-size": 128, "cache-disk-size": 1024, "cache-sync-interval": 100,
        "host": "mosquitto", "port": 1883, "username": "", "password": "", "ssl": False}}, tok))
    must("subscribe", call(b, "POST", "/api/v2/subscribe", {"app": "mqtt", "driver": "modbus", "group": "g1",
                                                             "params": {"topic": a.topic}}, tok))
    for n in ("modbus", "mqtt"):
        must(f"start {n}", call(b, "POST", "/api/v2/node/ctl", {"node": n, "cmd": 0}, tok))
    time.sleep(3)
    for n in ("modbus", "mqtt"):
        print("state", n, call(b, "GET", f"/api/v2/node/state?node={n}", token=tok), flush=True)


if __name__ == "__main__":
    main()
