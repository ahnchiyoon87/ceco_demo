<script setup>
import { computed, onMounted, onUnmounted, ref } from 'vue'
const emit = defineEmits(['started', 'reset', 'dashboard', 'state'])
const catalog = ref([]), scenario = ref('strainer_fouling'), state = ref(null)
const busy = ref(false), error = ref(''), message = ref(''), uncertain = ref(false)
let timer, mounted = true
const selected = computed(() => catalog.value.find(x => x.id === scenario.value))
const active = computed(() => !!state.value?.active_faults?.length)
const working = computed(() => !!state.value?.execution_active)
const disabled = computed(() => busy.value || !state.value || !!error.value || uncertain.value || working.value)
async function request(path, body) {
  const response = await fetch('/simulation/' + path, {
    method: body === undefined ? 'GET' : 'POST',
    headers: { 'X-CECO-Portal': 'interactive', ...(body === undefined ? {} : { 'Content-Type': 'application/json' }) },
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
    signal: AbortSignal.timeout(30000),
  })
  const data = await response.json().catch(() => ({}))
  if (!response.ok) throw new Error(data.detail || `설비 연결 확인 필요 (${response.status})`)
  return data
}
async function refresh() {
  clearTimeout(timer)
  try {
    const data = await request('state')
    if (!mounted) return
    state.value = data; error.value = ''; emit('state',data)
  } catch (e) { if (mounted) { state.value = null; error.value = e.message } }
  finally { if (mounted) timer = setTimeout(refresh, 3000) }
}
async function start() {
  if (disabled.value || active.value) return
  busy.value = true; message.value = ''
  const since = Date.now()
  try {
    await request('fault', { scenario: scenario.value })
    message.value = `${selected.value.title}이 발생했습니다. 센서 감지와 분석이 자동으로 이어집니다.`
    const group = ['strainer_fouling', 'jacket_fouling'].includes(scenario.value) ? 'thermal' : ['bearing_wear', 'shaft_misalignment'].includes(scenario.value) ? 'mixer' : 'pressure'
    emit('started', { since, scenario: scenario.value, group })
    await refresh()
  } catch (e) { error.value = e.message; uncertain.value = true }
  finally { busy.value = false }
}
async function reset() {
  if (disabled.value) return
  busy.value = true; message.value = ''
  try {
    await request('reset', {})
    message.value = '이상을 초기화했습니다. 온도와 유량이 안정되면 다시 시작하세요.'
    emit('reset'); await refresh()
  } catch (e) { error.value = e.message; uncertain.value = true }
  finally { busy.value = false }
}
async function check() { await refresh(); if (state.value) uncertain.value = false }
onMounted(async () => {
  try { const data = await request('catalog'); if (mounted) catalog.value = data.items }
  catch (e) { if (mounted) error.value = e.message }
  if (mounted) refresh()
})
onUnmounted(() => { mounted = false; clearTimeout(timer) })
</script>

<template>
  <section class="simulation-controls" aria-label="설비 이상 발생">
    <div class="simulation-head"><strong>이상 발생</strong><span>{{ !state ? '설비 연결 확인 중' : working ? '정비·회복 확인 중' : active ? '이상 발생 중' : '이상 없음' }}</span></div>
    <div class="simulation-actions">
      <label for="simulation-scenario">상황 선택</label>
      <select id="simulation-scenario" v-model="scenario" :disabled="disabled || active">
        <option v-for="item in catalog" :key="item.id" :value="item.id">{{ item.group }} · {{ item.title }}</option>
      </select>
      <button class="start-fault" :disabled="disabled || active || !selected" @click="start">{{ busy ? '반영 확인 중…' : '이상 발생' }}</button>

    </div>
    <p>{{selected?.description}}</p>
    <p v-if="message" class="simulation-result" role="status">{{ message }}</p>
    <p v-if="working" class="simulation-result">승인된 정비가 진행 중입니다. 완료 후 다시 시작할 수 있습니다.</p>
    <p v-if="error || uncertain" class="simulation-error" role="alert">{{ error || '응답 확인이 필요합니다.' }} <button @click="check">상태 다시 확인</button></p>
    <details class="reset-tools"><summary>상황을 취소하고 다시 시작</summary><p>발생시킨 이상을 초기화합니다. 정비로 복구한 결과는 남지 않습니다.</p><button :disabled="disabled" @click="reset">이상 초기화</button></details>
  </section>
</template>

<style scoped>
.simulation-controls{margin-top:18px;padding:16px 18px;border:1px solid #375767;border-radius:12px;background:#142b39;color:#e4f1f5}
.simulation-head{display:flex;justify-content:space-between;align-items:center;gap:12px;margin-bottom:12px}.simulation-head strong{font-size:16px}.simulation-head span{font-size:13px;color:#8ee1c7}
.simulation-actions{display:flex;gap:10px;align-items:center;flex-wrap:wrap}.simulation-actions label{font-size:13px}.simulation-actions select{min-width:260px;flex:1;max-width:420px;padding:10px;background:#f3f9f7;color:#183b42;border:1px solid #73a19a;border-radius:7px;font:inherit;font-size:14px}
.simulation-actions button,.simulation-error button{padding:10px 14px;border:1px solid #608b91;border-radius:7px;background:#203d49;color:#e9f7fa;font:inherit;font-size:14px;cursor:pointer}.simulation-actions .start-fault{background:#a44032;border-color:#c57662;color:white;font-weight:700}.simulation-actions .open-dashboard{background:#176957;border-color:#52a78f}.simulation-actions button:disabled{opacity:.45;cursor:default}
.simulation-controls p{font-size:13px;line-height:1.7;margin:11px 0 0;color:#c0d7df}.simulation-controls p span{color:#94b4bf}.simulation-controls small{display:block;font-size:12px;color:#a2bcc8;margin-top:8px}.simulation-controls .simulation-result{color:#9eefd5}.simulation-controls .simulation-error{color:#ffd1b7}
@media(max-width:700px){.simulation-actions select{min-width:0;width:100%;max-width:none;flex-basis:100%}.simulation-actions label{width:100%}.simulation-actions .open-dashboard{width:100%}.simulation-controls{padding:14px}}
</style>

<style scoped>.reset-tools{margin-top:12px;font-size:12px;color:#a7c5cf}.reset-tools summary{cursor:pointer}.reset-tools button{margin-top:8px;background:#203d49;border:1px solid #608b91;color:white;border-radius:7px;padding:8px 12px;font:inherit}</style>
