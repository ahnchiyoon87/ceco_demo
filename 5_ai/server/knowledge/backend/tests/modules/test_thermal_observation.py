from copy import deepcopy
import pytest
from backend.src.modules.operations import thermal_observation as thermal
from backend.src.modules.operations import actions, evidence as evidence_module
from .test_actions_integration import case
from .test_thermal_approval import thermal_case


def state(seq=1,temp=70):
    return {'status':'available','site':'AR-100','device':'reactor-line-01','seq':seq,
            'commands':{'temp_sp_c':70,'cooler_enable':True},'readings':{'TT-101':temp}}


def test_only_fresh_continuous_samples_can_complete_hold():
    track=thermal.start(state(),100)
    for i in range(16):track=thermal.observe(track,state(i),100+i*2)
    assert track['status']=='temperature_stable'
    assert track['held_s']==30
    assert '정비 완료는 아닙니다' in track['reason']


def test_same_scan_or_disconnect_cannot_accumulate_hold():
    track=thermal.observe(thermal.start(state(),100),state(),100)
    assert thermal.observe(track,state(),131)['status']=='unknown'
    unknown=thermal.observe(track,{'status':'unavailable'},101)
    assert unknown['within_since'] is None
    resumed=thermal.observe(unknown,state(2),132)
    assert resumed['held_s']==0


def test_restart_gap_resets_hold_in_persisted_track():
    track=thermal.start(state(),100)
    for i in range(10):track=thermal.observe(track,state(i),100+2*i)
    resumed=thermal.observe(deepcopy(track),state(11),145)
    assert resumed['held_s']==0
    assert resumed['status']=='observing'


@pytest.mark.parametrize('change',['target','cooler','device','seq','interlock'])
def test_changed_approval_context_interrupts_without_command(change):
    track=thermal.observe(thermal.start(state(),100),state(10),100)
    changed=state(11)
    if change=='target':changed['commands']['temp_sp_c']=71
    if change=='cooler':changed['commands']['cooler_enable']=False
    if change=='device':changed['device']='another'
    if change=='seq':changed['seq']=1
    if change=='interlock':changed['interlock']=True
    assert thermal.observe(track,changed,102)['status']=='interrupted'


def test_timeout_and_bad_numbers_cannot_succeed():
    track=thermal.start(state(),100)
    assert thermal.observe(track,state(2),1000)['status']=='timeout'
    for value in [None,float('nan'),float('inf'),True]:
        assert thermal.observe(track,state(2,value),102)['status']=='unknown'


def test_observer_persists_fresh_samples_and_terminal_result_without_second_command(case,monkeypatch):
    uid,body,evidence,plant=thermal_case(case)
    clock=[100.0]
    monkeypatch.setattr(thermal.time,'time',lambda:clock[0])
    calls=[]
    monkeypatch.setattr(actions,'enable_cooling',lambda _:calls.append(1) or {'status':'cooling_command_verified'})
    proposal=actions.create_proposal(uid,body,evidence,origin='thermal-observation-test')
    actions.decide(proposal['id'],actions.Decision(decision='approve',note='Test observer'))
    plant.update(seq=200,readings={'TT-101':70})
    plant['commands']['cooler_enable']=True
    monkeypatch.setattr(evidence_module,'live_state',lambda:deepcopy(plant))
    for i in range(16):
        clock[0]=100+i*2
        plant['seq']=200+i
        thermal.tick()
        thermal.tick()  # same scan must not add hold time or repeat commands
    saved=actions.list_proposals(uid)['items'][0]
    assert saved['status']=='awaiting_maintenance'
    assert saved['result']['status']=='temperature_stable'
    assert saved['result']['thermal_observation']['held_s']==30
    assert saved['completed_at'] is not None
    assert calls==[1]
    with actions.connection() as conn:
        records=conn.execute("SELECT count(*) AS n FROM manufacturing_events WHERE incident_id=%s AND kind='thermal_observation'",(uid,)).fetchone()
        assert records['n']==16


def test_changed_review_basis_stops_old_recovery_claim(case,monkeypatch):
    uid,body,evidence,plant=thermal_case(case)
    monkeypatch.setattr(actions,'enable_cooling',lambda _: {'status':'cooling_command_verified'})
    proposal=actions.create_proposal(uid,body,evidence,origin='thermal-basis-test')
    actions.decide(proposal['id'],actions.Decision(decision='approve',note='Test context change'))
    with actions.connection() as conn:
        conn.execute('UPDATE manufacturing_incidents SET review_revision=review_revision+1 WHERE id=%s',(uid,))
    plant['commands']['cooler_enable']=True
    monkeypatch.setattr(evidence_module,'live_state',lambda:deepcopy(plant))
    thermal.tick()
    saved=actions.list_proposals(uid)['items'][0]
    assert saved['status']=='unresolved'
    assert saved['result']['status']=='interrupted'
    assert '검토 기준' in saved['result']['reason']
