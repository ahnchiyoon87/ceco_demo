<script setup>
import {computed,ref,watch,nextTick,onMounted,onUnmounted} from 'vue'
import {layout,context,kind,name,kinds,relations,shorten} from './knowledgeMap.js'
const props=defineProps({graph:{type:Object,default:()=>({nodes:[],edges:[]})},loading:Boolean,error:String,loadedAt:String})
defineEmits(['refresh'])
const selected=ref(''),query=ref(''),map=ref(null),width=ref(1200)
const drawing=computed(()=>layout(props.graph,width.value))
const emphasis=computed(()=>context(props.graph,selected.value,query.value))
const current=computed(()=>props.graph.nodes.find(n=>n.id===selected.value))
const assets=computed(()=>props.graph.nodes.filter(n=>kind(n)==='Asset').sort((a,b)=>name(a).localeCompare(name(b),'ko',{numeric:true})))
const connections=computed(()=>props.graph.edges.filter(e=>e.from===selected.value||e.to===selected.value).map((e,i)=>{
 const outgoing=e.from===selected.value,id=outgoing?e.to:e.from
 return {...e,key:i,outgoing,neighbor:props.graph.nodes.find(n=>n.id===id),id}
}))
const original=computed(()=>Object.fromEntries(Object.entries(current.value?.properties||{}).filter(([k])=>k!=='embedding')))
const description=computed(()=>current.value?.properties?.description||current.value?.properties?.title||'')
const orderedEdges=computed(()=>[...drawing.value.edges].sort((a,b)=>Number(a.from===selected.value||a.to===selected.value)-Number(b.from===selected.value||b.to===selected.value)))
let observer
async function choose(id,bringIntoView=false){
 selected.value=id===selected.value?'':id
 if(!bringIntoView||!selected.value)return
 await nextTick()
 const n=drawing.value.nodes.find(n=>n.id===selected.value)
 if(n&&map.value){
  const box=map.value
  const top=n.y<box.scrollTop?Math.max(0,n.y-16):n.y+32>box.scrollTop+box.clientHeight?n.y+48-box.clientHeight:box.scrollTop
  const left=n.x<box.scrollLeft?Math.max(0,n.x-16):n.x+n.width>box.scrollLeft+box.clientWidth?n.x+n.width+16-box.clientWidth:box.scrollLeft
  if(top!==box.scrollTop||left!==box.scrollLeft)box.scrollTo({top,left,behavior:'smooth'})
 }
}
watch(()=>props.graph,()=>{if(selected.value&&!current.value)selected.value=''}, {deep:false})
watch(query,async()=>{
 await nextTick();const n=drawing.value.nodes.find(n=>emphasis.value.matches.has(n.id))
 if(n&&map.value)map.value.scrollTo({top:Math.max(0,n.y-65),left:Math.max(0,n.x-16),behavior:'smooth'})
})
onMounted(()=>{observer=new ResizeObserver(entries=>{const w=entries[0]?.contentRect.width;if(w>0)width.value=w});if(map.value)observer.observe(map.value)})
onUnmounted(()=>observer?.disconnect())
</script>

<template>
 <section class="knowledge-map" aria-label="지식 지도">
  <div class="map-toolbar">
   <label>중심 설비<select aria-label="중심 설비" :value="assets.some(n=>n.id===selected)?selected:''" @change="choose($event.target.value,true)"><option value="">전체 보기</option><option v-for="n in assets" :key="n.id" :value="n.id">{{name(n)}}</option></select></label>
   <label class="map-search">이름 검색<input v-model="query" type="search" aria-label="지식 지도 이름 검색" placeholder="설비, 원인, 문서 찾기"></label>
   <button v-if="selected||query" @click="selected='';query=''">전체 보기</button>
   <button :disabled="loading" @click="$emit('refresh')">{{loading?'조회 중…':'다시 읽기'}}</button>
  </div>
  <div class="map-legend" aria-label="지식 분류"><span v-for="g in drawing.columns" :key="g.key"><i :style="{background:g.color}"></i>{{g.title}} <b>{{g.nodes.length}}</b></span></div>
  <p class="map-caption" role="status">{{graph.nodes.length}}개 항목 · {{graph.edges.length}}개 관계<span v-if="selected"> · 선택한 항목과 직접 연결을 강조합니다.</span><span v-else> · 항목을 선택하면 연결 관계와 근거를 확인합니다.</span><span v-if="query"> · 검색 {{emphasis.matches.size}}개</span><span v-if="loadedAt" class="map-updated"> · {{new Date(loadedAt).toLocaleTimeString('ko-KR')}} 조회</span></p>
  <p v-if="error" class="map-error" role="alert">최신 조회를 완료하지 못했습니다. 마지막으로 받은 지도입니다.</p>
  <div ref="map" class="map-canvas" tabindex="0" role="region" aria-label="지식 지도, 가로와 세로로 이동 가능">
   <p v-if="!graph.nodes.length" class="map-empty">{{loading?'게시된 지식을 불러오고 있습니다.':error?'연결 상태를 확인한 뒤 다시 읽어 주세요.':'게시된 지식이 없습니다. 문서·지식에서 검토한 관계를 게시해 주세요.'}}</p>
   <svg v-else :width="drawing.width" :height="drawing.height" role="group" aria-label="종류별 설비 지식과 연결 관계">
    <g v-for="(g,i) in drawing.columns" :key="g.key"><rect :x="i*drawing.columnWidth+3" y="3" :width="drawing.columnWidth-6" :height="drawing.height-6" rx="8" :fill="g.color" fill-opacity=".04"/><text :x="i*drawing.columnWidth+14" y="28" class="map-column" :fill="g.color">{{g.title}}</text></g>
    <path v-for="e in orderedEdges" :key="e.key" :d="e.path" class="map-edge" :class="{hot:e.from===selected||e.to===selected,dim:(selected||query)&&e.from!==selected&&e.to!==selected}"><title>{{e.description}}</title></path>
    <text v-for="(h,i) in drawing.headings" :key="i" :x="h.x" :y="h.y" class="map-kind">{{h.label}}</text>
    <g v-for="n in drawing.nodes" :key="n.id" class="map-node" :class="{selected:n.id===selected,neighbor:emphasis.local.has(n.id),dim:emphasis.dim(n.id),match:emphasis.matches.has(n.id)}" :style="{'--node-color':n.color}" :data-id="n.id" role="button" tabindex="0" :aria-label="(kinds[kind(n)]||kind(n))+' · '+name(n)" :aria-pressed="n.id===selected" @click="choose(n.id)" @keydown.enter.prevent="choose(n.id)" @keydown.space.prevent="choose(n.id)">
     <rect :x="n.x" :y="n.y" :width="n.width" height="32" rx="5"/><text :x="n.x+9" :y="n.y+21" class="map-label">{{shorten(name(n),n.width)}}</text><title>{{kinds[kind(n)]||kind(n)}} · {{name(n)}}</title>
    </g>
   </svg>
  </div>
  <p class="map-hint">종류별로 정리한 전체 지도입니다. 지도 안에서 스크롤해 이동할 수 있습니다.</p>
  <section v-if="current" class="map-detail" aria-label="선택 항목의 연결과 근거">
   <div class="map-summary"><span>{{kinds[kind(current)]||kind(current)}}</span><h3>{{name(current)}}</h3><p v-if="description">{{description}}</p><details><summary>원본 속성과 출처</summary><pre>{{JSON.stringify(original,null,2)}}</pre></details></div>
   <div class="map-connections"><h4>연결 관계 <span>{{connections.length}}</span></h4><ul><li v-for="e in connections" :key="e.key"><span>{{e.outgoing?'→':'←'}} {{relations[e.type]||e.type}}</span><button @click="choose(e.id,true)">{{name(e.neighbor)}}</button></li></ul><p v-if="!connections.length">저장된 직접 연결이 없습니다.</p></div>
  </section>
 </section>
</template>

<style scoped>
.knowledge-map{min-width:0;color:#24364b}.map-toolbar{display:flex;align-items:end;gap:12px;flex-wrap:wrap;margin-bottom:16px}.map-toolbar label{display:flex;flex-direction:column;gap:6px;font-size:12px;color:#5b6c80}.map-toolbar select,.map-toolbar input{height:40px;padding:8px 12px;border:1px solid #d7e1e8;border-radius:7px;background:white;color:#273c4c;min-width:200px;font:inherit;font-size:14px}.map-search{flex:1;max-width:380px}.map-toolbar button{min-height:40px;padding:8px 14px;border:1px solid #d7e1e8;border-radius:7px;background:white;color:#35645b;font:inherit;font-size:13px;cursor:pointer}.map-toolbar button:disabled{opacity:.6;cursor:wait}.map-legend{display:flex;gap:8px;flex-wrap:wrap}.map-legend span{display:flex;gap:6px;align-items:center;padding:5px 9px;border:1px solid #e1e6ec;border-radius:15px;font-size:12px;background:white;color:#526174}.map-legend i{width:8px;height:8px;border-radius:2px}.map-legend b{font-weight:400;color:#758398}.map-caption,.map-hint{font-size:12px;line-height:1.7;color:#627486;margin:12px 0}.map-canvas{height:clamp(300px,48vh,520px);overflow:auto;border:1px solid #dfe6ec;border-radius:10px;background:white;max-width:100%}.map-canvas svg{display:block;font-family:'Segoe UI','Malgun Gothic',sans-serif}.map-column{font-size:14px;font-weight:600}.map-kind{font-size:11px;fill:#617184}.map-edge{fill:none;stroke:#9aa7b5;stroke-width:1;stroke-opacity:.15}.map-edge.dim{stroke-opacity:.025}.map-edge.hot{stroke:#c79123;stroke-width:2;stroke-opacity:.95}.map-node{cursor:pointer;transition:opacity .15s}.map-node rect{fill:white;stroke:var(--node-color);stroke-opacity:.55;stroke-width:1}.map-label{font-size:13px;fill:#26364c;pointer-events:none}.map-node.dim{opacity:.23}.map-node.neighbor rect{stroke-width:2;stroke-opacity:1}.map-node.selected rect{fill:var(--node-color);stroke-opacity:1}.map-node.selected text{fill:white;font-weight:600}.map-node.match rect{fill:#fff0c9;stroke-opacity:1;stroke-width:2}.map-node:hover rect{stroke-width:2;stroke-opacity:1}.map-node:focus{outline:none}.map-node:focus-visible rect{stroke-width:3;stroke-opacity:1}.map-empty{padding:30px;line-height:1.8;color:#627486}.map-detail{display:grid;grid-template-columns:minmax(220px,.75fr) minmax(0,1.5fr);gap:24px;border:1px solid #dfe6ec;border-radius:10px;background:#fff;padding:20px}.map-summary{min-width:0}.map-summary>span{font-size:12px;color:#65748b}.map-summary h3{font-size:18px;margin:6px 0 10px;overflow-wrap:anywhere}.map-summary p{font-size:13px;line-height:1.8;color:#526174;overflow-wrap:anywhere}.map-summary summary{font-size:12px;color:#577869;cursor:pointer;margin-top:14px}.map-summary pre{white-space:pre-wrap;overflow-wrap:anywhere;max-height:220px;overflow:auto;font-size:11px;background:#f7f9fc;padding:12px}.map-connections{min-width:0}.map-connections h4{font-size:14px;margin:0 0 12px}.map-connections h4 span{color:#65748b;font-weight:400}.map-connections ul{list-style:none;margin:0;padding:0;display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:8px 18px}.map-connections li{display:flex;gap:6px;align-items:center;flex-wrap:wrap;font-size:12px;border-bottom:1px solid #eef1f5;padding:7px 0;min-width:0}.map-connections li>span{color:#6b798b}.map-connections button{border:0;padding:2px 0;background:none;color:#17695b;font:inherit;font-weight:600;text-align:left;cursor:pointer;overflow-wrap:anywhere}.map-error{font-size:13px;color:#a54f2d}@media(max-width:700px){.map-toolbar label,.map-search{width:100%;max-width:none}.map-toolbar input,.map-toolbar select{min-width:0;width:100%}.map-detail{grid-template-columns:minmax(0,1fr);padding:16px}.map-connections ul{grid-template-columns:minmax(0,1fr)}}
</style>
