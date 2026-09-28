"""Read-only evidence adapters. Never expose injected-fault ground truth to AI."""
import csv
import io
import json
import os
import time
from datetime import datetime, timezone
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from fastapi import APIRouter

from .api import get_incident
from ..ontology.tools import _run_readonly_query

router = APIRouter(prefix="/api/operations", tags=["manufacturing-evidence"])


@router.get("/plant")
def live_state():
    try:
        with urlopen(os.environ.get("SCADA_STATE_URL", "http://host.docker.internal:27080/state"), timeout=5) as response:
            state = json.load(response)
        return {"status": "available", "retrieved_at": datetime.now(timezone.utc).isoformat(),
                "site": state["site"], "device": state["device"], "seq": state["seq"],
                "readings": state["readings"], "commands": state["commands"], "interlock": state["interlock"],
                "timestamp_note": "조회 시각이며 센서 측정 시각은 아닙니다."}
    except (OSError, ValueError, KeyError):
        return {"status": "unavailable", "error": "시뮬레이터 상태 조회 실패"}


def history(site, device, tags, start_ns, stop_ns):
    token, org, bucket = (os.environ.get(key, "") for key in ("INFLUX_TOKEN", "INFLUX_ORG", "INFLUX_BUCKET"))
    if not all((token, org, bucket)):
        return {"status": "unavailable", "error": "센서 이력 연결 설정이 없습니다.", "rows": []}
    if not tags:
        return {"status": "missing", "error": "조회할 센서 관계를 확인하지 못했습니다.", "rows": []}
    quote = lambda value: json.dumps(value, ensure_ascii=False)
    query = (f'from(bucket:{quote(bucket)}) |> range(start:time(v:{start_ns}), stop:time(v:{stop_ns})) '
             f'|> filter(fn:(r)=>r._measurement=="process_raw" and r._field=="value" '
             f'and r.site=={quote(site)} and r.device=={quote(device)} '
             f'and contains(value:r.tag,set:{quote(tags)})) '
             '|> group() |> sort(columns:["_time"]) |> limit(n:2001)')
    request = Request(os.environ.get("INFLUX_URL", "http://host.docker.internal:27086") + "/api/v2/query?" + urlencode({"org": org}),
                      data=json.dumps({"query": query, "type": "flux"}).encode(),
                      headers={"Authorization": f"Token {token}", "Content-Type": "application/json", "Accept": "application/csv"})
    try:
        with urlopen(request, timeout=10) as response:
            content = response.read().decode()
        lines = [line for line in content.splitlines() if line and not line.startswith("#")]
        rows = []
        for record in csv.DictReader(lines):
            if record.get("_value") in (None, "_value"):
                continue
            rows.append({"time": record["_time"], "tag": record["tag"],
                         "value": float(record["_value"]), "quality": record.get("quality", "UNKNOWN")})
        return {"status": "available" if rows else "missing", "rows": rows[:2000],
                "truncated": len(rows) > 2000, "start_ns": str(start_ns), "stop_ns": str(stop_ns),
                "source": "InfluxDB/process_raw", "limit": 2000}
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
