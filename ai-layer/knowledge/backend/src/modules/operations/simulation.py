"""Operator-only training controls. Fault truth is never added to agent evidence."""
import json
import os
import time
from uuid import UUID
from typing import Literal
from urllib.request import Request, urlopen
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, ConfigDict, model_validator
from psycopg.types.json import Jsonb
from .api import connection

router = APIRouter(prefix="/api/operations/simulation", tags=["training"])
# Deliberately fixed to the existing local training simulator, not an arbitrary URL.
BASE = "http://host.docker.internal:27080"


def enabled():
    if os.environ.get("SIMULATOR_ACTIONS_ENABLED") != "true":
        raise HTTPException(403, "교육용 시뮬레이터 조작이 비활성화되어 있습니다.")


def simulator(path, body=None):
    request = Request(BASE + path, data=None if body is None else json.dumps(body).encode(),
                      headers={"Content-Type": "application/json"})
    try:
        with urlopen(request, timeout=5) as response:
            return json.load(response)
    except (OSError, ValueError):
        raise HTTPException(502, "시뮬레이터 응답을 확인하지 못했습니다. 상태를 새로 조회하세요. 요청은 자동 재전송하지 않습니다.")


@router.get("")
def status():
    enabled()
    state = simulator("/state")
    return {"active_faults": state.get("active_faults", {}), "seq": state["seq"],
            "site": state["site"], "device": state["device"],
            "agitator_run": state["commands"]["agitator_run"],
            "cooler_enable": state["commands"].get("cooler_enable"), "interlock": state["interlock"]}


@router.post("/mixer-anomaly")
def inject():
    enabled()
    state = status()
    if state["interlock"] or not state["agitator_run"]:
        raise HTTPException(409, "교반기가 운전 중이어야 합니다. 대시보드의 설비 직접 조작에서 상태를 확인하고 기동하세요.")
    if state["active_faults"]:
        raise HTTPException(409, "이미 실습 이상이 적용되어 있습니다. 해제 후 다시 시작하세요.")
    return simulator("/fault", {"scenario": "bearing_wear", "duration_s": 600})


@router.post("/thermal-anomaly")
def inject_thermal():
    enabled()
    state = status()
    if state["interlock"]:
        raise HTTPException(409, "고압 인터록이 남아 있습니다. 온도 실습을 시작하지 않았습니다.")
    if state["active_faults"]:
        raise HTTPException(409, "이미 실습 이상이 적용되어 있습니다. 해제 후 다시 시작하세요.")
    if state["cooler_enable"] is not False:
        raise HTTPException(409, "냉각 기능이 지원되고 냉각 명령이 꺼져 있어야 합니다. 설비 직접 조작에서 확인하세요.")
    return simulator("/fault", {"scenario": "heater_stuck", "duration_s": 1200})


@router.post("/clear")
def clear():
    enabled()
    return simulator("/fault/clear", {})


# Matches simulator/plant.yaml. Only this fixed educational plant is writable.
CONTROL_MAP = {
    "pump_run": ("coil", 0, 0, 1, 1),
    "agitator_run": ("coil", 1, 0, 1, 1),
    "heater_enable": ("coil", 2, 0, 1, 1),
    "cooler_enable": ("coil", 3, 0, 1, 1),
    "pump_speed_sp": ("register", 100, 0, 100, 1),
    "valve_open_sp": ("register", 101, 0, 100, 1),
    "temp_sp_c": ("register", 102, 20, 100, 10),
}


class OperatorCommand(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)
    request_id: UUID
    target: Literal["pump_run", "agitator_run", "heater_enable", "cooler_enable", "pump_speed_sp", "valve_open_sp", "temp_sp_c"]
    value: float

    @model_validator(mode="after")
    def validate_value(self):
        _, _, low, high, scale = CONTROL_MAP[self.target]
        if not low <= self.value <= high or abs(self.value * scale - round(self.value * scale)) > 1e-7:
            raise ValueError("설정 범위 또는 입력 단위가 맞지 않습니다.")
        return self


@router.get("/controls")
def control_history():
    enabled()
    with connection() as conn:
        if not conn.execute("SELECT to_regclass('manufacturing_operator_commands') AS name").fetchone()["name"]:
            return {"items": []}
        return {"items": conn.execute("SELECT id,request,result,created_at FROM manufacturing_operator_commands ORDER BY created_at DESC LIMIT 20").fetchall()}


def write_operator_command(command, before):
    from pymodbus.client import ModbusTcpClient
    kind, address, _, _, scale = CONTROL_MAP[command.target]
    client = ModbusTcpClient("host.docker.internal", port=27002, timeout=3, retries=0)
    attempted = False
    try:
        if not client.connect():
            return {"status": "not_executed", "reason": "Modbus 연결 실패. 명령을 보내지 않았습니다."}
        attempted = True
        response = (client.write_coil(address, bool(command.value), slave=1) if kind == "coil"
                    else client.write_register(address, round(command.value * scale), slave=1))
        if response.isError():
            return {"status": "uncertain", "reason": "명령 응답 오류. 현재 상태를 확인하세요. 자동 재전송하지 않습니다."}
        deadline = time.monotonic() + 8
        after = None
        while time.monotonic() < deadline:
            after = simulator("/state")
            actual = after.get("commands", {}).get(command.target)
            if (after.get("seq", -1) > before["seq"]
                    and (after.get("site"), after.get("device")) == (before.get("site"), before.get("device"))
                    and actual is not None and abs(float(actual) - command.value) < 0.05):
                return {"status": "verified", "reason": "새 설비 상태에서 명령 반영을 확인했습니다. 온도 회복이나 고장 해소 확인은 아닙니다." if command.target in {"cooler_enable", "temp_sp_c"} else "새 설비 상태에서 반영을 확인했습니다.", "after": after}
            time.sleep(.25)
        return {"status": "uncertain", "reason": "명령은 전송했지만 반영을 확인하지 못했습니다. 현재 상태를 확인하세요.", "after": after}
    except Exception:
        return {"status": "uncertain" if attempted else "not_executed", "reason": "조작 통신 실패. 자동 재전송하지 않습니다."}
    finally:
        client.close()


def validate_operator_state(command, before):
    if command.target == "cooler_enable" and type(before.get("commands", {}).get("cooler_enable")) is not bool:
        raise HTTPException(409, "현재 시뮬레이터에는 냉각기 제어가 없습니다. 명령을 보내지 않았습니다.")
    if command.target.endswith(("_run", "_enable")) and command.value == 1:
        faults = set(before.get("active_faults", {}))
        # The educational cooler may mitigate a thermal fault, but does not
        # clear it or override the existing pressure interlock.
        thermal_mitigation = command.target == "cooler_enable" and faults <= {"heater_stuck", "cooling_loss"}
        if before["interlock"] or (faults and not thermal_mitigation):
            raise HTTPException(409, "인터록 또는 이 기동으로 대응할 수 없는 실습 이상이 남아 있습니다. 상태를 확인하세요.")


@router.post("/control")
def control(command: OperatorCommand):
    enabled()
    # Commit receipt before contacting the plant. A repeated request never writes again.
    with connection() as conn:
        conn.execute("""CREATE TABLE IF NOT EXISTS manufacturing_operator_commands (
            id uuid PRIMARY KEY, request jsonb NOT NULL, result jsonb NOT NULL,
            created_at timestamptz NOT NULL DEFAULT now())""")
        conn.execute("SELECT pg_advisory_xact_lock(hashtextextended(%s,2))", (str(command.request_id),))
        previous = conn.execute("SELECT request,result FROM manufacturing_operator_commands WHERE id=%s", (command.request_id,)).fetchone()
        payload = command.model_dump(mode="json")
        if previous:
            if previous["request"] != payload:
                raise HTTPException(409, "같은 요청 번호로 다른 조작을 보낼 수 없습니다.")
            return previous["result"]
        before = simulator("/state")
        validate_operator_state(command, before)
        pending = {"status": "uncertain", "reason": "접수된 조작입니다. 처리 중이거나 결과 확인이 필요합니다. 재전송하지 않습니다.", "before": before}
        conn.execute("INSERT INTO manufacturing_operator_commands(id,request,result) VALUES (%s,%s,%s)",
                     (command.request_id, Jsonb(payload), Jsonb(pending)))
    result = {**write_operator_command(command, before), "before": before, "target": command.target, "requested": command.value}
    with connection() as conn:
        conn.execute("UPDATE manufacturing_operator_commands SET result=%s WHERE id=%s", (Jsonb(result), command.request_id))
    return result
