"""Read-only bounded observation of four detectors, heap and checkpoints."""
import argparse
import json
import time
from datetime import datetime, timezone
from pathlib import Path
import requests

ap=argparse.ArgumentParser()
ap.add_argument('--seconds',type=int,default=300)
args=ap.parse_args()
out=Path(__file__).resolve().parents[2]/'experiments/BOOTH-20261013/threshold-ttl/stability.json'
base='http://localhost:37081'

def get(path):
    r=requests.get(base+path,timeout=15);r.raise_for_status();return r.json()

samples=[];end=time.monotonic()+args.seconds
while True:
    jobs=[j for j in get('/jobs/overview')['jobs'] if j['state'] not in ['FINISHED','CANCELED','FAILED']]
    sample={'at':datetime.now(timezone.utc).isoformat(),'jobs':[{k:j[k] for k in ['jid','name','state']} for j in jobs]}
    tm=get('/taskmanagers')['taskmanagers']
    if len(tm)==1:
        metrics=get('/taskmanagers/'+tm[0]['id']+'/metrics?get=Status.JVM.Memory.Heap.Used,Status.JVM.Memory.Heap.Max')
        sample['heap']={m['id'].split('.')[-1]:int(m['value']) for m in metrics}
    threshold=next((j for j in jobs if j['name']=='AR100-Tier1-Threshold'),None)
    if threshold:
        cp=get('/jobs/'+threshold['jid']+'/checkpoints')
        sample['checkpoint_counts']=cp['counts']
        sample['threshold_state_bytes']=cp.get('latest',{}).get('completed',{}).get('state_size')
    samples.append(sample)
    passed=all(len(s['jobs'])==4 and all(j['state']=='RUNNING' for j in s['jobs']) for s in samples)
    out.write_text(json.dumps({'passed':passed,'observation_s':args.seconds,'samples':samples},indent=2),encoding='utf-8')
    if time.monotonic()>=end:break
    time.sleep(min(30,max(0,end-time.monotonic())))
print(json.dumps({'passed':passed,'samples':len(samples),'threshold_state_bytes':samples[-1].get('threshold_state_bytes'),'heap':samples[-1].get('heap')}),flush=True)
if not passed:raise SystemExit(1)
