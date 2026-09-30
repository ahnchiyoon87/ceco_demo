#!/usr/bin/env python3
"""FUXA 프로젝트 생성기 — 설비 등록부(shared/registry/generated/tags.json)에서 HMI 를 만든다.

새 구조(HANDOFF §2-3 화면): FUXA 는 가상설비·PLC 에 Modbus 로 붙지 않는다. OT 허브(UNS)만 구독하고,
운전원 조작은 설비별 …/cmd/operator 토픽으로 발행한다(엣지 → PLC 운전원 채널, 받을지는 PLC 가 정한다).
  · 계측·상태 태그: MQTT json 태그, 값은 JSON 의 'value' 칸
  · 조작 태그: MQTT json 발행 {command, value, ts}
  · 받은 요청: OT 수신기의 대기 목록(…/request/pending)을 보이고 수락·거부를 …/request/decision 으로 발행
  · 분석 경고(참고): IT 가 DMZ 로 낸 표시용 alert(AR-100/alert/display), 알람 목록과 따로·소리·조작 없음
  · 공정 알람: 등록부 규격(USL/LSL)·인터록·비상정지·현장 통신 이상(IEC 62682·ISA-18.2 범위 = 제어 시스템·HMI 알람)
화면 배치는 2_ot/hmi-fuxa/dashboard.py. provision.py 가 POST /api/project 로 넣는다.
"""
from __future__ import annotations

import itertools
import json
import pathlib

ROOT = pathlib.Path(__file__).resolve().parents[2]
REG = json.loads((ROOT / "shared" / "registry" / "generated" / "tags.json").read_text(encoding="utf-8"))
L = REG["line_prefix"]
DEV = "UNS"                 # MQTT 디바이스(OT 허브)
W, H = 1600, 1180
INK = "#e8eef6"
DIM = "#8fa3ba"
PIPE = "#4a6488"


_ids = itertools.count(1)


def gid(p: str) -> str:
    """화면 요소 ID: 생성할 때마다 같게(등록부가 같으면 project.json 이 같다)."""
    return f"{p}_{next(_ids):06d}"


# ══════════════════════════════════════════════════════════════════════
# 1. 태그
# ══════════════════════════════════════════════════════════════════════
tags: dict[str, dict] = {}


def sub(tag_id: str, topic: str, key: str, desc: str, daq: bool = False) -> str:
    """UNS 구독 태그: JSON 의 key 칸 값을 쓴다."""
    tags[tag_id] = {"id": tag_id, "name": tag_id, "label": tag_id, "type": "json", "address": topic, "memaddress": key,
                    "options": {"subs": [key]}, "description": desc,
                    "daq": {"enabled": daq, "changed": True, "interval": 1}}
    return tag_id


def pub(tag_id: str, topic: str, items: list[dict], desc: str) -> str:
    """발행 태그: 값을 넣으면 items 로 만든 JSON 을 topic 에 발행한다."""
    tags[tag_id] = {"id": tag_id, "name": tag_id, "label": tag_id, "type": "json", "address": topic, "memaddress": "",
                    "options": {"pubs": items}, "description": desc, "daq": {"enabled": False, "changed": False, "interval": 60}}
    return tag_id


SENSOR = {t["tag"]: sub(t["tag"].replace("-", "_"), t["topic"], "value", f'{t["desc"]} [{t["unit"]}]', daq=True)
          for t in REG["tags"]}
cmd_by = {(c["asset"], c["name"]): c for c in REG["commands"]}
P = f'{L}/{REG["plc"]["asset"]}'
STATE = {
    "pump": sub("PumpRun", cmd_by[("P-101", "run")]["status_topic"], "value", "P-101 운전 출력"),
    "agitator": sub("AgitatorRun", cmd_by[("M-101", "run")]["status_topic"], "value", "M-101 운전 출력"),
    "heater": sub("HeaterEnable", cmd_by[("HX-101", "enable")]["status_topic"], "value", "HX-101 히터 출력"),
    "cooler": sub("CoolerEnable", cmd_by[("HX-102", "enable")]["status_topic"], "value", "HX-102 냉각기 출력"),
    "pump_sp": sub("PumpSpeedSP", cmd_by[("P-101", "speed_sp")]["status_topic"], "value", "펌프 속도 설정값 [%]"),
    "valve_sp": sub("ValveOpenSP", cmd_by[("CV-101", "open_sp")]["status_topic"], "value", "밸브 개도 설정값 [%]"),
    "temp_sp": sub("TempSP", cmd_by[("R-101", "temp_sp")]["status_topic"], "value", "반응기 온도 설정값 [°C]"),
    "mode": sub("PlcMode", f"{P}/status/mode", "value", "운전 모드"),
    "maint": sub("Maintenance", f"{P}/status/maintenance", "value", "정비 모드"),
    "maint_op": sub("MaintOperator", f"{P}/status/maint_operator", "value", "정비 담당자 ID"),
    "interlock": sub("Interlock", f"{P}/status/interlock", "value", "고압 인터록"),
    "estop": sub("Estop", f"{P}/status/estop", "value", "비상정지"),
    "field_comm": sub("FieldComm", f"{P}/status/field_comm", "value", "현장 장치 통신"),
    "run_state": sub("PlcRunState", f"{P}/status/run_state", "value", "PLC 실행 상태"),
    "plc_comm": sub("PlcComm", REG["plc"]["comm_topic"], "value", "PLC 통신(엣지 폴링)"),
    "ack": sub("LastAck", REG["plc"]["ack_operator_topic"], "result", "마지막 운전원 명령 응답"),
}
now_item = {"key": "ts", "type": "timestamp", "value": ""}


def command(tag_id: str, asset: str, name: str, desc: str) -> str:
    c = cmd_by[(asset, name)]
    return pub(tag_id, c["operator_topic"], [{"key": "command", "type": "static", "value": name},
                                             {"key": "value", "type": "value", "value": ""}, now_item], desc)


CMD = {
    "pump": command("CmdPumpRun", "P-101", "run", "P-101 기동(1)/정지(0)"),
    "agitator": command("CmdAgitatorRun", "M-101", "run", "M-101 기동/정지"),
    "heater": command("CmdHeaterEnable", "HX-101", "enable", "HX-101 켬/끔"),
    "cooler": command("CmdCoolerEnable", "HX-102", "enable", "HX-102 켬/끔"),
    "pump_sp": command("CmdPumpSpeedSP", "P-101", "speed_sp", "펌프 속도 설정 [%]"),
    "valve_sp": command("CmdValveOpenSP", "CV-101", "open_sp", "밸브 개도 설정 [%]"),
    "temp_sp": command("CmdTempSP", "R-101", "temp_sp", "온도 설정 [°C]"),
    "mode": command("CmdMode", "PLC-01", "mode", "운전 모드(REMOTE_MANUAL/REMOTE_AUTO)"),
    "maint": command("CmdMaintenanceOn", "PLC-01", "maintenance", "정비 모드 켜기(값 = 담당자 ID)"),
    "ilk_reset": command("CmdInterlockReset", "PLC-01", "interlock_reset", "고압 인터록 리셋(압력이 해제 값 아래일 때만)"),
}
PENDING = {k: sub(f"Req_{k}", REG["request"]["pending_topic"], k, d) for k, d in (
    ("count", "대기 요청 수"), ("head_job", "맨 앞 요청 ID"), ("head_desc", "맨 앞 요청 내용"),
    ("head_context", "맨 앞 요청 원인 요약"), ("head_wait_s", "맨 앞 요청 대기 초"))}
DECIDE = {d: pub(f"Req_{d}", REG["request"]["decision_topic"], [
    {"key": "job_order_id", "type": "tag", "value": PENDING["head_job"]},
    {"key": "decision", "type": "static", "value": d}, now_item], f"받은 요청 {d}") for d in ("accept", "reject")}
ALERT = sub("AnalysisAlert", REG["alert_display_topic"], "text", "분석 경고(참고) — IT 분석 결과, 공정 알람 아님")

devices = {DEV: {"id": DEV, "name": DEV, "type": "MQTTclient", "enabled": True, "polling": 1000,
                 # 계정·비밀번호는 프로젝트(로그인 없이도 읽힘)에 두지 않는다 — provision.py 가 관리자만 읽는 장치 보안 저장소에 넣는다
                 "property": {"address": "mqtt://ot-hub:1883", "clientId": "fuxa-hmi"},
                 "tags": tags}}

# ══════════════════════════════════════════════════════════════════════
# 2. 공정 알람(FUXA): 규격 이탈·인터록·비상정지·현장 통신 이상
# ══════════════════════════════════════════════════════════════════════
def level(text, lo, hi, delay=2):
    return {"enabled": True, "checkdelay": 1, "min": lo, "max": hi, "timedelay": delay, "text": text,
            "group": "공정", "ackmode": "ackactive", "bkcolor": "", "color": ""}


off = {"enabled": False, "checkdelay": 1, "min": 0, "max": 0, "timedelay": 1, "text": "", "group": "", "ackmode": "float"}
alarms = []
for t in REG["tags"]:
    a = {"name": f'{t["tag"]} 규격', "property": {"variableId": SENSOR[t["tag"]], "variableSrc": DEV, "permission": None},
         "highhigh": dict(off), "high": dict(off), "low": dict(off), "info": dict(off)}
    if t["usl"] is not None:
        a["high"] = level(f'{t["tag"]} 상한 {t["usl"]:g} {t["unit"]} 초과', t["usl"], 1e9)
    if t["lsl"] is not None:
        a["low"] = level(f'{t["tag"]} 하한 {t["lsl"]:g} {t["unit"]} 미만', -1e9, t["lsl"])
    if t["usl"] is not None or t["lsl"] is not None:
        alarms.append(a)
for key, text in (("interlock", "고압 인터록 트립 — 펌프 정지(압력이 내려오면 리셋)"), ("estop", "비상정지 눌림"),):
    alarms.append({"name": text, "property": {"variableId": STATE[key], "variableSrc": DEV, "permission": None},
                   "highhigh": level(text, 1, 1, delay=0), "high": dict(off), "low": dict(off), "info": dict(off)})
for key, text in (("field_comm", "현장 장치(가상설비) 통신 끊김"), ("plc_comm", "PLC 통신 끊김(엣지 폴링)")):
    alarms.append({"name": text, "property": {"variableId": STATE[key], "variableSrc": DEV, "permission": None},
                   "highhigh": dict(off), "high": level(text, 0, 0, delay=2), "low": dict(off), "info": dict(off)})

# ══════════════════════════════════════════════════════════════════════
# 3. 화면 요소
# ══════════════════════════════════════════════════════════════════════
svg: list[str] = []
items: dict[str, dict] = {}


def prop(tag: str, *, events=None, ranges=None) -> dict:
    return {"events": events or [], "variable": tag, "variableId": tag, "variableSrc": DEV,
            "alarmId": "", "alarmSrc": "", "alarm": "", "alarmColor": "", **({"ranges": ranges} if ranges else {})}


def static(markup: str) -> None:
    svg.append(markup)


def value(x, y, tag, unit, *, size=15, anchor="end", color="#7fe3b0", dec=2):
    i = gid("VAL")
    svg.append(f'<g id="{i}" type="svg-ext-value" text-anchor="{anchor}" font-family="Consolas,monospace" font-size="{size}" '
               f'fill="none" stroke-width="0"><text id="t{i}" x="{x}" y="{y}" text-anchor="{anchor}" font-family="Consolas,monospace" '
               f'font-size="{size}" fill="{color}" stroke-width="0">--.--</text></g>')
    ranges = [{"type": 1, "min": -99999, "max": 99999, "text": unit, "fractionDigits": str(dec if unit else 0)}] if unit is not None else None
    items[i] = {"id": i, "type": "svg-ext-value", "name": tag, "label": "Value", "property": prop(tag, ranges=ranges)}
    return i


def text_value(x, y, tag, *, size=13, color="#ffb4b4", anchor="start", placeholder="—"):
    i = gid("VAL")
    svg.append(f'<g id="{i}" type="svg-ext-value" text-anchor="{anchor}" font-family="Segoe UI,Arial" font-size="{size}" fill="none" '
               f'stroke-width="0"><text id="t{i}" x="{x}" y="{y}" text-anchor="{anchor}" font-family="Segoe UI,Arial" font-size="{size}" '
               f'fill="{color}" stroke-width="0">{placeholder}</text></g>')
    items[i] = {"id": i, "type": "svg-ext-value", "name": tag, "label": "Value", "property": prop(tag)}
    return i


def semaphore_box(x, y, w, h, tag, ranges, *, rx=8):
    i = gid("SEM")
    svg.append(f'<g id="{i}" type="svg-ext-gauge_semaphore"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" '
               f'fill="{ranges[0]["color"]}"/></g>')
    items[i] = {"id": i, "type": "svg-ext-gauge_semaphore", "name": tag, "label": "HtmlSemaphore", "property": prop(tag, ranges=ranges)}
    return i


def motor(cx, cy, r, tag, ranges):
    i = gid("MTR")
    svg.append(f'<g id="{i}" type="svg-ext-motor" stroke="#22303f" fill="#7f7f7f" font-family="sans-serif" font-size="14" '
               f'text-anchor="middle"><ellipse id="c{i}" cx="{cx}" cy="{cy}" rx="{r}" ry="{r}" stroke="#22303f"/>'
               f'<path id="s{i}" stroke="null" fill="#10161f" d="M{cx - r * 0.1},{cy - r * 0.92}L{cx + r * 0.95},{cy + 0.02 * r}'
               f'L{cx - r * 0.1},{cy + r * 0.96}L{cx - r * 0.1},{cy - r * 0.92}z"/></g>')
    items[i] = {"id": i, "type": "svg-ext-motor", "name": tag, "label": "Motor", "property": prop(tag, ranges=ranges)}
    return i


def valve(cx, cy, s, tag, ranges):
    i = gid("VLA")
    svg.append(f'<g id="{i}" type="svg-ext-valve" fill="#7f7f7f" stroke="#22303f" font-family="sans-serif" font-size="14" '
               f'text-anchor="middle"><path id="tl{i}" stroke="#22303f" d="M{cx - s},{cy - s}L{cx},{cy}L{cx - s},{cy + s}L{cx - s},{cy - s}z"/>'
               f'<path id="tr{i}" stroke="#22303f" d="M{cx + s},{cy + s}L{cx},{cy}L{cx + s},{cy - s}L{cx + s},{cy + s}z"/></g>')
    items[i] = {"id": i, "type": "svg-ext-valve", "name": tag, "label": "Valve", "property": prop(tag, ranges=ranges)}
    return i


def button(x, y, w, h, text, tag, setval, bg="#2f9e6e"):
    i, f = gid("HXB"), gid("HXB")
    svg.append(f'<g id="{i}" type="svg-ext-html_button" fill="#FFFFFF" font-size="14" font-family="sans-serif" text-anchor="right" '
               f'stroke="#000000"><rect id="r{i}" x="{x}" y="{y}" width="{w}" height="{h}" fill="{bg}" stroke-width="0"/>'
               f'<foreignObject id="H-{f}" x="{x}" y="{y}" width="{w}" height="{h}"><BUTTON id="B-{f}" class="md-btn md-btn-raised" '
               f'style="width:100%;height:100%;background-color:{bg};color:#ffffff;border:0;border-radius:7px;'
               f'vector-effect:non-scaling-stroke;font-size:14px;">{text}</BUTTON></foreignObject></g>')
    items[i] = {"id": i, "type": "svg-ext-html_button", "name": text, "label": "HtmlButton",
                "property": prop(tag, events=[{"type": "click", "action": "onSetValue", "actparam": str(setval)}])}
    return i


def number_input(x, y, w, h, tag):
    i, f = gid("HXI"), gid("HXI")
    svg.append(f'<g id="{i}" type="svg-ext-html_input" stroke="#000000" text-anchor="right" font-family="sans-serif" font-size="14" '
               f'fill="#f1f1f1"><rect id="r{i}" x="{x}" y="{y}" width="{w}" height="{h}" fill="#ffffff" stroke-width="0"/>'
               f'<foreignObject id="H-{f}" x="{x}" y="{y}" width="{w}" height="{h}"><INPUT id="I-{f}" type="number" '
               f'style="width:calc(100% - 7px);height:calc(100% - 7px);text-align:right;border:unset;background-color:#ffffff;'
               f'color:#000000;vector-effect:non-scaling-stroke;"/></foreignObject></g>')
    items[i] = {"id": i, "type": "svg-ext-html_input", "name": tag, "label": "HtmlInput", "property": prop(tag)}
    return i


def txt(x, y, s, *, size=13, fill=INK, anchor="start", weight="normal"):
    static(f'<text x="{x}" y="{y}" font-family="Segoe UI,Arial" font-size="{size}" fill="{fill}" text-anchor="{anchor}" '
           f'font-weight="{weight}">{s}</text>')


def box(x, y, w, h, *, fill="#141c28", stroke="#26364b", rx=6):
    static(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}"/>')


def line(x1, y1, x2, y2, *, w=7, c=PIPE):
    x, y = min(x1, x2), min(y1, y2)
    static(f'<rect x="{x}" y="{y}" width="{max(abs(x2 - x1), w)}" height="{max(abs(y2 - y1), w)}" fill="{c}" rx="2"/>')


def build() -> dict:
    from dashboard import render
    render(globals())
    svgcontent = (f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" xmlns:svg="http://www.w3.org/2000/svg" '
                  f'xmlns:html="http://www.w3.org/1999/xhtml"><g><title>AR-100</title>' + "".join(svg) + '</g></svg>')
    view = {"id": "v_ar100_pid", "name": "AR-100 P&ID", "profile": {"width": W, "height": H, "bkcolor": "#0b111aff", "margin": 10},
            "variables": {}, "svgcontent": svgcontent, "items": items, "property": {}, "type": "editor"}
    return {"version": "1.00", "name": "AR-100 Reactor Line", "devices": devices,
            "hmi": {"layout": {"start": view["id"], "zoom": "autoresize", "navigation": {"type": "", "mode": ""},
                               "header": {"title": "AR-100 SCADA"}}, "views": [view]},
            "alarms": alarms, "charts": [], "server": {"id": "0", "name": "FUXA Server", "type": "FuxaServer", "property": {}}}


if __name__ == "__main__":
    project = build()
    out = pathlib.Path(__file__).parent / "project.json"
    out.write_text(json.dumps(project, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"project.json 생성: 태그 {len(tags)}개 / 알람 {len(alarms)}개 / 바인딩 아이템 {len(items)}개")
