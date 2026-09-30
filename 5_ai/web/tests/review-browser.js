// Browser-only fixture: real Vue components, synthetic responses, zero live API calls.
import { createApp, h, ref } from 'vue'
import Review from '../src/features/operations/IncidentReview.vue'
import '../src/manufacturing.css'

const status = ref('awaiting_review'), revision = ref(0), log = ref([]), mode = ref('pending')
let proposal, run
function reset(next = 'pending') {
  mode.value = next; status.value = 'awaiting_review'; revision.value++; log.value = []
  proposal = {id:'fixture-proposal',origin:'browser-test',status:'pending',incident_revision:1,
    created_at:new Date().toISOString(),expires_at:new Date(Date.now()+3600000).toISOString(),
    body:{action:'request_inspection',summary:'격리 UI 시험용 점검 요청입니다. 실제 설비·DB에 연결하지 않습니다.',citations:['fixture-SOP'],uncertainties:['실제 판단 결과가 아닙니다.']}}
  run = {id:'fixture-run',model:'fixture · 모델 미호출',status:'awaiting_review',created_at:new Date().toISOString()}
  if (next === 'failure') {
    run.status = 'failed'; run.error = 'APIConnectionError'; run.updated_at = new Date().toISOString()
    proposal = null; status.value = 'received'
  }
}
reset()
globalThis.fetch = async (path, options = {}) => {
  const url = String(path), method = options.method || 'GET'
  // Deliberately no network fallback: unexpected requests must fail visibly.
  log.value.push({method,path:url,body:options.body ? JSON.parse(options.body) : null})
  const reply = (data, ok=true) => ({ok,status:ok?200:503,json:async()=>structuredClone(data)})
  if(method === 'GET') {
    if(url.endsWith('/proposals')) return reply({items:proposal?[proposal]:[]})
    if(url.endsWith('/analysis')) return reply({items:[run]})
    if(url.endsWith('/trace')) return reply({items:[],truncated:false})
    if(url.endsWith('/model-status')) return reply({configured:false,model:'fixture'})
  }
  if(method==='POST' && url.endsWith('/decision')) {
    if(mode.value==='ambiguous') return reply({detail:'시험용 응답 실패: 저장 기록을 다시 조회하세요.'},false)
    const decision=JSON.parse(options.body)
    proposal.decision=decision
    proposal.status=decision.decision==='reject'?'rejected':'awaiting_maintenance'
    status.value=decision.decision==='reject'?'unresolved':'awaiting_maintenance'
    if(decision.decision==='approve') proposal.result={status:'inspection_requested',reason:'시험용 점검 요청 기록. 설비 명령 없음.'}
    run.status='finished'
    return reply({proposal,replayed:false})
  }
  if(method==='POST' && url.endsWith('/recover')) return reply({status:'failed'})
  throw new Error(`Unexpected fixture request: ${method} ${url}`)
}
createApp({setup:()=>()=>h('main',{style:'max-width:1000px;margin:24px auto;padding:24px;font-family:Arial,sans-serif'},[
  h('h1','검토 UI 격리 검증'),
  h('p',{role:'note'},'시험용 응답 · 실제 Vue 컴포넌트 · 운영 API/DB/설비/모델 호출 없음'),
  h('nav',{style:'display:flex;gap:12px;margin:20px 0'},['pending','ambiguous','failure'].map(x=>h('button',{onClick:()=>reset(x)},x))),
  h(Review,{key:revision.value,incidentId:'fixture-incident',incidentStatus:status.value}),
  h('h2','시험 요청 기록'),h('pre',{id:'fixture-log',style:'white-space:pre-wrap'},JSON.stringify(log.value,null,2))
])}).mount('#app')
