"""hmibench 준비물 생성(컨테이너 없이 호스트에서 실행). 원본 fuxa/project.json 은 읽기만 한다.

    PYTHONUTF8=1 python harness/hmibench/hmi_prepare.py

만드는 것 (harness/hmibench/generated/):
  mosquitto.passwd   : hmi(읽기 전용)·bench(알람 발행)·nodered·tbgw 계정(PBKDF2-SHA512 $7$, mosquitto_passwd 와 같은 형식)
  project_poll.json  : V1 FUXA 프로젝트 그대로 + 알람 브로커 주소 mosquitto·계정(hmi). 설비 값은 Modbus 직접 폴링(V1 이중 폴링)
  project_uns.json   : P-UNS 변형 — 12 계측 태그를 MQTT 구독(iiot/AR-100/reactor-line-01/<tag>)으로, Modbus 장치에는 명령 태그만 남김
"""
import base64
import copy
import hashlib
import json
import os
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
OUT = pathlib.Path(__file__).resolve().parent / "generated"
USERS = {"hmi": "hmi-bench-pw", "bench": "bench-pub-pw", "nodered": "nodered-bench-pw", "tbgw": "tbgw-bench-pw"}


def mosq_hash(pw: str) -> str:
    salt = os.urandom(12)
    dk = hashlib.pbkdf2_hmac("sha512", pw.encode(), salt, 101, 64)
    return f"$7$101${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def main():
    OUT.mkdir(exist_ok=True)
    (OUT / "mosquitto.passwd").write_text("".join(f"{u}:{mosq_hash(p)}\n" for u, p in USERS.items()), newline="\n")
    src = json.loads((ROOT / "fuxa" / "project.json").read_text(encoding="utf-8"))
    poll = copy.deepcopy(src)
    al = poll["devices"]["ALERTS"]["property"]
    al.update({"address": "mqtt://mosquitto:1883", "username": "hmi", "password": USERS["hmi"]})
    (OUT / "project_poll.json").write_text(json.dumps(poll, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")

    uns = copy.deepcopy(poll)
    ar = uns["devices"]["AR100"]
    sensor_ids = [k for k, t in ar["tags"].items() if t.get("memaddress") == "400000" and int(t["address"]) < 100]
    mqtt_tags = {}
    for k in sensor_ids:
        t = ar["tags"].pop(k)
        mqtt_tags[k] = {"id": k, "name": t["name"], "label": t.get("label", t["name"]), "type": "json",
                        "address": f"iiot/AR-100/reactor-line-01/{t['name']}", "memaddress": "value",
                        "description": t.get("description", ""), "daq": t.get("daq", {})}
    uns["devices"]["UNS"] = {"id": "UNS", "name": "UNS", "type": "MQTTclient", "enabled": True, "polling": 1000,
                             "property": {"address": "mqtt://mosquitto:1883", "clientId": "fuxa-uns",
                                          "username": "hmi", "password": USERS["hmi"]},
                             "tags": mqtt_tags}
    (OUT / "project_uns.json").write_text(json.dumps(uns, ensure_ascii=False, indent=1), encoding="utf-8", newline="\n")
    print(f"generated: passwd({len(USERS)} users), poll(Modbus {len(poll['devices']['AR100']['tags'])} tags), "
          f"uns(MQTT {len(mqtt_tags)} + Modbus {len(ar['tags'])} command tags)")


if __name__ == "__main__":
    main()
