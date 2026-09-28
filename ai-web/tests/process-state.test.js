import test from 'node:test'
import assert from 'node:assert/strict'
import {processState} from '../src/features/operations/processState.js'
test('cooling command, unknown observation and held temperature stay distinct',()=>{
 const result={status:'cooling_command_verified',thermal_observation:{status:'observing'}}
 assert.equal(processState(null,{status:'observing',result}).nodes.result,'active')
 result.thermal_observation.status='unknown'
 assert.equal(processState(null,{status:'observing',result}).nodes.result,'warning')
 result.status='temperature_stable';result.thermal_observation.status='temperature_stable'
 const stable=processState(null,{status:'awaiting_maintenance',result})
 assert.equal(stable.nodes.result,'done');assert.match(stable.outcome,/정비 완료는 아님/)
})
test('no analysis does not pretend the agent started',()=>assert.equal(processState(null,null).nodes.investigate,'waiting'))
test('rejection bypasses equipment execution',()=>{const s=processState({status:'finished'},{status:'rejected',decision:{decision:'reject'}});assert.equal(s.nodes.execute,'waiting');assert.equal(s.branch,'rejected')})
test('persisted approval is not a successful result',()=>{const s=processState({status:'resuming'},{status:'executing',decision:{decision:'approve'}});assert.equal(s.nodes.execute,'active');assert.equal(s.nodes.result,'waiting')})
test('uncertain action is visibly different from verified stop',()=>{assert.equal(processState(null,{result:{status:'uncertain'}}).nodes.result,'warning');assert.equal(processState(null,{result:{status:'stop_verified'}}).nodes.result,'done')})
test('insufficient evidence does not enter approval',()=>{const s=processState({status:'needs_evidence'},null);assert.equal(s.nodes.review,'waiting');assert.equal(s.branch,'evidence')})
test('failed approval cannot appear as ordinary review or successful execution',()=>{
  const s=processState({status:'failed'},{status:'executing'})
  assert.equal(s.nodes.execute,'warning');assert.equal(s.nodes.result,'waiting')
  assert.match(s.outcome,/중단/)
})
test('resuming a review is not proof of approved equipment execution',()=>{
  const state=processState({status:'resuming'},{status:'pending'})
  assert.equal(state.nodes.review,'active')
  assert.equal(state.nodes.execute,'waiting')
  assert.match(state.outcome,/확인 전/)
})
test('a finished or unknown run without its proposal never shows a running investigation',()=>{
  for(const status of ['finished','awaiting_review','resuming','unexpected']){
    const state=processState({status},null)
    assert.notEqual(state.nodes.investigate,'active')
    assert.notEqual(state.nodes.execute,'active')
    assert.ok(Object.values(state.nodes).includes('warning'))
  }
})
