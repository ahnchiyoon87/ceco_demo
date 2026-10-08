"""In-memory Modbus datastore contract. Does not connect to the running plant."""
import copy
from pathlib import Path
import unittest
import yaml

from sim import Simulator, FC_COIL


class CoolingRegisterTest(unittest.TestCase):
    def model(self):
        cfg = yaml.safe_load(Path(__file__).with_name("plant.yaml").read_text(encoding="utf-8"))
        cfg["autopilot"]["enabled"] = False
        cfg["physics_time_scale"] = 1   # 레지스터·열량 계약은 설비 시간 1초 스캔으로 본다(배속 시험은 test_time_scale.py)
        sim = Simulator(copy.deepcopy(cfg))
        sim.plant.temp_c = 100
        return sim

    def test_coil_three_controls_cooling_and_snapshot_reports_actual_heat_removed(self):
        sim = self.model()
        self.assertTrue(sim.snapshot()["commands"]["cooler_enable"])   # 발열 반응: 기본은 냉각 켜짐
        sim.store.setValues(FC_COIL, 3, [0])
        sim.scan()
        self.assertFalse(sim.snapshot()["commands"]["cooler_enable"])
        sim.store.setValues(FC_COIL, 3, [1])
        sim.scan()
        snapshot = sim.snapshot()
        self.assertTrue(snapshot["commands"]["cooler_enable"])
        self.assertGreater(snapshot["thermal_model"]["cooler_kw"], 0)
        sim.store.setValues(FC_COIL, 3, [0])
        sim.scan()
        self.assertFalse(sim.snapshot()["commands"]["cooler_enable"])
        self.assertEqual(sim.snapshot()["thermal_model"]["cooler_kw"], 0)

    def test_failed_cooling_keeps_command_true_but_effect_zero(self):
        sim = self.model()
        sim.plant.inject("cooling_loss", 300)
        sim.store.setValues(FC_COIL, 3, [1])
        sim.scan()
        snapshot = sim.snapshot()
        self.assertTrue(snapshot["commands"]["cooler_enable"])
        self.assertEqual(snapshot["thermal_model"]["cooler_kw"], 0)
        self.assertIn("cooling_loss", snapshot["active_faults"])


if __name__ == "__main__":
    unittest.main()
