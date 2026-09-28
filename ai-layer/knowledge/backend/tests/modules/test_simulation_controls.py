import pytest
import os
from uuid import uuid4
from pydantic import ValidationError
from fastapi import HTTPException
from backend.src.modules.operations import simulation


def test_disabled_never_contacts_simulator(monkeypatch):
    monkeypatch.delenv('SIMULATOR_ACTIONS_ENABLED', raising=False)
    monkeypatch.setattr(simulation, 'simulator', lambda *a: pytest.fail('must not contact simulator'))
    with pytest.raises(HTTPException) as exc:
        simulation.inject()
    assert exc.value.status_code == 403


@pytest.mark.parametrize('running,interlock,faults', [(False,False,{}),(True,True,{}),(True,False,{'bearing_wear':{}})])
def test_invalid_start_never_writes(monkeypatch,running,interlock,faults):
    monkeypatch.setenv('SIMULATOR_ACTIONS_ENABLED','true')
    monkeypatch.setattr(simulation,'status',lambda:dict(agitator_run=running,interlock=interlock,active_faults=faults))
    monkeypatch.setattr(simulation,'simulator',lambda *a:pytest.fail('must not write'))
    with pytest.raises(HTTPException) as exc:simulation.inject()
    assert exc.value.status_code == 409


def test_only_fixed_training_scenario_is_sent(monkeypatch):
    monkeypatch.setenv('SIMULATOR_ACTIONS_ENABLED','true')
    monkeypatch.setattr(simulation,'status',lambda:dict(agitator_run=True,interlock=False,active_faults={}))
    writes=[]
    monkeypatch.setattr(simulation,'simulator',lambda *args:writes.append(args))
    simulation.inject()
    assert writes==[('/fault',{'scenario':'bearing_wear','duration_s':600})]


@pytest.mark.parametrize('target,value', [('pump_run',.5),('temp_sp_c',101),('temp_sp_c',20.01),('pump_speed_sp',-1),('valve_open_sp',float('nan')),('interlock',0)])
def test_operator_rejects_invalid_input(target,value):
    with pytest.raises(ValidationError):
        simulation.OperatorCommand(request_id=uuid4(),target=target,value=value)


@pytest.mark.parametrize('target,value,method,address,encoded',[
    ('agitator_run',0,'coil',1,False),('pump_run',1,'coil',0,True),
    ('heater_enable',0,'coil',2,False),('cooler_enable',1,'coil',3,True),('pump_speed_sp',60,'register',100,60),
    ('valve_open_sp',45,'register',101,45),('temp_sp_c',72.3,'register',102,723)])
def test_operator_modbus_mapping_and_fresh_readback(monkeypatch,target,value,method,address,encoded):
    import pymodbus.client
    from types import SimpleNamespace
    writes=[]
    class Client:
        def __init__(self,*args,**kwargs):assert kwargs['retries']==0
        def connect(self):return True
        def close(self):pass
        def write_coil(self,a,v,**kwargs):writes.append(('coil',a,v));return SimpleNamespace(isError=lambda:False)
        def write_register(self,a,v,**kwargs):writes.append(('register',a,v));return SimpleNamespace(isError=lambda:False)
    monkeypatch.setattr(pymodbus.client,'ModbusTcpClient',Client)
    before={'site':'test','device':'AR100','seq':10}
    states=iter([{**before,'commands':{target:value}},{**before,'seq':11,'commands':{target:value}}])
    monkeypatch.setattr(simulation,'simulator',lambda path:next(states))
    monkeypatch.setattr(simulation.time,'sleep',lambda _:None)
    result=simulation.write_operator_command(simulation.OperatorCommand(request_id=uuid4(),target=target,value=value),before)
    assert result['status']=='verified'
    assert result['after']['seq']==11
    assert writes==[(method,address,encoded)]


def test_repeated_operator_request_writes_once(monkeypatch):
    assert os.environ.get('DB_NAME','').startswith('ar100_pytest_'), 'Refuse to write to a non-isolated work database'
    monkeypatch.setenv('SIMULATOR_ACTIONS_ENABLED','true')
    monkeypatch.setattr(simulation,'simulator',lambda _:dict(seq=10,interlock=False,active_faults={}))
    calls=[]
    monkeypatch.setattr(simulation,'write_operator_command',lambda c,b:calls.append(c) or {'status':'uncertain','reason':'reply lost'})
    command=simulation.OperatorCommand(request_id=uuid4(),target='agitator_run',value=0)
    first=simulation.control(command)
    assert simulation.control(command)==first
    assert len(calls)==1
    saved=next(item for item in simulation.control_history()['items'] if item['id']==command.request_id)
    assert saved['result']==first
    assert saved['result']['status']=='uncertain'
    with pytest.raises(HTTPException) as exc:
        simulation.control(command.model_copy(update={'value':1}))
    assert exc.value.status_code==409
    assert len(calls)==1


@pytest.mark.parametrize('interlock,faults',[(True,{}),(False,{'bearing_wear':{}})])
def test_operator_start_guard_never_writes(monkeypatch,interlock,faults):
    assert os.environ.get('DB_NAME','').startswith('ar100_pytest_'), 'Refuse to write to a non-isolated work database'
    monkeypatch.setenv('SIMULATOR_ACTIONS_ENABLED','true')
    monkeypatch.setattr(simulation,'simulator',lambda _:dict(seq=10,interlock=interlock,active_faults=faults))
    monkeypatch.setattr(simulation,'write_operator_command',lambda *args:pytest.fail('must not write'))
    with pytest.raises(HTTPException) as exc:
        simulation.control(simulation.OperatorCommand(request_id=uuid4(),target='agitator_run',value=1))
    assert exc.value.status_code==409


@pytest.mark.parametrize('faults,interlock,available,allowed',[
    ({'heater_stuck':{}},False,True,True),
    ({'cooling_loss':{}},False,True,True),
    ({'bearing_wear':{}},False,True,False),
    ({'heater_stuck':{}},True,True,False),
    ({},False,False,False),
])
def test_cooling_guard_preserves_interlock_and_requires_runtime_capability(faults,interlock,available,allowed):
    command=simulation.OperatorCommand(request_id=uuid4(),target='cooler_enable',value=1)
    state={'interlock':interlock,'active_faults':faults,'commands':{'cooler_enable':False} if available else {}}
    if allowed:
        simulation.validate_operator_state(command,state)
    else:
        with pytest.raises(HTTPException) as exc:simulation.validate_operator_state(command,state)
        assert exc.value.status_code==409
