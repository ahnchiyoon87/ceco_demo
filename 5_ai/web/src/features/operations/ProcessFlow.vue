<script setup>
import {computed,useId} from 'vue'
import {processState} from './processState.js'
const props=defineProps({run:Object,proposal:Object,selected:String})
const emit=defineEmits(['select'])
const state=computed(()=>processState(props.run,props.proposal))
const arrowId='process-arrow-'+useId()
const arrow=()=>`url(#${arrowId})`
const labels={waiting:'대기',active:'진행 중',done:'기록 확인',warning:'확인 필요'}
const steps=[['received','이상 사건 접수',90],['investigate','Agent 근거 조사',290],['review','담당자 검토',490],['execute','조치·상태 확인',740],['result','결과 기록',940]]
</script>
<template>
<section class="process-flow" aria-label="실제 업무 처리 흐름">
  <header><div><small>LIVE PROCESS / 저장된 업무 상태</small><h3>이상 접수에서 조치 결과까지</h3></div><span :class="state.branch">{{state.outcome}}</span></header>
  <div class="diagram-scroll" role="region" tabindex="0" aria-label="업무 흐름도, 좁은 화면에서는 가로로 이동">
    <svg viewBox="0 0 1060 280" role="group" :aria-label="state.outcome">
      <defs><marker :id="arrowId" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0 0L8 4L0 8Z" fill="#6b8fa0"/></marker></defs>
      <rect x="8" y="24" width="1044" height="244" rx="14" class="pool"/><text x="26" y="48" class="lane-label">PILOT · 이상 대응 업무</text>
      <path v-for="line in ['M160 119H220','M360 119H420','M560 119H590','M650 119H670','M810 119H870']" :key="line" :d="line" class="connector" :marker-end="arrow()"/>
      <path d="M620 149V222H940V157" class="connector branch" :marker-end="arrow()" :class="{selected:state.branch==='rejected'}"/>
      <path d="M290 157V211" class="connector branch" :marker-end="arrow()" :class="{selected:state.branch==='evidence'}"/>
      <rect x="190" y="211" width="200" height="38" rx="8" class="gateway"/>
      <text x="290" y="235" text-anchor="middle" class="path-label">보완 필요 · 실행하지 않음</text>
      <text x="304" y="190" class="path-label">근거 부족</text><text x="770" y="211" text-anchor="middle" class="path-label">반려 · 명령 없음</text><text x="660" y="101" text-anchor="middle" class="path-label">승인</text>
      <path d="M620 89L650 119L620 149L590 119Z" class="gateway"/><text x="620" y="126" text-anchor="middle" class="gateway-symbol">×</text>
      <g v-for="[key,title,x] in steps" :key="key" :class="['step',state.nodes[key],{selected:selected===key}]" role="button" tabindex="0" :aria-label="title+' · '+labels[state.nodes[key]]" :aria-pressed="selected===key" @click="emit('select',key)" @keydown.enter.prevent="emit('select',key)" @keydown.space.prevent="emit('select',key)">
        <rect :x="x-70" y="81" width="140" height="76" :rx="key==='received'||key==='result'?35:10"/>
        <text :x="x" y="111" text-anchor="middle" class="step-title">{{title}}</text><text :x="x" y="137" text-anchor="middle" class="step-status">{{labels[state.nodes[key]]}}{{selected===key?' · 선택':''}}</text>
      </g>
      <text x="290" y="70" text-anchor="middle" class="path-label">알람 · 센서 · 문서 조회</text>
      <text x="740" y="180" text-anchor="middle" class="path-label">승인된 조치 · 새 상태 확인</text>
    </svg>
  </div>
  <nav class="compact-stages" aria-label="작업 카드 선택"><button v-for="[key,title] in steps" :key="key" :aria-pressed="selected===key" :class="[state.nodes[key],{selected:selected===key}]" @click="emit('select',key)"><b>{{title}}</b><small>{{labels[state.nodes[key]]}}</small></button><p>그림은 좌우로 밀어서 볼 수 있습니다. 위 버튼으로도 모든 카드를 선택할 수 있습니다.</p></nav>
  <footer><span><i class="active"></i>진행 중</span><span><i class="done"></i>기록 확인</span><span><i class="warning"></i>확인 필요</span><span>흰 테두리 · 선택한 카드</span></footer>
</section>
</template>
<style scoped>
.compact-stages{display:none}@media(max-width:1000px){.compact-stages{display:grid;grid-template-columns:1fr 1fr;gap:8px;padding:12px}.compact-stages button{min-height:48px;border:1px solid #547887;border-radius:8px;background:#203e4d;color:#e2edf1;text-align:left;padding:9px}.compact-stages small{display:block;margin-top:4px}.compact-stages .selected{border:2px solid white}.compact-stages .active{background:#12685e}.compact-stages .warning{background:#634522}.compact-stages p{grid-column:1/-1;color:#b7cdd8;font-size:12px;margin:0}}
@media(min-width:1000px) and (min-height:850px){.process-flow{position:sticky;top:8px;z-index:5;box-shadow:0 6px 18px #102b3926}}
.selection-label{fill:#fff;font-size:11px}.step{cursor:pointer}.step.selected rect,.step:focus rect{stroke:#fff;stroke-width:3;filter:drop-shadow(0 0 4px #91e6d5)}.step:focus{outline:none}
.diagram-scroll svg{min-width:720px!important}.path-label{font-size:12px!important}
.process-flow{background:#102b39;border:1px solid #2f5263;border-radius:14px;color:#e9f2f4;margin:12px 0 22px;overflow:hidden}.process-flow header{display:flex;flex-wrap:wrap;justify-content:space-between;gap:12px;padding:20px 22px}.process-flow small{font-size:11px;color:#94c4c8;letter-spacing:1px}.process-flow h3{color:#fff;font-size:18px;margin:6px 0!important}.process-flow header>span{font-size:13px;color:#a2e5d4;max-width:310px}.diagram-scroll{overflow-x:auto}.diagram-scroll svg{display:block;width:100%;min-width:780px}.pool{fill:#173544;stroke:#355668}.lane-label{fill:#a2c0ce;font-size:12px}.connector{fill:none;stroke:#6b8fa0;stroke-width:2}.branch{opacity:.5;stroke-dasharray:6 5}.branch.selected{opacity:1;stroke:#f5c477;stroke-width:3}.gateway{fill:#274958;stroke:#83a4b4}.gateway-symbol{fill:#d0e1e7;font-size:22px}.path-label{fill:#b4cbd5;font-size:11px}.step rect{fill:#203e4d;stroke:#527586;stroke-width:1.5}.step-title{fill:#e2edf1;font:13px 'Malgun Gothic',sans-serif;font-weight:700}.step-status{fill:#bacdd7;font-size:11px}.step.done rect{fill:#1b534c;stroke:#5ab59f}.step.active rect{fill:#12685e;stroke:#81f0ce;stroke-width:3;animation:breathe 2s ease-in-out infinite}.step.warning rect{fill:#634522;stroke:#e0b875}.process-flow footer{padding:0 22px 17px;display:flex;gap:16px;flex-wrap:wrap;font-size:11px;color:#b7cdd8}.process-flow footer i{display:inline-block;width:7px;height:7px;border-radius:50%;margin-right:6px;background:#67dfbd}.process-flow footer i.done{background:#389d84}.process-flow footer i.warning{background:#e0b875}.process-flow footer p{width:100%;margin:0;line-height:1.7}@keyframes breathe{50%{stroke-opacity:.45}}@media(prefers-reduced-motion:reduce){.step.active rect{animation:none}}
</style>
