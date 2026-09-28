<script setup>
import { ref, computed, onMounted, onUnmounted, defineAsyncComponent } from 'vue'
const OntologyGraphPanel = defineAsyncComponent(() => import('./features/ontology/OntologyGraphPanel.vue'))
import './manufacturing.css'
import ObservationComparison from './features/operations/ObservationComparison.vue'
import KnowledgeReview from './features/ontology/KnowledgeReview.vue'
import IncidentReview from './features/operations/IncidentReview.vue'
import IncidentTimeline from './features/operations/IncidentTimeline.vue'
import { graphContext } from './features/ontology/graphContext.js'

const evidencePanel=ref(null)
function jumpToEvidence(selector){evidencePanel.value?.querySelector(selector)?.scrollIntoView({block:'start',behavior:'instant'})}
const page=ref('operations'), incidents=ref([]), plant=ref(null), selected=ref(null), evidence=ref(null), error=ref(''), busy=ref(false)
const structure=ref({classes:[],relationships:[]}), graphFilter=ref('')
const graph=ref({nodes:[],edges:[]}), graphError=ref(''), loaded=ref(null)
const graphLoading=ref(false), graphLoaded=ref(null)
let graphGeneration=0
const model=ref(null), modelError=ref('')
const statusLabels={received:'접수 · 근거 확인',awaiting_review:'대응안 검토 대기',executing:'조치 실행 중',awaiting_maintenance:'점검 대기',unresolved:'미해결 · 재검토 필요',closed:'종결',rejected:'반려'}
const statusLabel=value=>statusLabels[value]||'상태 확인 필요'
const currentIncident=computed(()=>list.value.find(item=>item.id===selected.value?.id)||selected.value)
const stage=computed(()=>({received:1,awaiting_review:2,executing:3,awaiting_maintenance:4,closed:4}[currentIncident.value?.status]??null))
let timer, selectionGeneration=0
const list=computed(()=>incidents.value)
const totalSignals=computed(()=>list.value.reduce((sum,x)=>sum+(x.alarm_count||1),0))
const time=value=>value?new Date(value).toLocaleTimeString('ko-KR',{hour:'2-digit',minute:'2-digit',second:'2-digit'}):'—'
async function api(path){const r=await fetch(path,{signal:AbortSignal.timeout(20000)});if(!r.ok)throw new Error(`요청 실패 (${r.status})`);return r.json()}
async function refreshModel(){try{model.value=await api('/api/operations/model-status');modelError.value=''}catch(e){model.value=null;modelError.value=e.message}}
async function refresh(){await Promise.all([refreshModel(),(async()=>{try{const [cases,state]=await Promise.all([api('/api/operations/incidents'),api('/api/operations/plant')]);incidents.value=cases.items;plant.value=state;loaded.value=new Date().toISOString();error.value=''}catch(e){error.value=e.message}})()])}
async function choose(item){const generation=++selectionGeneration;selected.value=item;evidence.value=null;busy.value=true;error.value='';try{const data=await api(`/api/operations/incidents/${item.id}/evidence`);if(generation===selectionGeneration)evidence.value=data}catch(e){if(generation===selectionGeneration)error.value=e.message}finally{if(generation===selectionGeneration)busy.value=false}}
async function loadGraph(){const generation=++graphGeneration;graphLoading.value=true;try{const [data,shape]=await Promise.all([api('/api/graph?limit=250'),api('/api/knowledge/structure')]);if(generation!==graphGeneration)return;graph.value=data;structure.value=shape;graphLoaded.value=new Date().toISOString();graphError.value=''}catch(e){if(generation===graphGeneration)graphError.value=e.message}finally{if(generation===graphGeneration)graphLoading.value=false}}
const visibleGraph=computed(()=>graphContext(graph.value,graphFilter.value))
function go(value){page.value=value;if(value==='knowledge')loadGraph()}
onMounted(async()=>{await refresh();if(list.value.length)choose(list.value.find(x=>x.correlation_key?.includes('mixer'))||list.value[0]);timer=setInterval(refresh,10000)})
onUnmounted(()=>{clearInterval(timer);selectionGeneration++})
</script>

<template>
  <div class="mfg-app">
    <aside class="mfg-nav">
      <a class="mfg-brand" href="#" @click.prevent="go('operations')"><span class="mfg-mark">a<span>·</span></span><span>ASSEMBLY<small>MANUFACTURING INTELLIGENCE</small></span></a>
      <p class="nav-caption">WORKSPACE</p>
      <button :class="{chosen:page==='operations'}" @click="go('operations')"><span>▦</span>운영 워크스페이스</button>
      <button :class="{chosen:page==='knowledge'}" @click="go('knowledge')"><span>⌘</span>설비 지식 스튜디오</button>
      <div class="nav-bottom"><span class="simulation-dot"></span> AR-100 시뮬레이션<small>실제 센서 파이프라인 연결<br>가상 반응기 공정 · 교육용</small></div>
    </aside>
    <div class="mfg-main">
      <header class="mfg-top"><span>제조 운영 <b>/</b> {{page==='knowledge'?'지식 스튜디오':'이상 대응'}}</span><span class="connection" :class="{offline:error||plant?.status!=='available'}"><i></i>{{error?'연결 확인 필요':plant?.status==='available'?'공정 연결됨':'연결 확인 중'}}</span><button @click="refresh">↻ 새로고침</button></header>
      <main>
        <div class="page-heading"><div><p class="eyebrow">{{page==='knowledge'?'CONNECTED KNOWLEDGE':'OPERATIONS / AR-100'}}</p><h1>{{page==='knowledge'?'설비의 맥락을 연결합니다.':'알람 너머, 다음 행동까지.'}}</h1><p>{{page==='knowledge'?'설비·센서·문서의 관계를 탐색하고 판단 근거를 확인하세요.':'관련 신호를 하나의 사건으로 모으고, 데이터와 절차를 함께 확인하세요.'}}</p></div><span class="heading-note">{{loaded?time(loaded)+' 갱신':'데이터 불러오는 중'}}<small>10초마다 공정 상태 갱신</small></span></div>
        <div v-if="error" class="mfg-error" role="alert">{{error}} · 이전 표시값은 최신 상태가 아닐 수 있습니다. <button @click="refresh">다시 연결</button></div>
        <template v-if="page==='operations'">
          <section class="metric-grid"><article><span>표시 중인 대응 사건</span><strong>{{list.length}}<small>건</small></strong><p>최근 100건 조회 · 사건별 처리 상태 확인</p></article><article><span>연결된 원본 알람</span><strong>{{totalSignals}}<small>건</small></strong><p>묶인 신호도 원본 이력은 보존</p></article><article><span>교반기 상태</span><strong class="state-text">{{plant?.status==='available'?(plant.commands.agitator_run?'운전 중':'정지'):'확인 불가'}}</strong><p>기동 상태 · 정비 완료 여부와 구분</p></article><article class="ai-status"><span>AI 업무도우미</span><strong class="state-text">{{modelError?'설정 확인 실패':model?.configured?'모델 설정됨':model?'모델 연결 대기':'설정 확인 중'}}</strong><p>{{modelError||model?.note||'모델 설정을 조회하고 있습니다.'}}</p></article></section>
          <section class="workspace-grid">
            <article class="mfg-panel incident-panel"><div class="panel-heading"><h2>대응 사건</h2><span class="count-chip">{{list.length}}</span></div><p class="panel-hint">반복 신호를 묶어 맥락을 확인합니다.</p><div class="incident-list"><button v-for="item in list" :key="item.id" class="incident-item" :class="{selected:selected?.id===item.id}" @click="choose(item)"><span class="incident-top"><b>{{item.correlation_key?.includes('mixer')?'교반기 전류·진동 이상':item.alarm.alert_type==='ML_AUTOENCODER'?'다변량 이상 신호':item.alarm.tag+' 이상 신호'}}</b><span class="severity">{{item.alarm.severity}}</span></span><span class="incident-sub">{{item.device}} · {{item.alarm_count||1}}개 알람</span><span class="incident-meta">{{time(item.created_at)}}<span>{{statusLabel(item.status)}} →</span></span></button><p v-if="!list.length" class="empty-state">접수된 사건이 없습니다.<br>SCADA 알람 수신을 기다리고 있습니다.</p></div></article>
            <article ref="evidencePanel" class="mfg-panel evidence-panel"><template v-if="selected"><div class="panel-heading"><div><p class="eyebrow">INCIDENT EVIDENCE</p><h2>{{evidence?.graph.assets?.[0]?.name||selected.alarm.tag}} · 판단 근거</h2></div><span class="count-chip">검토 {{evidence?.revision||selected.review_revision}}</span></div><nav class="evidence-jumps" aria-label="사건 상세 바로가기"><button :disabled="busy||!evidence" @click="jumpToEvidence('.observation-comparison')">현재 관측</button><button @click="jumpToEvidence('.review-section')">대응안 검토</button><button @click="jumpToEvidence('.incident-timeline')">처리 이력</button></nav><div class="workflow-steps"><span v-for="(label,index) in ['01 접수','02 근거 확인','03 대응안','04 검토·조치']" :key="label" :class="{done:stage!==null&&index<stage,current:index===stage}">{{label}}</span></div><p class="panel-hint" role="status">현재 상태: {{statusLabel(currentIncident?.status)}} · 단계 표시는 저장된 업무 상태 기준입니다.</p><div v-if="busy" class="loading-state" role="status"><i></i>설비 관계와 센서 이력을 모으고 있습니다.</div><template v-else-if="evidence"><div class="evidence-summary"><span class="summary-icon">↗</span><div><b>확인된 근거부터 판단합니다.</b><p>설비 {{evidence.graph.assets?.length||0}}개 · 관련 문서 {{evidence.graph.documents?.length||0}}개 · 관측 {{evidence.history.rows.length}}건</p></div></div><div v-if="evidence.graph.status!=='available'||evidence.history.status!=='available'" class="mfg-error">일부 근거를 확인하지 못했습니다. {{evidence.graph.error}} {{evidence.history.error}}</div><h3>관측 이력 <small>{{evidence.history.source||'조회 결과 없음'}}</small></h3><p class="panel-hint">{{evidence.window_capped?'긴 사건의 첫 5분 구간입니다.':'사건 발생 전후 구간입니다.'}} {{evidence.history.truncated?'표시 한도에 도달했습니다.':''}}</p><ObservationComparison :evidence="evidence" @refresh="choose(selected)" /><div class="sensor-chips"><span v-for="s in evidence.graph.sensors" :key="s.tag">{{s.tag}} <small>{{s.unit}}</small></span></div><div class="observation-table"><table><thead><tr><th>측정 시각</th><th>센서</th><th>값</th><th>품질</th></tr></thead><tbody><tr v-for="(row,index) in evidence.history.rows.slice(-12)" :key="index"><td>{{time(row.time)}}</td><td>{{row.tag}}</td><td>{{row.value.toFixed(3)}}</td><td>{{row.quality}}</td></tr></tbody></table></div><p class="panel-hint">조회된 관측 중 마지막 12건 · 분석 결론이 아닌 실제 조회값</p><h3>적용 문서와 출처</h3><details v-for="doc in evidence.graph.documents" :key="doc.document_id" class="source-document"><summary><span>▤ {{doc.document_id}}</span><small>v{{doc.version}} · 교육용</small></summary><pre>{{doc.content}}</pre><small>{{doc.source_path}}</small></details><p v-if="!evidence.graph.documents?.length" class="empty-state">이 사건에 연결된 적용 문서가 없습니다. 근거를 추정하지 않습니다.</p></template><IncidentReview :incident-id="selected.id" :incident-status="currentIncident?.status" @updated="refresh" /><IncidentTimeline :incident-id="selected.id" :revision="currentIncident?.revision" /></template><p v-else class="empty-state">왼쪽에서 대응 사건을 선택하세요.</p></article>
          </section>
        </template>
        <section v-else class="mfg-panel knowledge-panel"><KnowledgeReview @published="loadGraph" /><div class="panel-heading"><h2>관계 탐색</h2><span>{{graph.nodes.length}}개 노드 · {{graph.edges.length}}개 관계</span></div><div v-if="graphError" class="mfg-error">{{graphError}}<button @click="loadGraph">재시도</button></div><p class="panel-hint" role="status">{{graphLoading ? "게시된 관계를 조회하고 있습니다." : graphError ? "최신 조회에 실패했습니다. 마지막으로 받은 그래프입니다." : "마지막 조회 " + time(graphLoaded)}} <span v-if="graphFilter">· {{graphFilter}} 중심 및 직접 연결 대상 표시</span></p><OntologyGraphPanel api-base="" read-only :allow-natural-language="false" :graph-data="visibleGraph" :schema="structure" :entity-counts="structure.classes" @filter="graphFilter=$event" @refresh="loadGraph"/><p class="panel-hint">게시된 교육용 관계 · 원본 문서의 적용 범위와 버전을 함께 확인하세요.</p></section>
      </main>
    </div>
  </div>
</template>
