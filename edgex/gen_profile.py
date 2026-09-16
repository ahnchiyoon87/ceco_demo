#!/usr/bin/env python3
"""plant.yaml → EdgeX 디바이스 프로파일 / 디바이스 정의 생성기.

태그·레지스터맵의 단일 출처는 simulator/plant.yaml 이다.
plant.yaml 을 고친 뒤 `make regen-edgex` 로 재생성한다.
"""
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
cfg = yaml.safe_load((ROOT / "simulator" / "plant.yaml").read_text())

PROFILE = "AR100-Reactor-Line"
resources, sensor_ops, control_ops, status_ops = [], [], [], []

# ── 계측 태그: Float32 (홀딩레지스터 2워드, big-endian) ──
for t in cfg["tags"]:
    resources.append({
        "name": t["name"],
        "isHidden": True,
        "description": f"{t['desc']} [{t['unit']}]",
        "attributes": {"primaryTable": "HOLDING_REGISTERS", "startingAddress": t["hr"]},
        "properties": {"valueType": "Float32", "readWrite": "R", "units": t["unit"]},
    })
    sensor_ops.append({"deviceResource": t["name"]})

# ── 스캔 시퀀스 카운터 (Uint32) ──
resources.append({
    "name": "SEQ",
    "isHidden": True,
    "description": "스캔 시퀀스 카운터 (QoS1 중복 진단용)",
    "attributes": {"primaryTable": "HOLDING_REGISTERS",
                   "startingAddress": cfg["commands"]["sequence"]["addr"]},
    "properties": {"valueType": "Uint32", "readWrite": "R"},
})
status_ops.append({"deviceResource": "SEQ"})

# ── 제어 코일 ──
for key, spec in cfg["commands"]["coils"].items():
    ro = spec.get("readonly", False)
    name = "".join(p.capitalize() for p in key.split("_"))
    resources.append({
        "name": name,
        "isHidden": True,
        "description": spec["desc"],
        "attributes": {"primaryTable": "COILS", "startingAddress": spec["addr"]},
        "properties": {"valueType": "Bool", "readWrite": "R" if ro else "RW"},
    })
    # EdgeX 는 deviceCommand 의 readWrite 와 소속 리소스의 readWrite 가
    # 일치할 것을 요구한다. 읽기전용 리소스는 별도 커맨드로 분리한다.
    (status_ops if ro else control_ops).append({"deviceResource": name})

# ── 제어 설정치 (홀딩레지스터 Int16) ──
for key, spec in cfg["commands"]["holding"].items():
    name = "".join(p.capitalize() for p in key.split("_"))
    props = {"valueType": "Int16", "readWrite": "RW",
             "minimum": spec["min"], "maximum": spec["max"]}
    if key.endswith("_x10"):
        props["scale"] = 0.1          # degC*10 → degC 로 EdgeX 가 환산
    resources.append({
        "name": name,
        "isHidden": True,
        "description": spec["desc"],
        "attributes": {"primaryTable": "HOLDING_REGISTERS", "startingAddress": spec["addr"]},
        "properties": props,
    })
    control_ops.append({"deviceResource": name})

profile = {
    "name": PROFILE,
    "manufacturer": "uEngine",
    "model": "AR-100",
    "labels": ["reactor", "modbus-tcp", "iiot-demo"],
    "description": "AR-100 반응기 라인 — 계측 12점 + 양방향 제어",
    "deviceResources": resources,
    "deviceCommands": [
        # autoEvents 가 참조하는 소스. 12개 리딩이 단일 Event 로 묶여 발행된다.
        {"name": "AllSensors", "readWrite": "R", "isHidden": False,
         "resourceOperations": sensor_ops},
        {"name": "Control", "readWrite": "RW", "isHidden": False,
         "resourceOperations": control_ops},
        {"name": "Status", "readWrite": "R", "isHidden": False,
         "resourceOperations": status_ops},
    ],
}

interval_ms = cfg["scan_interval_ms"]
devices = {
    "deviceList": [{
        "name": cfg["device"],
        "profileName": PROFILE,
        "description": "AR-100 반응기 라인 (Modbus/TCP)",
        "labels": [cfg["site"]],
        "protocols": {
            "modbus-tcp": {
                "Address": "plant-simulator", "Port": 502, "UnitID": 1,
                "Timeout": 5, "IdleTimeout": 5,
            }
        },
        "autoEvents": [
            {"interval": f"{interval_ms}ms", "onChange": False, "sourceName": "AllSensors"}
        ],
    }]
}

hdr = "# ⚠ 자동 생성 파일 — simulator/plant.yaml 수정 후 `make regen-edgex` 로 재생성\n"
(Path(__file__).parent / "profiles" / "ar100.profile.yaml").write_text(
    hdr + yaml.safe_dump(profile, allow_unicode=True, sort_keys=False, default_flow_style=False))
(Path(__file__).parent / "devices" / "ar100.devices.yaml").write_text(
    hdr + yaml.safe_dump(devices, allow_unicode=True, sort_keys=False, default_flow_style=False))
print(f"생성 완료: deviceResources={len(resources)}  autoEvent={interval_ms}ms")
