"""Read-only sampling after a separately authorized browser control action."""
import json
import time
from pathlib import Path
from urllib.request import urlopen

target=Path(__file__).resolve().parents[1]/'docs/ai-work/uiux-20260928/thermal-live-observations.json'
samples=[]
for index in range(13):
    with urlopen('http://localhost:28000/api/operations/plant',timeout=8) as response:
        state=json.load(response)
    samples.append({'observed_at':time.time(),'seq':state.get('seq'),'status':state.get('status'),
                    'temperature':state.get('readings',{}).get('TT-101'),
                    'commands':state.get('commands'),'interlock':state.get('interlock')})
    target.write_text(json.dumps({'kind':'live read-only observations after browser target=60 control; not alarm/Agent E2E','samples':samples},ensure_ascii=False,indent=2),encoding='utf-8')
    if index<12:time.sleep(5)
print(json.dumps({'count':len(samples),'first':samples[0],'last':samples[-1]}))
