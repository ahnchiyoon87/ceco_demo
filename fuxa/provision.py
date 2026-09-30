#!/usr/bin/env python3
"""FUXA 자동 설정(기동 때 1회, 다시 돌려도 같은 결과).

  0) 로그인: 보안(secureEnabled)은 fuxa/seed_settings.js 가 켠다. FUXA 첫 기동의 기본 관리자(admin/123456)를
     환경변수 FUXA_ADMIN_PASSWORD 로 바꾸고, 운전원 계정 operator(그룹 Operator=2, FUXA_OPERATOR_PASSWORD)를 만든다.
     화면 값 보기는 로그인 없이(guest), 운전원 명령은 로그인한 사용자만, 화면·설정 변경은 관리자만 된다(FUXA 1.3.4 규칙).
  1) MQTT 장치 계정(fuxa)·비밀번호를 장치 보안 저장소(POST /api/device, query=security, 관리자만 읽고 씀)에 넣는다.
     프로젝트는 로그인 없이도 읽히므로 거기에는 계정을 두지 않는다(09-30 실측: 두면 IT 컨테이너가 호스트 포트로 읽어 간다).
  2) project.json(registry/generate.py 가 등록부에서 만든 화면·태그·공정 알람)을 관리자 토큰으로 POST /api/project 로 넣는다.
  3) DAQ(OT 이력, SQLite) 보존이 7일인지 확인한다(HANDOFF §2-2 보존 표, ⑨-9: FUXA 1.3.4 의 daqstore.retention).
     값은 compose 가 FUXA 첫 기동 때 넣는 fuxa/mysettings.json 에서 온다. 여기서 설정 API 로 바꾸지 않는다 —
     프로젝트 넣기에 이어 설정을 넣으면 런타임이 1초 안에 두 번 재시작돼 FUXA 가 같은 이름의 DAQ 파일을 지운다.
새 구조의 FUXA 는 MQTT(UNS)만 쓰므로 Modbus 플러그인을 설치하지 않는다(OT 망은 인터넷이 없다).
"""
from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

BASE = os.getenv("FUXA_URL", "http://fuxa:1881")
PROJECT = pathlib.Path(__file__).parent / "project.json"
TIMEOUT_S = int(os.getenv("PROVISION_TIMEOUT_S", "180"))
DAQ_RETENTION = os.getenv("FUXA_DAQ_RETENTION", "days7")


TOKEN: str | None = None


def call(path: str, payload=None, method: str | None = None, timeout: int = 15):
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {"Content-Type": "application/json", **({"x-access-token": TOKEN} if TOKEN else {})}
    req = urllib.request.Request(BASE + path, data=data, headers=headers, method=method or ("POST" if data else "GET"))
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode() or "{}"
    return json.loads(body) if body.strip().startswith(("{", "[")) else body


def wait_ready() -> bool:
    deadline = time.time() + TIMEOUT_S
    while time.time() < deadline:
        try:
            call("/api/project", timeout=5)
            return True
        except urllib.error.HTTPError as e:
            if e.code in (401, 403):
                return True
        except Exception:
            pass
        time.sleep(2)
    return False


def signin(user: str, password: str) -> str | None:
    try:
        r = call("/api/signin", {"username": user, "password": password})
        return (r.get("data") or {}).get("token")
    except urllib.error.HTTPError:
        return None


def accounts() -> None:
    """관리자 비밀번호를 환경변수 값으로(처음 한 번), 운전원 계정을 만든다. 다시 돌려도 같은 결과."""
    global TOKEN
    admin_pw = os.environ["FUXA_ADMIN_PASSWORD"]
    TOKEN = signin("admin", admin_pw)
    if TOKEN is None:
        TOKEN = signin("admin", "123456")            # FUXA 첫 기동의 기본 관리자
        if TOKEN is None:
            raise SystemExit("[fuxa-provision] 관리자 로그인 실패 — FUXA_ADMIN_PASSWORD 와 FUXA 사용자 DB 확인")
        call("/api/users", {"params": {"username": "admin", "fullname": "Administrator Account", "password": admin_pw, "groups": -1, "info": "{}"}})
        TOKEN = signin("admin", admin_pw)
        print("[fuxa-provision] 관리자 기본 비밀번호를 바꿈", flush=True)
    call("/api/users", {"params": {"username": "operator", "fullname": "운전원", "password": os.environ["FUXA_OPERATOR_PASSWORD"],
                                   "groups": 2, "info": "{}"}})
    if signin("operator", os.environ["FUXA_OPERATOR_PASSWORD"]) is None:
        raise SystemExit("[fuxa-provision] 운전원 계정 로그인 확인 실패")
    print("[fuxa-provision] 계정: admin(관리자), operator(운전원) 로그인 확인", flush=True)


def main() -> int:
    print(f"[fuxa-provision] FUXA 대기 ({BASE})", flush=True)
    if not wait_ready():
        print(f"[fuxa-provision] {TIMEOUT_S}초 안에 응답 없음", file=sys.stderr)
        return 1
    project = json.loads(PROJECT.read_text(encoding="utf-8"))
    view = project["hmi"]["views"][0]
    try:
        settings = call("/api/settings")
        if not settings.get("secureEnabled"):
            print("[fuxa-provision] FUXA 보안(로그인)이 꺼져 있음 — fuxa/seed_settings.js·_appdata/mysettings.json 확인", file=sys.stderr)
            return 1
        accounts()
        for dev_id, dev in project["devices"].items():   # 연결보다 먼저: 프로젝트 넣기가 런타임을 다시 시작하며 이 값으로 연결한다
            call("/api/device", {"params": {"query": "security", "name": dev_id,   # 값은 객체로(FUXA 저장소가 문자열로 바꿔 둔다)
                                            "value": {"clientId": dev["property"]["clientId"], "uid": "fuxa",
                                                      "pwd": os.environ["MQTT_FUXA_PASSWORD"]}}})
        call("/api/project", project)
        cur = call("/api/project")
        got = cur.get("result", cur) if isinstance(cur, dict) else {}
        ntags = sum(len(d.get("tags", {})) for d in (got.get("devices") or {}).values())
        print(f"[fuxa-provision] 화면 넣음: 태그 {ntags}개 / 알람 {len(got.get('alarms') or [])}개 / "
              f"화면 요소 {len(view['items'])}개", flush=True)
        daq = call("/api/settings").get("daqstore") or {}
        print(f"[fuxa-provision] DAQ(OT 이력) 보존: {daq}", flush=True)
        if daq.get("retention") != DAQ_RETENTION or daq.get("type", "SQlite") != "SQlite":
            print(f"[fuxa-provision] DAQ 보존이 {DAQ_RETENTION} 가 아님 — fuxa/mysettings.json 과 볼륨의 _appdata/mysettings.json 확인",
                  file=sys.stderr)
            return 1
    except urllib.error.HTTPError as e:
        print(f"[fuxa-provision] HTTP {e.code}: {e.read().decode()[:300]}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
