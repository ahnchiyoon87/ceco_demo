from copy import deepcopy
from datetime import datetime, timezone, timedelta
import pytest
from fastapi import HTTPException
from backend.src.modules.operations import actions
from .test_actions_integration import case


def thermal_case(case):
    uid, original, evidence, state = case
    state['commands'] = {'cooler_enable':False, 'temp_sp_c':70}
    state['readings'] = {'TT-101':100}
    evidence['graph']['assets'] = [{'name':'R-101'}]
    evidence['graph']['documents'] = [{'document_id':'AR100-THERMAL-RESPONSE'}]
    evidence['graph']['sensors'] = [{'tag':'TT-101','unit':'degC','lsl':40,'usl':95,'source_sha256':'test-source'}]
    evidence['current_history']['rows'] = [{'tag':'TT-101','value':100,'quality':'GOOD','time':datetime.now(timezone.utc).isoformat()}]
    body=original.model_copy(update={'action':'enable_cooling','citations':['AR100-THERMAL-RESPONSE']})
    return uid,body,evidence,state


@pytest.mark.parametrize('change',['stale','quality','unit','source','threshold','target','unsupported','interlock','normal_history','normal_live','ambiguous'])
def test_thermal_preconditions_reject_invalid_evidence(case,change):
    _,_,evidence,state=thermal_case(case)
    sensor=evidence['graph']['sensors'][0]
    row=evidence['current_history']['rows'][0]
    if change=='stale':row['time']=(datetime.now(timezone.utc)-timedelta(seconds=20)).isoformat()
    if change=='quality':row['quality']='BAD'
    if change=='unit':sensor['unit']='F'
    if change=='source':sensor['source_sha256']=''
    if change=='threshold':sensor['usl']=None
    if change=='target':state['commands']['temp_sp_c']=99
    if change=='unsupported':state['commands'].pop('cooler_enable')
    if change=='interlock':state['interlock']=True
    if change=='normal_history':row['value']=90
    if change=='normal_live':state['readings']['TT-101']=90
    if change=='ambiguous':evidence['graph']['sensors'].append(deepcopy(sensor))
    with pytest.raises(HTTPException):actions.require_current_thermal_anomaly(evidence,state)


def test_approved_cooling_is_dispatched_once_but_not_declared_recovered(case,monkeypatch):
    uid,body,evidence,state=thermal_case(case)
    proposal=actions.create_proposal(uid,body,evidence,origin='thermal-test')
    calls=[]
    monkeypatch.setattr(actions,'enable_cooling',lambda before:calls.append(before) or {'status':'cooling_command_verified','reason':'Command only'})
    decision=actions.Decision(decision='approve',note='Test grounded cooling proposal')
    first=actions.decide(proposal['id'],decision)
    assert first['proposal']['result']['status']=='cooling_command_verified'
    assert first['proposal']['status']=='observing'
    assert first['proposal']['completed_at'] is None
    assert actions.decide(proposal['id'],decision)['replayed'] is True
    assert len(calls)==1


def test_temperature_recovers_between_approval_and_dispatch_so_no_command(case,monkeypatch):
    uid,body,evidence,state=thermal_case(case)
    proposal=actions.create_proposal(uid,body,evidence,origin='thermal-test')
    normal=deepcopy(state);normal['readings']['TT-101']=90
    states=iter([deepcopy(state),normal])
    monkeypatch.setattr(actions,'live_state',lambda:next(states))
    monkeypatch.setattr(actions,'enable_cooling',lambda _:pytest.fail('No command after temperature changed'))
    result=actions.decide(proposal['id'],actions.Decision(decision='approve',note='Test changing temperature'))
    assert result['proposal']['result']['status']=='not_executed'


def test_cooling_rejection_never_dispatches(case,monkeypatch):
    uid,body,evidence,_=thermal_case(case)
    proposal=actions.create_proposal(uid,body,evidence,origin='thermal-test')
    monkeypatch.setattr(actions,'enable_cooling',lambda _:pytest.fail('Rejected cooling must not dispatch'))
    result=actions.decide(proposal['id'],actions.Decision(decision='reject',note='More evidence needed'))
    assert result['proposal']['status']=='rejected'
