"""E2 구성 복잡도(측정 도구): compose 설정 JSON + paths.yaml → 서비스·이미지·설정 마운트·포트·경유 단계.
  python harness/tools/e2_complexity.py <구조이름> <compose-config.json>... > experiments/<EXP>/e2_<구조>.json
"""
import json, sys
import yaml

name, files = sys.argv[1], sys.argv[2:]
services = {}
for f in files:
    services.update(json.load(open(f, encoding="utf-8"))["services"])
oneshot = sorted(k for k, v in services.items() if v.get("restart") in (None, "no") and any(w in k for w in ("init", "submitter", "provisioner", "trainer")))
paths = yaml.safe_load(open("harness/situations/paths.yaml", encoding="utf-8")).get(name, {})
out = {"structure": name, "services_total": len(services), "services_long_running": len(services) - len(oneshot),
       "oneshot": oneshot, "images": sorted({v.get("image", "(build)") for v in services.values()}),
       "bind_mounts": sum(1 for v in services.values() for m in v.get("volumes", []) if m.get("type") == "bind"),
       "published_ports": sum(len(v.get("ports", [])) for v in services.values()),
       "alarm_to_hmi_hops": len(paths.get("alarm_to_hmi", [])), "duplicates": paths.get("duplicates", {})}
out["image_count"] = len(out["images"])
print(json.dumps(out, ensure_ascii=False, indent=1))
