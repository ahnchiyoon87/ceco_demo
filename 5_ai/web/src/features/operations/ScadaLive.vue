<script setup>
import { computed, onMounted, onUnmounted, ref, defineAsyncComponent } from 'vue'
const PipelineStatus = defineAsyncComponent(() => import('./PipelineStatus.vue'))
const emit=defineEmits(['control'])
const plant = ref(null), error = ref(''), history = ref({}), lastChanged = ref(0), now = ref(Date.now())
const diagramExpanded = ref(false)
let timer, clockTimer, generation = 0
const tags = [ ['LT-101','원료탱크 레벨','%'], ['LT-102','반응기 레벨','%'], ['TT-101','반응기 온도','°C'], ['TT-102','재킷 온도','°C'], ['PT-101','반응기 압력','barg'], ['FT-101','공급 유량','m³/h'], ['FT-102','배출 유량','m³/h'], ['IT-101','펌프 전류','A'], ['IT-102','교반기 전류','A'], ['VT-101','교반기 진동','mm/s'], ['pH-101','반응기 pH','pH'], ['CT-101','전도도','mS/cm'],
  ['PT-102','반응기 압력(독립)','barg'], ['FT-103','냉각수 유량','m³/h'], ['PDT-103','스트레이너 차압','bar'], ['TT-103','냉각수 공급','°C'], ['TT-104','냉각수 회수','°C'] ]
const stale = computed(() => !!error.value || plant.value?.status !== 'available' || now.value - lastChanged.value > 15000)
const readings = computed(() => plant.value?.readings || {})
const commands = computed(() => plant.value?.commands || {})
const value = tag => typeof readings.value[tag] === 'number' && Number.isFinite(readings.value[tag]) ? readings.value[tag].toFixed(2) : '—'
const running = key => !stale.value && commands.value[key] === true
function spark(tag) {
  const samples = history.value[tag] || []
  if (samples.length < 2) return ''
  const low = Math.min(...samples), high = Math.max(...samples), span = high - low || 1
  return samples.map((v, i) => `${i * 200 / (samples.length - 1)},${40 - (v - low) * 32 / span}`).join(' ')
}
async function load() {
  clearTimeout(timer)
  const token = ++generation
  try {
    const response = await fetch('/api/operations/plant', { signal: AbortSignal.timeout(8000) })
    if (!response.ok) throw new Error(`공정 조회 실패 (${response.status})`)
    const data = await response.json()
    if (token !== generation) return
    if (data.status !== 'available') throw new Error(data.error || '공정 연결을 확인할 수 없습니다.')
    if (data.seq !== plant.value?.seq) {
      lastChanged.value = Date.now()
      for (const [tag] of tags) {
        const v = data.readings?.[tag]
        if (typeof v === 'number' && Number.isFinite(v)) history.value[tag] = [...(history.value[tag] || []), v].slice(-45)
      }
    }
    plant.value = data; error.value = ''
  } catch (e) { if (token === generation) error.value = e.message }
  finally { if (token === generation) timer = setTimeout(load, 2000) }
}
onMounted(() => { load(); clockTimer = setInterval(() => { now.value = Date.now() }, 1000) })
onUnmounted(() => { generation++; clearTimeout(timer); clearInterval(clockTimer) })
</script>

<template>
  <section class="scada-live" aria-label="실시간 공정 감시">
    <header class="live-heading"><div><small>AR-100 / LIVE PROCESS</small><h2>AR-100 공정 관제</h2><p>설비 상태부터 센서 변화까지, 현재 조회값을 연결해서 확인합니다.</p></div><span class="live-badge" :class="{stale}">{{ stale ? '연결·갱신 확인 필요' : '공정 상태 수신 중' }}</span></header>
    <div v-if="stale" role="alert" class="live-warning">{{ error || '새 스캔을 기다립니다. 15초 이상 값이 갱신되지 않으면 상태 확인이 필요합니다.' }} 이전 수치는 마지막 조회값입니다.</div>

    <div class="process-workspace"><div class="plant-overview"><div class="live-process" :class="{stale}">
      <div class="process-title"><b>원료 공급 → 교반·반응(발열) → 제품 배출 · 냉각수 계통</b><span>SCAN {{ plant?.seq ?? '—' }}</span></div>
      <div class="diagram-toolbar"><button :aria-pressed="diagramExpanded" aria-controls="process-diagram-viewport" @click="diagramExpanded = !diagramExpanded">{{ diagramExpanded ? '전체 공정 보기' : '공정도 크게 보기' }}</button><span id="process-diagram-help">{{ diagramExpanded ? '좌우로 밀어서 확인하세요. 키보드는 그림 영역에서 ← → 키를 사용하세요.' : '전체 연결을 보여줍니다. 작은 글씨는 크게 보기를 눌러 확인하세요.' }}</span></div>
      <div id="process-diagram-viewport" class="process-diagram-viewport" :class="{expanded:diagramExpanded}" tabindex="0" role="region" aria-label="공정도 보기" aria-describedby="process-diagram-help">
      <svg viewBox="0 0 1000 400" role="img" aria-label="원료탱크, 공급펌프, 반응기, 배출밸브와 냉각수 계통(스트레이너·재킷 코일)의 현재 상태">
        <defs><linearGradient id="vessel" x2="0" y2="1"><stop stop-color="#214b66"/><stop offset="1" stop-color="#12283a"/></linearGradient></defs>
        <path d="M180 190H405 M665 190H910" class="pipe"/>
        <path d="M180 190H405" class="flow" :class="{moving:running('pump_run')}"/>
        <path d="M665 190H910" class="flow" :class="{moving:!stale && readings['FT-102']>0.1}"/>
        <rect x="50" y="70" width="130" height="180" rx="18" fill="url(#vessel)" stroke="#6092ad"/>
        <text x="115" y="48" text-anchor="middle">TK-101 원료</text><text x="115" y="137" text-anchor="middle" class="value">{{value('LT-101')}}%</text><text x="115" y="164" text-anchor="middle" class="sub">탱크 레벨</text>
        <circle cx="280" cy="190" r="28" fill="#123346" stroke="#55bca7"/>
        <text x="280" y="196" text-anchor="middle">P</text><text x="280" y="248" text-anchor="middle" class="sub">P-101 · {{stale ? '미확인' : commands.pump_run ? '운전' : '정지'}}</text>
        <rect x="405" y="70" width="260" height="180" rx="24" fill="url(#vessel)" stroke="#6092ad"/>
        <text x="535" y="48" text-anchor="middle">R-101 반응기</text>
        <g class="agitator" :class="{rotating:running('agitator_run')}"><path d="M513 103H557 M535 84V122" stroke="#63d5bc" stroke-width="5" stroke-linecap="round"/></g>
        <text x="535" y="158" text-anchor="middle" class="value">{{value('TT-101')}} °C</text><text x="535" y="187" text-anchor="middle">PT-101 {{value('PT-101')}} · PT-102 {{value('PT-102')}} barg</text><text x="535" y="225" text-anchor="middle" class="sub">M-101 · {{stale ? '미확인' : commands.agitator_run ? '교반 중' : '정지'}}</text>
        <path d="M763 167L805 213V167L763 213Z" fill="#356e83" stroke="#80b4c8"/>
        <text x="784" y="248" text-anchor="middle" class="sub">CV-101 · {{commands.valve_open_sp ?? '—'}}%</text><text x="923" y="180" class="sub">제품 →</text>
        <!-- 냉각수 계통: 공용 유틸리티 → 이중 스트레이너(ST-103) → 재킷 냉각 코일(HX-102) → 회수 -->
        <path d="M40 330H405 L420 315 L440 345 L460 315 L480 345 L500 315 L520 345 L540 315 L560 345 L580 315 L600 345 L620 315 L640 345 L665 330H960" class="pipe cw"/>
        <path d="M40 330H405" class="flow cw-flow" :class="{moving:!stale && readings['FT-103']>1}"/>
        <path d="M665 330H960" class="flow cw-flow" :class="{moving:!stale && readings['FT-103']>1}"/>
        <text x="48" y="300" class="sub">냉각수 공급 TT-103 {{value('TT-103')}} °C</text>
        <rect x="230" y="306" width="96" height="48" rx="8" fill="#123346" stroke="#55bca7"/>
        <text x="278" y="328" text-anchor="middle">ST-103</text><text x="278" y="346" text-anchor="middle" class="sub">스트레이너 A/B</text>
        <text x="278" y="378" text-anchor="middle" class="sub">차압 {{value('PDT-103')}} bar</text>
        <text x="360" y="300" text-anchor="middle" class="sub">유량 FT-103</text><text x="360" y="378" text-anchor="middle" class="value cw-value">{{value('FT-103')}}</text>
        <text x="535" y="378" text-anchor="middle" class="sub">HX-102 재킷 냉각 코일 · {{stale ? '미확인' : commands.cooler_enable ? '냉각 중' : '정지'}}</text>
        <text x="952" y="300" text-anchor="end" class="sub">회수 TT-104 {{value('TT-104')}} °C →</text>
      </svg>
      </div>
      <footer><span :class="{alarm:plant?.interlock}">인터록 {{stale ? '확인 불가' : plant?.interlock ? '발동' : '미발동'}}</span><span>애니메이션: 조회된 운전 상태 · 도형 높이는 레벨값이 아닙니다.</span></footer>
    </div>
    <div class="telemetry-grid"><article v-for="[tag,label,unit] in tags" :key="tag" :class="{stale}"><header><b>{{tag}}</b><span>{{label}}</span></header><p>{{value(tag)}}<small>{{unit}}</small></p><svg viewBox="0 0 200 48" role="img" :aria-label="tag+' 최근 조회 추세'"><polyline :points="spark(tag)" fill="none" stroke="currentColor" stroke-width="2" vector-effect="non-scaling-stroke"/></svg><small>{{stale ? '마지막 조회값' : '현재 조회값'}} · {{history[tag]?.length || 0}}개 샘플</small></article></div>
    </div><p class="control-note">설비 조작은 공장(OT) 안의 운전원 화면 FUXA 에서만 합니다. 이 화면은 DMZ 에 올라온 설비 사본을 읽기만 합니다.</p></div><details class="pipeline-details"><summary>수집·분석 연결 상태 확인</summary><PipelineStatus /></details><div class="scada-foot"><p>추세는 이 화면을 연 후 수집한 최근 45개 조회값입니다. 자동 축척이므로 센서 간 높이를 비교하지 마세요. 조회 시각은 센서 측정 시각과 다릅니다.</p><button class="console-button" @click="emit('control')">설비 제어 패널 열기</button></div>
  </section>
</template>

<style scoped>
.process-workspace{display:grid;grid-template-columns:minmax(0,1.7fr) minmax(300px,1fr);align-items:start;gap:18px;margin:24px 0}.plant-overview{min-width:0;display:flex;flex-direction:column;gap:18px}.process-workspace .live-process{margin:0}.process-workspace .telemetry-grid{grid-column:1;grid-template-columns:repeat(3,minmax(0,1fr))}.process-workspace .plant-controls{grid-column:2;grid-row:1}@media(max-width:1100px){.process-workspace{grid-template-columns:1fr}.plant-overview{display:contents}.process-workspace .live-process{grid-row:1}.process-workspace .plant-controls{grid-column:1;grid-row:2}.process-workspace .telemetry-grid{grid-row:3}.process-workspace .telemetry-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
.scada-live{color:#dce9f2;background:#0e1b29;border-radius:18px;padding:28px}.live-heading{display:flex;justify-content:space-between;align-items:center;gap:20px}.live-heading small{font-size:var(--ui-font-caption);letter-spacing:2px;color:#63d5bc}.live-heading h2{font-size:28px;margin:8px 0}.live-heading p{font-size:13px;color:#93adbf;margin:0}.live-badge{white-space:nowrap;background:#153d36;color:#77dfc5;border:1px solid #296453;padding:8px 13px;border-radius:30px;font-size:var(--ui-font-caption)}.live-badge.stale{background:#4a3821;color:#f0c48a;border-color:#755935}.live-warning{padding:13px;border:1px solid #71532e;color:#f3ce9b;background:#332c22;border-radius:8px;margin-top:18px;font-size:13px}.live-process{margin:24px 0;border:1px solid #294155;border-radius:var(--ui-radius-card);background:#132435;overflow:hidden}.process-title{padding:17px 22px;display:flex;justify-content:space-between;font-size:13px}.process-title span{color:#789bb3;font-family:monospace}.process-diagram-viewport>svg{display:block;width:100%;min-height:210px}.live-process text{fill:#d3e5f0;font:16px 'Segoe UI','Malgun Gothic',sans-serif}.live-process .value{font-size:25px;fill:#91e8d1}.live-process .sub{font-size:13px;fill:#9bb6c9}.pipe{fill:none;stroke:#2d5b74;stroke-width:8}.flow{fill:none;stroke:#64c9c0;stroke-width:3;stroke-dasharray:7 14;opacity:.2}.flow.moving{opacity:1;animation:flow 2s linear infinite}.agitator{transform-origin:535px 103px}.rotating{animation:turn 3s linear infinite}.live-process footer{padding:13px 22px;border-top:1px solid #294155;display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap;font-size:var(--ui-font-caption);color:#88a5ba}.alarm{color:#ffae93}.telemetry-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:13px}.telemetry-grid article{padding:16px 19px;border-radius:12px;border:1px solid #294155;background:#142738;min-width:0}.telemetry-grid header{display:flex;justify-content:space-between;gap:8px;font-size:var(--ui-font-caption)}.telemetry-grid header span{color:#93adbf;font-size:var(--ui-font-caption)}.telemetry-grid p{font-size:29px;font-variant-numeric:tabular-nums;margin:12px 0 0}.telemetry-grid p small{font-size:var(--ui-font-caption);color:#88a6ba;margin-left:7px}.telemetry-grid svg{width:100%;height:43px;color:#5ac8af;margin-top:6px}.telemetry-grid article>small{font-size:var(--ui-font-caption);color:#7999af}.stale .value,.telemetry-grid .stale p{color:#b0b6bd}.scada-foot{display:flex;align-items:center;justify-content:space-between;gap:22px;margin-top:20px}.scada-foot p{font-size:var(--ui-font-caption);line-height:1.8;color:#88a5ba;max-width:650px}.scada-foot a{color:#7ee0c7;text-decoration:none;font-size:var(--ui-font-caption);white-space:nowrap;border:1px solid #367566;padding:10px 16px;border-radius:var(--ui-radius-control)}@keyframes flow{to{stroke-dashoffset:-42}}@keyframes turn{to{transform:rotate(360deg)}}@media(max-width:1200px){.telemetry-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}@media(max-width:700px){.scada-live{padding:16px}.live-heading,.scada-foot{align-items:flex-start;flex-direction:column}.live-heading h2{font-size:23px}.telemetry-grid{grid-template-columns:repeat(2,minmax(0,1fr))}.telemetry-grid article{padding:12px}.telemetry-grid header{flex-direction:column}.telemetry-grid p{font-size:24px}.process-diagram-viewport>svg{min-height:160px}.process-title{font-size:var(--ui-font-caption);padding:12px}}
</style>
<style scoped>.process-diagram-viewport>svg{max-height:340px;min-height:200px}.pipe.cw{stroke:#24506b;stroke-width:6}.cw-flow{stroke:#5fb1e0}.cw-value{font-size:20px!important}.pipeline-details{margin-top:20px;border:1px solid #375767;border-radius:10px;padding:12px 16px;font-size:13px;color:#b4d6de}.pipeline-details summary{cursor:pointer}.live-heading h2{font-size:26px}.telemetry-grid article{padding:12px 16px}.telemetry-grid p{font-size:26px;margin-top:6px}.telemetry-grid svg{height:30px}</style>

<style scoped>
.diagram-toolbar{display:flex;align-items:center;gap:var(--ui-space-md);padding:0 var(--ui-space-lg) var(--ui-space-md);flex-wrap:wrap}
.diagram-toolbar button{border:1px solid #367566;background:#153d36;color:#91e8d1;border-radius:var(--ui-radius-control);padding:8px 12px;font-size:var(--ui-font-caption)}
.diagram-toolbar span{flex:1 1 180px;font-size:var(--ui-font-caption);line-height:var(--ui-line-height);color:#b2c4cf}
.process-diagram-viewport{width:100%;overflow-x:auto;overscroll-behavior-x:contain;scrollbar-color:#6092ad #132435;scrollbar-width:auto}
.process-diagram-viewport:focus-visible{outline:3px solid var(--ui-focus-on-dark);outline-offset:-3px}
.process-diagram-viewport.expanded>svg{width:1000px;min-width:1000px;min-height:300px;max-height:none}
@media(prefers-reduced-motion:reduce){.process-diagram-viewport{scroll-behavior:auto}}
</style>
