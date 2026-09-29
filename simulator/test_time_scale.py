"""V2 시간 배속: 하나의 설비 시계로 서서히 진행하는 현상이 자연스럽게 빨라지고, 이상은 10초 안에 드러난다.
기본값(plant.yaml physics_time_scale)으로 띄운 설비를 그대로 시험한다."""
import copy
from pathlib import Path
import unittest

import yaml
from plant import ReactorPlant

CONFIG = yaml.safe_load(Path(__file__).with_name("plant.yaml").read_text(encoding="utf-8"))


def model(**over):
    cfg = copy.deepcopy(CONFIG)
    cfg["autopilot"]["enabled"] = False
    cfg["noise"] = {tag: 0 for tag in cfg["noise"]}
    cfg.update(over)
    m = ReactorPlant(cfg)
    m.sp_temp_c = 72.0
    for _ in range(5):                       # 정상 상태
        m.step(1)
    return m


def run_until(m, cond, limit):
    for s in range(1, limit + 1):
        m.step(1)
        if cond(m):
            return s
    return None


class TimeScaleTest(unittest.TestCase):
    def test_default_heater_stuck_crosses_usl_within_5s(self):
        m = model()
        m.cmd_heater = False
        m.inject("heater_stuck")
        self.assertIsNotNone(run_until(m, lambda m: m.temp_c > 95, 5), "히터 고착 뒤 5초 안에 TT-101 > 95")

    def test_default_bearing_current_then_vibration_within_10s(self):
        m = model()
        m.inject("bearing_wear")
        it = run_until(m, lambda m: m._agitator_current(m.rx_vol / (m.p_rx["area_m2"] * m.p_rx["height_m"])) > 9.6, 10)
        m2 = model(); m2.inject("bearing_wear")
        vt = run_until(m2, lambda m: m._vibration(m.rx_vol / (m.p_rx["area_m2"] * m.p_rx["height_m"])) > 7.1, 10)
        self.assertIsNotNone(it); self.assertIsNotNone(vt)
        self.assertLess(it, vt, "전류가 먼저, 진동이 나중(CEP 선후)")
        self.assertLessEqual(vt - it, 10, "CEP 10초 창 안")

    def test_default_drift_rises_gradually_not_a_jump(self):
        m = model()
        m.inject("drift")
        base = m._ph()
        ramp = []
        for _ in range(10):
            m.step(1)
            f = m.faults["drift"]
            ramp.append(min(1.0, f.elapsed / f.ramp_s))
        self.assertLess(ramp[0], 0.5, "첫 1초에 다 오르지 않는다(서서히)")
        self.assertGreaterEqual(ramp[-1], 1.0, "10초 안에 최대에 이른다")

    def test_event_fault_lasts_real_seconds(self):
        m = model()
        m.inject("spike")
        for _ in range(7):
            m.step(1)
        self.assertIn("spike", m.faults, "순간 사건은 실제 초 동안 지속")
        for _ in range(2):
            m.step(1)
        self.assertNotIn("spike", m.faults)

    def test_large_scale_temperature_control_stays_bounded(self):
        m = model(physics_time_scale=300)
        temps = []
        for _ in range(60):
            m.step(1)
            temps.append(m.temp_c)
        self.assertLess(max(temps[-20:]) - min(temps[-20:]), 1.0)


if __name__ == "__main__":
    unittest.main()
