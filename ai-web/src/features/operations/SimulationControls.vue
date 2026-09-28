<script setup>
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import {trainingScenarios,injectionDisabledReason,findTrainingIncident} from './trainingScenarios.js'
const props=defineProps({incidents:{type:Array,default:()=>[]}})
const emit=defineEmits(['inspect','incident','control'])
const state=ref(null), pending=ref(''), error=ref(''), message=ref('')
const actionError=ref('')
const storageKey='ar100-training-track-v1'
let restored=null
try{restored=JSON.parse(sessionStorage.getItem(storageKey));if(!Number.isFinite(restored?.started)||restored.started>Date.now()||Date.now()-restored.started>86400000)restored=null}catch{}
const started=ref(restored?.started||0), tracked=ref(null), trackedId=ref(restored?.incidentId||null)
const scenarioId=ref(trainingScenarios.some(s=>s.id===restored?.scenario)?restored.scenario:'mixer')
const trackingScenario=ref(scenarioId.value), ended=ref(restored?.ended||'')
const scenario=computed(()=>trainingScenarios.find(s=>s.id===scenarioId.value))
const trackingTitle=computed(()=>trainingScenarios.find(s=>s.id===trackingScenario.value)?.title||'이상')
const disabledReason=computed(()=>injectionDisabledReason(state.value,scenarioId.value,!!pending.value))
function saveTrack(){try{sessionStorage.setItem(storageKey,JSON.stringify({started:started.value,incidentId:trackedId.value,scenario:trackingScenario.value,ended:ended.value}))}catch{}}
const elapsed=ref(0)
const match=computed(()=>findTrainingIncident(props.incidents,{started:started.value,incidentId:trackedId.value,
  scenario:trackingScenario.value,ended:ended.value,site:state.value?.site,device:state.value?.device},started.value+elapsed.value*1000))
watch(match,item=>{if(item&&!tracked.value){tracked.value=item;trackedId.value=item.id;saveTrack();emit('incident',item)}},{immediate:true})
let timer, alive=true
async function request(path, method='GET') {
  try{
    const r=await fetch('/api/operations/simulation'+path,{method,signal:AbortSignal.timeout(12000)})
    let data
    try{data=await r.json()}catch{throw new Error('실습 응답 형식을 확인하지 못했습니다. 현재 상태를 다시 확인하세요.')}
    if(!r.ok) throw new Error(typeof data.detail==='string'?data.detail:'실습 상태를 확인하지 못했습니다.')
    return data
  }catch(e){
    if(e.name==='TypeError'||e.name==='TimeoutError'||e.name==='AbortError')throw new Error('실습 연결을 확인하지 못했습니다. 연결이 돌아오면 현재 상태를 확인하세요. 요청을 자동 재전송하지 않습니다.')
    throw e
  }
}
async function load(){try{const data=await request('');if(alive){state.value=data;error.value=''}}catch(e){if(alive){state.value=null;error.value=e.message}}}
async function act(path){
  if(pending.value)return
  pending.value=path;message.value='';error.value='';actionError.value=''
  try{
    const at=Date.now(), selected=trainingScenarios.find(s=>s.path===path)
    await request(path,'POST')
    if(selected){started.value=at;trackingScenario.value=selected.id;tracked.value=null;trackedId.value=null;ended.value='';elapsed.value=0;saveTrack();emit('incident',null)}
    else if(path==='/clear'){ended.value='이상 주입 해제';saveTrack()}
    await load()
    message.value=path==='/clear'?'주입한 이상을 해제했습니다. 이미 생긴 사건과 설비 명령은 그대로이며, 온도가 즉시 정상으로 돌아오지는 않습니다.':selected?.id==='thermal'
      ?'20분 동안 히터의 열 공급이 계속됩니다. 온도는 서서히 변합니다. 실제 TT-101 알람이 접수되어야 다음 조사로 연결됩니다.'
      :'10분 동안 교반기 전류·진동이 증가합니다. 실제 알람 접수를 기다립니다.'
  }
  catch(e){actionError.value=e.message;await load()}
  finally{pending.value=''}
}
function tick(){
  load();elapsed.value=started.value?Math.floor((Date.now()-started.value)/1000):0
  const duration=trainingScenarios.find(s=>s.id===trackingScenario.value)?.duration||600
  if(started.value&&!tracked.value&&!ended.value&&elapsed.value>duration+60){ended.value='알람 확인 시간 종료';saveTrack()}
}
onMounted(()=>{tick();timer=setInterval(tick,5000)})
onUnmounted(()=>{alive=false;clearInterval(timer)})
</script>
<template>
  <section class="simulation-controls" aria-label="이상 대응 실습">
    <div class="sim-title"><span class="section-index">실습</span><div><h2>이상 대응을 직접 시험하세요</h2><p>① 이상 발생 → ② 사건 선택·AI 분석 → ③ 검토·승인 → ④ 실제 결과 확인</p></div><span class="sim-status">{{state ? Object.keys(state.active_faults).length ? '실습 이상 적용 중' : '주입한 이상 없음' : '상태 확인 필요'}}</span></div>
    <fieldset class="scenario-options"><legend>시험할 이상 선택 · 가상 설비에 적용</legend><label v-for="item in trainingScenarios" :key="item.id" :class="{chosen:scenarioId===item.id}"><input v-model="scenarioId" type="radio" name="training-scenario" :value="item.id" :disabled="!!pending"/><span><b>{{item.title}}</b><small>{{item.description}}</small></span></label></fieldset>
    <div class="sim-actions"><button class="primary-action" :disabled="!!disabledReason" aria-describedby="injection-conditions" @click="act(scenario.path)">{{pending&&pending!=='/clear'?'요청 중…':scenario.title+' 발생 · '+scenario.duration/60+'분'}}</button><button :disabled="!!pending||!state||!Object.keys(state.active_faults).length" @click="act('/clear')">{{pending==='/clear'?'해제 중…':'주입한 이상 모두 해제'}}</button><button @click="emit('inspect')">이상 대응 화면으로 →</button><button @click="emit('control')">설비 직접 조작 보기</button></div>
    <p id="injection-conditions" class="sim-help">{{disabledReason||'주입은 가상 고장을 적용합니다. 알람 생성·AI 분석·설비 조치가 즉시 완료되는 버튼은 아닙니다.'}}</p>
    <p v-if="scenarioId==='thermal'" class="sim-help">온도가 기준을 넘기까지 시간이 걸립니다. 냉각 명령이 켜져도 온도 안정이나 고장 수리가 확인된 것은 아닙니다.</p>
    <p v-for="(fault,name) in state?.active_faults" :key="name" class="sim-help">{{({bearing_wear:'교반기 전류·진동 이상',heater_stuck:'히터 열 공급 지속',cooling_loss:'냉각 성능 상실'})[name]||name}} · 남은 시간 약 {{Math.ceil(fault.remaining_s)}}초</p>
    <p v-if="message" role="status" class="sim-message">{{message}}</p>
    <p v-if="actionError" role="alert" class="sim-error"><b>직전 요청 결과 확인 필요</b><br>{{actionError}}<span v-if="state"><br>현재 상태 조회는 다시 연결되었습니다. 위에 표시된 적용 중인 이상을 확인하세요. 실패한 요청을 다시 보내지는 않았습니다.</span></p>
    <p v-else-if="error" role="alert" class="sim-error">{{error}}</p>
    <div v-if="started" class="injection-tracker" role="status"><b>{{trackingTitle}} · {{tracked?'관련 알람 접수 확인':ended||'알람 접수 대기'}}</b><p>{{tracked?'주입 뒤 같은 설비의 관련 센서 알람이 들어왔습니다. 주입이 원인이라는 확정은 아니며, 아래 AI 분석에서 근거를 조사합니다.':ended?'새 사건을 자동 연결하는 대기를 종료했습니다. 기존 사건은 이상 대응 화면에서 확인할 수 있습니다.':elapsed+'초 경과 · 센서 변화 → 수집 → 이상 검사 → 실제 알람 접수를 기다립니다.'}}</p><button v-if="tracked" @click="emit('incident',tracked)">이 사건 처리하기 · {{tracked.id.slice(0,8)}}</button><p v-if="!tracked&&!ended&&elapsed>90">아직 알람을 확인하지 못했습니다. 온도 추이와 수집·분석 연결 상태를 확인하세요. 이상을 중복 주입하지 마세요.</p></div>
  </section>
</template>
<style scoped>
.scenario-options{margin:var(--ui-space-lg) 0 0;padding:0;border:0;display:grid;grid-template-columns:1fr 1fr;gap:var(--ui-space-md)}
.scenario-options legend{font-size:var(--ui-font-caption);color:var(--ui-text-muted);margin-bottom:var(--ui-space-sm)}
.scenario-options label{display:flex;align-items:flex-start;gap:var(--ui-space-sm);padding:var(--ui-space-lg);border:1px solid var(--ui-border);border-radius:var(--ui-radius-card);cursor:pointer;color:var(--ui-text)}
.scenario-options label.chosen{background:var(--ui-selected-surface);border-color:var(--ui-selected-border)}
.scenario-options input{margin-top:5px;accent-color:#176f60}
.scenario-options b{font-size:var(--ui-font-body)}
.scenario-options small{display:block;margin-top:var(--ui-space-xs);font-size:var(--ui-font-caption);color:var(--ui-text-muted);line-height:var(--ui-line-height)}
@media(max-width:600px){.scenario-options{grid-template-columns:1fr}}
.simulation-controls{background:var(--ui-surface);border:1px solid var(--ui-border);border-radius:var(--ui-radius-card);padding:var(--ui-space-panel);margin:var(--ui-space-panel) 0}.sim-title{display:flex;align-items:center;gap:var(--ui-space-lg);flex-wrap:wrap}.section-index{background:#e2f3ef;color:#126b5b;padding:9px;border-radius:var(--ui-radius-card);font-weight:750}.sim-title h2{font-size:var(--ui-font-heading);margin:0}.sim-title p{font-size:var(--ui-font-caption);color:#526678;margin:5px 0}.sim-status{margin-left:auto;color:#466273;font-size:var(--ui-font-caption);padding:5px 10px;background:#f0f5f7;border-radius:20px}.sim-actions{display:flex;gap:var(--ui-space-sm);flex-wrap:wrap;margin-top:var(--ui-space-lg)}.sim-actions button,.sim-actions a{padding:11px 16px;border:1px solid #c9d7df;border-radius:var(--ui-radius-control);background:#fff;color:#314c60;font-size:var(--ui-font-caption);text-decoration:none}.sim-actions .primary-action{background:#146f60;border-color:#146f60;color:white;font-weight:700}.sim-actions button:disabled{opacity:.45;cursor:not-allowed}.sim-help,.sim-message,.sim-error{font-size:var(--ui-font-caption);line-height:var(--ui-line-height);margin:12px 0 0}.sim-help{color:#526678}.sim-message{color:#126b5b}.sim-error{color:#a23131}@media(max-width:600px){.simulation-controls{padding:16px}.sim-status{margin-left:0}.sim-actions>*{flex:1 1 180px;text-align:center}}
</style>
<style scoped>.injection-tracker{margin-top:var(--ui-space-lg);background:#eef7f4;border:1px solid #bbdcd0;border-radius:var(--ui-radius-card);padding:16px;font-size:var(--ui-font-body);color:#245e51}.injection-tracker p{font-size:var(--ui-font-caption);margin:6px 0;line-height:var(--ui-line-height)}.injection-tracker button{padding:10px 15px;border:0;border-radius:var(--ui-radius-control);background:#176f60;color:white;margin-top:8px}</style>
