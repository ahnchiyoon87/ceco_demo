<script setup>
import { computed } from 'vue'
const props = defineProps({ properties: { type:Object, default:()=>({}) } })
const labels = {description:'설명',unit:'측정 단위',lsl:'기준 하한',usl:'기준 상한',version:'문서 버전',source_path:'원본 위치',source_excerpt:'원본 인용',mapping_reason:'연결한 이유',content:'문서 내용',site:'현장',device:'대상 장치'}
const value = item => typeof item === 'object' ? JSON.stringify(item,null,2) : String(item)
const useful = item => item !== undefined && item !== null && item !== ''
const summary = computed(()=>Object.entries(labels).filter(([key])=>useful(props.properties[key])).map(([key,label])=>({key,label,value:value(props.properties[key])})))
const extra = computed(()=>Object.fromEntries(Object.entries(props.properties).filter(([key,item])=>!Object.hasOwn(labels,key)&&key!=='embedding'&&useful(item))))
</script>
<template>
  <section class="graph-evidence" aria-label="저장된 설명과 출처">
    <dl v-if="summary.length">
      <div v-for="item in summary" :key="item.key">
        <dt>{{item.label}}</dt>
        <dd v-if="item.value.length<=240">{{item.value}}</dd>
        <dd v-else><details><summary>{{item.value.slice(0,160)}}… <span>전체 보기</span></summary><pre>{{item.value}}</pre></details></dd>
      </div>
    </dl>
    <p v-else class="no-evidence">별도로 저장된 설명·원문 인용이 없습니다.</p>
    <details v-if="Object.keys(extra).length" class="technical-properties"><summary>식별자·검토 기록 등 세부 속성 {{Object.keys(extra).length}}개</summary><pre>{{JSON.stringify(extra,null,2)}}</pre></details>
  </section>
</template>
<style scoped>
.graph-evidence{font-size:var(--ui-font-caption);line-height:var(--ui-line-height);min-width:0;margin:10px 0}.graph-evidence dl{margin:0}.graph-evidence dl>div{display:grid;grid-template-columns:90px minmax(0,1fr);gap:12px;padding:8px 0;border-bottom:1px solid #e2e9ee}.graph-evidence dt{color:#597080;font-weight:600}.graph-evidence dd{margin:0;white-space:pre-wrap;overflow-wrap:anywhere}.graph-evidence summary{cursor:pointer;overflow-wrap:anywhere}.graph-evidence summary span{color:#147666;font-weight:600}.graph-evidence pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:320px;overflow:auto;background:#edf2f5;padding:12px;border-radius:8px;font-size:12px}.technical-properties{margin-top:12px;color:#586c7d}.no-evidence{color:#637c8a}@media(max-width:650px){.graph-evidence dl>div{grid-template-columns:1fr;gap:3px}}
</style>
