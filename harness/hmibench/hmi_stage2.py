"""HMI 비교 ② 측정 클라이언트 (EXP-HMI, 측정 도구).

    python /repo/harness/hmibench/hmi_stage2.py run --profile fuxa-v1|fuxa134|fuxa134-uns|nodered|thingsboard|scadalts|streampipes
    python /repo/harness/hmibench/hmi_stage2.py tb-prepare        # ThingsBoard: 게이트웨이 장치·토큰 준비(호스트가 이후 tb-gateway 기동)
    python /repo/harness/hmibench/hmi_stage2.py summarize --profile fuxa134

같은 판정(결과 보기 전 고정 2026-09-29):
  D1 표시: 12태그가 HMI 에 숫자로 보이는가(API 로 읽음) + 가상설비 /state 값과 일치하는가
  D2 신선도: /state 값이 바뀐 뒤 같은 값이 HMI 에 보이기까지(5Hz 폴링, 30초) p50/p95
  D3 알람: V1 알람 토픽(scada/hmi/latest-alert 문자열, scada/alerts/{tag} JSON) 발행 → HMI 에 보이기까지
  D4 명령: 인증한 운전원이 교반기(코일1) 켜기 → /state commands.agitator_run 반영, 인증 없는 쓰기는 거부
  D5 감사: 명령한 사람이 기록되는가
  D6 읽기 경로: 설비 직접 폴링(Modbus)인가 MQTT 구독인가(V1 이중 폴링 문제)
"""
from __future__ import annotations

import argparse
import json
import os
import pathlib
import threading
import time

import requests

RAW = pathlib.Path("/experiments/EXP-HMI/raw")
PLANT = "http://plant-simulator:8080/state"
GEN = pathlib.Path("/repo/harness/hmibench/generated")
TAGS = ["LT-101", "LT-102", "TT-101", "TT-102", "PT-101", "FT-101", "FT-102", "IT-101", "IT-102", "VT-101", "pH-101", "CT-101"]
TOL = 1e-3


def plant():
    return requests.get(PLANT, timeout=5).json()


def mqtt_pub(topic, payload):
    import paho.mqtt.client as mqtt
    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"bench-pub-{time.time_ns()}", protocol=mqtt.MQTTv311)
    c.username_pw_set("bench", "bench-pub-pw")
    c.connect("mosquitto", 1883)
    c.loop_start()
    c.publish(topic, payload, qos=1).wait_for_publish(10)
    c.loop_stop()
    c.disconnect()


# ─────────────────────────────── 어댑터 ───────────────────────────────
class Fuxa:
    reads_via = "modbus-poll"

    def __init__(self, profile):
        self.url = "http://fuxa:1881"
        self.secure = profile != "fuxa-v1"
        self.proj = GEN / ("project_uns.json" if profile == "fuxa134-uns" else "project_poll.json")
        self.reads_via = "mqtt(12 계측) + modbus-poll(명령 9태그)" if profile == "fuxa134-uns" else "modbus-poll"
        self.h = {}
        self.default_password_works = None

    def _login(self, user="admin", pw="123456"):
        r = requests.post(f"{self.url}/api/signin", json={"username": user, "password": pw}, timeout=10)
        if r.ok:
            j = r.json()
            tok = (j.get("data") or {}).get("token") or j.get("token")
            return {"x-access-token": tok} if tok else {}
        return None

    def setup(self):
        for _ in range(60):
            try:
                requests.get(f"{self.url}/api/settings", timeout=5)
                break
            except Exception:
                time.sleep(3)
        if self.secure:
            h = self._login()
            self.default_password_works = h is not None
            self.h = h or {}
        # V1 provision.py 와 같은 순서: Modbus 플러그인 → 프로젝트
        try:
            plugs = {p.get("name"): p.get("current") for p in requests.get(f"{self.url}/api/plugins", headers=self.h, timeout=20).json()}
            if not plugs.get("modbus-serial"):
                requests.post(f"{self.url}/api/plugins", json={"params": {"name": "modbus-serial", "version": "8.0.19"}},
                              headers=self.h, timeout=300)
        except Exception as e:
            print("plugin:", e)
        r = requests.post(f"{self.url}/api/project", json=json.loads(self.proj.read_text(encoding="utf-8")), headers=self.h, timeout=30)
        self.project_upload = r.status_code
        time.sleep(15)

    def ids(self):
        p = json.loads(self.proj.read_text(encoding="utf-8"))
        m = {}
        for d in p["devices"].values():
            for k, t in d.get("tags", {}).items():
                if t["name"] in TAGS:
                    m[t["name"]] = k
        return m

    def values(self, headers=None):
        idm = self.ids()
        r = requests.get(f"{self.url}/api/getTagValue", params={"ids": json.dumps(list(idm.values()))},
                         headers=self.h if headers is None else headers, timeout=10)
        if r.status_code != 200:
            return None, r.status_code
        out = {}
        for x in r.json():
            name = next((n for n, i in idm.items() if i == x.get("id")), None)
            if name:
                out[name] = x.get("value")
        return out, 200

    def alarm_text(self):
        r = requests.get(f"{self.url}/api/getTagValue", params={"ids": json.dumps(["ActiveAlert"])}, headers=self.h, timeout=10)
        return (r.json() or [{}])[0].get("value") if r.ok else None

    def command(self, value, auth=True):
        r = requests.post(f"{self.url}/api/setTagValue", json={"tags": [{"id": "AgitatorRun", "value": value}]},
                          headers=self.h if auth else {}, timeout=10)
        return r.status_code

    def audit(self):
        return {"available": False, "note": "FUXA setTagValue 는 사용자별 쓰기 감사 기록 API 없음(로그 파일만) [②에서 _logs 확인]"}


class NodeRed:
    reads_via = "mqtt"

    def __init__(self, profile):
        self.url = "http://nodered:1880"
        self.auth = ("operator", "nr-operator-bench-pw")
        self.default_password_works = False

    def setup(self):
        for _ in range(60):
            try:
                if requests.get(f"{self.url}/bench/values", auth=self.auth, timeout=5).ok:
                    break
            except Exception:
                pass
            time.sleep(3)
        self.project_upload = "flows.json(파일)"
        time.sleep(5)

    def values(self, headers=None):
        r = requests.get(f"{self.url}/bench/values", auth=None if headers == {} else self.auth, timeout=10)
        if r.status_code != 200:
            return None, r.status_code
        return {k: v["value"] for k, v in r.json()["tags"].items()}, 200

    def alarm_text(self):
        j = requests.get(f"{self.url}/bench/alarm", auth=self.auth, timeout=10).json()
        return (j.get("latest") or {}).get("text")

    def command(self, value, auth=True):
        r = requests.post(f"{self.url}/bench/command", json={"target": "agitator_run", "value": value},
                          auth=self.auth if auth else None, timeout=15)
        return r.status_code

    def audit(self):
        a = requests.get(f"{self.url}/bench/audit", auth=self.auth, timeout=10).json().get("audit", [])
        return {"available": any(x.get("user") == "operator" for x in a), "records": a[-5:]}


class ThingsBoard:
    reads_via = "mqtt(tb-gateway MQTT 커넥터) → TB"

    def __init__(self, profile):
        self.url = "http://thingsboard:8080"
        self.default_password_works = None

    def _login(self):
        r = requests.post(f"{self.url}/api/auth/login", json={"username": "tenant@thingsboard.org", "password": "tenant"}, timeout=10)
        r.raise_for_status()
        return {"X-Authorization": f"Bearer {r.json()['token']}"}

    def setup(self):
        self.h = self._login()
        self.default_password_works = True     # 데모 계정 기본 비밀번호(LOAD_DEMO) — 운영 시 제거 항목
        self.project_upload = "tb-prepare + gateway"
        for _ in range(60):
            self.dev = self._device("AR100")
            if self.dev:
                break
            time.sleep(3)
        self.cmd_dev = self._device("AR100-CMD")

    def _device(self, name):
        r = requests.get(f"{self.url}/api/tenant/devices", params={"deviceName": name}, headers=self.h, timeout=10)
        return r.json()["id"]["id"] if r.ok and r.text else None

    def values(self, headers=None):
        r = requests.get(f"{self.url}/api/plugins/telemetry/DEVICE/{self.dev}/values/timeseries",
                         params={"keys": ",".join(TAGS)}, headers=self.h if headers is None else headers, timeout=10)
        if r.status_code != 200:
            return None, r.status_code
        return {k: float(v[0]["value"]) for k, v in r.json().items() if v}, 200

    def alarm_text(self):
        r = requests.get(f"{self.url}/api/plugins/telemetry/DEVICE/{self.dev}/values/timeseries",
                         params={"keys": "last_alert"}, headers=self.h, timeout=10).json()
        return (r.get("last_alert") or [{}])[0].get("value")

    def command(self, value, auth=True):
        if not self.cmd_dev:
            return "no-cmd-device"
        r = requests.post(f"{self.url}/api/plugins/rpc/twoway/{self.cmd_dev}", json={"method": "agitator_run", "params": value},
                          headers=self.h if auth else {}, timeout=20)
        return r.status_code

    def audit(self):
        r = requests.get(f"{self.url}/api/audit/logs", params={"pageSize": 20, "page": 0, "sortOrder": "DESC"}, headers=self.h, timeout=10)
        recs = r.json().get("data", []) if r.ok else []
        return {"available": any("RPC" in json.dumps(x) for x in recs), "records": [x.get("actionType") for x in recs[:10]]}


class HealthOnly:
    """Scada-LTS·StreamPipes: 기동·로그인까지만 자동화. 데이터 소스·화면·명령 구성은 제품 API 확인 후([미검증]) — STAGE2.md."""
    reads_via = "?"

    def __init__(self, profile):
        self.profile = profile
        self.default_password_works = None

    def setup(self):
        self.project_upload = "해당 없음(자동화 안 됨)"
        if self.profile == "scadalts":
            self.reads_via = "modbus-poll(Scada-LTS Modbus IP 데이터 소스) — MQTT 데이터 소스 없음[미확인]"
            url = "http://scadalts:8080/Scada-LTS/"
            ok = None
            for _ in range(90):
                try:
                    ok = requests.get(url, timeout=5).status_code
                    if ok < 500:
                        break
                except Exception:
                    pass
                time.sleep(4)
            r = requests.post("http://scadalts:8080/Scada-LTS/api/auth/admin/admin", timeout=10) if ok else None
            self.default_password_works = bool(r is not None and r.ok)
            self.health = ok
        else:
            self.reads_via = "mqtt(StreamPipes MQTT 어댑터)[미검증]"
            ok = None
            for _ in range(90):
                try:
                    ok = requests.get("http://sp-ui:8088/", timeout=5).status_code
                    if ok < 500:
                        break
                except Exception:
                    pass
                time.sleep(4)
            r = requests.post("http://sp-backend:8030/streampipes-backend/api/v2/auth/login",
                              json={"username": "admin@streampipes.apache.org", "password": "admin"}, timeout=10) if ok else None
            self.default_password_works = bool(r is not None and r.ok)
            self.health = ok

    def values(self, headers=None):
        return None, "not-automated"

    def alarm_text(self):
        return None

    def command(self, value, auth=True):
        return "not-automated"

    def audit(self):
        return {"available": None, "note": "자동화 안 됨"}


ADAPTERS = {"fuxa-v1": Fuxa, "fuxa134": Fuxa, "fuxa134-uns": Fuxa, "nodered": NodeRed, "thingsboard": ThingsBoard,
            "scadalts": HealthOnly, "streampipes": HealthOnly}


def close(a, b):
    try:
        return abs(float(a) - float(b)) <= TOL * max(1.0, abs(float(b)))
    except (TypeError, ValueError):
        return False


def run(a):
    RAW.mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    ad = ADAPTERS[a.profile](a.profile)
    ad.setup()
    res = {"exp": "EXP-HMI", "stage": 2, "profile": a.profile, "reads_via": ad.reads_via,
           "project_upload": getattr(ad, "project_upload", None), "default_password_works": ad.default_password_works,
           "health": getattr(ad, "health", None)}
    # D1 표시 + 값 일치
    vals, st = ad.values()
    s = plant()
    prev = {}
    if vals is not None:
        time.sleep(1)
        s2 = plant()
        vals, st = ad.values()
        numeric = {t: isinstance(vals.get(t), (int, float)) or _isnum(vals.get(t)) for t in TAGS}
        match = {t: close(vals.get(t), s2["readings"].get(t)) or close(vals.get(t), s["readings"].get(t)) for t in TAGS}
        res["D1_display"] = {"tags_numeric": sum(numeric.values()), "of": 12, "match_state_now_or_prev_scan": sum(match.values()),
                             "sample": {t: vals.get(t) for t in TAGS[:3]}}
    else:
        res["D1_display"] = {"status": st}
    # 인증 없는 읽기
    try:
        _, st_noauth = ad.values(headers={})
        res["unauth_read_status"] = st_noauth
    except Exception as e:
        res["unauth_read_status"] = repr(e)[:100]
    # D2 신선도
    if vals is not None:
        lags, pending, t0 = [], {}, time.time()
        last_state = {}
        while time.time() - t0 < a.fresh_s:
            now = time.time()
            try:
                rd = plant()["readings"]
                hv, _ = ad.values()
            except Exception:
                time.sleep(0.2)
                continue
            for t in TAGS:
                if rd.get(t) != last_state.get(t):
                    last_state[t] = rd.get(t)
                    pending[(t, rd.get(t))] = now
            for (t, v), ts in list(pending.items()):
                if close((hv or {}).get(t), v):
                    lags.append((time.time() - ts) * 1000)
                    del pending[(t, v)]
                elif now - ts > 10:
                    del pending[(t, v)]
            time.sleep(0.2)
        lags.sort()
        res["D2_freshness_ms"] = {"n": len(lags), "p50": lags[len(lags) // 2] if lags else None,
                                  "p95": lags[int(0.95 * (len(lags) - 1))] if lags else None,
                                  "note": "HMI API 폴링 5Hz 해상도(±200ms). 값이 1초마다 바뀌므로 10초 안 미반영은 버림"}
    # D3 알람
    text = f"{time.strftime('%m-%d %H:%M:%S', time.gmtime())} UTC | CRITICAL | IT-102 | THRESHOLD_USL"
    t_pub = time.time()
    try:
        mqtt_pub("scada/alerts/IT-102", json.dumps({"fields": {"value": 9.9, "detail": "IT-102 = 9.900 A / 규격 [-, 9.6]"},
                                                    "name": "alert", "tags": {"site": "AR-100", "device": "reactor-line-01",
                                                    "tag": "IT-102", "alert_type": "THRESHOLD_USL", "severity": "CRITICAL",
                                                    "detector": "TIER1_RULE"}, "timestamp": time.time_ns()}))
        mqtt_pub("scada/hmi/latest-alert", text)
        seen = None
        while time.time() - t_pub < 20:
            v = ad.alarm_text()
            if v and ("IT-102" in str(v)):
                seen = round((time.time() - t_pub) * 1000, 1)
                break
            time.sleep(0.1)
        res["D3_alarm"] = {"visible": seen is not None, "latency_ms": seen}
    except Exception as e:
        res["D3_alarm"] = {"error": repr(e)[:200]}
    # D4 명령
    try:
        before = plant()["commands"]["agitator_run"]
        target = 0 if before else 1
        st_noauth = ad.command(target, auth=False)
        time.sleep(3)
        after_noauth = plant()["commands"]["agitator_run"]
        st_auth = ad.command(target, auth=True)
        t_cmd = time.time()
        reflected = None
        while time.time() - t_cmd < 10:
            if plant()["commands"]["agitator_run"] == target:
                reflected = round((time.time() - t_cmd) * 1000, 1)
                break
            time.sleep(0.2)
        res["D4_command"] = {"unauth_status": st_noauth, "unauth_changed_plant": after_noauth != before,
                             "auth_status": st_auth, "reflected_ms": reflected, "target": target}
        ad.command(before, auth=True)
    except Exception as e:
        res["D4_command"] = {"error": repr(e)[:200]}
    try:
        res["D5_audit"] = ad.audit()
    except Exception as e:
        res["D5_audit"] = {"error": repr(e)[:200]}
    res["D6_reads_via"] = ad.reads_via
    res["double_polling_with_collector"] = "modbus-poll" in ad.reads_via
    res["marks"] = {"run_start_epoch": t_start, "run_end_epoch": time.time()}
    (RAW / f"{a.profile}_run.json").write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str))
    print(json.dumps(res, ensure_ascii=False, default=str)[:1500])


def _isnum(v):
    try:
        float(v)
        return True
    except (TypeError, ValueError):
        return False


def tb_prepare(a):
    """게이트웨이 장치(토큰 bench-gw-token) 생성. 호스트가 이후 tb-gateway 를 띄운다."""
    url = "http://thingsboard:8080"
    for _ in range(120):
        try:
            r = requests.post(f"{url}/api/auth/login", json={"username": "tenant@thingsboard.org", "password": "tenant"}, timeout=10)
            if r.ok:
                break
        except Exception:
            pass
        time.sleep(5)
    h = {"X-Authorization": f"Bearer {r.json()['token']}"}
    d = requests.post(f"{url}/api/device", json={"name": "bench-gateway", "type": "gateway", "additionalInfo": {"gateway": True}},
                      params={"accessToken": "bench-gw-token"}, headers=h, timeout=20)
    print("gateway device:", d.status_code, d.text[:200])


def summarize(a):
    import csv
    f = RAW / f"{a.profile}_run.json"
    run_ = json.loads(f.read_text()) if f.exists() else None
    stats = {}
    sf = RAW / f"stats_{a.profile}.csv"
    if sf.exists():
        by = {}
        for r in csv.DictReader(open(sf)):
            if "client" in r["name"] or "plant-simulator" in r["name"] or "mosquitto" in r["name"]:
                continue
            try:
                by.setdefault(r["name"], {"cpu": [], "mem": []})
                by[r["name"]]["cpu"].append(float(r["cpu_pct"]))
                by[r["name"]]["mem"].append(float(r["mem_mib"]))
            except ValueError:
                pass
        stats = {n: {"cpu_pct_median": sorted(v["cpu"])[len(v["cpu"]) // 2], "mem_mib_median": sorted(v["mem"])[len(v["mem"]) // 2],
                     "mem_mib_max": max(v["mem"])} for n, v in by.items() if v["mem"]}
    ok = run_ and (run_.get("D1_display", {}).get("match_state_now_or_prev_scan") == 12 and run_.get("D3_alarm", {}).get("visible")
                   and run_.get("D4_command", {}).get("reflected_ms") is not None)
    img = RAW / f"images_{a.profile}.txt"
    res = {"exp": "EXP-HMI", "stage": 2, "profile": a.profile, "run": run_, "resources": stats,
           "images": img.read_text().splitlines() if img.exists() else None,
           "stage2_verdict": "미실행" if not run_ else ("통과(기능)" if ok else "탈락 또는 부분(세부는 run)"),
           "security_note": "unauth_read_status·D4.unauth_* 가 거부(401/403)여야 ① 기본 보안 통과. fuxa-v1 은 V1 그대로(인증 꺼짐) 기준선."}
    p = pathlib.Path(f"/experiments/EXP-HMI/stage2_{a.profile}.json")
    p.write_text(json.dumps(res, ensure_ascii=False, indent=2, default=str))
    print(f"wrote {p} verdict={res['stage2_verdict']}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "tb-prepare", "summarize"])
    ap.add_argument("--profile", default="fuxa134")
    ap.add_argument("--fresh-s", type=int, default=30)
    a = ap.parse_args()
    {"run": run, "tb-prepare": tb_prepare, "summarize": summarize}[a.cmd](a)


if __name__ == "__main__":
    main()
