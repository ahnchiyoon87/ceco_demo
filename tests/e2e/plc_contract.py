"""[측정 도구] soft-PLC 계약 시험 — PLC 프로그램(1_control/plc-openplc/main.st.tmpl)이 약속한 동작을 실제 PLC·가상설비로 확인한다.

엣지 없이 PLC 의 Modbus 슬레이브에 직접 붙어 엣지가 할 일(시각 동기, 명령 채널 쓰기, 상태 읽기)을 흉내 낸다.
가상설비의 강사 API·현장 패널은 HTTP Basic 계정으로 쓴다(시험 도구 = 사람 자리).
    python tests/e2e/plc_contract.py --plc plc --sim plant-sim --phase 1 --out r1.json   # 정비 모드 켜기까지
    (PLC 컨테이너 재시작)
    python tests/e2e/plc_contract.py --plc plc --sim plant-sim --phase 2 --out r2.json   # RETAIN 확인부터 끝까지
판정: 항목마다 기대/실제/PASS·FAIL. 하나라도 FAIL 이면 종료 코드 1.
"""
from __future__ import annotations

import argparse
import base64
import json
import os
import struct
import sys
import threading
import time
import urllib.request

from pymodbus.client import ModbusTcpClient

ap = argparse.ArgumentParser()
ap.add_argument("--plc", default="plc")
ap.add_argument("--sim", default="plant-sim")
ap.add_argument("--out", required=True)
ap.add_argument("--phase", type=int, choices=[1, 2], required=True)
a = ap.parse_args()

MW = 1024  # %MW0 = 홀딩 레지스터 1024 (OpenPLC 슬레이브: %QW 1024개 다음)
ACK = {0: "ACCEPTED", 1: "LOCAL_MODE", 2: "MAINTENANCE", 3: "MODE", 4: "RANGE", 5: "INTERLOCK", 6: "EXPIRED",
       7: "DUPLICATE", 8: "UNKNOWN_COMMAND", 9: "ESTOP", 10: "NO_TIME_SYNC", 11: "PHYSICS"}
results: list[dict] = []
c = ModbusTcpClient(a.plc, port=502, timeout=3)
deadline = time.time() + 90          # 재시작 직후에는 런타임이 프로그램을 올린 뒤 Modbus 를 연다
while not c.connect():
    assert time.time() < deadline, "PLC 연결 실패(90 s)"
    time.sleep(1)
lock = threading.Lock()


def http(port: int, path: str, body: dict | None, user_env: str, pw_env: str) -> dict:
    auth = base64.b64encode(f'{os.environ[user_env]}:{os.environ[pw_env]}'.encode()).decode()
    req = urllib.request.Request(f"http://{a.sim}:{port}{path}", data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Authorization": f"Basic {auth}", "Content-Type": "application/json"},
                                 method="POST" if body is not None else "GET")
    with urllib.request.urlopen(req, timeout=5) as r:
        return json.load(r)


panel = lambda action, **kw: http(8081, "/panel", {"action": action, **kw}, "FIELD_PANEL_USER", "FIELD_PANEL_PASSWORD")
instr = lambda path, body=None: http(8080, path, body, "INSTRUCTOR_USER", "INSTRUCTOR_PASSWORD")


def hr(addr: int, n: int = 1) -> list[int]:
    with lock:
        r = c.read_holding_registers(addr, count=n, slave=1)
    assert not r.isError(), r
    return r.registers


def ir(addr: int, n: int = 1) -> list[int]:
    with lock:
        r = c.read_input_registers(addr, count=n, slave=1)
    assert not r.isError(), r
    return r.registers


def wr(addr: int, values: list[int]) -> None:
    with lock:
        r = c.write_registers(addr, [v & 0xFFFF for v in values], slave=1)
    assert not r.isError(), r


def status() -> dict:
    s = hr(103, 16)
    return {"mode": s[1], "maint": s[2], "maint_op": s[3], "interlock": s[4], "field_comm": s[5], "estop": s[6],
            "outputs": s[7], "op_ack_seq": s[8], "op_ack": s[9], "rq_ack_seq": s[10], "rq_ack": s[11],
            "rq_hash": (s[12] << 16) | s[13], "heartbeat": s[14], "fb_fault": s[15]}


def check(name: str, expected, actual, ok: bool | None = None) -> bool:
    ok = (expected == actual) if ok is None else ok
    results.append({"item": name, "expected": expected, "actual": actual, "verdict": "PASS" if ok else "FAIL"})
    print(f'{"PASS" if ok else "FAIL"} {name}: 기대 {expected} / 실제 {actual}', flush=True)
    return ok


# ── 시각 동기(엣지 역할): 1초마다 epoch 초를 %MW0..1 에 쓴다 ──
sync_on = threading.Event(); sync_on.set()
stop_all = threading.Event()


def time_sync():
    while not stop_all.is_set():
        if sync_on.is_set():
            t = int(time.time())
            wr(MW + 0, [t >> 16, t & 0xFFFF])
        time.sleep(1)


threading.Thread(target=time_sync, daemon=True).start()
op_seq = [hr(MW + 10)[0]]
rq_seq = [hr(MW + 20)[0]]


def op(code: int, value: int) -> str:
    op_seq[0] = (op_seq[0] + 1) & 0xFFFF
    wr(MW + 11, [code, value])
    wr(MW + 10, [op_seq[0]])
    return wait_ack("op_ack_seq", "op_ack", op_seq[0])


def rq(code: int, value: int, *, accepted: int = 0, exp: int | None = None, h: int = 0) -> str:
    rq_seq[0] = (rq_seq[0] + 1) & 0xFFFF
    exp = int(time.time()) + 30 if exp is None else exp
    wr(MW + 21, [code, value, exp >> 16, exp & 0xFFFF, accepted, h >> 16, h & 0xFFFF])
    wr(MW + 20, [rq_seq[0]])
    return wait_ack("rq_ack_seq", "rq_ack", rq_seq[0])


def wait_ack(seq_key: str, code_key: str, seq: int, timeout: float = 3.0) -> str:
    end = time.time() + timeout
    while time.time() < end:
        s = status()
        if s[seq_key] == seq:
            return ACK.get(s[code_key], str(s[code_key]))
        time.sleep(0.05)
    return "NO_ACK"


def wait_for(pred, timeout: float = 5.0) -> bool:
    end = time.time() + timeout
    while time.time() < end:
        if pred():
            return True
        time.sleep(0.1)
    return False


def f32(words: list[int]) -> float:
    return struct.unpack(">f", struct.pack(">HH", *words))[0]


try:
  if a.phase == 1:
    instr("/fault/clear", {})
    time.sleep(2)
    s0 = status()
    check("PLC 기동 시 모드 = REMOTE_MANUAL(1)", 1, s0["mode"])
    check("현장 통신 정상", 1, s0["field_comm"])
    hb = s0["heartbeat"]; time.sleep(1)
    check("하트비트 증가(PLC RUN)", True, status()["heartbeat"] != hb)
    # 계측값 통과: PLC 입력 레지스터 = 가상설비 값(같은 스캔 순번에서)
    matched = None
    for _ in range(20):
        st = instr("/state"); seq_a = ir(24, 2); regs = ir(0, 24); seq_b = ir(24, 2)
        if seq_a == seq_b and st["seq"] == ((seq_a[0] << 16) | seq_a[1]):
            matched = max(abs(f32(regs[i:i + 2]) - v) for i, v in zip(range(0, 24, 2), st["readings"].values()) if v is not None)
            break
        time.sleep(0.2)
    check("계측 12점 PLC 통과(같은 스캔 순번에서 가상설비 값과 차이 < 1e-3)", True, matched is not None and matched < 1e-3)
    w = ir(26, 2); pts1 = (w[0] << 16) | w[1]; time.sleep(2); w = ir(26, 2); pts2 = (w[0] << 16) | w[1]
    check("설비 시각 증가(배속 600: 2초에 약 1200초)", True, 900 <= pts2 - pts1 <= 1500)

    # 운전원 채널 — REMOTE_MANUAL
    check("운전원: 교반기 정지(REMOTE_MANUAL)", "ACCEPTED", op(2, 0))
    check("가상설비 교반기 코일 꺼짐", True, wait_for(lambda: instr("/state")["commands"]["agitator_run"] is False))
    check("운전원: 교반기 기동", "ACCEPTED", op(2, 1))
    check("범위 밖 설정값(펌프 150%) 거부", "RANGE", op(5, 150))
    check("없는 명령 코드 거부", "UNKNOWN_COMMAND", op(99, 1))
    # 외부 요청 — REMOTE_MANUAL 에서 운전원 수락 표시 없으면 거부, 있으면 수용
    check("외부 요청(REMOTE_MANUAL, 수락 표시 없음) 거부", "MODE", rq(4, 1, h=0x1001))
    check("외부 요청(REMOTE_MANUAL, 운전원 수락) 수용", "ACCEPTED", rq(4, 1, accepted=1, h=0x1002))
    check("같은 요청 해시 재수신 → 중복 거부", "DUPLICATE", rq(4, 1, accepted=1, h=0x1002))
    check("만료된 요청 거부", "EXPIRED", rq(4, 0, accepted=1, exp=int(time.time()) - 5, h=0x1003))  # PLC 시각은 1 s 마다 동기되므로 그보다 확실히 지난 만료
    check("냉각기 끔(운전원)", "ACCEPTED", op(4, 0))
    # REMOTE_AUTO
    check("운전원: REMOTE_AUTO 로", "ACCEPTED", op(10, 2))
    check("REMOTE_AUTO 에서 운전원 조작 거부", "MODE", op(2, 0))
    check("REMOTE_AUTO 에서 외부 요청 자동 수용", "ACCEPTED", rq(4, 1, h=0x2001))
    check("가상설비 냉각기 코일 켜짐", True, wait_for(lambda: instr("/state")["commands"]["cooler_enable"] is True))
    check("운전원: REMOTE_MANUAL 로", "ACCEPTED", op(10, 1))
    check("냉각기 끔", "ACCEPTED", op(4, 0))
    # 시각 동기 끊김 → 만료 검사 불가 → 외부 요청 거부
    sync_on.clear(); time.sleep(7)
    check("시각 동기 멈춤 → 외부 요청 거부", "NO_TIME_SYNC", rq(4, 1, accepted=1, h=0x3001))
    sync_on.set(); time.sleep(2)
    # 정비 모드
    check("운전원: 정비 모드 켜기(담당자 101)", "ACCEPTED", op(11, 101))
    s = status(); check("정비 모드 표시·담당자", [1, 101], [s["maint"], s["maint_op"]])
    check("정비 모드: 외부 요청 거부", "MAINTENANCE", rq(4, 1, accepted=1, h=0x4001))
    check("정비 모드: 운전원 기동 거부", "MAINTENANCE", op(4, 1))
    check("정비 모드: 운전원 정지(안전 쪽) 수용", "ACCEPTED", op(4, 0))
    check("정비 모드: 운전원 모드 바꾸기 거부", "MAINTENANCE", op(10, 2))
  else:
    # RETAIN: PLC 재시작 뒤에도 정비 모드 유지, 모드는 REMOTE_MANUAL 로 시작(1단계 끝에서 정비 모드를 켜 두었다)
    wait_for(lambda: status()["field_comm"] == 1, 30)
    s = status(); check("PLC 재시작 뒤 정비 모드 유지(RETAIN)·모드 REMOTE_MANUAL", [1, 101, 1], [s["maint"], s["maint_op"], s["mode"]])
    panel("maintenance_release")
    check("현장 해제 키로 정비 모드 끔", True, wait_for(lambda: status()["maint"] == 0))
    # LOCAL
    panel("mode", value="LOCAL")
    check("현장 모드 스위치 LOCAL", True, wait_for(lambda: status()["mode"] == 0))
    check("LOCAL: 운전원 조작 거부", "LOCAL_MODE", op(2, 0))
    check("LOCAL: 외부 요청 거부", "LOCAL_MODE", rq(2, 0, accepted=1, h=0x5001))
    panel("local", equipment="agitator", value=0)
    check("LOCAL: 현장 버튼으로 교반기 정지", True, wait_for(lambda: instr("/state")["commands"]["agitator_run"] is False))
    panel("local", equipment="agitator", value=1)
    check("LOCAL: 현장 버튼으로 교반기 기동", True, wait_for(lambda: instr("/state")["commands"]["agitator_run"] is True))
    check("LOCAL: 운전원 정비 모드 켜기만 수용", "ACCEPTED", op(11, 102))
    panel("maintenance_release"); wait_for(lambda: status()["maint"] == 0)
    panel("mode", value="REMOTE")
    check("REMOTE 로 돌아오면 REMOTE_MANUAL", True, wait_for(lambda: status()["mode"] == 1))
    # 고압 인터록(계기 튐 spike 로 PT-101 지시값 상승)
    instr("/fault", {"scenario": "spike", "duration_s": 6})
    check("PT-101 6.5 barg 이상 → 인터록", True, wait_for(lambda: status()["interlock"] == 1, 4))
    check("인터록 중 펌프 출력 꺼짐", True, wait_for(lambda: status()["outputs"] & 1 == 0, 2))
    check("인터록 중 펌프 기동 명령 거부", "INTERLOCK", op(1, 1))
    check("외부 요청으로 인터록 리셋 불가(모르는 명령)", "UNKNOWN_COMMAND", rq(12, 1, accepted=1, h=0x5002))
    instr("/fault/clear", {})
    wait_for(lambda: instr("/state")["readings"]["PT-101"] <= 5.0, 60)
    time.sleep(2)
    check("압력이 내려와도 트립 유지(기억)", 1, status()["interlock"])
    check("트립 뒤 펌프 운전 명령 꺼짐(저절로 다시 돌지 않음)", 0, status()["outputs"] & 1)
    check("운전원 인터록 리셋 수용", "ACCEPTED", op(12, 1))
    check("리셋 → 인터록 해제", True, wait_for(lambda: status()["interlock"] == 0, 4))
    check("리셋 뒤 운전원 펌프 기동", "ACCEPTED", op(1, 1))
    check("펌프 출력 복귀", True, wait_for(lambda: status()["outputs"] & 1 == 1, 4))
    # 압력이 높은 동안의 리셋은 거부, 현장 패널 리셋으로도 풀린다
    wait_for(lambda: instr("/state")["readings"]["PT-101"] >= 3.0, 60)   # 운전점으로 돌아와야 스파이크가 트립 값을 넘는다
    instr("/fault", {"scenario": "spike", "duration_s": 6})
    check("다시 트립", True, wait_for(lambda: status()["interlock"] == 1, 4))
    # 리셋 허용값(5.2 barg)보다 지시값이 확실히 높은 순간에 리셋을 낸다. 펌프가 멈추면 실제 압력이 떨어지므로 먼저 확인한다
    check("트립 뒤 PT-101 지시값이 리셋 허용값 + 0.3 barg 위", True,
          wait_for(lambda: instr("/state")["readings"]["PT-101"] > 5.5, 3))
    check("압력이 높은 동안 운전원 리셋 거부", "INTERLOCK", op(12, 1))
    instr("/fault/clear", {})
    wait_for(lambda: instr("/state")["readings"]["PT-101"] <= 5.0, 60)
    panel("reset")
    check("현장 패널 리셋 → 인터록 해제", True, wait_for(lambda: status()["interlock"] == 0, 4))
    op(1, 1); wait_for(lambda: status()["outputs"] & 1 == 1, 4)
    # 비상정지(가상설비 안 래치 + PLC 명령 끔)
    panel("estop")
    check("비상정지 → 모든 출력 꺼짐", True, wait_for(lambda: status()["estop"] == 1 and status()["outputs"] == 0))
    check("비상정지 중 가상설비 전류 0(제어와 독립)", True, wait_for(lambda: instr("/state")["readings"]["IT-102"] < 0.1))
    check("비상정지 중 기동 거부", "ESTOP", op(2, 1))
    panel("reset")
    check("리셋 뒤에도 저절로 다시 돌지 않음", True, wait_for(lambda: status()["estop"] == 0) and status()["outputs"] == 0)
    for code in (1, 2, 3):
        op(code, 1)
    check("리셋 뒤 운전원 기동으로 복귀(펌프·교반기·히터)", True, wait_for(lambda: status()["outputs"] & 7 == 7))
    # 생산 스케줄: 설정값이 설비 시각에 따라 움직인다 / 수동 조작 뒤 300초 보류
    sp1 = hr(100, 3); time.sleep(15); sp2 = hr(100, 3)
    check("생산 스케줄로 설정값 변동(15초)", True, sp1 != sp2)
    check("운전원: 온도 설정 70.0", "ACCEPTED", op(7, 700))
    time.sleep(15)
    check("수동 조작 뒤 온도 설정 보류(15초 동안 700 유지)", 700, hr(102)[0])
    check("되읽기 감시 이상 없음", 0, status()["fb_fault"])
finally:
    stop_all.set()
    fails = [r for r in results if r["verdict"] == "FAIL"]
    json.dump({"results": results, "pass": sum(r["verdict"] == "PASS" for r in results), "fail": len(fails)},
              open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"PASS {sum(r['verdict'] == 'PASS' for r in results)} / FAIL {len(fails)}")
    sys.exit(1 if fails else 0)
