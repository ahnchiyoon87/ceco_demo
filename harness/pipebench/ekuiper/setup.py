"""eKuiper 2.4.2 규칙 생성(REST :9081) — 중계 후보 P1(CANDIDATES §4 "알람 워커·규칙", 패턴 P-EDGE).
stage2.sh 가 ekuiper 컨테이너 기동 후 client 컨테이너에서 한 번 실행한다. 모두 제품 SQL 규칙·싱크 설정(직접 짠 중계 코드 없음).

  중계 ① r1a: MQTT edgex/telemetry → SELECT unnest(readings) → memory 토픽(펼치기)
         r1b: memory → 계측 12태그·센티널 제외 → {ts,site,device,tag,value,quality} → Kafka sensor.telemetry.raw (key {{.tag}})
  중계 ② r2_<m>: Kafka 토픽 4개 → influx2 싱크(측정·태그·필드는 V1 sink.conf 와 같게, tsFieldName=ts, precision ns)
  중계 ③ r3: Kafka sensor.alerts → MQTT scada/alerts/{{.tag}} (V1 Telegraf JSON 모양, dataTemplate) + scada/hmi/latest-alert(텍스트)
알려진 위험(② 기동·기능에서 확인): JSON 숫자를 float64 로 읽으면 ts(ns, 1.8e18) 끝자리가 뭉개진다 → 스키마를 BIGINT 로 선언했지만
보존 여부 [미검증]. 싱크 속성 이름(kafka key, influx2 tags/fields/tsFieldName)은 2.x 문서 기준 [미검증].

    python /repo/harness/pipebench/ekuiper/setup.py [--base http://ekuiper:9081]
"""
import argparse
import json
import sys
import time
import urllib.error
import urllib.request

TAGS = ["LT-101", "LT-102", "TT-101", "TT-102", "PT-101", "FT-101", "FT-102",
        "IT-101", "IT-102", "VT-101", "pH-101", "CT-101"]
INFLUX = {"addr": "http://influxdb:8086", "token": "pipebench-token", "org": "bench", "bucket": "process",
          "tsFieldName": "ts", "precision": "ns", "sendSingle": True}


def call(base, method, path, body=None):
    req = urllib.request.Request(base + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def must(base, method, path, body, what):
    code, txt = call(base, method, path, body)
    ok = code in (200, 201)
    print(f"{'OK ' if ok else 'ERR'} {what}: {code} {txt[:200]}", flush=True)
    if not ok:
        sys.exit(f"eKuiper 설정 실패: {what}")


def stream(base, name, cols, src, typ, extra=""):
    sql = f'CREATE STREAM {name} ({cols}) WITH (DATASOURCE="{src}", FORMAT="JSON", TYPE="{typ}"{extra})'
    must(base, "POST", "/streams", {"sql": sql}, f"stream {name}")


def rule(base, rid, sql, actions):
    must(base, "POST", "/rules", {"id": rid, "sql": sql, "actions": actions,
                                  "options": {"qos": 1, "checkpointInterval": "1s", "sendError": False}}, f"rule {rid}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://ekuiper:9081")
    a = ap.parse_args()
    b = a.base
    for _ in range(60):
        try:
            if call(b, "GET", "/")[0] == 200:
                break
        except OSError:
            pass
        time.sleep(2)
    # Kafka 소스 연결 설정(그룹은 규칙마다 다르게: V1 처럼 중계별 소비 그룹)
    for key, group in (("sink", "ekuiper-influx"), ("republish", "ekuiper-alert-republish")):
        must(b, "PUT", f"/metadata/sources/kafka/confKeys/{key}", {"brokers": "kafka:9092", "groupID": group}, f"kafka conf {key}")

    # 중계 ①
    stream(b, "edgex", "", "edgex/telemetry", "mqtt")
    rule(b, "r1a", "SELECT unnest(readings) FROM edgex", [{"memory": {"topic": "relay1/readings", "sendSingle": True}}])
    stream(b, "rd", "origin BIGINT, deviceName STRING, resourceName STRING, `value` STRING", "relay1/readings", "memory")
    tags = ",".join(f'"{t}"' for t in TAGS)
    rule(b, "r1b",
         'SELECT origin AS ts, "AR-100" AS site, deviceName AS device, resourceName AS tag, cast(`value`, "float") AS `value`, '
         f'"GOOD" AS quality FROM rd WHERE resourceName IN ({tags}) AND cast(`value`, "float") > -999998',
         [{"kafka": {"brokers": "kafka:9092", "topic": "sensor.telemetry.raw", "key": "{{.tag}}", "sendSingle": True}}])

    # 중계 ②
    specs = {
        "process": ("sensor.telemetry.clean", "ts BIGINT, site STRING, device STRING, tag STRING, quality STRING, `value` FLOAT",
                    ["site", "device", "tag", "quality"], ["value"]),
        "process_raw": ("sensor.telemetry.raw", "ts BIGINT, site STRING, device STRING, tag STRING, quality STRING, `value` FLOAT",
                        ["site", "device", "tag", "quality"], ["value"]),
        "anomaly": ("sensor.anomaly.score", "ts BIGINT, site STRING, device STRING, top_contributors STRING, reconstruction_error FLOAT, "
                    "threshold FLOAT, inference_ms FLOAT, is_anomaly BOOLEAN",
                    ["site", "device", "top_contributors"], ["reconstruction_error", "threshold", "inference_ms", "is_anomaly"]),
        "alerts": ("sensor.alerts", "ts BIGINT, site STRING, device STRING, tag STRING, `value` FLOAT, alert_type STRING, "
                   "severity STRING, detector STRING, detail STRING",
                   ["site", "device", "tag", "alert_type", "severity", "detector"], ["value", "detail"]),
    }
    for m, (topic, cols, tg, fl) in specs.items():
        stream(b, f"k_{m}", cols, topic, "kafka", ', CONF_KEY="sink"')
        rule(b, f"r2_{m}", f"SELECT * FROM k_{m}",
             [{"influx2": dict(INFLUX, measurement=m, tags={t: "{{." + t + "}}" for t in tg}, fields=fl)}])

    # 중계 ③
    stream(b, "k_alerts_rp", specs["alerts"][1], "sensor.alerts", "kafka", ', CONF_KEY="republish"')
    tmpl = ('{"fields":{"detail":{{json .detail}},"value":{{.value}}},"name":"alert","tags":{"alert_type":{{json .alert_type}},'
            '"detector":{{json .detector}},"device":{{json .device}},"severity":{{json .severity}},"site":{{json .site}},'
            '"tag":{{json .tag}}},"timestamp":{{printf "%.0f" .ts}}}')
    rule(b, "r3", 'SELECT *, format_time(ts / 1000000, "MM-dd HH:mm:ss") AS hmi_time FROM k_alerts_rp', [
        {"mqtt": {"server": "tcp://emqx:1883", "topic": "scada/alerts/{{.tag}}", "qos": 1, "clientId": "ekuiper-alert-republisher",
                  "sendSingle": True, "dataTemplate": tmpl}},
        {"mqtt": {"server": "tcp://emqx:1883", "topic": "scada/hmi/latest-alert", "qos": 1, "clientId": "ekuiper-alert-republisher-hmi",
                  "sendSingle": True, "dataTemplate": "{{.hmi_time}} UTC | {{.severity}} | {{.tag}} | {{.alert_type}}"}},
    ])
    time.sleep(3)
    code, txt = call(b, "GET", "/rules")
    print("rules:", txt[:600], flush=True)


if __name__ == "__main__":
    main()
