<script setup>
import { ref, watch, computed, onUnmounted, defineAsyncComponent, nextTick } from 'vue'
import {processState} from './processState.js'
import {actionPresentation} from './actionPresentation.js'
const ProcessFlow = defineAsyncComponent(() => import('./ProcessFlow.vue'))
const ProposalFacts = defineAsyncComponent(() => import('./ProposalFacts.vue'))
const ExecutionTrace = defineAsyncComponent(() => import('./ExecutionTrace.vue'))
const ThermalObservation = defineAsyncComponent(() => import('./ThermalObservation.vue'))
const MaintenancePlanCard = defineAsyncComponent(() => import('./MaintenancePlanCard.vue'))
const props = defineProps({ incidentId: { type: String, required: true }, incidentStatus: { type: String, default: 'received' } })
const canAnalyze = computed(() => ['received', 'awaiting_review', 'unresolved'].includes(props.incidentStatus))
const emit = defineEmits(['updated'])
const items = ref([]), error = ref(''), loading = ref(false), submitting = ref(false), note = ref('')
const runs = ref([]), model = ref(null)
const errorNotice = ref(null)
const latestRun = computed(() => runs.value[0])
// Never present an older run's proposal as the result of a new investigation.
const flowProposal = computed(() => latestRun.value
  ? items.value.find(p => p.origin?.split(':')[1] === latestRun.value.id)
  : items.value[0])
const previousFailures = computed(() => runs.value.slice(1).filter(r=>['failed','interrupted'].includes(r.status)))
const selectedStage=ref('received')
const flowView=ref(null)
const stagePanel=ref(null)
let selectionInitialized=false
const stageNames={received:'이상 사건 접수',investigate:'Agent 근거 조사',review:'담당자 검토',execute:'조치·상태 확인',result:'결과 기록'}
const currentStage=computed(()=>{
  const nodes=processState(latestRun.value,flowProposal.value).nodes
  return Object.keys(nodes).find(k=>nodes[k]==='active') || Object.keys(nodes).reverse().find(k=>nodes[k]==='warning'||nodes[k]==='done') || 'received'
})
function selectStage(stage){
  selectedStage.value=stage;selectionInitialized=true
  nextTick(()=>{
    const target=window.matchMedia('(max-width:1000px)').matches?stagePanel.value:flowView.value?.$el
    target?.scrollIntoView({block:'start',behavior:'instant'})
    if(target===stagePanel.value)target?.focus({preventScroll:true})
  })
}
function showProcess(){flowView.value?.$el?.scrollIntoView({block:'start',behavior:'instant'})}
function resumeFollow(){selectStage(currentStage.value)}
const stageProposals=computed(()=>['review','execute','result'].includes(selectedStage.value)?items.value:[])
const date = value => new Date(value).toLocaleString('ko-KR')
function failureAdvice(run) {
  if (run.status === 'interrupted') return '저장된 상태를 먼저 확인하세요. 처리 이력을 확인한 후 다음 작업을 결정합니다.'
  if (/StructuredOutputValidationError|MultipleStructuredOutputsError/.test(run.error || '')) return 'AI 응답이 필수 형식을 충족하지 못했습니다. 기록에 남은 거절 응답을 확인한 뒤 다시 분석할 수 있습니다.'
  if (/APITimeoutError|APIConnectionError/.test(run.error || '')) return '모델 연결 또는 응답 시간을 확인하세요. 자동으로 다시 요청하지 않습니다. 처리 기록을 확인한 뒤 재분석하세요.'
  return '오류 내용과 현재 근거를 확인하세요. 이미 처리된 조치가 있는지 기록을 확인한 뒤 다시 진행합니다.'
}
const runActive = computed(() => runs.value.some(r=>['running','resuming'].includes(r.status)) || items.value.some(p=>['observing','executing'].includes(p.status)))
let poll
const now=ref(Date.now())
const expiryClock=setInterval(()=>{now.value=Date.now()},1000)
const expired=proposal=>new Date(proposal.expires_at).getTime()<=now.value
let generation = 0
const labels = { pending:'검토 대기', executing:'실행 중 · 재전송 금지', observing:'명령 반영 후 온도 관측', rejected:'반려', superseded:'새 대응안으로 교체', awaiting_maintenance:'점검 대기', resolved:'정비 완료 · 회복 확인', unresolved:'미해결 · 재분석 필요' }
async function request(path, options={}) {
  const response = await fetch(path, { ...options, signal: AbortSignal.timeout(25000) })
  const data = await response.json()
  if (!response.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `요청 실패 (${response.status})`)
  return data
}
async function load() {
  const current = ++generation
  clearTimeout(poll)
  loading.value = true
  error.value = ''
  try {
    const [data, analysis, status] = await Promise.all([
      request(`/api/operations/incidents/${props.incidentId}/proposals`),
      request(`/api/operations/incidents/${props.incidentId}/analysis`),
      request('/api/operations/model-status')
    ])
    if (generation === current) {
      const priorStatus = latestRun.value?.status
      const priorProposalStatus = flowProposal.value?.status
      items.value = data.items; runs.value = analysis.items; model.value = status
      if(!selectionInitialized){selectedStage.value=currentStage.value;selectionInitialized=true}
      if ((priorStatus && priorStatus !== latestRun.value?.status) || (priorProposalStatus && priorProposalStatus !== flowProposal.value?.status)) emit('updated')
    }
  } catch (e) { if (generation === current) error.value = e.message }
  finally { if (generation === current) {
    loading.value = false
    // Retry transient read failures; never retry a POST or an equipment action.
    if (runActive.value || error.value) poll = setTimeout(load, error.value ? 6000 : items.value.some(p=>p.status==='executing') ? 1500 : 3000)
  } }
}
let selectionVersion = 0
watch(() => props.incidentId, () => {
  selectionVersion++; clearTimeout(poll)
  items.value = []; runs.value = []; model.value = null
  note.value = ''; submitting.value = false
  selectionInitialized=false;selectedStage.value='received'
  load()
}, { immediate:true })
onUnmounted(() => { selectionVersion++; generation++; clearTimeout(poll);clearInterval(expiryClock) })
async function submitAction(action, { clearNote=false, notify=false, errorHint='' }={}) {
  if (submitting.value) return
  const owner = selectionVersion
  submitting.value = true
  error.value = ''
  try {
    await action()
    if (owner !== selectionVersion) return
    if (clearNote) note.value = ''
    await load()
    if (owner === selectionVersion && notify) emit('updated')
  } catch (e) {
    if (owner === selectionVersion) {
      error.value = e.message + errorHint
      await nextTick()
      if (owner === selectionVersion) {
        errorNotice.value?.scrollIntoView({block:'nearest'})
        errorNotice.value?.focus({preventScroll:true})
      }
    }
  } finally {
    if (owner === selectionVersion) submitting.value = false
  }
}
async function analyze() {
  if (!canAnalyze.value) return
  selectStage('investigate')
  const incident = props.incidentId
  return submitAction(() => request(`/api/operations/incidents/${incident}/analyze`, {method:'POST'}))
}
async function recoverRun(run) {
  return submitAction(() => request(`/api/operations/analysis/${run.id}/recover`, {method:'POST'}))
}
async function decide(proposal, decision) {
  if (!note.value.trim()) return
  if(decision==='approve' && expired(proposal))return
  const reviewNote = note.value.trim()
  const path = proposal.origin.startsWith('ai-run:')
    ? `/api/operations/analysis/${proposal.origin.split(':')[1]}/decision`
    : `/api/operations/proposals/${proposal.id}/decision`
  return submitAction(() => request(path, {
    method:'POST', headers:{'Content-Type':'application/json'},
    body:JSON.stringify({decision,note:reviewNote})
  }), { clearNote:true, notify:true, errorHint:' 결과가 불명확하면 먼저 기록을 새로 조회하세요.' })
}
async function recover(proposal) {
  return submitAction(() => request(`/api/operations/proposals/${proposal.id}/recover`, {method:'POST'}), {notify:true})
}
</script>

<template>
  <section class="review-section">
    <ProcessFlow ref="flowView" :run="latestRun" :proposal="flowProposal" :selected="selectedStage" @select="selectStage" />
    <div ref="stagePanel" class="stage-toolbar" tabindex="-1" :aria-label="stageNames[selectedStage]"><h3>{{stageNames[selectedStage]}}</h3><button @click="showProcess">프로세스 보기</button><button @click="resumeFollow">현재 처리 단계 보기 · {{stageNames[currentStage]}}</button></div>
    <p class="panel-hint">선택한 카드의 내용입니다. 처리 상태는 계속 갱신되며, 보고 있는 카드는 자동으로 바뀌지 않습니다.</p>
    <div v-if="selectedStage==='received'" class="stage-receipt"><b>선택한 이상 사건</b><p>{{incidentId}}</p><p>접수 상태: {{incidentStatus}} · 정비 판단이 연결된 사건은 알람이 이어지면 AI 분석이 자동으로 시작됩니다. 아래 버튼으로 직접 시작하거나 다시 분석할 수 있습니다.</p></div>
    <div class="panel-heading"><span class="panel-hint">실제 저장 기록 기준</span><button class="review-refresh" :disabled="loading" @click="load">기록 새로고침</button></div>
    <div v-if="['received','investigate'].includes(selectedStage)" class="analysis-control"><div><b>AI가 센서 기록과 매뉴얼을 확인합니다</b><p>{{model?.configured?model.model+' · 분석 버튼을 누르면 시작합니다':'모델 연결 대기 · 근거 조회는 이용 가능'}}</p></div><button :disabled="!model?.configured||submitting||runActive||!canAnalyze" @click="resumeFollow();analyze()">{{runActive?'처리 중…':submitting?'요청 중…':'AI 분석 · 대응안 작성'}}</button></div>
    <ExecutionTrace v-show="['investigate','execute'].includes(selectedStage)" :mode="selectedStage==='execute'?'execute':'investigate'" :run="latestRun" @state="value=>{if(value.status!==latestRun?.status)load()}" />
    <p v-if="!canAnalyze" class="panel-hint">현재 사건은 조치 실행·점검 대기 또는 종료 단계입니다. 저장된 대응안과 처리 결과를 확인하세요.</p><p v-if="runActive" role="status" class="panel-hint">분석 또는 승인 처리가 진행 중입니다. 실행 기록을 자동 조회합니다.</p>
    <article v-if="latestRun && ['failed','interrupted'].includes(latestRun.status)" class="analysis-failure" role="alert">
      <header><b>{{latestRun.status==='interrupted'?'중단된 처리 확인 필요':'최근 분석·검토를 완료하지 못했습니다'}}</b><time>{{date(latestRun.updated_at)}}</time></header>
      <p>{{latestRun.error}}</p><p class="failure-advice">{{failureAdvice(latestRun)}}</p>
      <button :disabled="submitting" @click="recoverRun(latestRun)">저장된 상태 확인</button>
    </article>
    <details v-if="previousFailures.length" class="analysis-history">
      <summary>이전 실패·중단 기록 {{previousFailures.length}}건</summary>
      <div v-for="run in previousFailures" :key="run.id" class="past-run"><time>{{date(run.updated_at)}}</time><p>{{run.error}}</p><small>실행 {{run.id.slice(0,8)}}</small> <button :disabled="submitting" @click="recoverRun(run)">상태 확인</button></div>
    </details>
    <p v-if="loading" role="status" class="panel-hint">저장된 검토 기록을 조회합니다.</p>
    <component :is="run.id===latestRun?.id?'article':'details'" v-for="run in runs.filter(r=>r.status==='needs_evidence' && selectedStage==='investigate')" :key="run.id" class="proposal-card evidence-needed">
      <summary v-if="run.id!==latestRun?.id">이전 근거 보완 기록 · {{date(run.updated_at)}}</summary>
      <header><b>근거 보완 필요</b><span>설비 명령 없음</span></header>
      <p class="panel-hint">승인할 대응안이 생성되지 않았습니다. 아래 내용은 추가 확인 요청입니다.</p>
      <p class="proposal-summary">{{run.result?.result?.summary}}</p>
      <h4>부족하거나 확인이 필요한 근거</h4>
      <ul><li v-for="item in run.result?.result?.missing" :key="item">{{item}}</li></ul>
      <h4>다음 확인 단계</h4>
      <ol><li v-for="item in run.result?.result?.next_steps" :key="item">{{item}}</li></ol>
      <p class="panel-hint">{{new Date(run.updated_at).toLocaleString('ko-KR')}} · 자료를 보완한 뒤 다시 분석하세요.</p>
    </component>
    <p v-if="error" ref="errorNotice" class="mfg-error" role="alert" tabindex="-1">{{error}}</p>
    <p v-if="!loading && !items.length && !error && !runs.some(r=>r.status==='needs_evidence')" class="panel-hint">아직 작성된 대응안이 없습니다. 근거 분석을 완료하면 이곳에서 검토합니다.</p>
    <p v-if="['execute','result'].includes(selectedStage)&&!flowProposal?.result&&flowProposal?.status!=='executing'" class="panel-hint">아직 조치 결과가 없습니다. 승인 전에는 설비 명령을 보내지 않습니다.</p>
    <component :is="index===0||proposal.status==='pending'?'article':'details'" v-for="(proposal,index) in stageProposals" :key="proposal.id" class="proposal-card">
      <summary v-if="index>0 && proposal.status!=='pending'">이전 대응안 · {{labels[proposal.status]||proposal.status}} · {{date(proposal.created_at)}}</summary>
      <header><b>{{actionPresentation(proposal.body.action).title}}</b><span>{{labels[proposal.status]||proposal.status}}</span></header>
      <p v-if="proposal.origin.includes('test')" class="test-label">강사 통합 검증 기록 · AI 생성 대응안 아님</p>
      <div v-if="proposal.result" class="action-result" :class="{uncertain:proposal.status==='unresolved'}"><b>{{proposal.result.status==='stop_verified'?'정지 확인 · 정비 완료 아님':labels[proposal.status]}}</b><p>{{proposal.result.reason}}</p></div>
      <MaintenancePlanCard v-if="proposal.plan" :proposal="proposal" :mode="selectedStage==='review'?'review':'result'" />
      <template v-else>
      <ThermalObservation v-if="proposal.result?.thermal_observation" :track="proposal.result.thermal_observation" />
      <ProposalFacts :proposal="proposal" :mode="selectedStage==='review'?'review':'result'" />
      <details v-if="selectedStage==='review'" class="analysis-explanation"><summary>AI 판단 이유 · 상세 설명 펼치기</summary><p class="proposal-summary">{{proposal.body.summary}}</p></details>
      </template>
      <div class="sensor-chips"><span v-for="citation in proposal.body.citations" :key="citation">▤ {{citation}}</span></div>
      <template v-if="selectedStage==='review'"><p class="panel-hint">AI 제안 당시의 미확인 사항{{proposal.result?' · 실행 여부는 위 조치 결과를 확인하세요.':''}}</p>
      <ul><li v-for="item in proposal.body.uncertainties" :key="item">{{item}}</li></ul></template>
      <p class="panel-hint">검토 기준 {{proposal.incident_revision}} · 검토 기한 {{new Date(proposal.expires_at).toLocaleString('ko-KR')}}</p>
      <template v-if="proposal.status==='pending' && selectedStage==='review'">
        <p v-if="expired(proposal)" class="mfg-error" role="status">이 대응안은 검토 기한이 지났습니다. 승인할 수 없습니다. Agent 근거 조사 카드에서 현재 상태로 다시 분석하세요. 반려는 가능합니다.</p>
        <label :for="'review-'+proposal.id">검토 의견</label>
        <textarea :id="'review-'+proposal.id" v-model="note" maxlength="2000" rows="2" placeholder="근거를 확인한 후 승인 또는 반려 이유를 작성하세요." :disabled="submitting"></textarea>
        <p class="panel-hint">{{actionPresentation(proposal.body.action).description}} 상태 변경·만료 시 재분석이 필요합니다.</p>
        <div class="review-buttons"><button :disabled="submitting||runActive||!note.trim()" @click="decide(proposal,'reject')">반려</button><button class="approve-button" :disabled="submitting||runActive||!note.trim()||expired(proposal)" @click="decide(proposal,'approve')">{{submitting||runActive?'처리 중…':expired(proposal)?'기한 만료 · 재분석 필요':'승인하고 진행'}}</button></div>
      </template>
      <p v-if="proposal.decision" class="review-note">검토 결과: {{proposal.decision.decision==='approve'?'승인':'반려'}} · {{proposal.decision.note}}</p>
      <div v-if="proposal.status==='executing' && !proposal.plan" class="mfg-error">처리 중이거나 결과 저장이 중단된 상태입니다. 기록을 먼저 새로고침하세요. 30초 이상 지속되면 명령을 다시 보내지 않고 미해결로 전환할 수 있습니다.<button :disabled="submitting" @click="recover(proposal)">중단된 실행 확인</button></div>
    </component>
  </section>
</template>

<style scoped>
.stage-toolbar{display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap}.stage-toolbar h3{margin:0;font-size:var(--ui-font-heading)}.stage-toolbar button{border:1px solid #91b9af;border-radius:8px;background:#eef8f4;color:#15594c;padding:9px 12px}.stage-receipt{padding:16px;border:1px solid #dae6e2;border-radius:10px;overflow-wrap:anywhere;font-size:var(--ui-font-caption)}
.proposal-card .proposal-summary{font-size:var(--ui-font-body);line-height:1.95;overflow-wrap:anywhere}
.review-section .proposal-card ul{font-size:var(--ui-font-caption);line-height:1.85;color:#685f4c}
.review-section .proposal-card header{font-size:var(--ui-font-input);align-items:center}
.proposal-card .review-note{font-size:var(--ui-font-caption);line-height:1.8}
.proposal-card .panel-hint{font-size:var(--ui-font-caption)}
.analysis-control{gap:12px;flex-wrap:wrap}
.analysis-failure{margin:16px 0;padding:16px 18px;border:1px solid #e8c9b7;border-left:4px solid #b87142;border-radius:10px;background:#fff9f4;color:#70482c;font-size:var(--ui-font-caption);line-height:var(--ui-line-height)}.analysis-failure header{display:flex;flex-wrap:wrap;gap:8px;justify-content:space-between}.analysis-failure time,.past-run time{font-size:var(--ui-font-caption);color:#6f747c}.failure-advice{color:#4d5963}.analysis-failure button,.past-run button{border:1px solid #d6dadc;background:white;border-radius:6px;padding:7px 11px;color:#384c59}.analysis-history{margin:14px 0;border:1px solid #dfe6e9;border-radius:9px;padding:12px 15px;font-size:var(--ui-font-caption)}.analysis-history summary,.proposal-card>summary{cursor:pointer;color:#536775;line-height:var(--ui-line-height)}.past-run{border-top:1px solid #e5ecef;margin-top:12px;padding-top:12px}.past-run p{margin:5px 0}.proposal-card>summary{font-size:var(--ui-font-caption)}.proposal-card[open]>summary{padding-bottom:14px;margin-bottom:14px;border-bottom:1px solid #e4ebee}.evidence-needed h4{font-size:var(--ui-font-caption);color:#405866}.evidence-needed ol{font-size:var(--ui-font-caption);line-height:1.8;padding-left:22px}
.analysis-control{display:flex;justify-content:space-between;align-items:center;background:#f0f6f4;padding:14px;border-radius:8px;margin-top:15px;font-size:var(--ui-font-caption)}.analysis-control p{font-size:var(--ui-font-caption);color:#74877c;margin:5px 0 0}.analysis-control button{border:1px solid #bcd7cd;background:white;color:#267c66;border-radius:6px;padding:8px 12px;font-size:var(--ui-font-caption)}
.review-section{border-top:1px solid #e2e9ed;margin-top:28px;padding-top:8px}.review-refresh{font-size:var(--ui-font-caption);background:none;border:0;color:#188371}.proposal-card{border:1px solid #dae6e2;border-radius:9px;padding:17px;margin:14px 0}.proposal-card header{display:flex;justify-content:space-between;font-size:var(--ui-font-caption);gap:15px}.proposal-card header span{color:#176f60;font-size:var(--ui-font-caption)}.proposal-summary{font-size:var(--ui-font-caption);white-space:pre-wrap;line-height:1.9}.proposal-card ul{font-size:var(--ui-font-caption);color:#7a715c;padding-left:20px;line-height:1.8}.proposal-card label{display:block;font-size:var(--ui-font-caption);margin:12px 0 5px}.proposal-card textarea{width:100%;border:1px solid #cfdbd8;border-radius:6px;padding:10px;font:inherit;font-size:var(--ui-font-caption);resize:vertical}.review-buttons{display:flex;justify-content:flex-end;gap:10px}.review-buttons button{border:1px solid #ccd9d4;background:white;padding:9px 18px;border-radius:6px;font-size:var(--ui-font-caption)}.review-buttons .approve-button{background:#167c68;color:white;border-color:#167c68}button:disabled{opacity:.5;cursor:default}.review-note{font-size:var(--ui-font-caption);color:var(--ui-text-muted);border-top:1px solid #e5ece9;padding-top:12px}.action-result{border-radius:6px;padding:12px;background:#eff7f2;font-size:var(--ui-font-caption);color:#35755f}.action-result p{margin:5px 0}.action-result.uncertain{background:#fff4e8;color:#936a32}.test-label{display:inline-block;background:#edf0f4;font-size:var(--ui-font-caption);padding:3px 7px;color:#6a7885;border-radius:4px}
</style>
