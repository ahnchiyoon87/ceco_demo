"""Apache StreamPipes 0.98.0 배포 준비·조사: 실행 중인 백엔드에서 설치된 파이프라인 요소를 읽어
V1 규칙마다 쓸 수 있는 요소가 있는지 기록한다(엔진 실행으로 확인, 문헌 아님).

    python /repo/candidates/l4-streampipes/probe.py     (tools 컨테이너 안, stage2.sh 가 호출)

StreamPipes 는 규칙을 "어댑터(입력) → 처리 요소 → 싱크" 파이프라인으로 GUI/REST 에서 조립한다.
  L4-01 임계치 : 처리 요소 중 Threshold/Limit 계열 존재 여부
  L4-02 Z-Score: 이동 통계(Moving average·Welford·표준편차) 계열 존재 여부 — 행 60개 창 + 5중 3 지속성까지 되는지는 요소 설정 항목으로 판정
  L4-03/04 CEP : Sequence·Pattern·CEP 계열 존재 여부
  L4-12 ONNX   : ONNX·모델 추론 계열 존재 여부
  입력/출력    : Kafka 어댑터·Kafka 싱크 존재 여부
파이프라인 자동 조립(REST 로 어댑터 생성 → 요소 연결 → 시작)은 요소 설명(JSON) 구조가 커서 이 스크립트는 조사까지만 한다.
찾은 요소로 임계치 파이프라인을 조립하는 것은 ② 첫 실행에서 요소 설명을 보고 이어서 한다(결과를 attempts 에 남김).
"""
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("SP_API", "http://streampipes-backend:8030/streampipes-backend")
USER = os.environ.get("SP_INITIAL_ADMIN_EMAIL", "admin@streampipes.apache.org")
PW = os.environ.get("SP_INITIAL_ADMIN_PASSWORD", "admin")
ATTEMPTS = f"/experiments/EXP-L4/raw/stage2_{os.environ.get('RUN', 'manual')}_attempts.jsonl"
NEEDS = {
    "L4-01 임계치": r"threshold|limit|filter",
    "L4-02 Z-Score": r"moving|average|welford|stddev|standard deviation|statistic|z-?score|trend",
    "L4-03/04 CEP": r"sequence|pattern|cep|absence|and\b|peak",
    "L4-12 ONNX": r"onnx|model|inference|autoencoder|ml\b",
    "입력(Kafka)": r"kafka",
}


def call(method, path, body=None, token=None):
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if token:
        h["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body else None, headers=h)
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except OSError as e:
        return 599, str(e)


def record(rule, feature, ok, error="", statement=""):
    print(rule, "|", feature, "|", ok, "|", error[:300], flush=True)
    with open(ATTEMPTS, "a", encoding="utf-8") as f:
        f.write(json.dumps({"engine": "streampipes", "rule": rule, "feature": feature, "ok": ok, "error": error[:2000],
                            "statement": statement[:3000], "at": time.time()}, ensure_ascii=False) + "\n")


def names(txt):
    try:
        data = json.loads(txt)
    except ValueError:
        return []
    items = data if isinstance(data, list) else data.get("list", data.get("elements", []))
    return [(i.get("name") or i.get("appId") or "", i.get("appId") or i.get("elementId") or "", i.get("description") or "")
            for i in items if isinstance(i, dict)]


def main():
    token = None
    for _ in range(120):                        # 백엔드 초기 설치(요소 등록)에 수 분 걸림
        code, txt = call("POST", "/api/v2/auth/login", {"username": USER, "password": PW})
        if code == 200:
            token = json.loads(txt).get("accessToken")
            break
        time.sleep(5)
    if not token:
        record("설정", "POST /api/v2/auth/login", False, f"로그인 실패: {code} {txt[:500]}")
        sys.exit("StreamPipes 로그인 실패")
    time.sleep(30)
    elements = {}
    for kind, path in (("processor", "/api/v2/sepas"), ("sink", "/api/v2/actions"),
                       ("adapter", "/api/v2/connect/master/description/adapters")):
        code, txt = call("GET", path, token=token)
        found = names(txt) if code == 200 else []
        elements[kind] = found
        record("설정", f"GET {path}", code == 200, "" if code == 200 else f"HTTP {code}: {txt[:500]}",
               json.dumps([n for n, _, _ in found], ensure_ascii=False))
    for rule, pat in NEEDS.items():
        hits = [f"{k}:{n} ({a})" for k, lst in elements.items() for n, a, d in lst
                if re.search(pat, f"{n} {a} {d}", re.I)]
        record(rule, "설치된 파이프라인 요소 검색 /" + pat + "/", bool(hits),
               "" if hits else "해당 요소 없음(설치된 요소 전체는 '설정' 기록 참조)", json.dumps(hits, ensure_ascii=False))
    if not elements.get("processor"):
        sys.exit("처리 요소 목록을 못 읽음")


if __name__ == "__main__":
    main()
