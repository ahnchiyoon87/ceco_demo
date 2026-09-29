"""Deterministic local model tests; no running equipment or database is used."""
import copy
from pathlib import Path
import unittest

import yaml
from plant import ReactorPlant

CONFIG = yaml.safe_load(Path(__file__).with_name("plant.yaml").read_text(encoding="utf-8"))


def plant():
    cfg = copy.deepcopy(CONFIG)
    cfg["autopilot"]["enabled"] = False
    cfg["noise"] = {tag: 0 for tag in cfg["noise"]}
    cfg["physics_time_scale"] = 1   # 물리 방정식 자체 검증(시간 축 고정)
    model = ReactorPlant(cfg)
    model.temp_c = model.jacket_c = 100.0
    model.sp_temp_c = 70.0
    model.cmd_heater = model.cmd_pump = False
    model.sp_valve_open = 0
    return model


class ThermalModelTest(unittest.TestCase):
    def test_enabled_cooler_removes_heat_and_lowers_actual_temperature(self):
        baseline, cooling = plant(), plant()
        cooling.cmd_cooler = True
        for _ in range(120):
            baseline.step(1)
            cooling.step(1)
        self.assertLess(cooling.temp_c, baseline.temp_c - 5)
        self.assertEqual(cooling.readings["TT-101"], cooling.temp_c)
        self.assertGreater(cooling.thermal["cooler_kw"], 0)
        self.assertEqual(baseline.thermal["cooler_kw"], 0)

    def test_cooling_command_does_not_prove_effect_during_cooling_loss(self):
        baseline, failed = plant(), plant()
        failed.cmd_cooler = True
        failed.inject("cooling_loss", 300)
        for _ in range(120):
            baseline.step(1)
            failed.step(1)
        self.assertTrue(failed.cmd_cooler)
        self.assertEqual(failed.thermal["cooler_kw"], 0)
        self.assertAlmostEqual(failed.temp_c, baseline.temp_c)

    def test_stuck_heater_survives_stop_and_cooling_does_not_claim_repair(self):
        heating, mitigated = plant(), plant()
        for model in (heating, mitigated):
            model.inject("heater_stuck", 1200)
        mitigated.cmd_cooler = True
        for _ in range(120):
            heating.step(1)
            mitigated.step(1)
        self.assertGreater(heating.temp_c, 100)
        self.assertLess(mitigated.temp_c, 100)
        self.assertIn("heater_stuck", mitigated.faults)
        self.assertFalse(mitigated.cmd_heater)
        self.assertEqual(mitigated.thermal["heater_kw"], CONFIG["physics"]["heater"]["max_power_kw"])

    def test_no_cooling_below_target_or_below_ambient(self):
        model = plant()
        model.cmd_cooler = True
        model.temp_c = 60
        model.step(1)
        self.assertEqual(model.thermal["cooler_kw"], 0)
        model.temp_c = model.p_rx["ambient_c"] + .001
        model.sp_temp_c = 0
        model.step(60)
        self.assertGreaterEqual(model.temp_c, model.p_rx["ambient_c"])

    def test_older_configuration_without_cooler_keeps_zero_cooling(self):
        cfg = copy.deepcopy(CONFIG)
        del cfg["physics"]["cooler"]
        model = ReactorPlant(cfg)
        model.cmd_cooler = True
        model.step(1)
        self.assertEqual(model.thermal["cooler_kw"], 0)


if __name__ == "__main__":
    unittest.main()
