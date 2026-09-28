"""Apache StreamPipes 0.98.0 배포: V1 규칙을 StreamPipes 파이프라인(어댑터 → 처리 요소 → 싱크)으로 REST 로 조립·시작한다.

    python /repo/candidates/l4-streampipes/deploy.py     (tools 컨테이너 안, stage2.sh 가 호출)

StreamPipes 0.98 의 "compact" REST 를 쓴다(소스 release/0.98.0 에서 확인):
  POST /streampipes-backend/api/v2/connect/compact-adapters   CompactAdapter{id,name,appId,configuration,createOptions}
  POST /streampipes-backend/api/v2/compact-pipelines          CompactPipeline{id,name,pipelineElements[type,ref,id,connectedTo,configuration,output],createOptions}
  configuration = [{내부이름: 값}, …]. 대안(alternatives)은 선택값과 그 하위 항목을 한 맵에. 필드 매핑 값은 "s0::필드".
  어댑터는 만들 때 Kafka 토픽에서 표본을 읽어 스키마를 추정한다 → 만드는 동안 장치 "sp-warmup" 레코드를 흘린다(판정 장치가 아니라 평가에서 빠짐).

V1 규칙 → StreamPipes 요소(엔진 기능):
  입력      : Kafka 어댑터(org.apache.streampipes.connect.iiot.protocol.stream.kafka) exp.l4.raw, JSON 단일 객체, latest
  L4-01     : 규격(태그·상한/하한)마다 파이프라인 1개 = 숫자+문자 필터(filters.jvm.numericaltextfilter: tag MATCHES X AND value >/< 규격)
              → 정적 메타데이터(transformation.jvm.processor.staticmetadata: alert_type·severity·detector·detail 추가) → Kafka 싱크(exp.l4.alerts.streampipes)
  L4-02 시도: 이동 표준편차·Z-Score 요소는 없음. 가장 가까운 설치 요소 = Welford 변화 탐지(changedetection.jvm.welford, 누적 평균·분산 기반 CUSUM).
              태그마다 문자 필터 → Welford → 불리언 필터(changeDetectedHigh=True) → 메타데이터(ZSCORE) → 알람 싱크. V1(60행 창·|z|>3.5·5중 3)과 의미가 다름을 기록
  L4-03/04 시도: Siddhi 순서 요소(processors.siddhi.sequence, 입력 2개 + duration) — 과전류 필터·진동 필터를 두 입력으로, duration 10초.
              주의(소스 확인): 이 요소의 Siddhi 문장은 "from every not <입력1> for N sec" 로 두 번째 입력을 쓰지 않는다 → ②에서 결과로 확인
  L4-12     : ONNX·모델 추론 요소 없음(설치 요소 조사로 기록)
모든 요청의 성공·엔진 응답을 /experiments/EXP-L4/raw/stage2_<RUN>_attempts.jsonl 에 남긴다. 임계치 파이프라인이 하나도 안 서면 배포 실패.
"""
import csv
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.request

API = os.environ.get("SP_API", "http://backend:8030/streampipes-backend")
USER = os.environ.get("SP_INITIAL_ADMIN_EMAIL", "admin@streampipes.apache.org")
PW = os.environ.get("SP_INITIAL_ADMIN_PASSWORD", "admin")
BOOT = os.environ.get("BOOTSTRAP", "kafka:9092")
OUT = os.environ.get("ALERT_TOPIC", "exp.l4.alerts.streampipes")
WIN = int(os.environ.get("PATTERN_WINDOW_S", "10"))
LIMITS = "/repo/flink/sql/tag_limits.csv"
ATTEMPTS = f"/experiments/EXP-L4/raw/stage2_{os.environ.get('RUN', 'manual')}_attempts.jsonl"
ADAPTER_ID = "sp-l4-raw"
P = "org.apache.streampipes."
NEEDS = {
    "L4-01 임계치": r"threshold|limit|numerical",
    "L4-02 Z-Score": r"moving|average|welford|stddev|standard deviation|z-?score|trend",
    "L4-03/04 CEP": r"sequence|pattern|cep|absence",
    "L4-12 ONNX": r"onnx|inference|autoencoder|model",
}
TOKEN = {"v": None}


def call(method, path, body=None):
    h = {"Content-Type": "application/json", "Accept": "application/json"}
    if TOKEN["v"]:
        h["Authorization"] = f"Bearer {TOKEN['v']}"
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body is not None else None,
                                 headers=h)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except OSError as e:
        return 599, str(e)


def record(rule, feature, ok, error="", statement=""):
    print(rule, "|", feature, "|", ok, "|", str(error)[:300], flush=True)
    with open(ATTEMPTS, "a", encoding="utf-8") as f:
        f.write(json.dumps({"engine": "streampipes", "rule": rule, "feature": feature, "ok": ok, "error": str(error)[:2000],
                            "statement": statement[:3000], "at": time.time()}, ensure_ascii=False) + "\n")


def ok_response(code, txt):
    """compact API 는 200 이어도 본문에 실패 알림을 담을 수 있다(success=false)."""
    if code >= 300:
        return False
    try:
        j = json.loads(txt)
    except ValueError:
        return True
    return not (isinstance(j, dict) and j.get("success") is False)


def login():
    for _ in range(120):                                    # 첫 기동 시 백엔드가 요소를 설치하느라 수 분 걸린다
        code, txt = call("POST", "/api/v2/auth/login", {"username": USER, "password": PW})
        if code == 200:
            TOKEN["v"] = json.loads(txt).get("accessToken")
            return True
        time.sleep(5)
    record("설정", "POST /api/v2/auth/login", False, f"HTTP {code}: {txt[:500]}")
    return False


def names(txt):
    try:
        data = json.loads(txt)
    except ValueError:
        return []
    items = data if isinstance(data, list) else []
    return [(i.get("name") or "", i.get("appId") or i.get("elementId") or "", i.get("description") or "")
            for i in items if isinstance(i, dict)]


def probe():
    """설치된 요소를 읽고, 이후 쓸 요소가 설치될 때까지(최대 5분) 기다린다."""
    need = {P + "processors.filters.jvm.numericaltextfilter", P + "processors.transformation.jvm.processor.staticmetadata",
            P + "sinks.brokers.jvm.kafka"}
    elements = {}
    for _ in range(30):
        elements = {}
        for kind, path in (("processor", "/api/v2/sepas"), ("sink", "/api/v2/actions")):
            code, txt = call("GET", path)
            elements[kind] = names(txt) if code == 200 else []
        have = {a for lst in elements.values() for _, a, _ in lst}
        if need <= have:
            break
        time.sleep(10)
    record("설정", "설치된 처리 요소·싱크", bool(elements.get("processor")), "",
           json.dumps({k: [a for _, a, _ in v] for k, v in elements.items()}, ensure_ascii=False))
    for rule, pat in NEEDS.items():
        hits = [f"{k}:{a}" for k, lst in elements.items() for n, a, d in lst if re.search(pat, f"{n} {a} {d}", re.I)]
        record(rule, "설치 요소 검색 /" + pat + "/", bool(hits), "" if hits else "해당 요소 없음",
               json.dumps(hits, ensure_ascii=False))
    return {a for lst in elements.values() for _, a, _ in lst}


def warmup(stop):
    """어댑터 스키마 추정용 표본. 판정 장치(manifest)에 없는 장치라 evaluate 에서 빠진다."""
    try:
        from confluent_kafka import Producer
        p = Producer({"bootstrap.servers": BOOT})
    except Exception as e:                                   # 표본 발행 실패도 기록(어댑터 스키마 추정이 실패할 수 있음)
        record("입력", "스키마 추정용 표본 발행", False, f"{type(e).__name__}: {e}")
        return
    while not stop.is_set():
        rec = {"ts": time.time_ns(), "site": "AR-100", "device": "sp-warmup", "tag": "WARMUP", "value": 1.5,
               "quality": "GOOD", "trace_id": "warmup", "case": "warmup", "kind": "warmup", "emit_ns": time.time_ns()}
        p.produce("exp.l4.raw", key="WARMUP", value=json.dumps(rec))
        p.poll(0)
        time.sleep(0.2)
    p.flush(5)


def make_adapter():
    body = {"id": ADAPTER_ID, "name": "l4-raw", "description": "stage2 L4 입력(exp.l4.raw)",
            "appId": P + "connect.iiot.protocol.stream.kafka",
            "configuration": [
                {"access-mode": "unauthenticated-plain"},
                {"host": BOOT.split(":")[0]},
                {"port": int(BOOT.split(":")[1])},
                {"consumer-group": "group-id", "group-id-input": "streampipes-l4"},
                {"hide-internal-topics": True},
                {"topic": "exp.l4.raw"},
                {"auto.offset.reset": "latest"},
                {"additional-properties": "# none"},
                {"format": "Json", "json_options": "object"},
            ],
            "createOptions": {"persist": False, "start": True}}
    stop = threading.Event()
    t = threading.Thread(target=warmup, args=(stop,), daemon=True)
    t.start()
    time.sleep(3)
    code, txt = call("POST", "/api/v2/connect/compact-adapters", body)
    stop.set()
    ok = ok_response(code, txt)
    record("입력", "POST compact-adapters (Kafka 어댑터, 스키마 추정)", ok, "" if ok else f"HTTP {code}: {txt}",
           json.dumps(body, ensure_ascii=False))
    if not ok:
        return None
    for _ in range(30):
        code, txt = call("GET", "/api/v2/streams")
        if code == 200:
            for s in json.loads(txt):
                if s.get("correspondingAdapterId") == ADAPTER_ID or s.get("name") == "l4-raw":
                    props = [p.get("runtimeName") for p in (s.get("eventSchema") or {}).get("eventProperties", [])]
                    record("입력", "GET streams (어댑터가 만든 데이터 스트림)", True, "", json.dumps(
                        {"elementId": s.get("elementId"), "fields": props}, ensure_ascii=False))
                    return s["elementId"]
        time.sleep(3)
    record("입력", "GET streams", False, "어댑터의 데이터 스트림을 찾지 못함")
    return None


def meta(alert_type, severity, detector, detail):
    rows = [("alert_type", alert_type), ("severity", severity), ("detector", detector), ("detail", detail)]
    return [{"static-metadata-input": [{"static-metadata-input-runtime-name": k, "static-metadata-input-value": v,
                                        "static-metadata-input-datatype": "String",
                                        "static-metadata-input-label": k, "static-metadata-input-description": k}
                                       for k, v in rows]}]


def sink(ref, src, topic=OUT):
    return {"type": "sink", "ref": ref, "id": P + "sinks.brokers.jvm.kafka", "connectedTo": [src],
            "configuration": [{"topic": topic}, {"host": BOOT.split(":")[0]}, {"port": int(BOOT.split(":")[1])},
                              {"access-mode": "unauthenticated-plain"}, {"additional-properties": "# none"}]}


def pipeline(rule, pid, elements):
    body = {"id": pid, "name": pid, "description": rule, "pipelineElements": elements,
            "createOptions": {"persist": False, "start": True}}
    code, txt = call("POST", "/api/v2/compact-pipelines", body)
    ok = ok_response(code, txt)
    record(rule, f"POST compact-pipelines {pid}", ok, "" if ok else f"HTTP {code}: {txt}", json.dumps(body, ensure_ascii=False))
    return ok


def main():
    if not login():
        sys.exit("StreamPipes 로그인 실패")
    installed = probe()
    stream = make_adapter()
    if not stream:
        sys.exit("입력 어댑터를 만들지 못함")
    src = {"type": "stream", "ref": "raw", "id": stream}

    # ── L4-01 ──
    n_ok = 0
    for tag, unit, lsl, usl in (r[:4] for r in csv.reader(open(LIMITS, encoding="utf-8")) if len(r) >= 4):
        for kind, op, lim in (("USL", ">", usl), ("LSL", "<", lsl)):
            if not lim.strip():
                continue
            pid = f"l4-th-{tag}-{kind}".lower()
            els = [src,
                   {"type": "processor", "ref": "f", "id": P + "processors.filters.jvm.numericaltextfilter",
                    "connectedTo": ["raw"],
                    "configuration": [{"number-mapping": "s0::value"}, {"number-operation": op},
                                      {"number-value": float(lim)}, {"text-mapping": "s0::tag"},
                                      {"text-operation": "MATCHES"}, {"text-keyword": tag}]},
                   {"type": "processor", "ref": "m", "id": P + "processors.transformation.jvm.processor.staticmetadata",
                    "connectedTo": ["f"],
                    "configuration": meta(f"THRESHOLD_{kind}", "CRITICAL", "TIER1_RULE",
                                          f"{tag} {unit} / 규격 [{lsl.strip() or '-'}, {usl.strip() or '-'}]")},
                   sink("k", "m")]
            n_ok += pipeline("L4-01 임계치", pid, els)

    # ── L4-02 시도(Welford) ──
    if P + "processors.changedetection.jvm.welford" in installed:
        for tag, *_ in (r[:4] for r in csv.reader(open(LIMITS, encoding="utf-8")) if len(r) >= 4):
            els = [src,
                   {"type": "processor", "ref": "t", "id": P + "processors.filters.jvm.textfilter", "connectedTo": ["raw"],
                    "configuration": [{"text": "s0::tag"}, {"operation": "MATCHES"}, {"keyword": tag}]},
                   {"type": "processor", "ref": "w", "id": P + "processors.changedetection.jvm.welford", "connectedTo": ["t"],
                    "configuration": [{"number-mapping": "s0::value"}, {"param-k": 0.5}, {"param-h": 3.5}]},
                   {"type": "processor", "ref": "b", "id": P + "processors.filters.jvm.processor.booleanfilter",
                    "connectedTo": ["w"], "configuration": [{"boolean-mapping": "s0::changeDetectedHigh"}, {"value": "True"}]},
                   {"type": "processor", "ref": "m", "id": P + "processors.transformation.jvm.processor.staticmetadata",
                    "connectedTo": ["b"], "configuration": meta("ZSCORE", "WARNING", "TIER1_ZSCORE", "Welford CUSUM (V1 z-score 대체 시도)")},
                   sink("k", "m")]
            pipeline("L4-02 Z-Score", f"l4-z-{tag}".lower(), els)
    else:
        record("L4-02 Z-Score", "Welford 요소", False, "설치되지 않음")

    # ── L4-03/04 시도(Siddhi 순서 요소) ──
    if P + "processors.siddhi.sequence" in installed:
        els = [src,
               {"type": "processor", "ref": "oc", "id": P + "processors.filters.jvm.numericaltextfilter", "connectedTo": ["raw"],
                "configuration": [{"number-mapping": "s0::value"}, {"number-operation": ">"}, {"number-value": 9.6},
                                  {"text-mapping": "s0::tag"}, {"text-operation": "MATCHES"}, {"text-keyword": "IT-102"}]},
               {"type": "processor", "ref": "vib", "id": P + "processors.filters.jvm.numericaltextfilter", "connectedTo": ["raw"],
                "configuration": [{"number-mapping": "s0::value"}, {"number-operation": ">"}, {"number-value": 7.1},
                                  {"text-mapping": "s0::tag"}, {"text-operation": "MATCHES"}, {"text-keyword": "VT-101"}]},
               {"type": "processor", "ref": "seq", "id": P + "processors.siddhi.sequence", "connectedTo": ["oc", "vib"],
                "configuration": [{"duration": WIN}],
                "output": {"keep": ["s0::ts", "s0::site", "s0::device", "s0::tag", "s0::value"]}},
               {"type": "processor", "ref": "m", "id": P + "processors.transformation.jvm.processor.staticmetadata",
                "connectedTo": ["seq"], "configuration": meta("CEP_BEARING", "CRITICAL", "TIER1_CEP", "Siddhi sequence")},
               sink("k", "m")]
        pipeline("L4-03/04 CEP", "l4-cep", els)
    else:
        record("L4-03/04 CEP", "Siddhi 순서 요소", False, "설치되지 않음")

    code, txt = call("GET", "/api/v2/pipelines")
    running = [p.get("name") for p in (json.loads(txt) if code == 200 else []) if p.get("running")]
    record("설정", "GET pipelines (실행 중)", code == 200, "", json.dumps(running, ensure_ascii=False))
    if n_ok == 0:
        sys.exit("임계치 파이프라인을 하나도 시작하지 못함")


if __name__ == "__main__":
    main()
