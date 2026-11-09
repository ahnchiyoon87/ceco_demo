<script setup>
import { computed, defineAsyncComponent } from 'vue'
import { processState } from './processState.js'
const ProcessFlow=defineAsyncComponent(()=>import('./ProcessFlow.vue'))
const MaintenancePlanCard = defineAsyncComponent(() => import('./MaintenancePlanCard.vue'))
const ExecutionTrace = defineAsyncComponent(() => import('./ExecutionTrace.vue'))
const props = defineProps({run:Object,proposal:Object,incidentStatus:String,waiting:Boolean,loading:Boolean,error:String,note:String,submitting:Boolean,expired:Boolean,canAnalyze:Boolean,configured:Boolean})
const emit = defineEmits(['update:note','decide','analyze','recover','reload','control'])
const phases = [['received','이상 감지'],['investigate','원인 분석'],['review','승인 대기'],['execute','정비'],['result','복구 확인']]
const plan = computed(()=>props.proposal?.plan)
const ps = computed(()=>props.proposal?.result?.plan_state)
const report = computed(()=>props.proposal?.result?.report || ps.value?.report)
const state = computed(()=>{
  if(!props.incidentStatus)return {nodes:Object.fromEntries(phases.map(([key])=>[key,key==='received'&&props.waiting?'active':'waiting'])),outcome:''}
  const value=processState(props.run,props.proposal)
  if(!props.run&&!props.proposal)value.nodes.received='active'
  if(props.proposal?.status==='pending'&&props.expired)value.nodes.review='warning'
  if(ps.value?.phase==='verify'&&props.proposal?.result?.status==='executing_plan'){
    value.nodes.execute='done';value.nodes.result='active'
  }
  return value
})
const failed = computed(()=>['failed','interrupted','needs_evidence'].includes(props.run?.status) || ['unresolved','superseded'].includes(props.proposal?.status))
const pending = computed(()=>props.proposal?.status==='pending' && !failed.value)
const title = computed(()=>{
  if(props.error)return '처리 상태를 확인하고 있습니다'
  if(failed.value)return '추가 확인이 필요합니다'
  if(props.proposal?.status==='rejected')return '대응안을 반려했습니다'
  if(report.value?.outcome==='recovered')return '정비를 마치고 정상으로 복구했습니다'
  if(pending.value)return props.expired?'검토 기한이 지나 다시 분석해야 합니다':'대응안을 검토하고 승인해 주세요'
  if(ps.value?.phase==='verify')return '정상 상태가 유지되는지 확인합니다'
  if(props.proposal?.status==='executing')return '승인한 정비를 진행하고 있습니다'
  if(props.run?.status==='resuming')return '승인을 반영하고 있습니다'
  if(props.run?.status==='running')return '센서와 정비 문서에서 원인을 찾고 있습니다'
  if(props.incidentStatus)return '이상을 등록했습니다'
  return props.waiting?'센서에서 이상을 감지하고 있습니다':'이상 발생부터 복구까지 여기서 확인하세요'
})
const description = computed(()=>{
  if(props.error)return '연결이 복구되면 자동으로 갱신됩니다. 표시된 내용은 마지막으로 확인한 기록입니다.'
  if(failed.value)return props.run?.status==='needs_evidence'?'대응안을 만들기 위한 자료가 부족합니다. 아래 확인 사항을 살펴보세요.':'분석 또는 정비를 완료하지 못했습니다. 아래 기록을 확인한 뒤 다음 조치를 결정하세요.'
  if(pending.value)return props.expired?'현재 센서 상태로 대응안을 다시 작성한 뒤 검토합니다.':'예상 원인, 정비 방법과 영향을 확인하고 의견을 작성하세요. 승인 전에는 정비를 시작하지 않습니다.'
  if(report.value?.outcome==='recovered')return '정비 후 센서값이 회복 기준을 충족했습니다. 결과는 자동으로 저장됩니다.'
  if(props.proposal?.status==='rejected')return '이 대응안은 실행하지 않습니다. 필요하면 현재 상태로 다시 분석할 수 있습니다.'
  if(ps.value?.phase==='verify')return '온도와 유량이 회복 기준을 만족한 채 일정 시간 유지되어야 복구로 판정합니다.'
  if(props.proposal?.status==='executing'||props.run?.status==='resuming')return '진행 상태는 자동으로 바뀝니다. 정비가 끝나면 센서로 복구 여부를 확인합니다.'
  if(props.run?.status==='running')return '경보와 센서 변화, 설비에 연결된 문서를 함께 확인해 대응안을 작성합니다.'
  if(props.incidentStatus)return '경보를 모아 분석 조건을 확인합니다. 조건을 만족하면 분석이 자동으로 시작됩니다.'
  return props.waiting?'설비 변화가 경보로 들어오면 이 화면에 사건과 분석 과정이 자동으로 나타납니다.':'왼쪽에서 상황을 선택하고 이상을 발생시키세요. 분석은 자동으로 진행되며 승인할 때만 기다립니다.'
})
const causes = computed(()=>(props.proposal?.body?.cause_assessment||[]).filter(c=>c.status==='supported').map(c=>plan.value?.failure_modes?.[c.failure_mode]?.name||'센서 관측과 일치하는 원인'))
const summary = computed(()=>{
  const text=props.proposal?.body?.summary||''
  const match=text.match(/\[승인 시 영향\]([\s\S]*?)(?=\[|$)/)
  return match?.[1]?.trim() || ''
})
const steps = computed(()=>ps.value?.steps || plan.value?.steps || [])
const operatorWaiting = computed(()=>steps.value.find(s=>s.kind==='operator'&&s.status==='running'))
const plain=value=>String(value||'').replaceAll('스트레이너','필터').replaceAll('바스켓','필터망')
const stepLabels={pending:'대기',sent:'진행 중',running:'진행 중',done:'완료',done_no_fault:'점검 완료',no_fault:'원인 불일치',failed:'중단'}
const readingUnit=tag=>({'TT-101':'°C','FT-103':'m³/h','PDT-103':'bar','VT-101':'mm/s','PT-101':'barg','PT-102':'barg'})[tag]||''
const readingName=key=>({'TT_101':'반응기 온도','FT_103':'냉각수 유량','PDT_103':'필터 차압','VT_101':'교반기 진동','PT_101':'반응기 압력','PT_102':'반응기 압력(독립)'})[key.replaceAll('-','_')]||key.replaceAll('_','-')
</script>

<template>
  <section class="guided-incident" aria-label="이상 처리 과정" :aria-busy="submitting">
    <header class="guide-heading"><span>이상 처리 과정</span><small>자동 진행 · 승인 시 대기</small></header>
    <ProcessFlow display-only :run="run" :proposal="proposal" :state-override="state" />
    <div class="guide-current" role="status" aria-live="polite"><span class="guide-state" :class="{attention:pending||failed||error,complete:report?.outcome==='recovered'}"></span><div><h2>{{title}}</h2><p>{{description}}</p></div></div>
    <ExecutionTrace v-if="run" simplified :run="run" @state="value=>{if(value.status!==run?.status)emit('reload')}" />
    <div v-if="error" class="guide-warning" role="alert">{{error}} <button @click="emit('reload')">다시 연결</button></div>
    <div v-if="proposal" class="guide-summary">
      <article><small>예상 원인</small><strong>{{plain(causes.join(' · ')) || '추가 확인 필요'}}</strong><p>센서와 문서로 판단한 원인이며, 정비 중 실제 상태를 확인합니다.</p></article>
      <article><small>권장 정비</small><strong>{{plain(plan?.option_name || proposal.body?.summary)}}</strong></article>
      <details v-if="summary" class="guide-impact"><summary>승인 시 영향과 주의 사항</summary><p>{{summary}}</p><ul v-if="proposal.body?.uncertainties?.length"><li v-for="item in proposal.body.uncertainties" :key="item">{{item}}</li></ul></details>
    </div>
    <form v-if="pending" class="guide-approval" @submit.prevent="emit('decide','approve')">
      <div v-if="expired" class="guide-warning">기한이 지난 대응안은 승인할 수 없습니다. <button type="button" :disabled="submitting||!canAnalyze||!configured" @click="emit('analyze')">현재 상태로 다시 분석</button></div>
      <label for="guided-review-note">검토 의견</label>
      <textarea id="guided-review-note" :value="note" @input="emit('update:note',$event.target.value)" maxlength="2000" rows="2" required :disabled="submitting" placeholder="대응안을 검토한 의견을 작성해 주세요."></textarea>
      <div class="guide-review-actions"><small>{{note?.trim()?'승인하면 정비와 복구 확인이 이어집니다.':'의견을 작성하면 승인할 수 있습니다.'}}</small><button type="button" :disabled="submitting||!note?.trim()||run?.status==='resuming'" @click="emit('decide','reject')">반려</button><button class="guide-approve" type="submit" :disabled="submitting||!note?.trim()||expired||run?.status==='resuming'">{{submitting?'승인 반영 중…':'정비 승인'}}</button></div>
    </form>
    <section v-if="proposal?.status==='executing'||report" class="guide-repair" aria-label="정비 진행">
      <h3>정비 진행</h3><ol><li v-for="s in steps" :key="s.order" :class="s.status"><span>{{stepLabels[s.status]||'대기'}}</span><div><b>{{plain(s.say)}}</b><p v-if="s.finding">{{s.finding}}</p><p v-if="s.reason&&['failed','no_fault'].includes(s.status)">{{s.reason}}</p></div></li></ol>
      <div v-if="operatorWaiting" class="guide-warning">{{operatorWaiting.say}} · 운전원 조치가 필요합니다. <button @click="emit('control')">설비 제어 열기</button></div>
    </section>
    <section v-if="ps?.verify" class="guide-recovery" aria-label="복구 확인"><h3>복구 확인</h3><p>정상 조건 유지 <b>{{Math.floor(ps.verify.held_s||0)}} / {{plan.recovery?.hold_s||30}}초</b></p><progress :value="ps.verify.held_s||0" :max="plan.recovery?.hold_s||30"></progress></section>
    <section v-if="report" class="guide-report" aria-label="정비 결과"><h3>{{report.outcome==='recovered'?'복구 결과':'정비 결과 · 추가 확인 필요'}}</h3><dl v-for="v in report.before_after" :key="v.tag"><dt>{{readingName(v.tag)}} <small>{{v.unit||readingUnit(v.tag)}}</small></dt><dd>{{v.before?.toFixed?.(2)??v.before??'—'}} → <strong>{{v.after?.toFixed?.(2)??v.after??'—'}}</strong></dd></dl></section>
    <section v-if="failed" class="guide-warning"><p>{{run?.result?.result?.summary || proposal?.result?.reason || '저장된 기록에서 완료하지 못한 이유를 확인하세요.'}}</p><ul><li v-for="item in run?.result?.result?.missing" :key="item">{{item}}</li><li v-for="item in run?.result?.result?.next_steps" :key="item">{{item}}</li></ul><button v-if="['failed','interrupted'].includes(run?.status)" :disabled="submitting" @click="emit('recover')">중단 상태 확인</button><button v-if="canAnalyze&&configured&&run?.status!=='running'" :disabled="submitting" @click="emit('analyze')">현재 상태로 다시 분석</button></section>
    <button v-if="proposal?.status==='rejected'&&canAnalyze&&configured" :disabled="submitting" @click="emit('analyze')">현재 상태로 다시 분석</button>

    <details v-if="proposal" class="guide-details"><summary>판단 근거와 정비 결과 자세히 보기</summary><MaintenancePlanCard v-if="plan" :proposal="proposal" :mode="pending?'review':'result'" /><p v-else>{{proposal.body?.summary}}</p></details>
  </section>
</template>

<style scoped>
.guided-incident{background:#fff;border:1px solid #dce6e5;border-radius:18px;padding:26px;color:#193c43;min-width:0}.guide-heading{display:flex;justify-content:space-between;gap:8px;align-items:center;font-weight:750;font-size:18px}.guide-heading small{color:#6a8086;font-size:12px;font-weight:400}.guide-progress{display:grid;grid-template-columns:repeat(5,minmax(0,1fr));list-style:none;margin:22px 0 26px;padding:0;gap:3px}.guide-progress li{text-align:center;position:relative;color:#73898e}.guide-progress li:not(:last-child):after{content:'';position:absolute;top:17px;left:calc(50% + 21px);width:calc(100% - 42px);height:2px;background:#e1e9e8}.guide-progress li.done:after{background:#83c5b2}.guide-progress li>span{display:grid;place-items:center;width:36px;height:36px;margin:0 auto 9px;border-radius:50%;background:#eef3f3;color:#799093;font-size:14px}.guide-progress li.active>span{background:#176e5e;color:white;box-shadow:0 0 0 5px #e7f5f0}.guide-progress li.done>span{background:#dff2ea;color:#176e5e}.guide-progress li.warning>span{background:#fff0df;color:#966025}.guide-progress b{display:block;font-size:14px}.guide-progress small{display:block;font-size:11px;margin-top:5px}.guide-progress .active{color:#176e5e}.guide-current{display:flex;align-items:flex-start;gap:13px;padding:20px;background:#f0f7f5;border-radius:12px}.guide-state{width:10px;height:10px;flex:none;background:#16836b;border-radius:50%;margin-top:7px}.guide-state.attention{background:#ba7a27}.guide-current h2{font-size:19px;line-height:1.55;margin:0 0 8px}.guide-current p{font-size:14px;line-height:1.85;color:#577177;margin:0}.guide-summary{margin:20px 0}.guide-summary article{padding:14px 0;border-bottom:1px solid #edf1f0}.guide-summary small{display:block;font-size:12px;color:#638086;margin-bottom:7px}.guide-summary strong{font-size:17px;line-height:1.7}.guide-summary p{font-size:13px;line-height:1.9;color:#637b81;margin:7px 0 0}.guide-impact{font-size:13px;line-height:1.85;padding:14px 0}.guide-impact summary{font-weight:600;color:#48666a;cursor:pointer}.guide-impact p,.guide-impact ul{color:#4d676d;overflow-wrap:anywhere}.guide-approval{padding-top:8px}.guide-approval label{display:block;font-size:14px;font-weight:700;margin-bottom:8px}.guide-approval textarea{box-sizing:border-box;width:100%;font:inherit;font-size:14px;padding:12px;border:1px solid #bfcfcd;border-radius:8px;resize:vertical;line-height:1.7}.guide-review-actions{display:flex;align-items:center;gap:9px;flex-wrap:wrap;margin-top:12px}.guide-review-actions small{flex:1;color:#638086;font-size:12px}.guided-incident button{font:inherit;font-size:13px;padding:10px 16px;background:white;border:1px solid #c3d6d0;border-radius:8px;color:#325e56;cursor:pointer}.guided-incident button.guide-approve{background:#176e5e;color:white;border-color:#176e5e;font-weight:700}.guided-incident button:disabled{opacity:.4;cursor:default}.guide-details{margin-top:16px;border-top:1px solid #e1e9e6;padding-top:16px;font-size:14px}.guide-details>summary{cursor:pointer;color:#41675e;line-height:1.6}.guide-warning{background:#fff5e9;border:1px solid #ebd8bb;border-radius:10px;padding:14px;margin:14px 0;font-size:14px;line-height:1.8;overflow-wrap:anywhere}.guide-warning button{margin:5px}.guide-repair h3,.guide-recovery h3,.guide-report h3{font-size:16px;margin:22px 0 12px}.guide-repair ol{list-style:none;padding:0;margin:0}.guide-repair li{display:flex;gap:12px;padding:11px 0;border-bottom:1px solid #edf2f0;font-size:14px}.guide-repair li>span{flex:0 0 52px;font-size:11px;color:#6a8086;padding-top:3px}.guide-repair li.done>span{color:#16836b}.guide-repair li.running>span{color:#b1782e;font-weight:bold}.guide-repair li div{min-width:0}.guide-repair li b{line-height:1.7}.guide-repair li p{font-size:12px;color:#637b81;line-height:1.7;margin:5px 0}.guide-recovery{font-size:14px}.guide-recovery p{display:flex;justify-content:space-between;gap:8px}.guide-recovery progress{width:100%;height:9px;accent-color:#16836b}.guide-report dl{display:flex;justify-content:space-between;gap:12px;font-size:14px}.guide-report dd{margin:0;font-variant-numeric:tabular-nums}.guide-report strong{color:#16836b}@media(max-width:600px){.guided-incident{padding:18px}.guide-progress b{font-size:12px}.guide-progress small{font-size:10px}.guide-heading{font-size:16px}.guide-heading small{font-size:10px}.guide-current{padding:15px}.guide-current h2{font-size:17px}.guide-review-actions small{flex-basis:100%}.guide-summary strong{font-size:15px}}
</style>
