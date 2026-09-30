#!/usr/bin/env python3
"""설비 등록부(registry/equipment.yaml) → 각 망의 설정 생성.

배포 전에 한 번 돌린다(설비를 추가·변경했을 때). 산출물은 저장소에 함께 둔다.
    python registry/generate.py            # 생성
    python registry/generate.py --check    # 산출물이 정본과 같은지만 확인(다르면 종료 코드 1)

만드는 것
  registry/generated/tags.json                  신호 목록(토픽·키·수집 값·PLC 주소) — 엣지·적재기·수집기·FUXA 생성기가 읽는다
  registry/generated/work_masters.ot.json       OT 수신기용 작업 정의 표(작업 → 제어기 명령 토픽·명령 코드)
  registry/generated/work_masters.allow.json    DMZ·IT 허용 목록(작업 ID·설비·파라미터 범위만, 주소 없음)
  registry/generated/schemas/*.schema.json      JSON Schema(작업 요청, UNS 값)
  registry/generated/ontology_seed.json         온톨로지 설비·센서 노드와 관계(단계 7에서 그래프에 넣는다)
  flink/sql/tag_limits.csv                      Flink 규칙 범위(USL/LSL)
  postgres/init/20_registry.sql                 PostgreSQL registry 스키마 표 내용
"""
from __future__ import annotations

import argparse
import hashlib
import json
import pathlib
import sys

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
REG = yaml.safe_load((ROOT / "registry" / "equipment.yaml").read_text(encoding="utf-8"))
PLANT = yaml.safe_load((ROOT / "simulator" / "plant.yaml").read_text(encoding="utf-8"))
H = REG["hierarchy"]
LINE_PREFIX = f'{H["site"]}/{H["area"]}/{H["line"]}'


def topic(asset: str, kind: str, name: str) -> str:
    """UNS 토픽 규칙 {site}/{area}/{line}/{asset}/{kind}/{name} (HANDOFF §2-2)."""
    return f"{LINE_PREFIX}/{asset}/{kind}/{name}"


def deadband(sig: dict) -> float:
    cls = REG["signal_classes"][sig["class"]]
    if "deadband" in cls:
        return float(cls["deadband"])
    if cls.get("deadband_rule") == "noise_half":
        # 가상 센서 잡음은 현장 장치(plant.yaml noise)가 정본. 새 계기는 등록부 신호에 noise 를 적는다
        noise = PLANT["noise"].get(sig["tag"], sig.get("noise"))
        if noise is None:
            raise ValueError(f'{sig["tag"]}: 잡음(noise)을 plant.yaml 또는 등록부 신호에 적어야 deadband 를 정할 수 있다')
        return round(float(noise) / 2.0, 6)
    raise ValueError(f'deadband 규칙 없음: {sig["tag"]}')


def build() -> dict[pathlib.Path, str]:
    out: dict[pathlib.Path, str] = {}
    scale = float(PLANT.get("physics_time_scale", 1))
    tags, assets_seed, sensors_seed = [], [], []
    for a in REG["assets"]:
        assets_seed.append({"id": a["id"], "type": a["type"], "name": a["name"],
                            "site": H["site"], "area": H["area"], "line": H["line"]})
        for s in a.get("signals", []):
            cls = REG["signal_classes"][s["class"]]
            tags.append({
                "tag": s["tag"], "asset": a["id"], "asset_type": a["type"], "class": s["class"],
                "unit": s["unit"], "desc": s["desc"], "lsl": s["lsl"], "usl": s["usl"],
                "plc_ir": s["plc_ir"], "deadband": deadband(s),
                "scan_s": cls["scan_s"], "max_interval_s": cls["max_interval_s"],
                # 벽시계 = 공정 시간 ÷ 배속(하한은 엣지 폴링 주기로 자른다)
                "wall_scan_s": cls["scan_s"] / scale, "wall_max_interval_s": cls["max_interval_s"] / scale,
                "topic": topic(a["id"], "tag", s["tag"]),
                "kafka_key": a["id"],
            })
            sensors_seed.append({"tag": s["tag"], "asset": a["id"], "unit": s["unit"],
                                 "lsl": s["lsl"], "usl": s["usl"], "desc": s["desc"]})
    tags.sort(key=lambda t: t["plc_ir"])
    commands = []
    for a in REG["assets"]:
        for c in a.get("commands", []):
            commands.append({"asset": a["id"], **c,
                             "operator_topic": topic(a["id"], "cmd", "operator"),
                             "request_topic": topic(a["id"], "cmd", "request"),
                             "status_topic": topic(a["id"], "status", c["name"])})
    cmd_index = {(c["asset"], c["name"]): c for c in commands}

    ot_table, allow_table = [], []
    for wm in REG["work_masters"]:
        c = cmd_index[(wm["equipment_id"], wm["command"])]
        params = wm.get("parameters", [])
        ot_table.append({
            "work_master_id": wm["id"], "equipment_id": wm["equipment_id"], "command": wm["command"],
            "code": c["code"], "kind": c["kind"], "scale": c.get("scale", 1),
            "fixed_value": wm.get("value"), "parameters": params,
            "command_topic": c["request_topic"], "status_topic": c["status_topic"], "desc": wm["desc"]})
        allow_table.append({
            "work_master_id": wm["id"], "equipment_id": wm["equipment_id"],
            "parameters": [{"id": p["id"], "min": p["min"], "max": p["max"], "unit": p.get("unit")} for p in params],
            "desc": wm["desc"]})

    reg_doc = {"hierarchy": H, "line_prefix": LINE_PREFIX, "tags": tags, "commands": commands,
               "plc": {"asset": "PLC-01", "host": "plc", "port": 502, "unit_id": 1,
                       # 엣지가 읽는 두 블록(각각 한 번의 Modbus 요청): 계측값·순번·설비 시각 / 설정값·상태·ACK
                       "read_values": {"fc": 4, "start": 0, "count": 28, "seq_word": 24, "pts_word": 26},
                       "read_status": {"fc": 3, "start": 100, "count": 19,
                                       "fields": ["sp_pump", "sp_valve", "sp_temp_x10", "run", "mode", "maintenance",
                                                  "maint_operator", "interlock", "field_comm", "estop", "outputs",
                                                  "op_ack_seq", "op_ack_code", "rq_ack_seq", "rq_ack_code",
                                                  "rq_ack_hash_hi", "rq_ack_hash_lo", "heartbeat", "fb_fault"]},
                       # 엣지가 쓰는 %MW(홀딩 레지스터 1024 + n): 시각 동기, 운전원 채널, 외부 요청 채널
                       "write": {"time_sync": 1024, "operator": 1034, "request": 1044},
                       "ack_codes": {"0": "ACCEPTED", "1": "LOCAL_MODE", "2": "MAINTENANCE", "3": "MODE", "4": "RANGE",
                                     "5": "INTERLOCK", "6": "EXPIRED", "7": "DUPLICATE", "8": "UNKNOWN_COMMAND",
                                     "9": "ESTOP", "10": "NO_TIME_SYNC", "11": "PHYSICS"},
                       "modes": {"0": "LOCAL", "1": "REMOTE_MANUAL", "2": "REMOTE_AUTO"},
                       "outputs_bits": {"P-101/run": 0, "M-101/run": 1, "HX-101/enable": 2, "HX-102/enable": 3},
                       # 상태 신호 최대 간격(공정 28800 s)을 벽시계로: 상태 블록에는 설비 시각이 없어 벽시계로 잰다
                       "state_max_interval_wall_s": REG["signal_classes"]["state"]["max_interval_s"] / scale,
                       "status_prefix": topic("PLC-01", "status", ""),
                       "ack_operator_topic": topic("PLC-01", "ack", "operator"),
                       "ack_request_topic": topic("PLC-01", "ack", "request"),
                       "comm_topic": topic("PLC-01", "state", "comm")},
               "request": {"in_topic": f'{H["site"]}/request/in',
                           "response_prefix": f'{H["site"]}/response',
                           "pending_topic": f"{LINE_PREFIX}/request/pending",
                           "decision_topic": f"{LINE_PREFIX}/request/decision"},
               "alert_display_topic": f'{H["site"]}/alert/display',
               "legacy_telemetry_topic": "edgex/telemetry"}
    gen = ROOT / "registry" / "generated"
    dump = lambda o: json.dumps(o, ensure_ascii=False, indent=1) + "\n"
    out[gen / "tags.json"] = dump(reg_doc)
    out[gen / "work_masters.ot.json"] = dump(ot_table)
    out[gen / "work_masters.allow.json"] = dump({"work_masters": allow_table,
                                                  "requesters": REG["requesters"],
                                                  "approvers": REG["approvers"]})

    wm_ids = [w["work_master_id"] for w in allow_table]
    # 스키마 판은 draft-07: 게이트웨이(Python jsonschema)와 OT 수신기(Node-RED json 노드 = ajv 8 기본 클래스)가 둘 다 안다.
    # 2020-12 로 두면 ajv 8 이 메타 스키마를 몰라 엣지 기동 뒤 첫 요청을 SCHEMA_INVALID 로 거부한다(09-30 실측, 제어 회귀 S17).
    META = "http://json-schema.org/draft-07/schema#"
    job_schema = {
        "$schema": META,
        "$id": "https://ar100.local/schemas/job_request.schema.json",
        "title": "작업 요청(OPC UA ISA-95 Job Control 필드 흉내)",
        "type": "object", "additionalProperties": False,
        "required": ["job_order_id", "work_master_id", "equipment_id", "job_order_parameters",
                     "requester", "approver", "created_at"],
        "properties": {
            "job_order_id": {"type": "string", "pattern": "^[A-Za-z0-9._:-]{8,80}$"},
            "work_master_id": {"type": "string", "enum": wm_ids},
            "equipment_id": {"type": "string", "enum": sorted({w["equipment_id"] for w in allow_table})},
            "job_order_parameters": {"type": "array", "maxItems": 8, "items": {
                "type": "object", "additionalProperties": False, "required": ["id", "value"],
                "properties": {"id": {"type": "string"}, "value": {"type": "number"}}}},
            "requester": {"type": "string"}, "approver": {"type": "string"},
            "created_at": {"type": "number", "description": "요청 생성 시각(epoch 초)"},
            "expires_at": {"type": "number", "description": "게이트웨이가 붙이는 만료 시각(epoch 초, 표준에 없는 확장)"},
            "context": {"type": "object", "description": "원인 alert 요약(선택)"},
        },
    }
    uns_schema = {
        "$schema": META,
        "$id": "https://ar100.local/schemas/uns_value.schema.json",
        "title": "UNS 값(Sparkplug 규칙을 JSON으로 흉내: 출처 시각·품질·순번)",
        "type": "object", "required": ["ts", "value", "quality"],
        "properties": {"ts": {"type": "integer", "description": "출처 시각(epoch ns, 엣지가 읽은 시각)"},
                       "value": {"type": ["number", "null"]},
                       "quality": {"enum": ["GOOD", "UNCERTAIN", "BAD", "STALE"]},
                       "seq": {"type": "integer", "description": "현장 장치 스캔 순번"},
                       "pts": {"type": "integer", "description": "설비 시각(초)"}},
    }
    out[gen / "schemas" / "job_request.schema.json"] = dump(job_schema)
    out[gen / "schemas" / "uns_value.schema.json"] = dump(uns_schema)
    out[gen / "ontology_seed.json"] = dump({"assets": assets_seed, "sensors": sensors_seed,
                                             "relations": [{"from": s["asset"], "type": "HAS_SENSOR", "to": s["tag"]}
                                                           for s in sensors_seed]})

    csv_lines = []
    for t in tags:
        fmt = lambda v: "" if v is None else str(v)
        csv_lines.append(f'{t["tag"]},{t["unit"]},{fmt(t["lsl"])},{fmt(t["usl"])}')
    out[ROOT / "flink" / "sql" / "tag_limits.csv"] = "\n".join(csv_lines) + "\n"

    sql = ["-- registry/generate.py 가 registry/equipment.yaml 에서 생성. 손으로 고치지 않는다.",
           "SET search_path TO registry;"]
    q = lambda v: "NULL" if v is None else ("'" + str(v).replace("'", "''") + "'" if isinstance(v, str) else str(v))
    for a in REG["assets"]:
        sql.append(f"INSERT INTO equipment(id, type, name, site, area, line) VALUES "
                   f"({q(a['id'])},{q(a['type'])},{q(a['name'])},{q(H['site'])},{q(H['area'])},{q(H['line'])});")
    for t in tags:
        sql.append(f"INSERT INTO signal(tag, equipment_id, class, unit, lsl, usl, deadband, scan_s, max_interval_s, topic) VALUES "
                   f"({q(t['tag'])},{q(t['asset'])},{q(t['class'])},{q(t['unit'])},{q(t['lsl'])},{q(t['usl'])},"
                   f"{t['deadband']},{t['scan_s']},{t['max_interval_s']},{q(t['topic'])});")
    for w in allow_table:
        sql.append(f"INSERT INTO work_master(id, equipment_id, parameters, description) VALUES "
                   f"({q(w['work_master_id'])},{q(w['equipment_id'])},{q(json.dumps(w['parameters'], ensure_ascii=False))}::jsonb,{q(w['desc'])});")
    out[ROOT / "postgres" / "init" / "20_registry.sql"] = "\n".join(sql) + "\n"
    out.update(build_plc(tags))
    out.update(build_nodered(reg_doc))
    return out


def build_nodered(reg: dict) -> dict[pathlib.Path, str]:
    """엣지 후보 Node-RED 의 흐름: 수집·명령 탭 + OT 작업 요청 수신기 탭(전용 MQTT 계정). 함수 본문은 edge/nodered/src/*.js."""
    src = ROOT / "edge" / "nodered" / "src"
    js = lambda name: (src / f"{name}.js").read_text(encoding="utf-8")
    L = reg["line_prefix"]
    nodes: list[dict] = []
    pos = {"edge": [0, 0], "receiver": [0, 0]}

    def add(tab, node_id, typ, x, y, wires=None, **props):
        n = {"id": node_id, "type": typ, "z": tab, "x": x, "y": y, **props}
        if wires is not None:
            n["wires"] = wires
        nodes.append(n)

    def fn(tab, node_id, name, code, x, y, wires, outputs=1):
        add(tab, node_id, "function", x, y, wires, name=name, func=js(code), outputs=outputs,
            timeout=0, noerr=0, initialize="", finalize="", libs=[])

    def mqtt_in(tab, node_id, name, topic, broker, x, y, wires):
        add(tab, node_id, "mqtt in", x, y, wires, name=name, topic=topic, qos="1", datatype="utf8", broker=broker,
            nl=False, rap=True, rh=0, inputs=0)

    def flex_write(tab, node_id, name, x, y, wires):
        add(tab, node_id, "modbus-flex-write", x, y, wires, name=name, showStatusActivities=False, showErrors=True,
            showWarnings=True, server="mbc", emptyMsgOnFail=False, keepMsgProperties=True, delayOnStart=False, startDelayTime="")

    def read(tab, node_id, name, dtype, adr, qty, x, y, wires):
        add(tab, node_id, "modbus-read", x, y, wires, name=name, topic=name, showStatusActivities=True, logIOActivities=False,
            showErrors=False, showWarnings=True, unitid=str(reg["plc"]["unit_id"]), dataType=dtype, adr=str(adr),
            quantity=str(qty), rate="250", rateUnit="ms", delayOnStart=False, startDelayTime="", server="mbc",
            useIOFile=False, ioFile="", useIOForPayload=False, emptyMsgOnFail=False)

    edge_state = f"{L}/EDGE-01/state/node"
    nodes += [
        {"id": "edge", "type": "tab", "label": "엣지 수집·명령 (EDGE-01)", "disabled": False,
         "info": "PLC 를 250 ms 마다 두 블록으로 읽어 UNS·edgex/telemetry 로 낸다. 운전원·외부 요청 명령을 PLC 명령 채널에 쓴다. 등록부에서 생성(registry/generate.py)."},
        {"id": "receiver", "type": "tab", "label": "OT 작업 요청 수신기", "disabled": False,
         "info": "외부 시스템(우리 AI)의 작업 요청을 OT 안에서 받을지 정한다. 전용 MQTT 계정. 결정과 제어기 명령 토픽 발행까지만."},
        {"id": "mbc", "type": "modbus-client", "name": "PLC-01", "clienttype": "tcp", "bufferCommands": True,
         "stateLogEnabled": False, "queueLogEnabled": False, "failureLogEnabled": True, "tcpHost": reg["plc"]["host"],
         "tcpPort": str(reg["plc"]["port"]), "tcpType": "DEFAULT", "serialPort": "", "serialType": "RTU-BUFFERD",
         "serialBaudrate": "9600", "serialDatabits": "8", "serialStopbits": "1", "serialParity": "none",
         "serialConnectionDelay": "100", "serialAsciiResponseStartDelimiter": "", "unit_id": str(reg["plc"]["unit_id"]),
         "commandDelay": "1", "clientTimeout": "1000", "reconnectOnTimeout": True, "reconnectTimeout": "2000",
         "parallelUnitIdsAllowed": True, "showErrors": False, "showWarnings": True, "showLogs": False},
        {"id": "mqe", "type": "mqtt-broker", "name": "OT 허브(edge 계정)", "broker": "ot-hub", "port": "1883",
         "clientid": "edge-01", "autoConnect": True, "usetls": False, "protocolVersion": "4", "keepalive": "15",
         "cleansession": True, "autoUnsubscribe": True,
         "birthTopic": edge_state, "birthQos": "1", "birthRetain": "true", "birthPayload": '{"value":true,"quality":"GOOD"}', "birthMsg": {},
         "closeTopic": edge_state, "closeQos": "1", "closeRetain": "true", "closePayload": '{"value":false,"quality":"GOOD"}', "closeMsg": {},
         "willTopic": edge_state, "willQos": "1", "willRetain": "true", "willPayload": '{"value":false,"quality":"GOOD"}', "willMsg": {},
         "userProps": "", "sessionExpiry": ""},
        {"id": "mqr", "type": "mqtt-broker", "name": "OT 허브(ot-receiver 계정)", "broker": "ot-hub", "port": "1883",
         "clientid": "ot-receiver", "autoConnect": True, "usetls": False, "protocolVersion": "5", "keepalive": "15",
         "cleansession": False, "sessionExpiry": "3600", "autoUnsubscribe": False,
         "birthTopic": "", "closeTopic": "", "willTopic": "", "userProps": ""},
    ]
    # ── 엣지 탭 ──
    read("edge", "rd_values", "계측값 블록 FC4 0..27", "InputRegister", reg["plc"]["read_values"]["start"],
         reg["plc"]["read_values"]["count"], 180, 80, [["f_values"], []])
    read("edge", "rd_status", "상태 블록 FC3 100..118", "HoldingRegister", reg["plc"]["read_status"]["start"],
         reg["plc"]["read_status"]["count"], 180, 160, [["f_status"], []])
    fn("edge", "f_values", "값 → UNS·edgex/telemetry", "values", 460, 80, [["f_saf"]])
    fn("edge", "f_status", "상태·ACK → UNS", "status", 460, 160, [["f_saf"]])
    add("edge", "st_modbus", "status", 180, 240, [["f_comm"]], name="PLC 폴링 상태", scope=["rd_values", "rd_status"])
    fn("edge", "f_comm", "장치 통신 상태(DDEATH 흉내)", "comm", 460, 240, [["f_saf"]])
    fn("edge", "f_saf", "끊김 시 저장 후 전송", "saf", 760, 160, [["mq_out"]])
    add("edge", "mq_out", "mqtt out", 1000, 160, [], name="OT 허브로", topic="", qos="", retain="", respTopic="",
        contentType="", userProps="", correl="", expiry="", broker="mqe")
    add("edge", "st_mqtt", "status", 760, 240, [["f_mqstate"]], name="OT 허브 연결 상태", scope=["mq_out"])
    fn("edge", "f_mqstate", "연결 표시", "mqtt_state", 1000, 240, [["f_saf"]])
    add("edge", "in_time", "inject", 180, 320, [["f_time"]], name="1초", props=[], repeat="1", crontab="", once=True,
        onceDelay="2", topic="")
    fn("edge", "f_time", "시각 동기(%MW0..1)", "time_sync", 460, 320, [["fw_time"]])
    flex_write("edge", "fw_time", "시각 쓰기", 760, 320, [[], []])
    mqtt_in("edge", "in_opcmd", "운전원 명령", f"{L}/+/cmd/operator", "mqe", 180, 400, [["f_opcmd"]])
    fn("edge", "f_opcmd", "운전원 명령 → PLC 운전원 채널", "operator_cmd", 460, 400, [["fw_op1"], ["f_saf"]], outputs=2)
    flex_write("edge", "fw_op1", "코드·값 쓰기", 760, 400, [["f_opseq"], []])
    fn("edge", "f_opseq", "순번", "write_seq", 960, 400, [["fw_op2"]])
    flex_write("edge", "fw_op2", "순번 쓰기", 1160, 400, [[], []])
    mqtt_in("edge", "in_rqcmd", "외부 요청 명령", f"{L}/+/cmd/request", "mqe", 180, 480, [["f_rqcmd"]])
    fn("edge", "f_rqcmd", "요청 명령 → PLC 외부 요청 채널", "request_cmd", 460, 480, [["fw_rq1"]])
    flex_write("edge", "fw_rq1", "코드·값·만료·해시 쓰기", 760, 480, [["f_rqseq"], []])
    fn("edge", "f_rqseq", "순번", "write_seq", 960, 480, [["fw_rq2"]])
    flex_write("edge", "fw_rq2", "순번 쓰기", 1160, 480, [[], []])
    add("edge", "http_metrics", "http in", 180, 560, [["f_metrics"]], name="지표", url="/metrics", method="get",
        upload=False, swaggerDoc="")
    fn("edge", "f_metrics", "Prometheus 텍스트", "metrics", 460, 560, [["http_resp"]])
    add("edge", "http_resp", "http response", 700, 560, [], name="", statusCode="", headers={})
    # ── 수신기 탭 ──
    mqtt_in("receiver", "in_req", "작업 요청(DMZ → 브리지 in)", reg["request"]["in_topic"], "mqr", 180, 80, [["ch_schema"]])
    add("receiver", "ch_schema", "change", 420, 80, [["js_req"]], name="요청 스키마", rules=[
        {"t": "set", "p": "schema", "pt": "msg", "to": "jobSchema", "tot": "global"}], action="", property="",
        from_="", to="", reg=False)
    add("receiver", "js_req", "json", 620, 80, [["f_req"]], name="스키마 재검사", property="payload", action="obj", pretty=False)
    add("receiver", "catch_schema", "catch", 620, 140, [["f_invalid"]], name="스키마 오류", scope=["js_req"], uncaught=False)
    fn("receiver", "f_req", "수용 결정(자동 수용 / 운전원 대기 / 거부)", "receiver_request", 900, 80, [["f_batch"]])
    fn("receiver", "f_invalid", "스키마 오류 거부", "receiver_invalid", 900, 140, [["f_batch"]])
    mqtt_in("receiver", "in_plc", "PLC 상태", f"{L}/PLC-01/status/+", "mqr", 180, 220, [["f_rstate"]])
    fn("receiver", "f_rstate", "모드·정비 모드 기억", "receiver_state", 460, 220, [[]])
    mqtt_in("receiver", "in_dec", "운전원 결정(FUXA)", reg["request"]["decision_topic"], "mqr", 180, 300, [["f_dec"]])
    fn("receiver", "f_dec", "수락 → 명령 / 거부", "receiver_decision", 460, 300, [["f_batch"]])
    add("receiver", "in_tick", "inject", 180, 380, [["f_timer"]], name="1초", props=[], repeat="1", crontab="",
        once=True, onceDelay="2", topic="")
    fn("receiver", "f_timer", "운전원 대기 60초·대기 목록", "receiver_timer", 460, 380, [["f_batch"]])
    mqtt_in("receiver", "in_ack", "PLC 요청 ACK", reg["plc"]["ack_request_topic"], "mqr", 180, 460, [["f_ack"]])
    fn("receiver", "f_ack", "PLC ACK → 응답(plc 단계)", "receiver_plc_ack", 460, 460, [["f_batch"]])
    fn("receiver", "f_batch", "묶음 풀기", "batch", 1100, 220, [["mq_rout"]])
    add("receiver", "mq_rout", "mqtt out", 1300, 220, [], name="OT 허브로(수신기)", topic="", qos="", retain="",
        respTopic="", contentType="", userProps="", correl="", expiry="", broker="mqr")
    for n in nodes:  # 파이썬 예약어를 피한 속성 이름 되돌리기
        if "from_" in n:
            n["from"] = n.pop("from_")
    cred = {"mqe": {"user": "edge", "password": "${MQTT_EDGE_PASSWORD}"},
            "mqr": {"user": "ot-receiver", "password": "${MQTT_RECEIVER_PASSWORD}"}}
    d = ROOT / "edge" / "nodered"
    return {d / "flows.json": json.dumps(nodes, ensure_ascii=False, indent=1) + "\n",
            d / "flows_cred.json": json.dumps(cred, indent=1) + "\n"}


PLC_TASK_MS = 100            # PLC 태스크 주기 = Modbus 마스터 주기
PLC_SIM_HOST = "plant-sim"   # 가상설비 호스트 이름(ot-net)


def build_plc(tags: list[dict]) -> dict[pathlib.Path, str]:
    """PLC 프로젝트(OpenPLC Editor v4 형식): 프로그램 상수와 Modbus 마스터·슬레이브 설정."""
    ctl = REG["controller"]
    ap = PLANT["autopilot"]
    hold = PLANT["commands"]["holding"]
    temp = next(c for a in REG["assets"] for c in a.get("commands", []) if c["name"] == "temp_sp")
    subst = {
        "SP_PUMP_DEFAULT": f'{float(hold["pump_speed_sp"]["default"])}',
        "SP_VALVE_DEFAULT": f'{float(hold["valve_open_sp"]["default"])}',
        "SP_TEMP_DEFAULT": f'{hold["temp_sp_x10"]["default"] / 10.0}',
        "FIELD_COMM_TIMEOUT_S": str(ctl["field_comm_timeout_s"]),
        "TIME_SYNC_TIMEOUT_S": str(ctl["time_sync_timeout_s"]),
        "ILK_TRIP": f'{ctl["interlock"]["trip_barg"]}', "ILK_RESET": f'{ctl["interlock"]["reset_barg"]}',
        "TEMP_X10_MIN": str(int(temp["min"] * temp["scale"])), "TEMP_X10_MAX": str(int(temp["max"] * temp["scale"])),
        "DRY_RUN_MIN_LEVEL": f'{ctl["dry_run_min_level_pct"]}',
        "HOLD_CYCLES": str(int(ap["hold_after_manual_s"] * 1000 / PLC_TASK_MS)),
        "AP_PERIOD_S": f'{float(ap["period_s"])}', "AP_RAMP_S": f'{float(ap["ramp_s"])}',
        "AP_SUBSTEP_S": f'{float(PLANT["physics_max_substep_s"])}',
        "AP_PUMP_LO": f'{float(ap["ranges"]["pump_speed_sp"][0])}', "AP_PUMP_HI": f'{float(ap["ranges"]["pump_speed_sp"][1])}',
        "AP_VALVE_LO": f'{float(ap["ranges"]["valve_open_sp"][0])}', "AP_VALVE_HI": f'{float(ap["ranges"]["valve_open_sp"][1])}',
        "AP_TEMP_LO": f'{float(ap["ranges"]["temp_sp_c"][0])}', "AP_TEMP_HI": f'{float(ap["ranges"]["temp_sp_c"][1])}',
        "RUN_CURRENT_A": f'{ctl["running_current_a"]}', "FB_TIMEOUT_S": str(ctl["feedback_timeout_s"]),
    }
    st = (ROOT / "plc" / "main.st.tmpl").read_text(encoding="utf-8")
    st = st.replace("   이 파일은 plc/main.st.tmpl 에서 registry/generate.py 가 만든다.",
                    "   이 파일은 registry/generate.py 가 plc/main.st.tmpl 에서 만든다. 손으로 고치지 않는다.")
    for k, v in subst.items():
        st = st.replace("{{" + k + "}}", v)
    if "{{" in st:
        raise ValueError("PLC 템플릿에 채우지 않은 자리가 있다")

    sim = PLANT["commands"]
    panel = PLANT["field_panel"]["registers"]
    # 계측값 + 순번·설비 시각(가상설비 HR 0..27)을 한 번에 읽는다
    last_word = max(max(t["plc_ir"] for t in tags) + 2, sim["plant_time"]["addr"] + 2)

    def group(gid, name, fc, offset, length, iec_first):
        return {"id": gid, "name": name, "functionCode": str(fc), "cycleTime": PLC_TASK_MS,
                "offset": str(offset), "length": length, "errorHandling": "keep-last-value",
                "ioPoints": [{"id": f"{gid}-0", "name": f"{gid}-0", "type": "WORD", "iecLocation": iec_first}]}
    project = {
        "meta": {"name": "ar100-plc", "type": "plc-project"},
        "data": {
            "pous": [], "dataTypes": [], "libraries": [],
            "configuration": {"resource": {
                "tasks": [{"name": "task0", "triggering": "Cyclic", "interval": f"T#{PLC_TASK_MS}ms", "priority": 1}],
                "instances": [{"name": "instance0", "program": "main", "task": "task0"}],
                "globalVariables": []}},
            # Modbus 슬레이브: 엣지가 붙는다(입력 %IW = FC4, 출력 %QW·메모리 %MW = FC3/6/16)
            "servers": [{"name": "edge_server", "protocol": "modbus-tcp",
                         "modbusSlaveConfig": {"enabled": True, "networkInterface": "0.0.0.0", "port": 502}}],
            # Modbus 마스터: 현장 장치(가상설비)
            "remoteDevices": [{"name": "plant", "protocol": "modbus-tcp", "modbusTcpConfig": {
                "transport": "tcp", "host": PLC_SIM_HOST, "port": 502, "timeout": 1000, "slaveId": 1,
                "ioGroups": [
                    group("tags", "계측 12점·스캔 순번·설비 시각", 3, 0, last_word, "%IW0"),
                    group("panel", "현장 패널", 3, PLANT["field_panel"]["base"], len(panel), f'%IW{PLANT["field_panel"]["base"]}'),
                    group("coils", "구동기", 15, sim["coils"]["pump_run"]["addr"], 4, "%QX0.0"),
                    group("sp", "설정값", 16, sim["holding"]["pump_speed_sp"]["addr"], 3,
                          f'%QW{sim["holding"]["pump_speed_sp"]["addr"]}'),
                ]}}],
        },
    }
    device = {"deviceBoard": "OpenPLC Runtime v4", "communicationPort": "", "runtimeIpAddress": "",
              "vendorScreenData": {}, "vendorScreenDataByBoard": {},
              "persistentStorage": {"enabled": True, "path": "", "flushSeconds": 5},
              "persistentStorageByBoard": {}, "selectedPlatformOptions": {}, "vppPackagePinsByBoard": {}}
    p = ROOT / "plc" / "project"
    return {p / "pous" / "programs" / "main.st": st,
            p / "project.json": json.dumps(project, ensure_ascii=False, indent=2) + "\n",
            p / "devices" / "configuration.json": json.dumps(device, ensure_ascii=False, indent=2) + "\n"}


def build_fuxa() -> dict[pathlib.Path, str]:
    """FUXA 화면(fuxa/build_project.py)은 생성된 tags.json 을 읽으므로 다른 산출물을 쓴 뒤 만든다."""
    sys.path.insert(0, str(ROOT / "fuxa"))
    import build_project
    return {ROOT / "fuxa" / "project.json": json.dumps(build_project.build(), ensure_ascii=False, indent=1) + "\n"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true")
    args = ap.parse_args()
    stale: list[pathlib.Path] = []

    def apply(files: dict[pathlib.Path, str]) -> None:
        for path, content in files.items():
            cur = path.read_text(encoding="utf-8") if path.exists() else None
            if cur != content:
                stale.append(path)
                if not args.check:
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(content, encoding="utf-8", newline="\n")
    files = build()
    apply(files)
    fuxa = build_fuxa()          # 방금 쓴 tags.json 을 읽는다(--check 면 저장소의 tags.json)
    apply(fuxa)
    files.update(fuxa)
    digest = hashlib.sha256("".join(files[p] for p in sorted(files)).encode()).hexdigest()[:12]
    if args.check:
        for p in stale:
            print(f"다름: {p.relative_to(ROOT)}")
        print(f"registry {digest}: {'정본과 같음' if not stale else f'{len(stale)}개 파일이 정본과 다름'}")
        return 1 if stale else 0
    print(f"registry {digest}: {len(files)}개 파일 생성(바뀐 것 {len(stale)}개)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
