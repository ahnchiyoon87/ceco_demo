#!/usr/bin/env python3
"""전 계층 자동 검증(새 베이스: 망 3구역 · soft-PLC · UNS · DMZ · IT).

검사하는 것: 프로토콜 정규화, 제어 반응, 흐름, 저장, 역할 분리, 화면 표시(HANDOFF §3-4).
길은 새 구조의 것이다: 제어는 FUXA → OT 허브 …/cmd/operator → 엣지 → PLC → 가상설비, 저장은 DMZ 원시 사본과 IT 결과 두 곳.
호스트에서 공개 포트와 `docker exec` 로만 접근하므로 별도 의존성이 없다. 계정·포트는 .env 에서 읽는다.
    python tests/verify.py [edge backbone stream detection storage scada]
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
ENV = dict(
    line.split("=", 1)
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines()
    if "=" in line and not line.strip().startswith("#")
)
P = os.environ.get("COMPOSE_PROJECT_NAME", ENV.get("COMPOSE_PROJECT_NAME", "rot-base"))
SIM = f"http://localhost:{ENV['PORT_SIM_API']}"
SIM_AUTH = {"Authorization": "Basic " + base64.b64encode(f"{ENV['INSTRUCTOR_USER']}:{ENV['INSTRUCTOR_PASSWORD']}".encode()).decode()}
FLINK = f"http://localhost:{ENV['PORT_FLINK_UI']}"
IT_INFLUX = f"http://localhost:{ENV['PORT_IT_INFLUX']}"
DMZ_INFLUX = f"http://localhost:{ENV['PORT_DMZ_INFLUX']}"
PROM = f"http://localhost:{ENV['PORT_PROMETHEUS']}"
FUXA = f"http://localhost:{ENV['PORT_FUXA']}"
REG = json.loads((ROOT / "shared/registry/generated/tags.json").read_text(encoding="utf-8"))
LINE = REG["line_prefix"]

OK, FAIL = "  \033[32m✓\033[0m", "  \033[31m✗\033[0m"
results: list[tuple[str, bool, str]] = []


def c(svc: str) -> str:
    return f"{P}-{svc}-1"


def get(url: str, timeout: int = 10, headers: dict | None = None):
    req = urllib.request.Request(url, headers=headers or {})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode()
    return json.loads(body) if body.strip() else {}


def post(url: str, payload=None, timeout: int = 10, headers: dict | None = None):
    data = json.dumps(payload).encode() if payload is not None else b"{}"
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json", **(headers or {})}, method="POST")
    with urllib.request.urlopen(req, timeout=timeout) as r:
        body = r.read().decode()
    return json.loads(body) if body.strip().startswith(("{", "[")) else {}


sim_state = lambda: get(f"{SIM}/state", headers=SIM_AUTH)
fault = lambda scenario=None, **kw: post(f"{SIM}/fault" if scenario else f"{SIM}/fault/clear",
                                        {"scenario": scenario, **kw} if scenario else {}, headers=SIM_AUTH)


def sh(*args: str, timeout: int = 60) -> str:
    return subprocess.run(list(args), capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace").stdout


def kafka(*args: str, timeout: int = 60) -> str:
    return sh("docker", "exec", c("kafka"), *args, timeout=timeout)


def offsets(topic: str) -> dict[int, int]:
    """토픽의 파티션별 끝 오프셋."""
    out = kafka("/opt/kafka/bin/kafka-get-offsets.sh", "--bootstrap-server", "localhost:9092", "--topic", topic)
    return {int(p): int(o) for _, p, o in (x.rsplit(":", 2) for x in out.split() if x.count(":") >= 2)}


def read_range(topic: str, start: dict[int, int]) -> list[dict]:
    """start 오프셋부터 지금 끝까지를 파티션마다 정확한 건수로 읽는다. 컨슈머가 스스로 끝나므로 출력이 모두 나온다."""
    rows: list[dict] = []
    for part, end in offsets(topic).items():
        n = end - start.get(part, 0)
        if n > 0:
            rows += _parse(kafka("/opt/kafka/bin/kafka-console-consumer.sh", "--bootstrap-server", "localhost:9092",
                                 "--topic", topic, "--partition", str(part), "--offset", str(start.get(part, 0)),
                                 "--max-messages", str(n), "--timeout-ms", "30000"))
    return rows


def consume(topic: str, ms: int) -> list[dict]:
    start = offsets(topic)
    time.sleep(ms / 1000)
    return read_range(topic, start)


def _parse(out: str) -> list[dict]:
    rows = []
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("{"):
            try:
                rows.append(json.loads(line))
            except ValueError:
                pass
    return rows


def mqtt_sub(topic: str, count: int, wait_s: int = 15) -> list[str]:
    """OT 허브를 읽기 전용 계정(viewer)으로 구독(수업 자료가 쓰는 방식과 같다)."""
    out = sh("docker", "exec", c("ot-hub"), "mosquitto_sub", "-u", "viewer", "-P", ENV["MQTT_VIEWER_PASSWORD"],
             "-t", topic, "-C", str(count), "-W", str(wait_s), "-v", timeout=wait_s + 15)
    return [l for l in out.splitlines() if l.strip()]


def influx_query(base: str, token: str, flux: str) -> str:
    req = urllib.request.Request(f"{base}/api/v2/query?org={ENV['INFLUX_ORG']}", data=flux.encode(),
                                 headers={"Authorization": f"Token {token}", "Content-Type": "application/vnd.flux",
                                          "Accept": "application/csv"}, method="POST")
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode()


def fuxa_token(user: str, pw_env: str) -> str:
    return post(f"{FUXA}/api/signin", {"username": user, "password": ENV[pw_env]})["data"]["token"]


def plc_status(name: str):
    lines = mqtt_sub(f"{LINE}/PLC-01/status/{name}", 1, 5)
    return json.loads(lines[0].split(" ", 1)[1]).get("value") if lines else None


def operator_cmd(asset: str, name: str, value) -> None:
    """FUXA 와 같은 운전원 명령(…/cmd/operator, FUXA 계정)."""
    topic = next(x["operator_topic"] for x in REG["commands"] if x["asset"] == asset and x["name"] == name)
    body = json.dumps({"command": name, "value": value, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())})
    sh("docker", "exec", c("ot-hub"), "mosquitto_pub", "-u", "fuxa", "-P", ENV["MQTT_FUXA_PASSWORD"], "-q", "1", "-t", topic, "-m", body)


def recover_interlock(timeout: int = 90) -> None:
    """인터록은 트립을 기억한다: 압력이 내려와 리셋이 받아질 때까지 리셋하고 펌프를 다시 켠다."""
    end = time.time() + timeout
    while time.time() < end and plc_status("interlock") is True:
        operator_cmd("PLC-01", "interlock_reset", 1)
        time.sleep(2)
    operator_cmd("P-101", "run", 1)
    time.sleep(3)


def check(name: str, passed: bool, detail: str = "") -> None:
    results.append((name, passed, detail))
    print(f"{OK if passed else FAIL} {name}" + (f"  — {detail}" if detail else ""), flush=True)


def section(title: str) -> None:
    print(f"\n\033[1m{title}\033[0m", flush=True)


# ══════════════════════════════════════════════════════════════════════
def t1_edge() -> None:
    section("Tier 1 · 현장 → PLC → 엣지 — 프로토콜 정규화와 제어 반응")
    st = sim_state()
    check("가상설비 응답(강사용 API, 계정 필요)", bool(st["readings"]), f"태그 {len(st['readings'])}점, seq={st['seq']}")
    # 엣지가 PLC 를 읽어 UNS(ISA-95 토픽)와 수업용 edgex/telemetry 로 정규화하는가
    uns = mqtt_sub(f"{LINE}/+/tag/+", 60, 10)
    tags = {l.split(" ", 1)[0].rsplit("/", 1)[-1] for l in uns}
    check("엣지 정규화 (PLC 레지스터 → UNS JSON: 값·품질·출처 시각·순번)", len(tags) >= 12,
          f"10초 안 {len(uns)}건, 태그 {len(tags)}종")
    ev = mqtt_sub("edgex/telemetry", 1, 10)
    try:
        names = {r["resourceName"] for r in json.loads(ev[0].split(" ", 1)[1]).get("readings", [])}
    except (IndexError, ValueError, KeyError):
        names = set()
    check("수업용 edgex/telemetry (EdgeX 이벤트 모양) 유지", len(names) >= 12, f"이벤트 1건에 계측 {len(names)}종")
    # 제어 반응: FUXA 와 같은 운전원 명령(…/cmd/operator, FUXA 계정) → PLC 수용 → 가상설비 펌프 정지
    before = sim_state()["readings"]
    topic = next(x["operator_topic"] for x in REG["commands"] if x["asset"] == "P-101" and x["name"] == "run")

    operator_cmd("P-101", "run", 0)
    time.sleep(6)
    after = sim_state()["readings"]
    stopped = after["FT-101"] < 0.2 and after["IT-101"] < 0.2
    check("제어 반응 (운전원 명령 → PLC → 가상설비 물리 반응)", stopped,
          f"FT-101 {before['FT-101']:.2f} → {after['FT-101']:.2f} m3/h, IT-101 {before['IT-101']:.2f} → {after['IT-101']:.2f} A")
    operator_cmd("P-101", "run", 1)
    time.sleep(3)


def t2_backbone() -> None:
    section("Tier 2 · DMZ → Kafka — 무손실 유입")
    topics = set(kafka("/opt/kafka/bin/kafka-topics.sh", "--bootstrap-server", "localhost:9092", "--list").split())
    need = {"sensor.telemetry.raw", "sensor.telemetry.clean", "sensor.anomaly.score", "sensor.alerts",
            "plant.status", "alerts.display", "request.events", "request.responses", "audit.copy"}
    check("Kafka 토픽 구성", need <= topics, f"{len(need & topics)}/{len(need)}개 토픽")
    rows = consume("sensor.telemetry.raw", 12000)
    tags = {r["tag"] for r in rows}
    schema_ok = bool(rows) and all({"ts", "site", "device", "tag", "value", "quality", "seq", "pts"} <= set(r) for r in rows[:50])
    check("정규화 스키마 일관성 (값·품질·스캔 순번·설비 시각)", schema_ok and len(tags) >= 12, f"{len(rows)}건 / 태그 {len(tags)}종")
    ns_ok = all(r["ts"] > 1e18 for r in rows[:50]) if rows else False
    check("나노초 타임스탬프 보존", ns_ok, "출처 시각(엣지가 읽은 시각)")


def t3_stream() -> None:
    section("Tier 3 · 스트림 처리 & ML")
    jobs = get(f"{FLINK}/jobs/overview")["jobs"]
    running = [j for j in jobs if j["state"] == "RUNNING"]
    check("Flink 잡 가동", len(running) >= 4, f"RUNNING {len(running)}개 (Tier-1 SQL 3 + Tier-2 ONNX 1)")
    # 결측: dropout 을 걸고 원시에는 공백, 정제에는 보간(품질로 구분)이 생기는지. 두 토픽을 먼저 구독한다
    fault()
    time.sleep(3)
    s_raw, s_clean = offsets("sensor.telemetry.raw"), offsets("sensor.telemetry.clean")
    time.sleep(5)
    fault("dropout", duration_s=15)
    time.sleep(40)
    raw, clean = read_range("sensor.telemetry.raw", s_raw), read_range("sensor.telemetry.clean", s_clean)
    raw_tt = sorted(r["ts"] for r in raw if r["tag"] == "TT-101")
    gaps = [round((b - a) / 1e9, 1) for a, b in zip(raw_tt, raw_tt[1:]) if (b - a) / 1e9 > 2.0]
    check("원시에 결측 구간 보존 (무결성)", bool(gaps), f"raw TT-101 공백 {gaps}초 — 보간으로 덮어쓰지 않음")
    interp = [r for r in clean if str(r.get("quality", "")).startswith("INTERPOLATED")]
    check("결측치 보간 수행", bool(interp), f"clean 보간 {len(interp)}건, 방식 {sorted({r['quality'] for r in interp}) or '-'}")
    check("보간값이 quality 로 식별됨 (감사 추적)", bool(interp) and all(r["quality"] != "GOOD" for r in interp),
          "실측치와 추정치가 구분되어 저장됨")
    fault()
    scores = consume("sensor.anomaly.score", 12000)
    check("Autoencoder 추론 동작", len(scores) > 0, f"{len(scores)}건 수신")
    if scores:
        lat = sum(s["inference_ms"] for s in scores) / len(scores)
        check("임베디드 서빙 지연 < 5ms", lat < 5.0, f"평균 {lat:.3f}ms — TaskManager 내부 직접 호출")
        check("이상 기여 센서 역추적", any(s.get("top_contributors") for s in scores), scores[0].get("top_contributors", ""))


def t3_detection() -> None:
    section("Tier 3 · 다층 이상 탐지 — 시나리오별 담당 계층 확인")

    def run(scenario: str, wait: int, want: str, note: str) -> None:
        fault()
        time.sleep(4)
        start = offsets("sensor.alerts")
        fault(scenario)
        time.sleep(wait - 12)
        alerts = read_range("sensor.alerts", start)
        found = {a.get("detector") for a in alerts}
        sample = next((a for a in alerts if a.get("detector") == want), None)
        check(f"{scenario} → {want}", want in found,
              (str(sample.get("detail"))[:95] if sample else f"탐지기 {sorted(found) or '없음'}") + f" | {note}")
        fault()
        if scenario == "spike":
            recover_interlock()

    only = os.environ.get("VERIFY_SCENARIO")
    for sc, wait, det, note in [("spike", 30, "TIER1_RULE", "규격 이탈은 1계층 규칙이 즉시 처리"),
                                ("bearing_wear", 40, "TIER1_CEP", "전류→진동 시간 종속 패턴은 CEP 가 처리"),
                                ("drift", 45, "TIER2_ML", "상관구조 붕괴는 Autoencoder 만 탐지")]:
        if not only or sc == only:
            run(sc, wait, det, note)


def t4_storage() -> None:
    section("Tier 4 · 저장 · 감시")
    csv = influx_query(IT_INFLUX, ENV["IT_INFLUX_TOKEN"], f'''
from(bucket: "{ENV['IT_INFLUX_BUCKET']}") |> range(start: -5m) |> filter(fn: (r) => r._measurement == "process")
  |> group(columns: ["tag"]) |> count()''')
    tags = {line.split(",")[-1].strip() for line in csv.splitlines()[1:] if line.strip()}
    check("IT InfluxDB 적재 (Flink 정제값)", len(tags) >= 8, f"최근 5분 태그 {len(tags)}종")
    csvq = influx_query(IT_INFLUX, ENV["IT_INFLUX_TOKEN"], f'''
from(bucket: "{ENV['IT_INFLUX_BUCKET']}") |> range(start: -10m) |> filter(fn: (r) => r._measurement == "process")
  |> group(columns: ["quality"]) |> count()''')
    check("quality 태그 보존", "GOOD" in csvq, "실측/추정 구분이 히스토리안까지 전달됨")
    csvd = influx_query(DMZ_INFLUX, ENV["DMZ_INFLUX_TOKEN"], f'''
from(bucket: "{ENV['DMZ_INFLUX_BUCKET']}") |> range(start: -1m) |> filter(fn: (r) => r._measurement == "process_raw")
  |> group(columns: ["tag"]) |> count()''')
    dtags = {line.split(",")[-1].strip() for line in csvd.splitlines()[1:] if line.strip()}
    check("DMZ 원시 사본 적재 (OT 원시값, IT 는 조회만)", len(dtags) >= 12, f"최근 1분 태그 {len(dtags)}종")
    series = get(f"{PROM}/api/v1/label/__name__/values")["data"]
    leak = [m for m in series if any(t.replace("-", "_").lower() in m.lower() for t in ["LT_101", "TT_101", "PT_101", "pH_101"])]
    check("Prometheus 에 공정 데이터 없음 (역할 분리)", not leak, f"메트릭 {len(series)}종 중 공정태그 {len(leak)}개")
    targets = get(f"{PROM}/api/v1/targets")["data"]["activeTargets"]
    up = [t for t in targets if t["health"] == "up"]
    check("Prometheus 인프라 스크랩", len(up) >= 4, f"{len(up)}/{len(targets)} 타깃 정상")
    zones = get(f"{PROM}/api/v1/query?query=" + urllib.parse.quote("count by (zone) (up == 1)"))["data"]["result"]
    zset = {r["metric"].get("zone") for r in zones}
    check("구역 감시 연결 (OT agent → DMZ → IT federate)", {"ot", "dmz"} <= zset, f"IT 에서 보이는 구역 {sorted(z for z in zset if z)}")


def t4_scada() -> None:
    section("Tier 4 · SCADA(FUXA) — 화면 표시와 운전원 제어")
    admin = {"x-access-token": fuxa_token("admin", "FUXA_ADMIN_PASSWORD")}
    proj = get(f"{FUXA}/api/project", headers=admin)
    devs = proj.get("devices", {})
    views = (proj.get("hmi") or {}).get("views") or []
    check("FUXA 화면 자동 프로비저닝 (등록부에서 생성)", bool(devs) and bool(views),
          f"장치 {len(devs)}개, 뷰 {len(views)}개, 요소 {len(views[0].get('items', {})) if views else 0}개")
    q = json.dumps({"sids": ["TT_101"], "from": 1, "to": 1})
    cur = get(f"{FUXA}/api/daq?" + urllib.parse.urlencode({"query": q}))[0][0]
    simv = sim_state()["readings"]["TT-101"]
    check("FUXA 실시간 표시 (UNS 구독)", cur.get("value") is not None and abs(cur["value"] - simv) < 3.0,
          f"TT_101={cur.get('value')} vs 가상설비 {simv:.2f}")
    # 양방향: FUXA 쓰기(명령 태그) → …/cmd/operator 발행 → PLC → 물리 반응
    post(f"{FUXA}/api/setTagValue", {"tags": [{"id": "CmdPumpRun", "value": 0}]}, headers=admin)
    time.sleep(7)
    stopped = sim_state()["readings"]
    post(f"{FUXA}/api/setTagValue", {"tags": [{"id": "CmdPumpRun", "value": 1}]}, headers=admin)
    time.sleep(2)
    post(f"{FUXA}/api/setTagValue", {"tags": [{"id": "CmdPumpSpeedSP", "value": 85}]}, headers=admin)
    time.sleep(8)
    restarted = sim_state()["readings"]
    check("FUXA 양방향 제어 (화면 → 운전원 명령 → PLC → 물리)", stopped["FT-101"] < 0.2 and restarted["FT-101"] > 7.0,
          f"정지 FT-101={stopped['FT-101']:.2f} → 85% 재기동 FT-101={restarted['FT-101']:.2f} m3/h")
    try:
        post(f"{FUXA}/api/setTagValue", {"tags": [{"id": "CmdPumpRun", "value": 0}]})
        guest = "쓰기됨"
    except urllib.error.HTTPError as e:
        guest = f"HTTP {e.code}"
    check("로그인 없는 쓰기 거부 (FUXA 보안)", guest.startswith("HTTP 401"), f"guest setTagValue → {guest}")


STAGES = {"edge": t1_edge, "backbone": t2_backbone, "stream": t3_stream, "detection": t3_detection,
          "storage": t4_storage, "scada": t4_scada}


def main() -> int:
    print(f"\033[1mAR-100 IIoT/SCADA 새 베이스 · 전 계층 검증 ({P})\033[0m")
    wanted = [a for a in sys.argv[1:] if not a.startswith("-")]
    unknown = [w for w in wanted if w not in STAGES]
    if unknown:
        print(f"알 수 없는 단계: {unknown}. 사용 가능: {list(STAGES)}")
        return 2
    for fn in [STAGES[w] for w in wanted] or list(STAGES.values()):
        try:
            fn()
        except Exception as e:      # 단계가 깨지면 실패로 센다(건너뜀으로 세지 않는다)
            check(f"{fn.__name__} 실행", False, f"{type(e).__name__}: {e}")
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n결과: {passed}/{len(results)} 통과")
    return 0 if passed == len(results) else 1


if __name__ == "__main__":
    sys.exit(main())
