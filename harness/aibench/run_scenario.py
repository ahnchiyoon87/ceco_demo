"""EXP-AI 시나리오 1회 실행기(측정 도구, 솔루션 부품 아님). PROTOCOL.md §4 절차.

설비 준비(운전원 조작 API) → 고장 주입(시뮬레이터) → answer-key 의 alarm_trigger 사건 대기 → 분석 요청
→ 결과·도구 기록·대응안 원본 저장 → 고장 해제·원상 복구(냉각으로 온도 복귀) → 알람 조용 35초 대기.
정답(주입 이름)은 에이전트 입력에 넣지 않는다. 결과 파일: experiments/EXP-AI/raw/<run_id>.json

  python harness/aibench/run_scenario.py <arm A|B|C> <SC1_bearing|SC2_heater_stuck|SC3_overpressure> <run_id>
"""
import json, os, subprocess, sys, time, urllib.request, uuid
from datetime import datetime, timezone
from pathlib import Path

import yaml

API = "http://127.0.0.1:38000/api/operations"
SIM = "http://127.0.0.1:37080"
DURATION = {"bearing_wear": 600, "heater_stuck": 2400, "spike": None}  # heater: 71→95°C 에 약 27분(#76)
WAIT_ALARM = {"SC1_bearing": 240, "SC2_heater_stuck": 2400, "SC3_overpressure": 180}
arm, scenario, run_id = sys.argv[1:4]
out = Path(f"experiments/EXP-AI/raw/{run_id}.json")
if out.exists():
    raise SystemExit(f"실행 ID 재사용 금지: {out}")
sc = yaml.safe_load(open("ontology/v2/answer-key.yaml", encoding="utf-8"))["scenarios"][scenario]
log = {"run_id": run_id, "arm": arm, "scenario": scenario, "started_at": datetime.now(timezone.utc).isoformat(), "steps": []}


def call(url, body=None, method=None, timeout=60):
    req = urllib.request.Request(url, None if body is None else json.dumps(body).encode(),
                                 {"Content-Type": "application/json"}, method=method or ("POST" if body is not None else "GET"))
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"http_error": e.code, "body": e.read().decode()[:2000]}


def step(name, **data):
    log["steps"].append({"at": time.time(), "step": name, **data})
    print(f"[{run_id}] {name} {json.dumps(data, ensure_ascii=False)[:300]}", flush=True)


def state():
    return call(SIM + "/state")


def control(target, value):
    return call(API + "/simulation/control", {"request_id": str(uuid.uuid4()), "target": target, "value": value}, timeout=30)


def sql(query):
    cmd = ["docker", "exec", "rot-ai-work-db-1", "psql", "-U", "ar100", "-d", "ar100_work", "-At", "-c", query]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8").stdout.strip()


RELATED = {"SC1_bearing": ["IT-102", "VT-101"], "SC2_heater_stuck": ["TT-101", "TT-102"], "SC3_overpressure": ["PT-101"]}


def quiet_since(seconds):
    """No alarm on this scenario's tags for `seconds` (correlation gap is 30 s). Other groups (e.g. ML) do not merge."""
    tags = ",".join(f"'{t}'" for t in RELATED[scenario])
    last = sql(f"SELECT coalesce(extract(epoch from max(created_at)),0) FROM manufacturing_events WHERE payload->>'tag' IN ({tags})")
    return time.time() - float(last or 0) >= seconds


def save():
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(log, ensure_ascii=False, indent=1, default=str), encoding="utf-8")


s0 = state()
initial = dict(s0["commands"])
step("precheck", active_faults=s0.get("active_faults"), commands=initial, interlock=s0["interlock"])
if s0.get("active_faults"):
    raise SystemExit("고장이 남아 있습니다. 해제 후 다시 실행하세요.")
deadline = time.time() + 300
while not quiet_since(35):
    if time.time() > deadline:
        log["invalid"] = "사전 조용 구간 35초 확보 실패"; save(); raise SystemExit(log["invalid"])
    time.sleep(5)

for target, value in (sc.get("plant_setup") or {}).items():
    step("setup", target=target, result=control(target, value).get("status"))
t0 = time.time()
inj = sc["inject"]["scenario"]
body = {"scenario": inj} | ({"duration_s": DURATION[inj]} if DURATION[inj] else {})
step("inject", response=call(SIM + "/fault", body))

trig = sc["alarm_trigger"]
incident = None
while time.time() - t0 < WAIT_ALARM[scenario]:
    rows = sql(f"""SELECT DISTINCT i.id FROM manufacturing_incidents i JOIN manufacturing_events e ON e.incident_id=i.id
        WHERE i.created_at > to_timestamp({t0 - 5}) AND e.payload->>'tag'='{trig['tag']}' AND e.payload->>'alert_type'='{trig['alert_type']}'""")
    if rows:
        incident = rows.splitlines()[0]
        break
    time.sleep(3)
step("alarm", incident=incident, waited_s=round(time.time() - t0, 1))

if incident:
    time.sleep(3)  # 같은 사건으로 묶일 동반 알람이 도착할 짧은 여유
    delay = float(os.environ.get("ANALYZE_DELAY_S", "0"))  # 보조 변형(#75): 순간 이상이 끝난 뒤 분석
    if delay:
        step("analyze_delay", seconds=delay); time.sleep(delay)
    log["analyze_delay_s"] = delay
    started = call(f"{API}/incidents/{incident}/analyze", {}, timeout=30)
    step("analyze", response={k: started.get(k) for k in ("replayed", "http_error", "body")})
    run = (started.get("run") or {})
    a0 = time.time()
    while run.get("id") and time.time() - a0 < 360:
        rows = call(f"{API}/incidents/{incident}/analysis")["items"]
        run = next((r for r in rows if r["id"] == started["run"]["id"]), run)
        if run["status"] not in ("running", "resuming"):
            break
        time.sleep(3)
    step("analysis_done", status=run.get("status"), seconds=round(time.time() - a0, 1), error=run.get("error"))
    log["analysis_run"] = run
    if run.get("id"):
        log["trace"] = call(f"{API}/analysis/{run['id']}/trace")
    pid = (run.get("result") or {}).get("proposal_id")
    if pid:
        log["proposal"] = json.loads(sql(f"SELECT row_to_json(p) FROM (SELECT id,status,body,origin,created_at FROM manufacturing_proposals WHERE id='{pid}') p") or "null")
    log["incident"] = call(f"{API}/incidents/{incident}")
    log["plant_at_analysis_end"] = state()
else:
    log["invalid"] = "정해진 시간 안에 alarm_trigger 사건이 생기지 않음"

step("clear", response=call(SIM + "/fault/clear", {}))
# 원상 복구: 온도가 높으면 냉각으로 목표 부근까지 내린 뒤 초기 명령으로 되돌린다.
s = state()
if s["readings"]["TT-101"] > s["commands"]["temp_sp_c"] + 3:
    step("restore_cooling_on", result=control("cooler_enable", 1).get("status"))
    r0 = time.time()
    while state()["readings"]["TT-101"] > state()["commands"]["temp_sp_c"] + 3 and time.time() - r0 < 900:
        time.sleep(5)
    step("restore_cooled", seconds=round(time.time() - r0, 1), tt101=state()["readings"]["TT-101"])
now = state()["commands"]
for target in ("cooler_enable", "heater_enable", "agitator_run"):
    if target in initial and now.get(target) != initial[target]:
        step("restore", target=target, result=control(target, int(initial[target])).get("status"))
log["finished_at"] = datetime.now(timezone.utc).isoformat()
save()
print(json.dumps({"run_id": run_id, "incident": incident, "status": (log.get("analysis_run") or {}).get("status"),
                  "action": ((log.get("proposal") or {}).get("body") or {}).get("action"), "invalid": log.get("invalid")}, ensure_ascii=False))
