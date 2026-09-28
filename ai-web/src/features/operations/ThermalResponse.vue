<script setup>
import {computed,ref,watch,onUnmounted} from 'vue'
import {startThermal,observeThermal,thermalStatus} from './thermalResponse.js'
const props=defineProps({plant:Object,stale:Boolean,command:Object})
const track=ref(null),now=ref(Date.now())
const timer=setInterval(()=>now.value=Date.now(),1000)
onUnmounted(()=>clearInterval(timer))
function start(){if(!props.stale)track.value=startThermal(props.plant,Date.now())}
watch(()=>props.command,result=>{if(result?.status==='verified'&&['temp_sp_c','cooler_enable'].includes(result.target))track.value=startThermal(result.after,Date.now())})
watch(()=>props.plant,state=>{if(!props.stale)track.value=observeThermal(track.value,state,Date.now())})
watch(()=>props.stale,stale=>{if(stale&&track.value)track.value={...track.value,withinSince:null}})
const status=computed(()=>thermalStatus(track.value,now.value,props.stale))
const chart=computed(()=>{
  if(!track.value)return null
  const {samples,target,started}=track.value
  const low=Math.floor(Math.min(target-2,...samples.map(s=>s.value))-1)
  const high=Math.ceil(Math.max(target+2,...samples.map(s=>s.value))+1)
  const end=Math.max(started+30000,samples.at(-1).at)
  const y=v=>150-(v-low)/(high-low)*125
  return {low,high,targetY:y(target),points:samples.map(s=>`${45+(s.at-started)/(end-started)*340},${y(s.value)}`).join(' '),seconds:Math.round((end-started)/1000)}
})
</script>
<template>
<section class="thermal-response" aria-label="목표 온도와 실제 온도 관측">
 <header><h4>설정 적용 후 실제 온도</h4><button :disabled="stale" @click="start">{{track?'현재 목표로 관측 다시 시작':'현재 목표 관측 시작'}}</button></header>
 <p class="thermal-status" :class="status.kind" role="status">{{status.label}}</p>
 <template v-if="track">
 <div class="thermal-values"><span>목표 <b>{{track.target.toFixed(1)}}°C</b></span><span>{{stale?'마지막 관측':'최근 관측'}} <b>{{track.samples.at(-1).value.toFixed(2)}}°C</b></span><span>범위 유지 <b>{{Math.floor((status.held||0)/1000)}} / 30초</b></span></div>
 <svg v-if="chart" viewBox="0 0 420 180" role="img" aria-label="시간별 실제 온도 실선과 목표 온도 점선">
  <path d="M45 20V150H385" fill="none" stroke="#7094a8"/>
  <path :d="`M45 ${chart.targetY}H385`" stroke="#ffd37d" stroke-dasharray="5 4"/>
  <polyline :points="chart.points" fill="none" stroke="#7ce3c6" stroke-width="2"/>
  <text x="2" y="28">{{chart.high}}°C</text><text x="2" y="150">{{chart.low}}°C</text><text x="45" y="170">0초</text><text x="345" y="170">{{chart.seconds}}초</text>
 </svg>
 <p>실선: 실제 온도 · 점선: 요청 목표. {{new Date(track.started).toLocaleTimeString('ko-KR')}}부터 이 화면에서 수신한 값입니다.</p>
 </template>
 <p>교육용 확인 기준: 목표 ±1°C에서 새 관측값이 30초 이어지는지 확인합니다. 이상 원인 제거나 정비 완료 판정은 아닙니다. 화면을 닫으면 관측은 종료됩니다.</p>
 <p v-if="typeof plant?.commands?.cooler_enable==='boolean'">냉각 명령: {{stale?'상태 미확인':plant.commands.cooler_enable?'켜짐':'꺼짐'}}. 켜짐은 명령 상태입니다. 실제 온도 변화와 범위 유지를 별도로 확인하세요. 냉각 고장이나 계속되는 열 공급 때문에 목표에 도달하지 못할 수 있습니다.</p>
 <p v-else>현재 연결된 설비에는 별도 냉각기 제어가 없습니다. 가열을 줄였다고 즉시 식지는 않으며 원료 유입·열 손실에 따라 달라집니다.</p>
</section>
</template>
<style scoped>
.thermal-response{margin-top:18px;border:1px solid #527486;border-radius:10px;padding:14px;background:#0e2030}.thermal-response header{display:flex;flex-wrap:wrap;gap:10px;align-items:center;justify-content:space-between}.thermal-response h4{margin:0;font-size:var(--ui-font-input)}.thermal-response button{padding:8px;border:1px solid #79b4a8;border-radius:6px;background:#174c43;color:white;font-size:var(--ui-font-caption);min-height:40px}.thermal-response button:disabled{opacity:.5}.thermal-response p{font-size:var(--ui-font-caption);line-height:var(--ui-line-height);color:#bad0dd}.thermal-status{font-weight:700;color:#ffe0a3!important}.thermal-status.held{color:#88e6c7!important}.thermal-values{display:flex;flex-wrap:wrap;gap:16px;font-size:var(--ui-font-caption)}.thermal-values b{display:block;font-size:17px;margin-top:3px}.thermal-response svg{width:100%;display:block;margin-top:10px}.thermal-response text{fill:#bad0dd;font-size:var(--ui-font-caption)}
</style>
