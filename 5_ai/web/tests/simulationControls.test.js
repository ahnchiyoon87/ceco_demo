import test from 'node:test'
import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
import {parse, compileScript} from '@vue/compiler-sfc'
import {createRenderer, h, nextTick} from 'vue'
const source=await readFile(new URL('../src/features/operations/SimulationControls.vue',import.meta.url),'utf8')
const {descriptor}=parse(source)
const code=compileScript(descriptor,{id:'simulation-controls'}).content.replace(/from 'vue'/g,`from '${import.meta.resolve('vue')}'`)
const {default:Controls}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))
Controls.render=()=>null
const renderer=createRenderer({createElement:()=>({}),createText:()=>({}),createComment:()=>({}),insert(){},remove(){},setText(){},setElementText(){},patchProp(){},parentNode:()=>null,nextSibling:()=>null})
const flush=async()=>{await new Promise(r=>setImmediate(r));await nextTick()}
const normal={active_faults:[],execution_active:false}
const response=data=>({ok:true,json:async()=>data})

test('rapid repeated clicks send one fault and notify the new exercise once',async()=>{
 const original=globalThis.fetch
 let view,finish,writes=0,started=0
 globalThis.fetch=async(url,options)=>{
  if(url.endsWith('/catalog'))return response({items:[{id:'strainer_fouling',title:'필터 막힘'}]})
  if(url.endsWith('/state'))return response(normal)
  assert.equal(options.headers['X-CECO-Portal'],'interactive')
  writes++;return new Promise(r=>{finish=()=>r(response({started:'strainer_fouling'}))})
 }
 const app=renderer.createApp({render:()=>h(Controls,{ref:x=>view=x,onStarted:()=>started++})})
 try{
  app.mount({});await flush()
  const s=view.$.setupState,first=s.start()
  await s.start();assert.equal(writes,1)
  finish();await first;assert.equal(started,1)
 }finally{app.unmount();globalThis.fetch=original}
})

test('an ambiguous write is not retried until the user explicitly checks state',async()=>{
 const original=globalThis.fetch
 let view,writes=0
 globalThis.fetch=async(url)=>{
  if(url.endsWith('/catalog'))return response({items:[{id:'strainer_fouling',title:'필터 막힘'}]})
  if(url.endsWith('/state'))return response(normal)
  writes++;throw new Error('timeout')
 }
 const app=renderer.createApp({render:()=>h(Controls,{ref:x=>view=x})})
 try{
  app.mount({});await flush()
  const s=view.$.setupState
  await s.start();assert.equal(s.uncertain,true)
  await s.refresh();await s.start();assert.equal(writes,1)
  await s.check();assert.equal(s.uncertain,false)
  await s.start();assert.equal(writes,2)
 }finally{app.unmount();globalThis.fetch=original}
})

test('approved execution blocks fault injection and reset',async()=>{
 const original=globalThis.fetch
 let view,writes=0
 globalThis.fetch=async(url,options)=>{
  if(options.method==='POST')writes++
  return response(url.endsWith('/catalog')?{items:[{id:'strainer_fouling',title:'필터 막힘'}]}:{...normal,execution_active:true})
 }
 const app=renderer.createApp({render:()=>h(Controls,{ref:x=>view=x})})
 try{
  app.mount({});await flush()
  await view.$.setupState.start();await view.$.setupState.reset();assert.equal(writes,0)
 }finally{app.unmount();globalThis.fetch=original}
})
