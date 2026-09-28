import test from 'node:test'
import assert from 'node:assert/strict'
import {injectionDisabledReason,findTrainingIncident} from '../src/features/operations/trainingScenarios.js'
const ready={site:'AR-100',device:'reactor-line-01',interlock:false,active_faults:{},agitator_run:true,cooler_enable:false}
test('unsupported, enabled cooling, interlock and existing faults cannot start thermal injection',()=>{
 assert.equal(injectionDisabledReason(ready,'thermal'),'')
 for(const patch of [{cooler_enable:null},{cooler_enable:true},{interlock:true},{active_faults:{heater_stuck:{}}}])
  assert.ok(injectionDisabledReason({...ready,...patch},'thermal'))
 assert.ok(injectionDisabledReason(null,'thermal'))
 assert.ok(injectionDisabledReason(ready,'thermal',true))
 assert.ok(injectionDisabledReason({...ready,agitator_run:false},'mixer'))
 assert.equal(injectionDisabledReason({...ready,agitator_run:false},'thermal'),'')
})
const started=1700000000000
const track={scenario:'thermal',started,site:'AR-100',device:'reactor-line-01'}
const alarm=(id,tag,offset=1000,site='AR-100')=>({id,last_ts:(started+offset)*1e6,alarm:{site,device:'reactor-line-01',tag},correlation_key:'mixer'})
test('thermal tracking selects only new TT-101 alarms at the same site/device',()=>{
 const correct=alarm('correct','TT-101')
 assert.equal(findTrainingIncident([alarm('wrong-tag','TT-102'),alarm('old','TT-101',-1000),alarm('wrong-site','TT-101',1000,'OTHER'),correct],track,started+2000),correct)
 assert.equal(findTrainingIncident([{...correct,alarm:{...correct.alarm,device:'other'}}],track,started+2000),null)
})
test('cleared/expired tracking never attaches later alarms, but retained incident remains accessible',()=>{
 const item=alarm('case','TT-101')
 assert.equal(findTrainingIncident([item],{...track,ended:'cleared'},started+2000),null)
 assert.equal(findTrainingIncident([item],track,started+1260001),null)
 assert.equal(findTrainingIncident([item],{...track,incidentId:'case',ended:'cleared'},started+1300000),item)
 assert.equal(findTrainingIncident([item],{...track,scenario:'missing'},started+2000),null)
})
