import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { parse, compileScript } from '@vue/compiler-sfc'
import { createRenderer, h, ref, nextTick } from 'vue'

const renderer = createRenderer({ createElement:()=>({}),createText:()=>({}),createComment:()=>({}),insert(){},remove(){},setText(){},setElementText(){},patchProp(){},parentNode:()=>null,nextSibling:()=>null })
const flush = async () => { await new Promise(r => setImmediate(r)); await nextTick() }
async function component(name) {
  const source = await readFile(new URL(`../src/features/operations/${name}.vue`, import.meta.url), 'utf8')
  const { descriptor } = parse(source)
  const code = compileScript(descriptor, {id:name}).content.replace(/from 'vue'/g, `from '${import.meta.resolve('vue')}'`).replace(/import (ExecutionTrace|PlantControls) from '.\/(ExecutionTrace|PlantControls).vue'/g, 'const $1 = {}')
  const {default: C} = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))
  C.render = () => null
  return C
}
const Live = await component('ScadaLive'), Trace = await component('ExecutionTrace')
const Activity = await component('DashboardActivity')
const Simulation = await component('SimulationControls')

test('simulation restores only the saved incident from fresh server data',async()=>{
  const originalFetch=globalThis.fetch, originalStorage=globalThis.sessionStorage
  const saved={started:Date.now()-10000,incidentId:'saved'}
  globalThis.sessionStorage={getItem:()=>JSON.stringify(saved),setItem(){}}
  globalThis.fetch=async()=>({ok:true,json:async()=>({active_faults:{}})})
  let view,selected
  const incidents=ref([])
  const app=renderer.createApp({render:()=>h(Simulation,{incidents:incidents.value,onIncident:item=>selected=item,ref:x=>view=x})})
  try{
    app.mount({});await flush()
    assert.equal(view.$.setupState.tracked,null)
    incidents.value=[{id:'other',correlation_key:'mixer',last_ts:Date.now()*1000000}];await flush()
    assert.equal(selected,undefined)
    incidents.value.push({id:'saved',status:'awaiting_maintenance'});await flush()
    assert.equal(selected.id,'saved')
    assert.equal(selected.status,'awaiting_maintenance')
  }finally{app.unmount();globalThis.fetch=originalFetch;globalThis.sessionStorage=originalStorage}
})

test('dashboard clears loading when incidents disappear and ignores the late response', async () => {
  const original = globalThis.fetch
  let finish, view
  globalThis.fetch = () => new Promise(resolve => { finish=resolve })
  const incidents=ref([{id:'gone'}])
  const app=renderer.createApp({render:()=>h(Activity,{incidents:incidents.value,ref:x=>view=x})})
  try {
    app.mount({}); await flush()
    assert.equal(view.$.setupState.loading,true)
    incidents.value=[]; await flush()
    assert.equal(view.$.setupState.loading,false)
    finish({ok:true,json:async()=>({items:[{id:'stale',status:'running'}]})}); await flush()
    assert.equal(view.$.setupState.run,null)
    assert.equal(view.$.setupState.loading,false)
  } finally {app.unmount();globalThis.fetch=original}
})

test('dashboard distinguishes unavailable analysis from an empty successful result', async () => {
  const original=globalThis.fetch
  let fail=true,view
  globalThis.fetch=async()=>({ok:!fail,status:503,json:async()=>({items:[]})})
  const app=renderer.createApp({render:()=>h(Activity,{incidents:[{id:'one'}],ref:x=>view=x})})
  try {
    app.mount({}); await flush()
    const state=view.$.setupState, unavailable=state.emptyMessage
    assert.ok(state.error)
    fail=false; await state.load()
    assert.equal(state.error,'')
    assert.notEqual(state.emptyMessage,unavailable)
  } finally {app.unmount();globalThis.fetch=original}
})

test('SCADA marks repeated scans stale, keeps values on disconnect and bounds samples', async () => {
  const original = globalThis.fetch
  let seq = 1, fail = false, view
  globalThis.fetch = async () => { if(fail) throw new Error('offline'); return {ok:true,json:async()=>({status:'available',seq,readings:{'TT-101':seq},commands:{pump_run:true}})} }
  const app = renderer.createApp({render:()=>h(Live,{ref:x=>view=x})})
  try {
    app.mount({}); await flush()
    const s=view.$.setupState
    assert.equal(s.stale,false); assert.equal(s.running('pump_run'),true)
    s.now = s.lastChanged + 16000
    assert.equal(s.stale,true); assert.equal(s.running('pump_run'),false)
    await s.load(); assert.equal(s.stale,true,'same scan must not refresh freshness')
    s.now = Date.now()
    for(seq=2;seq<60;seq++) await s.load()
    assert.equal(s.history['TT-101'].length,45)
    fail=true; await s.load()
    assert.equal(s.stale,true); assert.equal(s.value('TT-101'),'59.00')
  } finally { app.unmount(); globalThis.fetch=original }
})

test('trace excludes late previous run and preserves paired call status', async () => {
  const original=globalThis.fetch
  let resolveOld, view
  globalThis.fetch=async url=>url.includes('/old/') ? new Promise(resolve=>{resolveOld=resolve}) : {ok:true,json:async()=>({items:[
    {id:1,kind:'agent_tool_started',created_at:'2026-09-23T00:00:00Z',payload:{call_id:'one',tool:'alarm'}},
    {id:2,kind:'agent_tool_result',created_at:'2026-09-23T00:00:01Z',payload:{call_id:'one',tool:'alarm',duration_ms:1000,result:{revision:2}}}
  ],truncated:false})}
  const run=ref({id:'old',status:'running'})
  const app=renderer.createApp({render:()=>h(Trace,{run:run.value,ref:x=>view=x})})
  try {
    app.mount({}); await flush(); run.value={id:'new',status:'finished'}; await flush()
    assert.equal(view.$.setupState.calls.length,1)
    assert.equal(view.$.setupState.calls[0].state,'complete')
    resolveOld({ok:true,json:async()=>({items:[],truncated:false})}); await flush()
    assert.equal(view.$.setupState.calls[0].result.revision,2)
  } finally {app.unmount();globalThis.fetch=original}
})

test('SSE supersedes a delayed HTTP snapshot and an old connection cannot break the new one',async()=>{
 const originalFetch=globalThis.fetch, originalSource=globalThis.EventSource
 const streams=[];let finish,view
 class Source{
  constructor(){this.listeners={};streams.push(this)}
  addEventListener(name,fn){this.listeners[name]=fn}
  close(){this.closed=true}
  trace(run,items){this.listeners.trace({data:JSON.stringify({run,items,truncated:false})})}
 }
 globalThis.EventSource=Source
 globalThis.fetch=async()=>new Promise(resolve=>finish=resolve)
 const run=ref({id:'one',status:'running'})
 const app=renderer.createApp({render:()=>h(Trace,{run:run.value,ref:x=>view=x})})
 try{
  app.mount({});await flush();const initialHttp=finish
  streams[0].trace(run.value,[{id:2,kind:'agent_model_output',payload:{}}])
  initialHttp({ok:true,json:async()=>({items:[],truncated:false})});await flush()
  assert.equal(view.$.setupState.events.length,1)
  run.value={id:'two',status:'running'};await flush()
  assert.equal(streams[0].closed,true)
  streams[1].trace(run.value,[]);streams[0].onerror();await flush()
  assert.equal(view.$.setupState.streaming,true)
  assert.equal(view.$.setupState.error,'')
  streams[1].listeners.trace({data:'bad json'});await flush()
  assert.equal(view.$.setupState.streaming,false)
  assert.match(view.$.setupState.error,/형식/)
 }finally{app.unmount();globalThis.fetch=originalFetch;globalThis.EventSource=originalSource}
})
