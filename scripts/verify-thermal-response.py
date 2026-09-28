"""Exercise the real plant equations in isolation; not a running Modbus/Flink E2E."""
from pathlib import Path
import copy
import json
import sys

import yaml

root = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(root / 'simulator'))
from plant import ReactorPlant

cfg = yaml.safe_load((root / 'simulator/plant.yaml').read_text(encoding='utf8'))
cfg['autopilot']['enabled'] = False
cfg['noise'] = {key: 0 for key in cfg['noise']}

def scenario(name, target, heater=True, feed=True):
    p = ReactorPlant(copy.deepcopy(cfg))
    p.temp_c = p.jacket_c = 95.0
    p.sp_temp_c = target
    p.cmd_heater = heater
    p.cmd_pump = feed
    # Keep mass nearly steady for the stopped-feed comparison; no new cooling term.
    if not feed:
        p.sp_valve_open = 0
    rows = []
    for second in range(1, 1801):
        p.step(1.0)
        if second in (1, 30, 60, 300, 600, 900, 1800):
            rows.append({'seconds':second,'temperature_c':round(p.temp_c,3),
                         'pressure_barg':round(p.readings['PT-101'],3),
                         'interlock':p.interlocked,'flow_m3h':round(p.readings['FT-101'],3)})
    return {'name':name,'target_c':target,'heater_enabled':heater,'feed_enabled':feed,'samples':rows}

cases = [scenario('unchanged_high_target',95),scenario('lower_target',65),
         scenario('heater_off',65,False),scenario('heater_off_no_feed',65,False,False)]
base,lower,off,no_feed = [c['samples'][-1]['temperature_c'] for c in cases]
assert lower < base - 2, 'Lower target should reduce temperature relative to no intervention'
assert off < base - 2, 'Heater-off should reduce temperature relative to no intervention'
assert no_feed > off, 'Without cool feed the model should cool more slowly'
assert no_feed > 65, 'Heater-off must not be reported as reaching target merely because command applied'
result = {'scope':'isolated real plant equations, 1800 simulated seconds; no live equipment IO',
          'conditions':'initial 95C; autopilot disabled; measurement noise zero; no active cooler exists',
          'cases':cases,'checks_passed':4}
out=root/'docs/ai-work/uiux-20260928/thermal-response-isolated.json'
out.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
print(json.dumps({'checks_passed':4,'final_c':dict(zip([c['name'] for c in cases],[base,lower,off,no_feed]))}))
