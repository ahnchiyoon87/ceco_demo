"""V2 물리 배속: 실습에서 고장 결과가 10초 안에 보이고, 큰 배속에서도 제어가 발산하지 않는다."""
import copy
from pathlib import Path
import unittest

import yaml
from plant import ReactorPlant

CONFIG = yaml.safe_load(Path(__file__).with_name("plant.yaml").read_text(encoding="utf-8"))


def model(scale=None):
    cfg = copy.deepcopy(CONFIG)
    cfg["autopilot"]["enabled"] = False
    cfg["noise"] = {tag: 0 for tag in cfg["noise"]}
    if scale is not None:
        cfg["physics_time_scale"] = scale
    m = ReactorPlant(cfg)
    m.sp_temp_c = 72.0
    return m


class TimeScaleTest(unittest.TestCase):
    def test_default_scale_heater_stuck_crosses_usl_within_10s(self):
        m = model()
        for _ in range(600):                       # 1배속 기준 정상 상태 도달(배속 300 이면 즉시)
            m.step(1)
        self.assertLess(m.temp_c, 95)
        m.cmd_heater = False
        m.inject("heater_stuck", 1200)
        crossed = next((s for s in range(1, 11) if (m.step(1), m.temp_c)[1] > 95), None)
        self.assertIsNotNone(crossed, "히터 고착 뒤 실제 10초 안에 TT-101 이 95°C 를 넘어야 한다")

    def test_large_scale_temperature_control_stays_bounded(self):
        m = model(300)
        temps = []
        for _ in range(120):
            m.step(1)
            temps.append(m.temp_c)
        tail = temps[-30:]
        self.assertLess(max(tail) - min(tail), 1.0, "P 제어가 소구간 적분으로 안정해야 한다")
        self.assertLess(abs(tail[-1] - m.sp_temp_c), 5.0)

    def test_fault_timing_is_real_seconds(self):
        m = model(300)
        m.inject("bearing_wear", 30)
        for _ in range(5):
            m.step(1)
        self.assertEqual(m.vib_wear, 0.0, "진동은 실제 6초 뒤부터(CEP 선후 간격 유지)")
        for _ in range(3):
            m.step(1)
        self.assertGreater(m.vib_wear, 0.0)
        for _ in range(30):
            m.step(1)
        self.assertNotIn("bearing_wear", m.faults, "고장 지속은 실제 초")


if __name__ == "__main__":
    unittest.main()
