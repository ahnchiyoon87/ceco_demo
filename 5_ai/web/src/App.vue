<script setup>
import { ref, computed, nextTick, onMounted, onUnmounted, defineAsyncComponent } from 'vue'
import './manufacturing.css'
import './portal.css'
import IncidentReview from './features/operations/IncidentReview.vue'
import OperatorConsole from './features/operations/OperatorConsole.vue'
import KnowledgeReview from './features/ontology/KnowledgeReview.vue'
import KnowledgeCoverage from './features/ontology/KnowledgeCoverage.vue'
const ScadaLive=defineAsyncComponent(()=>import('./features/operations/ScadaLive.vue'))
const GuidedIncident=defineAsyncComponent(()=>import('./features/operations/GuidedIncident.vue'))
const KnowledgeMap=defineAsyncComponent(()=>import('./features/ontology/KnowledgeMap.vue'))
const IncidentTimeline=defineAsyncComponent(()=>import('./features/operations/IncidentTimeline.vue'))
const view=ref('operations')
const viewNames={operations:'운영 현황',ontology:'온톨로지',documents:'문서·지식',history:'처리 이력'}
const viewDescriptions={operations:'이상을 발생시키면 분석이 자동으로 이어집니다. 대응안을 검토하고 승인하면 정비와 복구를 확인합니다.',ontology:'설비·센서·문서가 어떻게 연결되어 있는지 확인합니다.',documents:'원본 자료와 관계 후보를 확인하고 검토한 지식을 게시합니다.',history:'이전 사건의 분석·검토·정비·복구 기록을 확인합니다.'}
let navigationGeneration=0
const controlsOpen=ref(false),incidents=ref([]),plant=ref(null),selected=ref(null),error=ref('')
const currentExercise=ref(null),faultActive=ref(false),timelineRefresh=ref(0)
const currentIncident=computed(()=>incidents.value.find(x=>x.id===selected.value?.id)||selected.value)
const time=value=>value?new Date(value).toLocaleString('ko-KR'):'—'
const statusLabel=value=>({received:'감지됨',awaiting_review:'승인 대기',executing:'정비 중',observing:'복구 확인 중',resolved:'복구 완료',unresolved:'추가 확인 필요',rejected:'반려',closed:'종료',awaiting_maintenance:'점검 대기'})[value]||'상태 확인 필요'
const incidentTitle=item=>item.correlation_key?.includes('thermal')?'냉각 계통 이상':item.correlation_key?.includes('mixer')?'교반기 이상':item.correlation_key?.includes('pressure')?'반응기 압력 이상':'설비 이상'
const list=computed(()=>incidents.value.filter(x=>x.has_limit_alarm!==false || x.status!=='received'))
const pendingCases=computed(()=>list.value.filter(x=>['received','awaiting_review','executing','observing','awaiting_maintenance'].includes(x.status)))
let timer,mounted=true,refreshing=false
async function api(path){const r=await fetch(path,{signal:AbortSignal.timeout(20000)});if(!r.ok)throw new Error(`연결 확인 필요 (${r.status})`);return r.json()}
async function refresh(){
 if(refreshing||!mounted)return
 refreshing=true
 try{
  const [cases,state]=await Promise.all([api('/api/operations/incidents'),api('/api/operations/plant')])
  if(!mounted)return
  incidents.value=cases.items;plant.value=state;error.value=''
  if(!selected.value){
   const exercise=currentExercise.value
   const candidates=pendingCases.value.filter(x=>!exercise?(x.last_ts||x.first_ts||0)/1e6>=Date.now()-120000:((x.last_ts||x.first_ts||0)/1e6>=exercise.since-1000&&(!exercise.group||(x.correlation_key||'').includes(exercise.group))))
   const candidate=candidates.sort((a,b)=>(b.last_ts||0)-(a.last_ts||0))[0]
   if(candidate)selected.value=candidate
  }
 }catch(e){if(mounted)error.value=e.message}
 finally{refreshing=false}
}
function scrollTop(){document.getElementById('app')?.scrollTo({top:0,behavior:'smooth'})}
function choose(item){selected.value=item}
function exerciseStarted(value){currentExercise.value=value;selected.value=null;refresh()}
function exerciseReset(){currentExercise.value={since:Date.now(),group:''};selected.value=null;refresh()}
function simulationState(state){faultActive.value=!!state.active_faults?.length}
async function reviewUpdated(){timelineRefresh.value++;await refresh()}
const knowledgeTab=ref('work'),knowledgeVisited=ref(false),structure=ref({classes:[],relationships:[]})
const graph=ref({nodes:[],edges:[]}),graphError=ref(''),graphLoading=ref(false),graphLoaded=ref(null)
let graphGeneration=0
async function loadGraph(){const generation=++graphGeneration;graphLoading.value=true;try{const [data,shape]=await Promise.all([api('/api/graph?limit=500'),api('/api/knowledge/structure')]);if(generation!==graphGeneration)return;graph.value=data;structure.value=shape;graphLoaded.value=new Date().toISOString();graphError.value=''}catch(e){if(generation===graphGeneration)graphError.value=e.message}finally{if(generation===graphGeneration)graphLoading.value=false}}
async function go(value){
 const generation=++navigationGeneration
 if(['ontology','documents'].includes(value)&&!knowledgeVisited.value){knowledgeVisited.value=true;loadGraph()}
 if(value==='ontology')knowledgeTab.value='graph'
 if(value==='documents')knowledgeTab.value='work'
 view.value=value
 await nextTick()
 if(generation===navigationGeneration&&mounted)scrollTop()
}
onMounted(()=>{refresh();timer=setInterval(refresh,2000)})
onUnmounted(()=>{mounted=false;clearInterval(timer);graphGeneration++;navigationGeneration++})
</script>

<template>
 <div class="portal-shell">
  <OperatorConsole :open="controlsOpen" @close="controlsOpen=false" />
  <aside class="portal-sidebar" aria-label="포털 메뉴"><a href="#" class="portal-brand" @click.prevent="go('operations')">ASSEMBLY<span>설비 운영</span></a><nav><button v-for="(label,key) in viewNames" :key="key" :class="{chosen:view===key}" :aria-current="view===key?'page':undefined" @click="go(key)">{{label}}</button></nav></aside>
  <div class="portal-frame">
  <header class="portal-header"><span class="portal-page-name">{{viewNames[view]}}</span><span class="portal-connection" :class="{offline:error||plant?.status!=='available'}"><i></i>{{error?'연결 확인 필요':plant?.status==='available'?'설비 연결됨':'연결 확인 중'}}</span><button @click="controlsOpen=true">설비 제어 패널</button></header>
  <main class="portal-content">
   <div class="portal-intro"><h1>{{view==='operations'?'설비와 이상 대응을 한눈에':viewNames[view]}}</h1><p>{{viewDescriptions[view]}}</p></div>
   <div v-if="error" class="portal-error" role="alert">{{error}} · 연결되면 자동으로 갱신합니다. <button @click="refresh">다시 연결</button></div>
   <div v-show="view==='operations'" class="portal-workspace">
    <ScadaLive @control="controlsOpen=true" @fault-started="exerciseStarted" @reset="exerciseReset" @simulation-state="simulationState" />
    <div class="portal-response"><IncidentReview v-if="selected" guided :incident-id="selected.id" :incident-status="currentIncident?.status" @updated="reviewUpdated" @control="controlsOpen=true" /><GuidedIncident v-else :waiting="faultActive" /></div>
   </div>
   <section v-show="view==='history'" class="portal-history mfg-panel"><div class="portal-history-layout"><div class="portal-case-list"><button v-for="item in list" :key="item.id" :class="{chosen:selected?.id===item.id}" @click="choose(item);go('operations')"><b>{{incidentTitle(item)}}</b><span>{{statusLabel(item.status)}}</span><small>{{time(item.created_at)}}</small></button><p v-if="!list.length">등록된 사건이 없습니다.</p></div><IncidentTimeline v-if="selected" :incident-id="selected.id" :revision="currentIncident?.revision" :refresh-token="timelineRefresh" /></div></section>
   <section v-show="['ontology','documents'].includes(view)" class="portal-knowledge mfg-panel">
   <nav v-if="view==='ontology'" class="knowledge-tabs" aria-label="온톨로지 화면"><button :aria-pressed="knowledgeTab==='graph'" @click="knowledgeTab='graph'">지식 지도</button><button :aria-pressed="knowledgeTab==='coverage'" @click="knowledgeTab='coverage'">연결 현황</button></nav>
   <section v-if="knowledgeVisited" class="mfg-panel knowledge-panel"><nav class="knowledge-tabs" aria-label="지식 스튜디오 화면"><button :aria-pressed="knowledgeTab==='work'" @click="knowledgeTab='work'">자료 · 후보 · 검토</button><button :aria-pressed="knowledgeTab==='graph'" @click="knowledgeTab='graph'">지식 지도</button><button :aria-pressed="knowledgeTab==='coverage'" @click="knowledgeTab='coverage'">연결 현황 · 누락</button></nav><KnowledgeCoverage v-show="knowledgeTab==='coverage'" :graph="graph" :loading="graphLoading" :error="graphError"/><KnowledgeReview v-show="knowledgeTab==='work'" @published="loadGraph" /><div v-show="knowledgeTab==='graph'"><KnowledgeMap :graph="graph" :loading="graphLoading" :error="graphError" :loaded-at="graphLoaded" @refresh="loadGraph"/><p class="panel-hint">게시된 설비 관계 · 원본 문서의 적용 범위와 버전을 함께 확인하세요.</p></div></section>
   </section>
  </main>
  </div>
 </div>
</template>
