import test from 'node:test'
import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
import {parse,compileScript} from '@vue/compiler-sfc'
import {createRenderer,h,nextTick} from 'vue'
const {descriptor}=parse(await readFile(new URL('../src/features/ontology/KnowledgeReview.vue',import.meta.url),'utf8'))
const code=compileScript(descriptor,{id:'knowledge-review-test'}).content
 .replace(/from 'vue'/g,`from '${import.meta.resolve('vue')}'`)
 .replace("import GraphEvidence from './GraphEvidence.vue'",'const GraphEvidence = {}')
const {default:Review}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))
Review.render=()=>null
const renderer=createRenderer({createElement:()=>({}),createText:()=>({}),createComment:()=>({}),insert(){},remove(){},setText(){},setElementText(){},patchProp(){},parentNode:()=>null,nextSibling:()=>null})

test('build stream is selection-scoped, preserves review errors, closes on completion and never starts work',async()=>{
 const originalFetch=globalThis.fetch,originalStream=globalThis.EventSource
 const streams=[],posts=[];let review
 class Stream{
  listeners={};closed=false
  constructor(url){this.url=url;streams.push(this)}
  addEventListener(kind,fn){this.listeners[kind]=fn}
  close(){this.closed=true}
  send(run){this.listeners.build({data:JSON.stringify(run)})}
 }
 globalThis.EventSource=Stream
 globalThis.fetch=async(url,options={})=>{
  if(options.method==='POST')posts.push(url)
  return{ok:true,json:async()=>url.includes('/builds/')?{id:url.split('/').at(-1),status:'running',trace:[]}:{uploads:[],items:[]}}
 }
 const app=renderer.createApp({render:()=>h(Review,{ref:x=>review=x})})
 try{
  app.mount({});await nextTick();await new Promise(r=>setImmediate(r))
  const s=review.$.setupState;s.error='기존 후보 오류'
  await s.openBuild({id:'a'});const a=streams.at(-1)
  a.send({id:'a',status:'running',trace:[{tool:'read_registered_source'}]})
  assert.equal(s.buildConnection,'stream');assert.equal(s.buildRun.trace.length,1);assert.equal(s.error,'기존 후보 오류')
  await s.openBuild({id:'b'});const b=streams.at(-1)
  assert.equal(a.closed,true)
  a.send({id:'a',status:'candidate'});assert.equal(s.buildRun.id,'b')
  b.send({id:'b',status:'candidate',result:{summary:'후보 준비'}})
  assert.equal(s.buildConnection,'complete');assert.equal(b.closed,true);assert.equal(posts.length,0)
  await s.openBuild({id:'c'});const c=streams.at(-1);c.onerror()
  assert.equal(s.buildConnection,'fallback');assert.equal(c.closed,true)
  await s.openBuild({id:'d'});const d=streams.at(-1)
  s.buildOffline();assert.equal(d.closed,true);assert.equal(s.buildConnection,'disconnected')
  s.buildOnline();await new Promise(r=>setImmediate(r))
  assert.equal(streams.at(-1).url,'/api/knowledge/builds/d/stream')
  assert.notEqual(streams.at(-1),d);assert.equal(posts.length,0)
 }finally{app.unmount();globalThis.fetch=originalFetch;globalThis.EventSource=originalStream}
})

test('failed candidate replacement preserves the existing review; a successful replacement resets consent',async()=>{
 const original=globalThis.fetch
 let review,failPrepare=true
 const old={nodes:[{id:'old',class:'Sensor',properties:{name:'old'}}],relationships:[]}
 const replacement={nodes:[{id:'new',class:'Sensor',properties:{name:'new'}}],relationships:[]}
 globalThis.fetch=async(url)=>({ok:!(url.endsWith('/prepare')&&failPrepare),status:503,json:async()=>url.endsWith('/prepare')?{detail:'test offline'}:url.endsWith('/preview')?{batch:replacement,sha256:'new-hash'}:{uploads:[],items:[]}})
 const app=renderer.createApp({render:()=>h(Review,{ref:x=>review=x})})
 try{
  app.mount({});await nextTick();await new Promise(r=>setImmediate(r))
  const s=review.$.setupState
  s.candidate=old;s.preview={sha256:'old-hash'};s.selected=old.nodes[0];s.note='기존 검토 의견';s.acknowledged=true
  await s.readCandidate({target:{files:[{name:'bad.json',size:1,text:async()=>'{'}],value:'bad'}})
  assert.match(s.error,/JSON 형식이 올바르지/)
  assert.equal(s.candidate.nodes[0].id,'old');assert.equal(s.preview.sha256,'old-hash');assert.equal(s.note,'기존 검토 의견')
  await s.prepareSources()
  assert.equal(s.candidate.nodes[0].id,'old');assert.match(s.error,/기존 검토 후보는 유지/)
  await s.readCandidate({target:{files:[{name:'valid.json',size:2,text:async()=>'{}'}],value:'valid'}})
  assert.equal(s.candidate.nodes[0].id,'new');assert.equal(s.acknowledged,false);assert.equal(s.note,'')
  globalThis.fetch=async()=>{throw new TypeError('Failed to fetch')}
  await s.prepareSources()
  assert.match(s.error,/서버에 연결하지 못했습니다/)
  assert.match(s.error,/기존 검토 후보는 유지/)
  assert.equal(s.candidate.nodes[0].id,'new')
 }finally{app.unmount();globalThis.fetch=original}
})

test('duplicate candidate relation is rejected locally without publishing or validating new data',async()=>{
 const original=globalThis.fetch;let review;const posts=[]
 globalThis.fetch=async(url,options={})=>{if(options.method==='POST')posts.push(url);return{ok:true,json:async()=>({uploads:[],items:[]})}}
 const app=renderer.createApp({render:()=>h(Review,{ref:x=>review=x})})
 try{
  app.mount({});await nextTick()
  const s=review.$.setupState
  s.candidate={nodes:[],relationships:[{from_id:'a',to_id:'b',type:'HAS_SENSOR'}]}
  s.relationFrom='a';s.relationTo='b';s.relationType='HAS_SENSOR';s.relationReason='이미 연결된 센서'
  await s.addRelation()
  assert.match(s.error,/이미 있습니다/);assert.equal(s.candidate.relationships.length,1);assert.equal(posts.length,0)
 }finally{app.unmount();globalThis.fetch=original}
})

test('opening a persisted model candidate reviews the browser payload before enabling consent',async()=>{
 const original=globalThis.fetch;let review;const posts=[]
 const batch={nodes:[{id:'sensor',class:'Sensor',properties:{limit:10}}],relationships:[]}
 globalThis.fetch=async(url,options={})=>{
  if(options.method==='POST')posts.push({url,body:JSON.parse(options.body)})
  return{ok:true,json:async()=>url.endsWith('/preview')?{batch,sha256:'wire-digest'}:{uploads:[],items:[]}}
 }
 const app=renderer.createApp({render:()=>h(Review,{ref:x=>review=x})})
 try{
  app.mount({});await nextTick();await new Promise(r=>setImmediate(r))
  const s=review.$.setupState
  s.buildRun={id:'candidate-run',result:{batch,sha256:'python-float-digest',summary:'Model summary'}}
  s.acknowledged=true;s.note='previous consent'
  await s.useBuildCandidate()
  assert.equal(s.preview.sha256,'wire-digest');assert.equal(s.preview.summary,'Model summary')
  assert.equal(s.buildRun.result.sha256,'python-float-digest')
  assert.equal(s.acknowledged,false);assert.equal(s.note,'');assert.equal(s.workspace,'review')
  assert.deepEqual(posts,[{url:'/api/knowledge/preview',body:batch}])
 }finally{app.unmount();globalThis.fetch=original}
})
