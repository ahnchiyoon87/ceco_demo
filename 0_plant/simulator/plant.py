"""AR-100 반응기 라인 물리 모델.

질량수지 · 에너지수지 · 헤드스페이스 압력 모델을 1차 오일러 적분으로 푼다.
모든 파라미터는 plant.yaml 에서 주입되며 이 파일에 하드코딩된 상수는 없다.
"""
from __future__ import annotations

import math
import random
import time
from dataclasses import dataclass, field

# 센서 통신 불량을 나타내는 센티널. Telegraf 브리지가 이 값을 걸러내어
# Kafka 상에 '실제 결측 구간'을 만들고, Flink 가 이를 보간한다.
BAD_QUALITY = -999999.0

ABS_ZERO_C = 273.15
ATM_BAR = 1.013


@dataclass
class Fault:
    """고장 주입 상태.

    시계는 고장의 성질로 정한다(plant.yaml kind):
      process — 서서히 진행하는 물리 과정(가열·냉각 상실·마모·드리프트). **설비 시계**를 따르므로
                배속을 올리면 현실의 시간 흐름 그대로 자연스럽게 빨라진다.
      event   — 순간 사건(계기 튐·결측·잡음). 관측 시계(실제 초)로 지속한다.
    """

    scenario: str
    started_at: float
    expires_at: float
    magnitude: float = 0.0
    lag_s: float = 0.0
    targets: tuple[str, ...] = ()
    elapsed: float = 0.0
    ramp_s: float = 45.0
    clock: str = "plant"
    spec: dict = field(default_factory=dict)


class ReactorPlant:
    def __init__(self, cfg: dict):
        self.cfg = cfg
        ph = cfg["physics"]
        self.p_feed = ph["feed_tank"]
        self.p_rx = ph["reactor"]
        self.p_pump = ph["pump"]
        self.p_valve = ph["valve"]
        self.p_heater = ph["heater"]
        self.p_cooler = ph.get("cooler", {"max_power_kw": 0.0, "kp": 0.0})
        self.p_agit = ph["agitator"]
        # 릴리프 밸브식 압력 상한(제어와 독립인 마지막 보호). 설정이 없으면 상한 없음.
        self.relief_barg = float(ph.get("relief", {}).get("set_barg", float("inf")))
        self.p_rxn = ph["reaction"]
        self.noise = cfg["noise"]
        # 트랜스미터 하한(LRV): 물리적으로 음수가 불가능한 계측점은 0 에서 클램프
        self.clamp_lo = {
            t["name"]: t["clamp_lo"] for t in cfg["tags"] if t.get("clamp_lo") is not None
        }

        # ── 상태 변수 ──
        self.feed_vol = self.p_feed["area_m2"] * self.p_feed["height_m"] * 0.70
        self.rx_vol = self.p_rx["area_m2"] * self.p_rx["height_m"] * 0.55
        self.temp_c = self.p_rx["ambient_c"] + 30.0
        self.jacket_c = self.temp_c
        self.bearing_wear = 0.0
        # 진동은 전류보다 늦게 반응한다. 전류 상승이 선행하고 진동이 뒤따라야
        # CEP 의 시간 선후 패턴이 의미를 갖는다 (단순 AND 와 구별됨).
        self.vib_wear = 0.0
        # 비상정지: 가상설비 안의 래치. 켜져 있으면 제어 명령과 무관하게 모든 구동기를 끈다.
        self.estop = False
        self.seq = 0
        self.sim_time = 0.0          # 적분된 물리 시각 [s] (= 실제 시간 × 배속)
        self.wall_time = 0.0         # 스캔 시계 [s]: 고장·autopilot·수동 유지는 이 시계로 센다
        # 물리 배속: 온도·액위·마모 같은 공정 변화만 빨라진다(실습에서 결과가 수 초 안에 보이도록).
        # 큰 배속에서도 적분이 안정하도록 스캔 한 번을 max_substep 이하 소구간으로 나눠 푼다.
        self.time_scale = float(cfg.get("physics_time_scale", 1.0))
        self.max_substep = float(cfg.get("physics_max_substep_s", 5.0))

        # ── 명령 (Modbus 로부터 매 스캔 갱신) ──
        self.cmd_pump = True
        self.cmd_agitator = True
        self.cmd_heater = True
        self.cmd_cooler = True       # 발열 반응: 정상 운전에서 냉각이 상시 켜져 있다
        self.thermal = {"heater_kw": 0.0, "cooler_kw": 0.0}
        self.sp_pump_speed = 60.0
        self.sp_valve_open = 45.0
        self.sp_temp_c = 72.0

        self.faults: dict[str, Fault] = {}
        self.readings: dict[str, float] = {}

        # ── 열화 상태(고장이 진행시키고 현장 정비만 되돌린다. 저절로 낫지 않는다) ──
        self.p_cw = ph.get("cooling_water", {})
        self.cw_basket = "A"                     # 이중 스트레이너의 사용 중 바스켓
        self.basket_foul = {"A": 0.0, "B": 0.0}  # 바스켓 막힘 정도 0..1
        self.jacket_clean = 1.0                  # 재킷 전열면 청결도(스케일이 끼면 낮아짐)
        self.misalign = 0.0                      # 교반기 축 정렬 불량 0..1
        self.pt101_drift = 0.0                   # PT-101 지시 편차 [bar]
        self.cv_stick = 0.0                      # 배출 밸브 스템 고착 0..1
        # 정비 격리(LOTO): 정비 중인 설비는 명령과 무관하게 멈춰 있다. 계기 격리는 지시값이 BAD.
        self.isolated: set[str] = set()
        self.cw = {"flow": 0.0, "supply": 0.0, "return": 0.0, "dp": 0.0}

        # ── autopilot 상태 ──
        self.ap = cfg.get("autopilot", {"enabled": False})
        self._ap_next = 0.0
        self._ap_target = {
            "pump_speed_sp": self.sp_pump_speed,
            "valve_open_sp": self.sp_valve_open,
            "temp_sp_c": self.sp_temp_c,
        }
        self._manual_until: dict[str, float] = {}

    # ── 운전원 수동 조작 등록 (해당 설정치를 일시적으로 autopilot 에서 제외) ──
    def note_manual(self, key: str) -> None:
        hold = float(self.ap.get("hold_after_manual_s", 300))
        self._manual_until[key] = self.wall_time + hold

    def _autopilot(self, dt_s: float) -> None:
        """생산 스케줄은 설비 시계(dt_s = 설비 시간). 운전원 수동 유지는 사람 행동이라 실제 초."""
        if not self.ap.get("enabled"):
            return
        if self.sim_time >= self._ap_next:
            self._ap_next = self.sim_time + float(self.ap["period_s"])
            for key, (lo, hi) in self.ap["ranges"].items():
                self._ap_target[key] = random.uniform(lo, hi)
        step = dt_s / max(float(self.ap["ramp_s"]), 1.0)
        for key, attr in (
            ("pump_speed_sp", "sp_pump_speed"),
            ("valve_open_sp", "sp_valve_open"),
            ("temp_sp_c", "sp_temp_c"),
        ):
            if self.wall_time < self._manual_until.get(key, 0.0):
                continue
            cur = getattr(self, attr)
            tgt = self._ap_target[key]
            setattr(self, attr, cur + (tgt - cur) * min(step, 1.0))

    # ── 고장 주입 ────────────────────────────────────────────────
    def _clock(self, kind: str) -> float:
        return self.sim_time if kind == "plant" else self.wall_time

    def inject(self, scenario: str, duration_s: float | None = None) -> Fault:
        """duration_s 는 그 고장의 시계 단위(process = 설비 초, event = 실제 초)."""
        spec = self.cfg["faults"][scenario]
        dur = duration_s if duration_s is not None else spec["default_duration_s"]
        clock = "plant" if spec.get("kind", "process") == "process" else "wall"
        f = Fault(
            scenario=scenario,
            started_at=self._clock(clock),
            expires_at=self._clock(clock) + dur,
            clock=clock, spec=spec,
            magnitude=float(spec.get("magnitude", 0.0)),
            lag_s=float(spec.get("lag_s", 0.0)),
            targets=tuple(spec.get("target", [])),
            ramp_s=float(spec.get("ramp_s", 45.0)),
        )
        self.faults[scenario] = f
        return f

    def clear_faults(self) -> None:
        """강사 초기화: 고장과 모든 열화 상태를 새 설비 상태로 되돌린다(정비가 아니다)."""
        self.faults.clear()
        self.bearing_wear = 0.0
        self.vib_wear = 0.0
        self.basket_foul = {"A": 0.0, "B": 0.0}
        self.cw_basket = "A"
        self.jacket_clean = 1.0
        self.misalign = 0.0
        self.pt101_drift = 0.0
        self.cv_stick = 0.0
        self.isolated.clear()

    def _degrade(self, dt_s: float) -> None:
        """열화 고장의 진행. 진행이 끝나도 상태는 남는다(수리 전까지)."""
        for name, f in list(self.faults.items()):
            rate = dt_s / max(f.ramp_s, 1e-9)
            if name == "strainer_fouling":
                # 냉각수 속 이물 덩어리: 총량 1.0 이 그때 사용 중인 바스켓에 쌓인다(도중 전환하면 나머지는 B 로).
                left = max(0.0, 1.0 - f.spec.setdefault("_deposited", 0.0))
                add = min(rate, left)
                self.basket_foul[self.cw_basket] = min(1.0, self.basket_foul[self.cw_basket] + add)
                f.spec["_deposited"] += add
            elif name == "jacket_fouling":
                self.jacket_clean = max(float(f.spec.get("floor", 0.12)), self.jacket_clean - rate)
            elif name == "shaft_misalignment":
                self.misalign = min(1.0, self.misalign + rate)
            elif name == "pt_drift":
                self.pt101_drift = min(float(f.magnitude), self.pt101_drift + rate * float(f.magnitude))
            elif name == "outlet_valve_stick":
                self.cv_stick = min(float(f.spec.get("max", 0.85)), self.cv_stick + rate)

    def _expire_faults(self) -> None:
        for f in self.faults.values():
            f.elapsed = self._clock(f.clock) - f.started_at
        for k in [k for k, f in self.faults.items() if f.expires_at <= self._clock(f.clock)]:
            del self.faults[k]
            if k == "bearing_wear":
                self.bearing_wear = 0.0
                self.vib_wear = 0.0

    # ── 1 스캔 적분 ──────────────────────────────────────────────
    def _integrate(self, dt_s: float):
        """물리 소구간 적분(질량·에너지 수지, 인터록, 마모). dt_s 는 물리 시간."""
        rx_area = self.p_rx["area_m2"]
        rx_h = self.p_rx["height_m"]
        fd_area = self.p_feed["area_m2"]
        fd_h = self.p_feed["height_m"]

        feed_level_frac = self.feed_vol / (fd_area * fd_h)
        rx_level_frac = self.rx_vol / (rx_area * rx_h)
        rx_level_m = rx_level_frac * rx_h

        # 고압 인터록은 soft-PLC 가 한다(PT-101 지시값으로 펌프 명령을 끈다). 여기서는 명령을 그대로 따른다.
        # 비상정지는 제어와 독립으로 모든 구동기를 끈다.
        press_now = self._pressure(rx_level_frac, self.temp_c)
        pump_active = self.cmd_pump and not self.estop and "P-101" not in self.isolated
        self._degrade(dt_s)

        # ── 공급 유량 (펌프 특성 × 흡입측 레벨) ──
        if pump_active and feed_level_frac > 0.02:
            suction = min(1.0, feed_level_frac / 0.25)
            q_in = self.p_pump["max_flow_m3h"] * (self.sp_pump_speed / 100.0) * suction
            q_in *= max(0.35, 1.0 - press_now / 12.0)   # 토출 배압에 의한 유량 저하
        else:
            q_in = 0.0

        # ── 배출 유량 (밸브 Cv × 정수두) ──
        # 스템이 고착되면 실제 개도가 설정값보다 작다(설정값·명령은 정상으로 보인다). 정비 격리 중엔 닫힘.
        actual_open = 0.0 if "CV-101" in self.isolated else (self.sp_valve_open / 100.0) * (1.0 - self.cv_stick)
        q_out = self.p_valve["cv"] * actual_open * math.sqrt(max(rx_level_m, 0.0))

        # ── 질량수지 ──
        # 원료 보충: level_sp_pct 가 있으면 실제 설비처럼 액위 제어(보충량 = 소비량 + P 보정, 0~refill_m3h),
        # 설정이 없으면 고정 보충(소비보다 많아 설비 시간 몇 시간 뒤 탱크가 넘친다).
        if "level_sp_pct" in self.p_feed:
            err = self.p_feed["level_sp_pct"] - feed_level_frac * 100.0
            refill = min(max(q_in + self.p_feed.get("level_kp", 0.5) * err, 0.0), self.p_feed["refill_m3h"])
        else:
            refill = self.p_feed["refill_m3h"]
        self.feed_vol += (refill - q_in) * dt_s / 3600.0
        self.feed_vol = min(max(self.feed_vol, 0.0), fd_area * fd_h)

        self.rx_vol += (q_in - q_out) * dt_s / 3600.0
        self.rx_vol = min(max(self.rx_vol, 0.02 * rx_area * rx_h), rx_area * rx_h)

        rx_level_frac = self.rx_vol / (rx_area * rx_h)

        # ── 에너지수지 ──
        rho = self.p_rx["rho_kg_m3"]
        cp = self.p_rx["cp_kj_kgk"]
        mass = max(self.rx_vol * rho, 1.0)
        ambient = self.p_rx["ambient_c"]

        if self.cmd_heater and not self.estop:
            err = self.sp_temp_c - self.temp_c
            duty = min(max(self.p_heater["kp"] * err / 100.0, 0.0), 1.0)
        else:
            duty = 0.0
        # A stuck heater is a physical fault: turning its command off does not
        # remove the heat. Clearing the fault represents a separate repair.
        if "heater_stuck" in self.faults:
            duty = 1.0
        q_heat = self.p_heater["max_power_kw"] * duty
        # ── 냉각수 계통(공용 유틸리티 → 이중 스트레이너 → 재킷 냉각 코일) ──
        cw = self.p_cw
        supply = float(cw.get("supply_c", ambient))
        foul = self.basket_foul[self.cw_basket]
        flow_frac = max(1.0 - float(cw.get("clog_flow_drop", 0.0)) * foul, 0.01)
        cw_flow = float(cw.get("nominal_flow_m3h", 0.0)) * flow_frac
        # 열 제거 능력 = 전열 계수(유량^0.8 · 전열면 청결도) × (반응물 − 냉각수 공급) 온도차
        ua = float(cw.get("ua_kw_per_k", float("inf"))) * flow_frac ** 0.8 * self.jacket_clean
        capacity = max(0.0, ua * (self.temp_c - supply)) if cw else float("inf")
        cooling_duty = 0.0
        if self.cmd_cooler and not self.estop and "cooling_loss" not in self.faults:
            cooling_duty = min(max(self.p_cooler["kp"] * (self.temp_c - self.sp_temp_c) / 100.0, 0.0), 1.0)
        q_cool = min(self.p_cooler["max_power_kw"] * cooling_duty, capacity)
        # Do not remove more energy than the contents hold above ambient in a
        # scan. This is an educational heat-exchanger model, not a real plant rating.
        q_cool = min(q_cool, max(0.0, (self.temp_c - ambient) * mass * cp / max(dt_s, 1e-9)))
        self.thermal = {"heater_kw": q_heat, "cooler_kw": q_cool, "cooling_capacity_kw": min(capacity, 1e6)}
        cw_kw_per_k = cw_flow / 3600.0 * 1000.0 * 4.18
        self.cw = {"flow": cw_flow, "supply": supply,
                   "return": supply + (q_cool / cw_kw_per_k if cw_kw_per_k > 0 else 0.0),
                   "dp": float(cw.get("clean_dp_bar", 0.0)) + float(cw.get("clog_dp_bar", 0.0)) * foul ** 1.5}
        cool_drop = q_cool / max(float(cw.get("jacket_ua_kw_per_k", 20.0)), 1e-9)
        self.jacket_c += ((self.temp_c + duty * 38.0 - cool_drop + 2.0) - self.jacket_c) * min(1.0, dt_s / 8.0)

        q_loss = self.p_rx["heat_loss_kw_per_k"] * (self.temp_c - ambient)
        q_feed = (q_in / 3600.0) * rho * cp * (ambient - self.temp_c)
        # 반응열(발열 반응): 공급되는 원료만큼 열이 난다. 정상 운전에서 냉각이 상시 필요한 이유.
        q_rxn = float(self.p_rxn.get("heat_kw_per_m3h", 0.0)) * q_in
        self.thermal["reaction_kw"] = q_rxn
        self.temp_c += (q_heat + q_rxn - q_cool - q_loss + q_feed) / (mass * cp) * dt_s
        self.temp_c = min(max(self.temp_c, ambient), 140.0)

        # ── 베어링 열화 (bearing_wear 고장 주입 시 누적) ──
        # 전류는 즉시, 진동은 lag_s 경과 후부터 그리고 더 느리게 누적된다.
        if "bearing_wear" in self.faults:
            f = self.faults["bearing_wear"]
            self.bearing_wear = min(1.0, self.bearing_wear + dt_s / float(f.spec.get("wear_ramp_s", 25.0)))
            if f.elapsed >= f.lag_s:
                self.vib_wear = min(1.0, self.vib_wear + dt_s / float(f.spec.get("vib_ramp_s", 23.0)))

        return q_in, q_out, pump_active, rx_level_frac

    def step(self, dt_s: float) -> dict[str, float]:
        """스캔 1회: 실제 dt_s 초. 물리는 dt_s × 배속만큼 소구간으로 적분한다."""
        self.wall_time += dt_s
        self.seq = (self.seq + 1) & 0xFFFFFFFF
        phys = dt_s * self.time_scale
        n = max(1, math.ceil(phys / self.max_substep))
        for _ in range(n):
            h = phys / n
            self.sim_time += h
            self._expire_faults()
            self._autopilot(h)
            q_in, q_out, pump_active, rx_level_frac = self._integrate(h)
        fd_area = self.p_feed["area_m2"]
        fd_h = self.p_feed["height_m"]

        pressure = self._pressure(rx_level_frac, self.temp_c)

        # ── 계측 원값 산출 ──
        raw = {
            "LT-101": self.feed_vol / (fd_area * fd_h) * 100.0,
            "LT-102": rx_level_frac * 100.0,
            "TT-101": self.temp_c,
            "TT-102": self.jacket_c,
            "PT-101": pressure,
            "FT-101": q_in,
            "FT-102": q_out,
            "IT-101": self._pump_current(pump_active, q_in, pressure),
            "IT-102": self._agitator_current(rx_level_frac),
            "VT-101": self._vibration(rx_level_frac),
            "pH-101": self._ph(),
            "CT-101": 0.0,   # pH 종속 → 아래에서 산출
        }
        raw["CT-101"] = (
            self.p_rxn["conductivity_base"]
            + self.p_rxn["conductivity_per_ph"] * (raw["pH-101"] - self.p_rxn["ph_setpoint"])
            + 0.05 * (self.temp_c - 72.0) / 10.0
        )
        # 압력계 드리프트는 PT-101 지시값만 바꾼다(물리 압력과 독립 압력계 PT-102 는 그대로).
        raw["PT-101"] = pressure + self.pt101_drift
        if self.p_cw:
            raw.update({"FT-103": self.cw["flow"], "TT-103": self.cw["supply"], "TT-104": self.cw["return"],
                        "PDT-103": self.cw["dp"], "PT-102": pressure})
        known = {t["name"] for t in self.cfg["tags"]}
        raw = {k: v for k, v in raw.items() if k in known}

        self.readings = {t: self._measure(t, v) for t, v in raw.items()}
        if "PT-101" in self.isolated and "PT-101" in self.readings:
            self.readings["PT-101"] = BAD_QUALITY   # 교정 중: 계기 차단 밸브로 격리되어 지시값 없음
        return self.readings

    # ── 헤드스페이스 압력: 레벨·온도와 물리적으로 결합 ──
    def _pressure(self, level_frac: float, temp_c: float) -> float:
        head_frac = max(1.0 - level_frac, 0.05)
        ref_head = self.p_rx["headspace_ref_frac"]
        charge = self.p_rx["charge_pressure_bara"]
        p_abs = charge * (temp_c + ABS_ZERO_C) / (self.p_rx["ambient_c"] + ABS_ZERO_C) * (ref_head / head_frac)
        p_vap = 0.0061094 * math.exp(17.625 * temp_c / (temp_c + 243.04))
        # 릴리프 밸브가 설정 압력에서 열려 그 이상 오르지 않는다(계기 튐 spike 는 지시값만이라 무관).
        return min(max(p_abs + p_vap - ATM_BAR, 0.0), self.relief_barg)

    def _pump_current(self, active: bool, q_in: float, pressure: float) -> float:
        if not active:
            return 0.02
        nl = self.p_pump["no_load_current_a"]
        rated = self.p_pump["rated_current_a"]
        load = q_in / self.p_pump["max_flow_m3h"]
        return nl + (rated - nl) * load * (0.62 + 0.38 * min(pressure / 3.0, 1.6))

    def agitator_running(self) -> bool:
        return self.cmd_agitator and not self.estop and "M-101" not in self.isolated

    def _agitator_current(self, level_frac: float) -> float:
        if not self.agitator_running():
            return 0.02
        rated = self.p_agit["rated_current_a"]
        visc = 1.0 + 0.0045 * (72.0 - self.temp_c)      # 저온일수록 점도 ↑ → 부하 ↑
        # 베어링 마모는 마찰 부하로 전류를 먼저 크게 올린다(액위 30~90 % 어디서든 상한 초과). 축 정렬 불량은 전류를 조금만 올린다(상한 미만).
        return rated * (0.55 + 0.45 * level_frac) * visc * (1.0 + 0.95 * self.bearing_wear) * (1.0 + 0.18 * self.misalign)

    def _vibration(self, level_frac: float) -> float:
        if not self.agitator_running():
            return 0.03
        base = self.p_agit["base_vibration_mms"]
        v = base * (0.82 + 0.30 * level_frac)
        # 전류 상승이 선행하고 진동은 lag_s 이후 더 느리게 상승
        # → CEP 의 "A 후 10초 이내 B" 패턴이 실제로 성립한다
        if self.vib_wear > 0.0:
            v *= 1.0 + 3.0 * self.vib_wear
        # 축 정렬 불량은 진동을 곧바로 크게 올린다(전류 선행 없음)
        return v * (1.0 + 3.0 * self.misalign)

    # ── 현장 정비 작업(가상 정비팀이 현장에서 하는 일) ───────────────────
    def field_check(self, task: str, spec: dict) -> str | None:
        """작업 전 현장 안전 확인. 문제가 있으면 이유를 돌려준다."""
        need = spec.get("requires_stopped")
        if need == "M-101" and self.agitator_running():
            return "교반기가 회전 중이라 작업할 수 없습니다(정지·격리 필요)."
        if need == "P-101" and self.cmd_pump and not self.estop:
            return "공급 펌프가 운전 중이라 작업할 수 없습니다(정지·격리 필요)."
        if task == "strainer_switch" and self.basket_foul["B" if self.cw_basket == "A" else "A"] > 0.5:
            return "예비 바스켓도 막혀 있어 전환할 수 없습니다(먼저 세척 필요)."
        return None

    def field_apply(self, task: str) -> dict:
        """작업 완료 시점의 실제 효과와 현장 소견. 원인과 맞지 않는 작업은 설비를 바꾸지 않는다."""
        def drop(*names):
            for n in names:
                self.faults.pop(n, None)
        if task == "strainer_switch":
            old, new = self.cw_basket, "B" if self.cw_basket == "A" else "A"
            before = self.cw["dp"]
            self.cw_basket = new
            return {"effective": self.basket_foul[old] > 0.3,
                    "finding": f"사용 바스켓 {old}→{new} 전환. 전환 전 {old} 막힘 추정 {self.basket_foul[old]:.0%}, 전환 전 차압 {before:.2f} bar."}
        if task == "strainer_clean":
            basket = "B" if self.cw_basket == "A" else "A"
            foul = self.basket_foul[basket]
            self.basket_foul[basket] = 0.0
            return {"effective": foul > 0.3,
                    "finding": f"대기 바스켓 {basket} 분해 세척. " + ("이물(스케일 조각·섬유) 다량 제거." if foul > 0.3 else "이물 거의 없음.")}
        if task == "jacket_descale":
            was = self.jacket_clean
            self.jacket_clean = 1.0
            drop("jacket_fouling")
            return {"effective": was < 0.8,
                    "finding": f"재킷 냉각 코일 화학 세정. " + ("스케일층 다량 제거, 전열 회복." if was < 0.8 else "스케일 거의 없음.")}
        if task == "bearing_replace":
            if self.bearing_wear > 0.2 or "bearing_wear" in self.faults:
                drop("bearing_wear")
                self.bearing_wear = self.vib_wear = 0.0
                return {"effective": True, "finding": "구동측 베어링 외륜 박리·윤활 탄화 확인. 신품 교체, 유격 정상."}
            return {"effective": False, "mismatch": True,
                    "finding": "베어링 분해 점검: 유격·소음·윤활 정상. 교체하지 않음(예비품 미사용). 축 정렬 점검 권고."}
        if task == "shaft_align":
            if self.misalign > 0.2 or "shaft_misalignment" in self.faults:
                was = self.misalign
                drop("shaft_misalignment")
                self.misalign = 0.0
                return {"effective": True, "finding": f"커플링 각 편차 {0.05 + 0.4 * was:.2f} mm 확인, 레이저 정렬로 0.02 mm 이내 조정."}
            return {"effective": False, "mismatch": True, "finding": "축 정렬 편차 0.02 mm, 허용 범위. 조정하지 않음."}
        if task == "pt_calibrate":
            drift = self.pt101_drift
            if abs(drift) > 0.3 or "pt_drift" in self.faults:
                drop("pt_drift")
                self.pt101_drift = 0.0
                return {"effective": True, "finding": f"기준 압력계 비교: PT-101 지시 {drift:+.2f} bar 편차. 영점·스팬 교정 후 편차 ±0.02 bar."}
            return {"effective": False, "mismatch": True, "finding": f"기준 압력계 비교: 편차 {drift:+.2f} bar, 허용 범위. 교정하지 않음."}
        if task == "cv_repair":
            was = self.cv_stick
            if was > 0.2 or "outlet_valve_stick" in self.faults:
                drop("outlet_valve_stick")
                self.cv_stick = 0.0
                return {"effective": True, "finding": f"배출 밸브 스템에 결정성 이물 고착(실제 개도 약 {1 - was:.0%}). 분해 청소·패킹 교체, 스트로크 정상."}
            return {"effective": False, "mismatch": True, "finding": "배출 밸브 스트로크 시험 정상. 분해하지 않음."}
        if task == "release_lockout":
            return {"effective": True, "finding": "작업 구역·공구 회수 확인, 격리(LOTO) 해제, 정비 해제 키 조작."}
        raise KeyError(task)

    def _ph(self) -> float:
        sp = self.p_rxn["ph_setpoint"]
        return sp + self.p_rxn["ph_drift_per_degc"] * (self.temp_c - 72.0)

    # ── 계측 단계: 노이즈 + 고장 효과 부착 ──
    def _measure(self, tag: str, value: float) -> float:
        for f in self.faults.values():
            if tag not in f.targets:
                continue
            if f.scenario == "dropout":
                return BAD_QUALITY
            if f.scenario == "spike":
                value += f.magnitude
            elif f.scenario == "noise":
                value += random.gauss(0.0, self.noise.get(tag, 0.05) * f.magnitude)
            elif f.scenario == "drift":
                ramp = min(1.0, f.elapsed / max(f.ramp_s, 1e-9))
                # 정상 상태에서 pH↑ ⇒ CT↓ 이지만, 이 고장은 둘을 동시에 상승시켜
                # 센서 간 상관 구조를 붕괴시킨다. 각 태그는 규격 내에 머무른다.
                scale = 1.0 if tag == "pH-101" else 1.6
                value += f.magnitude * ramp * scale
        value += random.gauss(0.0, self.noise.get(tag, 0.05))
        lo = self.clamp_lo.get(tag)
        return value if lo is None else max(value, lo)
