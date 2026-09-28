<script setup>
import {computed} from 'vue'
const props=defineProps({graph:Object,loading:Boolean,error:String})
const sensors=computed(()=>props.graph.nodes.filter(n=>n.labels?.includes('Sensor')))
const linked=computed(()=>new Set(props.graph.edges.filter(e=>e.type==='HAS_SENSOR').map(e=>e.to)))
const missing=computed(()=>sensors.value.filter(n=>!linked.value.has(n.id)))
const count=label=>props.graph.nodes.filter(n=>n.labels?.includes(label)).length
</script>
<template>
<section class="knowledge-coverage" aria-label="지식 연결 현황"><header><div><p class="eyebrow">KNOWLEDGE COVERAGE</p><h2>자료가 판단 근거로 연결되어 있나요?</h2></div><span>{{loading?'조회 중':error?'마지막 조회값':'현재 조회 그래프 기준'}}</span></header><div class="coverage-metrics"><article><b>{{graph.nodes.length}}</b><span>노드</span></article><article><b>{{graph.edges.length}}</b><span>관계</span></article><article><b>{{count('Asset')}}</b><span>설비</span></article><article><b>{{count('Document')}}</b><span>문서</span></article><article><b>{{sensors.length-missing.length}} / {{sensors.length}}</b><span>설비 소속이 연결된 센서</span></article></div><p class="coverage-path">자료 등록 → 구조·관계 후보 생성 → 출처 검토 → 그래프 게시 → 이상 대응에서 조회</p><details v-if="missing.length"><summary>설비 소속 연결을 확인할 센서 {{missing.length}}개</summary><p>{{missing.map(n=>n.label).join(' · ')}}</p><p>원본에서 소속을 확인한 뒤 관계 후보를 만들고 검토하세요. 관계 개수만으로 정확성이나 대응 가능성을 판단할 수는 없습니다.</p></details></section>
</template>
<style scoped>
.knowledge-coverage{background:#f1f7f7;border:1px solid #cddfe1;padding:var(--ui-space-panel);border-radius:var(--ui-radius-card);margin-bottom:24px}.knowledge-coverage header{display:flex;justify-content:space-between;gap:var(--ui-space-lg);flex-wrap:wrap}.knowledge-coverage h2{margin:0;font-size:20px}.knowledge-coverage header>span{font-size:var(--ui-font-caption);color:#526b76}.coverage-metrics{display:grid;grid-template-columns:repeat(4,1fr) 2fr;gap:12px;margin-top:20px}.coverage-metrics article{background:var(--ui-surface);border:1px solid #dce8e8;border-radius:var(--ui-radius-control);padding:14px}.coverage-metrics b{display:block;font-size:26px;color:#176657}.coverage-metrics span,.coverage-path,details{font-size:var(--ui-font-caption);color:#425b69}.coverage-path{margin-top:18px}details{border-top:1px solid #ccdedf;padding-top:14px}summary{cursor:pointer;font-weight:650}@media(max-width:650px){.coverage-metrics{grid-template-columns:1fr 1fr}.coverage-metrics article:last-child{grid-column:1/-1}.knowledge-coverage{padding:16px}}
</style>
