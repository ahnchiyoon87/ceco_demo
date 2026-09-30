<script setup>
import { computed, ref, watch, onUnmounted } from 'vue'
import ExecutionTrace from './ExecutionTrace.vue'
const props = defineProps({ incidents: {type:Array, default:()=>[]}, model:Object, modelError:String })
const emit = defineEmits(['inspect'])
const selectedId = ref(null), run = ref(null), error = ref(''), loading = ref(false)
let timer, generation=0
const current = computed(() => props.incidents.find(x=>x.id===selectedId.value) || props.incidents[0])
const emptyMessage = computed(() => loading.value ? '저장된 실행 확인 중' : error.value ? '분석 기록을 확인하지 못했습니다.' : !current.value ? '대응 사건을 기다립니다.' : '아직 AI 분석 기록이 없습니다.')
const open = computed(() => props.incidents.filter(x=>!['closed','rejected'].includes(x.status)).length)
const review = computed(() => props.incidents.filter(x=>x.status==='awaiting_review').length)
const label = item => item.correlation_key?.includes('mixer') ? '교반기 전류·진동 이상' : `${item.alarm?.tag || item.device} · ${item.alarm?.alert_type || '이상 신호'}`
const statuses = {received:'접수',awaiting_review:'검토 대기',executing:'조치 중',observing:'온도 관측 중',awaiting_maintenance:'점검 대기',unresolved:'미해결',closed:'종결',rejected:'반려'}
async function load() {
  clearTimeout(timer)
  const token=++generation, id=current.value?.id
  if(!id) { loading.value=false; return }
  loading.value=true
  try {
    const response=await fetch(`/api/operations/incidents/${id}/analysis`,{signal:AbortSignal.timeout(15000)})
    if(!response.ok) throw new Error(`AI 실행 상태 조회 실패 (${response.status})`)
    const data=await response.json()
    if(token===generation){run.value=data.items[0] || null;error.value=''}
  }catch(e){if(token===generation)error.value=e.message}
  finally{if(token===generation){loading.value=false;timer=setTimeout(load,['running','resuming'].includes(run.value?.status)?2000:10000)}}
}
watch(()=>current.value?.id,()=>{generation++;clearTimeout(timer);run.value=null;error.value='';load()},{immediate:true})
onUnmounted(()=>{generation++;clearTimeout(timer)})
</script>

<template>
  <section class="dashboard-activity" aria-label="대응 사건과 AI 진행">
    <div class="dashboard-kpis"><article><span>미종결 사건</span><strong>{{open}}</strong><small>최근 조회 {{incidents.length}}건 기준</small></article><article><span>사람의 검토 대기</span><strong>{{review}}</strong><small>근거 확인 후 승인·반려</small></article><article><span>AI 업무도우미</span><strong class="model-state">{{modelError ? '설정 조회 실패' : model?.configured ? '모델 설정됨' : '연결 설정 확인'}}</strong><small>{{model?.model || '모델 상태를 조회합니다.'}} · 추론 성공은 실행별 확인</small></article></div>
    <div class="activity-grid"><section class="recent-cases"><header><h3>최근 대응 사건</h3><span>{{incidents.length}}건 조회</span></header><button v-for="item in incidents.slice(0,6)" :key="item.id" :class="{selected:current?.id===item.id}" @click="selectedId=item.id"><b>{{label(item)}}</b><span>{{statuses[item.status] || item.status}} · {{item.alarm_count || 1}}개 원본 알람</span><small>{{new Date(item.created_at).toLocaleString('ko-KR')}}</small></button><p v-if="!incidents.length">아직 조회된 사건이 없습니다. 공정 수신과 연결 상태를 확인하세요.</p></section>
    <section class="dashboard-run"><header><div><h3>AI 처리 과정</h3><p>{{current ? label(current) : '대응 사건을 기다립니다.'}}</p></div><button v-if="current" @click="emit('inspect',current)">근거·대응안 열기 →</button></header><p v-if="error" role="alert" class="dashboard-error">{{error}} · 자동 재연결 중</p><ExecutionTrace v-if="run" :run="run"/><div v-else class="no-analysis"><span>⌘</span><b>{{emptyMessage}}</b><p v-if="current && !error && !loading">사건의 근거를 확인하고 대응안 작성을 시작하면<br>사용한 도구와 처리 과정이 여기에 나타납니다.</p></div></section></div>
  </section>
</template>

<style scoped>
.dashboard-activity{margin-top:24px}.dashboard-kpis{display:grid;grid-template-columns:1fr 1fr 1.5fr;gap:var(--ui-space-lg);margin-bottom:20px}.dashboard-kpis article{background:var(--ui-surface);border:1px solid var(--ui-border);border-radius:var(--ui-radius-card);padding:var(--ui-space-panel)}.dashboard-kpis span{font-size:var(--ui-font-caption);color:var(--ui-text-muted)}.dashboard-kpis strong{display:block;font-size:32px;color:var(--ui-text);line-height:1.5}.dashboard-kpis strong.model-state{font-size:21px;margin:8px 0}.dashboard-kpis small{font-size:var(--ui-font-caption);color:var(--ui-text-muted)}.activity-grid{display:grid;grid-template-columns:minmax(260px,.8fr) minmax(0,1.4fr);gap:var(--ui-space-panel)}.recent-cases,.dashboard-run{padding:var(--ui-space-panel);background:var(--ui-surface);border:1px solid var(--ui-border);border-radius:var(--ui-radius-card);min-width:0}.activity-grid header{display:flex;justify-content:space-between;align-items:center;gap:10px}.activity-grid h3{font-size:16px;margin:0}.activity-grid header span,.activity-grid header p{font-size:var(--ui-font-caption);color:var(--ui-text-muted)}.recent-cases>button{width:100%;display:flex;flex-direction:column;text-align:left;padding:14px;border:1px solid #e0e8ee;border-radius:var(--ui-radius-control);background:var(--ui-surface-muted);margin-top:12px;gap:4px;color:#2b4254}.recent-cases>button.selected{border-color:var(--ui-selected-border);background:var(--ui-selected-surface);box-shadow:inset 3px 0 var(--ui-selected-accent)}.recent-cases b{font-size:var(--ui-font-caption);overflow-wrap:anywhere}.recent-cases span,.recent-cases small{font-size:var(--ui-font-caption);color:var(--ui-text-muted)}.dashboard-run header>button{border:1px solid #bad9ce;background:#edf7f2;border-radius:var(--ui-radius-control);color:#28715e;padding:9px 12px;white-space:nowrap;font-size:var(--ui-font-caption)}.no-analysis{display:flex;align-items:center;flex-direction:column;justify-content:center;min-height:230px;color:#718699;text-align:center}.no-analysis>span{font-size:38px;color:#90aaa9}.no-analysis b{font-size:var(--ui-font-body);margin-top:10px}.no-analysis p{font-size:var(--ui-font-caption);line-height:1.9}.dashboard-error{font-size:var(--ui-font-caption);color:#a35335}@media(max-width:1000px){.activity-grid{grid-template-columns:1fr}.dashboard-kpis{grid-template-columns:1fr 1fr}.dashboard-kpis article:last-child{grid-column:1/-1}}@media(max-width:600px){.dashboard-kpis{gap:10px}.dashboard-kpis article{padding:15px}.dashboard-run header{flex-wrap:wrap}}
</style>
