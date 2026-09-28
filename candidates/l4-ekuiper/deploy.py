"""eKuiper 2.4.2 규칙 배포: V1 규칙(flink/sql/02·03·04)을 eKuiper SQL 규칙으로 옮겨 REST(9081)로 등록한다.

    python /repo/candidates/l4-ekuiper/deploy.py            (tools 컨테이너 안, stage2.sh 가 호출)

엔진 기능만 쓴다. 이 스크립트는 규칙 문자열을 만들어 등록하는 배포 연결 코드다.
  L4-01 임계치  : 규격표(V1 tag_limits.csv)를 WHERE/CASE 식으로 펼친 규칙 1개(설정 파일 → 선언 규칙).
                  eKuiper 조회(lookup) 테이블은 memory·redis·sql 소스만 가능해 CSV 조인 대신 식으로 펼친다.
  L4-02 Z-Score : 태그마다 규칙 2단. ① WHERE tag=X + COUNTWINDOW(60,1) → avg·stddevs·count·last_value → memory 토픽
                  ② memory 스트림 WHERE tag=X AND n>=30 + COUNTWINDOW(5,1) → 위반 합 >= 3
                  (COUNTWINDOW 는 스트림 단위라 태그별 규칙으로 나눈다. 창이 찰 때부터 발화 → 태그별 처음 59행 미판정)
  L4-03/04 CEP  : 분석 함수 latest() OVER (PARTITION BY device WHEN 과전류) 로 장치별 마지막 과전류 시각을 달고,
                  진동 초과 행에서 0 <= ts-과전류 < 10초 이고 직전 매칭과 다른 과전류일 때만(lag(...) != oc_ts) 알람
                  → MATCH_RECOGNIZE 의 AFTER MATCH SKIP PAST LAST ROW 를 분석 함수로 근사. 전용 CEP 문법은 없음.
  L4-12 ONNX    : 시도 — 문서의 onnx 함수 플러그인 호출 규칙을 등록해 본다(-full 이미지에 플러그인 미설치면 엔진 오류가 기록됨).
                  V1 은 장치별 1초 처리시각 표본 10개 창이라 같은 입력을 만들 창도 없다(COUNTWINDOW 는 동적 키별로 못 나눔).
각 규칙은 따로 등록하고 성공·엔진 오류를 /experiments/EXP-L4/raw/stage2_<RUN>_attempts.jsonl 에 남긴다(하나가 실패해도 계속).
알려진 차이: 이벤트 시각 정렬·워터마크(V1 5초) 없이 도착 순서로 처리(S07 늦은 진동이 V1 과 달라질 수 있음).
"""
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("EKUIPER_API", "http://ekuiper:9081")
LIMITS = "/repo/flink/sql/tag_limits.csv"
OUT = os.environ.get("ALERT_TOPIC", "exp.l4.alerts.ekuiper")
WIN = int(os.environ.get("PATTERN_WINDOW_S", "10"))        # L4-10: 창 변경은 이 값(선언)만 바꿔 재배포
OPTS = {"qos": 1, "checkpointInterval": 10000, "sendError": False}   # V1 체크포인트 10초에 맞춤
KAFKA = {"kafka": {"brokers": "kafka:9092", "topic": OUT, "sendSingle": True}}


def call(method, path, body=None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except OSError as e:
        return 599, str(e)


ATTEMPTS = f"/experiments/EXP-L4/raw/stage2_{os.environ.get('RUN', 'manual')}_attempts.jsonl"
RULE = {"current": "setup"}


def attempt(rule, feature, ok, error="", statement=""):
    with open(ATTEMPTS, "a", encoding="utf-8") as f:
        f.write(json.dumps({"engine": "ekuiper", "rule": rule, "feature": feature, "ok": ok, "error": error[:2000],
                            "statement": statement[:3000], "at": time.time()}, ensure_ascii=False) + chr(10))


def must(method, path, body=None):
    code, txt = call(method, path, body)
    print(method, path, code, txt[:200], flush=True)
    ok = code < 300
    attempt(RULE["current"], f"{method} {path}", ok, "" if ok else f"HTTP {code}: {txt}", json.dumps(body, ensure_ascii=False))
    if not ok:
        FAILED.append(RULE["current"])
    return ok


FAILED = []


def q(s):
    return '"' + s.replace('"', '\\"') + '"'


def main():
    for _ in range(60):
        if call("GET", "/")[0] == 200:
            break
        time.sleep(2)
    lim = [r for r in csv.reader(open(LIMITS, encoding="utf-8")) if len(r) >= 4]
    # 재배포(L4-10 창 변경 등)를 위해 기존 규칙·스트림을 먼저 지운다(data 볼륨에 영속되어 남아 있을 수 있음)
    code, txt = call("GET", "/rules")
    for r in (json.loads(txt) if code == 200 else []):
        print("DELETE rule", r["id"], call("DELETE", f"/rules/{r['id']}")[0])
    for name in ("raw", "zmid", "cepmid"):
        call("DELETE", f"/streams/{name}")

    must("POST", "/streams", {"sql": 'CREATE STREAM raw (ts BIGINT, site STRING, device STRING, tag STRING, '
                                     'value FLOAT, quality STRING) WITH (DATASOURCE="exp.l4.raw", TYPE="kafka", '
                                     'FORMAT="json", CONF_KEY="l4")'})
    must("POST", "/streams", {"sql": 'CREATE STREAM zmid () WITH (DATASOURCE="l4/z", TYPE="memory", FORMAT="json")'})
    must("POST", "/streams", {"sql": 'CREATE STREAM cepmid () WITH (DATASOURCE="l4/cep", TYPE="memory", FORMAT="json")'})

    # ── L4-01 ──
    RULE["current"] = "L4-01 임계치"
    conds, usl_c, det = [], [], []
    for tag, unit, lsl, usl in (r[:4] for r in lim):
        parts = []
        if usl.strip():
            parts.append(f"value > {float(usl)}")
            usl_c.append(f"(tag = {q(tag)} AND value > {float(usl)})")
        if lsl.strip():
            parts.append(f"value < {float(lsl)}")
        if parts:
            conds.append(f"(tag = {q(tag)} AND ({' OR '.join(parts)}))")
            det.append(f"WHEN tag = {q(tag)} THEN "
                       + q(f" {unit} / 규격 [{lsl.strip() or '-'}, {usl.strip() or '-'}]"))
    sql = (f"SELECT ts, site, device, tag, value, "
           f"CASE WHEN {' OR '.join(usl_c)} THEN \"THRESHOLD_USL\" ELSE \"THRESHOLD_LSL\" END AS alert_type, "
           f"\"CRITICAL\" AS severity, \"TIER1_RULE\" AS detector, "
           f"concat(tag, \" = \", format(round(value, 3), \"\"), CASE {' '.join(det)} ELSE \"\" END) AS detail "
           f"FROM raw WHERE {' OR '.join(conds)}")
    must("POST", "/rules", {"id": "l4_threshold", "sql": sql, "actions": [KAFKA], "options": OPTS})

    # ── L4-02 ──
    RULE["current"] = "L4-02 Z-Score"
    z = "CASE WHEN sd > 0.000000001 THEN abs(value - mu) / sd ELSE 0.0 END"
    for tag, *_ in lim:
        t = tag.replace("-", "_")
        must("POST", "/rules", {"id": "l4_z1_" + t, "options": OPTS,
                                "actions": [{"memory": {"topic": "l4/z", "sendSingle": True}}],
                                "sql": f"SELECT last_value(ts, true) AS ts, last_value(site, true) AS site, "
                                       f"last_value(device, true) AS device, last_value(tag, true) AS tag, "
                                       f"last_value(value, true) AS value, count(*) AS n, avg(value) AS mu, "
                                       f"stddevs(value) AS sd FROM raw WHERE tag = {q(tag)} GROUP BY COUNTWINDOW(60, 1)"})
        must("POST", "/rules", {"id": "l4_z2_" + t, "options": OPTS, "actions": [KAFKA],
                                "sql": f"SELECT last_value(ts, true) AS ts, last_value(site, true) AS site, "
                                       f"last_value(device, true) AS device, last_value(tag, true) AS tag, "
                                       f"last_value(value, true) AS value, \"ZSCORE\" AS alert_type, "
                                       f"\"WARNING\" AS severity, \"TIER1_ZSCORE\" AS detector, "
                                       f"concat(last_value(tag, true), \" 최근5중 \", "
                                       f"format(sum(CASE WHEN {z} > 3.5 THEN 1 ELSE 0 END), \"\"), \"회 위반\") AS detail "
                                       f"FROM zmid WHERE tag = {q(tag)} AND n >= 30 GROUP BY COUNTWINDOW(5, 1) "
                                       f"HAVING sum(CASE WHEN {z} > 3.5 THEN 1 ELSE 0 END) >= 3"})

    # ── L4-03/04 ──
    RULE["current"] = "L4-03/04 CEP(분석 함수 근사)"
    oc = 'tag = "IT-102" AND value > 9.6'
    must("POST", "/rules", {"id": "l4_cep1", "options": OPTS,
                            "actions": [{"memory": {"topic": "l4/cep", "sendSingle": True}}],
                            "sql": f"SELECT ts, site, device, tag, value, "
                                   f"latest(ts, 0) OVER (PARTITION BY device WHEN {oc}) AS oc_ts, "
                                   f"latest(value, 0) OVER (PARTITION BY device WHEN {oc}) AS oc_val "
                                   f"FROM raw WHERE tag = \"IT-102\" OR tag = \"VT-101\""})
    m = f'tag = "VT-101" AND value > 7.1 AND oc_ts > 0 AND ts >= oc_ts AND ts - oc_ts < {WIN * 1_000_000_000}'
    must("POST", "/rules", {"id": "l4_cep2", "options": OPTS, "actions": [KAFKA],
                            "sql": f"SELECT ts, site, device, \"VT-101\" AS tag, value, \"CEP_BEARING\" AS alert_type, "
                                   f"\"CRITICAL\" AS severity, \"TIER1_CEP\" AS detector, "
                                   f"concat(\"교반기 전류 \", format(round(oc_val, 2), \"\"), \"A (정격 120% 초과) 후 \", "
                                   f"format((ts - oc_ts) / 1000000000, \"\"), \"초 내 진동 \", format(round(value, 2), \"\"), "
                                   f"\"mm/s 상회 → 베어링 열화 의심\") AS detail "
                                   f"FROM cepmid WHERE {m} AND lag(oc_ts, 1, 0) OVER (PARTITION BY device WHEN {m}) != oc_ts"})

    # ── L4-12 ONNX 시도: 문서(guide/ai/onnx.md)의 함수 플러그인 호출 형태 ──
    RULE["current"] = "L4-12 ONNX"
    code, txt = call("GET", "/plugins/functions")
    attempt("L4-12 ONNX", "GET /plugins/functions (설치된 함수 플러그인)", code < 300, "" if code < 300 else txt, txt[:500])
    must("POST", "/rules", {"id": "l4_onnx_try", "options": OPTS,
                            "actions": [{"memory": {"topic": "l4/onnx", "sendSingle": True}}],
                            "sql": "SELECT onnx(\"autoencoder\", value) AS score FROM raw"})

    time.sleep(5)
    _, txt = call("GET", "/rules")
    rules = json.loads(txt)
    bad = [(r["id"], r.get("status")) for r in rules if str(r.get("status", "")).lower() != "running"]
    print("rules", len(rules), "not running", bad, "등록 실패 규칙", FAILED, flush=True)
    for rid, st in bad:
        attempt("rule status", rid, False, f"status={st}: {call('GET', f'/rules/{rid}/status')[1][:1500]}")
    if not any(r.get("id") == "l4_threshold" for r in rules):
        sys.exit("임계치 규칙조차 등록 못 함 — 배포 실패")


if __name__ == "__main__":
    main()
