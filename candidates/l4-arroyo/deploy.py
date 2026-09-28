"""Arroyo 0.15.0 배포(REST 5115): V1 규칙을 파이프라인으로 하나씩 낸다.

    python /repo/candidates/l4-arroyo/deploy.py        (tools 컨테이너 안, stage2.sh 가 호출)

엔진 기능: Kafka 소스·싱크(JSON), SQL 파이프라인, 체크포인트, UDF.
규격표: Arroyo 는 정적(조회) 테이블 커넥터가 없어 V1 tag_limits.csv 를 WHERE/CASE 식으로 펼친다(설정 → 선언 규칙).
  L4-01 임계치 : 표현
  L4-02 Z-Score: 시도 — 행 프레임 OVER 창(문서: 창 함수는 PARTITION BY 에 스트리밍 창 필요)
  L4-03/04 CEP : 시도 — V1 MATCH_RECOGNIZE 그대로(문서에 없음)
  L4-12 ONNX   : 시도 — Python UDF 에서 onnxruntime import(문서: 의존성 동적 설치 불가)
각 시도의 성공·엔진 오류를 /experiments/EXP-L4/raw/stage2_<RUN>_attempts.jsonl 에 남기고 계속한다.
"""
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("ARROYO_API", "http://arroyo:5115/api/v1")
LIMITS = "/repo/flink/sql/tag_limits.csv"
ATTEMPTS = f"/experiments/EXP-L4/raw/stage2_{os.environ.get('RUN', 'manual')}_attempts.jsonl"

SRC = """CREATE TABLE raw (ts BIGINT, site TEXT, device TEXT, tag TEXT, value DOUBLE, quality TEXT)
WITH (connector = 'kafka', bootstrap_servers = 'kafka:9092', topic = 'exp.l4.raw', type = 'source',
      format = 'json', 'source.offset' = 'latest');
CREATE TABLE alerts (ts BIGINT, site TEXT, device TEXT, tag TEXT, value DOUBLE, alert_type TEXT, severity TEXT,
      detector TEXT, detail TEXT)
WITH (connector = 'kafka', bootstrap_servers = 'kafka:9092', topic = 'exp.l4.alerts.arroyo', type = 'sink', format = 'json');
"""


def call(method, path, body=None):
    req = urllib.request.Request(API + path, method=method, data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except OSError as e:
        return 599, str(e)


def record(rule, feature, ok, error="", statement=""):
    print(rule, feature, ok, error[:300], flush=True)
    with open(ATTEMPTS, "a", encoding="utf-8") as f:
        f.write(json.dumps({"engine": "arroyo", "rule": rule, "feature": feature, "ok": ok, "error": error[:2000],
                            "statement": statement[:3000], "at": time.time()}, ensure_ascii=False) + "\n")


def pipeline(rule, name, query, udfs=None):
    body = {"name": name, "query": query, "parallelism": 1}
    if udfs:
        body["udfs"] = udfs
    code, txt = call("POST", "/pipelines", body)
    if code >= 300:
        record(rule, "POST /pipelines", False, f"HTTP {code}: {txt}", query)
        return False
    pid = json.loads(txt).get("id")
    for _ in range(40):
        c, t = call("GET", f"/pipelines/{pid}/jobs")
        jobs = json.loads(t).get("data", []) if c == 200 else []
        states = [j.get("state") for j in jobs]
        if "Running" in states:
            record(rule, "POST /pipelines → Running", True, "", query)
            return True
        if any(s in ("Failed", "Stopped") for s in states):
            record(rule, "잡 상태", False, f"{states} {[j.get('failureMessage') for j in jobs]}", query)
            return False
        time.sleep(3)
    record(rule, "잡 상태", False, "90초 안에 Running 도달 못 함", query)
    return False


def main():
    for _ in range(90):
        if call("GET", "/pipelines")[0] == 200:
            break
        time.sleep(2)
    conds, usl_c, det = [], [], []
    for tag, unit, lsl, usl in (r[:4] for r in csv.reader(open(LIMITS, encoding="utf-8")) if len(r) >= 4):
        parts = []
        if usl.strip():
            parts.append(f"value > {float(usl)}")
            usl_c.append(f"(tag = '{tag}' AND value > {float(usl)})")
        if lsl.strip():
            parts.append(f"value < {float(lsl)}")
        if parts:
            conds.append(f"(tag = '{tag}' AND ({' OR '.join(parts)}))")
            det.append(f"WHEN tag = '{tag}' THEN ' {unit} / 규격 [{lsl.strip() or '-'}, {usl.strip() or '-'}]'")
    th = pipeline("L4-01 임계치", "l4-threshold", SRC + f"""INSERT INTO alerts
SELECT ts, site, device, tag, value,
       CASE WHEN {' OR '.join(usl_c)} THEN 'THRESHOLD_USL' ELSE 'THRESHOLD_LSL' END AS alert_type,
       'CRITICAL' AS severity, 'TIER1_RULE' AS detector,
       concat(tag, ' = ', CAST(round(value, 3) AS TEXT), CASE {' '.join(det)} ELSE '' END) AS detail
FROM raw WHERE {' OR '.join(conds)};""")

    pipeline("L4-02 Z-Score", "l4-zscore", SRC + """INSERT INTO alerts
SELECT ts, site, device, tag, value, 'ZSCORE', 'WARNING', 'TIER1_ZSCORE', 'z' FROM (
  SELECT *, sum(viol) OVER (PARTITION BY tag ORDER BY ts ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS viol_run FROM (
    SELECT *, CASE WHEN sd > 1e-9 AND abs(value - mu) / sd > 3.5 THEN 1 ELSE 0 END AS viol FROM (
      SELECT ts, site, device, tag, value,
        avg(value) OVER (PARTITION BY tag ORDER BY ts ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS mu,
        stddev(value) OVER (PARTITION BY tag ORDER BY ts ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS sd,
        count(*) OVER (PARTITION BY tag ORDER BY ts ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS n
      FROM raw) a WHERE n >= 30) b) c
WHERE viol_run >= 3;""")

    pipeline("L4-03/04 CEP", "l4-cep", SRC + """INSERT INTO alerts
SELECT ts, site, device, tag, value, 'CEP_BEARING', 'CRITICAL', 'TIER1_CEP', 'cep'
FROM (SELECT * FROM raw WHERE tag IN ('IT-102', 'VT-101'))
MATCH_RECOGNIZE (PARTITION BY device ORDER BY ts
  MEASURES LAST(VIB.ts) AS ts, LAST(VIB.site) AS site, 'VT-101' AS tag, LAST(VIB.value) AS value
  ONE ROW PER MATCH AFTER MATCH SKIP PAST LAST ROW
  PATTERN (OVERCURRENT OTHER*? VIB) WITHIN INTERVAL '10' SECOND
  DEFINE OVERCURRENT AS OVERCURRENT.tag = 'IT-102' AND OVERCURRENT.value > 9.6,
         VIB AS VIB.tag = 'VT-101' AND VIB.value > 7.1);""")

    udf = "from arroyo_udf_python import udf\nimport onnxruntime\n\n@udf\ndef onnx_probe(x: float) -> float:\n    return x\n"
    code, txt = call("POST", "/udfs/validate", {"definition": udf, "language": "python"})
    ok = code < 300 and not (json.loads(txt).get("errors") if code < 300 and txt.strip().startswith("{") else True)
    record("L4-12 ONNX", "POST /udfs/validate (python, import onnxruntime)", ok, "" if ok else f"HTTP {code}: {txt}", udf)
    if ok:
        pipeline("L4-12 ONNX", "l4-onnx", SRC + "INSERT INTO alerts SELECT ts, site, device, tag, onnx_probe(value), "
                 "'ML_AUTOENCODER', 'WARNING', 'TIER2_ML', 'probe' FROM raw WHERE false;",
                 udfs=[{"definition": udf, "language": "python"}])
    if not th:
        sys.exit("임계치 파이프라인조차 실행 못 함")


if __name__ == "__main__":
    main()
