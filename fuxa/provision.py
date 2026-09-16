#!/usr/bin/env python3
"""FUXA 프로젝트 자동 주입.

FUXA 기동을 기다렸다가 project.json 을 POST /api/project 로 넣는다.
운영자가 화면을 직접 그릴 필요가 없다. 재실행해도 안전하다(멱등).
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


def call(path: str, payload=None, method: str | None = None, timeout: int = 15):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(
        BASE + path, data=data,
        headers={"Content-Type": "application/json"},
        method=method or ("POST" if data else "GET"))
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
            # 인증이 걸려 있어도 서버가 살아있다는 뜻
            if e.code in (401, 403):
                return True
        except Exception:
            pass
        time.sleep(3)
    return False


# FUXA 는 산업 프로토콜 드라이버를 런타임 플러그인으로 설치한다.
# Modbus 드라이버가 없으면 디바이스가 아예 기동되지 않으므로 먼저 설치한다.
REQUIRED_PLUGINS = [("modbus-serial", "8.0.19")]


def ensure_plugins() -> None:
    try:
        installed = {p.get("name"): p.get("current") for p in call("/api/plugins")}
    except Exception as e:
        print(f"[fuxa-provision] 플러그인 목록 조회 실패: {e}", flush=True)
        return
    for name, version in REQUIRED_PLUGINS:
        if installed.get(name):
            print(f"[fuxa-provision] 플러그인 {name} {installed[name]} 이미 설치됨", flush=True)
            continue
        print(f"[fuxa-provision] 플러그인 설치: {name} {version} (수 분 소요)", flush=True)
        try:
            call("/api/plugins", {"params": {"name": name, "version": version}}, timeout=300)
            print(f"[fuxa-provision] ✓ {name} 설치 완료", flush=True)
        except Exception as e:
            print(f"[fuxa-provision] ✗ {name} 설치 실패: {e}", file=sys.stderr)


def main() -> int:
    print(f"[fuxa-provision] FUXA 대기 중... ({BASE})", flush=True)
    if not wait_ready():
        print(f"[fuxa-provision] ✗ {TIMEOUT_S}초 내 응답 없음", file=sys.stderr)
        return 1

    ensure_plugins()

    project = json.loads(PROJECT.read_text())
    views = project["hmi"]["views"]
    print(f"[fuxa-provision] 주입: 디바이스 {len(project['devices'])}개 / "
          f"뷰 {len(views)}개 / 아이템 {len(views[0]['items'])}개", flush=True)

    try:
        call("/api/project", project)
    except urllib.error.HTTPError as e:
        print(f"[fuxa-provision] ✗ HTTP {e.code}: {e.read().decode()[:300]}", file=sys.stderr)
        return 1

    # 실제로 반영됐는지 되읽어 확인
    try:
        cur = call("/api/project")
        got = cur.get("result", cur) if isinstance(cur, dict) else {}
        devs = got.get("devices") or {}
        nviews = len((got.get("hmi") or {}).get("views") or [])
        print(f"[fuxa-provision] ✓ 반영 확인 — 디바이스 {len(devs)}개, 뷰 {nviews}개", flush=True)
    except Exception as e:
        print(f"[fuxa-provision] 주입은 성공했으나 확인 실패: {e}", flush=True)

    print(f"[fuxa-provision] 완료. 화면: http://localhost:{os.getenv('PORT_FUXA', '27018')}", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
