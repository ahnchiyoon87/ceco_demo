import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { parse, compileScript } from '@vue/compiler-sfc'
import { createRenderer, h, ref, nextTick } from 'vue'

// Exercise the real SFC setup through Vue reactivity, without pretending to
// verify DOM layout or browser interaction. Network promises are controlled.
const source = await readFile(new URL('../src/features/operations/IncidentReview.vue', import.meta.url), 'utf8')
const { descriptor } = parse(source)
const code = compileScript(descriptor, { id: 'incident-scope-test' }).content
  .replace(/from 'vue'/g, `from '${import.meta.resolve('vue')}'`)
  .replace("from './processState.js'", `from '${new URL('../src/features/operations/processState.js',import.meta.url).href}'`)
const { default: Review } = await import('data:text/javascript;base64,' + Buffer.from(code).toString('base64'))
Review.render = () => null
const renderer = createRenderer({
  createElement: () => ({}), createText: () => ({}), createComment: () => ({}),
  insert() {}, remove() {}, setText() {}, setElementText() {}, patchProp() {},
  parentNode: () => null, nextSibling: () => null,
})
const flush = async () => { await new Promise(resolve => setImmediate(resolve)); await nextTick() }
const deferred = () => { let resolve, reject; const promise = new Promise((a,b) => { resolve=a; reject=b }); return {promise,resolve,reject} }

test('expired proposal cannot send approval but can still be rejected',async()=>{
  const original=globalThis.fetch;let review;const posts=[]
  globalThis.fetch=async(url,options={})=>{if(options.method==='POST')posts.push(JSON.parse(options.body));return {ok:true,json:async()=>url.endsWith('model-status')?{configured:true}:{items:[]}}}
  const app=renderer.createApp({render:()=>h(Review,{incidentId:'expired-case',ref:x=>review=x})})
  try{
    app.mount({});await flush();const s=review.$.setupState
    const proposal={id:'p',origin:'ai-run:r:coding',expires_at:'2000-01-01T00:00:00Z'}
    s.note='현재 상태 재확인 필요'
    await s.decide(proposal,'approve');assert.equal(posts.length,0)
    await s.decide(proposal,'reject');assert.equal(posts.length,1);assert.equal(posts[0].decision,'reject')
  }finally{app.unmount();globalThis.fetch=original}
})

test('server progression never takes the reader away from the selected card', async()=>{
  const original=globalThis.fetch
  let review
  globalThis.fetch=async url=>({ok:true,json:async()=>url.endsWith('model-status')?{configured:true}:{items:[]}})
  const app=renderer.createApp({render:()=>h(Review,{incidentId:'stage-case',ref:x=>review=x})})
  try{
    app.mount({});await flush()
    const s=review.$.setupState
    s.runs=[{id:'r',status:'running'}];await flush()
    assert.equal(s.currentStage,'investigate')
    assert.equal(s.selectedStage,'received')
    s.selectStage('investigate')
    s.items=[{id:'p',origin:'ai-run:r:coding',status:'pending'}];await flush()
    assert.equal(s.currentStage,'review');assert.equal(s.selectedStage,'investigate')
    s.resumeFollow();assert.equal(s.selectedStage,'review')
    s.items[0].status='executing';await flush();assert.equal(s.currentStage,'execute');assert.equal(s.selectedStage,'review')
    s.items[0].result={status:'uncertain'};await flush()
    assert.equal(s.currentStage,'result')
  }finally{app.unmount();globalThis.fetch=original}
})

test('new analysis never inherits an older proposal in the process diagram', async () => {
  const original=globalThis.fetch
  let review
  globalThis.fetch=async url=>({ok:true,json:async()=>url.endsWith('model-status')?{configured:true}:{items:[]}})
  const app=renderer.createApp({render:()=>h(Review,{incidentId:'flow-case',ref:x=>review=x})})
  try{
    app.mount({});await flush()
    const state=review.$.setupState
    state.runs=[{id:'new-run',status:'running'}]
    state.items=[{id:'old',origin:'ai-run:old-run:openai:coding',status:'pending'}]
    assert.equal(state.flowProposal,undefined)
    state.items.unshift({id:'new',origin:'ai-run:new-run:openai:coding',status:'pending'})
    assert.equal(state.flowProposal.id,'new')
  }finally{app.unmount();globalThis.fetch=original}
})

test('transient polling failure retries reads without replaying an action', async () => {
  const originalFetch=globalThis.fetch, originalTimer=globalThis.setTimeout
  let failed=true, pending, delay, posts=0, review
  globalThis.setTimeout=(callback,ms)=>{pending=callback;delay=ms;return {fake:true}}
  globalThis.fetch=async(url,options={})=>{
    if(options.method==='POST')posts++
    if(failed)throw new Error('temporary disconnect')
    return {ok:true,json:async()=>url.endsWith('model-status')?{configured:true}:{items:[]}}
  }
  const app=renderer.createApp({render:()=>h(Review,{incidentId:'retry-case',ref:x=>review=x})})
  try{
    app.mount({});await flush()
    assert.equal(review.$.setupState.error,'temporary disconnect')
    assert.equal(delay,6000)
    failed=false;await pending();await flush()
    assert.equal(review.$.setupState.error,'')
    assert.equal(posts,0)
  }finally{app.unmount();globalThis.fetch=originalFetch;globalThis.setTimeout=originalTimer}
})

test('analysis follows incident state changes and does not submit for completed or unknown states', async () => {
  const originalFetch = globalThis.fetch
  let posts = 0, review
  globalThis.fetch = async (url, options={}) => {
    if (options.method === 'POST') posts++
    return {ok:true,json:async()=>url.endsWith('model-status')?{configured:true}:{items:[]}}
  }
  const status = ref('awaiting_maintenance')
  const app = renderer.createApp({render:()=>h(Review,{incidentId:'state-case',incidentStatus:status.value,ref:x=>{review=x}})})
  try {
    app.mount({}); await flush()
    for (const value of ['awaiting_maintenance','executing','closed','unknown']) {
      status.value=value; await flush()
      assert.equal(review.$.setupState.canAnalyze,false)
      await review.$.setupState.analyze()
    }
    assert.equal(posts,0)
    status.value='unresolved'; await flush()
    assert.equal(review.$.setupState.canAnalyze,true)
    await review.$.setupState.analyze()
    assert.equal(posts,1)
  } finally {app.unmount(); globalThis.fetch=originalFetch}
})

test('late old-incident failure cannot replace new incident error or release its request lock', async () => {
  const originalFetch = globalThis.fetch
  const posts = []
  globalThis.fetch = async (url, options={}) => {
    if (options.method === 'POST') {
      const pending = deferred(); posts.push({url,...pending}); return pending.promise
    }
    return {ok:true,json:async()=>url.endsWith('model-status')?{configured:true}:{items:[]}}
  }
  const incident = ref('incident-a')
  let review
  const app = renderer.createApp({render:()=>h(Review,{incidentId:incident.value,ref:instance=>{review=instance}})})
  try {
    app.mount({}); await flush()
    const state = review.$.setupState
    const old = state.analyze()
    incident.value = 'incident-b'; await flush()
    const current = state.analyze()
    assert.equal(posts.length,2)
    assert.match(posts[0].url,/incident-a\/analyze$/)
    assert.match(posts[1].url,/incident-b\/analyze$/)
    posts[0].reject(new Error('old incident failure')); await old
    assert.equal(state.error,'')
    assert.equal(state.submitting,true)
    await state.analyze()
    assert.equal(posts.length,2,'duplicate click must not send another POST')
    posts[1].reject(new Error('current failure')); await current
    assert.equal(state.error,'current failure')
    assert.equal(state.submitting,false)
  } finally { app.unmount(); globalThis.fetch=originalFetch }
})

test('late old recovery cannot clear new review note or publish updated event', async () => {
  const originalFetch=globalThis.fetch, pending=deferred()
  let updated=0, getCount=0, review
  globalThis.fetch=async (url,options={}) => {
    if(options.method==='POST') return pending.promise
    getCount++
    return {ok:true,json:async()=>url.endsWith('model-status')?{configured:true}:{items:[]}}
  }
  const incident=ref('incident-a')
  const app=renderer.createApp({render:()=>h(Review,{incidentId:incident.value,onUpdated:()=>updated++,ref:x=>{review=x}})})
  try {
    app.mount({}); await flush()
    const state=review.$.setupState
    const task=state.recover({id:'old-proposal'})
    incident.value='incident-b'; await flush()
    state.note='new incident review'
    const before=getCount
    pending.resolve({ok:true,json:async()=>({})}); await task
    assert.equal(state.note,'new incident review')
    assert.equal(getCount,before,'old request must not reload a different incident')
    assert.equal(updated,0)
  } finally { app.unmount(); globalThis.fetch=originalFetch }
})
