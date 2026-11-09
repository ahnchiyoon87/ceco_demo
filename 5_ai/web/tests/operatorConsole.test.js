import test from 'node:test'
import assert from 'node:assert/strict'
import {readFile} from 'node:fs/promises'
import {parse,compileScript} from '@vue/compiler-sfc'
import {createRenderer,h,ref,nextTick} from 'vue'
const source=await readFile(new URL('../src/features/operations/OperatorConsole.vue',import.meta.url),'utf8')
const {descriptor}=parse(source)
const code=compileScript(descriptor,{id:'operator-console'}).content.replace(/from 'vue'/g,`from '${import.meta.resolve('vue')}'`)
const {default:Console}=await import('data:text/javascript;base64,'+Buffer.from(code).toString('base64'))
Console.render=()=>null
const renderer=createRenderer({createElement:()=>({}),createText:()=>({}),createComment:()=>({}),insert(){},remove(){},setText(){},setElementText(){},patchProp(){},parentNode:()=>null,nextSibling:()=>null})
const flush=async()=>{await new Promise(r=>setImmediate(r));await nextTick()}
const user={username:'operator',groups:2,token:'test-session'}
test('each open renews an ordinary operator session before loading the iframe',async()=>{
 const original=globalThis.fetch,storage=globalThis.sessionStorage
 let view,writes=0,stored
 const open=ref(false)
 globalThis.sessionStorage={setItem:(key,value)=>{assert.equal(key,'currentUser');stored=JSON.parse(value)}}
 globalThis.fetch=async(url,options)=>{assert.equal(url,'/simulation/operator-session');assert.equal(options.method,'POST');writes++;return {ok:true,json:async()=>({user})}}
 const app=renderer.createApp({render:()=>h(Console,{ref:x=>view=x,open:open.value})})
 try{
  app.mount({});await flush();assert.equal(writes,0)
  open.value=true;await flush();assert.equal(view.$.setupState.ready,true);assert.deepEqual(stored,user)
  open.value=false;await flush();assert.equal(view.$.setupState.ready,false)
  open.value=true;await flush();assert.equal(writes,2)
 }finally{app.unmount();globalThis.fetch=original;globalThis.sessionStorage=storage}
})
test('failure stays in portal with explicit retry; a closed request cannot install a session',async()=>{
 const original=globalThis.fetch,storage=globalThis.sessionStorage
 let view,writes=0,resolve
 const open=ref(false)
 globalThis.sessionStorage={setItem:()=>assert.fail('closed request installed a session')}
 globalThis.fetch=async()=>{writes++;if(writes===1)return {ok:false,json:async()=>({detail:'연결 실패'})};return new Promise(r=>resolve=r)}
 const app=renderer.createApp({render:()=>h(Console,{ref:x=>view=x,open:open.value})})
 try{
  app.mount({});open.value=true;await flush()
  const state=view.$.setupState
  assert.equal(state.error,'연결 실패');assert.equal(state.ready,false);await flush();assert.equal(writes,1)
  const pending=state.connect();open.value=false;await flush()
  resolve({ok:true,json:async()=>({user})});await pending;assert.equal(state.ready,false)
 }finally{app.unmount();globalThis.fetch=original;globalThis.sessionStorage=storage}
})
