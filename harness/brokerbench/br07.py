"""BR-07 운영 지표 노출 확인(harness/situations/BROKER.md). 합격: 연결 수·수신·발신 지표를 스크레이프(HTTP) 또는 $SYS 로 조회 가능.

브로커마다 (1) 알려진 HTTP 지표 엔드포인트 GET, (2) $SYS/# 10초 구독을 해 보고 찾은 지표 이름을 기록한다.
  python /repo/harness/brokerbench/br07.py --exp EXP-130 --run e
"""
import argparse
import base64
import json
import pathlib
import time
import urllib.request

import paho.mqtt.client as mqtt

HTTP = {
    "emqx": [("http://emqx:18083/api/v5/prometheus/stats", None)],
    "mosquitto": [],
    "nanomq": [("http://nanomq:8081/api/v4/prometheus", ("admin", "public")),
               ("http://nanomq:8081/api/v4/metrics", ("admin", "public"))],
    "hivemq": [("http://hivemq:9399/metrics", None)],
}
KEYS = {"connections": ["connections", "clients/connected", "clients.connected", "connected"],
        "received": ["messages.received", "messages/received", "received", "incoming"],
        "sent": ["messages.sent", "messages/sent", "sent", "outgoing"]}


def http_probe(url, auth):
    req = urllib.request.Request(url)
    if auth:
        req.add_header("Authorization", "Basic " + base64.b64encode(f"{auth[0]}:{auth[1]}".encode()).decode())
    try:
        body = urllib.request.urlopen(req, timeout=5).read().decode(errors="replace")
        return {"url": url, "status": 200, "bytes": len(body), "sample": [l for l in body.splitlines() if l and not l.startswith("#")][:5],
                "text": body}
    except Exception as e:  # noqa: BLE001 — 실패도 결과로 기록
        return {"url": url, "error": f"{type(e).__name__}: {e}"[:200]}


def sys_probe(broker, secs=10):
    topics = {}
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"br07-{broker}-{int(time.time())}")
    c.on_connect = lambda cl, u, f, rc, p=None: cl.subscribe("$SYS/#", qos=0)
    c.on_message = lambda cl, u, m: topics.__setitem__(m.topic, m.payload[:80].decode(errors="replace"))
    c.connect(broker, 1883)
    c.loop_start()
    time.sleep(secs)
    c.loop_stop()
    c.disconnect()
    return topics


def found(text):
    t = text.lower()
    return {k: any(x in t for x in v) for k, v in KEYS.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--exp", required=True)
    ap.add_argument("--run", required=True)
    ap.add_argument("--brokers", default="emqx,mosquitto,nanomq,hivemq")
    a = ap.parse_args()
    out = pathlib.Path(f"/experiments/{a.exp}/raw/br07_{a.run}.json")
    if out.exists():
        raise SystemExit(f"실행 ID 재사용 금지: {out}")
    res = {}
    for b in a.brokers.split(","):
        https = [http_probe(u, au) for u, au in HTTP.get(b, [])]
        sys_t = sys_probe(b)
        http_ok = [h for h in https if h.get("status") == 200]
        http_found = found("\n".join(h["text"] for h in http_ok)) if http_ok else {}
        sys_found = found("\n".join(sys_t))
        via = {k: (http_found.get(k) or sys_found.get(k)) for k in KEYS}
        for h in https:
            h.pop("text", None)
        res[b] = {"http": https, "sys_topics": len(sys_t), "sys_sample": sorted(sys_t)[:12],
                  "http_found": http_found, "sys_found": sys_found,
                  "verdict": "PASS" if all(via.values()) else "FAIL", "covered": via}
        print(b, json.dumps({k: res[b][k] for k in ("verdict", "covered", "sys_topics", "http_found")}, ensure_ascii=False), flush=True)
    out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
