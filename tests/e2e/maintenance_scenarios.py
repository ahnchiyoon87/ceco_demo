#!/usr/bin/env python3
"""[측정 도구 — 솔루션 부품 아님] 정비 시나리오 실제 경로 시험: 이상 발생 → 탐지·사건 → 자동 AI 분석(실제 LLM) → 조치 카드
→ (반려·재분석) → 승인 → 정비 계획 실행(PLC 작업 요청·가상 정비팀) → 회복 판정 → 작업 보고서.

    PYTHONUTF8=1 python tests/e2e/maintenance_scenarios.py s1            # 시나리오 1 (스트레이너 막힘)
    PYTHONUTF8=1 python tests/e2e/maintenance_scenarios.py s2 --reject-first "반려 사유"
    PYTHONUTF8=1 python tests/e2e/maintenance_scenarios.py s2m           # 원인 불일치 훈련(시험용 대응안, AI 생성 아님)

시나리오: s1 strainer_fouling · s1v jacket_fouling · s2 bearing_wear · s2v shaft_misalignment · s3 pt_drift · s3v outlet_valve_stick
운전원 몫(인터록 리셋)은 FUXA 운전원 길(…/cmd/operator)로 사람 대신 누른다 — 화면에서 사람이 하는 일과 같은 길이다.
원출력은 experiments/MAINT-SCN/ 에 남는다. LLM 호출이 들어가므로 필요한 시나리오만 돌린다.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import verify as V  # noqa: E402  (계정·포트·운전원 명령 도우미)

AI = f"http://localhost:{V.ENV['PORT_AI_KNOWLEDGE']}"
OUT = V.ROOT / "experiments" / "MAINT-SCN"
SCENARIOS = {
    "s1": ("strainer_fouling", "thermal", "FM-CW-STRAINER-CLOG"),
    "s1v": ("jacket_fouling", "thermal", "FM-JACKET-FOULING"),
    "s2": ("bearing_wear", "mixer", "FM-MIXER-BEARING-WEAR"),
    "s2v": ("shaft_misalignment", "mixer", "FM-MIXER-SHAFT-MISALIGNMENT"),
    "s3": ("pt_drift", "pressure", "FM-PT101-DRIFT"),
    "s3v": ("outlet_valve_stick", "pressure", "FM-OUTLET-RESTRICTION"),
}


def api(path, body=None, method=None, timeout=30):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(AI + path, data=data, method=method or ("POST" if body is not None else "GET"),
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        return {"_error": e.code, "detail": json.load(e) if e.headers.get("content-type", "").startswith("application/json") else e.read().decode()}


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def plant():
    return V.get(V.SIM + "/state", headers=V.SIM_AUTH)


def prepare():
    """정상 운전으로: 고장·열화 초기화, REMOTE_AUTO, 정비 모드 해제, 인터록 리셋, 구동기 켜기."""
    V.post(V.SIM + "/fault/clear", {}, headers=V.SIM_AUTH)
    if V.plc_status("maintenance") is True:
        V.post(f"http://localhost:{V.ENV['PORT_FIELD_PANEL']}/panel", {"action": "maintenance_release"},
               headers={"Authorization": "Basic " + __import__("base64").b64encode(
                   f"{V.ENV['FIELD_PANEL_USER']}:{V.ENV['FIELD_PANEL_PASSWORD']}".encode()).decode()})
        time.sleep(2)
    # 운전원 기동 명령은 REMOTE_MANUAL 에서만 받는다(REMOTE_AUTO 에서는 PLC 가 MODE 로 거부 — 설계).
    # 앞선 계획이 설비를 정지 상태로 인계했을 수 있으므로 수동 모드에서 기동·확인한 뒤 자동으로 바꾼다.
    V.operator_cmd("PLC-01", "mode", 1)
    time.sleep(1)
    if V.plc_status("interlock") is True:
        V.recover_interlock()
    for _ in range(3):
        for asset in ("P-101", "M-101"):
            V.operator_cmd(asset, "run", 1)
        V.operator_cmd("HX-102", "enable", 1)
        time.sleep(3)
        r = plant()["readings"]
        if r["IT-102"] > 1.0 and r["FT-101"] > 1.0:
            break
    else:
        raise SystemExit(f"설비를 운전 상태로 되돌리지 못했습니다(IT-102 {r['IT-102']}, FT-101 {r['FT-101']}).")
    V.operator_cmd("PLC-01", "mode", 2)
    time.sleep(1)
    quiet_since = time.time()
    end = time.time() + 180
    while time.time() < end:
        busy = [i for i in api("/api/operations/incidents").get("items", [])
                if (i.get("last_ts") or 0) / 1e9 > time.time() - 35]
        if busy:
            quiet_since = time.time()
        elif time.time() - quiet_since > 35:
            break
        time.sleep(3)
    r = plant()["readings"]
    log(f"정상 운전 확인: TT-101 {r['TT-101']:.1f} · VT-101 {r['VT-101']:.2f} · PT-101 {r['PT-101']:.2f} · FT-103 {r['FT-103']:.1f}")


def wait_incident(group, since, timeout=90):
    """이상 발생 뒤 한계 이탈 경보(상·하한·CEP)가 붙은 그 묶음의 사건. 직전 과도 신호로 먼저 생긴 사건에 합쳐질 수 있어
    생성 시각이 아니라 경보 시각으로 찾는다."""
    end = time.time() + timeout
    while time.time() < end:
        for i in api("/api/operations/incidents").get("items", []):
            if group not in (i.get("correlation_key") or "") or i["status"] in ("resolved", "rejected", "closed"):
                continue
            if (i.get("last_ts") or 0) / 1e9 < since:
                continue
            events = api(f"/api/operations/incidents/{i['id']}").get("events", [])
            if any(e["kind"].startswith("alarm_") and e["payload"]["alert_type"] in ("THRESHOLD_USL", "THRESHOLD_LSL", "CEP_BEARING")
                   and e["payload"]["ts"] / 1e9 >= since - 1 for e in events):
                return i
        time.sleep(2)
    raise SystemExit(f"한계 이탈 사건이 {timeout}초 안에 생기지 않았습니다({group}).")


def wait_run(incident_id, not_ids=(), timeout=420, since=0.0):
    """이 시나리오에서 시작된(since 뒤) 분석의 최종 결과. 실패하면 자동 재분석(새 경보 구성)이 이어질 수 있어
    40초 더 기다려 새 실행이 없을 때만 실패로 본다."""
    end = time.time() + timeout
    failed_at = None
    while time.time() < end:
        runs = [r for r in api(f"/api/operations/incidents/{incident_id}/analysis").get("items", [])
                if r["id"] not in not_ids and datetime.fromisoformat(r["created_at"]).timestamp() >= since - 1]
        if runs and runs[0]["status"] in ("awaiting_review", "needs_evidence", "finished"):
            return runs[0]
        if runs and runs[0]["status"] in ("failed", "interrupted"):
            failed_at = failed_at or time.time()
            if time.time() - failed_at > 40:
                return runs[0]
            log(f"   분석 실패({runs[0].get('error')}) — 자동 재분석 대기")
        else:
            failed_at = None
        time.sleep(3)
    raise SystemExit("AI 분석이 시간 안에 끝나지 않았습니다.")


def proposals(incident_id):
    return api(f"/api/operations/incidents/{incident_id}/proposals").get("items", [])


def card(p):
    plan, body = p.get("plan") or {}, p["body"]
    d = (plan.get("evaluation") or {}).get("decisions", [{}])[0]
    log(f"조치 카드: {body['action']} · 대안 {body.get('option_id')} · 권고 {plan.get('recommended')} · 순위 {plan.get('rank')}")
    for c in body.get("cause_assessment", []):
        log(f"   원인 {c['failure_mode']:<30} {c['status']:<14} {c['evidence'][:90]}")
    for o in d.get("options", []):
        log(f"   대안 {o['option_id']:<26} 합계 {o['total']!s:>8} 자격 {o['eligible']!s:<5} 제외 {o['excluded']!s:<5} {(o['rules'] or [{}])[0].get('reason', '')}")
    for f in d.get("flips", [])[:3]:
        log(f"   뒤집힘 {f['fact']} {f['current']} → {f['flip_value']} 이면 {f['new_recommendation']}")


def follow(p, timeout=420):
    """실행을 지켜본다. 운전원 몫(인터록 리셋)이 오면 FUXA 운전원 길로 누른다."""
    end, seen = time.time() + timeout, {}
    while time.time() < end:
        cur = next(x for x in proposals(p["incident_id"]) if x["id"] == p["id"])
        ps = (cur.get("result") or {}).get("plan_state") or {}
        for s in ps.get("steps", []):
            key = (s["order"], s.get("status"))
            if key not in seen:
                seen[key] = True
                log(f"   단계 {s['order']} [{s['kind']}] {s['say']} → {s.get('status')}" + (f" · 소견: {s['finding']}" if s.get("finding") else "")
                    + (f" · {s['reason']}" if s.get("reason") and s.get("status") in ("failed", "no_fault") else ""))
            if s["kind"] == "operator" and s.get("status") == "running" and V.plc_status("interlock") is True:
                V.operator_cmd("PLC-01", "interlock_reset", 1)
        if ps.get("phase") == "verify" and ps.get("verify"):
            v = ps["verify"]
            if int(v["held_s"]) % 10 == 0:
                log(f"   회복 관측 유지 {v['held_s']}s · {[(r['criterion'], r['ok']) for r in (v.get('last') or {}).get('results', [])]}")
        if cur["status"] in ("resolved", "unresolved"):
            return cur
        time.sleep(2)
    raise SystemExit("정비 계획이 시간 안에 끝나지 않았습니다.")


def approve(run, note):
    r = api(f"/api/operations/analysis/{run['id']}/decision", {"decision": "approve", "note": note})
    if "_error" in r:
        raise SystemExit(f"승인 거부: {r}")


def reject(run, note):
    r = api(f"/api/operations/analysis/{run['id']}/decision", {"decision": "reject", "note": note})
    if "_error" in r:
        raise SystemExit(f"반려 실패: {r}")
    time.sleep(4)


def report(p):
    rep = (p.get("result") or {}).get("report") or {}
    log(f"작업 보고서 {rep.get('work_order_id')}: {rep.get('headline')} — {rep.get('reason')}")
    for f in rep.get("findings", []):
        log(f"   소견 {f['say']}: {f['finding']}")
    for r in rep.get("before_after", []):
        log(f"   {r['tag']}: {r['before']} → {r['after']}")
    k = rep.get("kpi", {})
    log(f"   KPI 예상 {k.get('predicted')} · 실적 {k.get('actual')}")
    log(f"   다음: {rep.get('next')}")
    return rep


def run(key, reject_first=None):
    fault, group, truth = SCENARIOS["s2v" if key == "s2m" else key]
    record = {"scenario": key, "fault": fault, "truth": truth, "started": time.time(), "steps": []}
    prepare()
    t0 = time.time()
    V.post(V.SIM + "/fault", {"scenario": fault}, headers=V.SIM_AUTH)
    log(f"이상 발생: {fault} (정답 {truth}, AI 에는 주지 않음)")
    inc = wait_incident(group, t0)
    log(f"사건 접수 {inc['id'][:8]} · {inc['correlation_key']} · +{time.time() - t0:.1f}s")
    if key == "s2m":
        return mismatch_drill(inc, record, t0)
    run1 = wait_run(inc["id"], since=t0)
    log(f"AI 분석 {run1['status']} · +{time.time() - t0:.1f}s")
    record["runs"] = [run1]
    if run1["status"] != "awaiting_review":
        record["result"] = run1
        return save(record)
    p = proposals(inc["id"])[0]
    card(p)
    record["first_proposal"] = p
    if reject_first:
        reject(run1, reject_first)
        log(f"반려: {reject_first}")
        r = api(f"/api/operations/incidents/{inc['id']}/analyze", {})
        run1b = wait_run(inc["id"], not_ids={run1["id"]})
        log(f"재분석 {run1b['status']}")
        record["runs"].append(run1b)
        if run1b["status"] != "awaiting_review":
            record["result"] = run1b
            return save(record)
        p = next(x for x in proposals(inc["id"]) if x["status"] == "pending")
        card(p)
        log("재분석 요약(반려 사유 대응): " + p["body"]["summary"].split("[대안 비교]")[-1][:400])
        run1 = run1b
    if p["body"]["action"] != "maintenance_plan":
        log("정비 계획이 아닌 결과 — 승인하지 않고 종료")
        record["result"] = p
        return save(record)
    approve(run1, "근거·손익 확인, 계획대로 진행")
    log(f"승인 · +{time.time() - t0:.1f}s")
    done = follow(p)
    record["final"] = done
    record["report"] = report(done)
    record["elapsed_s"] = round(time.time() - t0, 1)
    record["chosen_matches_truth"] = truth in (done.get("plan") or {}).get("treats", [])
    return save(record)


def mismatch_drill(inc, record, t0):
    """원인 불일치 가지: 정렬 불량인데 베어링 교체 계획을 승인한 경우(시험용 대응안 — AI 생성 아님).
    현장 소견 '베어링 정상'으로 계획이 멈추고, 이어서 AI 재분석이 소견을 근거로 다른 대안을 고르는지 본다."""
    run0 = wait_run(inc["id"], since=t0)  # 자동 분석은 그대로 돌게 두고, 결과는 기록만
    record["auto_run"] = run0
    if run0["status"] == "awaiting_review":
        reject(run0, "훈련: 원인 불일치 가지를 확인하기 위해 반려")
    code = f"""
import json
from uuid import UUID
from backend.src.modules.operations.actions import Proposal, create_proposal, decide, Decision
from backend.src.modules.operations.evidence import incident_evidence
from pydantic import create_model
from backend.src.modules.operations.agent import CauseAssessment
ev = incident_evidence('{inc['id']}')
M = create_model('DrillProposal', __base__=Proposal, cause_assessment=(list[CauseAssessment], ...))
body = M(expected_revision=ev['revision'], action='maintenance_plan', option_id='OPT-BEARING-NOW',
         summary='[관측] 훈련용 대응안(측정 도구). AI 진단이 아니다 — 원인 불일치 가지를 확인한다.',
         citations=['AR100-AGITATOR-MAINT'], uncertainties=['훈련: 일부러 베어링으로 가정'],
         cause_assessment=[{{'failure_mode':'FM-MIXER-BEARING-WEAR','status':'supported','evidence':'훈련 가정(실제 관측 아님)'}},
                           {{'failure_mode':'FM-MIXER-SHAFT-MISALIGNMENT','status':'refuted','evidence':'훈련 가정(실제 관측 아님)'}}])
p = create_proposal(UUID('{inc['id']}'), body, ev, origin='drill-test')
r = decide(p['id'], Decision(decision='approve', note='훈련: 원인 불일치 가지 확인'))
print(json.dumps({{'id': str(p['id']), 'status': r['proposal']['status']}}))
"""
    out = V.sh("docker", "exec", "-i", V.c("knowledge"), "python", "-c", code, timeout=120)
    created = json.loads(out.strip().splitlines()[-1])
    log(f"훈련 대응안 승인 {created}")
    p = next(x for x in proposals(inc["id"]) if x["id"] == created["id"])
    done = follow(p)
    record["drill_final"] = done
    record["drill_report"] = report(done)
    api(f"/api/operations/incidents/{inc['id']}/analyze", {})
    run2 = wait_run(inc["id"], not_ids={run0["id"]})
    log(f"소견 반영 재분석 {run2['status']}")
    record["rerun"] = run2
    if run2["status"] == "awaiting_review":
        p2 = next(x for x in proposals(inc["id"]) if x["status"] == "pending")
        card(p2)
        approve(run2, "현장 소견 반영 계획 승인")
        done2 = follow(p2)
        record["final"] = done2
        record["report"] = report(done2)
    record["elapsed_s"] = round(time.time() - t0, 1)
    return save(record)


def save(record):
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"{record['scenario']}-{datetime.now():%Y%m%d-%H%M%S}.json"
    path.write_text(json.dumps(record, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    log(f"원출력 저장 {path.relative_to(V.ROOT)}")
    V.post(V.SIM + "/fault/clear", {}, headers=V.SIM_AUTH)
    return record


def single_instance():
    """한 번에 하나만 돈다: 두 시험이 겹치면 서로의 고장 주입·승인이 섞여 결과가 무효다(10-06 오염 사고)."""
    OUT.mkdir(parents=True, exist_ok=True)
    fh = open(OUT / ".lock", "a+")
    try:
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(fh.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(fh, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError:
        raise SystemExit("다른 정비 시나리오 시험이 돌고 있습니다. 끝난 뒤 다시 실행하세요.")
    return fh


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("scenarios", nargs="+", choices=[*SCENARIOS, "s2m"], help="차례로 돈다(한 프로세스)")
    ap.add_argument("--reject-first", default=None, help="s2 에만: 첫 카드를 이 사유로 반려")
    a = ap.parse_args()
    lock = single_instance()
    for sc in a.scenarios:
        print(f"######## {sc} {time.strftime('%H:%M:%S')}", flush=True)
        try:
            run(sc, a.reject_first if sc == "s2" else None)
            print(f"######## {sc} exit 0", flush=True)
        except SystemExit as exc:
            print(f"######## {sc} 실패: {exc}", flush=True)
            V.post(V.SIM + "/fault/clear", {}, headers=V.SIM_AUTH)
