"""[측정 도구] E12 기본 보안: 인증 없이 각 접점에 접근되는지(읽기·쓰기 시도는 무해한 것만). rot-iiot 망에서 실행."""
import argparse, json, socket, urllib.request, uuid

def absent(host):
    """이름이 풀리지 않으면 그 구조에 없는 부품(열림·닫힘이 아니라 '없음', #109)."""
    try:
        socket.getaddrinfo(host, None); return False
    except socket.gaierror:
        return True
import paho.mqtt.client as mqtt

def http(url, method="GET"):
    host = url.split("//")[1].split(":")[0].split("/")[0]
    if absent(host):
        return {"absent": True, "open": False}
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, method=method), timeout=5)
        return {"status": r.status, "open": True}
    except urllib.error.HTTPError as e:
        return {"status": e.code, "open": e.code not in (401, 403)}
    except Exception as e:
        return {"status": None, "open": False, "error": type(e).__name__}

def mqtt_anon(host):
    if absent(host):
        return {"absent": True, "open": False}
    res = {}
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"probe-{uuid.uuid4().hex[:6]}")
    c.on_connect = lambda c, u, f, rc, p=None: res.setdefault("connack", str(rc))
    try:
        c.connect(host, 1883, 5); c.loop_start()
        import time; time.sleep(2)
        info = c.publish("probe/anon", "x", qos=1); info.wait_for_publish(3)
        res["publish_ok"] = info.is_published(); c.loop_stop(); c.disconnect()
    except Exception as e:
        res["error"] = type(e).__name__
    res["open"] = res.get("connack") == "Success"
    return res

def kafka_anon():
    try:
        from confluent_kafka.admin import AdminClient
        md = AdminClient({"bootstrap.servers": "kafka:9092"}).list_topics(timeout=5)
        return {"open": True, "topics": len(md.topics)}
    except Exception as e:
        return {"open": False, "error": type(e).__name__}

ap = argparse.ArgumentParser(); ap.add_argument("--out", required=True)
ap.add_argument("--broker", default="emqx", help="SCADA MQTT 브로커 호스트(V1 emqx, V2 mqtt)"); a = ap.parse_args()
out = {
  "mqtt_emqx_anonymous": mqtt_anon(a.broker),   # 키 이름은 V1 결과와 비교하려고 유지 — 값은 그 구조의 SCADA 브로커
  "mqtt_edgex_internal_anonymous": mqtt_anon("edgex-mqtt-broker"),
  "kafka_plaintext_no_auth": kafka_anon(),
  "influxdb_query_no_token": http("http://influxdb:8086/api/v2/buckets"),
  "fuxa_project_no_login": http("http://fuxa:1881/api/project"),
  "grafana_no_login": http("http://grafana:3000/api/search"),
  "flink_rest_no_auth": http("http://flink-jobmanager:8081/jobs/overview"),
  "edgex_command_no_auth": http("http://edgex-core-command:59882/api/v3/device/all"),
  "prometheus_no_auth": http("http://prometheus:9090/api/v1/targets"),
  "alertmanager_no_auth": http("http://alertmanager:9093/api/v2/status"),
  "simulator_api_no_auth": http("http://plant-simulator:8080/state"),
}
out["open_count"] = sum(1 for v in out.values() if isinstance(v, dict) and v.get("open"))
out["absent"] = sorted(k for k, v in out.items() if isinstance(v, dict) and v.get("absent"))
out["probed"] = len([k for k, v in out.items() if isinstance(v, dict)]) - len(out["absent"])
json.dump(out, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps({k: v.get("open") if isinstance(v, dict) else v for k, v in out.items()}, ensure_ascii=False))
