import test from 'node:test'
import assert from 'node:assert/strict'
import {startThermal,observeThermal,thermalStatus} from '../src/features/operations/thermalResponse.js'
const state=(seq,temp=72,target=72)=>({site:'AR-100',device:'reactor-line-01',seq,readings:{'TT-101':temp},commands:{temp_sp_c:target}})
test('a setpoint readback and duplicate scans never prove maintained temperature',()=>{
 let t=startThermal(state(1),0)
 t=observeThermal(t,state(1),30000)
 assert.equal(thermalStatus(t,30000).kind,'unknown')
 assert.equal(t.samples.length,1)
})
test('sustained fresh samples confirm only the training band; drift revokes it',()=>{
 let t=startThermal(state(1),0)
 for(let i=1;i<=15;i++)t=observeThermal(t,state(i+1,72.2),i*2000)
 assert.equal(thermalStatus(t,30000).kind,'held')
 t=observeThermal(t,state(17,74),32000)
 assert.equal(thermalStatus(t,32000).kind,'observing')
 assert.equal(t.withinSince,null)
})
test('a missing interval restarts the hold and stale data cannot claim success',()=>{
 let t=startThermal(state(1),0)
 t=observeThermal(t,state(20),40000)
 assert.equal(t.withinSince,40000)
 assert.equal(thermalStatus(t,40000).kind,'holding')
 assert.equal(thermalStatus(t,40000,true).kind,'unknown')
})
test('changed target, device and simulator restart interrupt the old observation',()=>{
 for(const sample of [state(2,72,75),{...state(2),device:'other'},state(0)]){
 const t=observeThermal(startThermal(state(1),0),sample,2000)
 assert.equal(thermalStatus(t,2000).kind,'interrupted')
 }
})
test('non-recovery times out, malformed temperatures never start, and history is bounded',()=>{
 assert.equal(startThermal(state(1,NaN),0),null)
 let t=startThermal(state(1,90),0)
 for(let i=1;i<=200;i++)t=observeThermal(t,state(i+1,90),i*2000)
 assert.equal(thermalStatus(t,400000).kind,'timeout')
 assert.equal(t.samples.length,180)
})
