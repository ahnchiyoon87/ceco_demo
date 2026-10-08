"""AR-100 반응기 라인 가상설비(현장 장치).

  · Modbus/TCP 슬레이브 — soft-PLC 하나만 붙는다(계측값 읽기, 구동기·설정값 쓰기, 현장 패널 읽기)
  · 강사·실습 도구 API(API_PORT)    — 고장 주입·해제·상태 조회. 강사 계정(Basic 인증), 호스트 전용 포트
  · 현장 패널(API_PANEL_PORT)       — 모드 선택·현장 기동정지·정비·비상정지 스위치. 패널 계정(Basic 인증)
  · 정비팀 작업(API_CREW_PORT)      — 가상 정비팀이 현장에서 하는 정비(점검·교체·세정·교정). 정비팀 계정(Basic 인증)은
                                      OT 작업 요청 수신기(엣지)만 갖는다. 승인된 작업 지시만 이 길로 온다.
  강사·패널 계정은 어떤 컨테이너에도 주지 않는다(사람이 호스트에서만 쓴다).

동작에 필요한 모든 값은 plant.yaml 과 환경변수에서 읽는다.
"""
from __future__ import annotations

import asyncio
import base64
import hmac
import logging
import os
import struct
import time

import yaml
from aiohttp import web
from pymodbus.datastore import (
    ModbusSequentialDataBlock,
    ModbusServerContext,
    ModbusSlaveContext,
)
from pymodbus.server import StartAsyncTcpServer

from plant import BAD_QUALITY, ReactorPlant

logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s %(levelname)-5s %(name)s | %(message)s",
)
log = logging.getLogger("sim")

CONFIG_PATH = os.getenv("PLANT_CONFIG", "/app/plant.yaml")
MODBUS_PORT = int(os.getenv("MODBUS_PORT", "502"))
API_PORT = int(os.getenv("API_PORT", "8080"))
PANEL_PORT = int(os.getenv("API_PANEL_PORT", "8081"))
CREW_PORT = int(os.getenv("API_CREW_PORT", "8082"))
INSTRUCTOR = (os.getenv("INSTRUCTOR_USER", ""), os.getenv("INSTRUCTOR_PASSWORD", ""))
PANEL = (os.getenv("FIELD_PANEL_USER", ""), os.getenv("FIELD_PANEL_PASSWORD", ""))
CREW = (os.getenv("FIELD_CREW_USER", ""), os.getenv("FIELD_CREW_PASSWORD", ""))

FC_COIL = 1
FC_HOLDING = 3


def f32_regs(value: float) -> list[int]:
    """float32 → 홀딩레지스터 2워드 (big-endian, ABCD)."""
    return list(struct.unpack(">HH", struct.pack(">f", float(value))))


def u32_regs(value: int) -> list[int]:
    return list(struct.unpack(">HH", struct.pack(">I", int(value) & 0xFFFFFFFF)))


class Simulator:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        self.plant = ReactorPlant(cfg)
        if os.getenv("PHYSICS_TIME_SCALE"):
            self.plant.time_scale = float(os.environ["PHYSICS_TIME_SCALE"])
        self.dt = cfg["scan_interval_ms"] / 1000.0
        self.tags = cfg["tags"]
        self.coils = cfg["commands"]["coils"]
        self.holding = cfg["commands"]["holding"]
        self.seq_addr = cfg["commands"]["sequence"]["addr"]
        self.pts_addr = cfg["commands"]["plant_time"]["addr"]
        self.panel = cfg["field_panel"]["registers"]

        self.context = ModbusServerContext(
            slaves=ModbusSlaveContext(
                co=ModbusSequentialDataBlock(0, [0] * 64),
                di=ModbusSequentialDataBlock(0, [0] * 64),
                hr=ModbusSequentialDataBlock(0, [0] * 512),
                ir=ModbusSequentialDataBlock(0, [0] * 256),
            ),
            single=True,
        )
        self.store = self.context[0]
        self.crew_jobs: dict[str, object] = {}
        self._seed_defaults()
        self.started = time.time()

    # ── 초기값: 제어기가 붙기 전의 현장 상태(구동기 켜짐, 설정값 기본, 현장 스위치 REMOTE) ──
    def _seed_defaults(self) -> None:
        for key in ("pump_run", "agitator_run", "heater_enable", "cooler_enable"):
            self.store.setValues(FC_COIL, self.coils[key]["addr"], [1])
        for spec in self.holding.values():
            self.store.setValues(FC_HOLDING, spec["addr"], [int(spec["default"])])
        self.store.setValues(FC_HOLDING, self.panel["mode_selector"], [1])

    # ── 1 스캔 ────────────────────────────────────────────────
    def scan(self) -> None:
        self._read_commands()
        readings = self.plant.step(self.dt)
        self._write_readings(readings)

    def _read_commands(self) -> None:
        p = self.plant
        coil = lambda k: bool(self.store.getValues(FC_COIL, self.coils[k]["addr"], 1)[0])
        p.cmd_pump, p.cmd_agitator = coil("pump_run"), coil("agitator_run")
        p.cmd_heater, p.cmd_cooler = coil("heater_enable"), coil("cooler_enable")
        hr = lambda k: min(max(self.store.getValues(FC_HOLDING, self.holding[k]["addr"], 1)[0],
                               self.holding[k]["min"]), self.holding[k]["max"])
        p.sp_pump_speed = float(hr("pump_speed_sp"))
        p.sp_valve_open = float(hr("valve_open_sp"))
        p.sp_temp_c = hr("temp_sp_x10") / 10.0
        p.estop = bool(self.store.getValues(FC_HOLDING, self.panel["estop"], 1)[0])

    def _write_readings(self, readings: dict[str, float]) -> None:
        for t in self.tags:
            self.store.setValues(FC_HOLDING, t["hr"], f32_regs(readings[t["name"]]))
        self.store.setValues(FC_HOLDING, self.seq_addr, u32_regs(self.plant.seq))
        self.store.setValues(FC_HOLDING, self.pts_addr, u32_regs(int(self.plant.sim_time)))

    # ── 현장 패널 ─────────────────────────────────────────────
    def panel_state(self) -> dict:
        get = lambda k: self.store.getValues(FC_HOLDING, self.panel[k], 1)[0]
        return {"mode_selector": "REMOTE" if get("mode_selector") else "LOCAL",
                "operator_id": get("operator_id"), "estop": bool(get("estop"))}

    def panel_action(self, action: str, body: dict) -> dict:
        reg = self.panel
        get = lambda k: self.store.getValues(FC_HOLDING, reg[k], 1)[0]
        put = lambda k, v: self.store.setValues(FC_HOLDING, reg[k], [int(v) & 0xFFFF])
        bump = lambda k: put(k, get(k) + 1)
        if action == "mode":
            put("mode_selector", 1 if body.get("value") == "REMOTE" else 0)
        elif action == "local":
            code = {"pump": 1, "agitator": 2, "heater": 3, "cooler": 4}[body["equipment"]]
            put("local_cmd_code", code)
            put("local_cmd_value", 1 if body.get("value") else 0)
            bump("local_cmd_seq")
        elif action == "maintenance_on":
            put("operator_id", int(body.get("operator_id", 0)))
            bump("maint_on_seq")
        elif action == "maintenance_release":
            bump("maint_release_seq")
        elif action == "estop":
            put("estop", 1)
        elif action == "reset":
            put("estop", 0)
            bump("reset_seq")
        else:
            raise KeyError(action)
        log.warning("현장 패널: %s %s", action, {k: v for k, v in body.items() if k != "action"})
        return self.panel_state()

    # ── 가상 정비팀: 현장 정비 작업 ─────────────────────────────────
    async def field_task(self, task: str, job_id: str, release_maintenance: bool) -> dict:
        """현장 안전 확인 → 격리(LOTO) → 작업(설비 시간만큼) → 효과·소견 → 격리 해제(→ 필요하면 정비 해제 키).
        같은 작업 지시 ID 는 한 번만 수행한다(중복 수신은 이전 결과를 돌려준다)."""
        done = self.crew_jobs.get(job_id)
        if done is not None:
            return done if not isinstance(done, asyncio.Future) else await asyncio.shield(done)
        spec = self.cfg.get("field_tasks", {}).get(task)
        if spec is None:
            return {"status": "REJECTED", "reason": "UNKNOWN_TASK", "finding": f"정비팀이 모르는 작업: {task}"}
        fut = asyncio.get_running_loop().create_future()
        self.crew_jobs[job_id] = fut
        p = self.plant
        started = time.time()
        blocked = p.field_check(task, spec)
        if blocked:
            result = {"status": "REJECTED", "reason": "FIELD_SAFETY", "finding": blocked, "task": task}
        else:
            iso = set(spec.get("isolate", [])) - p.isolated
            p.isolated |= iso
            log.warning("정비팀 작업 시작: %s (%s, 격리 %s)", task, job_id, sorted(iso))
            try:
                await asyncio.sleep(float(spec["duration_s"]) / max(p.time_scale, 1e-9))
                effect = p.field_apply(task)
            finally:
                p.isolated -= iso
            result = {"status": "DONE" if not effect.get("mismatch") else "DONE_NO_FAULT", "task": task,
                      "effective": bool(effect.get("effective")), "finding": effect["finding"],
                      "plant_duration_s": spec["duration_s"], "wall_s": round(time.time() - started, 2)}
            if release_maintenance:
                self.panel_action("maintenance_release", {"by": "field-crew"})
                result["maintenance_released"] = True
            log.warning("정비팀 작업 완료: %s → %s", task, result["finding"])
        self.crew_jobs[job_id] = result
        fut.set_result(result)
        if len(self.crew_jobs) > 256:
            for k in list(self.crew_jobs)[:-128]:
                self.crew_jobs.pop(k, None)
        return result

    # ── 상태 스냅샷(강사 도구용. 제어 시스템 경로가 아니다) ─────────────
    def snapshot(self) -> dict:
        p = self.plant
        return {
            "site": self.cfg["site"],
            "device": self.cfg["device"],
            "uptime_s": round(time.time() - self.started, 1),
            "sim_time_s": round(p.sim_time, 1),
            "physics_time_scale": p.time_scale,
            "seq": p.seq,
            "readings": {k: (None if v == BAD_QUALITY else round(v, 4)) for k, v in p.readings.items()},
            "commands": {"pump_run": p.cmd_pump, "agitator_run": p.cmd_agitator,
                          "heater_enable": p.cmd_heater, "cooler_enable": p.cmd_cooler,
                          "pump_speed_sp": round(p.sp_pump_speed, 1), "valve_open_sp": round(p.sp_valve_open, 1),
                          "temp_sp_c": round(p.sp_temp_c, 1)},
            "thermal_model": {key: round(value, 3) for key, value in p.thermal.items()},
            "field_panel": self.panel_state(),
            "degradation": {"cw_basket": p.cw_basket, "basket_foul": {k: round(v, 3) for k, v in p.basket_foul.items()},
                            "jacket_clean": round(p.jacket_clean, 3), "bearing_wear": round(p.bearing_wear, 3),
                            "misalign": round(p.misalign, 3), "pt101_drift": round(p.pt101_drift, 3),
                            "cv_stick": round(p.cv_stick, 3), "isolated": sorted(p.isolated)},
            "active_faults": {
                k: {"elapsed_s": round(f.elapsed, 1), "remaining_s": round(f.expires_at - p._clock(f.clock), 1)}
                for k, f in p.faults.items()
            },
        }


def basic_auth(expected: tuple[str, str]):
    """Basic 인증 미들웨어. 계정이 비어 있으면 모든 요청을 거부한다(기본값으로 열리지 않게)."""
    user, password = expected
    token = base64.b64encode(f"{user}:{password}".encode()).decode() if user and password else None

    @web.middleware
    async def mw(request: web.Request, handler):
        if request.path == "/health":
            return await handler(request)
        got = request.headers.get("Authorization", "")
        if token is None or not hmac.compare_digest(got, f"Basic {token}"):
            return web.Response(status=401, headers={"WWW-Authenticate": 'Basic realm="ar100"'})
        return await handler(request)
    return mw


def build_instructor_api(sim: Simulator) -> web.Application:
    app = web.Application(middlewares=[basic_auth(INSTRUCTOR)])

    async def health(_):
        return web.json_response({"status": "ok", "seq": sim.plant.seq})

    async def state(_):
        return web.json_response(sim.snapshot())

    async def faults(_):
        return web.json_response({k: v["desc"] for k, v in sim.cfg["faults"].items()})

    async def inject(request: web.Request):
        body = await request.json()
        scenario = body.get("scenario")
        if scenario not in sim.cfg["faults"]:
            return web.json_response({"error": f"unknown scenario '{scenario}'",
                                      "available": list(sim.cfg["faults"])}, status=400)
        f = sim.plant.inject(scenario, body.get("duration_s"))
        log.warning("고장 주입: %s (%.0fs, 대상 %s)", scenario, f.expires_at - f.started_at, list(f.targets))
        return web.json_response({"injected": scenario, "duration_s": round(f.expires_at - f.started_at, 1),
                                  "targets": list(f.targets), "desc": sim.cfg["faults"][scenario]["desc"]})

    async def clear(_):
        sim.plant.clear_faults()
        log.info("전체 고장 해제")
        return web.json_response({"cleared": True})

    async def page(_):
        return web.Response(text=INSTRUCTOR_HTML, content_type="text/html")

    app.router.add_get("/", page)
    app.router.add_get("/health", health)
    app.router.add_get("/state", state)
    app.router.add_get("/faults", faults)
    app.router.add_post("/fault", inject)
    app.router.add_post("/fault/clear", clear)
    return app


INSTRUCTOR_HTML = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>AR-100 강사 도구</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:system-ui,sans-serif;background:#f6f8f7;color:#1d2a24;margin:16px;max-width:980px}
h1{font-size:19px}section{background:#fff;border:1px solid #d5e1db;border-radius:9px;padding:14px;margin:10px 0}
h2{font-size:15px;margin:0 0 8px}p{font-size:13px;color:#5b6d64;margin:4px 0 10px}
button{margin:4px 6px 4px 0;padding:9px 14px;border-radius:6px;border:1px solid #1f7a62;background:#1f7a62;color:#fff;cursor:pointer;font-size:14px}
button.alt{background:#fff;color:#1f7a62}button.reset{background:#8a3b2e;border-color:#8a3b2e}
table{border-collapse:collapse;font-size:13px}td{padding:3px 10px 3px 0;font-variant-numeric:tabular-nums}
pre{background:#eef3f0;padding:8px;border-radius:6px;font-size:12px;white-space:pre-wrap}</style></head><body>
<h1>AR-100 강사 도구 — 이상 발생</h1>
<p>버튼은 설비에 열화를 시작시킨다. 열화는 저절로 낫지 않고 현장 정비로만 회복된다. AI 화면에는 고장 이름이 전달되지 않는다.</p>
<section><h2>시나리오 1 · 반응기 온도 상승(냉각수 계통)</h2><p>주 원인: 냉각수 스트레이너 막힘 · 헷갈리는 변형: 재킷 냉각 코일 스케일</p>
<button onclick="go('strainer_fouling')">이상 발생</button><button class="alt" onclick="go('jacket_fouling')">변형: 재킷 스케일</button></section>
<section><h2>시나리오 2 · 교반기 진동(회전기계)</h2><p>주 원인: 베어링 마모 · 헷갈리는 변형: 축 정렬 불량</p>
<button onclick="go('bearing_wear')">이상 발생</button><button class="alt" onclick="go('shaft_misalignment')">변형: 축 정렬 불량</button></section>
<section><h2>시나리오 3 · 반응기 고압(계기·배출)</h2><p>주 원인: PT-101 압력계 드리프트(오지시로 인터록 작동) · 헷갈리는 변형: 배출 밸브 고착(실제 고압)</p>
<button onclick="go('pt_drift')">이상 발생</button><button class="alt" onclick="go('outlet_valve_stick')">변형: 배출 밸브 고착</button></section>
<section><h2>초기화</h2><p>모든 고장·열화를 새 설비 상태로 되돌린다(정비가 아님). 시연을 처음부터 다시 할 때만.</p>
<button class="reset" onclick="clr()">전체 초기화</button></section>
<section><h2>현재 설비(강사만 보는 진값)</h2><table id="t"></table><pre id="out"></pre></section>
<script>
const show=['TT-101','TT-104','FT-103','PDT-103','IT-102','VT-101','PT-101','PT-102','LT-102','FT-101','FT-102'];
async function go(s){const r=await fetch('fault',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({scenario:s})});document.getElementById('out').textContent=await r.text();}
async function clr(){if(!confirm('모든 고장과 열화를 지웁니다.'))return;const r=await fetch('fault/clear',{method:'POST'});document.getElementById('out').textContent=await r.text();}
async function tick(){try{const s=await (await fetch('state')).json();
document.getElementById('t').innerHTML=show.map(k=>`<tr><td>${k}</td><td>${s.readings[k]??'—'}</td></tr>`).join('')+
`<tr><td>열화</td><td>${JSON.stringify(s.degradation)}</td></tr><tr><td>고장</td><td>${Object.keys(s.active_faults).join(', ')||'없음'}</td></tr>`;}catch(e){}}
setInterval(tick,1000);tick();
</script></body></html>"""


PANEL_HTML = """<!doctype html><html lang="ko"><head><meta charset="utf-8"><title>AR-100 현장 패널</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<style>body{font-family:system-ui,sans-serif;background:#0f141b;color:#e6edf3;margin:16px}
h1{font-size:18px}section{border:1px solid #30363d;border-radius:8px;padding:12px;margin:10px 0}
button{margin:4px;padding:8px 12px;border-radius:6px;border:0;background:#2f6feb;color:#fff;cursor:pointer}
button.stop{background:#b62324}button.estop{background:#da3633;font-weight:700;font-size:16px}
pre{background:#161b22;padding:8px;border-radius:6px}</style></head><body>
<h1>AR-100 현장 패널 (가상설비 현장 스위치)</h1>
<section><b>모드 선택 스위치</b><br><button onclick="act('mode',{value:'LOCAL'})">LOCAL</button>
<button onclick="act('mode',{value:'REMOTE'})">REMOTE</button></section>
<section><b>현장 기동·정지 (LOCAL 에서만 PLC 가 받음)</b><br>
<span id="loc"></span></section>
<section><b>정비 모드</b><br>담당자 ID <input id="op" type="number" value="101" style="width:80px">
<button onclick="act('maintenance_on',{operator_id:+document.getElementById('op').value})">정비 모드 켜기</button>
<button class="stop" onclick="act('maintenance_release',{})">정비 해제 키</button></section>
<section><button class="estop" onclick="act('estop',{})">비상정지</button>
<button onclick="act('reset',{})">리셋</button></section>
<pre id="out"></pre>
<script>
const eq=['pump','agitator','heater','cooler'];
document.getElementById('loc').innerHTML=eq.map(e=>`${e} <button onclick="act('local',{equipment:'${e}',value:1})">기동</button><button class="stop" onclick="act('local',{equipment:'${e}',value:0})">정지</button>`).join('<br>');
async function act(a,b){const r=await fetch('panel',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({action:a,...b})});document.getElementById('out').textContent=await r.text();}
fetch('panel').then(r=>r.text()).then(t=>document.getElementById('out').textContent=t);
</script></body></html>"""


def build_crew_app(sim: Simulator) -> web.Application:
    """가상 정비팀 접점(OT 안). 승인·발송·수신 검사를 거친 작업 지시만 OT 수신기가 여기로 보낸다."""
    app = web.Application(middlewares=[basic_auth(CREW)])

    async def health(_):
        return web.json_response({"status": "ok"})

    async def task(request: web.Request):
        body = await request.json()
        job = str(body.get("job_order_id") or "")
        if not (8 <= len(job) <= 80):
            return web.json_response({"status": "REJECTED", "reason": "BAD_JOB_ID"}, status=400)
        result = await sim.field_task(str(body.get("task", "")), job, bool(body.get("release_maintenance")))
        return web.json_response({"job_order_id": job, **result})

    app.router.add_get("/health", health)
    app.router.add_post("/tasks", task)
    return app


def build_panel_app(sim: Simulator) -> web.Application:
    app = web.Application(middlewares=[basic_auth(PANEL)])

    async def page(_):
        return web.Response(text=PANEL_HTML, content_type="text/html")

    async def get_state(_):
        return web.json_response(sim.panel_state())

    async def post(request: web.Request):
        body = await request.json()
        try:
            return web.json_response(sim.panel_action(body.get("action", ""), body))
        except (KeyError, ValueError, TypeError) as exc:
            return web.json_response({"error": f"잘못된 패널 동작: {exc}"}, status=400)

    app.router.add_get("/", page)
    app.router.add_get("/panel", get_state)
    app.router.add_post("/panel", post)
    return app


async def main() -> None:
    with open(CONFIG_PATH) as fh:
        cfg = yaml.safe_load(fh)
    if os.getenv("SCAN_INTERVAL_MS"):
        cfg["scan_interval_ms"] = int(os.environ["SCAN_INTERVAL_MS"])

    sim = Simulator(cfg)
    log.info("AR-100 가상설비 기동 | 태그 %d점 | 스캔 %dms | 배속 %g | Modbus :%d | 강사 API :%d | 현장 패널 :%d",
             len(cfg["tags"]), cfg["scan_interval_ms"], sim.plant.time_scale, MODBUS_PORT, API_PORT, PANEL_PORT)

    for app, port in ((build_instructor_api(sim), API_PORT), (build_panel_app(sim), PANEL_PORT),
                      (build_crew_app(sim), CREW_PORT)):
        runner = web.AppRunner(app, access_log=None)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", port).start()

    async def loop():
        interval = cfg["scan_interval_ms"] / 1000.0
        nxt = time.monotonic()
        while True:
            try:
                sim.scan()
            except Exception:
                log.exception("스캔 실패")
            nxt += interval
            await asyncio.sleep(max(0.0, nxt - time.monotonic()))

    asyncio.create_task(loop())
    await StartAsyncTcpServer(context=sim.context, address=("0.0.0.0", MODBUS_PORT))


if __name__ == "__main__":
    asyncio.run(main())
