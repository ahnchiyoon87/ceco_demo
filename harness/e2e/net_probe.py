"""[측정 도구] 구역 사이 연결 시도(라우터 규칙이 실제로 막고 넘기는지). 대상 컨테이너 안에서 실행:
  docker exec -i <컨테이너> python3 - <구역> <NET_PREFIX> < harness/e2e/net_probe.py
구역별로 '막혀야 하는 것'과 '열려야 하는 것'에 TCP 연결을 시도한다(3 s). 결과 JSON 한 줄.
주소는 compose.yml 고정 주소(ipv4_address)와 라우터의 구역별 주소(.2)다.
"""
import json, socket, sys

zone, P = sys.argv[1], sys.argv[2]
OT = {"sim-api": (f"{P}.10.11", 8080), "field-panel": (f"{P}.10.11", 8081), "sim-modbus": (f"{P}.10.11", 5020),
      "ot-hub": (f"{P}.10.12", 1883), "edge": (f"{P}.10.13", 1880), "plc-modbus": (f"{P}.10.14", 502),
      "plc-api": (f"{P}.10.14", 8443), "fuxa": (f"{P}.10.15", 1881)}
R_OT, R_DMZ, R_IT = f"{P}.10.2", f"{P}.20.2", f"{P}.30.2"
DMZ = {"dmz-broker": (f"{P}.20.11", 1883), "dmz-influx": (f"{P}.20.12", 8086), "dmz-prom": (f"{P}.20.13", 9090),
       "dmz-gateway": (f"{P}.20.14", 8088)}
IT_SVCS = {"kafka": 9092, "postgres": 5432, "it-influx": 8086, "knowledge": 8000}

tests = {}
if zone == "dmz":       # DMZ → OT·IT 새 연결 없음(규칙), DMZ → 라우터로 OT·IT 포트 없음
    block = {f"dmz->ot {k}": v for k, v in OT.items()}
    block |= {f"dmz->router(dmz) {p}": (R_DMZ, p) for p in (1883, 8080, 8081, 502, 1881, 9092, 5432)}
    block |= {f"dmz->it {k}": (f"{P}.30.{i}", p) for i, (k, p) in enumerate(IT_SVCS.items(), start=10)}
    allow = {}
elif zone == "it":      # IT → OT 없음(직접·라우터 사람용 포트 모두), IT → DMZ 는 허용 4개만
    block = {f"it->ot {k}": v for k, v in OT.items()}
    block |= {f"it->router(it) host-only {p}": (R_IT, p) for p in (21881, 28080, 28081, 21883, 21880, 28443)}
    block |= {f"it->dmz direct {k}": v for k, v in DMZ.items()}
    block |= {f"it->router(it) other {p}": (R_IT, p) for p in (502, 5020, 1881, 8080)}
    allow = {f"it->dmz via router {k}": (R_IT, v[1]) for k, v in DMZ.items()}
elif zone == "ot":      # OT → DMZ 는 브리지 1883·감시 9090 만, OT → IT 없음
    block = {f"ot->router(ot) {p}": (R_OT, p) for p in (8086, 8088, 9092, 5432)}
    block |= {f"ot->dmz direct {k}": v for k, v in DMZ.items()}
    block |= {f"ot->it {k}": (f"{P}.30.{i}", p) for i, (k, p) in enumerate(IT_SVCS.items(), start=10)}
    allow = {"ot->dmz bridge 1883": (R_OT, 1883), "ot->dmz prom 9090": (R_OT, 9090)}
else:
    raise SystemExit(f"구역을 모름: {zone}")


def try_connect(addr):
    s = socket.socket(); s.settimeout(3)
    try:
        s.connect(addr); return "open"
    except socket.timeout:
        return "timeout"
    except OSError as e:
        return type(e).__name__ + (f"({e.errno})" if e.errno else "")
    finally:
        s.close()


for name, addr in block.items():
    r = try_connect(addr); tests[name] = {"addr": f"{addr[0]}:{addr[1]}", "result": r, "expect": "blocked", "ok": r != "open"}
for name, addr in allow.items():
    r = try_connect(addr); tests[name] = {"addr": f"{addr[0]}:{addr[1]}", "result": r, "expect": "open", "ok": r == "open"}
print(json.dumps({"zone": zone, "ok": all(t["ok"] for t in tests.values()), "n": len(tests),
                  "failed": {k: v for k, v in tests.items() if not v["ok"]}, "tests": tests}, ensure_ascii=False))
