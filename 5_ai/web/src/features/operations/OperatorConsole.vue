<script setup>
import {ref,watch,nextTick,onBeforeUnmount} from 'vue'
const props=defineProps({open:Boolean})
const emit=defineEmits(['close'])
const dialog=ref(null)
const ready=ref(false),loading=ref(false),error=ref('')
let request=null
async function connect(){
  if(loading.value)return
  const active=new AbortController()
  request=active
  loading.value=true;ready.value=false;error.value=''
  const timeout=setTimeout(()=>active.abort(),15000)
  try{
    const response=await fetch('/simulation/operator-session',{
      method:'POST',headers:{'Content-Type':'application/json','X-CECO-Portal':'interactive'},
      body:'{}',signal:active.signal,cache:'no-store'
    })
    const result=await response.json()
    if(!response.ok)throw new Error(result.detail||'제어 패널에 연결하지 못했습니다.')
    if(!result.user?.token||result.user.username!=='operator'||result.user.groups!==2)throw new Error('운전원 연결을 확인하지 못했습니다.')
    if(request!==active||!props.open)return
    // The same-origin iframe shares this tab's session storage. FUXA reads its
    // ordinary operator token at startup; no browser credentials are required.
    sessionStorage.setItem('currentUser',JSON.stringify(result.user))
    ready.value=true
  }catch(exc){
    if(request===active&&props.open)error.value=exc.name==='AbortError'?'연결 시간이 길어지고 있습니다. 다시 연결해 주세요.':exc.message
  }finally{
    clearTimeout(timeout)
    if(request===active){request=null;loading.value=false}
  }
}
function disconnect(){request?.abort();request=null;loading.value=false;ready.value=false;error.value=''}
watch(()=>props.open,async value=>{
  await nextTick()
  if(value){if(!dialog.value?.open)dialog.value?.showModal();connect()}
  else{disconnect();dialog.value?.close()}
})
onBeforeUnmount(disconnect)
</script>
<template>
  <dialog ref="dialog" class="operator-console" aria-labelledby="operator-title" @cancel="emit('close')">
    <header><div><h2 id="operator-title">설비 제어 패널</h2><p>운전원으로 자동 연결됩니다. 값을 조절한 뒤 설비 상태에서 변화를 확인하세요.</p></div><button autofocus @click="emit('close')">닫고 설비로 돌아가기</button></header>
    <iframe v-if="open&&ready" src="/operator/" title="가상 설비 제어 화면"></iframe>
    <div v-else class="connection" :aria-busy="loading"><p v-if="loading" role="status">설비 제어 패널에 연결하고 있습니다…</p><template v-else-if="error"><p role="alert">{{error}}</p><button @click="connect">다시 연결</button></template></div>
  </dialog>
</template>
<style scoped>
.operator-console{width:calc(100vw - 40px);max-width:1800px;height:calc(100vh - 40px);max-height:none;border:1px solid #355969;border-radius:16px;padding:0;background:#102b39;color:#e2eef4;overflow:hidden}
.operator-console::backdrop{background:#061624cc}
.operator-console[open]{display:flex;flex-direction:column}
.operator-console header{display:flex;align-items:center;justify-content:space-between;padding:16px 22px;gap:20px;flex-shrink:0}
.operator-console h2{font-size:20px;margin:0}
.operator-console p{font-size:var(--ui-font-caption);color:#b9cedb;margin:7px 0 0}
.operator-console button{background:#e4f5ef;color:#165b4e;border:0;border-radius:8px;padding:12px;white-space:nowrap;cursor:pointer}
.operator-console iframe{width:100%;flex:1;min-height:0;border:0;background:#0e1b29}
.connection{flex:1;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:18px}
@media(max-width:650px){.operator-console{width:100vw;height:100dvh;border-radius:0}.operator-console header{flex-wrap:wrap}}
</style>
