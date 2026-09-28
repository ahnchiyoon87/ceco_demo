"""EXP-113b L4 후보: Python 스트림 서비스 (임계치 + Z-Score + CEP 한 프로세스, 재시작 복구 포함).

V1 Flink SQL(flink/sql/01~04)의 의미를 그대로 옮긴다.
- 입력: raw 레코드(harness/SCHEMA.md). ts = ns.
- 파티션: 컨슈머 그룹 대신 토픽의 모든 파티션을 직접 할당한다(Flink Kafka 소스와 같음, 재할당 대기 없음).
- 이벤트 시간: 할당된 파티션마다 최대 이벤트 시각을 추적. 워터마크 = 활성 파티션 최대 시각의 최소값 - 5s.
  할당 뒤 아직 레코드가 없는 파티션은 워터마크를 붙잡고, 5초 동안 레코드가 없으면 유휴로 보고 제외한다(Flink idle-timeout 5s).
- 임계치는 도착 즉시 판정(V1 02와 같음). Z-Score·CEP는 워터마크 이하가 된 순서대로 판정.
- 늦은 레코드(도착 시 이미 워터마크 이하): Z-Score·CEP에서 폐기하고 dropped 토픽에 기록한다(정책: 폐기+기록).
- 재시작 복구: 1초마다 {파티션별 다음 오프셋, 버퍼, 규칙 상태, 워터마크}를 한 파일에 원자적으로 저장하고,
  시작할 때 있으면 그 지점부터 다시 읽는다(Flink 체크포인트 대응). 스냅샷 뒤 발행한 알람은 재발행될 수 있다(최소 1회).
- 출력: alerts 스키마(SCHEMA.md §3)와 같은 필드.
- V1 ONNX 잡 대응(ml.py): raw → 보간(clean 토픽) → 장치별 ONNX 점수(score 토픽) → ML 알람(alerts 토픽). 상태는 같은 스냅샷에 저장.
- 운영 지표: Prometheus 형식 :9249/metrics (V1 Flink 리포터 포트와 같음).
"""
import collections
import csv
import heapq
import json
import math
import os
import time

from confluent_kafka import OFFSET_END, Consumer, Producer, TopicPartition
from prometheus_client import Counter, Gauge, Histogram, start_http_server

import ml

BOOT = os.environ["BOOTSTRAP"]
IN = os.environ.get("IN_TOPIC", "exp.l4.raw")
OUT = os.environ.get("OUT_TOPIC", "exp.l4.alerts.python")
DROP = os.environ.get("DROP_TOPIC", "exp.l4.dropped.python")
WM_NS = int(float(os.environ.get("WATERMARK_S", "5")) * 1e9)
IDLE_S = float(os.environ.get("IDLE_S", "5"))
WITHIN_NS = int(float(os.environ.get("PATTERN_WINDOW_S", "10")) * 1e9)
IT_LIMIT = float(os.environ.get("IT102_LIMIT", "9.6"))
VT_LIMIT = float(os.environ.get("VT101_LIMIT", "7.1"))
LIMITS_CSV = os.environ.get("TAG_LIMITS", "/app/tag_limits.csv")
# Z-Score 규칙 값(V1 03_tier1_zscore.sql 과 같은 기본값). L4-10: 코드 수정 없이 환경변수로 변경
Z_WIN = int(os.environ.get("ZSCORE_WINDOW", "60"))
Z_MIN = int(os.environ.get("ZSCORE_MIN_N", "30"))
Z_LIMIT = float(os.environ.get("ZSCORE_LIMIT", "3.5"))
Z_RUN_WIN = int(os.environ.get("ZSCORE_RUN_WINDOW", "5"))
Z_RUN_MIN = int(os.environ.get("ZSCORE_RUN_MIN", "3"))
SNAP = os.environ.get("SNAPSHOT", "/state/snapshot.json")
SNAP_EVERY_S = float(os.environ.get("SNAPSHOT_EVERY_S", "1"))
ML_ON = os.environ.get("ML", "1") == "1"
CLEAN = os.environ.get("CLEAN_TOPIC", "exp.l4.clean.python")
SCORE = os.environ.get("SCORE_TOPIC", "exp.l4.score.python")
MODEL = os.environ.get("MODEL_PATH", "/opt/models/model.onnx")
META = os.environ.get("MODEL_META", "/opt/models/model_meta.json")
METRICS_PORT = int(os.environ.get("METRICS_PORT", "9249"))

M_IN = Counter("l4_records_in_total", "입력 레코드 수")
M_ALERT = Counter("l4_alerts_out_total", "발행 알람 수", ["detector"])
M_DROP = Counter("l4_late_dropped_total", "늦게 도착해 순서 규칙에서 폐기한 레코드 수")
M_CLEAN = Counter("l4_clean_out_total", "clean 발행 수", ["quality"])
M_SCORE = Counter("l4_scores_out_total", "ONNX 점수 발행 수")
M_INFER = Histogram("l4_inference_ms", "ONNX 추론 시간(ms)", buckets=(0.1, 0.25, 0.5, 1, 2, 5, 10, 50))
M_WM_LAG = Gauge("l4_watermark_lag_seconds", "현재 시각 - 워터마크")
M_SNAP_AGE = Gauge("l4_snapshot_age_seconds", "마지막 스냅샷 이후 경과")
M_RESTARTS = Gauge("l4_restarts_total", "스냅샷에서 복구해 재시작한 횟수")


def load_limits(path):
    out = {}
    for row in csv.reader(open(path, encoding="utf-8")):
        tag, unit, lsl, usl = row
        out[tag] = (unit, float(lsl) if lsl else None, float(usl) if usl else None)
    return out


def fmt(v):
    return repr(float(v)) if v is not None else "-"


class Rules:
    def __init__(self, emit, state=None):
        self.emit = emit
        self.limits = load_limits(LIMITS_CSV)
        state = state or {}
        self.win = collections.defaultdict(lambda: collections.deque(maxlen=Z_WIN),
                                           {k: collections.deque(v, maxlen=Z_WIN) for k, v in state.get("win", {}).items()})
        self.viol = collections.defaultdict(lambda: collections.deque(maxlen=Z_RUN_WIN),
                                            {k: collections.deque(v, maxlen=Z_RUN_WIN) for k, v in state.get("viol", {}).items()})
        self.pending = collections.defaultdict(list, state.get("pending", {}))

    def state(self):
        return {"win": {k: list(v) for k, v in self.win.items()},
                "viol": {k: list(v) for k, v in self.viol.items()},
                "pending": {k: v for k, v in self.pending.items() if v}}

    def on_arrival(self, r):
        # V1 02_tier1_rules.sql 은 이벤트 시간 정렬 없이 들어오는 대로 판정한다 → 늦은 레코드도 임계치 판정
        self.threshold(r)

    def on_ordered(self, r):
        # 03 ZScore(OVER ORDER BY event_time)·04 CEP(MATCH_RECOGNIZE)는 워터마크 순서로 처리
        self.zscore(r)
        self.cep(r)

    def threshold(self, r):
        lim = self.limits.get(r["tag"])
        if not lim:
            return
        unit, lsl, usl = lim
        v = r["value"]
        if (usl is not None and v > usl) or (lsl is not None and v < lsl):
            kind = "THRESHOLD_USL" if usl is not None and v > usl else "THRESHOLD_LSL"
            self.emit(r, kind, "CRITICAL", "TIER1_RULE",
                      f"{r['tag']} = {round(v, 3)} {unit} / 규격 [{fmt(lsl)}, {fmt(usl)}]")

    def zscore(self, r):
        w = self.win[r["tag"]]
        w.append(r["value"])
        n = len(w)
        if n < Z_MIN:
            return
        mu = sum(w) / n
        sd = math.sqrt(sum((x - mu) ** 2 for x in w) / (n - 1))   # STDDEV_SAMP
        z = abs(r["value"] - mu) / sd if sd > 1e-9 else 0.0
        vq = self.viol[r["tag"]]
        vq.append(1 if z > Z_LIMIT else 0)
        if sum(vq) >= Z_RUN_MIN:
            self.emit(r, "ZSCORE", "WARNING", "TIER1_ZSCORE",
                      f"{r['tag']} z={round(z, 2)} (μ={round(mu, 3)}, σ={round(sd, 4)}, 최근5중 {sum(vq)}회 위반)")

    def cep(self, r):
        # PATTERN (OVERCURRENT OTHER*? VIB) WITHIN 10s, AFTER MATCH SKIP PAST LAST ROW, PARTITION BY device
        dev = r["device"]
        if r["tag"] == "IT-102" and r["value"] > IT_LIMIT:
            self.pending[dev].append(r)
            return
        if r["tag"] == "VT-101" and r["value"] > VT_LIMIT:
            live = [p for p in self.pending[dev] if r["ts"] - p["ts"] < WITHIN_NS]
            if live:
                first = live[0]
                secs = (r["ts"] - first["ts"]) // 1_000_000_000
                self.emit(r, "CEP_BEARING", "CRITICAL", "TIER1_CEP",
                          f"교반기 전류 {round(first['value'], 2)}A (정격 120% 초과) 후 {secs}초 내 진동 "
                          f"{round(r['value'], 2)}mm/s 상회 → 베어링 열화 의심", tag="VT-101")
                self.pending[dev].clear()
                return
        self.pending[dev] = [p for p in self.pending[dev] if r["ts"] - p["ts"] < WITHIN_NS]


def load_snapshot():
    try:
        return json.load(open(SNAP, encoding="utf-8"))
    except (FileNotFoundError, ValueError):
        return None


def save_snapshot(snap):
    tmp = SNAP + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(snap, f)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, SNAP)


def main():
    prod = Producer({"bootstrap.servers": BOOT, "acks": "all", "linger.ms": 5})
    cons = Consumer({"bootstrap.servers": BOOT, "group.id": "l4-python-b", "enable.auto.commit": False})

    def emit(r, kind, sev, det, detail, tag=None):
        out = {"ts": r["ts"], "site": r["site"], "device": r["device"], "tag": tag or r["tag"],
               "value": r["value"], "alert_type": kind, "severity": sev, "detector": det, "detail": detail}
        prod.produce(OUT, value=json.dumps(out, ensure_ascii=False))
        prod.poll(0)
        M_ALERT.labels(det).inc()

    snap = load_snapshot()
    rules = Rules(emit, snap.get("rules") if snap else None)
    restarts = (snap.get("restarts", 0) + 1) if snap else 0
    M_RESTARTS.set(restarts)
    start_http_server(METRICS_PORT)
    interp = scorer = None
    if ML_ON:
        interp = ml.Interpolator(state=snap.get("interp") if snap else None)
        scorer = ml.OnnxScorer(MODEL, META, state=snap.get("scorer") if snap else None)

    def ml_in(r):
        for c in interp.process(r):
            prod.produce(CLEAN, value=json.dumps(c, ensure_ascii=False))
            M_CLEAN.labels(c["quality"]).inc()
            scorer.process(c, int(time.time() * 1000))

    def ml_fire():
        scores, alerts = scorer.fire_due(int(time.time() * 1000))
        for sc in scores:
            prod.produce(SCORE, value=json.dumps(sc, ensure_ascii=False))
            M_SCORE.inc()
            M_INFER.observe(sc["inference_ms"])
        for al in alerts:
            prod.produce(OUT, value=json.dumps(al, ensure_ascii=False))
            M_ALERT.labels(al["detector"]).inc()
    heap = [tuple(x) for x in snap["heap"]] if snap else []
    heapq.heapify(heap)
    seq = max((x[1] for x in heap), default=-1) + 1
    emitted_wm = snap["emitted_wm"] if snap else -1
    next_off = {int(k): v for k, v in snap["offsets"].items()} if snap else {}

    parts = sorted(cons.list_topics(IN, timeout=30).topics[IN].partitions)
    cons.assign([TopicPartition(IN, p, next_off.get(p, OFFSET_END)) for p in parts])
    now = time.time()
    pmax = {p: None for p in parts}       # None = 할당 뒤 아직 레코드 없음 → 워터마크를 붙잡는다
    pseen = {p: now for p in parts}
    print(f"start: snapshot={'yes' if snap else 'no'} offsets={next_off} wm={emitted_wm} heap={len(heap)}", flush=True)

    last_snap = now
    while True:
        wait = 0.2
        if scorer is not None:
            nf = scorer.next_fire_ms()
            if nf is not None:
                wait = max(0.0, min(wait, nf / 1000 - time.time()))
        m = cons.poll(wait)
        now = time.time()
        if m is not None and not m.error():
            p = m.partition()
            next_off[p] = m.offset() + 1
            try:
                r = json.loads(m.value())
                r["value"] = float(r["value"])
            except (ValueError, KeyError, TypeError):
                r = None
            if r is not None:
                M_IN.inc()
                rules.on_arrival(r)
                if interp is not None:
                    ml_in(r)
                pmax[p] = r["ts"] if pmax[p] is None else max(pmax[p], r["ts"])
                pseen[p] = now
                if r["ts"] <= emitted_wm:
                    prod.produce(DROP, value=json.dumps({**r, "reason": "late", "watermark_ns": emitted_wm}))
                    M_DROP.inc()
                else:
                    heapq.heappush(heap, (r["ts"], seq, r))
                    seq += 1
        active = [pmax[p] for p in parts if now - pseen[p] <= IDLE_S]
        if active and None not in active:
            wm = min(active) - WM_NS
            if wm > emitted_wm:
                emitted_wm = wm
        while heap and heap[0][0] <= emitted_wm:
            rules.on_ordered(heapq.heappop(heap)[2])
        if scorer is not None:
            ml_fire()
        prod.poll(0)
        if emitted_wm > 0:
            M_WM_LAG.set(now - emitted_wm / 1e9)
        M_SNAP_AGE.set(now - last_snap)
        if now - last_snap >= SNAP_EVERY_S:
            prod.flush(5)   # 스냅샷 이전 알람은 브로커에 확정
            save_snapshot({"offsets": next_off, "heap": heap, "emitted_wm": emitted_wm, "rules": rules.state(),
                           "restarts": restarts,
                           "interp": interp.state() if interp else None, "scorer": scorer.state() if scorer else None})
            last_snap = now


if __name__ == "__main__":
    main()
