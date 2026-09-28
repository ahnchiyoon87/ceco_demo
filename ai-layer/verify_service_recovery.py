"""Live local-container fault injection. Always restore stopped services.

Requires the running AR-100 stack; never stops the original SCADA services.
Only synthetic records created by this run are removed after verification.
"""
import argparse
import base64
import json
import subprocess
import time
import urllib.request
import urllib.error
from pathlib import Path
from uuid import UUID, uuid4

ROOT=Path(__file__).resolve().parents[1]
COMPOSE=['docker','compose','--env-file','ai-layer/.env.local','-f','ai-layer/compose.yml','-f','ai-layer/compose.scada.yml','--profile','knowledge']
BASE='http://127.0.0.1:28000'
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('incident_id', type=UUID, help='Existing AR-100 incident linked to the three published demo documents')
CASE=str(parser.parse_args().incident_id)
report={'verification':'real-container-outage-and-kafka-recovery','steps':[]}


def command(args, *, code=None):
    result=subprocess.run(args,input=code,cwd=ROOT,text=True,encoding='utf-8',capture_output=True,timeout=60)
    if result.returncode:raise RuntimeError(f'Command failed: {args[:3]}: {result.stderr[-1000:]}')
    return result.stdout


def api(path):
    try:
        with urllib.request.urlopen(BASE+path,timeout=20) as response:return response.status,json.load(response)
    except urllib.error.HTTPError as error:return error.code,json.load(error)


def wait_for(function, timeout=45):
    end=time.monotonic()+timeout
    last=None
    while time.monotonic()<end:
        try:
            last=function()
            if last:return last
        except (OSError,RuntimeError):pass
        time.sleep(1)
    raise TimeoutError(f'Recovery condition not met; last={last}')


def in_knowledge(code):
    return json.loads(command(COMPOSE+['exec','-T','knowledge','python','-'],code=code))


def kafka(code):
    return json.loads(command(['docker','run','--rm','-i','--network','iiot','--entrypoint','python','ar100-ai-knowledge','-'],code=code))


def committed(partition):
    return kafka(f"""import json
from confluent_kafka import Consumer,TopicPartition
c=Consumer({{'bootstrap.servers':'kafka:9092','group.id':'ar100-ai-incidents-v1'}})
try: print(json.dumps({{'offset':c.committed([TopicPartition('sensor.alerts',{partition})],timeout=10)[0].offset}}))
finally:c.close()
""")["offset"]


marker='verification-recovery-'+str(uuid4())
alarm={'ts':time.time_ns(),'site':marker,'device':'probe','tag':'VT-101','value':8.0,
       'alert_type':'RECOVERY_TEST','severity':'INFO','detector':'INTEGRATION','detail':'Synthetic outage verification; not a plant event'}
valid=json.dumps(alarm,separators=(',',':')).encode()
invalid=b'{"invalid_verification_message":true}'
payloads=[base64.b64encode(raw).decode() for raw in (valid,valid,invalid)]
offsets=[]
try:
    assert api('/api/operations/incidents')[0]==200
    print('Verified initial incident API.',flush=True)
    before=api(f'/api/operations/incidents/{CASE}/evidence')[1]
    assert before['graph']['status']=='available' and len(before['graph']['documents'])==3
    try:
        command(COMPOSE+['stop','graph'])
        status,degraded=api(f'/api/operations/incidents/{CASE}/evidence')
        assert status==200 and degraded['graph']['status']=='unavailable'
        assert not degraded['graph']['documents']
        assert api('/api/knowledge/published')[0]==503
        report['steps'].append({'step':'graph_unavailable','graph_status':degraded['graph']['status'],
                                'historical_status':degraded['history']['status'],'published_api':503})
    finally:
        command(COMPOSE+['start','graph'])
        def graph_ready():
            code,value=api(f'/api/operations/incidents/{CASE}/evidence')
            return value if code==200 and value['graph']['status']=='available' else None
        restored=wait_for(graph_ready)
        assert {d['document_id']:d['sha256'] for d in restored['graph']['documents']}=={d['document_id']:d['sha256'] for d in before['graph']['documents']}
        report['steps'].append({'step':'graph_restored','documents':len(restored['graph']['documents']),'source_hashes_preserved':True})
        print('Graph outage reported explicitly; source hashes preserved after restart.',flush=True)
    try:
        command(COMPOSE+['stop','work-db'])
        assert api('/api/operations/incidents')[0]==503
        offsets=kafka(f"""import json,base64
from confluent_kafka import Producer
p=Producer({{'bootstrap.servers':'kafka:9092'}}); delivered=[]
def ack(error,message):
    if error: raise RuntimeError(str(error))
    delivered.append({{'partition':message.partition(),'offset':message.offset()}})
for raw in {payloads!r}:p.produce('sensor.alerts',key={marker!r},value=base64.b64decode(raw),on_delivery=ack)
assert p.flush(15)==0
print(json.dumps(delivered))
""")
        assert len(offsets)==3 and len({row['partition'] for row in offsets})==1
        partition=offsets[0]['partition']
        offset_numbers=sorted(row['offset'] for row in offsets)
        down_offset=committed(partition)
        assert down_offset<=min(offset_numbers), 'Offset advanced past a message while DB was unavailable'
        report['steps'].append({'step':'database_unavailable','api_status':503,'produced_offsets':offsets,'committed_offset':down_offset})
        print('DB unavailable: incident API 503 and Kafka offset did not pass pending messages.',flush=True)
    finally:
        command(COMPOSE+['start','work-db'])
        wait_for(lambda:api('/api/operations/incidents')[0]==200)
    def persisted():
        rows=in_knowledge(f"""import json,base64
from backend.src.modules.operations.api import connection
with connection() as c:
 rows=c.execute('SELECT offset_id,status,incident_id,raw_payload FROM manufacturing_inbox WHERE topic=%s AND partition_id=%s AND offset_id=ANY(%s) ORDER BY offset_id',('sensor.alerts',{partition},{offset_numbers!r})).fetchall()
 for r in rows:r['raw_payload']=base64.b64encode(bytes(r['raw_payload'])).decode()
 print(json.dumps(rows,default=str))
""")
        return rows if len(rows)==3 else None
    rows=wait_for(persisted,60)
    assert [r['status'] for r in rows]==['accepted','accepted','rejected']
    assert [r['raw_payload'] for r in rows]==payloads
    assert rows[0]['incident_id']==rows[1]['incident_id']
    details=api('/api/operations/incidents/'+rows[0]['incident_id'])[1]
    assert details['incident']['alarm_count']==1
    assert len(details['events'])==1
    after_offset=wait_for(lambda:(v if (v:=committed(partition))>max(offset_numbers) else None))
    report['steps'].append({'step':'database_restored','inbox':rows,'incident_count':1,'original_alarm_count':1,
                            'event_count':1,'committed_offset':after_offset})
    report['passed']=True
finally:
    # Recovery is attempted even if an assertion fails. Never remove containers/volumes.
    command(COMPOSE+['start','work-db','graph'])
    wait_for(lambda:api('/api/operations/incidents')[0]==200)
    if offsets:
        command(COMPOSE+['exec','-T','knowledge','python','-'],code=f"""from backend.src.modules.operations.api import connection
with connection() as c:
 ids=[r['id'] for r in c.execute('SELECT id FROM manufacturing_incidents WHERE site=%s',({marker!r},)).fetchall()]
 c.execute('DELETE FROM manufacturing_inbox WHERE topic=%s AND partition_id=%s AND offset_id=ANY(%s)',('sensor.alerts',{offsets[0]['partition']},{[row['offset'] for row in offsets]!r}))
 for uid in ids:
  c.execute('DELETE FROM manufacturing_alarm_links WHERE incident_id=%s',(uid,))
  c.execute('DELETE FROM manufacturing_events WHERE incident_id=%s',(uid,))
  c.execute('DELETE FROM manufacturing_incidents WHERE id=%s',(uid,))
""")
    (ROOT/'docs/ai-work/live-service-recovery.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({'passed':report.get('passed',False),'completed_steps':[step['step'] for step in report['steps']]}))
