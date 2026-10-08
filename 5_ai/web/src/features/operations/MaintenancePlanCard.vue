<script setup>
// 정비 계획 조치 카드: AI 판단 요약 · 원인 판단 · 대안 손익 비교 · 정비 단계 · 회복 기준 → (승인 뒤) 진행 · 회복 판정 · 작업 보고서.
// 숫자는 저장된 계획·실행 기록에서만 읽는다(화면이 계산하거나 지어내지 않는다).
import {computed} from 'vue'
const props=defineProps({proposal:Object,mode:{type:String,default:'review'}})
const plan=computed(()=>props.proposal.plan||{})
const decision=computed(()=>plan.value.evaluation?.decisions?.[0]||{options:[],flips:[],facts_used:[]})
const kpis=computed(()=>plan.value.evaluation?.kpis||[])
const ps=computed(()=>props.proposal.result?.plan_state)
const report=computed(()=>props.proposal.result?.report||ps.value?.report)
const optionName=id=>decision.value.options.find(o=>o.option_id===id)?.name||id
const won=v=>v===null||v===undefined?'—':(v>0?'+':'')+Number(v).toLocaleString('ko-KR',{maximumFractionDigits:1})
const kpiValue=(o,k)=>o.impacts.find(i=>i.kpi===k)?.value
const sections=computed(()=>{
  const text=props.proposal.body?.summary||''
  const heads=['관측','원인 판단','대안 비교','정비 계획','승인 시 영향']
  const parts=[];const re=/\[(관측|원인 판단|대안 비교|정비 계획|승인 시 영향)\]/g;let m,last=null,idx=0
  while((m=re.exec(text))){if(last)parts.push({head:last,body:text.slice(idx,m.index).trim()});last=m[1];idx=re.lastIndex}
  if(last)parts.push({head:last,body:text.slice(idx).trim()})
  return parts.length?parts.sort((a,b)=>heads.indexOf(a.head)-heads.indexOf(b.head)):[{head:'AI 판단',body:text}]
})
const statusText={supported:'관측이 지지',refuted:'관측이 반박',unknown:'센서로 확인 불가',not_applicable:'전제 불성립'}
const causes=computed(()=>(props.proposal.body?.cause_assessment||[]).map(c=>({...c,name:plan.value.failure_modes?.[c.failure_mode]?.name||c.failure_mode,
  field:plan.value.failure_modes?.[c.failure_mode]?.field_checks?.join(', ')})))
const kinds={control:'운전 명령',field:'현장 정비',operator:'운전원',wait:'설비 대기'}
const stepState={pending:'대기',sent:'진행 중',running:'진행 중',done:'완료',done_no_fault:'점검 · 고장 없음',no_fault:'고장 없음 · 계획 중단',failed:'실패 · 중단'}
const steps=computed(()=>ps.value?.steps||plan.value.steps||[])
const readable=t=>String(t).replace(/abs\(([^)]*)\)/g,'|$1|').replace(/o_([A-Za-z]+)_(\d+)/g,'$1-$2').replace(/usl_([A-Za-z]+)_(\d+)/g,'$1-$2 상한')
  .replace(/c_temp_sp_c/g,'목표 온도').replace(/<=/g,'≤').replace(/>=/g,'≥').replace(/ - /g,' − ')
const verify=computed(()=>ps.value?.verify)
const holdPct=computed(()=>Math.min(100,Math.round(100*(verify.value?.held_s||0)/(plan.value.recovery?.hold_s||30))))
const series=computed(()=>{
  const s=verify.value?.samples||[];if(s.length<2)return []
  const keys=Object.keys(s[0]).filter(k=>k!=='at')
  return keys.map((k,i)=>{const vals=s.map(x=>x[k]).filter(v=>typeof v==='number');if(vals.length<2)return null
    const lo=Math.min(...vals),hi=Math.max(...vals),span=hi-lo||1
    const pts=s.map((x,j)=>typeof x[k]==='number'?`${(j/(s.length-1)*300).toFixed(1)},${(52-(x[k]-lo)/span*44).toFixed(1)}`:null).filter(Boolean).join(' ')
    return {key:k.replace(/_(\d+)$/,'-$1'),pts,last:vals.at(-1),lo,hi,color:['#1f7a62','#b26b2b','#3d5f9a'][i%3]}}).filter(Boolean)
})
const outcomeClass=computed(()=>({recovered:'ok',not_recovered:'bad',cause_mismatch:'bad',step_failed:'bad'})[report.value?.outcome]||'')
const operatorWaiting=computed(()=>steps.value.find(s=>s.kind==='operator'&&s.status==='running'))
const kindOf=o=>o.kind==='inspect'?'점검형':'원인 대응'
</script>

<template>
<div class="plan-card">
  <header class="plan-head">
    <div><small>정비 계획 · {{decision.name}}</small><h4>{{plan.option_name}}</h4></div>
    <span v-if="plan.differs_from_recommended" class="badge warn">손익 1위 권고와 다른 선택</span>
    <span v-else class="badge ok">손익 1위 권고안</span>
  </header>

  <section class="summary-blocks">
    <article v-for="part in sections" :key="part.head"><b>{{part.head}}</b><p>{{part.body}}</p></article>
  </section>

  <section v-if="causes.length">
    <h5>원인 판단 <small>지지하는 관측이 있어도 확정이 아닙니다. 확정은 현장 정비 소견으로 합니다.</small></h5>
    <table class="grid"><thead><tr><th>고장모드 후보</th><th>판단</th><th>근거 관측</th></tr></thead>
      <tbody><tr v-for="c in causes" :key="c.failure_mode" :class="c.status"><td><b>{{c.name}}</b><br><small>{{c.failure_mode}}</small></td>
        <td><span class="pill" :class="c.status">{{statusText[c.status]||c.status}}</span></td><td>{{c.evidence}}<small v-if="c.field" class="field-note"><br>현장 확인: {{c.field}}</small></td></tr></tbody></table>
  </section>

  <section>
    <h5>대안 손익 비교 <small>단위 만원 · 기업 시스템 사실값 × 온톨로지 손익 식 · 큰 값이 유리</small></h5>
    <div class="table-scroll"><table class="grid options">
      <thead><tr><th>대안</th><th v-for="k in kpis" :key="k.kpi">{{k.name}}<br><small>{{k.owner}}</small></th><th>합계</th><th>판정</th></tr></thead>
      <tbody><tr v-for="o in decision.options" :key="o.option_id" :class="{chosen:o.option_id===plan.option_id,excluded:o.excluded,ineligible:!o.eligible}">
        <td><b>{{o.name}}</b><br><small>{{kindOf(o)}} · {{o.option_id}}</small></td>
        <td v-for="k in kpis" :key="k.kpi" class="num">{{won(kpiValue(o,k.kpi))}}</td>
        <td class="num total">{{won(o.total)}}</td>
        <td><span v-if="o.option_id===plan.option_id" class="pill supported">선택</span>
          <span v-else-if="o.rank" class="pill">순위 {{o.rank}}</span>
          <span v-if="o.excluded" class="pill refuted" :title="o.rules.map(r=>r.policy).join(', ')">규칙 제외: {{o.rules.map(r=>r.reason).join(' · ')}}</span>
          <span v-else-if="!o.eligible" class="pill unknown">원인과 맞지 않음</span>
          <span v-else-if="!o.executable" class="pill unknown">실행 단계 없음</span></td></tr></tbody></table></div>
    <div v-if="decision.flips?.length" class="flips"><b>이 권고가 뒤집히는 조건</b>
      <ul><li v-for="f in decision.flips.slice(0,4)" :key="f.fact">{{f.description}}({{f.system}}) 지금 {{f.current}}{{f.unit}} → {{f.flip_value}}{{f.unit}} 이면 <b>{{optionName(f.new_recommendation)}}</b></li></ul></div>
    <details><summary>계산에 쓴 기업 사실값 {{decision.facts_used?.length||0}}개</summary>
      <table class="grid"><tbody><tr v-for="f in decision.facts_used" :key="f.key"><td>{{f.system}}</td><td>{{f.description}}</td><td class="num">{{f.value}} {{f.unit}}</td></tr></tbody></table></details>
  </section>

  <section>
    <h5>정비 단계 <small v-if="!ps">승인하면 이 순서로 실행합니다. 결과가 불명확한 단계는 다시 보내지 않고 멈춥니다.</small></h5>
    <ol class="steps">
      <li v-for="s in steps" :key="s.order" :class="['step',s.status||'pending']">
        <span class="kind">{{kinds[s.kind]}}</span>
        <div><b>{{s.say}}</b><small v-if="s.wm"> · {{s.wm}}</small><small v-if="s.parameters?.length"> · {{s.parameters.map(p=>p.id+'='+p.value).join(', ')}}</small>
          <small v-if="s.plant_hours"> · 설비 {{s.plant_hours}} h</small>
          <p v-if="s.finding" class="finding">현장 소견: {{s.finding}}</p>
          <p v-if="s.reason && ['failed','no_fault'].includes(s.status)" class="fail-note">{{s.reason}}</p>
          <p v-if="s.waiting_operator" class="operator-note">{{s.kind==='operator'?'운전원 조치 대기: FUXA 에서 인터록 리셋(압력이 해제값 아래일 때만 받습니다).':'공장 운전원 수락 대기(FUXA 받은 요청).'}}</p>
          <p v-if="s.kind==='wait' && s.remaining_s>0" class="operator-note">설비 시간 대기 · 남은 실제 {{s.remaining_s}}초</p></div>
        <span v-if="ps" class="state">{{stepState[s.status]||s.status}}</span>
      </li>
    </ol>
    <p v-if="operatorWaiting" class="operator-banner">운전원 조치가 필요합니다: {{operatorWaiting.say}}</p>
  </section>

  <section>
    <h5>회복 확인 기준 <small>{{plan.recovery?.hold_s}}초 이상 유지 · 최대 {{plan.recovery?.timeout_s}}초 관측 · {{plan.recovery?.section}}</small></h5>
    <ul class="criteria"><li v-for="(c,i) in plan.recovery?.all||[]" :key="c">
      <span v-if="verify?.last" class="pill" :class="verify.last.results[i]?.ok?'supported':'refuted'">{{verify.last.results[i]?.ok?'충족':'미충족'}}</span> {{readable(c)}}</li></ul>
    <div v-if="verify" class="verify">
      <div class="bar"><span :style="{width:holdPct+'%'}"></span></div><small>유지 {{verify.held_s}} / {{plan.recovery?.hold_s}}초</small>
      <div class="sparks"><figure v-for="sr in series" :key="sr.key"><svg viewBox="0 0 300 56" preserveAspectRatio="none"><polyline :points="sr.pts" :stroke="sr.color" fill="none" stroke-width="2"/></svg>
        <figcaption>{{sr.key}} <b>{{sr.last?.toFixed(2)}}</b> <small>({{sr.lo.toFixed(1)}}~{{sr.hi.toFixed(1)}})</small></figcaption></figure></div>
    </div>
  </section>

  <section v-if="report" class="report" :class="outcomeClass">
    <h5>작업 보고서 · {{report.work_order_id}}</h5>
    <p class="headline">{{report.headline}}</p><p>{{report.reason}}</p>
    <p v-if="report.cleanup" class="cleanup-note"><b>중단 정리</b> {{report.cleanup.note}}<span v-if="report.cleanup.finding"> · {{report.cleanup.finding}}</span></p>
    <div v-if="report.findings?.length"><b>현장 소견</b><ul><li v-for="f in report.findings" :key="f.order">{{f.say}} — {{f.finding}}</li></ul></div>
    <table class="grid"><thead><tr><th>측정</th><th>승인 시점</th><th>정비 뒤</th></tr></thead>
      <tbody><tr v-for="r in report.before_after" :key="r.tag"><td>{{r.tag}}</td><td class="num">{{r.before?.toFixed?.(2)??'—'}}</td><td class="num">{{r.after?.toFixed?.(2)??'—'}}</td></tr></tbody></table>
    <table class="grid"><thead><tr><th>KPI</th><th>예상</th><th>실적</th></tr></thead><tbody>
      <tr><td>생산 손실(정지 {{report.kpi.actual.downtime_plant_h}} h{{report.kpi.actual.batch_scrapped?' · 배치 폐기':''}})</td><td class="num">{{won(report.kpi.predicted['KPI-PRODUCTION-LOSS']??0)}}</td><td class="num">{{won(report.kpi.actual.production_loss)}}</td></tr>
      <tr><td>정비 비용(작업 {{report.kpi.actual.field_work_plant_h}} h{{report.kpi.actual.parts.length?' · '+report.kpi.actual.parts.map(p=>p.item).join(', '):''}})</td><td class="num">{{won(report.kpi.predicted['KPI-MAINT-COST']??0)}}</td><td class="num">{{won(report.kpi.actual.maint_cost)}}</td></tr>
      <tr v-if="report.kpi.actual.quality_loss!==undefined"><td>품질 손실({{report.kpi.actual.over_limit_tag}} 상한 초과 {{report.kpi.actual.over_limit_plant_h}} h)</td><td class="num">{{won(report.kpi.predicted['KPI-QUALITY-LOSS']??0)}}</td><td class="num">{{won(report.kpi.actual.quality_loss)}}</td></tr>
      <tr v-if="report.kpi.actual.equipment_risk!==undefined"><td>설비·안전 위험({{report.kpi.actual.over_limit_tag}} 상한 초과 {{report.kpi.actual.over_limit_plant_h}} h)</td><td class="num">{{won(report.kpi.predicted['KPI-EQUIPMENT-RISK']??0)}}</td><td class="num">{{won(report.kpi.actual.equipment_risk)}}</td></tr>
    </tbody></table>
    <p class="kpi-note">실적은 정비 실행 구간(승인 → 종료)의 기록으로 계산합니다. 분석·검토에 걸린 시간은 넣지 않습니다.</p>
    <p class="next"><b>다음:</b> {{report.next}}</p>
  </section>
</div>
</template>

<style scoped>
.plan-card{margin:14px 0;font-size:var(--ui-font-caption);line-height:1.75;color:#2b3f38}
.plan-head{display:flex;justify-content:space-between;align-items:flex-start;gap:10px;flex-wrap:wrap}.plan-head small{color:#5b7469}.plan-head h4{margin:4px 0;font-size:var(--ui-font-input);color:#1d4a3f}
.badge{border-radius:999px;padding:4px 10px;font-size:12px;white-space:nowrap}.badge.ok{background:#e4f3ec;color:#17694f}.badge.warn{background:#fff1e0;color:#8a5317}
section{margin:16px 0}h5{font-size:var(--ui-font-body);margin:0 0 8px;color:#21463c}h5 small{font-weight:400;color:#6b7f76;margin-left:6px}
.summary-blocks{display:grid;gap:8px}.summary-blocks article{border-left:3px solid #8cc2ad;background:#f6faf8;padding:8px 12px;border-radius:0 8px 8px 0}.summary-blocks b{color:#1f6a55}.summary-blocks p{margin:3px 0 0;white-space:pre-wrap;overflow-wrap:anywhere}
.table-scroll{overflow-x:auto}.grid{width:100%;border-collapse:collapse}.grid th,.grid td{border:1px solid #dce6e2;padding:7px 8px;text-align:left;vertical-align:top}.grid thead{background:#eef4f2}.grid small{color:#6b7f76}
.num{text-align:right!important;font-variant-numeric:tabular-nums;white-space:nowrap}.total{font-weight:700}
.options tr.chosen{background:#e9f6ef;outline:2px solid #69b38f}.options tr.excluded{color:#8a7f7a;background:#faf6f4}.options tr.ineligible{color:#9aa5a1}
.pill{display:inline-block;border-radius:999px;padding:2px 8px;background:#edf1f0;margin:2px 4px 2px 0;font-size:12px;white-space:nowrap}.pill.supported{background:#dff2e8;color:#16684d}.pill.refuted{background:#fbe7e2;color:#9a3b25}.pill.unknown{background:#f1efe6;color:#6f6538}
tr.refuted td{color:#7d8a85}.field-note{color:#6b7f76}
.flips{background:#fbf7ec;border:1px solid #eee0bd;border-radius:8px;padding:8px 12px;margin-top:10px}.flips ul{margin:4px 0;padding-left:18px}
details{margin-top:8px}summary{cursor:pointer;color:#2d6657}
.steps{list-style:none;padding:0;margin:0;display:grid;gap:6px}.step{display:grid;grid-template-columns:76px 1fr auto;gap:10px;align-items:start;border:1px solid #dfe8e4;border-radius:8px;padding:8px 10px;background:#fff}
.step .kind{font-size:12px;background:#eef4f2;border-radius:6px;padding:2px 6px;text-align:center;color:#2f5a4e}.step .state{font-size:12px;color:#5b6f66;white-space:nowrap}
.step.sent,.step.running{border-color:#7fb9a2;background:#f3fbf7}.step.done,.step.done_no_fault{opacity:.85}.step.failed,.step.no_fault{border-color:#e2a594;background:#fff6f3}
.finding{margin:4px 0 0;color:#22524a}.fail-note{margin:4px 0 0;color:#99412b}.operator-note{margin:4px 0 0;color:#8a5317}
.operator-banner{background:#fff1e0;border:1px solid #f0c48e;color:#7a4612;padding:8px 12px;border-radius:8px;font-weight:600}
.criteria{padding-left:0;list-style:none;margin:0}.criteria li{margin:3px 0}
.verify .bar{height:8px;background:#e7eeeb;border-radius:4px;overflow:hidden;margin:6px 0 2px}.verify .bar span{display:block;height:100%;background:#2f8f6c;transition:width .5s}
.sparks{display:grid;grid-template-columns:repeat(auto-fill,minmax(200px,1fr));gap:8px;margin-top:8px}.sparks figure{margin:0;border:1px solid #e1e9e6;border-radius:8px;padding:6px}.sparks svg{width:100%;height:56px}.sparks figcaption{font-size:12px}
.report{border:1px solid #cfe1d9;border-radius:10px;padding:12px 14px;background:#f7fbf9}.report.ok{border-color:#8fcbb1}.report.bad{border-color:#e4ad9d;background:#fff8f5}
.report .headline{font-size:var(--ui-font-input);font-weight:700;margin:2px 0}.report.ok .headline{color:#17694f}.report.bad .headline{color:#9a3b25}.report table{margin:8px 0}.next{margin:6px 0 0}.cleanup-note{background:#fff6ec;border-radius:6px;padding:6px 10px;margin:6px 0}.kpi-note{font-size:12px;color:#6b7f76;margin:2px 0 6px}
@media(max-width:650px){.step{grid-template-columns:1fr}.step .state{justify-self:start}}
</style>
