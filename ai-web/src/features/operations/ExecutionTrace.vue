<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
const props = defineProps({ run: Object, mode:{type:String,default:'investigate'} })
const emit = defineEmits(['state'])
const streaming=ref(false)
let stream
function connect(){
  stream?.close();streaming.value=false
  if(typeof navigator!=='undefined'&&navigator.onLine===false){offline();return}
  if(!props.run?.id||typeof EventSource==='undefined')return
  const id=props.run.id
  stream=new EventSource(`/api/operations/analysis/${id}/stream`)
  stream.addEventListener('trace',event=>{
    if(props.run?.id!==id)return
    let data
    try{data=JSON.parse(event.data);if(!Array.isArray(data.items)||!data.run)throw new Error('invalid trace')}
    catch{streaming.value=false;error.value='실행 기록 형식을 확인하지 못했습니다. 다시 조회합니다.';clearTimeout(timer);timer=setTimeout(load,2000);return}
    // A later SSE snapshot supersedes any older in-flight HTTP fallback.
    generation++
    events.value=data.items;truncated.value=data.truncated;received.value=new Date().toISOString();error.value='';streaming.value=true
    clearTimeout(timer)
    emit('state',data.run)
  })
  function unavailable(){if(props.run?.id!==id)return;streaming.value=false;error.value='실시간 기록 연결이 끊겼습니다. 자동 재연결 중입니다.';clearTimeout(timer);timer=setTimeout(load,2000)}
  stream.addEventListener('unavailable',unavailable)
  stream.onerror=unavailable
}
const events = ref([]), error = ref(''), received = ref(null), truncated = ref(false)
let timer, generation = 0
const names = { alarm: ['get_incident_alarm', '원본 알람 · 사건 버전', 'PostgreSQL'], documents: ['get_asset_documents', '설비 관계 · 적용 문서', 'Neo4j'], observations: ['get_sensor_observations', '사건 당시 · 현재 관측', 'InfluxDB + 시뮬레이터'] }
const statuses = { running: 'AI 근거 분석 중', awaiting_review: '사람의 검토 대기', resuming: '검토 결과 처리 중', finished: '처리 완료', failed: '실행 실패', interrupted: '실행 중단', needs_evidence: '근거 보완 필요' }
const active = computed(() => ['running', 'resuming'].includes(props.run?.status))
const eventNames={agent_model_output:'AI 응답 수신',agent_model_output_rejected:'AI 응답 검증 실패',agent_needs_evidence:'근거 보완 요청',agent_run_failed:'실행 실패',proposal_created:'대응안 작성',proposal_rejected:'담당자 반려 · 명령 없음',action_connecting:'설비 통신 연결',action_dispatch_started:'설비 명령 전송 시작',thermal_observation:'조치 후 온도 관측',action_acknowledged:'Modbus 응답 수신',action_observed:'설비 상태 재조회',action_authorized:'승인 및 실행 조건 확인',action_result:'조치 결과 확인',execution_recovered:'중단된 실행 확인'}
const actionKinds=['action_connecting','action_dispatch_started','action_acknowledged','action_observed','action_authorized','action_result','thermal_observation','proposal_rejected','execution_recovered']
const milestones=computed(()=>events.value.filter(e=>props.mode==='execute'?actionKinds.includes(e.kind):!actionKinds.includes(e.kind)&&!['agent_tool_started','agent_tool_result','agent_tool_failed'].includes(e.kind)))
const calls = computed(() => {
  const rows = new Map()
  for (const event of events.value) {
    if (!['agent_tool_started', 'agent_tool_result', 'agent_tool_failed'].includes(event.kind)) continue
    const p = event.payload
    const key = p.call_id || `legacy-${event.id}`
    const previous = rows.get(key)
    rows.set(key, { ...previous, ...p, key, time: previous?.time || event.created_at,
      state: event.kind === 'agent_tool_result' ? 'complete' : event.kind === 'agent_tool_failed' ? 'failed' : active.value ? 'running' : 'unknown' })
  }
  return [...rows.values()]
})
const clock = value => new Date(value).toLocaleTimeString('ko-KR')
async function load() {
  clearTimeout(timer)
  if(typeof navigator!=='undefined'&&navigator.onLine===false){offline();return}
  const token = ++generation, id = props.run?.id
  if (!id) return
  try {
    const response = await fetch(`/api/operations/analysis/${id}/trace`, { signal: AbortSignal.timeout(15000) })
    if (!response.ok) throw new Error(`실행 기록 조회 실패 (${response.status})`)
    const data = await response.json()
    if (token !== generation) return
    events.value = data.items; truncated.value = data.truncated; received.value = new Date().toISOString(); error.value = ''
  } catch (e) { if (token === generation) error.value = e.message }
  finally { if (token === generation && !streaming.value && (active.value || error.value)) timer = setTimeout(load, error.value ? 6000 : 2000) }
}
watch(() => props.run?.id, () => { generation++; clearTimeout(timer); events.value = []; received.value = null; error.value = ''; load();connect() }, { immediate: true })
watch(() => props.run?.status, load)
function offline(){generation++;stream?.close();streaming.value=false;clearTimeout(timer);error.value='브라우저 오프라인 · 마지막 저장 기록입니다. 연결 복구를 기다립니다.'}
function online(){load();connect()}
onMounted(()=>{if(typeof window!=='undefined'){window.addEventListener('offline',offline);window.addEventListener('online',online)}})
onUnmounted(() => { generation++; clearTimeout(timer);stream?.close();if(typeof window!=='undefined'){window.removeEventListener('offline',offline);window.removeEventListener('online',online)} })
</script>

<template>
  <section v-if="run" class="execution-trace" aria-label="AI 도구 실행 과정">
    <header><div><small>{{mode==='execute'?'ACTION TRACE':'EXECUTION TRACE'}}</small><h4><i :class="{ active }"></i>{{ statuses[run.status] || run.status }}</h4></div><button @click="load">기록 갱신</button></header>
    <p class="trace-caption">{{ run.model }} · {{ clock(run.created_at) }} 시작<br>실행 <code>{{ run.id }}</code></p>
    <p v-if="error" class="trace-error" role="alert">{{ error }} · 마지막 기록을 표시합니다. 자동 재연결 중입니다.</p>
    <p v-if="mode==='investigate'&&!calls.length" role="status">{{ active ? '모델이 요청을 처리하고 있습니다. 도구 호출이 기록되면 여기에 표시됩니다.' : '이 실행에 저장된 도구 호출 기록이 없습니다.' }}</p>
    <p v-if="mode==='execute'&&!milestones.length" role="status">저장된 조치 이벤트가 없습니다. 승인·조치 기록이 생기면 여기에 표시됩니다.</p>
    <ol v-if="mode==='investigate'" class="tool-calls">
      <li v-for="call in calls" :key="call.key" :class="call.state">
        <div class="tool-line"><span class="tool-state">{{ ({complete:'완료',running:'실행 중',failed:'실패',unknown:'결과 미확인'})[call.state] }}</span><b>{{ names[call.tool]?.[1] || call.tool }}</b><time>{{ clock(call.time) }}</time></div>
        <p><code>{{ names[call.tool]?.[0] || call.tool }}</code><span>{{ names[call.tool]?.[2] }}<template v-if="call.duration_ms != null"> · {{ call.duration_ms }} ms</template></span></p>
        <p v-if="call.result?.status && call.result.status !== 'available'" class="trace-error">조회 상태: {{ call.result.status }} · {{ call.result.error }}</p>
        <p v-if="call.error_type" class="trace-error">{{ call.error_type }}</p>
        <details v-if="call.result"><summary>도구 반환값 · 출처 확인</summary><pre>{{ JSON.stringify(call.result, null, 2) }}</pre></details>
      </li>
    </ol>
    <section v-if="milestones.length" class="milestones" aria-label="저장된 처리 이벤트"><article v-for="event in milestones" :key="event.id"><b>{{eventNames[event.kind]||event.kind}}</b> <time>{{clock(event.created_at)}}</time><p v-if="event.payload.reason">{{event.payload.reason}}</p><p v-if="event.payload.observation">조회 {{event.payload.attempt}}회 · 상태 {{event.payload.observation.status}} · 관측 번호 {{event.payload.observation.seq ?? '확인 불가'}} · 교반기 {{event.payload.observation.commands?.agitator_run === false ? '정지 값' : event.payload.observation.commands?.agitator_run === true ? '가동 값' : '상태 미확인'}}</p><p v-if="event.payload.note">검토 의견: {{event.payload.note}}</p><details><summary>상세 기록 · 원본 값</summary><pre>{{JSON.stringify(event.payload,null,2)}}</pre></details></article></section>
    <p v-if="run.status === 'awaiting_review'" class="review-checkpoint">검토 지점에 저장됨 · 아래 대응안과 근거를 확인한 후 승인 또는 반려하세요.</p>
    <p v-if="truncated" class="trace-error">최근 200개 실행 이벤트만 표시합니다.</p>
    <footer>서버에 저장된 호출 기록 · {{ received ? clock(received) + ' 수신' : '연결 중' }} · {{streaming?'실시간 이벤트 연결됨':'연결 확인 중'}}</footer>
  </section>
</template>

<style scoped>
.milestones article{padding:14px;background:#fff;border:1px solid #dce5ee;border-left:3px solid #008575;border-radius:8px;margin:10px 0;font-size:var(--ui-font-caption)}.milestones time{font-size:var(--ui-font-caption);color:#526b7c}.milestones p{line-height:1.8}.milestones details{margin-top:8px}
.execution-trace{margin:18px 0;padding:20px;background:#f5f8fc;border:1px solid #d7e1ed;border-radius:12px;overflow-wrap:anywhere}.execution-trace header{display:flex;justify-content:space-between;align-items:center;gap:12px}.execution-trace small{font-size:var(--ui-font-caption);letter-spacing:2px;color:#60788c}.execution-trace h4{margin:6px 0;font-size:17px;color:#233b50}.execution-trace button{padding:8px 12px;background:white;border:1px solid #ccd9e5;border-radius:7px;color:#385469}.execution-trace i{display:inline-block;width:9px;height:9px;border-radius:50%;background:#7894a9;margin-right:9px}.execution-trace i.active{background:#008c77;animation:trace-pulse 1.4s infinite}.trace-caption,footer{font-size:var(--ui-font-caption);color:#61778a;line-height:1.9}.tool-calls{list-style:none;padding:0;margin:18px 0}.tool-calls li{padding:14px;margin:10px 0;background:white;border:1px solid #dce5ee;border-left:3px solid #7995ac;border-radius:8px}.tool-calls li.complete{border-left-color:#008575}.tool-calls li.failed{border-left-color:#c35050}.tool-calls li.running{border-left-color:#4279bf}.tool-line{display:flex;gap:10px;align-items:center;flex-wrap:wrap;font-size:var(--ui-font-caption)}.tool-line time{margin-left:auto;font-size:var(--ui-font-caption);color:var(--ui-text-muted)}.tool-state{font-size:var(--ui-font-caption);padding:2px 7px;border-radius:4px;background:#edf3f7;color:#476277}.tool-calls p{display:flex;gap:8px;justify-content:space-between;flex-wrap:wrap;font-size:var(--ui-font-caption);color:var(--ui-text-muted);margin:8px 0}.execution-trace code{font-size:var(--ui-font-caption)}.execution-trace summary{font-size:var(--ui-font-caption);cursor:pointer;color:#277666}.execution-trace pre{max-height:280px;overflow:auto;white-space:pre-wrap;overflow-wrap:anywhere;padding:12px;background:#f0f4f8;font-size:var(--ui-font-caption)}.trace-error{color:#a54f2d!important;font-size:var(--ui-font-caption)}.review-checkpoint{border:1px solid #c8dfd5;border-radius:8px;background:#eaf5ef;padding:12px;font-size:var(--ui-font-caption);color:#23705a}@keyframes trace-pulse{50%{opacity:.35}}
</style>


