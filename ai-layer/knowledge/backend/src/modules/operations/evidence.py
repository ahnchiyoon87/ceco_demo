"""Read-only evidence adapters. Never expose injected-fault ground truth to AI."""
import base64
import json
import os
import re
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import APIRouter

from .api import get_incident
from ..ontology.tools import _run_readonly_query

router = APIRouter(prefix="/api/operations", tags=["manufacturing-evidence"])


# ── 설비 접점: DMZ InfluxDB 의 OT 원시값 사본을 읽기 전용 계정으로 조회한다(HANDOFF §1 AI 층, §2-1 ③) ──
# V1 은 가상설비 HTTP /state 를 직접 읽었다. 새 구조에서 IT 는 OT 에 닿지 않고 DMZ 사본만 본다.
# 명령 상태·인터록·모드·순번은 엣지가 UNS 에 낸 PLC 상태 토픽이 DMZ 사본(plc_status)에 들어온 것이다.
COMMANDS = {  # V1 /state 의 commands 이름 → PLC 상태(설비/이름)
    "pump_run": ("P-101", "run"), "agitator_run": ("M-101", "run"), "heater_enable": ("HX-101", "enable"),
    "cooler_enable": ("HX-102", "enable"), "pump_speed_sp": ("P-101", "speed_sp"), "valve_open_sp": ("CV-101", "open_sp"),
    "temp_sp_c": ("R-101", "temp_sp")}
SWITCHES = {"pump_run", "agitator_run", "heater_enable", "cooler_enable"}
STALE_S = 10


def dmz_query(influxql: str) -> list[dict]:
    """InfluxQL(v1 호환, 읽기 전용 계정) → 행 목록. 실패하면 OSError·ValueError."""
    url = os.environ.get("INFLUX_URL", "http://dmz-influx:8086") + "/query?" + urlencode(
        {"db": os.environ.get("INFLUX_DB", "plant_raw"), "q": influxql})
    auth = base64.b64encode(f'{os.environ["INFLUX_USER"]}:{os.environ["INFLUX_PASSWORD"]}'.encode()).decode()
    with urlopen(Request(url, headers={"Authorization": f"Basic {auth}"}), timeout=10) as response:
        body = json.load(response)
    out = []
    for result in body.get("results", []):
        if "error" in result:
            raise ValueError(result["error"])
        for series in result.get("series", []):
            for values in series["values"]:
                out.append({**series.get("tags", {}), **dict(zip(series["columns"], values))})
    return out


def q(value: str) -> str:
    return "'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'"


@router.get("/plant")
def live_state(site: str = "AR-100", device: str = "reactor-line-01"):
    try:
        where = f"site={q(site)} AND device={q(device)}"
        status = dmz_query(f'SELECT last("num") AS num, last("text") AS text FROM "plc_status" WHERE {where} '
                           f'AND time > now() - 1h GROUP BY "asset", "name"')
        values = dmz_query(f'SELECT last("value") AS value, last("seq") AS seq FROM "process_raw" WHERE {where} '
                           f'AND time > now() - {STALE_S}s GROUP BY "tag"')
        st = {(r["asset"], r["name"]): (r["text"] if r.get("text") is not None else r.get("num")) for r in status}
        if not values or ("PLC-01", "mode") not in st:
            return {"status": "unavailable", "error": f"최근 {STALE_S}초 설비 관측 또는 PLC 상태가 DMZ 사본에 없습니다."}
        commands = {}
        for name, key in COMMANDS.items():
            v = st.get(key)
            commands[name] = (bool(v) if name in SWITCHES else round(float(v), 1)) if v is not None else None
        return {"status": "available", "retrieved_at": datetime.now(timezone.utc).isoformat(), "site": site, "device": device,
                "seq": max(int(r["seq"]) for r in values if r.get("seq") is not None),
                "readings": {r["tag"]: round(float(r["value"]), 4) for r in values},
                "commands": commands, "interlock": bool(st.get(("PLC-01", "interlock"))),
                "mode": st.get(("PLC-01", "mode")), "maintenance": bool(st.get(("PLC-01", "maintenance"))),
                "field_comm": bool(st.get(("PLC-01", "field_comm"))), "run_state": st.get(("PLC-01", "run_state")),
                "source": "DMZ InfluxDB(OT 원시값 사본)",
                "timestamp_note": "조회 시각이며 센서 측정 시각은 아닙니다. 값은 DMZ 사본의 최근 10초 안 마지막 값입니다."}
    except (OSError, ValueError, KeyError, TypeError):
        return {"status": "unavailable", "error": "DMZ 설비 사본 조회 실패"}


def history(site, device, tags, start_ns, stop_ns):
    if not all(os.environ.get(k) for k in ("INFLUX_USER", "INFLUX_PASSWORD")):
        return {"status": "unavailable", "error": "센서 이력 연결 설정이 없습니다.", "rows": []}
    if not tags:
        return {"status": "missing", "error": "조회할 센서 관계를 확인하지 못했습니다.", "rows": []}
    pattern = "|".join(re.escape(t) for t in tags)
    try:
        rows = dmz_query(f'SELECT "value", "quality", "tag" FROM "process_raw" WHERE site={q(site)} AND device={q(device)} '
                         f'AND "tag" =~ /^({pattern})$/ AND time >= {int(start_ns)} AND time <= {int(stop_ns)} ORDER BY time LIMIT 2001')
        rows = [{"time": r["time"], "tag": r["tag"], "value": float(r["value"]), "quality": r.get("quality", "UNKNOWN")} for r in rows]
        return {"status": "available" if rows else "missing", "rows": rows[:2000],
                "truncated": len(rows) > 2000, "start_ns": str(start_ns), "stop_ns": str(stop_ns),
                "source": "DMZ InfluxDB/process_raw(OT 원시값 사본)", "limit": 2000}
    except (OSError, ValueError, KeyError):
        return {"status": "unavailable", "error": "센서 이력 조회 실패", "rows": []}


@router.get("/incidents/{incident_id}/evidence")
def incident_evidence(incident_id: str):
    detail = get_incident(incident_id)
    incident, events = detail["incident"], detail["events"]
    alarm = incident["alarm"]
    observed_tags = sorted({event["payload"]["tag"] for event in events if event["kind"].startswith("alarm_")})
    try:
        assets = _run_readonly_query("""MATCH (a:Asset)-[:HAS_SENSOR]->(s:Sensor)
            WHERE a.site=$site AND a.device=$device AND s.name IN $tags
            RETURN DISTINCT a.name AS name, a._source_id AS source_id""",
            {"site": alarm["site"], "device": alarm["device"], "tags": observed_tags})
        aids = [asset["source_id"] for asset in assets]
        documents = _run_readonly_query("""MATCH (a:Asset)-[:HAS_PROCEDURE|GOVERNED_BY|DESCRIBED_BY]->(d:Document)
            WHERE a._source_id IN $ids RETURN DISTINCT d.name AS document_id,
            d.content AS content, d.source_path AS source_path, d.source_sha256 AS sha256, d.version AS version""", {"ids": aids})
        sensors = _run_readonly_query("""MATCH (a:Asset) WHERE a._source_id IN $ids
            OPTIONAL MATCH (a)-[:INSTALLED_IN]->(parent:Asset)
            WITH a,parent MATCH (owner:Asset)-[:HAS_SENSOR]->(s:Sensor)
            WHERE owner=a OR owner=parent RETURN DISTINCT s.name AS tag,s.unit AS unit,
            s.lsl AS lsl,s.usl AS usl,s.source_sha256 AS source_sha256""", {"ids": aids})
        graph = {"status": "available", "assets": assets, "documents": documents, "sensors": sensors}
    except Exception:
        graph = {"status": "unavailable", "assets": [], "documents": [], "sensors": [], "error": "설비 관계 조회 실패"}
    graph['lookup_scope'] = {
        'site': alarm['site'], 'device': alarm['device'], 'alarm_tags': observed_tags,
        'asset_selection': 'Assets in this site/device linked by HAS_SENSOR to an alarm tag.',
        'document_selection': 'Documents linked to those matched assets only.',
        'limitation': ('Empty results do not establish that the device or factory has no assets, '
                       'documents or sensors. Unknown tags require checking tag identity and mapping; '
                       'do not assign them to M-101 without evidence.'),
    }
    start = max(1, (incident.get("first_ts") or alarm["ts"]) - 30_000_000_000)
    requested_stop = (incident.get("last_ts") or alarm["ts"]) + 15_000_000_000
    stop = min(requested_stop, start + 300_000_000_000)
    readings = history(alarm["site"], alarm["device"], [s["tag"] for s in graph["sensors"]], start, stop)
    now = time.time_ns()
    current = history(alarm["site"], alarm["device"], [s["tag"] for s in graph["sensors"]], now-30_000_000_000, now)
    return {"incident_id": incident_id, "revision": incident["review_revision"],
            "observation_revision": incident["revision"], "graph": graph,
            "history": readings, "current_history": current, "window_capped": stop < requested_stop,
            "notice": "근거 조회 결과이며 AI 진단 또는 조치 승인이 아닙니다."}
