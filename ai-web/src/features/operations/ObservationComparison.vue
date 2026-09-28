<script setup>
import { computed } from 'vue'
const props=defineProps({evidence:{type:Object,required:true}})
const emit=defineEmits(['refresh'])
const tags=['IT-102','VT-101','LT-102']
const time=value=>new Date(value).toLocaleString('ko-KR')
const series=computed(()=>tags.map(tag=>{
  const current=(props.evidence.current_history?.rows||[]).filter(r=>r.tag===tag)
  const earlier=(props.evidence.history?.rows||[]).filter(r=>r.tag===tag)
  const values=current.map(r=>r.value)
  const min=Math.min(...values),max=Math.max(...values)
  const points=values.map((value,index)=>`${8+index*204/Math.max(values.length-1,1)},${max===min?32:56-(value-min)*48/(max-min)}`).join(' ')
  return {tag,current,earlier,points,min,max,last:current.at(-1),peak:earlier.length?Math.max(...earlier.map(r=>r.value)):null,unit:props.evidence.graph.sensors?.find(s=>s.tag===tag)?.unit||''}
}))
</script>
<template>
  <section class="observation-comparison">
    <div class="comparison-heading"><h3>현재 관측과 사건 당시</h3><button @click="emit('refresh')">근거 다시 조회</button></div>
    <p class="panel-hint">현재 구간은 조회 시점의 최근 30초입니다. 각 그래프의 세로 범위는 자동 조정됩니다.</p>
    <p v-if="evidence.current_history?.status!=='available'" class="mfg-error">현재 관측을 확인할 수 없습니다. {{evidence.current_history?.error}}</p>
    <div class="comparison-grid"><article v-for="sensor in series" :key="sensor.tag"><header><b>{{sensor.tag}}</b><span>{{sensor.unit}}</span></header><strong>{{sensor.last?sensor.last.value.toFixed(2):'—'}}</strong><small>{{sensor.last?time(sensor.last.time)+' 측정':'현재 관측 없음'}}</small><svg v-if="sensor.current.length" viewBox="0 0 220 64" role="img" :aria-label="sensor.tag+' 최근 관측 추세'"><path d="M8 56 H212" stroke="#e3ede8"/><polyline :points="sensor.points" fill="none" stroke="#178774" stroke-width="2"/></svg><p v-if="sensor.current.length" class="chart-range">{{sensor.min.toFixed(2)}} ~ {{sensor.max.toFixed(2)}} · {{sensor.current.length}}건</p><footer><span>사건 당시 최댓값</span><b>{{sensor.peak===null?'미확인':sensor.peak.toFixed(2)}}</b></footer><p v-if="sensor.last" :class="{warning:sensor.last.quality!=='GOOD'}" class="quality-note">마지막 값 품질: {{sensor.last.quality}}</p></article></div>
  </section>
</template>
<style scoped>
.observation-comparison{margin:22px 0}.comparison-heading{display:flex;justify-content:space-between;align-items:center}.comparison-heading h3{margin:0!important}.comparison-heading button{border:0;background:none;color:#23816e;font-size:var(--ui-font-caption)}.comparison-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.comparison-grid article{padding:13px;border:1px solid #dde8e1;border-radius:8px;background:#fbfdfc;min-width:0}.comparison-grid header{display:flex;justify-content:space-between;font-size:var(--ui-font-caption)}.comparison-grid header span{color:#93a398;font-size:var(--ui-font-caption)}.comparison-grid strong{display:block;font-size:23px;font-weight:600;margin:10px 0 1px;font-variant-numeric:tabular-nums}.comparison-grid small{font-size:var(--ui-font-caption);color:#8b9a92}.comparison-grid svg{display:block;width:100%;margin-top:8px}.chart-range{font-size:var(--ui-font-caption);color:#8da197;margin:3px 0 12px}.comparison-grid footer{border-top:1px solid #e3eae6;padding-top:9px;display:flex;justify-content:space-between;font-size:var(--ui-font-caption);gap:7px;color:#819489}.comparison-grid footer b{color:#516e5d;font-variant-numeric:tabular-nums}.quality-note{font-size:var(--ui-font-caption);color:#67927b;margin-bottom:0}.quality-note.warning{color:#af7a26}@media(max-width:1150px){.comparison-grid{grid-template-columns:1fr}.comparison-grid svg{max-height:55px}.comparison-grid article{padding:12px 16px}}
</style>
