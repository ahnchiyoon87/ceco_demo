#!/usr/bin/env python3
"""FUXA 프로젝트 생성기 — P&ID 미믹 + 태그 바인딩 + 양방향 제어 위젯.

simulator/plant.yaml 이 단일 출처다. 이 스크립트가 project.json 을 만들고
provision.py 가 POST /api/project 로 주입하므로 화면 수작업이 전혀 없다.

FUXA 스키마 (실제 구현 확인 결과):
  · devices 는 디바이스 '이름'을 키로 하는 맵
  · variableId = "<device>^~^<tagId>"
  · Modbus memaddress = 영역 오프셋  ("0" 코일 / "400000" 홀딩레지스터)
  · Modbus address 는 **1-based** (드라이버가 내부에서 -1 한다)
  · Float32 = big-endian ABCD (워드 스왑 없음) — 시뮬레이터와 일치
  · 뷰는 단일 svgcontent 문자열이고 items 는 SVG 요소 id 로 바인딩된다
"""
from __future__ import annotations

import json
import pathlib
import uuid

import yaml

ROOT = pathlib.Path(__file__).resolve().parent.parent
CFG = yaml.safe_load((ROOT / "simulator" / "plant.yaml").read_text())

DEV = "AR100"           # Modbus 디바이스: 이름 == id 로 두어 참조를 단순화
ALERTS = "ALERTS"       # MQTT 알람 구독 디바이스
SEP = "^~^"

# FUXA Modbus 영역 키. 드라이버가 내부적으로 getMemoryAddress() 로 만드는 키와
# 정확히 일치해야 한다. 코일은 리터럴 '000000' 이며 "0" 으로 쓰면
# "Cannot read properties of undefined (reading 'Items')" 로 디바이스 적재가 실패한다.
COIL_AREA = "000000"     # Coil Status
DISCRETE_AREA = "100000"  # Discrete Inputs
INPUT_REG_AREA = "300000"  # Input Registers
HOLD_AREA = "400000"     # Holding Registers

W, H = 1280, 780
INK = "#e8eef6"
DIM = "#8fa3ba"
PIPE = "#4a6488"


def gid(p: str) -> str:
    return f"{p}_{uuid.uuid4().hex[:12]}"


# ══════════════════════════════════════════════════════════════════════
# 1. 디바이스 & 태그
# ══════════════════════════════════════════════════════════════════════
mb_tags: dict[str, dict] = {}


def mb(tag_id: str, name: str, area: str, addr0: int, dtype: str, desc: str) -> str:
    """addr0 는 0-based 실제 Modbus 주소. FUXA 는 1-based 이므로 +1 해서 넣는다."""
    mb_tags[tag_id] = {
        "id": tag_id,
        "name": name,
        "label": name,
        "type": dtype,
        "memaddress": area,
        "address": str(addr0 + 1),
        "description": desc,
        "divisor": 1,
        "daq": {"enabled": True, "changed": False, "interval": 60},
    }
    return tag_id


SENSOR = {}
for t in CFG["tags"]:
    tid = t["name"].replace("-", "_")
    SENSOR[t["name"]] = mb(tid, t["name"], HOLD_AREA, t["hr"], "Float32",
                           f"{t['desc']} [{t['unit']}]")

C = CFG["commands"]["coils"]
Hd = CFG["commands"]["holding"]
CTL = {
    "pump":      mb("PumpRun", "PumpRun", COIL_AREA, C["pump_run"]["addr"], "Bool", C["pump_run"]["desc"]),
    "agitator":  mb("AgitatorRun", "AgitatorRun", COIL_AREA, C["agitator_run"]["addr"], "Bool", C["agitator_run"]["desc"]),
    "heater":    mb("HeaterEnable", "HeaterEnable", COIL_AREA, C["heater_enable"]["addr"], "Bool", C["heater_enable"]["desc"]),
    "ack":       mb("AlarmAck", "AlarmAck", COIL_AREA, C["alarm_ack"]["addr"], "Bool", C["alarm_ack"]["desc"]),
    "interlock": mb("Interlock", "Interlock", COIL_AREA, C["interlock"]["addr"], "Bool", C["interlock"]["desc"]),
    "pump_sp":   mb("PumpSpeedSP", "PumpSpeedSP", HOLD_AREA, Hd["pump_speed_sp"]["addr"], "Int16", Hd["pump_speed_sp"]["desc"]),
    "valve_sp":  mb("ValveOpenSP", "ValveOpenSP", HOLD_AREA, Hd["valve_open_sp"]["addr"], "Int16", Hd["valve_open_sp"]["desc"]),
    "temp_sp":   mb("TempSP", "TempSP", HOLD_AREA, Hd["temp_sp_x10"]["addr"], "Int16", Hd["temp_sp_x10"]["desc"]),
}

devices = {
    DEV: {
        "id": DEV,
        "name": DEV,
        "type": "ModbusTCP",
        "enabled": True,
        "polling": CFG["scan_interval_ms"],
        "property": {"address": "plant-simulator:502", "slaveid": 1,
                     "connectionTimeout": 5000, "reconnectInterval": 5000},
        "tags": mb_tags,
    },
    ALERTS: {
        "id": ALERTS,
        "name": ALERTS,
        "type": "MQTTclient",
        "enabled": True,
        "polling": 1000,
        "property": {
            "address": "mqtt://emqx:1883",
            "clientId": "fuxa-scada",
            "subscriptions": [{"topic": "scada/alerts/#", "qos": 1, "type": "json"}],
        },
        "tags": {
            "ActiveAlert": {
                "id": "ActiveAlert",
                "name": "ActiveAlert",
                "label": "활성 알람",
                "type": "string",
                "address": "scada/alerts/#",
                "description": "Flink Tier1/Tier2 통합 알람",
                "daq": {"enabled": False, "changed": True, "interval": 60},
            }
        },
    },
}


# ══════════════════════════════════════════════════════════════════════
# 2. P&ID 미믹 — SVG 도면 + 바인딩 아이템
#    Grafana 로는 구현 불가한 영역 (PDF p.11): 설비 레이아웃 기반 상태 표출 + 제어
# ══════════════════════════════════════════════════════════════════════
svg: list[str] = []
items: dict[str, dict] = {}


def prop(dev: str, tag: str, *, events=None, ranges=None) -> dict:
    return {
        "events": events or [],
        "variable": tag,
        "variableId": f"{dev}{SEP}{tag}",
        "variableSrc": dev,
        "alarmId": "", "alarmSrc": "", "alarm": "", "alarmColor": "",
        **({"ranges": ranges} if ranges else {}),
    }


def static(markup: str) -> None:
    svg.append(markup)


def value(x, y, tag, unit, *, size=15, anchor="end", color="#7fe3b0", dec=2):
    """실시간 수치. FUXA 가 <text> 내용을 태그 값으로 치환한다."""
    i = gid("VAL")
    svg.append(
        f'<g id="{i}" type="svg-ext-value" text-anchor="{anchor}" font-family="Consolas,monospace" '
        f'font-size="{size}" fill="none" stroke-width="0">'
        f'<text id="t{i}" x="{x}" y="{y}" text-anchor="{anchor}" font-family="Consolas,monospace" '
        f'font-size="{size}" fill="{color}" stroke-width="0">--.--</text></g>')
    items[i] = {"id": i, "type": "svg-ext-value", "name": tag, "label": "Value",
                "property": prop(DEV, tag,
                                 ranges=[{"type": "unit", "min": -99999, "max": 99999,
                                          "text": f" {unit}"}])}
    return i


def alert_text(x, y, w):
    i = gid("VAL")
    svg.append(
        f'<g id="{i}" type="svg-ext-value" text-anchor="start" font-family="Segoe UI,Arial" '
        f'font-size="13" fill="none" stroke-width="0">'
        f'<text id="t{i}" x="{x}" y="{y}" text-anchor="start" font-family="Segoe UI,Arial" '
        f'font-size="13" fill="#ffb4b4" stroke-width="0">알람 없음</text></g>')
    items[i] = {"id": i, "type": "svg-ext-value", "name": "ActiveAlert", "label": "Value",
                "property": prop(ALERTS, "ActiveAlert")}
    return i


def motor(cx, cy, r, tag, ranges):
    """회전기기 심볼. 전류 값 구간에 따라 원 색상이 바뀐다 (정지/정상/과부하)."""
    i = gid("MTR")
    svg.append(
        f'<g id="{i}" type="svg-ext-motor" stroke="#22303f" fill="#7f7f7f" '
        f'font-family="sans-serif" font-size="14" text-anchor="middle">'
        f'<ellipse id="c{i}" cx="{cx}" cy="{cy}" rx="{r}" ry="{r}" stroke="#22303f"/>'
        f'<path id="s{i}" stroke="null" fill="#10161f" '
        f'd="M{cx - r * 0.1},{cy - r * 0.92}L{cx + r * 0.95},{cy + 0.02 * r}'
        f'L{cx - r * 0.1},{cy + r * 0.96}L{cx - r * 0.1},{cy - r * 0.92}z"/></g>')
    items[i] = {"id": i, "type": "svg-ext-motor", "name": tag, "label": "Motor",
                "property": prop(DEV, tag, ranges=ranges)}
    return i


def valve(cx, cy, s, tag, ranges):
    """제어밸브 심볼. 개도 구간에 따라 색이 바뀐다 (닫힘/중간/열림)."""
    i = gid("VLA")
    svg.append(
        f'<g id="{i}" type="svg-ext-valve" fill="#7f7f7f" stroke="#22303f" '
        f'font-family="sans-serif" font-size="14" text-anchor="middle">'
        f'<path id="tl{i}" stroke="#22303f" d="M{cx - s},{cy - s}L{cx},{cy}L{cx - s},{cy + s}L{cx - s},{cy - s}z"/>'
        f'<path id="tr{i}" stroke="#22303f" d="M{cx + s},{cy + s}L{cx},{cy}L{cx + s},{cy - s}L{cx + s},{cy + s}z"/></g>')
    items[i] = {"id": i, "type": "svg-ext-valve", "name": tag, "label": "Valve",
                "property": prop(DEV, tag, ranges=ranges)}
    return i


def button(x, y, w, h, text, tag, setval, bg="#2f9e6e"):
    """제어 버튼. 클릭하면 Modbus 쓰기가 즉시 하달된다 (Southbound)."""
    i = gid("HXB")
    f = gid("HXB")
    svg.append(
        f'<g id="{i}" type="svg-ext-html_button" fill="#FFFFFF" font-size="14" '
        f'font-family="sans-serif" text-anchor="right" stroke="#000000">'
        f'<rect id="r{i}" x="{x}" y="{y}" width="{w}" height="{h}" fill="{bg}" stroke-width="0"/>'
        f'<foreignObject id="H-{f}" x="{x}" y="{y}" width="{w}" height="{h}">'
        f'<BUTTON id="B-{f}" class="md-btn md-btn-raised" '
        f'style="width:100%;height:100%;background-color:{bg};color:#ffffff;'
        f'vector-effect:non-scaling-stroke;font-size:13px;">{text}</BUTTON>'
        f'</foreignObject></g>')
    items[i] = {"id": i, "type": "svg-ext-html_button", "name": text, "label": "HtmlButton",
                "property": prop(DEV, tag,
                                 events=[{"type": "click", "action": "onSetValue",
                                          "actparam": str(setval)}])}
    return i


def number_input(x, y, w, h, tag):
    """설정치 입력창. 값을 넣으면 홀딩레지스터에 직접 기록된다."""
    i = gid("HXI")
    f = gid("HXI")
    svg.append(
        f'<g id="{i}" type="svg-ext-html_input" stroke="#000000" text-anchor="right" '
        f'font-family="sans-serif" font-size="14" fill="#f1f1f1">'
        f'<rect id="r{i}" x="{x}" y="{y}" width="{w}" height="{h}" fill="#ffffff" stroke-width="0"/>'
        f'<foreignObject id="H-{f}" x="{x}" y="{y}" width="{w}" height="{h}">'
        f'<INPUT id="I-{f}" type="number" '
        f'style="width:calc(100% - 7px);height:calc(100% - 7px);text-align:right;border:unset;'
        f'background-color:#ffffff;color:#000000;vector-effect:non-scaling-stroke;"/>'
        f'</foreignObject></g>')
    items[i] = {"id": i, "type": "svg-ext-html_input", "name": tag, "label": "HtmlInput",
                "property": prop(DEV, tag)}
    return i


def txt(x, y, s, *, size=13, fill=INK, anchor="start", weight="normal"):
    static(f'<text x="{x}" y="{y}" font-family="Segoe UI,Arial" font-size="{size}" fill="{fill}" '
           f'text-anchor="{anchor}" font-weight="{weight}">{s}</text>')


def box(x, y, w, h, *, fill="#141c28", stroke="#26364b", rx=6):
    static(f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{rx}" fill="{fill}" stroke="{stroke}"/>')


def line(x1, y1, x2, y2, *, w=7, c=PIPE):
    x, y = min(x1, x2), min(y1, y2)
    static(f'<rect x="{x}" y="{y}" width="{max(abs(x2 - x1), w)}" height="{max(abs(y2 - y1), w)}" '
           f'fill="{c}" rx="2"/>')


# ── 배경 ──
static(f'<rect x="0" y="0" width="{W}" height="{H}" fill="#0b111a"/>')
txt(24, 34, "AR-100 반응기 라인 · 공정 감시 및 제어", size=20, weight="600")
txt(24, 56, "FUXA Web SCADA — Modbus/TCP 양방향 (감시 + 제어)", size=12, fill=DIM)

# ── TK-101 원료탱크 ──
box(50, 110, 130, 190, fill="#101826")
static('<rect x="58" y="230" width="114" height="62" rx="3" fill="#1d4f7a" opacity="0.75"/>')
txt(115, 104, "TK-101 원료탱크", size=12, fill=DIM, anchor="middle")
txt(64, 258, "LT-101", size=11, fill=DIM)
value(170, 258, "LT_101", "%")

# ── 흡입 배관 → P-101 → 토출 배관 ──
line(180, 285, 250, 285)
motor(272, 288, 22, "IT_101",
      [{"type": "range", "min": "-1", "max": "0.5", "color": "#556072"},    # 정지
       {"type": "range", "min": "0.5", "max": "12", "color": "#2f9e6e"},    # 정상
       {"type": "range", "min": "12", "max": "999", "color": "#d9534f"}])   # 과부하
txt(272, 336, "P-101 공급펌프", size=11, fill=DIM, anchor="middle")
txt(206, 360, "FT-101", size=11, fill=DIM)
value(300, 360, "FT_101", "m3/h", size=13)
txt(206, 380, "IT-101", size=11, fill=DIM)
value(300, 380, "IT_101", "A", size=13)
line(294, 285, 430, 285)

# ── R-101 반응기 ──
box(430, 130, 300, 230, fill="#101826")
static('<rect x="440" y="250" width="280" height="100" rx="4" fill="#1d4f7a" opacity="0.7"/>')
txt(580, 122, "R-101 교반 반응기", size=12, fill=DIM, anchor="middle")

# 교반기 M-101
static('<rect x="576" y="130" width="8" height="90" fill="#7c8ea6"/>')
static('<path d="M545,222 L615,222 L605,236 L555,236 z" fill="#7c8ea6"/>')
motor(580, 112, 18, "IT_102",
      [{"type": "range", "min": "-1", "max": "0.5", "color": "#556072"},
       {"type": "range", "min": "0.5", "max": "9.6", "color": "#2f9e6e"},
       {"type": "range", "min": "9.6", "max": "999", "color": "#d9534f"}])
txt(618, 108, "M-101 교반기", size=11, fill=DIM)

# 재킷 히터
static('<rect x="424" y="250" width="8" height="100" fill="#8a5a2b"/>')
static('<rect x="728" y="250" width="8" height="100" fill="#8a5a2b"/>')
txt(440, 378, "HX-101 재킷", size=11, fill=DIM)

# 반응기 계측
for i, (lbl, tag, unit) in enumerate([
        ("LT-102", "LT_102", "%"), ("TT-101", "TT_101", "degC"),
        ("PT-101", "PT_101", "barg"), ("pH-101", "pH_101", ""),
        ("TT-102", "TT_102", "degC"), ("CT-101", "CT_101", "mS/cm"),
        ("IT-102", "IT_102", "A"), ("VT-101", "VT_101", "mm/s")]):
    col, row = i % 2, i // 2
    x = 448 + col * 150
    y = 158 + row * 22
    txt(x, y, lbl, size=11, fill=DIM)
    value(x + 130, y, tag, unit, size=13)

# ── 배출 배관 → CV-101 → 제품 ──
line(730, 285, 800, 285)
valve(826, 288, 20, "ValveOpenSP",
      [{"type": "range", "min": "-1", "max": "5", "color": "#d9534f"},      # 닫힘
       {"type": "range", "min": "5", "max": "70", "color": "#e8a33d"},      # 중간
       {"type": "range", "min": "70", "max": "200", "color": "#2f9e6e"}])   # 열림
txt(826, 336, "CV-101 배출밸브", size=11, fill=DIM, anchor="middle")
line(852, 285, 940, 285)
txt(860, 360, "FT-102", size=11, fill=DIM)
value(952, 360, "FT_102", "m3/h", size=13)
txt(950, 278, "→ 제품", size=12, fill=DIM)

# ══════════════════════════════════════════════════════════════════════
# 3. 운전원 제어 패널 (Southbound) — PDF p.11 "Grafana 가 못 하는 것"
# ══════════════════════════════════════════════════════════════════════
box(24, 420, 720, 190, fill="#0f1826")
txt(40, 446, "운전원 제어 (Modbus/TCP 직접 쓰기)", size=14, weight="600")

txt(40, 484, "P-101 공급펌프", size=12, fill=DIM)
button(190, 468, 62, 26, "기동", CTL["pump"], 1)
button(258, 468, 62, 26, "정지", CTL["pump"], 0, bg="#a94442")
txt(346, 484, "속도 SP [%]", size=12, fill=DIM)
number_input(444, 466, 70, 28, CTL["pump_sp"])
value(600, 486, CTL["pump_sp"], "%", size=14, dec=0)

txt(40, 524, "M-101 교반기", size=12, fill=DIM)
button(190, 508, 62, 26, "기동", CTL["agitator"], 1)
button(258, 508, 62, 26, "정지", CTL["agitator"], 0, bg="#a94442")
txt(346, 524, "밸브 개도 [%]", size=12, fill=DIM)
number_input(444, 506, 70, 28, CTL["valve_sp"])
value(600, 526, CTL["valve_sp"], "%", size=14, dec=0)

txt(40, 564, "HX-101 히터", size=12, fill=DIM)
button(190, 548, 62, 26, "ON", CTL["heater"], 1)
button(258, 548, 62, 26, "OFF", CTL["heater"], 0, bg="#a94442")
txt(346, 564, "온도 SP [°C×10]", size=12, fill=DIM)
number_input(444, 546, 70, 28, CTL["temp_sp"])
value(600, 566, CTL["temp_sp"], "", size=14, dec=0)

# ══════════════════════════════════════════════════════════════════════
# 4. 안전 · 알람 패널
# ══════════════════════════════════════════════════════════════════════
box(764, 420, 492, 190, fill="#0f1826")
txt(780, 446, "안전 인터록 및 알람", size=14, weight="600")

txt(780, 484, "고압 인터록 (PT-101 > 6.5 barg)", size=12, fill=DIM)
value(1120, 484, CTL["interlock"], "", size=14, color="#ff8080")
txt(780, 510, "→ 발동 시 P-101 강제 트립. FUXA 가 아닌 현장 로직이 결정론적으로 수행",
    size=10, fill="#6d7f95")

txt(780, 548, "활성 알람 (Flink Tier1/Tier2)", size=12, fill=DIM)
alert_text(780, 572, 460)
button(1120, 552, 110, 28, "알람 ACK", CTL["ack"], 1, bg="#3c6e9e")

# ── 하단 안내 ──
txt(24, 650, "데이터 경로", size=13, weight="600")
txt(24, 674,
    "Modbus/TCP → EdgeX(정규화·Store-and-Forward) → EMQX(QoS1) → Kafka → "
    "Flink(보간·규칙·CEP·ONNX) → InfluxDB → Grafana", size=11, fill=DIM)
txt(24, 696,
    "제어 경로는 FUXA → Modbus/TCP 직결입니다. 버튼을 누르면 물리 모델이 즉시 반응하고 "
    "그 변화가 위 전 구간을 거쳐 Grafana 트렌드까지 나타납니다.", size=11, fill=DIM)
txt(24, 724, "고장 주입:  curl -XPOST localhost:27080/fault -d '{\"scenario\":\"drift\"}'",
    size=11, fill="#7fa6cc")

# ══════════════════════════════════════════════════════════════════════
# 5. 프로젝트 조립
# ══════════════════════════════════════════════════════════════════════
svgcontent = (
    f'<svg width="{W}" height="{H}" xmlns="http://www.w3.org/2000/svg" '
    f'xmlns:svg="http://www.w3.org/2000/svg" xmlns:html="http://www.w3.org/1999/xhtml">'
    f'<g><title>AR-100</title>' + "".join(svg) + '</g></svg>'
)

view = {
    "id": "v_ar100_pid",
    "name": "AR-100 P&ID",
    "profile": {"width": W, "height": H, "bkcolor": "#0b111aff", "margin": 10},
    "variables": {},
    "svgcontent": svgcontent,
    "items": items,
    "property": {},
    "type": "editor",
}

project = {
    "version": "1.00",
    "name": "AR-100 Reactor Line",
    "devices": devices,
    "hmi": {"layout": {"start": view["id"], "navigation": {"type": "", "mode": ""},
                       "header": {"title": "AR-100 SCADA"}},
            "views": [view]},
    "charts": [],
    "server": {"id": "0", "name": "FUXA Server", "type": "FuxaServer", "property": {}},
}

out = pathlib.Path(__file__).parent / "project.json"
out.write_text(json.dumps(project, ensure_ascii=False, indent=1))
print(f"project.json 생성: 디바이스 {len(devices)}개 / Modbus 태그 {len(mb_tags)}개 / "
      f"바인딩 아이템 {len(items)}개 / SVG {len(svgcontent):,}자")
