<script setup>
import { ref, watch, onUnmounted } from 'vue'
const props = defineProps({ incidentId: {type:String, required:true}, revision:Number })
const items=ref([]), loading=ref(false), error=ref(''), cursor=ref(null), more=ref(false)
let generation=0
const labels={alarm_received:'알람 접수',alarm_correlated:'추가 알람 연결',proposal_created:'대응안 작성',proposal_rejected:'대응안 반려',action_authorized:'조치 승인',action_result:'조치 결과 확인',execution_recovered:'중단된 조치 확인',agent_tool_result:'AI 근거 조회',agent_model_output:'AI 분석 기록',agent_run_failed:'AI 실행 실패'}
const results={stop_verified:'시뮬레이터 정지 확인 · 정비 완료는 아님',inspection_requested:'점검 요청 기록 · 설비 명령 없음',not_executed:'실행되지 않음',uncertain:'실행 여부 불명확 · 수동 확인 필요'}
const tools={alarm:'원본 알람',documents:'설비 관계와 문서',observations:'센서 관측 이력'}
function summary(event){
  const p=event.payload||{}
  if(event.kind.startsWith('alarm_')) return `${p.tag} · ${p.alert_type} · 관측값 ${p.value} · ${p.detector}`
  if(event.kind==='agent_tool_result') return `${tools[p.tool]||p.tool} 조회 결과 저장`
  if(event.kind==='action_result') return results[p.status]||p.reason||p.status
  if(event.kind==='execution_recovered') return p.result?.reason||'저장된 실행 상태를 확인했습니다.'
  if(event.kind==='proposal_created') return p.origin?.startsWith('ai-run:')?'AI 분석에서 생성한 대응안':'강사 통합 검증용 대응안'
  return p.note||p.error||(event.kind==='agent_model_output'?'모델 응답과 실행 정보를 저장했습니다.':'저장된 원본 기록을 확인하세요.')
}
async function load(append=false){
  if(append&&loading.value)return
  const token=++generation
  loading.value=true;error.value=''
  try{
    const query=new URLSearchParams({limit:'30'})
    if(append&&cursor.value)query.set('before_id',String(cursor.value))
    const response=await fetch(`/api/operations/incidents/${props.incidentId}/events?${query}`,{signal:AbortSignal.timeout(15000)})
    const data=await response.json()
    if(!response.ok)throw new Error(data.detail||`이력 조회 실패 (${response.status})`)
    if(token!==generation)return
    items.value=append?[...items.value,...data.items]:data.items
    more.value=data.has_more;cursor.value=data.next_before_id
  }catch(e){if(token===generation)error.value=e.message}
  finally{if(token===generation)loading.value=false}
}
watch(()=>props.incidentId,()=>{items.value=[];cursor.value=null;more.value=false;load()}, {immediate:true})
watch(()=>props.revision,()=>load())
onUnmounted(()=>generation++)
</script>

<template>
  <section class="incident-timeline" aria-label="사건 처리 이력">
    <div class="panel-heading"><h3>사건 처리 이력</h3><button :disabled="loading" @click="load()">이력 새로고침</button></div>
    <p class="panel-hint">최근 기록부터 표시 · 시간은 서버에 기록이 저장된 시각입니다. 승인·반려 사유를 보존하며 검토자 신원 인증은 아직 제공하지 않습니다.</p>
    <p v-if="error" class="mfg-error" role="alert">{{error}} · 이전 기록은 최신이 아닐 수 있습니다.</p>
    <p v-if="loading" class="panel-hint" role="status">기록을 조회하고 있습니다.</p>
    <p v-if="!loading&&!error&&!items.length" class="panel-hint">저장된 처리 이력이 없습니다.</p>
    <ol>
      <li v-for="event in items" :key="event.id">
        <div class="timeline-heading"><b>{{labels[event.kind]||event.kind}}</b><time :datetime="event.created_at">{{new Date(event.created_at).toLocaleString('ko-KR')}}</time></div>
        <p>{{summary(event)}}</p>
        <details><summary>기록 원문 보기</summary><pre>{{JSON.stringify(event.payload,null,2)}}</pre></details>
      </li>
    </ol>
    <button v-if="more" :disabled="loading" @click="load(true)">이전 기록 더 보기</button>
  </section>
</template>

<style scoped>
.incident-timeline{border-top:1px solid #e0e7ec;margin-top:28px;padding-top:8px}
button{border:1px solid #d4e1df;border-radius:7px;background:#f4f8f7;padding:7px 11px;color:#286f61;font-size:12px}
button:disabled{opacity:.5;cursor:wait}
ol{list-style:none;margin:16px 0;padding:0 0 0 14px;border-left:2px solid #d7e7e2}
li{position:relative;padding:0 0 20px 8px}
li::before{content:'';position:absolute;left:-20px;top:7px;width:8px;height:8px;background:#168976;border-radius:50%;box-shadow:0 0 0 4px white}
.timeline-heading{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-size:12px}
time{color:#758795;font-size:11px;font-variant-numeric:tabular-nums}
p{font-size:12px;color:#546b78;margin:5px 0;overflow-wrap:anywhere}
summary{font-size:11px;color:#738692;cursor:pointer}
pre{max-height:260px;overflow:auto;background:#f5f8f9;padding:12px;border-radius:6px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:11px}
</style>
