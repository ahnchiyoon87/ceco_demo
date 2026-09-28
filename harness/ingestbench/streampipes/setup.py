"""StreamPipes 0.98.0 설정 재현(09-29 결정: UI 설정 제품은 설정을 파일로 내보내 스크립트로 재적용할 때만 인정).

    python /repo/harness/ingestbench/streampipes/setup.py export   # 한 번: UI(http://localhost:39088)에서 만든 어댑터·파이프라인을 파일로
    python /repo/harness/ingestbench/streampipes/setup.py apply    # 매 실행: 파일 → REST 로 재생성·시작

만들 것(첫 수동 설정 기준, 이후 파일이 정본):
  어댑터: Modbus(PLC4X) TCP plant-simulator:502, 홀딩 레지스터 0~23 float32 12개, 필드 이름 = 태그 이름(LT-101 …), 1000 ms
  파이프라인: 어댑터 스트림 → MQTT 싱크(host mosquitto, port 1883, topic edgex/telemetry, QoS1)
    → 하류 파서 downstream/streampipes.conf 가 {timestamp(ms), <태그>: 값} 평면 이벤트를 raw 레코드로 바꾼다.
REST 경로(0.9x): /streampipes-backend/api/v2/auth/login, /connect/master/adapters, /pipelines — [미검증: 기동 금지 중 작성].
④ 운영 부담 기록: 첫 설정은 UI 수동 1회 + export 필요(어댑터 JSON 은 사람이 쓰기 어려운 내부 모델).
"""
import json
import pathlib
import sys
import time
import urllib.error
import urllib.request

BASE = "http://backend:8030/streampipes-backend/api/v2"
USER, PASS = "admin@streampipes.apache.org", "admin"          # 0.98 설치 기본 관리자
SPEC = pathlib.Path(__file__).with_name("exported.json")
DROP = {"_id", "_rev", "elementId", "createdAt", "running", "rev", "couchDbId", "couchDbRev"}


def req(method, path, body=None, token=None):
    r = urllib.request.Request(BASE + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                               headers={"Content-Type": "application/json", "Accept": "application/json"})
    if token:
        r.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(r, timeout=30) as resp:
            t = resp.read().decode()
            return resp.status, (json.loads(t) if t.strip().startswith(("{", "[")) else t)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]


def login():
    for _ in range(90):
        try:
            code, body = req("POST", "/auth/login", {"username": USER, "password": PASS})
            if code == 200 and isinstance(body, dict):
                return body.get("accessToken") or body.get("token")
        except OSError:
            pass
        time.sleep(5)
    sys.exit("StreamPipes 로그인 실패(기동 미완료 또는 기본 계정 다름)")


def strip(o):
    if isinstance(o, dict):
        return {k: strip(v) for k, v in o.items() if k not in DROP}
    if isinstance(o, list):
        return [strip(v) for v in o]
    return o


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "apply"
    tok = login()
    if mode == "export":
        _, adapters = req("GET", "/connect/master/adapters", token=tok)
        _, pipelines = req("GET", "/pipelines", token=tok)
        pathlib.Path("/experiments/EXP-ING/raw/streampipes_exported.json").write_text(json.dumps({"adapters": adapters, "pipelines": pipelines}, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"내보냄: experiments/EXP-ING/raw/streampipes_exported.json (어댑터 {len(adapters)}, 파이프라인 {len(pipelines)}) → {SPEC.name} 로 복사하면 apply 정본")
        return
    if not SPEC.exists():
        sys.exit(f"{SPEC} 없음 — UI 에서 1회 만든 뒤 `setup.py export` 로 내보내야 재현 가능(② 실행 불가 사유로 기록)")
    spec = json.loads(SPEC.read_text(encoding="utf-8"))
    for a in spec["adapters"]:
        code, body = req("POST", "/connect/master/adapters", strip(a), tok)
        print("adapter", a.get("name"), code, str(body)[:200], flush=True)
        if code not in (200, 201):
            sys.exit("어댑터 재생성 실패")
        aid = body.get("elementId") if isinstance(body, dict) else None
        if aid:
            print("start", req("POST", f"/connect/master/adapters/{aid}/start", {}, tok)[0])
    time.sleep(5)
    for p in spec["pipelines"]:
        code, body = req("POST", "/pipelines", strip(p), tok)
        print("pipeline", p.get("name"), code, str(body)[:200], flush=True)
        if code not in (200, 201):
            sys.exit("파이프라인 재생성 실패")
        pid = (body.get("notifications") or [{}])[0].get("title") if isinstance(body, dict) else None
        pid = (body.get("elementId") if isinstance(body, dict) else None) or pid
        if pid:
            print("start", req("GET", f"/pipelines/{pid}/start", token=tok)[0])


if __name__ == "__main__":
    main()
