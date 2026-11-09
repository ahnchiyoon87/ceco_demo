"""One-time booth repair: retain a savepoint and update only the threshold job.

The plant must be idle and no approved maintenance may be executing. Existing
Kafka offsets and operator state are restored from the savepoint. No histories
or checkpoint volumes are deleted, and the other three jobs remain running.
"""
import json
import re
import subprocess
import sys
import time
from pathlib import Path

import requests

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'tests/e2e'))
import maintenance_scenarios as M

OUT=ROOT/'experiments/BOOTH-20261013/threshold-ttl'
OUT.mkdir(exist_ok=True)
BASE='http://localhost:'+M.V.ENV['PORT_FLINK_UI']

def api(path,body=None):
    r=requests.get(BASE+path,timeout=30) if body is None else requests.post(BASE+path,json=body,timeout=30)
    r.raise_for_status();return r.json()

def write(name,value):
    (OUT/name).write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8')

def shell(*args):
    r=subprocess.run(args,capture_output=True,text=True,encoding='utf-8',errors='replace',timeout=180)
    if r.returncode:raise RuntimeError(r.stderr[-1500:])
    return r.stdout

state=M.plant()
assert not state['active_faults'] and not state.get('execution_active'),'정비가 끝난 정상 상태에서만 변경합니다.'
jobs=[j for j in api('/jobs/overview')['jobs'] if j['state']=='RUNNING']
assert len(jobs)==4
job=next(j for j in jobs if j['name']=='AR100-Tier1-Threshold')
write('before.json',{'jobs':jobs,'checkpoints':api('/jobs/'+job['jid']+'/checkpoints')})
# Ask Flink to checkpoint consumed offsets before terminating this one job.
trigger=api('/jobs/'+job['jid']+'/savepoints',{'target-directory':'file:///opt/flink/checkpoints/booth-threshold-ttl','cancel-job':True})
write('trigger.json',trigger)
deadline=time.monotonic()+120
while True:
    saved=api('/jobs/'+job['jid']+'/savepoints/'+trigger['request-id'])
    if saved['status']['id']=='COMPLETED':break
    if time.monotonic()>deadline:raise RuntimeError('Savepoint completion timeout; do not resubmit blindly.')
    time.sleep(1)
write('savepoint.json',saved)
location=saved['operation'].get('location')
assert location and not saved['operation'].get('failure-cause'),saved
# Keep restore strict: an unmatched operator must fail, never silently drop state.
sql="SET 'execution.savepoint.path' = '"+location+"';\nSET 'execution.savepoint.ignore-unclaimed-state' = 'false';\n"
sql+='SET \'execution.savepoint-restore-mode\' = \'NO_CLAIM\';\n'
sql+=(ROOT/'4_it/detection-flink/sql/01_sources.sql').read_text(encoding='utf-8')+'\n'
sql+=(ROOT/'4_it/detection-flink/sql/02_tier1_rules.sql').read_text(encoding='utf-8')+'\n'
path=OUT/'restore-threshold.sql';path.write_text(sql,encoding='utf-8')
container=M.V.c('flink-jobmanager')
shell('docker','cp',str(path),container+':/tmp/booth-threshold-ttl.sql')
output=shell('docker','exec',container,'/opt/flink/bin/sql-client.sh','-f','/tmp/booth-threshold-ttl.sql')
output=re.sub(r'\x1b\[[0-9;]*m','',output)
(OUT/'submit.log').write_text(output,encoding='utf-8')
assert '[ERROR]' not in output,output[-2000:]
match=re.search(r'Job ID:\s*([0-9a-f]{32})',output)
assert match,output[-2000:]
new_id=match[1]
deadline=time.monotonic()+120
while True:
    new=api('/jobs/'+new_id)
    if new['state']=='RUNNING':break
    if new['state'] in ['FAILED','CANCELED']:raise RuntimeError('Restore failed; original savepoint retained: '+location)
    if time.monotonic()>deadline:raise RuntimeError('Restore did not stabilize; inspect saved logs.')
    time.sleep(2)
write('result.json',{'old_job':job['jid'],'new_job':new_id,'restore_from':location,'restored':True,'other_jobs':[j['jid'] for j in jobs if j['jid']!=job['jid']],'checked_at':time.time()})
print('Threshold TTL restored from savepoint:',new_id,flush=True)
