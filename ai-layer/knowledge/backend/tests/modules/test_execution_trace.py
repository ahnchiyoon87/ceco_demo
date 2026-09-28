"""Trace isolation against a real temporary PostgreSQL database."""
from uuid import uuid4
import os

import pytest
from fastapi import HTTPException

from backend.tests.modules.test_actions_integration import case
from backend.tests.modules.test_agent_workflow_integration import make_run
from backend.src.modules.operations import agent, actions
from backend.src.modules.operations.api import connection


@pytest.fixture(autouse=True)
def require_isolated_database(isolated_work_database):
    assert os.environ.get('DB_NAME','').startswith('ar100_pytest_'), 'Trace integration must use an isolated database'


def test_trace_includes_only_this_runs_proposal_actions(case, monkeypatch):
    uid, body, evidence, _ = case
    run=make_run(uid)
    proposal=actions.create_proposal(uid,body,evidence,origin=f"ai-run:{run['id']}:test")
    monkeypatch.setattr(actions,'stop_mixer',lambda _: {'status':'stop_verified','observations':[]})
    actions.decide(proposal['id'],actions.Decision(decision='approve',note='isolated trace test'))
    with connection() as conn:
        actions.event(conn,uid,'action_result',{'proposal_id':str(uuid4()),'reason':'unrelated proposal'})
        actions.event(conn,uid,'agent_tool_result',{'run_id':str(uuid4()),'reason':'unrelated run'})
    trace=agent.run_trace(run['id'])
    assert [e['kind'] for e in trace['items']]==['proposal_created','action_authorized','action_result']
    assert all(e['payload']['proposal_id']==str(proposal['id']) for e in trace['items'])


def test_run_trace_survives_alarm_flood_and_excludes_other_runs(case):
    uid = case[0]
    run = make_run(uid)
    with connection() as conn:
        actions.event(conn, uid, 'agent_tool_started', {'run_id': str(run['id']), 'call_id': 'a', 'tool': 'alarm'})
        for index in range(205):
            actions.event(conn, uid, 'alarm_correlated', {'tag': 'IT-102', 'index': index})
        actions.event(conn, uid, 'agent_tool_result', {'run_id': str(uuid4()), 'tool': 'documents'})
        actions.event(conn, uid, 'agent_tool_result', {'run_id': str(run['id']), 'call_id': 'a', 'tool': 'alarm', 'duration_ms': 8, 'result': {'revision': 1}})
    trace = agent.run_trace(run['id'])
    assert trace['run']['incident_id'] == uid
    assert [row['kind'] for row in trace['items']] == ['agent_tool_started', 'agent_tool_result']
    assert trace['truncated'] is False
    assert trace['items'][1]['payload']['duration_ms'] == 8


def test_trace_reports_truncation_and_unknown_run(case):
    uid = case[0]
    run = make_run(uid)
    with connection() as conn:
        for index in range(201):
            actions.event(conn, uid, 'agent_tool_result', {'run_id': str(run['id']), 'sequence': index})
    trace = agent.run_trace(run['id'])
    assert trace['truncated'] is True
    assert len(trace['items']) == 200
    assert trace['items'][0]['payload']['sequence'] == 1
    assert trace['items'][-1]['payload']['sequence'] == 200
    with pytest.raises(HTTPException) as missing:
        agent.run_trace(uuid4())
    assert missing.value.status_code == 404


def test_progress_is_committed_before_action_finishes_and_not_replayed(case, monkeypatch):
    uid, body, evidence, _ = case
    run = make_run(uid)
    proposal = actions.create_proposal(uid, body, evidence, origin=f"ai-run:{run['id']}:test")
    calls = []

    def adapter(state):
        calls.append(state)
        actions.action_progress('action_dispatch_started', {'address': 1, 'value': False})
        # A separate reader sees the event while decide holds its incident lock.
        trace = agent.run_trace(run['id'])
        assert trace['items'][-1]['kind'] == 'action_dispatch_started'
        with connection() as conn:
            assert conn.execute('SELECT status FROM manufacturing_proposals WHERE id=%s', (proposal['id'],)).fetchone()['status'] == 'executing'
        return {'status': 'uncertain', 'reason': 'Test adapter did not send a command'}

    monkeypatch.setattr(actions, 'stop_mixer', adapter)
    decision = actions.Decision(decision='approve', note='isolated streaming test')
    actions.decide(proposal['id'], decision)
    assert actions._progress_sink.get() is None
    assert actions.decide(proposal['id'], decision)['replayed'] is True
    assert len(calls) == 1


@pytest.mark.parametrize('action,address,value,key,status', [
    ('stop_mixer',1,False,'agitator_run','stop_verified'),
    ('enable_cooling',3,True,'cooler_enable','cooling_command_verified'),
])
def test_modbus_progress_uses_real_adapter_order_without_equipment_io(monkeypatch,action,address,value,key,status):
    import pymodbus.client
    writes, events = [], []
    class Client:
        def __init__(self, *args, **kwargs):
            assert kwargs['retries'] == 0
        def connect(self): return True
        def write_coil(self, address, value, **kwargs):
            writes.append((address, value))
            return self
        def isError(self): return False
        def close(self): pass
    monkeypatch.setattr(pymodbus.client, 'ModbusTcpClient', Client)
    monkeypatch.setenv('SIMULATOR_ACTIONS_ENABLED', 'true')
    before = {'site': 'AR-100', 'device': 'reactor-line-01', 'seq': 10, 'commands':{key:not value}}
    states=iter([{**before,'status':'available','commands':{key:value}}, {**before,'status':'available','seq':11,'commands':{key:value}}])
    monkeypatch.setattr(actions, 'live_state', lambda: next(states))
    monkeypatch.setattr(actions.time, 'sleep', lambda _:None)
    token = actions._progress_sink.set(lambda kind, payload: events.append((kind, payload)))
    try:
        assert getattr(actions,action)(before)['status'] == status
    finally:
        actions._progress_sink.reset(token)
    assert writes == [(address, value)]
    assert [kind for kind, _ in events] == ['action_connecting', 'action_dispatch_started', 'action_acknowledged', 'action_observed', 'action_observed']
    assert events[-1][1]['observation']['seq'] == 11


@pytest.mark.parametrize('failed_stage,expected_writes,expected_status', [
    ('action_connecting', 0, 'not_executed'),
    ('action_dispatch_started', 0, 'not_executed'),
    ('action_acknowledged', 1, 'uncertain'),
    ('action_observed', 1, 'uncertain'),
])
@pytest.mark.parametrize('action',['stop_mixer','enable_cooling'])
def test_progress_failure_never_retries_or_claims_success(monkeypatch, failed_stage, expected_writes, expected_status,action):
    import pymodbus.client
    writes = []
    class Client:
        def __init__(self, *args, **kwargs): assert kwargs['retries'] == 0
        def connect(self): return True
        def write_coil(self, *args, **kwargs):
            writes.append(args)
            return self
        def isError(self): return False
        def close(self): pass
    monkeypatch.setattr(pymodbus.client, 'ModbusTcpClient', Client)
    monkeypatch.setenv('SIMULATOR_ACTIONS_ENABLED', 'true')
    monkeypatch.setattr(actions, 'live_state', lambda: {'status':'available','seq':11,'site':'AR-100','device':'reactor-line-01','commands':{'agitator_run':False}})
    def fail(kind, payload):
        if kind == failed_stage:
            raise RuntimeError('Test audit storage failure')
    token = actions._progress_sink.set(fail)
    try:
        result = getattr(actions,action)({'seq':10,'site':'AR-100','device':'reactor-line-01','commands':{'cooler_enable':False}})
        assert result['status'] == expected_status
        assert result['error_type'] == 'ActionProgressError'
        assert '기록' in result['reason']
        assert len(writes) == expected_writes
    finally:
        actions._progress_sink.reset(token)


def test_unsupported_cooler_never_creates_transport(monkeypatch):
    import pymodbus.client
    monkeypatch.setattr(pymodbus.client,'ModbusTcpClient',lambda *a,**k:pytest.fail('no transport for unsupported cooler'))
    assert actions.enable_cooling({'commands':{}})['status']=='not_executed'
