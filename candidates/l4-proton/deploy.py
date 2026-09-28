"""Timeplus Proton 3.0.31 배포(HTTP 8123, ClickHouse 호환): V1 규칙을 Proton SQL 로 하나씩 낸다.

    python /repo/candidates/l4-proton/deploy.py        (tools 컨테이너 안, stage2.sh 가 호출)

엔진 기능: Kafka 외부 스트림(JSONEachRow) 읽기·쓰기, 스트림↔table() 조인, 구체화 뷰 INTO 외부 스트림.
  L4-01 임계치 : 표현(구체화 뷰)
  L4-02 Z-Score: 시도 — 행 프레임 OVER 창 + stddev_samp 구체화 뷰(문서에 스트리밍 행 프레임·stddev 없음)
  L4-03/04 CEP : 시도 — V1 MATCH_RECOGNIZE 를 그대로(문서에 없음)
  L4-12 ONNX   : 시도 — Python UDF 에서 onnxruntime import
각 문장의 성공·엔진 오류를 /experiments/EXP-L4/raw/stage2_<RUN>_attempts.jsonl 에 남기고 계속한다(엔진 실행으로 기능 불가 확정).
"""
import csv
import json
import os
import sys
import time
import urllib.error
import urllib.request

API = os.environ.get("PROTON_HTTP", "http://proton:8123/")
LIMITS = "/repo/flink/sql/tag_limits.csv"
ATTEMPTS = f"/experiments/EXP-L4/raw/stage2_{os.environ.get('RUN', 'manual')}_attempts.jsonl"
OUT = "exp.l4.alerts.proton"


def run(sql):
    req = urllib.request.Request(API, data=sql.encode("utf-8"), method="POST")
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, r.read().decode()
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()
    except OSError as e:
        return 599, str(e)


def attempt(rule, sql):
    code, txt = run(sql)
    ok = code < 300
    print(code, rule, txt[:300].strip(), flush=True)
    with open(ATTEMPTS, "a", encoding="utf-8") as f:
        f.write(json.dumps({"engine": "proton", "rule": rule, "feature": sql.split("(")[0][:80], "ok": ok,
                            "error": "" if ok else f"HTTP {code}: {txt[:2000]}", "statement": sql[:3000],
                            "at": time.time()}, ensure_ascii=False) + "\n")
    return ok


def main():
    for _ in range(90):
        if run("SELECT 1")[0] == 200:
            break
        time.sleep(2)
    cols = "ts int64, site string, device string, tag string, `value` float64"
    kafka = "type='kafka', brokers='kafka:9092', data_format='JSONEachRow', one_message_per_row=true"
    ok = attempt("소스", f"CREATE EXTERNAL STREAM IF NOT EXISTS raw_ext ({cols}, quality string) "
                         f"SETTINGS {kafka}, topic='exp.l4.raw'")
    ok &= attempt("싱크", f"CREATE EXTERNAL STREAM IF NOT EXISTS alerts_ext ({cols}, alert_type string, severity string, "
                         f"detector string, detail string) SETTINGS {kafka}, topic='{OUT}'")
    ok &= attempt("규격표", "CREATE STREAM IF NOT EXISTS tag_limits (tag string, unit string, lsl nullable(float64), "
                           "usl nullable(float64))")
    rows = [f"('{t}', '{u}', {l.strip() or 'NULL'}, {h.strip() or 'NULL'})"
            for t, u, l, h in (r[:4] for r in csv.reader(open(LIMITS, encoding="utf-8")) if len(r) >= 4)]
    ok &= attempt("규격표", "INSERT INTO tag_limits (tag, unit, lsl, usl) VALUES " + ", ".join(rows))
    time.sleep(3)
    th = attempt("L4-01 임계치", "CREATE MATERIALIZED VIEW IF NOT EXISTS mv_threshold INTO alerts_ext AS "
                 "SELECT r.ts AS ts, r.site AS site, r.device AS device, r.tag AS tag, r.`value` AS `value`, "
                 "if(l.usl IS NOT NULL AND r.`value` > l.usl, 'THRESHOLD_USL', 'THRESHOLD_LSL') AS alert_type, "
                 "'CRITICAL' AS severity, 'TIER1_RULE' AS detector, "
                 "concat(r.tag, ' = ', to_string(round(r.`value`, 3)), ' ', l.unit, ' / 규격 [', "
                 "if(l.lsl IS NULL, '-', to_string(l.lsl)), ', ', if(l.usl IS NULL, '-', to_string(l.usl)), ']') AS detail "
                 "FROM raw_ext AS r INNER JOIN table(tag_limits) AS l ON r.tag = l.tag "
                 "WHERE (l.usl IS NOT NULL AND r.`value` > l.usl) OR (l.lsl IS NOT NULL AND r.`value` < l.lsl)")

    attempt("L4-02 Z-Score", "CREATE MATERIALIZED VIEW IF NOT EXISTS mv_zscore INTO alerts_ext AS "
            "SELECT ts, site, device, tag, `value`, 'ZSCORE' AS alert_type, 'WARNING' AS severity, "
            "'TIER1_ZSCORE' AS detector, 'z' AS detail FROM ("
            " SELECT *, sum(viol) OVER (PARTITION BY tag ORDER BY _tp_time ROWS BETWEEN 4 PRECEDING AND CURRENT ROW) AS viol_run"
            " FROM (SELECT *, if(sd > 1e-9 AND abs(`value` - mu) / sd > 3.5, 1, 0) AS viol FROM ("
            "  SELECT ts, site, device, tag, `value`, _tp_time,"
            "   avg(`value`) OVER (PARTITION BY tag ORDER BY _tp_time ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS mu,"
            "   stddev_samp(`value`) OVER (PARTITION BY tag ORDER BY _tp_time ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS sd,"
            "   count() OVER (PARTITION BY tag ORDER BY _tp_time ROWS BETWEEN 59 PRECEDING AND CURRENT ROW) AS n"
            "  FROM raw_ext) WHERE n >= 30)) WHERE viol_run >= 3")
    attempt("L4-03/04 CEP", "CREATE MATERIALIZED VIEW IF NOT EXISTS mv_cep INTO alerts_ext AS "
            "SELECT ts, site, device, tag, `value`, 'CEP_BEARING' AS alert_type, 'CRITICAL' AS severity, "
            "'TIER1_CEP' AS detector, 'cep' AS detail FROM (SELECT * FROM raw_ext WHERE tag IN ('IT-102', 'VT-101')) "
            "MATCH_RECOGNIZE (PARTITION BY device ORDER BY _tp_time "
            "MEASURES LAST(VIB.ts) AS ts, LAST(VIB.site) AS site, 'VT-101' AS tag, LAST(VIB.`value`) AS `value` "
            "ONE ROW PER MATCH AFTER MATCH SKIP PAST LAST ROW "
            "PATTERN (OVERCURRENT OTHER*? VIB) WITHIN INTERVAL '10' SECOND "
            "DEFINE OVERCURRENT AS OVERCURRENT.tag = 'IT-102' AND OVERCURRENT.`value` > 9.6, "
            "VIB AS VIB.tag = 'VT-101' AND VIB.`value` > 7.1)")
    attempt("L4-12 ONNX", "CREATE OR REPLACE FUNCTION onnx_probe(x float64) RETURNS float64 LANGUAGE PYTHON AS $$\n"
            "import onnxruntime\n"
            "def onnx_probe(x):\n"
            "    return [v for v in x]\n"
            "$$")
    attempt("L4-12 ONNX", "SELECT onnx_probe(1.0)")
    print(run("SHOW STREAMS")[1][:800])
    if not (ok and th):
        sys.exit("소스·임계치 배포 실패")


if __name__ == "__main__":
    main()
