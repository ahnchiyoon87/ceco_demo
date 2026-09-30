from datetime import datetime, timezone, timedelta
import io
import json

from backend.src.modules.operations import pipeline


def test_healthy_http_with_no_jobs_is_not_healthy_analysis(monkeypatch):
    monkeypatch.setattr(pipeline, 'urlopen', lambda *a, **kw: io.BytesIO(b'{"jobs":[]}'))
    assert pipeline.flink_status()['status'] == 'degraded'
    jobs = [{'name':str(i),'state':'RUNNING'} for i in range(4)]
    monkeypatch.setattr(pipeline, 'urlopen', lambda *a, **kw: io.BytesIO(json.dumps({'jobs':jobs}).encode()))
    assert pipeline.flink_status()['status'] == 'available'
    jobs[0]['state']='RESTARTING'
    assert pipeline.flink_status()['status'] == 'degraded'


def test_historian_requires_every_sensor_to_be_recent_and_good(monkeypatch):
    state={'status':'available','site':'AR-100','device':'reactor-line-01','readings':{'A':1,'B':2}}
    now=datetime.now(timezone.utc)
    rows=[{'tag':tag,'time':now.isoformat(),'quality':'GOOD','value':1} for tag in ('A','B')]
    monkeypatch.setattr(pipeline,'history',lambda *a:{'status':'available','rows':rows})
    assert pipeline.historian_status(state)['status']=='available'
    rows[1]['quality']='BAD'
    assert pipeline.historian_status(state)['status']=='degraded'
    rows[1]['quality']='GOOD'; rows[1]['time']=(now-timedelta(seconds=20)).isoformat()
    assert pipeline.historian_status(state)['status']=='degraded'
    rows.pop()
    assert pipeline.historian_status(state)['status']=='degraded'
