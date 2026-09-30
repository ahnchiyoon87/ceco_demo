"""Real PostgreSQL pagination while newer records arrive; no plant control."""
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.src.host.app import create_app
from backend.src.modules.operations.api import Alarm, initialize, ingest, connection


def test_new_records_do_not_shift_history_pages_or_leak_other_incidents():
    initialize()
    client=TestClient(create_app())
    ids=[]
    try:
        for _ in range(2):
            result=ingest(Alarm(ts=1,site=f'pagination-{uuid4()}',device='probe',tag='test',
                value=1,alert_type='TEST',severity='INFO',detector='integration',detail='Synthetic pagination test'))
            ids.append(result['incident']['id'])
        with connection() as c:
            for _ in range(4):
                c.execute("INSERT INTO manufacturing_events(incident_id,kind,payload) VALUES (%s,'probe','{}')",(ids[0],))
            expected=[r['id'] for r in c.execute('SELECT id FROM manufacturing_events WHERE incident_id=%s ORDER BY id DESC',(ids[0],)).fetchall()]
        path=f'/api/operations/incidents/{ids[0]}/events'
        first=client.get(path,params={'limit':2}).json()
        with connection() as c:
            added=c.execute("INSERT INTO manufacturing_events(incident_id,kind,payload) VALUES (%s,'new_arrival','{}') RETURNING id",(ids[0],)).fetchone()['id']
        second=client.get(path,params={'limit':2,'before_id':first['next_before_id']}).json()
        third=client.get(path,params={'limit':2,'before_id':second['next_before_id']}).json()
        assert [e['id'] for page in [first,second,third] for e in page['items']]==expected
        assert not third['has_more'] and third['next_before_id'] is None
        assert client.get(path,params={'limit':2}).json()['items'][0]['id']==added
        assert client.get(path,params={'before_id':-1}).status_code==422
        assert client.get(f'/api/operations/incidents/{uuid4()}/events').status_code==404
    finally:
        with connection() as c:
            for uid in ids:
                c.execute('DELETE FROM manufacturing_alarm_links WHERE incident_id=%s',(uid,))
                c.execute('DELETE FROM manufacturing_events WHERE incident_id=%s',(uid,))
                c.execute('DELETE FROM manufacturing_incidents WHERE id=%s',(uid,))
