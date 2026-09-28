"""알람 워커 후보: LF Edge eKuiper 2.4.2 — Kafka 소스(바이너리 형식) → SQL 싱크(alarm_intake). REST :9081 로 생성.

엔진 몫: sensor.alerts 소비 → alarm_intake(topic, partition_id, offset_id, raw_payload) 1행. 업무 판단은 DB 트리거.
알려진 위험(② 에서 확인): meta(partition)·meta(offset) 제공 여부 [미확인] — 없으면 NULL → 트리거가 partition -1 / offset=행 id 로 받음
(재전달 멱등성은 사건 쪽만). SQL 싱크가 이 이미지에 포함됐는지 [미확인]. 커밋 시점(싱크 성공 뒤인가) [미확인] → R 재전달 시험으로 드러남.
    python /repo/harness/alarmworkerbench/ekuiper/setup.py
"""
import json
import sys
import time
import urllib.error
import urllib.request

B = "http://ekuiper:9081"


def call(method, path, body=None):
    r = urllib.request.Request(B + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, resp.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()


def must(what, res):
    print(("OK " if res[0] in (200, 201) else "ERR"), what, res[0], res[1][:200], flush=True)
    if res[0] not in (200, 201):
        sys.exit(f"eKuiper 설정 실패: {what}")


for _ in range(60):
    try:
        if call("GET", "/")[0] == 200:
            break
    except OSError:
        pass
    time.sleep(2)
must("kafka conf", call("PUT", "/metadata/sources/kafka/confKeys/alw", {"brokers": "kafka:9092", "groupID": "alw-ekuiper"}))
must("stream", call("POST", "/streams", {"sql": 'CREATE STREAM alerts_raw () WITH (DATASOURCE="sensor.alerts", FORMAT="BINARY", TYPE="kafka", CONF_KEY="alw")'}))
must("rule", call("POST", "/rules", {
    "id": "alw_intake",
    "sql": 'SELECT "sensor.alerts" AS topic, meta(partition) AS partition_id, meta(offset) AS offset_id, self AS raw_payload FROM alerts_raw',
    "actions": [{"sql": {"url": "postgres://ar100:alwbench@work-db:5432/ar100_work?sslmode=disable", "table": "alarm_intake",
                         "fields": ["topic", "partition_id", "offset_id", "raw_payload"], "sendSingle": True}}],
    "options": {"qos": 1, "checkpointInterval": "1s"}}))
