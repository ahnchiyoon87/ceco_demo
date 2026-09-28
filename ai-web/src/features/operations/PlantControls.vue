<script setup>
import { computed, ref, onMounted } from 'vue'
import ThermalResponse from './ThermalResponse.vue'
const props=defineProps({plant:Object,stale:Boolean})
const emit=defineEmits(['updated'])
const devices=[['pump_run','P-101 공급펌프'],['agitator_run','M-101 교반기'],['heater_enable','HX-101 히터'],['cooler_enable','HX-102 냉각기']]
const availableDevices=computed(()=>devices.filter(([key])=>key!=='cooler_enable'||typeof props.plant?.commands?.cooler_enable==='boolean'))
const settings=[['pump_speed_sp','펌프 속도','%',0,100,1],['valve_open_sp','밸브 열림','%',0,100,1],['temp_sp_c','목표 온도','°C',20,100,0.1]]
const draft=ref({}),pending=ref(''),result=ref(null),error=ref('')
const history=ref([]),historyError=ref('')
const label=key=>[...devices,...settings].find(item=>item[0]===key)?.[1]||key
const format=(key,value)=>devices.some(item=>item[0]===key)?(value?'운전':'정지'):(value??'—')
const stamp=value=>new Date(value).toLocaleString('ko-KR')
async function loadHistory(){try{const r=await fetch('/api/operations/simulation/controls',{signal:AbortSignal.timeout(8000)});if(!r.ok)throw new Error('조작 이력을 조회하지 못했습니다.');history.value=(await r.json()).items;historyError.value=''}catch(e){historyError.value=e.message}}
onMounted(loadHistory)
async function apply(target,value){
  if(pending.value||props.stale)return
  pending.value=target;error.value='';result.value=null
  try{
    const response=await fetch('/api/operations/simulation/control',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({request_id:crypto.randomUUID(),target,value:Number(value)}),signal:AbortSignal.timeout(20000)})
    const data=await response.json()
    if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'입력 범위와 연결 상태를 확인하세요.')
    result.value=data
    if(data.status==='verified')delete draft.value[target]
  }catch(e){error.value=e.name==='TimeoutError'?'응답이 늦습니다. 현재 상태로 실행 여부를 확인하세요. 자동 재전송하지 않습니다.':e.message}
  finally{pending.value='';emit('updated');loadHistory()}
}
</script>
<template>
  <section class="plant-controls" aria-label="설비 직접 조작" tabindex="-1">
    <header><h3>설비 직접 조작</h3><span>교육용 가상 설비</span></header>
    <p class="help">기동·정지는 즉시 요청합니다. 설정값은 입력 후 <b>적용</b>을 누르세요.</p>
    <div v-for="[key,label] in availableDevices" :key="key" class="device-row">
      <div><b>{{label}}</b><span>{{stale?'상태 미확인':plant?.commands?.[key]?'운전 중':'정지'}}</span></div>
      <button :disabled="stale||!!pending||plant?.commands?.[key]||plant?.interlock" @click="apply(key,1)" :aria-label="label+' 기동'">기동</button>
      <button class="stop" :disabled="stale||!!pending||!plant?.commands?.[key]" @click="apply(key,0)" :aria-label="label+' 정지'">정지</button>
    </div>
    <form v-for="[key,label,unit,min,max,step] in settings" :key="key" class="setting-row" @submit.prevent="apply(key,draft[key])">
      <label :for="'set-'+key"><b>{{label}}</b><span>현재 설정 {{stale?'미확인':plant?.commands?.[key]??'—'}} {{unit}}</span></label>
      <div><input :id="'set-'+key" v-model="draft[key]" type="number" :min="min" :max="max" :step="step" required :placeholder="min+'~'+max" :disabled="stale||!!pending"/><span>{{unit}}</span><button :disabled="stale||!!pending||draft[key]===undefined||draft[key]===''">적용</button></div>
    </form>
    <p class="help">목표 온도는 원하는 값입니다. 실제 온도가 즉시 같아지지는 않습니다. 수동 설정 후 약 5분이 지나면 시뮬레이터 자동 운전 설정이 다시 움직일 수 있습니다.</p>
    <div v-if="pending" role="status" class="feedback">명령 전송 → 새 설비 상태 확인 중…</div>
    <div v-if="result" role="status" class="feedback" :class="{warning:result.status!=='verified'}"><b>{{result.status==='verified'?'반영 확인':'확인 필요'}}</b><p>{{result.reason}}</p><p v-if="result.after">{{label(result.target)}} · {{format(result.target,result.before.commands[result.target])}} → {{format(result.target,result.after.commands[result.target])}} · SCAN {{result.before.seq}} → {{result.after.seq}}</p></div>
    <p v-if="error" role="alert" class="feedback warning">{{error}}</p>
    <p v-if="result?.target==='cooler_enable' && result.after?.thermal_model" class="help">명령 확인 시점의 교육용 모형: 열 공급 {{result.after.thermal_model.heater_kw}} kW · 열 제거 {{result.after.thermal_model.cooler_kw}} kW (SCAN {{result.after.seq}}). 모형 내부 계산값이며 실제 열량 센서 측정값은 아닙니다. 이후 온도 변화는 아래에서 확인하세요.</p>
    <ThermalResponse :plant="plant" :stale="stale" :command="result" />
    <details class="operator-history"><summary>직접 조작 이력 · {{history.length}}건</summary><p class="help">저장된 조작 당시 결과입니다. 현재 상태는 위 운전값을 확인하세요.</p><button type="button" @click="loadHistory">이력 새로고침</button><p v-if="historyError" role="alert">{{historyError}}</p><article v-for="item in history" :key="item.id"><b>{{label(item.request.target)}} · {{format(item.request.target,item.request.value)}} 요청</b><small>{{stamp(item.created_at)}}</small><p>{{item.result.status==='verified'?'반영 확인':item.result.status==='not_executed'?'미실행':'확인 필요'}} · {{item.result.reason}}</p><p v-if="item.result.after">{{format(item.request.target,item.result.before.commands[item.request.target])}} → {{format(item.request.target,item.result.after.commands[item.request.target])}}</p></article></details>
  </section>
</template>
<style scoped>
button{white-space:nowrap;flex-shrink:0}.setting-row input{flex:1;width:0!important}
.operator-history{margin-top:16px;font-size:var(--ui-font-caption);line-height:var(--ui-line-height)}.operator-history summary{cursor:pointer;padding:8px 0}.operator-history article{border-top:1px solid #37576b;padding:12px 0}.operator-history small{display:block;color:#b5c9d8}.operator-history p{margin:5px 0}
.plant-controls{background:#142738;border:1px solid #37576b;border-radius:var(--ui-radius-card);padding:20px;color:#e1edf5}.plant-controls header{display:flex;justify-content:space-between;align-items:center;gap:12px}.plant-controls h3{margin:0;font-size:var(--ui-font-heading)}.plant-controls header span,.help{color:#b5c9d8;font-size:var(--ui-font-caption);line-height:var(--ui-line-height)}.device-row{display:flex;align-items:center;gap:8px;padding:13px 0;border-bottom:1px solid #345065}.device-row>div{flex:1}.device-row span,.setting-row label span{display:block;color:#a9c8d5;font-size:var(--ui-font-caption);margin-top:5px}button{background:#176d60;color:#fff;border:1px solid #63b6a8;border-radius:var(--ui-radius-control);padding:9px 13px;cursor:pointer}.stop{background:#743e3b;border-color:#c17c75}button:disabled{opacity:.4;cursor:not-allowed}.setting-row{padding-top:16px}.setting-row>div{display:flex;align-items:center;gap:8px;margin-top:7px}.setting-row input{min-width:0;width:100%;box-sizing:border-box;color:#eef8ff;background:#0c1d2b;border:1px solid #799bad;border-radius:var(--ui-radius-control);padding:10px;font-size:var(--ui-font-input)}.feedback{background:#19493e;padding:12px;border-radius:8px;font-size:var(--ui-font-caption);line-height:var(--ui-line-height)}.feedback p{margin:5px 0}.warning{background:#523d25;color:#ffe0b1}button:focus-visible,input:focus-visible{outline:3px solid #ffe195;outline-offset:3px}
</style>
