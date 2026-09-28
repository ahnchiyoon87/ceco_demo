"""운영 감시 비교 ② 측정 클라이언트 (EXP-MON, 측정 도구).

    python /repo/harness/monbench/mon_stage2.py check   --profile prom315     # 설정 동등성·대상 up·규칙 적재·합성 조건 발화→AM→웹훅
    python /repo/harness/monbench/mon_stage2.py e11     --profile prom315     # 호스트가 mon-victim 을 멈춘 뒤: 탐지까지 초
    python /repo/harness/monbench/mon_stage2.py resolve --profile prom315     # 호스트가 다시 띄운 뒤: 해소까지 초
    python /repo/harness/monbench/mon_stage2.py detector --profile prom315    # 호스트가 mon-detector 의 실행 잡 수를 4→0: DetectorJobsZero 탐지까지 초
    python /repo/harness/monbench/mon_stage2.py detector_resolve --profile prom315
모드: MON_MODE=standalone(벤치 합성 대상만) | rot(V1 과 같은 대상, compose.rot.yml). 규칙: MON_PROM_CFG 의 v1(V1 그대로) | v2(+rules.v2.yml).
    python /repo/harness/monbench/mon_stage2.py exporters --profile prom315   # cAdvisor v0.60.6·kafka-exporter v1.10.0 가 V1 이 쓰는 지표를 내는가
    python /repo/harness/monbench/mon_stage2.py grafana --profile grafana13   # V1 대시보드 4개 패널 질의가 전부 성공하는가
    python /repo/harness/monbench/mon_stage2.py summarize --profile prom315
V1 이 쓰는 지표 = prometheus/rules.yml 식 + grafana/dashboards/04-infra.json 식(아래 USED_METRICS).
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import pathlib
import sys
import time

import requests
import yaml

sys.path.insert(0, "/repo/harness/benchcommon")
import telemetry as T  # noqa: E402

RAW = pathlib.Path("/experiments/EXP-MON/raw")
PROM = "http://mon-prom:9090"
AM = "http://mon-am:9093"
VMALERT = "http://vmalert:8880"
V1_PROM = "http://prometheus:9090"        # rot 스택의 V1 Prometheus(읽기만) — 같은 대상을 V1 이 어떻게 보는지 대조
USED_METRICS = {
    "cadvisor": ["container_cpu_usage_seconds_total", "container_memory_working_set_bytes"],
    "kafka": ["kafka_consumergroup_lag", "kafka_topic_partition_current_offset"],
}
V1_RULES = ["KafkaConsumerLagHigh", "FlinkCheckpointFailing", "FlinkJobRestarting", "EMQXDisconnectSpike",
            "TelemetryIngestStalled", "PipelineServiceDown"]


def save(a, phase, res):
    RAW.mkdir(parents=True, exist_ok=True)
    (RAW / f"{a.profile}_{phase}.json").write_text(json.dumps(res, ensure_ascii=False, indent=2))
    print(json.dumps(res, ensure_ascii=False)[:1500])


def get(url, **kw):
    r = requests.get(url, timeout=20, **kw)
    r.raise_for_status()
    return r.json()


def wait(fn, timeout, step=2):
    t0 = time.time()
    while time.time() - t0 < timeout:
        try:
            v = fn()
            if v:
                return v, round(time.time() - t0, 1)
        except Exception:
            pass
        time.sleep(step)
    return None, None


def parity():
    """V1 prometheus.yml 과 벤치 설정의 V1 잡이 같은지(이름·대상·경로)."""
    v1 = yaml.safe_load(open("/repo/prometheus/prometheus.yml", encoding="utf-8"))
    cfg = os.environ.get("MON_PROM_CFG", "prometheus.standalone.v1.yml")
    b = yaml.safe_load(open(f"/repo/harness/monbench/conf/{cfg}", encoding="utf-8"))
    norm = lambda j: (j["job_name"], j.get("metrics_path", "/metrics"),
                      tuple(sorted(t for sc in j.get("static_configs", []) for t in sc["targets"])))
    v1j = {norm(j) for j in v1["scrape_configs"]}
    bj = {norm(j) for j in b["scrape_configs"]}
    rules_v1_only = b.get("rule_files") == v1.get("rule_files")
    mode = os.environ.get("MON_MODE", "standalone")
    return {"mode": mode, "config": cfg, "v1_jobs": len(v1j), "missing_in_bench": sorted(map(str, v1j - bj)),
            "same": (v1j <= bj) if mode == "rot" else None,
            "standalone_note": None if mode == "rot" else "단독 모드: V1 대상 없음(설계상) — 대상 동등성은 rot 모드에서",
            "global_same": v1["global"] == b["global"], "rules_exactly_v1": rules_v1_only}


def alerts_api(a):
    return f"{VMALERT}/api/v1/alerts" if a.profile.startswith("vm") else f"{PROM}/api/v1/alerts"


def firing(a, alertname, job):
    for al in get(alerts_api(a))["data"]["alerts"]:
        lb = al.get("labels", {})
        if lb.get("alertname") == alertname and lb.get("job") == job and al.get("state") == "firing":
            return True
    return False


def check(a):
    t_start = time.time()
    res = {"profile": a.profile, "config_parity": parity()}
    # 대상 up (벤치 후보 vs 같은 순간 V1 Prometheus)
    time.sleep(a.settle)
    tg = get(f"{PROM}/api/v1/targets")["data"]["activeTargets"]
    res["targets"] = {f'{t["labels"].get("job")}|{t["labels"].get("instance")}': t["health"] for t in tg}
    try:
        if os.environ.get("MON_MODE", "standalone") != "rot":
            raise RuntimeError("단독 모드 — V1 Prometheus 대조 안 함")
        v1 = get(f"{V1_PROM}/api/v1/targets")["data"]["activeTargets"]
        res["v1_targets_same_moment"] = {f'{t["labels"].get("job")}|{t["labels"].get("instance")}': t["health"] for t in v1}
        same = [k for k, v in res["v1_targets_same_moment"].items() if res["targets"].get(k) == v]
        res["targets_agree_with_v1"] = {"agree": len(same), "of": len(res["v1_targets_same_moment"])}
    except Exception as e:
        res["v1_targets_same_moment"] = {"error": repr(e)}
    # 규칙 적재
    rurl = f"{VMALERT}/api/v1/rules" if a.profile.startswith("vm") else f"{PROM}/api/v1/rules"
    groups = get(rurl)["data"]["groups"]
    rules = {r["name"]: r.get("health", r.get("lastError") or "ok") for g in groups for r in g["rules"]}
    res["rules"] = {"loaded": sorted(rules), "all_v1_loaded": all(n in rules for n in V1_RULES),
                    "health": rules}
    # 합성 조건 발화(up==0, for:1m) → Alertmanager → 웹훅
    ok, secs = wait(lambda: firing(a, "PipelineServiceDown", "synthetic-down"), 240)
    res["synthetic_fire"] = {"fired": bool(ok), "seconds_after_start": round(time.time() - t_start, 1) if ok else None}
    am_ok, _ = wait(lambda: any(x["labels"].get("job") == "synthetic-down" for x in get(f"{AM}/api/v2/alerts")), 60)
    res["alertmanager_received"] = bool(am_ok)
    sink = RAW / f"sink_{a.profile}.jsonl"
    hook, _ = wait(lambda: sink.exists() and "synthetic-down" in sink.read_text(encoding="utf-8"), 60)
    res["webhook_delivered"] = bool(hook)
    res["marks"] = {"check_start_epoch": t_start, "check_end_epoch": time.time()}
    res["pass_stage2_core"] = (res["config_parity"]["same"] is not False and res["rules"]["all_v1_loaded"]
                               and res["synthetic_fire"]["fired"] and res["alertmanager_received"] and res["webhook_delivered"])
    save(a, "check", res)


def e11(a):
    stop_epoch = float((RAW / f"{a.profile}_victim_stopped").read_text())
    ok, _ = wait(lambda: firing(a, "PipelineServiceDown", "victim"), 240)
    res = {"container_kill_detected": bool(ok), "seconds_from_stop": round(time.time() - stop_epoch, 1) if ok else None,
           "rule": "PipelineServiceDown(up==0, for:1m)"}
    save(a, "e11", res)


def resolve(a):
    start_epoch = float((RAW / f"{a.profile}_victim_started").read_text())
    ok, _ = wait(lambda: not firing(a, "PipelineServiceDown", "victim"), 240)
    save(a, "resolve", {"resolved": ok is not None, "seconds_from_start": round(time.time() - start_epoch, 1) if ok else None})


def detector(a):
    """E11 두 번째 조건: 탐지기(Flink 잡) 정지. V1 규칙에는 식이 없어 v1 설정은 탐지 못 하는 것이 예상(측정으로 확정)."""
    stop_epoch = float((RAW / f"{a.profile}_detector_zeroed").read_text())
    ok, _ = wait(lambda: any(al["labels"].get("alertname") == "DetectorJobsZero" and al["labels"].get("instance") == "mon-detector:8080"
                             and al.get("state") == "firing" for al in get(alerts_api(a))["data"]["alerts"]), a.detector_timeout)
    real = None
    if os.environ.get("MON_MODE") == "rot":     # 실제 rot Flink 잡 수(읽기만) — 지금 0개인지 관측 기록
        try:
            real = get(f"{PROM}/api/v1/query", params={"query": "flink_jobmanager_numRunningJobs"})["data"]["result"]
        except Exception as e:
            real = repr(e)[:200]
    save(a, "detector", {"detector_stop_detected": bool(ok), "seconds_from_zero": round(time.time() - stop_epoch, 1) if ok else None,
                         "timeout_s": a.detector_timeout, "ruleset": os.environ.get("MON_PROM_CFG"),
                         "rot_flink_running_jobs_now": real})


def detector_resolve(a):
    t = float((RAW / f"{a.profile}_detector_restored").read_text())
    ok, _ = wait(lambda: not any(al["labels"].get("alertname") == "DetectorJobsZero" and al["labels"].get("instance") == "mon-detector:8080"
                                 and al.get("state") == "firing" for al in get(alerts_api(a))["data"]["alerts"]), 180)
    save(a, "detector_resolve", {"resolved": ok is not None, "seconds_from_restore": round(time.time() - t, 1) if ok else None})


def exporters(a):
    res = {}
    for old, new, kind in (("cadvisor", "cadvisor-next", "cadvisor"), ("kafka", "kafka-next", "kafka")):
        row = {}
        for m in USED_METRICS[kind]:
            cnt = {}
            for job in (old, new):
                r = get(f"{PROM}/api/v1/query", params={"query": f'count({m}{{job="{job}"}})'})["data"]["result"]
                cnt[job] = int(float(r[0]["value"][1])) if r else 0
            row[m] = cnt
        res[kind] = row
    res["pass"] = all(v[f"{k}-next" if k == "cadvisor" else "kafka-next"] > 0 for k, rows in res.items() for v in rows.values())
    save(a, "exporters", res)


def grafana(a):
    base, auth = "http://grafana:3000", ("admin", "bench-admin")
    for host in ("http://grafana13:3000", "http://grafana-v1:3000"):
        try:
            requests.get(host + "/api/health", timeout=5)
            base = host
            break
        except Exception:
            continue
    health, secs = wait(lambda: get(base + "/api/health").get("database") == "ok", 180)
    dash = get(base + "/api/search", params={"type": "dash-db"}, auth=auth)
    panels, ok_n = [], 0
    now = int(time.time() * 1000)
    for d in dash:
        j = get(base + f"/api/dashboards/uid/{d['uid']}", auth=auth)["dashboard"]
        for p in j.get("panels", []):
            for t in p.get("targets", []):
                ds = t.get("datasource") or p.get("datasource") or {}
                q = dict(t, refId=t.get("refId", "A"), datasource=ds)
                q.setdefault("query", t.get("query"))
                body = {"queries": [q], "from": str(now - 3600_000), "to": str(now)}
                r = requests.post(base + "/api/ds/query", json=body, auth=auth, timeout=60)
                st = r.status_code
                frames = 0
                err = None
                try:
                    jr = r.json()
                    for ref in jr.get("results", {}).values():
                        err = ref.get("error") or err
                        frames += len(ref.get("frames", []))
                except Exception as e:
                    err = repr(e)
                good = st == 200 and not err
                ok_n += good
                panels.append({"dashboard": j.get("title"), "panel": p.get("title"), "status": st, "frames": frames,
                               "error": (err or "")[:200], "ok": good})
    ver = get(base + "/api/health").get("version")
    save(a, "grafana", {"grafana": base, "version": ver, "dashboards": len(dash), "panel_queries": len(panels),
                        "ok": ok_n, "panels": panels, "startup_s": secs})


def summarize(a):
    runs = {f.stem[len(a.profile) + 1:]: json.loads(f.read_text()) for f in sorted(RAW.glob(f"{a.profile}_*.json"))}
    stats = {}
    for f in RAW.glob(f"stats_{a.profile}.csv"):
        by = {}
        for r in csv.DictReader(open(f)):
            if "client" in r["name"] or "sink" in r["name"] or "victim" in r["name"]:
                continue
            try:
                by.setdefault(r["name"], {"cpu": [], "mem": []})
                by[r["name"]]["cpu"].append(float(r["cpu_pct"]))
                by[r["name"]]["mem"].append(float(r["mem_mib"]))
            except ValueError:
                pass
        stats = {n: {"cpu_pct_median": T.pct(v["cpu"], .5), "mem_mib_median": T.pct(v["mem"], .5),
                     "mem_mib_max": T.pct(v["mem"], 1)} for n, v in by.items()}
    img = RAW / f"images_{a.profile}.txt"
    chk = runs.get("check", {})
    e11_both = runs.get("e11", {}).get("container_kill_detected") and runs.get("detector", {}).get("detector_stop_detected")
    verdict = "미실행" if not runs else ("통과" if chk.get("pass_stage2_core") and e11_both
                                     else "탈락 또는 미완(세부는 runs — E11 은 컨테이너 정지·탐지기 정지 둘 다 필요)")
    if a.profile.startswith("grafana"):
        g = runs.get("grafana", {})
        verdict = "통과" if g and g.get("ok") == g.get("panel_queries") else "탈락 또는 미완(패널별 error)"
    res = {"exp": "EXP-MON", "stage": 2, "profile": a.profile, "runs": runs, "resources": stats,
           "images": img.read_text().splitlines() if img.exists() else None, "stage2_verdict": verdict,
           "mode": os.environ.get("MON_MODE"), "ruleset": os.environ.get("MON_PROM_CFG"),
           "note": "E11 = 컨테이너 정지(victim) + 탐지기 정지(detector-sim 잡 0개). V1 규칙엔 후자 식이 없고 V2 후보 rules.v2.yml 이 추가."}
    p = pathlib.Path(f"/experiments/EXP-MON/stage2_{a.profile}.json")   # profile = <프로파일>.<모드>
    p.write_text(json.dumps(res, ensure_ascii=False, indent=2))
    print(f"wrote {p} verdict={verdict}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["check", "e11", "resolve", "detector", "detector_resolve", "exporters", "grafana", "summarize"])
    ap.add_argument("--detector-timeout", type=int, default=150)
    ap.add_argument("--profile", required=True)
    ap.add_argument("--settle", type=int, default=45)
    a = ap.parse_args()
    globals()[a.cmd](a)


if __name__ == "__main__":
    main()
