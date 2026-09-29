"""시계열 저장 비교 ② 측정 클라이언트 (EXP-TS, 측정 도구 — 솔루션 부품 아님).

    python /repo/harness/tsbench/ts_stage2.py load    --engine influx29 [--hours 24]
    python /repo/harness/tsbench/ts_stage2.py query   --engine influx29 [--repeat 20]
    python /repo/harness/tsbench/ts_stage2.py fresh   --engine influx29          # 12행/초 60초 → 조회 가능해질 때까지(화면값=이력값 E7 전제)
    python /repo/harness/tsbench/ts_stage2.py r06     --engine influx29          # ④ R06 훅: Telegraf 1.40 경유 12행/초, 호스트가 DB 5분 정지
    python /repo/harness/tsbench/ts_stage2.py summarize --engine influx29

데이터(V1 측정값 이름·태그 그대로, harness/SCHEMA.md · telegraf/sink.conf):
  process_raw  : 12태그 × 1초, 태그 site/device/tag/quality, 필드 value. 결측(레코드 부재) 0.47% (V1: 결측은 부재로만 드러남)
  process      : clean — 결측 자리를 quality=INTERPOLATED_LINEAR 로 채운 전체
  anomaly      : 1초 1행, 태그 site/device/top_contributors, 필드 reconstruction_error·threshold·inference_ms·is_anomaly
  alerts       : 5분 1건, 태그 site/device/tag/alert_type/severity/detector, 필드 value·detail(문자열, 한글 포함)
ts = 초×1e9 + 213181400ns(V1 실측처럼 초 미만 자리 존재). 창·경계는 초 단위.
질의(V1이 실제로 쓰는 것만, 엔진별 번역):
  evidence   : ai-layer operations/evidence.py history() — 4태그, [t-30s, t+15s), time 정렬, limit 2001 (20개 시점)
  evidence300: 같은 질의, 창 상한 300s
  current    : pipeline.py historian_status — 12태그 최근 30초
  trend_1h / trend_24h : grafana 01-process 레벨 패널 — process mean, 창 10s / 60s
  quality_24h: 01-process 품질 패널 — process count by quality, 60s
  anomaly_24h: 02-anomaly 재구성오차·임계치 mean 60s / anomaly_count: is_anomaly==true count
  alerts_last100 / alerts_rate: 03-alerts 이력 100건 desc / detector별 60s count
  long_*     : --hours > 72 일 때만(F05 72h 초과 이력, InfluxDB 3 Core 432파일 한도 확인)
정답: 생성기가 결정적이므로 모든 질의의 기대값을 파이썬으로 계산해 엔진 결과와 대조(correct=true/false).
결과: /experiments/EXP-TS/raw/<engine>_<phase>.json → summarize → /experiments/EXP-TS/stage2_<engine>.json
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import math
import os
import pathlib
import random
import sys
import time
import uuid
from datetime import datetime, timezone

import requests

sys.path.insert(0, "/repo/harness/benchcommon")
import telemetry as T  # noqa: E402

RAW = pathlib.Path("/experiments/EXP-TS/raw")
SITE, DEV = T.SITE, T.DEVICE0
SUB = 213_181_400
EVID_TAGS = ["IT-102", "VT-101", "TT-101", "TT-102"]
TREND_TAGS = ["LT-101", "LT-102"]
DETECTORS = ["TIER1_RULE", "TIER1_ZSCORE", "TIER1_CEP", "TIER2_ML"]
ALERT_TAGS = ["IT-102", "VT-101", "TT-101"]
BATCH = 5000        # V1 telegraf-sink metric_batch_size


# ───────────────────────────── 생성기·정답 ─────────────────────────────
def dropped(s, k):
    return (s * 12 + k) % 211 == 0


def rec_err(s):
    return 0.05 if (s % 3600) < 30 else round(0.012 + 0.005 * math.sin(s / 300), 6)


def alert_at(s):
    i = s // 300
    tag = ALERT_TAGS[i % 3]
    return {"tag": tag, "alert_type": T.ALERT_TYPES[i % 5], "severity": "CRITICAL" if i % 2 else "WARNING",
            "detector": DETECTORS[i % 4], "value": round(T.value(tag, s), 4),
            "detail": f"{tag} = {T.value(tag, s):.3f} / 규격 [-, 9.6] \"bench\""}


def gen(start_s, end_s):
    """1시간 단위로 (측정값, 행 목록) 을 내준다. 행 = dict(ts, tags, fields)."""
    for h0 in range(start_s, end_s, 3600):
        raw, clean, anom, alerts = [], [], [], []
        for s in range(h0, min(h0 + 3600, end_s)):
            ts = s * 1_000_000_000 + SUB
            for k, tag in enumerate(T.TAG_NAMES):
                v = T.value(tag, s)
                d = dropped(s, k)
                base = {"site": SITE, "device": DEV, "tag": tag}
                if not d:
                    raw.append((ts, base | {"quality": "GOOD"}, {"value": v}))
                clean.append((ts, base | {"quality": "INTERPOLATED_LINEAR" if d else "GOOD"}, {"value": v}))
            e = rec_err(s)
            anom.append((ts, {"site": SITE, "device": DEV, "top_contributors": "CT-101(44%), pH-101(24%), IT-102(19%)"},
                         {"reconstruction_error": e, "threshold": 0.0351, "inference_ms": 0.45, "is_anomaly": e > 0.0351}))
            if s % 300 == 0:
                a = alert_at(s)
                alerts.append((ts, {"site": SITE, "device": DEV, "tag": a["tag"], "alert_type": a["alert_type"],
                                    "severity": a["severity"], "detector": a["detector"]},
                               {"value": a["value"], "detail": a["detail"]}))
        yield {"process_raw": raw, "process": clean, "anomaly": anom, "alerts": alerts}


class Truth:
    def evidence(self, tags, a, b, limit=2001):
        out = []
        for s in range(a, b):
            for k, tag in enumerate(T.TAG_NAMES):
                if tag in tags and not dropped(s, k):
                    out.append((s, tag, T.value(tag, s)))
        return out[:limit]

    def trend(self, tags, a, b, every):
        acc = {}
        for s in range(a, b):
            for tag in tags:
                acc.setdefault((tag, s - (s - a) % every), []).append(T.value(tag, s))
        return {k: sum(v) / len(v) for k, v in acc.items()}

    def quality(self, a, b, every):
        acc = {}
        for s in range(a, b):
            for k in range(12):
                q = "INTERPOLATED_LINEAR" if dropped(s, k) else "GOOD"
                key = (q, s - (s - a) % every)
                acc[key] = acc.get(key, 0) + 1
        return acc

    def anomaly(self, a, b, every):
        acc = {}
        for s in range(a, b):
            acc.setdefault(s - (s - a) % every, []).append(rec_err(s))
        return {("reconstruction_error", w): sum(v) / len(v) for w, v in acc.items()} | \
               {("threshold", w): 0.0351 for w in acc}

    def anomaly_count(self, a, b):
        return sum(1 for s in range(a, b) if rec_err(s) > 0.0351)

    def alerts_last100(self, a, b):
        rows = []
        for s in range(b - 1, a - 1, -1):
            if s % 300 == 0:
                x = alert_at(s)
                rows.append((s, x["tag"], x["alert_type"], x["severity"], x["detector"], x["detail"]))
                if len(rows) == 100:
                    break
        return rows

    def alerts_rate(self, a, b, every):
        acc = {}
        for s in range(a, b):
            if s % 300 == 0:
                key = (alert_at(s)["detector"], s - (s - a) % every)
                acc[key] = acc.get(key, 0) + 1
        return acc


def close(x, y, tol=1e-6):
    return abs(x - y) <= tol * max(1.0, abs(y))


def compare(kind, got, want):
    """엔진 결과(정규화)와 정답 비교 → (correct, detail)."""
    if kind in ("evidence",):
        ok = len(got) == len(want) and all(g[0] == w[0] and g[1] == w[1] and close(g[2], w[2])
                                           for g, w in zip(sorted(got), sorted(want)))
        return ok, {"rows": len(got), "want": len(want)}
    if kind in ("trend", "anomaly"):
        miss = [k for k in want if k not in got]
        bad = [k for k in want if k in got and not close(got[k], want[k])]
        extra = [k for k in got if k not in want]
        return not (miss or bad or extra), {"windows": len(got), "want": len(want), "missing": len(miss),
                                            "wrong": len(bad), "extra": len(extra)}
    if kind in ("quality", "alerts_rate"):
        g = {k: v for k, v in got.items() if v}
        return g == want, {"cells": len(g), "want": len(want),
                           "diff": len(set(g.items()) ^ set(want.items()))}
    if kind == "count":
        return got == want, {"got": got, "want": want}
    if kind == "alerts_last100":
        ok = len(got) == len(want) and all(g[0] == w[0] and tuple(g[1:]) == tuple(w[1:]) for g, w in zip(got, want))
        return ok, {"rows": len(got), "want": len(want), "first": list(got[0]) if got else None}
    return False, {"error": "unknown kind"}


# ───────────────────────────── 공통 도구 ─────────────────────────────
def iso(s):
    return datetime.fromtimestamp(s, timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def esc_tag(v):
    return str(v).replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")


def lp_lines(meas, rows):
    out = []
    for ts, tags, fields in rows:
        t = ",".join(f"{k}={esc_tag(v)}" for k, v in tags.items())
        f = []
        for k, v in fields.items():
            if isinstance(v, bool):
                f.append(f"{k}={'true' if v else 'false'}")
            elif isinstance(v, str):
                f.append(f'{k}="' + v.replace("\\", "\\\\").replace('"', '\\"') + '"')
            else:
                f.append(f"{k}={v}")
        out.append(f"{meas},{t} {','.join(f)} {ts}")
    return out


def sec_of(v):
    """엔진이 돌려준 시각(ns/µs/ms 정수, ISO 문자열, datetime)을 초로."""
    if isinstance(v, datetime):
        return int(v.replace(tzinfo=v.tzinfo or timezone.utc).timestamp())
    if isinstance(v, (int, float)):
        x = int(v)
        if x > 10 ** 17:
            return x // 1_000_000_000      # ns
        if x > 10 ** 14:
            return x // 1_000_000          # µs
        if x > 10 ** 11:
            return x // 1_000              # ms
        return x
    s = str(v).strip().replace(" ", "T")
    if s.isdigit():
        return sec_of(int(s))
    if "." in s:
        head, tail = s.split(".", 1)
        tz = "".join(c for c in tail if not c.isdigit())
        s = head + (tz or "")
    s = s.replace("Z", "+00:00")
    d = datetime.fromisoformat(s)
    return int((d if d.tzinfo else d.replace(tzinfo=timezone.utc)).timestamp())


# ───────────────────────────── 엔진 ─────────────────────────────
class Engine:
    time_col = "time"
    group = "alias"                 # alias | ordinal
    notes: list[str] = []

    def q(self, ident):
        return ident

    def lit(self, s):
        return f"'{iso(s)}'"

    def bucket(self, every):
        raise NotImplementedError

    def setup(self): ...
    def write(self, meas, rows): raise NotImplementedError
    def sql(self, text): raise NotImplementedError
    def flush(self): ...

    # 공통 SQL 번역
    def _rng(self, a, b):
        t = self.time_col
        return f"{t} >= {self.lit(a)} AND {t} < {self.lit(b)}"

    def _gb(self, *names):
        return "GROUP BY " + (", ".join(str(i + 1) for i in range(len(names))) if self.group == "ordinal" else ", ".join(names))

    def q_evidence(self, tags, a, b, limit=2001):
        tg = self.q("tag")
        inl = ",".join(f"'{x}'" for x in tags)
        rows = self.sql(f"SELECT {self.time_col}, {tg}, value FROM process_raw WHERE {self._rng(a, b)} "
                        f"AND site='{SITE}' AND device='{DEV}' AND {tg} IN ({inl}) ORDER BY {self.time_col} LIMIT {limit}")
        return [(sec_of(r[0]), r[1], float(r[2])) for r in rows]

    def q_trend(self, tags, a, b, every):
        tg = self.q("tag")
        inl = ",".join(f"'{x}'" for x in tags)
        rows = self.sql(f"SELECT {self.bucket(every)} AS w, {tg}, avg(value) FROM process WHERE {self._rng(a, b)} "
                        f"AND {tg} IN ({inl}) {self._gb('w', tg)}")
        return {(r[1], sec_of(r[0])): float(r[2]) for r in rows}

    def q_quality(self, a, b, every):
        qc = self.q("quality")
        rows = self.sql(f"SELECT {self.bucket(every)} AS w, {qc}, count(*) FROM process WHERE {self._rng(a, b)} {self._gb('w', qc)}")
        return {(r[1], sec_of(r[0])): int(r[2]) for r in rows}

    def q_anomaly(self, a, b, every):
        rows = self.sql(f"SELECT {self.bucket(every)} AS w, avg(reconstruction_error), avg(threshold) FROM anomaly "
                        f"WHERE {self._rng(a, b)} {self._gb('w')}")
        out = {}
        for r in rows:
            out[("reconstruction_error", sec_of(r[0]))] = float(r[1])
            out[("threshold", sec_of(r[0]))] = float(r[2])
        return out

    def q_anomaly_count(self, a, b):
        return int(self.sql(f"SELECT count(*) FROM anomaly WHERE {self._rng(a, b)} AND is_anomaly = true")[0][0])

    def q_alerts_last100(self, a, b):
        tg = self.q("tag")
        rows = self.sql(f"SELECT {self.time_col}, {tg}, alert_type, severity, detector, detail FROM alerts "
                        f"WHERE {self._rng(a, b)} ORDER BY {self.time_col} DESC LIMIT 100")
        return [(sec_of(r[0]), *r[1:6]) for r in rows]

    def q_alerts_rate(self, a, b, every):
        rows = self.sql(f"SELECT {self.bucket(every)} AS w, detector, count(*) FROM alerts WHERE {self._rng(a, b)} "
                        f"{self._gb('w', 'detector')}")
        return {(r[1], sec_of(r[0])): int(r[2]) for r in rows}

    def count_device(self, meas, device, a, b):
        """R06: device=... 행 수."""
        return int(self.sql(f"SELECT count(*) FROM {meas} WHERE device='{device}' AND {self._rng(a, b)}")[0][0])


class Influx2(Engine):
    """InfluxDB 2.x — V1 과 같은 Flux 질의를 그대로 보낸다(범위·창만 고정값)."""
    def __init__(self, url="http://influxdb:8086"):
        self.url, self.org, self.bucket_name = url, "uengine", "process"
        self.h = {"Authorization": "Token bench-admin-token-000000000000", "Content-Type": "application/json",
                  "Accept": "application/csv"}

    def write(self, meas, rows):
        body = "\n".join(lp_lines(meas, rows)).encode()
        r = requests.post(f"{self.url}/api/v2/write", params={"org": self.org, "bucket": self.bucket_name, "precision": "ns"},
                          data=body, headers={"Authorization": self.h["Authorization"]}, timeout=120)
        r.raise_for_status()

    def flux(self, q):
        r = requests.post(f"{self.url}/api/v2/query", params={"org": self.org}, headers=self.h,
                          data=json.dumps({"query": q, "type": "flux"}), timeout=300)
        r.raise_for_status()
        lines = [x for x in r.text.splitlines() if x and not x.startswith("#")]
        return [row for row in csv.DictReader(lines) if row.get("_value") not in (None, "_value")]

    def _range(self, a, b):
        return f'from(bucket:"process") |> range(start:time(v:{a * 10 ** 9}), stop:time(v:{b * 10 ** 9}))'

    def q_evidence(self, tags, a, b, limit=2001):
        # evidence.py history() 문자열과 같은 구조
        q = (self._range(a, b) + f' |> filter(fn:(r)=>r._measurement=="process_raw" and r._field=="value" '
             f'and r.site=="{SITE}" and r.device=="{DEV}" and contains(value:r.tag,set:{json.dumps(tags)})) '
             f'|> group() |> sort(columns:["_time"]) |> limit(n:{limit})')
        return [(sec_of(r["_time"]), r["tag"], float(r["_value"])) for r in self.flux(q)]

    def q_trend(self, tags, a, b, every):
        f = " or ".join(f'r["tag"] == "{t}"' for t in tags)
        q = (self._range(a, b) + ' |> filter(fn: (r) => r._measurement == "process") |> filter(fn: (r) => r._field == "value")'
             f' |> filter(fn: (r) => {f}) |> group(columns: ["tag"])'   # 태그 단위로 묶은 뒤 창 평균(SQL 후보와 같은 질문, #117)
             f' |> aggregateWindow(every: {every}s, fn: mean, createEmpty: false)'
             ' |> keep(columns: ["_time", "_value", "tag"])')
        return {(r["tag"], sec_of(r["_time"]) - every): float(r["_value"]) for r in self.flux(q)}

    def q_quality(self, a, b, every):
        q = (self._range(a, b) + ' |> filter(fn: (r) => r._measurement == "process") |> filter(fn: (r) => r._field == "value")'
             f' |> group(columns: ["quality"]) |> aggregateWindow(every: {every}s, fn: count, createEmpty: true)'
             ' |> keep(columns: ["_time", "_value", "quality"])')
        return {(r["quality"], sec_of(r["_time"]) - every): int(r["_value"]) for r in self.flux(q)}

    def q_anomaly(self, a, b, every):
        q = (self._range(a, b) + ' |> filter(fn: (r) => r._measurement == "anomaly")'
             ' |> filter(fn: (r) => r._field == "reconstruction_error" or r._field == "threshold")'
             f' |> aggregateWindow(every: {every}s, fn: mean, createEmpty: false) |> keep(columns: ["_time", "_value", "_field"])')
        return {(r["_field"], sec_of(r["_time"]) - every): float(r["_value"]) for r in self.flux(q)}

    def q_anomaly_count(self, a, b):
        q = (self._range(a, b) + ' |> filter(fn: (r) => r._measurement == "anomaly" and r._field == "is_anomaly")'
             ' |> filter(fn: (r) => r._value == true) |> count()')
        return sum(int(r["_value"]) for r in self.flux(q))

    def q_alerts_last100(self, a, b):
        q = (self._range(a, b) + ' |> filter(fn: (r) => r._measurement == "alerts" and r._field == "detail")'
             ' |> sort(columns: ["_time"], desc: true) |> limit(n: 100)'
             ' |> keep(columns: ["_time", "tag", "alert_type", "severity", "detector", "_value"])')
        rows = [(sec_of(r["_time"]), r["tag"], r["alert_type"], r["severity"], r["detector"], r["_value"]) for r in self.flux(q)]
        return sorted(rows, key=lambda x: -x[0])[:100]   # 시리즈별 테이블이라 전역 정렬은 화면(Grafana)이 한다

    def q_alerts_rate(self, a, b, every):
        q = (self._range(a, b) + ' |> filter(fn: (r) => r._measurement == "alerts" and r._field == "value")'
             f' |> group(columns: ["detector"]) |> aggregateWindow(every: {every}s, fn: count, createEmpty: true)'
             ' |> keep(columns: ["_time", "_value", "detector"])')
        return {(r["detector"], sec_of(r["_time"]) - every): int(r["_value"]) for r in self.flux(q)}

    def count_device(self, meas, device, a, b):
        q = (self._range(a, b) + f' |> filter(fn:(r)=>r._measurement=="{meas}" and r._field=="value" and r.device=="{device}")'
             ' |> group() |> count()')
        return sum(int(r["_value"]) for r in self.flux(q))


class Influx3(Engine):
    """InfluxDB 3 Core — Flux 미지원 → SQL(/api/v3/query_sql). V1 evidence.py 를 SQL 로 고쳐야 한다는 뜻(갭)."""
    def __init__(self):
        self.url = "http://influxdb3:8181"
        tok = os.environ.get("INFLUX3_TOKEN", "")
        self.h = {"Authorization": f"Bearer {tok}"} if tok else {}

    def write(self, meas, rows):
        r = requests.post(f"{self.url}/api/v3/write_lp", params={"db": "process", "precision": "nanosecond"},
                          data="\n".join(lp_lines(meas, rows)).encode(), headers=self.h, timeout=120)
        r.raise_for_status()

    def lit(self, s):
        return f"TIMESTAMP '{iso(s).replace('T', ' ').replace('Z', '')}'"

    def bucket(self, every):
        return f"date_bin(INTERVAL '{every} seconds', time, TIMESTAMP '1970-01-01 00:00:00')"

    def sql(self, text):
        r = requests.post(f"{self.url}/api/v3/query_sql", json={"db": "process", "q": text, "format": "json"},
                          headers=self.h, timeout=300)
        if r.status_code >= 400:
            raise RuntimeError(f"{r.status_code} {r.text[:400]}")
        return [list(x.values()) for x in r.json()]


class Postgres(Engine):
    """TimescaleDB Apache판 / PostgreSQL 18 + pg_partman. 같은 테이블 모양, 적재는 COPY."""
    def __init__(self, host, flavor):
        import psycopg
        self.psycopg = psycopg
        self.flavor = flavor
        self.dsn = f"host={host} user=postgres password=bench dbname=postgres"
        self.c = psycopg.connect(self.dsn, autocommit=True)

    def setup(self):
        cols = {"process_raw": "site text, device text, tag text, quality text, value double precision",
                "process": "site text, device text, tag text, quality text, value double precision",
                "anomaly": "site text, device text, top_contributors text, reconstruction_error double precision, "
                           "threshold double precision, inference_ms double precision, is_anomaly boolean",
                "alerts": "site text, device text, tag text, alert_type text, severity text, detector text, "
                          "value double precision, detail text"}
        for t, c in cols.items():
            if self.flavor == "timescale":
                self.c.execute(f"CREATE TABLE IF NOT EXISTS {t} (time timestamptz NOT NULL, {c})")
                self.c.execute(f"SELECT create_hypertable('{t}', by_range('time', INTERVAL '1 day'), if_not_exists => TRUE)")
            else:
                self.c.execute("CREATE SCHEMA IF NOT EXISTS partman")
                self.c.execute("CREATE EXTENSION IF NOT EXISTS pg_partman SCHEMA partman")
                self.c.execute(f"CREATE TABLE IF NOT EXISTS {t} (time timestamptz NOT NULL, {c}) PARTITION BY RANGE (time)")
                self.c.execute(f"SELECT partman.create_parent(p_parent_table => 'public.{t}', p_control => 'time', "
                               f"p_interval => '1 day', p_premake => 2, p_start_partition => '{iso(START - 86400)}') "
                               f"WHERE NOT EXISTS (SELECT 1 FROM partman.part_config WHERE parent_table='public.{t}')")
            if t in ("process_raw", "process", "alerts"):
                self.c.execute(f"CREATE INDEX IF NOT EXISTS {t}_tag_time ON {t} (tag, time DESC)")
        self.info = {"server": self.c.execute("SHOW server_version").fetchone()[0],
                     "extensions": dict(self.c.execute("SELECT extname, extversion FROM pg_extension").fetchall())}

    def write(self, meas, rows):
        if not rows:
            return
        tagk, fk = list(rows[0][1]), list(rows[0][2])
        with self.c.cursor() as cur:
            with cur.copy(f"COPY {meas} (time, {', '.join(tagk + fk)}) FROM STDIN") as cp:
                for ts, tags, fields in rows:
                    cp.write_row([datetime.fromtimestamp(ts / 1e9, timezone.utc), *tags.values(), *fields.values()])

    def bucket(self, every):
        return (f"time_bucket(INTERVAL '{every} seconds', time)" if self.flavor == "timescale"
                else f"date_bin(INTERVAL '{every} seconds', time, TIMESTAMPTZ '1970-01-01 00:00:00+00')")

    def lit(self, s):
        return f"TIMESTAMPTZ '{iso(s)}'"

    def sql(self, text):
        return self.c.execute(text).fetchall()


class QuestDB(Engine):
    """QuestDB 10 — ILP over HTTP 적재, /exec SQL. 태그는 SYMBOL, 지정 타임스탬프 열 이름 timestamp."""
    time_col = "timestamp"

    def __init__(self):
        self.url = "http://questdb:9000"

    def write(self, meas, rows):
        r = requests.post(f"{self.url}/write", params={"precision": "n"},
                          data="\n".join(lp_lines(meas, rows)).encode(), timeout=120)
        r.raise_for_status()

    def bucket(self, every):
        return f"timestamp_floor('{every}s', timestamp)"

    def sql(self, text):
        r = requests.get(f"{self.url}/exec", params={"query": text, "count": "false"}, timeout=300)
        j = r.json()
        if "error" in j:
            raise RuntimeError(j["error"])
        return j["dataset"]


class Greptime(Engine):
    """GreptimeDB — InfluxDB v2 쓰기 호환 적재, /v1/sql. 시간 열 greptime_timestamp."""
    time_col = "greptime_timestamp"

    def __init__(self):
        self.url = "http://greptime:4000"

    def write(self, meas, rows):
        r = requests.post(f"{self.url}/v1/influxdb/api/v2/write", params={"db": "public", "precision": "ns"},
                          data="\n".join(lp_lines(meas, rows)).encode(), timeout=120)
        r.raise_for_status()

    def q(self, ident):
        return f'"{ident}"'

    def bucket(self, every):
        return f"date_bin(INTERVAL '{every} seconds', greptime_timestamp)"

    def sql(self, text):
        r = requests.post(f"{self.url}/v1/sql", params={"db": "public"}, data={"sql": text}, timeout=300)
        j = r.json()
        if j.get("code", 0) not in (0, None) or "error" in j:
            raise RuntimeError(str(j)[:400])
        return j["output"][0]["records"]["rows"]


class Crate(Engine):
    """CrateDB 6.4 — HTTP /_sql bulk_args 적재."""
    time_col = "ts"
    group = "ordinal"

    def __init__(self):
        self.url = "http://cratedb:4200/_sql"

    def setup(self):
        ddl = {"process_raw": "tag TEXT, quality TEXT, value DOUBLE", "process": "tag TEXT, quality TEXT, value DOUBLE",
               "anomaly": "top_contributors TEXT, reconstruction_error DOUBLE, threshold DOUBLE, inference_ms DOUBLE, is_anomaly BOOLEAN",
               "alerts": "tag TEXT, alert_type TEXT, severity TEXT, detector TEXT, value DOUBLE, detail TEXT"}
        for t, c in ddl.items():
            self.sql(f"CREATE TABLE IF NOT EXISTS {t} (ts TIMESTAMP WITH TIME ZONE, site TEXT, device TEXT, {c}, "
                     f"day TIMESTAMP WITH TIME ZONE GENERATED ALWAYS AS date_trunc('day', ts)) PARTITIONED BY (day)")

    def write(self, meas, rows):
        if not rows:
            return
        k = ["ts"] + list(rows[0][1]) + list(rows[0][2])
        args = [[ts // 1_000_000, *t.values(), *f.values()] for ts, t, f in rows]
        r = requests.post(self.url, json={"stmt": f"INSERT INTO {meas} ({', '.join(k)}) VALUES ({', '.join('?' * len(k))})",
                                          "bulk_args": args}, timeout=300)
        r.raise_for_status()

    def flush(self):
        for t in ("process_raw", "process", "anomaly", "alerts"):
            self.sql(f"REFRESH TABLE {t}")

    def bucket(self, every):
        return f"DATE_BIN('{every} seconds'::INTERVAL, ts, 0)"

    def count_device(self, meas, device, a, b):
        if meas == "r06_raw":   # Telegraf outputs.cratedb 는 고정 스키마(timestamp, name, tags OBJECT, fields OBJECT)
            self.sql("REFRESH TABLE r06_metrics")
            return int(self.sql(f"SELECT count(*) FROM r06_metrics WHERE name='r06_raw' AND tags['device']='{device}' "
                                f"AND \"timestamp\" >= {a * 1000} AND \"timestamp\" < {b * 1000}")[0][0])
        self.sql(f"REFRESH TABLE {meas}")
        return super().count_device(meas, device, a, b)

    def sql(self, text):
        r = requests.post(self.url, json={"stmt": text}, timeout=300)
        j = r.json()
        if "error" in j:
            raise RuntimeError(j["error"])
        return j["rows"]


class ClickHouse(Engine):
    time_col = "ts"

    def __init__(self):
        import clickhouse_connect
        self.c = clickhouse_connect.get_client(host="clickhouse", username="default", password="bench")

    def setup(self):
        ddl = {"process_raw": "tag LowCardinality(String), quality LowCardinality(String), value Float64",
               "process": "tag LowCardinality(String), quality LowCardinality(String), value Float64",
               "anomaly": "top_contributors String, reconstruction_error Float64, threshold Float64, inference_ms Float64, is_anomaly Bool",
               "alerts": "tag String, alert_type String, severity String, detector String, value Float64, detail String"}
        for t, c in ddl.items():
            self.c.command(f"CREATE TABLE IF NOT EXISTS {t} (ts DateTime64(9, 'UTC'), site LowCardinality(String), "
                           f"device LowCardinality(String), {c}) ENGINE = MergeTree PARTITION BY toDate(ts) "
                           f"ORDER BY ({'tag, ' if 'tag ' in c else ''}ts)")

    def write(self, meas, rows):
        if not rows:
            return
        k = ["ts"] + list(rows[0][1]) + list(rows[0][2])
        self.c.insert(meas, [[datetime.fromtimestamp(ts // 1000 / 1e6, timezone.utc), *t.values(), *f.values()]
                             for ts, t, f in rows], column_names=k)

    def lit(self, s):
        return f"toDateTime64('{iso(s)[:-1].replace('T', ' ')}', 9, 'UTC')"

    def bucket(self, every):
        return f"toStartOfInterval(ts, INTERVAL {every} SECOND)"

    def count_device(self, meas, device, a, b):
        if meas == "r06_raw":   # Telegraf outputs.sql 가 만든 표(시간 열 timestamp)
            return int(self.sql(f"SELECT count() FROM r06_raw WHERE device='{device}' AND timestamp >= {self.lit(a)} "
                                f"AND timestamp < {self.lit(b)}")[0][0])
        return super().count_device(meas, device, a, b)

    def sql(self, text):
        return self.c.query(text).result_rows


class IoTDB(Engine):
    """IoTDB 2.0 테이블 모델. TAG 열(site/device/tag) + FIELD 열. 시간 정밀도 ms(기본 설정) → ns 자리는 잘림(기록)."""
    group = "ordinal"

    def __init__(self):
        from iotdb.table_session import TableSession, TableSessionConfig
        self.s = TableSession(TableSessionConfig(node_urls=["iotdb:6667"], username="root", password="root"))

    def setup(self):
        self.s.execute_non_query_statement("CREATE DATABASE IF NOT EXISTS process")
        self.s.execute_non_query_statement("USE process")
        ddl = {"process_raw": "site STRING TAG, device STRING TAG, \"tag\" STRING TAG, quality STRING FIELD, value DOUBLE FIELD",
               "process": "site STRING TAG, device STRING TAG, \"tag\" STRING TAG, quality STRING FIELD, value DOUBLE FIELD",
               "anomaly": "site STRING TAG, device STRING TAG, top_contributors STRING FIELD, reconstruction_error DOUBLE FIELD, "
                          "threshold DOUBLE FIELD, inference_ms DOUBLE FIELD, is_anomaly BOOLEAN FIELD",
               "alerts": "site STRING TAG, device STRING TAG, \"tag\" STRING TAG, alert_type STRING FIELD, severity STRING FIELD, "
                         "detector STRING FIELD, value DOUBLE FIELD, detail STRING FIELD"}
        for t, c in ddl.items():
            self.s.execute_non_query_statement(f"CREATE TABLE IF NOT EXISTS {t} ({c})")

    def write(self, meas, rows):
        from iotdb.utils.IoTDBConstants import TSDataType
        from iotdb.utils.Tablet import ColumnType, Tablet
        if not rows:
            return
        tagk, fk = list(rows[0][1]), list(rows[0][2])
        tagk_fields = [k for k in tagk if k in ("quality", "top_contributors", "alert_type", "severity", "detector")]
        tagk_tags = [k for k in tagk if k not in tagk_fields]
        cols = tagk_tags + tagk_fields + fk

        def dt(k, v):
            return TSDataType.BOOLEAN if isinstance(v, bool) else TSDataType.DOUBLE if isinstance(v, float) else TSDataType.STRING
        sample = rows[0][1] | rows[0][2]
        types = [dt(k, sample[k]) for k in cols]
        ctypes = [ColumnType.TAG] * len(tagk_tags) + [ColumnType.FIELD] * (len(tagk_fields) + len(fk))
        vals = [[(t | f)[k] for k in cols] for _, t, f in rows]
        self.s.insert(Tablet(meas, cols, types, vals, [ts // 1_000_000 for ts, _, _ in rows], ctypes))

    def q(self, ident):
        return f'"{ident}"'

    def lit(self, s):
        return str(s * 1000)

    def bucket(self, every):
        return f"date_bin({every}s, time)"

    def count_device(self, meas, device, a, b):
        if meas == "r06_raw":   # Telegraf outputs.iotdb 는 트리 모델(convert_tags_to=fields) → 트리 세션으로 센다 [미검증 질의]
            from iotdb.Session import Session
            t = Session("iotdb", "6667", "root", "root")
            t.open(False)
            ds = t.execute_query_statement(f"SELECT count(value) FROM root.bench.r06_raw WHERE device = '{device}' "
                                           f"AND time >= {a * 1000} AND time < {b * 1000}")
            n = ds.next().get_fields()[0].get_long_value() if ds.has_next() else 0
            ds.close_operation_handle()
            t.close()
            return int(n)
        return super().count_device(meas, device, a, b)

    def sql(self, text):
        ds = self.s.execute_query_statement(text)
        out = []
        while ds.has_next():
            r = ds.next()
            out.append([f.get_object_value(f.get_data_type()) if f.get_data_type() is not None else None
                        for f in r.get_fields()])
        ds.close_operation_handle()
        return out


class TDengine(Engine):
    """TDengine TSDB-OSS 3.4 (AGPL ⚠) — taosAdapter InfluxDB 쓰기 호환(schemaless), REST SQL. 창 질의는 INTERVAL 문법."""
    time_col = "_ts"

    def __init__(self):
        self.url = "http://tdengine:6041"
        self.auth = ("root", "taosdata")

    def setup(self):
        self.sql("CREATE DATABASE IF NOT EXISTS process PRECISION 'ns' KEEP 3650")

    def write(self, meas, rows):
        r = requests.post(f"{self.url}/influxdb/v1/write", params={"db": "process", "precision": "ns"},
                          data="\n".join(lp_lines(meas, rows)).encode(), auth=self.auth, timeout=120)
        r.raise_for_status()

    def q(self, ident):
        return f"`{ident}`"

    def lit(self, s):
        return str(s * 1_000_000_000)

    def sql(self, text):
        r = requests.post(f"{self.url}/rest/sql/process", data=text.encode(), auth=self.auth, timeout=300)
        j = r.json()
        if j.get("code", 0) != 0:
            raise RuntimeError(j.get("desc"))
        return j.get("data", [])

    def _win(self, sel, table, where, part, every):
        return self.sql(f"SELECT _wstart, {sel} FROM {table} WHERE {where} {part} INTERVAL({every}s)")

    def q_trend(self, tags, a, b, every):
        inl = ",".join(f"'{x}'" for x in tags)
        rows = self._win("`tag`, avg(`value`)", "process", f"{self._rng(a, b)} AND `tag` IN ({inl})", "PARTITION BY `tag`", every)
        return {(r[1], sec_of(r[0])): float(r[2]) for r in rows}

    def q_quality(self, a, b, every):
        rows = self._win("quality, count(*)", "process", self._rng(a, b), "PARTITION BY quality", every)
        return {(r[1], sec_of(r[0])): int(r[2]) for r in rows}

    def q_anomaly(self, a, b, every):
        rows = self._win("avg(reconstruction_error), avg(threshold)", "anomaly", self._rng(a, b), "", every)
        out = {}
        for r in rows:
            out[("reconstruction_error", sec_of(r[0]))] = float(r[1])
            out[("threshold", sec_of(r[0]))] = float(r[2])
        return out

    def q_alerts_rate(self, a, b, every):
        rows = self._win("detector, count(*)", "alerts", self._rng(a, b), "PARTITION BY detector", every)
        return {(r[1], sec_of(r[0])): int(r[2]) for r in rows}


class VictoriaMetrics(Engine):
    """VictoriaMetrics single — InfluxDB 줄 프로토콜 적재(metric=측정값_필드), MetricsQL/export 조회.
    문자열 필드(alerts.detail)는 저장하지 않는다 → alerts_last100 재현 불가(갭으로 기록)."""
    def __init__(self):
        self.url = "http://victoriametrics:8428"

    def write(self, meas, rows):
        r = requests.post(f"{self.url}/write", data="\n".join(lp_lines(meas, rows)).encode(), timeout=120)
        r.raise_for_status()

    def flush(self):
        requests.get(f"{self.url}/internal/force_flush", timeout=60)

    def export(self, match, a, b):
        r = requests.get(f"{self.url}/api/v1/export", params={"match[]": match, "start": a, "end": b - 0.001}, timeout=300)
        out = []
        for line in r.text.splitlines():
            j = json.loads(line)
            for v, t in zip(j["values"], j["timestamps"]):
                out.append((t // 1000, j["metric"], v))
        return out

    def rng(self, q, a, b, every):
        r = requests.get(f"{self.url}/api/v1/query_range",
                         params={"query": q, "start": a + every, "end": b, "step": f"{every}s", "nocache": "1"}, timeout=300)
        j = r.json()
        if j.get("status") != "success":
            raise RuntimeError(str(j)[:300])
        return j["data"]["result"]

    def q_evidence(self, tags, a, b, limit=2001):
        rows = self.export('process_raw_value{site="%s",device="%s",tag=~"%s"}' % (SITE, DEV, "|".join(tags)), a, b)
        return sorted([(s, m["tag"], float(v)) for s, m, v in rows])[:limit]

    def q_trend(self, tags, a, b, every):
        out = {}
        for s in self.rng('avg_over_time(process_value{tag=~"%s"}[%ds])' % ("|".join(tags), every), a, b, every):
            for t, v in s["values"]:
                out[(s["metric"]["tag"], int(t) - every)] = float(v)
        return out

    def q_quality(self, a, b, every):
        out = {}
        for s in self.rng('sum by (quality) (count_over_time(process_value[%ds]))' % every, a, b, every):
            for t, v in s["values"]:
                out[(s["metric"]["quality"], int(t) - every)] = int(float(v))
        return out

    def q_anomaly(self, a, b, every):
        out = {}
        for f in ("reconstruction_error", "threshold"):
            for s in self.rng('avg_over_time(anomaly_%s[%ds])' % (f, every), a, b, every):
                for t, v in s["values"]:
                    out[(f, int(t) - every)] = float(v)
        return out

    def q_anomaly_count(self, a, b):
        return int(sum(float(v) for _, _, v in self.export("anomaly_is_anomaly", a, b)))

    def q_alerts_last100(self, a, b):
        raise RuntimeError("VictoriaMetrics 는 문자열 필드(detail)를 저장하지 않음 — 알람 이력 표 재현 불가")

    def q_alerts_rate(self, a, b, every):
        out = {}
        for s in self.rng('sum by (detector) (count_over_time(alerts_value[%ds]))' % every, a, b, every):
            for t, v in s["values"]:
                out[(s["metric"]["detector"], int(t) - every)] = int(float(v))
        return out

    def count_device(self, meas, device, a, b):
        return len(self.export('%s_value{device="%s"}' % (meas, device), a, b))


ENGINES = {
    "influx27": lambda: Influx2(), "influx29": lambda: Influx2(), "influx3": Influx3,
    "timescale": lambda: Postgres("timescaledb", "timescale"), "pgpartman": lambda: Postgres("pgpartman", "partman"),
    "questdb": QuestDB, "victoriametrics": VictoriaMetrics, "iotdb": IoTDB, "greptime": Greptime,
    "cratedb": Crate, "clickhouse": ClickHouse, "tdengine": TDengine,
}
START = 0


# ───────────────────────────── 단계 ─────────────────────────────
def out_path(a, phase):
    RAW.mkdir(parents=True, exist_ok=True)
    return RAW / f"{a.engine}_{phase}.json"


def retry(fn, what, tries=90):
    last = None
    for _ in range(tries):
        try:
            return fn()
        except Exception as e:
            last = e
            time.sleep(2)
    raise RuntimeError(f"{what}: {last!r}")


def load(a):
    global START
    e = retry(ENGINES[a.engine], "connect")
    end = int(time.time()) // 3600 * 3600      # 정시 정렬: 모든 창(10s·60s·600s·3600s)이 epoch 정렬과 일치
    START = end - a.hours * 3600
    retry(e.setup, "setup")
    marks = {"load_start_epoch": time.time()}
    counts, lat, errors = {}, [], []
    t0 = time.time()
    for chunk in gen(START, end):
        for meas, rows in chunk.items():
            for i in range(0, len(rows), BATCH):
                b = rows[i:i + BATCH]
                t = time.time()
                try:
                    e.write(meas, b)
                except Exception as ex:
                    try:
                        time.sleep(1)
                        e.write(meas, b)
                    except Exception as ex2:
                        errors.append(repr(ex2)[:300])
                        continue
                lat.append((time.time() - t) * 1000)
                counts[meas] = counts.get(meas, 0) + len(b)
    e.flush()
    el = time.time() - t0
    marks["load_end_epoch"] = time.time()
    total = sum(counts.values())
    res = {"engine": a.engine, "hours": a.hours, "range": [START, end], "rows": counts, "rows_total": total,
           "elapsed_s": round(el, 1), "rows_per_s": round(total / el, 1),
           "batch_ms": {"p50": T.pct(lat, .5), "p95": T.pct(lat, .95), "max": T.pct(lat, 1)}, "batch_size": BATCH,
           "write_errors": len(errors), "error_samples": errors[:5], "marks": marks,
           "engine_info": getattr(e, "info", None),
           "guard": {"forced": os.environ.get("BENCH_GUARD_FORCED") == "1"}}
    out_path(a, f"load{a.hours}h").write_text(json.dumps(res, ensure_ascii=False, indent=2))
    (RAW / f"{a.engine}_range.json").write_text(json.dumps({"start": START, "end": end, "hours": a.hours}))
    print(json.dumps({k: res[k] for k in ("engine", "rows_total", "elapsed_s", "rows_per_s", "write_errors")}))


def query(a):
    rg = json.loads((RAW / f"{a.engine}_range.json").read_text())
    s0, end = rg["start"], rg["end"]
    e = retry(ENGINES[a.engine], "connect")
    tr = Truth()
    rnd = random.Random(20260929)
    day0 = max(s0, end - 86400)
    ev_points = [rnd.randrange(day0 + 60, end - 600) for _ in range(a.repeat)]
    plan = [
        ("evidence", "evidence", lambda i: e.q_evidence(EVID_TAGS, ev_points[i] - 30, ev_points[i] + 15),
         lambda i: tr.evidence(EVID_TAGS, ev_points[i] - 30, ev_points[i] + 15)),
        ("evidence300", "evidence", lambda i: e.q_evidence(EVID_TAGS, ev_points[i] - 30, ev_points[i] + 270),
         lambda i: tr.evidence(EVID_TAGS, ev_points[i] - 30, ev_points[i] + 270)),
        ("current", "evidence", lambda i: e.q_evidence(T.TAG_NAMES, end - 30, end), lambda i: tr.evidence(T.TAG_NAMES, end - 30, end)),
        ("trend_1h", "trend", lambda i: e.q_trend(TREND_TAGS, end - 3600, end, 10), lambda i: tr.trend(TREND_TAGS, end - 3600, end, 10)),
        ("trend_24h", "trend", lambda i: e.q_trend(TREND_TAGS, day0, end, 60), lambda i: tr.trend(TREND_TAGS, day0, end, 60)),
        ("quality_24h", "quality", lambda i: e.q_quality(day0, end, 60), lambda i: tr.quality(day0, end, 60)),
        ("anomaly_24h", "anomaly", lambda i: e.q_anomaly(day0, end, 60), lambda i: tr.anomaly(day0, end, 60)),
        ("anomaly_count", "count", lambda i: e.q_anomaly_count(day0, end), lambda i: tr.anomaly_count(day0, end)),
        ("alerts_last100", "alerts_last100", lambda i: e.q_alerts_last100(day0, end), lambda i: tr.alerts_last100(day0, end)),
        ("alerts_rate", "alerts_rate", lambda i: e.q_alerts_rate(day0, end, 60), lambda i: tr.alerts_rate(day0, end, 60)),
    ]
    if rg["hours"] > 72:   # F05: 72시간 초과 이력(InfluxDB 3 Core 쿼리당 432 Parquet 파일 한도 ≈72h)
        plan += [
            ("long_trend_full", "trend", lambda i: e.q_trend(TREND_TAGS, s0, end, 600), lambda i: tr.trend(TREND_TAGS, s0, end, 600)),
            ("long_evidence_oldest", "evidence", lambda i: e.q_evidence(EVID_TAGS, s0 + 3600, s0 + 3645),
             lambda i: tr.evidence(EVID_TAGS, s0 + 3600, s0 + 3645)),
            ("long_quality_full", "quality", lambda i: e.q_quality(s0, end, 3600), lambda i: tr.quality(s0, end, 3600)),
        ]
    marks = {"query_start_epoch": time.time()}
    results = {}
    for name, kind, run_q, want_q in plan:
        reps = a.repeat if name.startswith("evidence") else max(3, a.repeat // 4)
        lat, ok_all, detail, err = [], True, None, None
        for i in range(reps + 1):          # 0번째는 콜드(따로 기록)
            t = time.time()
            try:
                got = run_q(i % a.repeat)
            except Exception as ex:
                err = repr(ex)[:500]
                ok_all = False
                break
            ms = (time.time() - t) * 1000
            if i == 0:
                cold = ms
                ok, detail = compare(kind, got, want_q(0))
                ok_all &= ok
            else:
                lat.append(ms)
                if name.startswith("evidence") and i < 5:
                    ok, d2 = compare(kind, got, want_q(i % a.repeat))
                    ok_all &= ok
                    detail = detail if ok else d2
        results[name] = {"correct": ok_all and err is None, "detail": detail, "error": err,
                         "cold_ms": round(cold, 1) if err is None or lat else None,
                         "p50_ms": T.pct(lat, .5), "p95_ms": T.pct(lat, .95), "n": len(lat)}
    marks["query_end_epoch"] = time.time()
    res = {"engine": a.engine, "hours": rg["hours"], "queries": results, "marks": marks,
           "correct_all": all(r["correct"] for r in results.values())}
    out_path(a, f"query{rg['hours']}h").write_text(json.dumps(res, ensure_ascii=False, indent=2))
    print(json.dumps({n: (r["correct"], r["p95_ms"]) for n, r in results.items()}, ensure_ascii=False))


def fresh(a):
    """12행/초로 60초 쓰고, 각 초의 행이 current 질의에 나타날 때까지 걸린 시간(가시화 지연)."""
    e = retry(ENGINES[a.engine], "connect")
    dev = f"fresh-{uuid.uuid4().hex[:6]}"
    lags, miss = [], 0
    for i in range(a.fresh_seconds):
        s = int(time.time())
        rows = [(s * 1_000_000_000 + SUB, {"site": SITE, "device": dev, "tag": tag, "quality": "GOOD"}, {"value": T.value(tag, s)})
                for tag in T.TAG_NAMES]
        t = time.time()
        e.write("process_raw", rows)
        seen = False
        while time.time() - t < a.fresh_timeout:
            try:
                if e.count_device("process_raw", dev, s, s + 1) >= 12:
                    seen = True
                    break
            except Exception:
                pass
            time.sleep(0.05)
        if seen:
            lags.append((time.time() - t) * 1000)
        else:
            miss += 1
        time.sleep(max(0, 1 - (time.time() - t)))
    res = {"engine": a.engine, "seconds": a.fresh_seconds, "visible_ms": {"p50": T.pct(lags, .5), "p95": T.pct(lags, .95),
           "max": T.pct(lags, 1)}, "not_visible_within_s": {"timeout_s": a.fresh_timeout, "count": miss}}
    out_path(a, "fresh").write_text(json.dumps(res, ensure_ascii=False, indent=2))
    print(json.dumps(res))


def r06(a):
    """④ R06 훅. Telegraf 1.40(V1 writer 와 같은 역할·버퍼 200000) 에 12행/초를 보내는 동안 호스트가 DB 를 정지(기본 5분)·재기동.
    끝나고 기대(12×초) 대비 저장 행 수(유실)·초과(중복)를 센다. 측정값 이름 r06_raw(적재 표와 분리)."""
    import socket
    dev = f"r06-{uuid.uuid4().hex[:6]}"
    s = retry(lambda: socket.create_connection(("telegraf-r06", 8094), timeout=10), "telegraf")
    t0 = int(time.time()) + 1
    (RAW / f"{a.engine}_r06.ready").write_text(str(t0))
    n = 0
    for i in range(a.r06_seconds):
        sec = t0 + i
        while time.time() < sec:
            time.sleep(0.01)
        payload = "".join(f"r06_raw,site={SITE},device={dev},tag={tag},quality=GOOD value={T.value(tag, sec)} {sec * 10 ** 9 + SUB}\n"
                          for tag in T.TAG_NAMES)
        try:
            s.sendall(payload.encode())
            n += 12
        except OSError:
            s = retry(lambda: socket.create_connection(("telegraf-r06", 8094), timeout=10), "telegraf")
            s.sendall(payload.encode())
            n += 12
    s.close()
    e = retry(ENGINES[a.engine], "connect")
    stored, t_wait = None, time.time()
    while time.time() - t_wait < a.r06_drain:
        try:
            stored = e.count_device("r06_raw", dev, t0, t0 + a.r06_seconds)
            if stored >= n:
                break
        except Exception:
            pass
        time.sleep(5)
    res = {"engine": a.engine, "sent": n, "stored": stored, "lost": None if stored is None else max(0, n - stored),
           "duplicates": None if stored is None else max(0, stored - n), "drain_s": round(time.time() - t_wait, 1),
           "note": "DB 정지·재기동 시각은 raw/<engine>_r06_actions.log(호스트). 알람·화면 지속은 이 벤치 범위 밖(V1 알람 경로는 InfluxDB 를 거치지 않음)."}
    out_path(a, "r06").write_text(json.dumps(res, ensure_ascii=False, indent=2))
    print(json.dumps(res))


def summarize(a):
    runs = {f.stem[len(a.engine) + 1:]: json.loads(f.read_text()) for f in sorted(RAW.glob(f"{a.engine}_*.json"))
            if not f.stem.endswith("_range")}
    stats = {}
    for f in sorted(RAW.glob(f"stats_{a.engine}_*.csv")):
        rows = list(csv.DictReader(open(f)))
        phases = {}
        for ph, m in runs.items():
            mk = m.get("marks", {})
            for k in mk:
                if k.endswith("_start_epoch"):
                    nm = k[:-12]
                    phases[f"{ph}:{nm}"] = (mk[k], mk.get(nm + "_end_epoch", 1e20))
        out = {}
        for ph, (s, e) in phases.items():
            sel = [r for r in rows if s <= float(r["t_epoch"]) <= e and "client" not in r["name"] and "telegraf" not in r["name"]]
            by = {}
            for r in sel:
                try:
                    by.setdefault(r["name"], {"cpu": [], "mem": []})
                    by[r["name"]]["cpu"].append(float(r["cpu_pct"]))
                    by[r["name"]]["mem"].append(float(r["mem_mib"]))
                except ValueError:
                    pass
            out[ph] = {n: {"cpu_pct_median": T.pct(v["cpu"], .5), "mem_mib_median": T.pct(v["mem"], .5),
                           "mem_mib_max": T.pct(v["mem"], 1)} for n, v in by.items()}
        stats[f.stem] = out
    disk = {}
    for f in sorted(RAW.glob(f"disk_{a.engine}_*.txt")):
        disk[f.stem.split("_", 2)[2]] = f.read_text().strip()
    img = RAW / f"images_{a.engine}.txt"
    loads = [r for k, r in runs.items() if k.startswith("load")]
    queries = [r for k, r in runs.items() if k.startswith("query")]
    verdict = ("통과" if loads and queries and all(r["write_errors"] == 0 for r in loads) and all(q["correct_all"] for q in queries)
               else "탈락 또는 미완(세부는 runs — 질의별 correct·error)") if loads else "미실행"
    res = {"exp": "EXP-TS", "stage": 2, "engine": a.engine, "runs": runs, "resources": stats, "disk_kib": disk,
           "images": img.read_text().splitlines() if img.exists() else None, "stage2_verdict": verdict,
           "note": "판정 규칙 QUESTIONS.md §1. ②(기능·정답) 실측값. ③은 3회 반복 중앙값, ④ R06 은 r06 단계."}
    p = pathlib.Path(f"/experiments/EXP-TS/stage2_{a.engine}.json")
    p.write_text(json.dumps(res, ensure_ascii=False, indent=2))
    print(f"wrote {p} verdict={verdict}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["load", "query", "fresh", "r06", "summarize"])
    ap.add_argument("--engine", required=True, choices=list(ENGINES))
    ap.add_argument("--hours", type=int, default=24)
    ap.add_argument("--repeat", type=int, default=20)
    ap.add_argument("--fresh-seconds", type=int, default=60)
    ap.add_argument("--fresh-timeout", type=float, default=60)
    ap.add_argument("--r06-seconds", type=int, default=600)
    ap.add_argument("--r06-drain", type=float, default=300)
    a = ap.parse_args()
    {"load": load, "query": query, "fresh": fresh, "r06": r06, "summarize": summarize}[a.cmd](a)


if __name__ == "__main__":
    main()
