<script setup>
import {computed} from 'vue'
const props=defineProps({track:{type:Object,required:true}})
const labels={observing:'온도 관측 중',unknown:'새 관측 확인 필요',temperature_stable:'목표 범위 유지 확인',interrupted:'조건 변경 · 관측 중단',timeout:'관측 시간 초과'}
const latest=computed(()=>props.track.samples?.at(-1))
const chart=computed(()=>{
  const points=props.track.samples||[]
  if(!points.length)return null
  const low=Math.floor(Math.min(props.track.target-1,...points.map(p=>p.value))-1)
  const high=Math.ceil(Math.max(props.track.target+1,...points.map(p=>p.value))+1)
  const first=points[0].at,last=Math.max(first+1,points.at(-1).at)
  const y=value=>140-(value-low)/(high-low)*115
  return {low,high,target:y(props.track.target),path:points.map(p=>`${48+(p.at-first)/(last-first)*390},${y(p.value)}`).join(' '),seconds:Math.round(last-first)}
})
</script>
<template>
<section class="thermal-observation" aria-label="승인 조치 후 서버 온도 관측">
 <header><h4>조치 후 실제 온도</h4><b role="status">{{labels[track.status]||'관측 상태 확인 필요'}}</b></header>
 <div class="thermal-metrics"><span>승인 시 목표<strong>{{track.target}}°C</strong></span><span>마지막 관측<strong>{{latest?.value?.toFixed(2)??'—'}}°C</strong></span><span>범위 유지<strong>{{Math.floor(track.held_s||0)}} / 30초</strong></span></div>
 <p>{{track.reason}}</p>
 <svg v-if="chart" viewBox="0 0 470 170" role="img" aria-label="저장된 온도 관측 실선과 승인 목표 점선"><path d="M48 20V140H438" fill="none" stroke="#718899"/><path :d="`M48 ${chart.target}H438`" stroke="#a56a10" stroke-dasharray="5 4"/><polyline :points="chart.path" fill="none" stroke="#147e70" stroke-width="2"/><text x="1" y="25">{{chart.high}}°C</text><text x="1" y="140">{{chart.low}}°C</text><text x="48" y="161">표시 구간 시작</text><text x="370" y="161">{{chart.seconds}}초</text></svg>
 <p v-if="latest">마지막 수신 {{new Date(latest.at*1000).toLocaleString('ko-KR')}} · SCAN {{latest.seq}}. 최근 최대 200개 관측을 표시합니다.</p>
 <p>서버에 저장되는 관측입니다. 화면을 닫아도 이어집니다. 통신·서버 중단 동안의 유지 시간은 인정하지 않습니다. 목표 ±1°C에서 30초 유지 확인은 원인 제거·정비 완료가 아닙니다.</p>
</section>
</template>
<style scoped>
.thermal-observation{margin:var(--ui-space-lg) 0;padding:var(--ui-space-panel);border:1px solid var(--ui-border);border-radius:var(--ui-radius-card);background:var(--ui-surface-muted);color:var(--ui-text)}
header{display:flex;justify-content:space-between;gap:var(--ui-space-md);flex-wrap:wrap}h4{font-size:var(--ui-font-heading);margin:0}header b,p{font-size:var(--ui-font-caption);line-height:var(--ui-line-height)}
.thermal-metrics{display:flex;flex-wrap:wrap;gap:var(--ui-space-panel);margin-top:var(--ui-space-lg);font-size:var(--ui-font-caption)}strong{display:block;font-size:var(--ui-font-heading)}svg{display:block;width:100%;max-height:240px}text{font-size:13px;fill:#526b76}
</style>
