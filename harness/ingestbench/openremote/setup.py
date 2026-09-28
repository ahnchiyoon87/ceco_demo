"""OpenRemote 1.31.1 설정 재현(09-29 결정: UI 설정 제품은 스크립트 재적용일 때만 인정).

    python /repo/harness/ingestbench/openremote/setup.py apply    # spec.json(또는 exported.json) → REST 로 에이전트·자산·서비스 사용자 생성
    python /repo/harness/ingestbench/openremote/setup.py export   # 현재 자산(에이전트 포함)을 exported.json 으로(UI 에서 고친 뒤 정본 갱신용)

만드는 것:
  - Modbus TCP 에이전트(plant-simulator:502, unit 1) + 자산 "AR-100 reactor-line-01" 의 속성 12개(이름 = 태그, 1000 ms 폴링, HR float32)
  - MQTT 서비스 사용자 ingestbench(읽기 권한) → 비밀값을 /experiments/EXP-ING/raw/cred_openremote.env 로 기록(lib.sh 가 읽어 검사기·하류에 전달)
REST(1.x): 토큰 = Keycloak password grant(client openremote), /api/master/asset, /api/master/user/... — 모델 필드 이름 [미검증: 기동 금지 중 작성].
실패하면 UI 로 1회 고친 뒤 export → exported.json 이 정본이 된다. ④ 운영 부담: 플랫폼 4컨테이너 + Keycloak 계정·토큰 관리.
"""
import json
import pathlib
import ssl
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

KC = "http://keycloak:8080/auth/realms/master/protocol/openid-connect/token"
API = "http://manager:8080/api/master"
ADMIN_PASS = "bench-secret"
SVC_USER, SVC_SECRET = "ingestbench", "ingestbench-secret"
HERE = pathlib.Path(__file__).parent
TAGS = [("LT-101", 0), ("LT-102", 2), ("TT-101", 4), ("TT-102", 6), ("PT-101", 8), ("FT-101", 10),
        ("FT-102", 12), ("IT-101", 14), ("IT-102", 16), ("VT-101", 18), ("pH-101", 20), ("CT-101", 22)]
CTX = ssl._create_unverified_context()


def req(method, url, body=None, token=None, form=False):
    data = urllib.parse.urlencode(body).encode() if form else (json.dumps(body).encode() if body is not None else None)
    r = urllib.request.Request(url, method=method, data=data,
                               headers={"Content-Type": "application/x-www-form-urlencoded" if form else "application/json"})
    if token:
        r.add_header("Authorization", "Bearer " + token)
    try:
        with urllib.request.urlopen(r, timeout=30, context=CTX) as resp:
            t = resp.read().decode()
            return resp.status, (json.loads(t) if t.strip().startswith(("{", "[")) else t)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:500]


def token():
    for _ in range(120):
        try:
            code, body = req("POST", KC, {"grant_type": "password", "client_id": "openremote", "username": "admin",
                                          "password": ADMIN_PASS}, form=True)
            if code == 200:
                return body["access_token"]
        except OSError:
            pass
        time.sleep(5)
    sys.exit("OpenRemote 토큰 실패(Keycloak 기동 미완료 또는 client 이름 다름)")


def spec():
    ex = HERE / "exported.json"
    if ex.exists():
        return json.loads(ex.read_text(encoding="utf-8"))
    agent = {"name": "AR-100 Modbus", "type": "ModbusTcpAgent", "realm": "master",
             "attributes": {"host": {"name": "host", "type": "hostOrIPAddress", "value": "plant-simulator"},
                            "port": {"name": "port", "type": "IPPortNumber", "value": 502},
                            "unitId": {"name": "unitId", "type": "integer", "value": 1}}}
    asset = {"name": "AR-100 reactor-line-01", "type": "ThingAsset", "realm": "master", "attributes": {
        t: {"name": t, "type": "number", "meta": {"agentLink": {"id": "__AGENT_ID__", "type": "ModbusAgentLink",
                                                               "readType": "HOLDING", "readAddress": hr, "readValueType": "FLOAT",
                                                               "registersAmount": 2, "pollingMillis": 1000}}}
        for t, hr in TAGS}}
    return {"assets": [agent, asset]}


def main():
    mode = sys.argv[1] if len(sys.argv) > 1 else "apply"
    tok = token()
    if mode == "export":
        code, assets = req("POST", f"{API}/asset/query", {"realm": {"name": "master"}}, tok)
        pathlib.Path("/experiments/EXP-ING/raw/openremote_exported.json").write_text(json.dumps({"assets": assets}, ensure_ascii=False, indent=1), encoding="utf-8")
        print("내보냄: experiments/EXP-ING/raw/openremote_exported.json → harness/ingestbench/openremote/exported.json 로 복사하면 apply 정본", code, len(assets) if isinstance(assets, list) else assets)
        return
    agent_id = None
    for a in spec()["assets"]:
        body = json.loads(json.dumps(a).replace("__AGENT_ID__", agent_id or ""))
        body.pop("id", None)
        code, res = req("POST", f"{API}/asset", body, tok)
        print("asset", a["name"], code, str(res)[:200], flush=True)
        if code not in (200, 201, 204):
            sys.exit("자산 생성 실패")
        if a["type"].endswith("Agent"):
            agent_id = res.get("id") if isinstance(res, dict) else None
    # MQTT 서비스 사용자(비밀값 고정 시도 → 실패 시 재발급 값 기록)
    code, res = req("POST", f"{API}/user/master/users", {"username": SVC_USER, "serviceAccount": True, "enabled": True,
                                                         "realm": "master"}, tok)
    print("service user", code, str(res)[:200], flush=True)
    uid = res.get("id") if isinstance(res, dict) else None
    secret = SVC_SECRET
    if uid:
        req("PUT", f"{API}/user/master/userRoles/{uid}", [{"name": "read"}, {"name": "read:assets"}], tok)
        c2, sec = req("GET", f"{API}/user/master/reset-secret/{uid}", token=tok)
        if c2 == 200 and isinstance(sec, str) and sec.strip():
            secret = sec.strip().strip('"')
    out = pathlib.Path("/experiments/EXP-ING/raw/cred_openremote.env")
    out.write_text(f'MQTT_USER="master:{SVC_USER}"\nMQTT_PASS="{secret}"\n', encoding="utf-8")
    print("자격증명 기록:", out)


if __name__ == "__main__":
    main()
