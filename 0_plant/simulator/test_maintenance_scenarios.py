"""정비 시나리오 물리: 열화는 저절로 낫지 않고, 원인에 맞는 현장 정비만 회복시킨다(설비 없이 결정론으로 확인)."""
import copy
from pathlib import Path
import unittest

import yaml
from plant import ReactorPlant

CONFIG = yaml.safe_load(Path(__file__).with_name("plant.yaml").read_text(encoding="utf-8"))
TASKS = CONFIG["field_tasks"]


def plant():
    cfg = copy.deepcopy(CONFIG)
    cfg["noise"] = {tag: 0 for tag in cfg["noise"]}
    model = ReactorPlant(cfg)
    run(model, 20)
    return model


def run(model, seconds):
    for _ in range(seconds):
        model.step(1)
    return model.readings


class CoolingWater(unittest.TestCase):
    def test_normal_operation_needs_cooling(self):
        r = run(plant(), 30)
        self.assertLess(abs(r["TT-101"] - 72.0), 1.5)
        self.assertGreater(r["TT-104"] - r["TT-103"], 5)        # 냉각수가 반응열을 가져간다

    def test_strainer_clog_signature_and_switch_restores(self):
        p = plant()
        p.inject("strainer_fouling")
        r = run(p, 10)
        self.assertGreater(r["TT-101"], 95)                      # 반응기 온도 상한 초과
        self.assertLess(r["FT-103"], 10)
        self.assertGreater(r["PDT-103"], 1.0)
        self.assertGreater(r["TT-104"] - r["TT-103"], 25)        # 적은 유량이 열을 받아 크게 데워진다
        result = p.field_apply("strainer_switch")
        self.assertTrue(result["effective"])
        r = run(p, 10)
        self.assertLess(r["TT-101"], 74)
        self.assertLess(r["PDT-103"], 0.3)

    def test_jacket_scale_signature_and_switch_does_not_help(self):
        p = plant()
        p.inject("jacket_fouling")
        r = run(p, 10)
        self.assertGreater(r["TT-101"], 95)
        self.assertGreater(r["FT-103"], 28)                      # 유량·차압 정상
        self.assertLess(r["PDT-103"], 0.3)
        self.assertLess(r["TT-104"] - r["TT-103"], 5)            # 열이 안 넘어간다
        self.assertFalse(p.field_apply("strainer_switch")["effective"])
        self.assertGreater(run(p, 10)["TT-101"], 95)             # 잘못된 정비는 회복시키지 않는다
        self.assertIsNotNone(p.field_check("jacket_descale", TASKS["jacket_descale"]))   # 펌프 운전 중 금지
        p.cmd_pump = False
        run(p, 5)
        self.assertIsNone(p.field_check("jacket_descale", TASKS["jacket_descale"]))
        self.assertTrue(p.field_apply("jacket_descale")["effective"])
        p.cmd_pump = True
        self.assertLess(run(p, 15)["TT-101"], 74)

    def test_degradation_does_not_heal_by_itself(self):
        p = plant()
        p.inject("strainer_fouling")
        run(p, 300)                                              # 설비 시간 50시간
        self.assertGreater(p.readings["TT-101"], 95)


class Agitator(unittest.TestCase):
    def test_bearing_current_exceeds_limit_at_any_level_misalignment_never(self):
        for level in (0.30, 0.55, 0.90):
            bearing, shaft = plant(), plant()
            for p in (bearing, shaft):
                p.rx_vol = level * p.p_rx["area_m2"] * p.p_rx["height_m"]
                p.cmd_pump, p.sp_valve_open = False, 0          # 액위 고정
            bearing.inject("bearing_wear")
            shaft.inject("shaft_misalignment")
            self.assertGreater(run(bearing, 2)["IT-102"], 9.6, level)
            self.assertLess(run(shaft, 6)["IT-102"], 9.6, level)

    def test_bearing_current_rises_seconds_before_vibration(self):
        p = plant()
        p.inject("bearing_wear")
        r = run(p, 1)
        self.assertGreater(r["IT-102"], 9.6)
        self.assertLess(r["VT-101"], 7.1)                        # 전류가 먼저(진동은 약 3초 뒤)
        self.assertGreater(run(p, 5)["VT-101"], 7.1)

    def test_bearing_current_leads_misalignment_vibration_leads(self):
        bearing, shaft = plant(), plant()
        bearing.inject("bearing_wear")
        shaft.inject("shaft_misalignment")
        b, s = run(bearing, 5), run(shaft, 5)
        self.assertGreater(b["IT-102"], 9.6)
        self.assertGreater(s["VT-101"], 7.1)
        self.assertLess(s["IT-102"], 9.6)                        # 정렬 불량은 전류 상한을 넘지 않는다

    def test_wrong_part_replacement_leaves_vibration(self):
        p = plant()
        p.inject("shaft_misalignment")
        run(p, 5)
        self.assertIsNotNone(p.field_check("bearing_replace", TASKS["bearing_replace"]))   # 회전 중 금지
        p.cmd_agitator = False
        run(p, 2)
        result = p.field_apply("bearing_replace")
        self.assertTrue(result["mismatch"])
        p.cmd_agitator = True
        self.assertGreater(run(p, 5)["VT-101"], 7.1)
        p.cmd_agitator = False
        self.assertTrue(p.field_apply("shaft_align")["effective"])
        p.cmd_agitator = True
        self.assertLess(run(p, 5)["VT-101"], 3.0)

    def test_isolated_agitator_cannot_run(self):
        p = plant()
        p.isolated.add("M-101")
        self.assertLess(run(p, 2)["IT-102"], 0.5)


class Pressure(unittest.TestCase):
    def test_drift_is_indication_only(self):
        p = plant()
        p.inject("pt_drift")
        r = run(p, 5)
        self.assertGreater(r["PT-101"], 6.5)                     # 인터록 트립 수준
        self.assertLess(r["PT-102"], 4.0)                        # 독립 계기와 실제 압력은 정상
        p.isolated.add("PT-101")
        self.assertLess(run(p, 1)["PT-101"], -1000)              # 교정 중 지시 없음(BAD)
        p.isolated.discard("PT-101")
        self.assertTrue(p.field_apply("pt_calibrate")["effective"])
        self.assertLess(abs(run(p, 2)["PT-101"] - p.readings["PT-102"]), 0.05)

    def test_valve_stick_is_real_overpressure_and_calibration_finds_nothing(self):
        p = plant()
        p.inject("outlet_valve_stick")
        r = run(p, 6)
        self.assertGreater(r["PT-102"], 6.0)                     # 두 계기 모두 높다
        self.assertLess(abs(r["PT-101"] - r["PT-102"]), 0.1)
        self.assertGreater(r["LT-102"], 80)
        self.assertTrue(p.field_apply("pt_calibrate")["mismatch"])
        p.cmd_pump = False
        run(p, 2)
        self.assertTrue(p.field_apply("cv_repair")["effective"])
        p.cmd_pump = True
        r = run(p, 30)
        self.assertLess(r["PT-102"], 4.5)
        self.assertLess(r["LT-102"], 70)


if __name__ == "__main__":
    unittest.main()
