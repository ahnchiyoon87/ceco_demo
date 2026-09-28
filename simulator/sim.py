"""AR-100 반응기 라인 시뮬레이터.

  · Modbus/TCP 슬레이브  — EdgeX device-modbus 수집 + FUXA 양방향 제어
  · REST API             — 고장 주입 / 상태 조회
  · (선택) MQTT 직발행    — EdgeX 를 우회하는 lite 프로파일용

동작에 필요한 모든 값은 plant.yaml 과 환경변수에서 읽는다.
"""
from __future__ import annotations

import asyncio
import json
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

# lite 프로파일: EdgeX 를 거치지 않고 EMQX 로 직접 발행
DIRECT_MQTT = os.getenv("DIRECT_MQTT_ENABLE", "false").lower() == "true"
MQTT_HOST = os.getenv("MQTT_HOST", "emqx")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))
MQTT_TOPIC_PREFIX = os.getenv("MQTT_TOPIC_PREFIX", "iiot")

# Modbus 함수코드 → 데이터스토어 선택자
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
        self.dt = cfg["scan_interval_ms"] / 1000.0
        self.tags = cfg["tags"]
        self.coils = cfg["commands"]["coils"]
        self.holding = cfg["commands"]["holding"]
        self.seq_addr = cfg["commands"]["sequence"]["addr"]

        self.context = ModbusServerContext(
            slaves=ModbusSlaveContext(
                co=ModbusSequentialDataBlock(0, [0] * 64),
                di=ModbusSequentialDataBlock(0, [0] * 64),
                hr=ModbusSequentialDataBlock(0, [0] * 256),
                ir=ModbusSequentialDataBlock(0, [0] * 256),
            ),
            single=True,
        )
        self.store = self.context[0]

        # 외부(FUXA/EdgeX) 쓰기와 autopilot 쓰기를 구분하기 위한 마지막 기록값
        self._last_written: dict[str, int] = {}
        self._seed_defaults()
        self.mqtt = self._init_mqtt() if DIRECT_MQTT else None
        self.started = time.time()

    # ── 초기 설정치 적재 ──────────────────────────────────────
    def _seed_defaults(self) -> None:
        self.store.setValues(FC_COIL, self.coils["pump_run"]["addr"], [1])
        self.store.setValues(FC_COIL, self.coils["agitator_run"]["addr"], [1])
        self.store.setValues(FC_COIL, self.coils["heater_enable"]["addr"], [1])
        if "cooler_enable" in self.coils:
            self.store.setValues(FC_COIL, self.coils["cooler_enable"]["addr"], [0])
        for key, spec in self.holding.items():
            self.store.setValues(FC_HOLDING, spec["addr"], [int(spec["default"])])
            self._last_written[key] = int(spec["default"])
        self.plant.sp_pump_speed = float(self.holding["pump_speed_sp"]["default"])
        self.plant.sp_valve_open = float(self.holding["valve_open_sp"]["default"])
        self.plant.sp_temp_c = self.holding["temp_sp_x10"]["default"] / 10.0

    def _init_mqtt(self):
        import paho.mqtt.client as mqtt

        c = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2,
            client_id=f"sim-{self.cfg['device']}",
            clean_session=False,      # 세션 영속 (PDF p.4 권고)
        )
        c.connect_async(MQTT_HOST, MQTT_PORT, keepalive=30)
        c.loop_start()
        log.info("MQTT 직발행 활성화 → %s:%s", MQTT_HOST, MQTT_PORT)
        return c

    # ── 1 스캔 ────────────────────────────────────────────────
    def scan(self) -> None:
        self._read_commands()
        readings = self.plant.step(self.dt)
        self._write_readings(readings)
        if self.mqtt:
            self._publish(readings)

    def _read_commands(self) -> None:
        p = self.plant
        p.cmd_pump = bool(self.store.getValues(FC_COIL, self.coils["pump_run"]["addr"], 1)[0])
        p.cmd_agitator = bool(self.store.getValues(FC_COIL, self.coils["agitator_run"]["addr"], 1)[0])
        p.cmd_heater = bool(self.store.getValues(FC_COIL, self.coils["heater_enable"]["addr"], 1)[0])
        p.cmd_cooler = bool(self.store.getValues(FC_COIL, self.coils["cooler_enable"]["addr"], 1)[0]) if "cooler_enable" in self.coils else False

        for key, spec in self.holding.items():
            raw = self.store.getValues(FC_HOLDING, spec["addr"], 1)[0]
            if raw != self._last_written.get(key):
                # 직전에 우리가 쓴 값과 다르다 ⇒ 운전원(FUXA/EdgeX)의 수동 조작
                raw = min(max(raw, spec["min"]), spec["max"])
                p.note_manual("temp_sp_c" if key == "temp_sp_x10" else key)
                log.info("수동 조작 감지: %s = %s", key, raw)
            if key == "pump_speed_sp":
                p.sp_pump_speed = float(raw)
            elif key == "valve_open_sp":
                p.sp_valve_open = float(raw)
            elif key == "temp_sp_x10":
                p.sp_temp_c = raw / 10.0

    def _write_readings(self, readings: dict[str, float]) -> None:
        for t in self.tags:
            self.store.setValues(FC_HOLDING, t["hr"], f32_regs(readings[t["name"]]))
        self.store.setValues(FC_HOLDING, self.seq_addr, u32_regs(self.plant.seq))
        self.store.setValues(FC_COIL, self.coils["interlock"]["addr"], [int(self.plant.interlocked)])

        # autopilot 이 움직인 설정치를 레지스터에 반영 (운전원 화면 동기화)
        p = self.plant
        for key, value in (
            ("pump_speed_sp", int(round(p.sp_pump_speed))),
            ("valve_open_sp", int(round(p.sp_valve_open))),
            ("temp_sp_x10", int(round(p.sp_temp_c * 10))),
        ):
            self.store.setValues(FC_HOLDING, self.holding[key]["addr"], [value])
            self._last_written[key] = value

    def _publish(self, readings: dict[str, float]) -> None:
        ts = time.time_ns()
        site, dev = self.cfg["site"], self.cfg["device"]
        for tag, value in readings.items():
            if value == BAD_QUALITY:
                continue      # 통신 불량 → 아예 발행하지 않음 (실제 결측 구간 생성)
            payload = json.dumps(
                {
                    "ts": ts,
                    "site": site,
                    "device": dev,
                    "tag": tag,
                    "value": round(value, 4),
                    "quality": "GOOD",
                    "seq": self.plant.seq,
                }
            )
            self.mqtt.publish(f"{MQTT_TOPIC_PREFIX}/{site}/{dev}/{tag}", payload, qos=1)

    # ── 상태 스냅샷 ───────────────────────────────────────────
    def snapshot(self) -> dict:
        p = self.plant
        return {
            "site": self.cfg["site"],
            "device": self.cfg["device"],
            "uptime_s": round(time.time() - self.started, 1),
            "sim_time_s": round(p.sim_time, 1),
            "seq": p.seq,
            "readings": {
                k: (None if v == BAD_QUALITY else round(v, 4)) for k, v in p.readings.items()
            },
            "commands": {
                "pump_run": p.cmd_pump,
                "agitator_run": p.cmd_agitator,
                "heater_enable": p.cmd_heater,
                "cooler_enable": p.cmd_cooler,
                "pump_speed_sp": round(p.sp_pump_speed, 1),
                "valve_open_sp": round(p.sp_valve_open, 1),
                "temp_sp_c": round(p.sp_temp_c, 1),
            },
            "interlock": p.interlocked,
            "thermal_model": {key: round(value, 3) for key, value in p.thermal.items()},
            "active_faults": {
                k: {"elapsed_s": round(f.elapsed, 1),
                    "remaining_s": round(f.expires_at - p.sim_time, 1)}
                for k, f in p.faults.items()
            },
        }


def build_api(sim: Simulator) -> web.Application:
    app = web.Application()

    async def health(_):
        return web.json_response({"status": "ok", "seq": sim.plant.seq})

    async def state(_):
        return web.json_response(sim.snapshot())

    async def tags(_):
        return web.json_response(sim.cfg["tags"])

    async def faults(_):
        return web.json_response(
            {k: v["desc"] for k, v in sim.cfg["faults"].items()}
        )

    async def inject(request: web.Request):
        body = await request.json()
        scenario = body.get("scenario")
        if scenario not in sim.cfg["faults"]:
            return web.json_response(
                {"error": f"unknown scenario '{scenario}'",
                 "available": list(sim.cfg["faults"])}, status=400)
        f = sim.plant.inject(scenario, body.get("duration_s"))
        log.warning("고장 주입: %s (%.0fs, 대상 %s)", scenario, f.expires_at - f.started_at, list(f.targets))
        return web.json_response(
            {"injected": scenario,
             "duration_s": round(f.expires_at - f.started_at, 1),
             "targets": list(f.targets),
             "desc": sim.cfg["faults"][scenario]["desc"]})

    async def clear(_):
        sim.plant.clear_faults()
        log.info("전체 고장 해제")
        return web.json_response({"cleared": True})

    app.router.add_get("/health", health)
    app.router.add_get("/state", state)
    app.router.add_get("/tags", tags)
    app.router.add_get("/faults", faults)
    app.router.add_post("/fault", inject)
    app.router.add_post("/fault/clear", clear)
    return app


async def main() -> None:
    with open(CONFIG_PATH) as fh:
        cfg = yaml.safe_load(fh)
    if os.getenv("SCAN_INTERVAL_MS"):
        cfg["scan_interval_ms"] = int(os.environ["SCAN_INTERVAL_MS"])

    sim = Simulator(cfg)
    log.info("AR-100 시뮬레이터 기동 | 태그 %d점 | 스캔 %dms | Modbus :%d | API :%d",
             len(cfg["tags"]), cfg["scan_interval_ms"], MODBUS_PORT, API_PORT)

    runner = web.AppRunner(build_api(sim))
    await runner.setup()
    await web.TCPSite(runner, "0.0.0.0", API_PORT).start()

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
