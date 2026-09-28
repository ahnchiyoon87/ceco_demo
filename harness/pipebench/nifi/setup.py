"""NiFi 2.12.0 흐름 재현(09-29 결정: UI 제품은 설정을 파일/API 로 재적용할 때만 인정).

    python /repo/harness/pipebench/nifi/setup.py apply    # exported-flow.json 있으면 그 흐름 정의를 업로드, 없으면 아래 FLOW 선언으로 API 생성 → 시작
    python /repo/harness/pipebench/nifi/setup.py export   # 현재 흐름(프로세스 그룹 pipebench)을 exported-flow.json 으로(UI 에서 고친 뒤 정본 갱신)

V1 세 중계를 NiFi 표준 프로세서로(직접 짠 스크립트 프로세서 없음):
  ① ConsumeMQTT(edgex/telemetry, QoS1, 세션 유지) → SplitJson($.readings) → JoltTransformJSON(reading → raw 레코드)
     → EvaluateJsonPath(tag,value) → RouteOnAttribute(계측 12태그·센티널 제외) → PublishKafka(sensor.telemetry.raw, key=${tag})
  ② ConsumeKafka(4토픽) → EvaluateJsonPath(전 필드) → RouteOnAttribute(kafka.topic 별) → ReplaceText(라인 프로토콜) → InvokeHTTP(/api/v2/write)
  ③ ConsumeKafka(sensor.alerts) → EvaluateJsonPath → ReplaceText(Telegraf JSON) → PublishMQTT(scada/alerts/${tag})
                                                    ↘ ReplaceText(HMI 텍스트) → PublishMQTT(scada/hmi/latest-alert)
프로세서·속성 이름은 NiFi 2.x 표준 번들 기준 [미검증: 기동 금지 중 작성]. 첫 실행에서 틀린 속성은 UI 로 고친 뒤 export → 이후 정본.
④ 운영 부담: 흐름 21개 프로세서 + 컨트롤러 서비스 2개, 버전 올릴 때 흐름 정의 호환 확인 필요.
"""
import json
import pathlib
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid

BASE = "https://nifi:8443/nifi-api"
USER, PASS = "bench", "pipebench-nifi-12345"
HERE = pathlib.Path(__file__).parent
CTX = ssl._create_unverified_context()
TAGS = ["LT-101", "LT-102", "TT-101", "TT-102", "PT-101", "FT-101", "FT-102", "IT-101", "IT-102", "VT-101", "pH-101", "CT-101"]
P = "org.apache.nifi.processors."
TOK = None


def req(method, path, body=None, raw=None, ctype="application/json"):
    data = raw if raw is not None else (json.dumps(body).encode() if body is not None else None)
    r = urllib.request.Request(BASE + path, method=method, data=data, headers={"Content-Type": ctype})
    if TOK:
        r.add_header("Authorization", "Bearer " + TOK)
    try:
        with urllib.request.urlopen(r, timeout=60, context=CTX) as resp:
            t = resp.read().decode()
            return resp.status, (json.loads(t) if t.strip().startswith(("{", "[")) else t)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:600]


def must(what, res, ok=(200, 201)):
    code, body = res
    if code not in ok:
        sys.exit(f"NiFi 설정 실패 [{what}]: {code} {body}")
    return body


def login():
    global TOK
    for _ in range(120):
        try:
            code, body = req("POST", "/access/token", raw=urllib.parse.urlencode({"username": USER, "password": PASS}).encode(),
                             ctype="application/x-www-form-urlencoded")
            if code in (200, 201):
                TOK = body.strip()
                return
        except OSError:
            pass
        time.sleep(5)
    sys.exit("NiFi 로그인 실패")


# ── 흐름 선언 ───────────────────────────────────────────────────────────────────
KAFKA_CS = ("kafka", "org.apache.nifi.kafka.service.Kafka3ConnectionService", {"bootstrap.servers": "kafka:9092"})
JOLT_RAW = json.dumps([
    {"operation": "shift", "spec": {"origin": "ts", "deviceName": "device", "resourceName": "tag", "value": "value"}},
    {"operation": "default", "spec": {"site": "AR-100", "quality": "GOOD"}},
    {"operation": "modify-overwrite-beta", "spec": {"value": "=toDouble", "ts": "=toLong"}}])
TAG_IN = ",".join(f"'{t}'" for t in TAGS)
LINE = {  # kafka.topic → 라인 프로토콜(V1 sink.conf 측정·태그·필드)
    "clean": "process,site=${site},device=${device},tag=${tag},quality=${quality} value=${value} ${ts}",
    "raw": "process_raw,site=${site},device=${device},tag=${tag},quality=${quality} value=${value} ${ts}",
    "score": "anomaly,site=${site},device=${device},top_contributors=${top_contributors} reconstruction_error=${reconstruction_error},"
             "threshold=${threshold},inference_ms=${inference_ms},is_anomaly=${is_anomaly} ${ts}",
    "alerts": "alerts,site=${site},device=${device},tag=${tag},alert_type=${alert_type},severity=${severity},detector=${detector} "
              "value=${value},detail=\"${detail:replace('\"','\\\\\"')}\" ${ts}",
}
ALERT_FIELDS = {k: f"$.{k}" for k in ["ts", "site", "device", "tag", "value", "alert_type", "severity", "detector", "detail"]}
FLOW = [  # (이름, 타입, 속성, 자동 종료 관계)
    ("r1-mqtt", P + "mqtt.ConsumeMQTT", {"Broker URI": "tcp://emqx:1883", "Client ID": "nifi-relay1", "Topic Filter": "edgex/telemetry",
                                         "Quality of Service(QoS)": "1", "Session state": "false", "Max Queue Size": "100000"}, []),
    ("r1-split", P + "standard.SplitJson", {"JsonPath Expression": "$.readings"}, ["failure", "original"]),
    ("r1-jolt", P + "jolt.JoltTransformJSON", {"Jolt Transform": "jolt-transform-chain", "Jolt Specification": JOLT_RAW}, ["failure"]),
    ("r1-attrs", P + "standard.EvaluateJsonPath", {"Destination": "flowfile-attribute", "tag": "$.tag", "value": "$.value"}, ["failure", "unmatched"]),
    ("r1-filter", P + "standard.RouteOnAttribute", {"Routing Strategy": "Route to Property name",
                                                   "keep": f"${{tag:in({TAG_IN}):and(${{value:toDecimal():gt(-999998)}})}}"}, ["unmatched"]),
    ("r1-kafka", P + "kafka.processors.PublishKafka", {"Kafka Connection Service": "@kafka", "Topic Name": "sensor.telemetry.raw",
                                                       "FlowFile Attribute Key": "${tag}", "Delivery Guarantee": "DELIVERY_REPLICATED",
                                                       "Compression Type": "lz4"}, ["success", "failure"]),
    ("r2-kafka", P + "kafka.processors.ConsumeKafka", {"Kafka Connection Service": "@kafka", "Group ID": "nifi-influx",
                                                       "Topics": "sensor.telemetry.clean,sensor.telemetry.raw,sensor.anomaly.score,sensor.alerts",
                                                       "auto.offset.reset": "latest", "Processing Strategy": "FLOW_FILE"}, []),
    ("r2-attrs", P + "standard.EvaluateJsonPath", {"Destination": "flowfile-attribute", "Null Value Representation": "empty string",
                                                   **{k: f"$.{k}" for k in ["ts", "site", "device", "tag", "quality", "value", "top_contributors",
                                                                             "reconstruction_error", "threshold", "inference_ms", "is_anomaly",
                                                                             "alert_type", "severity", "detector", "detail"]}}, ["failure", "unmatched"]),
    ("r2-route", P + "standard.RouteOnAttribute", {"Routing Strategy": "Route to Property name",
                                                   "clean": "${kafka.topic:equals('sensor.telemetry.clean')}",
                                                   "raw": "${kafka.topic:equals('sensor.telemetry.raw')}",
                                                   "score": "${kafka.topic:equals('sensor.anomaly.score')}",
                                                   "alerts": "${kafka.topic:equals('sensor.alerts')}"}, ["unmatched"]),
    *[(f"r2-line-{k}", P + "standard.ReplaceText", {"Replacement Strategy": "Always Replace", "Replacement Value": v}, ["failure"])
      for k, v in LINE.items()],
    ("r2-merge", P + "standard.MergeContent", {"Merge Strategy": "Bin-Packing Algorithm", "Minimum Number of Entries": "5000",
                                               "Maximum Number of Entries": "5000", "Max Bin Age": "2 sec", "Delimiter Strategy": "Text",
                                               "Demarcator File": "\n"}, ["failure", "original"]),
    ("r2-influx", P + "standard.InvokeHTTP", {"HTTP Method": "POST", "HTTP URL": "http://influxdb:8086/api/v2/write?org=bench&bucket=process&precision=ns",
                                              "Authorization": "Token pipebench-token", "Request Content-Type": "text/plain"},
     ["Original", "Response", "Retry", "No Retry", "Failure"]),
    ("r3-kafka", P + "kafka.processors.ConsumeKafka", {"Kafka Connection Service": "@kafka", "Group ID": "nifi-alert-republish",
                                                       "Topics": "sensor.alerts", "auto.offset.reset": "latest", "Processing Strategy": "FLOW_FILE"}, []),
    ("r3-attrs", P + "standard.EvaluateJsonPath", {"Destination": "flowfile-attribute", **ALERT_FIELDS}, ["failure", "unmatched"]),
    ("r3-json", P + "standard.ReplaceText", {"Replacement Strategy": "Always Replace", "Replacement Value":
        '{"fields":{"detail":${detail:jsonEscape():prepend(\'"\'):append(\'"\')},"value":${value:toDecimal()}},"name":"alert",'
        '"tags":{"alert_type":"${alert_type}","detector":"${detector}","device":"${device}","severity":"${severity}","site":"${site}",'
        '"tag":"${tag}"},"timestamp":${ts}}'}, ["failure"]),
    ("r3-hmi", P + "standard.ReplaceText", {"Replacement Strategy": "Always Replace", "Replacement Value":
        "${ts:divide(1000000):format('MM-dd HH:mm:ss','UTC')} UTC | ${severity} | ${tag} | ${alert_type}"}, ["failure"]),
    ("r3-mqtt", P + "mqtt.PublishMQTT", {"Broker URI": "tcp://emqx:1883", "Client ID": "nifi-alert-republisher",
                                         "Topic": "scada/alerts/${tag}", "Quality of Service(QoS)": "1", "Retain Message": "false"}, ["success", "failure"]),
    ("r3-mqtt-hmi", P + "mqtt.PublishMQTT", {"Broker URI": "tcp://emqx:1883", "Client ID": "nifi-alert-republisher-hmi",
                                             "Topic": "scada/hmi/latest-alert", "Quality of Service(QoS)": "1", "Retain Message": "false"}, ["success", "failure"]),
]
LINKS = [("r1-mqtt", "r1-split", ["Message"]), ("r1-split", "r1-jolt", ["split"]), ("r1-jolt", "r1-attrs", ["success"]),
         ("r1-attrs", "r1-filter", ["matched"]), ("r1-filter", "r1-kafka", ["keep"]),
         ("r2-kafka", "r2-attrs", ["success"]), ("r2-attrs", "r2-route", ["matched"]),
         *[("r2-route", f"r2-line-{k}", [k]) for k in LINE], *[(f"r2-line-{k}", "r2-merge", ["success"]) for k in LINE],
         ("r2-merge", "r2-influx", ["merged"]),
         ("r3-kafka", "r3-attrs", ["success"]), ("r3-attrs", "r3-json", ["matched"]), ("r3-attrs", "r3-hmi", ["matched"]),
         ("r3-json", "r3-mqtt", ["success"]), ("r3-hmi", "r3-mqtt-hmi", ["success"])]


def rev():
    return {"clientId": "pipebench-setup", "version": 0}


def build(root):
    pg = must("group", req("POST", f"/process-groups/{root}/process-groups",
                           {"revision": rev(), "component": {"name": "pipebench", "position": {"x": 0, "y": 0}}}))["id"]
    cs = must("kafka service", req("POST", f"/process-groups/{pg}/controller-services",
                                   {"revision": rev(), "component": {"name": KAFKA_CS[0], "type": KAFKA_CS[1], "properties": KAFKA_CS[2]}}))
    must("enable kafka service", req("PUT", f"/controller-services/{cs['id']}/run-status",
                                     {"revision": cs["revision"], "state": "ENABLED"}))
    ids = {}
    for i, (name, typ, props, auto) in enumerate(FLOW):
        props = {k: (cs["id"] if v == "@kafka" else v) for k, v in props.items()}
        body = must(f"processor {name}", req("POST", f"/process-groups/{pg}/processors", {"revision": rev(), "component": {
            "name": name, "type": typ, "position": {"x": 400 * (i % 6), "y": 250 * (i // 6)},
            "config": {"properties": props, "autoTerminatedRelationships": auto, "schedulingPeriod": "0 sec"}}}))
        ids[name] = body["id"]
    for src, dst, rels in LINKS:
        must(f"link {src}->{dst}", req("POST", f"/process-groups/{pg}/connections", {"revision": rev(), "component": {
            "source": {"id": ids[src], "groupId": pg, "type": "PROCESSOR"},
            "destination": {"id": ids[dst], "groupId": pg, "type": "PROCESSOR"}, "selectedRelationships": rels}}))
    return pg


def upload(root, path):
    boundary = uuid.uuid4().hex
    parts = []
    for k, v in {"groupName": "pipebench", "positionX": "0", "positionY": "0", "clientId": "pipebench-setup"}.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{k}"\r\n\r\n{v}\r\n'.encode())
    parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="flow.json"\r\n'
                 f'Content-Type: application/json\r\n\r\n'.encode() + path.read_bytes() + b"\r\n")
    parts.append(f"--{boundary}--\r\n".encode())
    return must("upload flow", req("POST", f"/process-groups/{root}/process-groups/upload", raw=b"".join(parts),
                                   ctype=f"multipart/form-data; boundary={boundary}"))["id"]


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "apply"
    login()
    root = must("root", req("GET", "/flow/process-groups/root"))["processGroupFlow"]["id"]
    if mode == "export":
        groups = must("groups", req("GET", f"/process-groups/{root}/process-groups"))["processGroups"]
        pg = next(g["id"] for g in groups if g["component"]["name"] == "pipebench")
        _, flow = req("GET", f"/process-groups/{pg}/download")
        pathlib.Path("/experiments/EXP-PIPE/raw/nifi_exported-flow.json").write_text(json.dumps(flow, ensure_ascii=False, indent=1), encoding="utf-8")
        print("내보냄: experiments/EXP-PIPE/raw/nifi_exported-flow.json → harness/pipebench/nifi/exported-flow.json 로 복사하면 apply 정본")
        return
    ex = HERE / "exported-flow.json"
    pg = upload(root, ex) if ex.exists() else build(root)
    # 업로드한 흐름의 컨트롤러 서비스는 비활성 상태로 들어온다 → 모두 활성화 후 시작
    services = req("GET", f"/flow/process-groups/{pg}/controller-services")[1]
    for s in (services.get("controllerServices", []) if isinstance(services, dict) else []):
        req("PUT", f"/controller-services/{s['id']}/run-status", {"revision": s["revision"], "state": "ENABLED"})
    time.sleep(5)
    must("start", req("PUT", f"/flow/process-groups/{pg}", {"id": pg, "state": "RUNNING"}))
    print("NiFi 흐름 시작:", pg, "(원천:", "exported-flow.json" if ex.exists() else "FLOW 선언", ")")


if __name__ == "__main__":
    main()
