"""가상 정비팀 접점 계약: 현장 안전 확인 · 격리 중 기동 불가 · 같은 작업 지시 한 번만 · 정비 해제 키. 설비에 붙지 않는다."""
import asyncio
import copy
from pathlib import Path
import unittest

import yaml

from sim import Simulator

CFG = yaml.safe_load(Path(__file__).with_name("plant.yaml").read_text(encoding="utf-8"))


def simulator():
    cfg = copy.deepcopy(CFG)
    cfg["noise"] = {tag: 0 for tag in cfg["noise"]}
    sim = Simulator(cfg)
    sim.plant.time_scale = 36000.0   # 정비 시간(설비 초)을 시험에서 짧게
    for _ in range(5):
        sim.scan()
    return sim


class FieldCrew(unittest.TestCase):
    def run_task(self, sim, task, job, release=False):
        return asyncio.run(sim.field_task(task, job, release))

    def test_rotating_equipment_is_refused(self):
        sim = simulator()
        sim.plant.inject("bearing_wear")
        result = self.run_task(sim, "bearing_replace", "job-0000001")
        self.assertEqual(result["status"], "REJECTED")
        self.assertEqual(result["reason"], "FIELD_SAFETY")
        self.assertIn("bearing_wear", sim.plant.faults)          # 아무것도 바뀌지 않았다

    def test_repair_effect_and_same_job_once(self):
        sim = simulator()
        sim.plant.inject("bearing_wear")
        sim.plant.cmd_agitator = False
        first = self.run_task(sim, "bearing_replace", "job-0000002")
        self.assertEqual(first["status"], "DONE")
        self.assertTrue(first["effective"])
        self.assertNotIn("bearing_wear", sim.plant.faults)
        sim.plant.inject("bearing_wear")                          # 다시 고장 나도
        again = self.run_task(sim, "bearing_replace", "job-0000002")   # 같은 작업 지시는 다시 수행하지 않는다
        self.assertEqual(again, first)
        self.assertIn("bearing_wear", sim.plant.faults)

    def test_wrong_part_reports_no_fault(self):
        sim = simulator()
        sim.plant.inject("shaft_misalignment")
        sim.plant.cmd_agitator = False
        result = self.run_task(sim, "bearing_replace", "job-0000003")
        self.assertEqual(result["status"], "DONE_NO_FAULT")
        self.assertFalse(result["effective"])
        self.assertIn("shaft_misalignment", sim.plant.faults)

    def test_isolation_is_lifted_and_release_key_turned(self):
        sim = simulator()
        before = sim.store.getValues(3, sim.panel["maint_release_seq"], 1)[0]
        result = self.run_task(sim, "release_lockout", "job-0000004", release=True)
        self.assertTrue(result["maintenance_released"])
        self.assertEqual(sim.store.getValues(3, sim.panel["maint_release_seq"], 1)[0], before + 1)
        self.assertEqual(sim.plant.isolated, set())

    def test_unknown_task(self):
        self.assertEqual(self.run_task(simulator(), "replace_everything", "job-0000005")["reason"], "UNKNOWN_TASK")


if __name__ == "__main__":
    unittest.main()
