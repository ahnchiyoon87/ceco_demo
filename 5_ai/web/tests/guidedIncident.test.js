import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { parse, compileScript } from '@vue/compiler-sfc'
import { createRenderer, h, nextTick, reactive } from 'vue'
const {descriptor}=parse(readFileSync(new URL('../src/features/operations/GuidedIncident.vue',import.meta.url),'utf8'))
const code=compileScript(descriptor,{id:'guided-review-test'}).content
  .replaceAll("from 'vue'",`from '${import.meta.resolve('vue')}'`)
  .replace("from './processState.js'",`from '${new URL('../src/features/operations/processState.js',import.meta.url).href}'`)
const {default:Guide}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))
Guide.render=()=>null
const renderer=createRenderer({createElement:()=>({}),createText:()=>({}),createComment:()=>({}),insert(){},remove(){},setText(){},setElementText(){},patchProp(){},parentNode:()=>null,nextSibling:()=>null})
function mount(values={}){
  const props=reactive(values);let view
  const app=renderer.createApp({render:()=>h(Guide,{...props,ref:x=>view=x})});app.mount({})
  return {props,app,get state(){return view.$.setupState}}
}
test('idle flow does not invent a detected incident or started analysis',async()=>{
 const g=mount()
 try{
  assert.ok(Object.values(g.state.state.nodes).every(x=>x==='waiting'))
  g.props.waiting=true;await nextTick()
  assert.equal(g.state.state.nodes.received,'active');assert.equal(g.state.state.nodes.investigate,'waiting')
  g.props.incidentStatus='received';await nextTick()
  assert.equal(g.state.title,'이상을 등록했습니다');assert.equal(g.state.state.nodes.investigate,'waiting')
 }finally{g.app.unmount()}
})
test('verification belongs to recovery and does not mean recovered until an explicit result',async()=>{
 const g=mount({incidentStatus:'executing',run:{status:'resuming'},proposal:{status:'executing',plan:{},result:{status:'executing_plan',plan_state:{phase:'verify',verify:{held_s:12}}}}})
 try{
  assert.equal(g.state.state.nodes.execute,'done');assert.equal(g.state.state.nodes.result,'active')
  assert.equal(g.state.title,'정상 상태가 유지되는지 확인합니다')
  g.props.proposal.result={status:'not_recovered',report:{outcome:'not_recovered'}}
  g.props.proposal.status='unresolved';await nextTick()
  assert.equal(g.state.state.nodes.result,'warning')
  assert.equal(g.state.title,'추가 확인이 필요합니다')
  g.props.proposal.status='resolved';g.props.proposal.result={status:'recovered',report:{outcome:'recovered'}};await nextTick()
  assert.equal(g.state.title,'정비를 마치고 정상으로 복구했습니다')
 }finally{g.app.unmount()}
})
test('expired approval is marked for attention and plain sensor readings retain units',()=>{
 const g=mount({incidentStatus:'awaiting_review',run:{status:'awaiting_review'},proposal:{status:'pending'},expired:true})
 try{
  assert.equal(g.state.state.nodes.review,'warning')
  assert.equal(g.state.title,'검토 기한이 지나 다시 분석해야 합니다')
  assert.equal(g.state.readingName('FT-103'),'냉각수 유량')
  assert.equal(g.state.readingUnit('FT-103'),'m³/h')
 }finally{g.app.unmount()}
})
