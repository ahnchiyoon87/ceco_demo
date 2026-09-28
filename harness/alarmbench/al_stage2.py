"""알람 표시·상태(ISA-18.2) 비교 ② 측정 클라이언트 (EXP-ALM, 측정 도구).

    python /repo/harness/alarmbench/al_stage2.py run --profile pgisa|alerta|keep|thingsboard
    python /repo/harness/alarmbench/al_stage2.py summarize --profile alerta

입력은 V1 alerts 레코드 모양(harness/SCHEMA.md §3): {ts, site, device, tag, value, alert_type, severity, detector, detail}.
V1 에는 "복귀(RTN)" 신호가 없다 → 연결 코드가 raw 값이 한계 이하로 돌아온 것을 보고 만든다고 가정하고, 여기서는
같은 키로 {"rtn": true} 사건을 보낸다(갭: V1 에 RTN 생성 경로 추가 필요 — STAGE2.md).

수명주기 시나리오(결과 보기 전 고정 2026-09-29). 각 단계 뒤 관측 상태를 ISA 이름으로 정규화해 기대와 대조(E10 일치율).
  L01 IT-102 THRESHOLD_USL CRITICAL 발생                    → UNACK
  L02 같은 알람 5회 반복                                     → UNACK (알람 1건 유지, 중복 흡수)
  L03 운전원 op-a 확인(사유)                                 → ACKED   (CQ15: 누가·언제)
  L04 복귀                                                   → NORM
  L05 VT-101 CEP_BEARING 발생 → 확인 전 복귀                 → UNACK → RTNUN
  L06 운전원 op-b 확인                                       → NORM
  L07 TT-101 ZSCORE WARNING 발생 → op-a 확인                 → UNACK → ACKED
  L08 같은 알람 CRITICAL 로 악화(재알람)                     → UNACK
  L09 op-a 셸빙 60초(사유)                                   → SHLVD   (CQ08 대응: 누가·언제·왜)
  L10 셸빙 중 같은 알람 재발생                               → SHLVD (표시·경보 안 함)
  L11 만료 후(65초, 필요 시 만료 처리 호출)                  → UNACK (조건 아직 이상)
  L12 감사: 세 알람의 이력이 모든 전이를 사람·시각과 함께 담는가
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import time
import uuid
from datetime import datetime, timedelta, timezone

import requests

RAW = pathlib.Path("/experiments/EXP-ALM/raw")
SITE, DEV = "AR-100", "reactor-line-01"


def msg(tag, alert_type, severity, value, detector="TIER1_RULE"):
    return {"ts": time.time_ns(), "site": SITE, "device": DEV, "tag": tag, "value": value, "alert_type": alert_type,
            "severity": severity, "detector": detector, "detail": f"{tag} = {value:.3f} / bench"}


def key(m):
    return f'{m["site"]}|{m["device"]}|{m["tag"]}|{m["alert_type"]}'


# ─────────────────────────────── 어댑터 ───────────────────────────────
class PgIsa:
    """PostgreSQL 상태 테이블 + 함수(harness/alarmbench/pgisa/isa_pg.sql). 업무 DB 이름 ar100_work, 스키마 isa."""
    name = "pgisa"
    shelve_supported = True

    def __init__(self):
        import psycopg
        self.c = psycopg.connect("host=alarm-db user=postgres password=bench dbname=ar100_work options=-csearch_path=isa", autocommit=True)
        self.c.execute(open("/repo/harness/alarmbench/pgisa/isa_pg.sql", encoding="utf-8").read())

    def raise_(self, m):
        return self.c.execute("SELECT alarm_raise(%s::jsonb)", (json.dumps(m),)).fetchone()[0]

    def rtn(self, m):
        return self.c.execute("SELECT alarm_rtn(%s)", (key(m),)).fetchone()[0]

    def ack(self, m, who, why):
        return self.c.execute("SELECT alarm_ack(%s,%s,%s)", (key(m), who, why)).fetchone()[0]

    def shelve(self, m, who, secs, why):
        return self.c.execute("SELECT alarm_shelve(%s,%s,%s,%s)", (key(m), who, secs, why)).fetchone()[0]

    def expire(self):
        return self.c.execute("SELECT alarm_unshelve_expired()").fetchone()[0]

    def state(self, m):
        r = self.c.execute("SELECT state FROM alarm WHERE alarm_key=%s", (key(m),)).fetchone()
        return r[0] if r else "NORM"

    def count(self, m):
        return self.c.execute("SELECT count(*) FROM alarm WHERE alarm_key=%s", (key(m),)).fetchone()[0]

    def history(self, m):
        return [{"at": r[0].isoformat(), "who": r[1], "action": r[2], "from": r[3], "to": r[4], "why": r[5]}
                for r in self.c.execute("SELECT at, actor, action, from_state, to_state, reason FROM alarm_event "
                                        "WHERE alarm_key=%s ORDER BY id", (key(m),)).fetchall()]


class Alerta:
    """Alerta 9.1 — ALARM_MODEL=ISA_18_2, AUTH_REQUIRED, basic 인증. 셸빙 만료는 /management/housekeeping 호출이 처리."""
    name = "alerta"
    shelve_supported = True
    SEV = {"CRITICAL": "Critical", "WARNING": "Medium", "HIGH": "High"}

    def __init__(self):
        self.url = "http://alerta:8080/api"
        self.admin = {"Authorization": "Key bench-admin-key-000000000000000000"}
        self.tok, self.ids = {}, {}
        for u in ("op-a", "op-b"):
            email = f"{u}@bench.local"
            requests.post(f"{self.url}/auth/signup", json={"name": u, "email": email, "password": "bench-pass-1"}, timeout=20)
            r = requests.post(f"{self.url}/auth/login", json={"username": email, "password": "bench-pass-1"}, timeout=20)
            r.raise_for_status()
            self.tok[u] = {"Authorization": f"Bearer {r.json()['token']}"}
        self.model = requests.get(f"{self.url}/config", timeout=20).json().get("alarm_model", {})

    def raise_(self, m, sev=None):
        body = {"resource": f'{m["device"]}:{m["tag"]}', "event": m["alert_type"], "environment": "Production",
                "severity": sev or self.SEV.get(m["severity"], "Medium"), "service": [m["site"]], "group": "SCADA",
                "value": str(m["value"]), "text": m["detail"], "origin": m["detector"],
                "attributes": {"site": m["site"], "device": m["device"], "ts_ns": str(m["ts"])}}
        r = requests.post(f"{self.url}/alert", json=body, headers=self.admin, timeout=20)
        r.raise_for_status()
        a = r.json()["alert"]
        self.ids[key(m)] = a["id"]
        return a["status"]

    def rtn(self, m):
        return self.raise_(m, sev="OK")

    def _act(self, m, who, action, why, timeout=None):
        body = {"action": action, "text": why}
        if timeout:
            body["timeout"] = timeout
        r = requests.put(f"{self.url}/alert/{self.ids[key(m)]}/action", json=body, headers=self.tok[who], timeout=20)
        r.raise_for_status()
        return self.state(m)

    def ack(self, m, who, why):
        return self._act(m, who, "ack", why)

    def shelve(self, m, who, secs, why):
        return self._act(m, who, "shelve", why, secs)

    def expire(self):
        return requests.get(f"{self.url}/management/housekeeping", headers=self.admin, timeout=60).status_code

    def state(self, m):
        return requests.get(f"{self.url}/alert/{self.ids[key(m)]}", headers=self.admin, timeout=20).json()["alert"]["status"]

    def count(self, m):
        r = requests.get(f"{self.url}/alerts", params={"resource": f'{m["device"]}:{m["tag"]}', "event": m["alert_type"]},
                         headers=self.admin, timeout=20).json()
        return len(r.get("alerts", []))

    def history(self, m):
        h = requests.get(f"{self.url}/alert/{self.ids[key(m)]}", headers=self.admin, timeout=20).json()["alert"].get("history", [])
        return [{"at": x.get("updateTime"), "who": x.get("user"), "action": x.get("type"), "to": x.get("status"),
                 "why": x.get("text")} for x in h]


class Keep:
    """Keep 0.54.3 (MIT 코어). 상태 firing/acknowledged/resolved/suppressed — ISA 상태 없음. 셸빙≈dismissed+dismissUntil.
    [미검증 API] AUTH_TYPE=db 로그인·사용자 생성 경로는 ②에서 확인."""
    name = "keep"
    shelve_supported = True
    MAP = {"firing": "UNACK", "acknowledged": "ACKED", "resolved": "NORM", "suppressed": "SHLVD", "pending": "UNACK"}

    def __init__(self):
        self.url = "http://keep-api:8080"
        self.h = {}
        r = requests.post(f"{self.url}/signin", json={"username": "keep", "password": "keep-bench-pw"}, timeout=20)
        r.raise_for_status()
        admin = {"Authorization": f"Bearer {r.json()['accessToken']}"}
        for u in ("op-a", "op-b"):
            requests.post(f"{self.url}/auth/users", json={"username": u, "password": "bench-pass-1", "role": "admin"},
                          headers=admin, timeout=20)
            t = requests.post(f"{self.url}/signin", json={"username": u, "password": "bench-pass-1"}, timeout=20)
            self.h[u] = {"Authorization": f"Bearer {t.json()['accessToken']}"} if t.ok else admin
        self.admin = admin

    def raise_(self, m, status="firing"):
        body = {"name": f'{m["tag"]} {m["alert_type"]}', "status": status, "severity": m["severity"].lower(),
                "fingerprint": key(m), "source": ["scada"], "service": m["site"], "description": m["detail"],
                "lastReceived": datetime.now(timezone.utc).isoformat(), "labels": {"tag": m["tag"], "device": m["device"]}}
        r = requests.post(f"{self.url}/alerts/event", json=body, headers=self.admin, timeout=20)
        r.raise_for_status()
        time.sleep(1.5)          # 비동기 처리(202)
        return self.state(m)

    def rtn(self, m):
        return self.raise_(m, "resolved")

    def ack(self, m, who, why):
        requests.post(f"{self.url}/alerts/enrich", json={"fingerprint": key(m), "enrichments": {"status": "acknowledged", "note": why}},
                      headers=self.h[who], timeout=20).raise_for_status()
        return self.state(m)

    def shelve(self, m, who, secs, why):
        until = (datetime.now(timezone.utc) + timedelta(seconds=secs)).isoformat()
        requests.post(f"{self.url}/alerts/enrich", json={"fingerprint": key(m), "enrichments": {
            "dismissed": "true", "dismissUntil": until, "note": why}}, headers=self.h[who], timeout=20).raise_for_status()
        return self.state(m)

    def expire(self):
        return None

    def state(self, m):
        a = requests.get(f"{self.url}/alerts/{requests.utils.quote(key(m), safe='')}", headers=self.admin, timeout=20).json()
        return self.MAP.get(str(a.get("status")), str(a.get("status")))

    def count(self, m):
        return 1

    def history(self, m):
        a = requests.get(f"{self.url}/alerts/{requests.utils.quote(key(m), safe='')}/audit", headers=self.admin, timeout=20).json()
        return [{"at": x.get("timestamp"), "who": x.get("user_id"), "action": x.get("action"), "why": x.get("description")} for x in a]


class ThingsBoard:
    """ThingsBoard CE 4.3 알람 — ACK/CLEAR 만(셸빙 없음). 상태 ACTIVE_UNACK/ACTIVE_ACK/CLEARED_UNACK/CLEARED_ACK."""
    name = "thingsboard"
    shelve_supported = False
    MAP = {"ACTIVE_UNACK": "UNACK", "ACTIVE_ACK": "ACKED", "CLEARED_UNACK": "RTNUN", "CLEARED_ACK": "NORM"}
    SEV = {"CRITICAL": "CRITICAL", "WARNING": "WARNING", "HIGH": "MAJOR"}

    def __init__(self):
        self.url = "http://thingsboard:8080"
        self.admin = self._login("tenant@thingsboard.org", "tenant")
        me = requests.get(f"{self.url}/api/auth/user", headers=self.admin, timeout=20).json()
        self.h = {"op-a": self.admin}
        # 두 번째 운전원(테넌트 관리자) 생성·활성화
        u = requests.post(f"{self.url}/api/user", params={"sendActivationMail": "false"}, headers=self.admin, timeout=20,
                          json={"email": f"op-b-{uuid.uuid4().hex[:4]}@bench.local", "authority": "TENANT_ADMIN",
                                "tenantId": me["tenantId"], "firstName": "op-b"}).json()
        link = requests.get(f"{self.url}/api/user/{u['id']['id']}/activationLink", headers=self.admin, timeout=20).text
        tok = link.split("activateToken=")[-1]
        r = requests.post(f"{self.url}/api/noauth/activate", json={"activateToken": tok, "password": "bench-pass-1"}, timeout=20)
        self.h["op-b"] = {"X-Authorization": f"Bearer {r.json()['token']}"} if r.ok else self.admin
        d = requests.post(f"{self.url}/api/device", json={"name": f"{DEV}-{uuid.uuid4().hex[:4]}", "type": "reactor"},
                          headers=self.admin, timeout=20).json()
        self.dev = d["id"]
        self.ids = {}

    def _login(self, u, p):
        r = requests.post(f"{self.url}/api/auth/login", json={"username": u, "password": p}, timeout=20)
        r.raise_for_status()
        return {"X-Authorization": f"Bearer {r.json()['token']}"}

    def raise_(self, m):
        body = {"originator": self.dev, "type": f'{m["tag"]}|{m["alert_type"]}', "severity": self.SEV.get(m["severity"], "MAJOR"),
                "details": m}
        r = requests.post(f"{self.url}/api/alarm", json=body, headers=self.admin, timeout=20)
        r.raise_for_status()
        self.ids[key(m)] = r.json()["id"]["id"]
        return self.state(m)

    def rtn(self, m):
        requests.post(f"{self.url}/api/alarm/{self.ids[key(m)]}/clear", headers=self.admin, timeout=20).raise_for_status()
        return self.state(m)

    def ack(self, m, who, why):
        requests.post(f"{self.url}/api/alarm/{self.ids[key(m)]}/ack", headers=self.h[who], timeout=20).raise_for_status()
        return self.state(m)

    def shelve(self, m, who, secs, why):
        raise NotImplementedError("ThingsBoard CE 알람에 셸빙 없음")

    def expire(self):
        return None

    def state(self, m):
        a = requests.get(f"{self.url}/api/alarm/info/{self.ids[key(m)]}", headers=self.admin, timeout=20).json()
        return self.MAP.get(a.get("status"), a.get("status"))

    def count(self, m):
        r = requests.get(f"{self.url}/api/alarm/DEVICE/{self.dev['id']}", params={"pageSize": 100, "page": 0},
                         headers=self.admin, timeout=20).json()
        return sum(1 for x in r.get("data", []) if x.get("type") == f'{m["tag"]}|{m["alert_type"]}' and not x.get("cleared"))

    def history(self, m):
        r = requests.get(f"{self.url}/api/alarm/{self.ids[key(m)]}/comment", params={"pageSize": 100, "page": 0},
                         headers=self.admin, timeout=20).json()
        return [{"at": x.get("createdTime"), "who": (x.get("userId") or {}).get("id"), "action": x.get("type"),
                 "why": (x.get("comment") or {}).get("text")} for x in r.get("data", [])]


ADAPTERS = {"pgisa": PgIsa, "alerta": Alerta, "keep": Keep, "thingsboard": ThingsBoard}
ISA_NAME: dict = {}   # 어댑터가 이미 ISA 이름으로 정규화. 모르는 값(예: Alerta 기본 모델 open/ack)은 그대로 둬 불일치로 드러나게


def run(a):
    RAW.mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    ad = None
    for _ in range(90):
        try:
            ad = ADAPTERS[a.profile]()
            break
        except Exception as e:
            last = e
            time.sleep(4)
    if ad is None:
        raise SystemExit(f"연결 실패: {last!r}")
    A = msg("IT-102", "THRESHOLD_USL", "CRITICAL", 9.9)
    B = msg("VT-101", "CEP_BEARING", "CRITICAL", 7.5, "TIER1_CEP")
    C = msg("TT-101", "ZSCORE", "WARNING", 91.0, "TIER1_ZSCORE")
    C2 = dict(C, severity="CRITICAL", value=96.0)
    steps = []

    def step(sid, what, fn, expect):
        t = time.time()
        err = None
        try:
            fn()
        except NotImplementedError as e:
            steps.append({"id": sid, "what": what, "expect": expect, "observed": None, "match": False,
                          "unsupported": str(e)})
            return
        except Exception as e:
            err = repr(e)[:300]
        ms = round((time.time() - t) * 1000, 1)
        try:
            obs_raw = {k: ad.state(m) for k, m in (("A", A), ("B", B), ("C", C)) if k in expect}
        except Exception as e:
            obs_raw, err = {}, err or repr(e)[:300]
        obs = {k: ISA_NAME.get(v, v) for k, v in obs_raw.items()}
        steps.append({"id": sid, "what": what, "expect": expect, "observed": obs, "observed_raw": obs_raw,
                      "match": obs == expect and err is None, "api_ms": ms, "error": err})

    step("L01", "A 발생", lambda: ad.raise_(A), {"A": "UNACK"})
    step("L02", "A 5회 반복", lambda: [ad.raise_(dict(A, ts=time.time_ns())) for _ in range(5)], {"A": "UNACK"})
    steps[-1]["alarm_count"] = _safe(lambda: ad.count(A))
    step("L03", "op-a 가 A 확인", lambda: ad.ack(A, "op-a", "현장 확인, 교반기 부하 증가"), {"A": "ACKED"})
    step("L04", "A 복귀", lambda: ad.rtn(A), {"A": "NORM"})
    step("L05a", "B 발생", lambda: ad.raise_(B), {"B": "UNACK"})
    step("L05b", "B 확인 전 복귀", lambda: ad.rtn(B), {"B": "RTNUN"})
    step("L06", "op-b 가 B 확인", lambda: ad.ack(B, "op-b", "복귀 확인"), {"B": "NORM"})
    step("L07a", "C 발생(WARNING)", lambda: ad.raise_(C), {"C": "UNACK"})
    step("L07b", "op-a 가 C 확인", lambda: ad.ack(C, "op-a", "추이 관찰"), {"C": "ACKED"})
    step("L08", "C 악화(CRITICAL) 재알람", lambda: ad.raise_(dict(C2, ts=time.time_ns())), {"C": "UNACK"})
    step("L09", "op-a 가 C 셸빙 60초", lambda: ad.shelve(C, "op-a", 60, "센서 교정 작업 중(작업지시 WO-1)"), {"C": "SHLVD"})
    step("L10", "셸빙 중 C 재발생", lambda: ad.raise_(dict(C2, ts=time.time_ns())), {"C": "SHLVD"})
    if ad.shelve_supported:
        time.sleep(65)
    step("L11", "셸빙 만료", lambda: ad.expire(), {"C": "UNACK"})

    hist = {k: _safe(lambda m=m: ad.history(m)) for k, m in (("A", A), ("B", B), ("C", C))}

    def has(h, who, word):
        return isinstance(h, list) and any((x.get("who") or "") and who in str(x.get("who")) and word in
                                           json.dumps(x, ensure_ascii=False).lower() for x in h)
    cq15 = {"question": "IT-102 THRESHOLD_USL 알람은 확인됐는가, 누가 언제?",
            "answerable": isinstance(hist["A"], list) and any("ack" in json.dumps(x).lower() and x.get("who") and x.get("at")
                                                               for x in hist["A"]),
            "by_op_a": has(hist["A"], "op-a", "ack")}
    cq08 = {"question": "TT-101 ZSCORE 를 누가 언제 왜 셸빙했는가?(CQ08 의 승인·반려 기록 요건을 알람 조작에 적용)",
            "answerable": isinstance(hist["C"], list) and any("shelv" in json.dumps(x).lower() and x.get("who") and x.get("why")
                                                               for x in hist["C"])}
    matched = sum(s["match"] for s in steps)
    res = {"exp": "EXP-ALM", "stage": 2, "profile": a.profile, "steps": steps,
           "e10_match": {"matched": matched, "of": len(steps), "pct": round(100 * matched / len(steps), 1)},
           "cq15": cq15, "cq08_analog": cq08, "history": hist,
           "api_ms_p95": sorted(s.get("api_ms") or 0 for s in steps)[int(0.95 * (len(steps) - 1))],
           "shelve_supported": ad.shelve_supported, "marks": {"run_start_epoch": t_start, "run_end_epoch": time.time()},
           "model_info": getattr(ad, "model", None),
           "guard": {"forced": os.environ.get("BENCH_GUARD_FORCED") == "1"}}
    (RAW / f"{a.profile}_run.json").write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str))
    print(json.dumps({"profile": a.profile, "e10": res["e10_match"], "cq15": cq15["answerable"], "cq08": cq08["answerable"]},
                     ensure_ascii=False))


def _safe(fn):
    try:
        return fn()
    except Exception as e:
        return {"error": repr(e)[:300]}


def summarize(a):
    import csv
    run_ = json.loads((RAW / f"{a.profile}_run.json").read_text()) if (RAW / f"{a.profile}_run.json").exists() else None
    stats = {}
    f = RAW / f"stats_{a.profile}.csv"
    if f.exists():
        by = {}
        for r in csv.DictReader(open(f)):
            if "client" in r["name"]:
                continue
            try:
                by.setdefault(r["name"], []).append(float(r["mem_mib"]))
            except ValueError:
                pass
        stats = {n: {"mem_mib_median": sorted(v)[len(v) // 2], "mem_mib_max": max(v)} for n, v in by.items() if v}
    img = RAW / f"images_{a.profile}.txt"
    verdict = "미실행" if not run_ else ("통과" if run_["e10_match"]["pct"] == 100 and run_["cq15"]["answerable"]
                                        and run_["cq08_analog"]["answerable"] else "탈락 또는 부분(세부는 steps)")
    res = {"exp": "EXP-ALM", "stage": 2, "profile": a.profile, "run": run_, "resources": stats,
           "images": img.read_text().splitlines() if img.exists() else None, "stage2_verdict": verdict,
           "baseline_v1": "V1 은 알람 상태 관리 없음(E10 공백): Telegraf#3 → MQTT → FUXA 표시, ai-alarm-worker 는 사건 등록만. "
                          "CQ15 칸(ack_state·acknowledged_by…) 없음 — harness/aibench/cq_eval.py CQ15"}
    p = pathlib.Path(f"/experiments/EXP-ALM/stage2_{a.profile}.json")
    p.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str))
    print(f"wrote {p} verdict={verdict}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "summarize"])
    ap.add_argument("--profile", required=True, choices=list(ADAPTERS))
    a = ap.parse_args()
    {"run": run, "summarize": summarize}[a.cmd](a)


if __name__ == "__main__":
    main()
