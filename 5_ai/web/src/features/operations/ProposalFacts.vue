<script setup>
import {computed} from 'vue'
import {actionPresentation} from './actionPresentation.js'
const props=defineProps({proposal:Object,mode:{type:String,default:'all'}})
const before=computed(()=>props.proposal.evidence?.analysis_plant_state)
const after=computed(()=>props.proposal.result?.observations?.at(-1))
const documents=computed(()=>props.proposal.evidence?.graph?.documents||[])
const value=(state,tag)=>typeof state?.readings?.[tag]==='number'?state.readings[tag].toFixed(2):'확인값 없음'
const motor=state=>state?.commands?.agitator_run===true?'운전':state?.commands?.agitator_run===false?'정지':'미확인'
const cooling=state=>state?.commands?.cooler_enable===true?'켜짐':state?.commands?.cooler_enable===false?'꺼짐':'미확인'
</script>
<template>
<div class="proposal-facts">
 <div class="fact-cards"><article><small>제안된 조치</small><h4>{{actionPresentation(proposal.body.action).title}}</h4><p>{{actionPresentation(proposal.body.action).description}}</p></article><article><small>판단에 연결된 자료</small><h4>설비 {{proposal.evidence?.graph?.assets?.length||0}}개 · 문서 {{documents.length}}개</h4><p>AI가 조회한 센서·문서 기록입니다. 원인 확정이나 수리 완료를 의미하지 않습니다.</p></article></div>
 <div v-if="mode!=='review' && proposal.body.action!=='enable_cooling'" class="comparison"><h4>관측값과 조치 결과</h4><table><thead><tr><th>항목</th><th>AI 조회 당시</th><th>{{proposal.result?'조치 후 확인':'조치 후 · 대기'}}</th></tr></thead><tbody><tr><th>교반기</th><td>{{motor(before)}}</td><td>{{motor(after)}}</td></tr><tr><th>전류 · A</th><td>{{value(before,'IT-102')}}</td><td>{{value(after,'IT-102')}}</td></tr><tr><th>진동 · mm/s</th><td>{{value(before,'VT-101')}}</td><td>{{value(after,'VT-101')}}</td></tr><tr><th>상태 번호</th><td>{{before?.seq??'—'}}</td><td>{{after?.seq??'—'}}</td></tr></tbody></table><p>저장된 시점의 값입니다. 정지 직후 전류·진동이 안정되는 데 시간이 걸릴 수 있습니다. 점검 요청만 기록한 경우에는 조치 후 설비값이 없습니다.</p></div>
 <div v-if="mode!=='review' && proposal.body.action==='enable_cooling'" class="comparison"><h4>냉각 명령과 온도 관측</h4><table><thead><tr><th>항목</th><th>AI 조회 당시</th><th>명령 후 확인</th></tr></thead><tbody><tr><th>냉각 명령</th><td>{{cooling(before)}}</td><td>{{cooling(after)}}</td></tr><tr><th>목표 · °C</th><td>{{before?.commands?.temp_sp_c??'미확인'}}</td><td>{{after?.commands?.temp_sp_c??'미확인'}}</td></tr><tr><th>반응기 · °C</th><td>{{value(before,'TT-101')}}</td><td>{{value(after,'TT-101')}}</td></tr><tr><th>상태 번호</th><td>{{before?.seq??'—'}}</td><td>{{after?.seq??'—'}}</td></tr></tbody></table><p>저장된 시점의 값입니다. 냉각 명령이 켜졌다는 사실만으로 온도 안정이나 원인 제거를 확인할 수는 없습니다.</p></div>
 <details><summary>참조한 문서와 적용 버전 · {{documents.length}}개</summary><article v-for="doc in documents" :key="doc.document_id" class="document-proof"><b>{{doc.document_id}} · v{{doc.version}}</b><p>{{doc.source_path}}</p><details><summary>문서 내용 읽기</summary><pre>{{doc.content}}</pre></details></article></details>
</div>
</template>
<style scoped>
.proposal-facts{margin:18px 0}.fact-cards{display:grid;grid-template-columns:1fr 1fr;gap:12px}.fact-cards article{background:#f1f7f6;border:1px solid #d1e3dd;padding:16px;border-radius:10px}.fact-cards small{font-size:var(--ui-font-caption);color:#426b60}.fact-cards h4,.comparison h4{font-size:var(--ui-font-input);margin:7px 0;color:#234b42}.fact-cards p,.comparison p{font-size:var(--ui-font-caption);line-height:1.8;color:#4d6671;margin:6px 0}.comparison{margin:18px 0}.comparison table{width:100%;border-collapse:collapse;font-size:var(--ui-font-caption)}.comparison td,.comparison th{text-align:left;padding:10px;border:1px solid #dce5e9}.comparison thead{background:#edf3f6}.comparison td{font-variant-numeric:tabular-nums}details{font-size:var(--ui-font-caption);margin:12px 0;border:1px solid #dae4e9;padding:12px;border-radius:8px}summary{cursor:pointer;color:#275b63;font-weight:650}.document-proof{margin:12px 0;padding:8px}.document-proof p{font-size:var(--ui-font-caption);overflow-wrap:anywhere;color:#536d77}.document-proof pre{white-space:pre-wrap;font:13px/1.9 inherit;max-height:320px;overflow:auto}@media(max-width:650px){.fact-cards{grid-template-columns:1fr}.comparison td,.comparison th{padding:7px;font-size:var(--ui-font-caption)}}
</style>
