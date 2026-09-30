<script setup>
import { ref, onMounted, onUnmounted } from 'vue'
const data=ref(null), error=ref('')
let timer, generation=0
async function load(){
  clearTimeout(timer)
  const token=++generation
  try{
    const response=await fetch('/api/operations/pipeline',{signal:AbortSignal.timeout(18000)})
    if(!response.ok)throw new Error(`파이프라인 상태 조회 실패 (${response.status})`)
    const value=await response.json()
    if(token===generation){data.value=value;error.value=''}
  }catch(e){if(token===generation)error.value=e.message}
  finally{if(token===generation)timer=setTimeout(load,15000)}
}
onMounted(load)
onUnmounted(()=>{generation++;clearTimeout(timer)})
</script>
<template>
  <section class="pipeline-status" aria-label="파이프라인 상태">
    <header><b>데이터가 실제로 처리되고 있나요?</b><button @click="load">상태 확인 ↻</button></header>
    <p v-if="error" role="alert">{{error}} · 아래 표시는 마지막 조회 결과입니다.</p>
    <div class="pipeline-points"><details v-for="item in data?.items" :key="item.key" :class="error ? 'unavailable' : item.status"><summary><span class="status-dot"></span><b>{{item.name}}</b><small>{{item.detail}}</small><em>{{error ? '최신 조회 실패' : ({available:'확인됨',degraded:'점검 필요',unavailable:'확인 불가'})[item.status]}}</em></summary><p>{{item.boundary || '서비스 연결을 확인하세요.'}}</p><ul v-if="item.jobs"><li v-for="(job,index) in item.jobs" :key="index">{{job.name}} · {{job.state}}</li></ul></details></div>
    <small>{{data ? new Date(data.checked_at).toLocaleTimeString('ko-KR')+' 확인 · 15초 간격 조회' : '공정·수집·분석 상태 확인 중'}}</small>
  </section>
</template>
<style scoped>
.pipeline-status{margin-top:22px;padding:17px 20px;border:1px solid #294155;border-radius:12px;background:#122335}.pipeline-status header{display:flex;justify-content:space-between;align-items:center;gap:12px;font-size:var(--ui-font-caption)}.pipeline-status button{border:0;background:none;color:#8ddfcb;font-size:var(--ui-font-caption)}.pipeline-points{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:12px;margin:14px 0}.pipeline-points details{border:1px solid #31596a;border-radius:8px;padding:12px;background:#17313c}.pipeline-points details.degraded,.pipeline-points details.unavailable{border-color:#78603f;background:#342c25}.pipeline-points summary{cursor:pointer;list-style:none;font-size:var(--ui-font-caption)}.pipeline-points small{display:block;color:#b2c4cf;font-size:var(--ui-font-caption);margin:5px 0}.pipeline-points em{font-style:normal;color:#76dec5;font-size:var(--ui-font-caption)}.pipeline-points .degraded em,.pipeline-points .unavailable em{color:#edc38a}.status-dot{display:inline-block;background:#56cbb0;border-radius:50%;width:6px;height:6px;margin-right:7px}.degraded .status-dot,.unavailable .status-dot{background:#e3ae69}.pipeline-points p,.pipeline-points ul{font-size:var(--ui-font-caption);color:#acbdc9;overflow-wrap:anywhere;line-height:1.8;padding-left:0}.pipeline-status>p{font-size:var(--ui-font-caption);color:#edc38a}.pipeline-status>small{font-size:var(--ui-font-caption);color:#839caf}@media(max-width:700px){.pipeline-points{grid-template-columns:1fr}}
</style>
