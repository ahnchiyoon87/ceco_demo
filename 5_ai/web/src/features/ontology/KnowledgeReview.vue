<script setup>
import { ref, computed, onMounted, onUnmounted, nextTick } from 'vue'
import GraphEvidence from './GraphEvidence.vue'
const emit = defineEmits(['published'])
const candidate = ref(null), preview = ref(null), error = ref(''), note = ref(''), busy = ref(false)
const sourceFiles = ref([]), history = ref([]), selected = ref(null), result = ref(null), acknowledged = ref(false)
const filename = ref('')
const workspace=ref('sources')
const workspaces=[['sources','원본 자료','등록 · 분석 대상 선택'],['build','관계 후보 생성','도구 실행 · 생성 결과'],['review','담당자 검토','관계 · 출처 · 게시'],['history','게시 이력','검토 내용 · 게시 결과']]
const selectedSources = ref([])
const buildQuestion=ref('알람의 센서가 어느 설비에 속하며 어떤 문서를 근거로 대응해야 하는지, 원본 근거와 함께 관계 후보를 제안해 주세요.')
const buildRun=ref(null), buildHistory=ref([])
const buildConnection=ref('idle'), buildLastSeen=ref('')
const buildStateNames={running:'처리 중',candidate:'검토 후보 준비됨',failed:'실패 · 게시 안 됨',interrupted:'중단 · 게시 안 됨'}
const toolNames={read_registered_source:'선택 원본 읽기',read_extracted_structure:'추출된 센서·문서 구조 읽기'}
const buildStages={
  model_requested:['AI 관계 조사 요청','선택 원본과 질문을 전달했습니다. 도구 조회와 후보 응답을 기다립니다.'],
  model_returned:['AI 후보 응답 수신','응답을 받았습니다. 아직 원문 대조와 후보 구조 검증 전입니다.'],
  source_quotes_verified:['원문 인용 대조 통과','제안한 항목의 인용이 선택 원본에 실제로 있는지 확인했습니다. 관계의 적절성은 담당자가 검토해야 합니다.'],
  source_quote_validation:['원문 인용 불일치',''],
  candidate_structure_validation:['후보 연결 오류 확인',''],
  candidate_validation:['후보 구조 검증 시작','노드 식별정보와 관계의 연결 대상 등 검토 가능한 구조인지 검사합니다.'],
  candidate_validated:['후보 구조 검증 통과','검토 가능한 후보 구조를 확인했습니다. 최종 후보 저장과 담당자 검토가 남아 있습니다.']
}
function stageDescription(entry){
  if(entry.stage==='candidate_structure_validation')return entry.repair_requested?'없는 노드 참조 또는 중복 항목이 있어 실제 ID 목록과 오류를 전달하고 1회 수정을 요청했습니다.':'수정 후에도 연결 오류가 남아 후보 생성을 중단했습니다. 게시하지 않았습니다.'
  if(entry.stage==='source_quote_validation')return entry.repair_requested?'원문과 다른 인용을 발견해 1회 수정을 요청했습니다.':'수정 후에도 인용이 일치하지 않아 후보 생성을 중단했습니다.'
  return buildStages[entry.stage]?.[1] || '저장된 처리 기록입니다.'
}
const candidateHeading=ref(null)
const lifecycle=computed(()=> {
  if (buildRun.value?.status==='running') return '02 관계 후보 생성 중 · 원본 조회 도구 기록을 확인하세요.'
  if (result.value) return '04 게시 결과 확인 · 검토한 후보의 게시 응답을 확인하세요.'
  if (preview.value) return '03 사람 검토 · 출처·관계·미확인 사항을 확인한 뒤 게시하세요.'
  if (buildRun.value?.status==='candidate') return '02 관계 후보 생성됨 · 생성된 관계 후보 검토를 눌러 확인하세요.'
  if (['failed','interrupted'].includes(buildRun.value?.status)) return '02 후보 생성 실패·중단 · 게시되지 않았습니다. 오류와 원본을 확인하세요.'
  return sourceFiles.value.length ? '01 원본 자료 준비됨 · 분석할 자료를 선택하세요.' : '01 원본 자료 등록 대기 · 자료를 먼저 등록하세요.'
})
let buildPoll, buildStream, buildGeneration=0, mounted=true
function closeBuildStream(){buildStream?.close();buildStream=null}
function buildOffline(){
  if(buildRun.value?.status!=='running')return
  buildGeneration++;clearTimeout(buildPoll);closeBuildStream();buildConnection.value='disconnected'
}
function buildOnline(){
  if(buildRun.value?.id&&buildRun.value.status==='running')pollBuild(buildRun.value.id)
}
function connectBuildStream(id){
  closeBuildStream()
  if(typeof EventSource==='undefined')return false
  const stream=new EventSource(`/api/knowledge/builds/${id}/stream`)
  buildStream=stream;buildConnection.value='connecting'
  stream.addEventListener('build',event=>{
    if(!mounted||buildStream!==stream||buildRun.value?.id!==id)return
    try{
      const run=JSON.parse(event.data)
      if(run.id!==id)throw new Error('실행 식별정보가 다릅니다.')
      buildRun.value=run;buildLastSeen.value=new Date().toLocaleTimeString('ko-KR')
      buildConnection.value=run.status==='running'?'stream':'complete'
      if(run.status!=='running'){closeBuildStream();refresh()}
    }catch{fallback()}
  })
  function fallback(){
    if(!mounted||buildStream!==stream||buildRun.value?.id!==id)return
    closeBuildStream();buildConnection.value='fallback';clearTimeout(buildPoll);buildPoll=setTimeout(()=>pollBuild(id),3000)
  }
  stream.addEventListener('unavailable',fallback)
  stream.onerror=fallback
  return true
}
const assetName=ref(''), assetDescription=ref(''), relationFrom=ref(''), relationTo=ref(''), relationType=ref('HAS_SENSOR')
const assetDevice=ref(''), relationReason=ref('')
const devices=computed(()=>candidate.value?.nodes.filter(n=>n.class==='Device')||[])
const relationTypes=['HAS_SENSOR','INSTALLED_IN','HAS_PROCEDURE','GOVERNED_BY','DESCRIBED_BY','EXPOSES_ASSET']
const issueLabels={
  'Explicit asset-to-sensor membership requires review.':'각 센서가 어느 설비에 달려 있는지 원본을 보고 연결해야 합니다.',
  'A writable control point does not grant AI execution permission.':'값을 쓸 수 있는 제어 항목이어도 AI가 바로 조작할 수 있다는 뜻은 아닙니다.',
  'Alarm logic is in Flink SQL; tag limits alone are not the alarm contract.':'알람 조건은 Flink의 분석 규칙에 있습니다. 센서의 상한·하한만으로 모든 알람 조건을 설명할 수는 없습니다.'
}
async function request(path, options={}) {
  let response
  try{response = await fetch(path, { ...options, signal:AbortSignal.timeout(30000) })}
  catch(e){
    if(e.name==='TimeoutError'||e.name==='AbortError')throw new Error('서버 응답을 30초 안에 받지 못했습니다. 연결 상태를 확인한 뒤 다시 조회하세요.')
    if(e instanceof TypeError)throw new Error('서버에 연결하지 못했습니다. 인터넷과 서비스 연결 상태를 확인한 뒤 다시 시도하세요.')
    throw e
  }
  let data
  try{data=await response.json()}
  catch{throw new Error(`서버 응답을 읽을 수 없습니다. 서비스 상태를 확인하세요. (HTTP ${response.status})`)}
  if (!response.ok) {
    const detail = typeof data.detail === 'string' ? data.detail : JSON.stringify(data.detail || data)
    throw new Error(detail || `요청 실패 (${response.status})`)
  }
  return data
}
async function refresh() {
  try {
    const [files, published, builds] = await Promise.all([request('/api/files'),request('/api/knowledge/published'),request('/api/knowledge/builds')])
    sourceFiles.value = files.uploads; history.value = published.items; buildHistory.value=builds.items
  } catch(e) { error.value = e.message }
}
async function upload(event) {
  const files = [...event.target.files]
  if (!files.length) return
  busy.value = true; error.value = ''
  const form = new FormData()
  files.forEach(file=>form.append('files',file))
  try { await request('/api/upload',{method:'POST',body:form}); await refresh() }
  catch(e) { error.value = e.message }
  finally { busy.value = false; event.target.value = '' }
}
async function readCandidate(event) {
  const file = event.target.files[0]
  if (!file) return
  error.value = ''
  busy.value = true
  try {
    if (file.size > 5*1024*1024) throw new Error('관계 후보 파일은 5MB 이하로 나누어 검토하세요.')
    let data
    try{data=JSON.parse(await file.text())}
    catch(e){if(e instanceof SyntaxError)throw new Error('JSON 형식이 올바르지 않습니다. 내보낸 후보 JSON 파일인지 확인하세요.');throw e}
    const checked = await request('/api/knowledge/preview', {method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)})
    candidate.value = checked.batch; preview.value = checked; selected.value = checked.batch.nodes[0]
    result.value = null; acknowledged.value = false; note.value = ''; filename.value = file.name
  } catch(e) { error.value = `후보를 불러오지 못했습니다. ${e.message}${candidate.value ? ' 기존 검토 후보는 유지했습니다.' : ''}` }
  finally { busy.value = false; event.target.value = '' }
}
async function prepareSources() {
  busy.value=true; error.value=''
  try {
    const prepared=await request('/api/knowledge/prepare',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filenames:selectedSources.value})})
    const checked=await reviewWireCandidate(prepared)
    candidate.value=checked.batch; preview.value=checked; selected.value=checked.batch.nodes[0]
    result.value=null; acknowledged.value=false; note.value=''
    filename.value='등록 원본의 구조 추출 결과 · AI 의미 추론 아님'
  } catch(e) { error.value=`구조를 추출하지 못했습니다. ${e.message}${candidate.value ? ' 기존 검토 후보는 유지했습니다.' : ''}` }
  finally { busy.value=false }
}
async function reviewWireCandidate(checked){
  // JSON numbers such as Python 10.0 arrive in JS as 10. Obtain the review
  // digest for the exact browser payload BEFORE showing it for approval.
  const reviewed=await request('/api/knowledge/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(checked.batch)})
  return {...checked,...reviewed}
}
async function pollBuild(id) {
  clearTimeout(buildPoll)
  const token=++buildGeneration
  try {
    const run=await request(`/api/knowledge/builds/${id}`)
    if(!mounted||token!==buildGeneration||buildRun.value?.id!==id)return
    buildRun.value=run
    buildLastSeen.value=new Date().toLocaleTimeString('ko-KR')
    if(run.status==='running'){
      if(!connectBuildStream(id)){buildConnection.value='polling';buildPoll=setTimeout(()=>pollBuild(id),3000)}
    }else{buildConnection.value='complete';await refresh()}
  } catch(e){if(mounted&&token===buildGeneration&&buildRun.value?.id===id){buildConnection.value='disconnected';buildPoll=setTimeout(()=>pollBuild(id),6000)}}
}
async function startBuild() {
  busy.value=true;error.value='';clearTimeout(buildPoll);closeBuildStream();buildGeneration++
  try {
    buildRun.value=await request('/api/knowledge/build',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({filenames:selectedSources.value,question:buildQuestion.value})})
    await pollBuild(buildRun.value.id)
  } catch(e){error.value=e.message}
  finally{busy.value=false}
}
async function openBuild(run) {
  buildGeneration++;clearTimeout(buildPoll);closeBuildStream();buildLastSeen.value='';buildConnection.value='connecting';buildRun.value={id:run.id};await pollBuild(run.id)
}
async function useBuildCandidate() {
  const source=buildRun.value?.result, id=buildRun.value?.id
  if(!source||busy.value)return
  busy.value=true;error.value=''
  try{
    const checked=await reviewWireCandidate(source)
    candidate.value=JSON.parse(JSON.stringify(checked.batch));preview.value=checked;selected.value=candidate.value.nodes[0]
    result.value=null;acknowledged.value=false;note.value='';filename.value='AI 의미 관계 후보 · '+id.slice(0,8)
    workspace.value='review'
    await nextTick()
    candidateHeading.value?.scrollIntoView({block:'start'})
    candidateHeading.value?.focus({preventScroll:true})
  }catch(e){error.value=`후보를 검토용으로 준비하지 못했습니다. ${e.message}${candidate.value?' 기존 검토 후보는 유지했습니다.':''}`}
  finally{busy.value=false}
}
async function publish() {
  if (!preview.value || !acknowledged.value || note.value.trim().length<5 || busy.value) return
  busy.value = true; error.value = ''
  try {
    result.value = await request('/api/knowledge/publish',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({batch:candidate.value,expected_sha256:preview.value.sha256,review_note:note.value.trim()})})
    await refresh(); emit('published')
  } catch(e) { error.value = e.message }
  finally { busy.value = false }
}
async function reconcileAssets() {
  busy.value=true;error.value='';acknowledged.value=false;result.value=null
  try {
    const checked=await request('/api/knowledge/reconcile-assets',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(candidate.value)})
    candidate.value=checked.batch;preview.value=checked;selected.value=checked.batch.nodes.find(n=>n.class==='Asset')||checked.batch.nodes[0]
  } catch(e){error.value=e.message}
  finally{busy.value=false}
}
async function validateChange(changed) {
  busy.value=true; error.value=''; acknowledged.value=false; result.value=null
  try {
    const checked=await request('/api/knowledge/preview',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(changed)})
    candidate.value=checked.batch; preview.value=checked
    selected.value=checked.batch.nodes.find(n=>n.id===selected.value?.id)||checked.batch.nodes[0]
  } catch(e) { error.value=e.message }
  finally { busy.value=false }
}
async function addAsset() {
  const device=devices.value.find(n=>n.id===assetDevice.value)
  if (!device) {error.value='새 설비가 속할 Device를 선택하세요.';return}
  const name=assetName.value.trim()
  if (!name) return
  const changed=JSON.parse(JSON.stringify(candidate.value))
  const id=`${device.id}/asset/${name}`
  if(changed.nodes.some(node=>node.id===id)){error.value='같은 Device에 동일한 설비가 이미 있습니다.';return}
  changed.nodes.push({id,class:'Asset',properties:{name,description:assetDescription.value.trim(),site:device.properties.site,device:device.properties.name,mapping_method:'reviewer-defined',environment:'simulation'}})
  changed.relationships.push({from_id:device.id,to_id:id,type:'EXPOSES_ASSET'})
  await validateChange(changed)
  if(!error.value){assetName.value='';assetDescription.value=''}
}
async function addRelation() {
  if(!relationFrom.value||!relationTo.value||relationReason.value.trim().length<5)return
  const changed=JSON.parse(JSON.stringify(candidate.value))
  if(changed.relationships.some(r=>r.from_id===relationFrom.value&&r.to_id===relationTo.value&&r.type===relationType.value)){
    error.value='동일한 연결 관계가 이미 있습니다.';return
  }
  changed.relationships.push({from_id:relationFrom.value,to_id:relationTo.value,type:relationType.value,
    properties:{mapping_method:'reviewer-defined',mapping_reason:relationReason.value.trim()}})
  await validateChange(changed)
  if(!error.value)relationReason.value=''
}
onMounted(()=>{refresh();globalThis.addEventListener?.('offline',buildOffline);globalThis.addEventListener?.('online',buildOnline)})
onUnmounted(()=>{mounted=false;buildGeneration++;clearTimeout(buildPoll);closeBuildStream();buildRun.value=null;globalThis.removeEventListener?.('offline',buildOffline);globalThis.removeEventListener?.('online',buildOnline)})
</script>

<template>
  <section class="knowledge-review">
    <div class="knowledge-intro"><div><p class="eyebrow">KNOWLEDGE LIFECYCLE</p><h2>원본에서, 검토된 지식으로.</h2><p>자료 등록 → 관계 후보 확인 → 검토 후 게시</p></div><span class="knowledge-badge">검토 내용과 게시 내용을 해시로 대조</span></div>
    <p class="knowledge-stage" role="status">현재 단계: {{lifecycle}}</p>
    <p v-if="preview && workspace!=='review'" class="candidate-ready">검토할 후보가 준비되었습니다. 노드 {{preview.node_count}}개 · 관계 {{preview.relationship_count}}개 <button class="file-button" @click="workspace='review'">후보 검토 열기</button></p>
    <div v-if="error" class="mfg-error" role="alert">{{error}}</div>
    <div class="knowledge-overview"><article><span>등록된 원본</span><b>{{sourceFiles.length}}<small>개</small></b></article><article><span>이번 분석 대상</span><b>{{selectedSources.length}}<small>개 선택</small></b></article><article><span>게시 이력</span><b>{{history.length}}<small>건</small></b></article><article><span>현재 후보</span><b>{{preview?.node_count ?? '—'}}<small>노드</small></b></article></div>
    <nav class="knowledge-workspaces" aria-label="지식 구축 작업 선택"><button v-for="[key,title,description] in workspaces" :key="key" :aria-pressed="workspace===key" :class="{selected:workspace===key,working:key==='build'&&buildRun?.status==='running'}" @click="workspace=key"><b>{{title}}</b><small>{{description}}</small></button></nav><div v-show="workspace==='sources'" class="knowledge-inputs">
      <article><span class="step-number">01</span><h3>원본 자료 등록</h3><p>설정·목록·문서를 원본 작업 공간에 보관합니다. 등록만으로 설비 관계가 확정되지는 않습니다.</p><label class="file-button">자료 선택<input type="file" multiple :disabled="busy" @change="upload"></label><details v-if="sourceFiles.length" open><summary>등록된 자료 {{sourceFiles.length}}개</summary><ul><li v-for="(file,index) in sourceFiles" :key="index"><label><input type="checkbox" v-model="selectedSources" :value="file.name" :disabled="busy"> {{file.name}}</label></li></ul><button class="file-button" :disabled="busy||!selectedSources.length" @click="prepareSources">선택 자료에서 구조 추출</button><p>AR-100 YAML · Markdown/TXT 지원. 센서 목록과 문서 절 구조를 추출합니다. 설비 소속 관계는 별도로 검토합니다.</p></details></article>
      <article><span class="step-number">02</span><h3>관계 후보 불러오기</h3><p>설정 추출기 또는 지식 구축 작업이 만든 JSON을 검토합니다. 노드·관계·출처·미확인 사항을 확인하세요.</p><label class="file-button">후보 JSON 선택<input type="file" accept=".json,application/json" :disabled="busy" @change="readCandidate"></label><p v-if="filename" class="selected-file">{{filename}}</p></article>
    </div>
    <section v-show="workspace==='build'" class="meaning-builder"><div><h3>AI 의미 관계 제안</h3><p>선택한 원본을 읽고, 구조 추출만으로 알 수 없는 설비 소속·적용 문서 관계를 제안합니다. 결과는 검토 전 후보로 저장됩니다.</p></div><label for="knowledge-question">이 자료로 답하려는 질문</label><textarea id="knowledge-question" v-model="buildQuestion" rows="2" maxlength="3000" :disabled="busy||buildRun?.status==='running'"></textarea><button class="file-button" :disabled="busy||!selectedSources.length||buildQuestion.trim().length<10||buildRun?.status==='running'" @click="startBuild">{{buildRun?.status==='running'?'원본 분석 중…':'선택 원본으로 의미 관계 제안'}}</button><div v-if="buildRun" class="build-status" role="status"><p v-if="buildRun.status==='running'">모델이 원본과 추출 구조를 확인하고 있습니다. 실행 {{buildRun.id.slice(0,8)}}</p><p v-if="['failed','interrupted'].includes(buildRun.status)" class="mfg-error">{{buildRun.error}}</p><template v-if="buildRun.status==='candidate'"><p>{{buildRun.result.summary}}</p><button class="file-button" @click="useBuildCandidate">생성된 관계 후보 검토</button></template></div><details v-if="buildHistory.length"><summary>의미 분석 실행 기록 {{buildHistory.length}}건</summary><button v-for="run in buildHistory" :key="run.id" class="build-history-item" @click="openBuild(run)">{{new Date(run.created_at).toLocaleString('ko-KR')}} · {{buildStateNames[run.status] || run.status}} · {{run.question}}</button></details></section>
    <section v-if="buildRun" v-show="workspace==='build'" class="knowledge-tool-trace"><header><b>원본 조회 도구 기록</b><span>{{buildStateNames[buildRun.status] || '상태 확인 중'}} · {{buildRun.model || '모델 확인 중'}}</span></header><p class="build-connection" role="status">{{({idle:'실행 선택 대기',connecting:'진행 기록 연결 중',stream:'실시간 기록 연결됨',fallback:'스트림 연결 끊김 · 조회로 다시 연결합니다',polling:'진행 기록 주기적 조회 중',disconnected:'연결 끊김 · 마지막 기록을 유지하며 재연결 중',complete:'저장된 최종 기록'})[buildConnection]}}<span v-if="buildLastSeen"> · 마지막 수신 {{buildLastSeen}}</span></p><p v-if="!(buildRun.trace||[]).some(t=>t.tool||t.stage)">{{buildRun.status==='running'?'도구 호출 결과를 기다립니다. 실제 조회 기록이 저장되면 표시됩니다.':'저장된 조회 도구 기록이 없습니다.'}}</p><ol><li v-for="(entry,index) in (buildRun.trace||[]).filter(t=>t.tool||t.stage)" :key="index"><b>{{toolNames[entry.tool] || buildStages[entry.stage]?.[0] || entry.tool || entry.stage}}</b><time v-if="entry.at">{{new Date(entry.at).toLocaleTimeString('ko-KR')}}</time><p v-if="entry.stage">{{stageDescription(entry)}}</p><p v-else>{{entry.filename || '추출된 구조'}} <span v-if="entry.nodes!=null">· 노드 {{entry.nodes}} · 관계 {{entry.relationships}}</span></p><details><summary>처리 기록 상세</summary><pre>{{JSON.stringify(entry,null,2)}}</pre></details></li></ol><p v-if="buildRun.error" class="mfg-error" role="alert">{{buildRun.error}}</p><small>실행 {{buildRun.id}} · 후보 생성 후에도 사람 검토와 게시가 필요합니다.</small></section>
    <div v-if="busy" class="panel-hint" role="status">처리 중입니다. 결과를 확인할 때까지 기다려 주세요.</div>
    <p v-if="workspace==='review'&&!preview" class="panel-hint">원본 구조를 추출하거나 생성된 관계 후보를 선택하면 출처와 관계를 검토할 수 있습니다.</p><div v-if="preview" v-show="workspace==='review'">
      <div ref="candidateHeading" class="candidate-heading" tabindex="-1"><h3>검토할 관계 후보</h3><span>노드 {{preview.node_count}} · 관계 {{preview.relationship_count}}</span></div>
      <div v-if="candidate.nodes.some(n=>n.class==='Asset')" class="identity-review">
        <button class="file-button" :disabled="busy" @click="reconcileAssets">설비 식별자 정리</button>
        <p>명시된 사이트·장치·설비 이름으로 식별자를 맞춥니다. 소속이 불명확하면 정리하지 않습니다.</p>
        <div v-if="preview.identity_changes" role="status">
          <p v-if="!Object.keys(preview.identity_changes).length">식별자 변경이 필요하지 않습니다.</p>
          <p v-for="(next,previous) in preview.identity_changes" :key="previous"><code>{{previous}}</code> → <code>{{next}}</code></p>
          <p>관계와 원본 인용은 보존됩니다. 변경된 후보를 확인한 뒤 게시하세요.</p>
        </div>
      </div>
      <div class="candidate-browser"><div class="candidate-list"><button v-for="node in candidate.nodes" :key="node.id" :class="{active:selected?.id===node.id}" :aria-pressed="selected?.id===node.id" @click="selected=node"><small>{{node.class}}</small><b>{{node.properties.name||node.id}}</b></button></div><div v-if="selected" class="candidate-detail"><h4>{{selected.properties.name||selected.id}}</h4><code>{{selected.id}}</code><GraphEvidence :properties="selected.properties" /><h4>연결 관계</h4><ul><li v-for="(rel,index) in candidate.relationships.filter(r=>r.from_id===selected.id||r.to_id===selected.id)" :key="index">{{rel.from_id}} <b>— {{rel.type}} →</b> {{rel.to_id}}<details v-if="Object.keys(rel.properties||{}).length"><summary>연결 근거와 출처</summary><GraphEvidence :properties="rel.properties" /></details><p v-else>별도 출처 속성 없음 · 원본과 검토 사유를 확인하세요.</p></li></ul></div></div>
      <details class="mapping-editor"><summary>설비와 적용 관계 설계</summary><p>센서의 설비 소속과 적용 문서는 검토자가 명시합니다. 변경하면 검토 해시를 다시 계산합니다.</p><div class="mapping-row"><select v-model="assetDevice" aria-label="설비가 속할 Device" :disabled="busy"><option value="">상위 Device 선택</option><option v-for="device in devices" :key="device.id" :value="device.id">{{device.properties.name||device.id}} · {{device.properties.site||'사이트 미제공'}}</option></select><input v-model="assetName" aria-label="설비 이름" placeholder="설비 이름 (예: M-101)" :disabled="busy"><input v-model="assetDescription" aria-label="설비 설명" placeholder="설비 설명" :disabled="busy"><button :disabled="busy||!assetName.trim()||!devices.some(device=>device.id===assetDevice)" @click="addAsset">설비 추가</button></div><div class="mapping-row"><select v-model="relationFrom" aria-label="관계 출발 노드" :disabled="busy"><option value="">출발 노드 선택</option><option v-for="node in candidate.nodes" :key="node.id" :value="node.id">{{node.class}} · {{node.properties.name||node.id}}</option></select><select v-model="relationType" aria-label="관계 유형" :disabled="busy"><option v-for="type in relationTypes" :key="type">{{type}}</option></select><select v-model="relationTo" aria-label="관계 도착 노드" :disabled="busy"><option value="">도착 노드 선택</option><option v-for="node in candidate.nodes" :key="node.id" :value="node.id">{{node.class}} · {{node.properties.name||node.id}}</option></select><input v-model="relationReason" aria-label="관계 연결 사유" placeholder="연결 근거·사유 (5자 이상)" maxlength="2000" :disabled="busy"><button :disabled="busy||!relationFrom||!relationTo||relationReason.trim().length<5" @click="addRelation">관계 추가</button></div></details>
      <div v-if="preview.unresolved.length" class="unresolved-box"><b>미확인 사항 {{preview.unresolved.length}}개</b><ul><li v-for="item in preview.unresolved" :key="item">{{issueLabels[item] || item}}</li></ul></div>
      <div class="publish-box"><span class="step-number">03</span><div><h3>검토 후 게시</h3><p class="panel-hint">동일 ID의 속성을 갱신하고 관계를 추가·병합합니다. 이 후보에서 빠진 기존 노드와 관계는 삭제하지 않습니다.</p><label class="acknowledge"><input type="checkbox" v-model="acknowledged" :disabled="busy||!!result"> 출처와 관계, 미확인 사항을 확인했습니다.</label><textarea v-model="note" :disabled="busy||!!result" rows="2" maxlength="2000" placeholder="검토 범위와 남은 제약을 기록하세요. (5자 이상)"></textarea><p class="hash-line">검토 해시 {{preview.sha256}}</p><button class="publish-button" :disabled="busy||!acknowledged||note.trim().length<5||!!result" @click="publish">Neo4j에 게시</button><p v-if="result" role="status" class="publish-result">{{result.duplicate?'이미 게시된 동일 내용입니다. 중복 적재하지 않았습니다.':'게시 완료. 관계 탐색과 사건 근거 조회에 반영됩니다.'}}</p></div></div>
    </div>
    <section v-if="workspace==='review'&&!candidate" class="empty-review" role="status"><h3>아직 선택한 검토 후보가 없습니다</h3><p>원본에서 구조를 추출하거나, 저장된 AI 실행의 후보를 열어 출처와 관계를 검토하세요.</p><button class="file-button" @click="workspace='sources'">원본 자료 선택</button> <button class="file-button" @click="workspace='build'">생성된 후보 찾기</button></section>    <details v-show="workspace==='history'" open class="publication-history"><summary>게시 이력 {{history.length}}건</summary><article v-for="row in history" :key="row.sha256"><b>{{new Date(row.published_at).toLocaleString('ko-KR')}}</b><p>{{row.review_note}}</p><code>{{row.sha256}}</code></article></details>
  </section>
</template>

<style scoped>
.knowledge-workspaces{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:10px;margin:20px 0}.knowledge-workspaces button{padding:16px;border:1px solid #b6cbd1;border-radius:10px;background:#f4f8fa;color:#294c5d;text-align:left;min-height:74px}.knowledge-workspaces small{display:block;margin-top:6px}.knowledge-workspaces .selected{background:#173e49;color:#fff;border-color:#173e49}.knowledge-workspaces .working{box-shadow:inset 0 -4px #29b79b}.candidate-detail{font-size:var(--ui-font-caption)!important}.candidate-list b{font-size:var(--ui-font-caption)!important}.candidate-list button{min-height:48px}.candidate-detail ul{font-size:var(--ui-font-caption)!important;line-height:1.8}.candidate-detail code{color:#526d62!important}.knowledge-review h3{font-size:17px!important}.knowledge-inputs p,.meaning-builder p{font-size:var(--ui-font-caption)!important;color:#526d62!important}.file-button{font-size:var(--ui-font-caption)!important;min-height:40px}.knowledge-review details{font-size:var(--ui-font-caption)!important}@media(max-width:700px){.knowledge-workspaces{grid-template-columns:1fr 1fr}.candidate-browser{grid-template-columns:1fr!important;height:auto!important}.candidate-list{max-height:210px;border-right:0;border-bottom:1px solid #dce6e0}.candidate-detail{max-height:none;overflow:visible}.knowledge-overview{gap:8px}.knowledge-overview article{padding:12px}}
.candidate-ready{display:flex;align-items:center;flex-wrap:wrap;gap:12px;padding:12px 16px;background:#eef7f4;border:1px solid #bcdccd;border-radius:8px;color:#235d4d;font-size:var(--ui-font-body)}.knowledge-stage{padding:14px 18px;border:1px solid #a9cfc2;border-left:4px solid #167c68;border-radius:8px;background:#edf7f3;color:#24584b;font-size:var(--ui-font-body);line-height:var(--ui-line-height);margin:16px 0}
.knowledge-overview{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin:20px 0}.knowledge-overview article{border:1px solid #dce7e6;border-radius:10px;background:#f7faf9;padding:18px}.knowledge-overview span{display:block;font-size:var(--ui-font-caption);color:var(--ui-text-muted)}.knowledge-overview b{display:block;font-size:27px;color:#254f46;margin-top:6px}.knowledge-overview small{font-size:var(--ui-font-caption);margin-left:6px;color:var(--ui-text-muted)}.knowledge-tool-trace{margin:18px 0;padding:18px;border:1px solid #cbded8;background:#f4f9f7;border-radius:10px;font-size:var(--ui-font-caption)}.knowledge-tool-trace header{display:flex;justify-content:space-between;gap:12px;flex-wrap:wrap}.knowledge-tool-trace header span,.knowledge-tool-trace>small{color:#6e877e;font-size:var(--ui-font-caption)}.knowledge-tool-trace ol{list-style:none;padding:0}.knowledge-tool-trace li{padding:12px;margin:10px 0;border-radius:8px;background:white;border:1px solid #dce8e3}.knowledge-tool-trace time{float:right;color:#70877e;font-size:var(--ui-font-caption)}.knowledge-tool-trace pre{overflow:auto;max-height:180px;white-space:pre-wrap;overflow-wrap:anywhere;font-size:var(--ui-font-caption)}.knowledge-tool-trace p{font-size:var(--ui-font-caption);color:#5f7c70}.knowledge-tool-trace>small{overflow-wrap:anywhere}@media(max-width:650px){.knowledge-overview{grid-template-columns:repeat(2,minmax(0,1fr))}}

.meaning-builder{border:1px solid #d3e4dc;border-radius:9px;padding:20px;margin-top:18px;background:#f3f8f5}.meaning-builder p{font-size:var(--ui-font-caption);color:#758d7f;line-height:1.8}.meaning-builder label{display:block;font-size:var(--ui-font-caption);margin:14px 0 6px}.meaning-builder textarea{width:100%;border:1px solid #cbdcd3;border-radius:6px;background:white;padding:10px;font:inherit;font-size:var(--ui-font-caption);margin-bottom:10px}.build-history-item{display:block;text-align:left;width:100%;border:0;border-bottom:1px solid #dfebe4;background:none;font-size:var(--ui-font-caption);color:#54735f;padding:9px 0}.meaning-builder button:disabled{opacity:.5;cursor:default}
.mapping-editor{padding:15px;border:1px solid #dce6e0;border-radius:8px}.mapping-row{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}.mapping-row input,.mapping-row select{min-width:0;flex:1;border:1px solid #d5e0da;padding:7px;border-radius:5px;font-size:var(--ui-font-caption);background:white}.mapping-row button{border:1px solid #c1d6ca;background:#edf6f1;border-radius:5px;padding:7px 12px;font-size:var(--ui-font-caption)}
.knowledge-review{margin-bottom:28px;padding-bottom:25px;border-bottom:1px solid #e0e8e5}.knowledge-intro{display:flex;justify-content:space-between;gap:20px;align-items:center;margin:8px 0 22px}.knowledge-intro h2{font-size:21px;margin:0}.knowledge-intro p:not(.eyebrow){font-size:var(--ui-font-caption);color:var(--ui-text-muted);margin:7px 0}.knowledge-badge{font-size:var(--ui-font-caption);color:var(--ui-text-muted);border:1px solid #dbe8e2;border-radius:6px;padding:7px 10px}.knowledge-inputs{display:grid;grid-template-columns:1fr 1fr;gap:18px}.knowledge-inputs article{border:1px solid #e0e9e5;background:#f8fbfa;border-radius:9px;padding:20px}.step-number{font-size:var(--ui-font-caption);color:#176f60;font-weight:bold}.knowledge-review h3{font-size:var(--ui-font-body);margin:8px 0}.knowledge-inputs p{font-size:var(--ui-font-caption);color:var(--ui-text-muted);line-height:1.8;max-width:450px}.file-button{display:inline-block;border:1px solid #c8dbd2;color:#367b65;background:white;padding:7px 14px;border-radius:6px;font-size:var(--ui-font-caption);cursor:pointer}.file-button input{display:block;font-size:var(--ui-font-caption);margin-top:7px;max-width:220px}.knowledge-review details{font-size:var(--ui-font-caption);color:var(--ui-text-muted);margin-top:12px}.selected-file{word-break:break-all}.candidate-heading{display:flex;justify-content:space-between;margin:22px 0 8px;align-items:center}.candidate-heading span{font-size:var(--ui-font-caption);color:var(--ui-text-muted)}.candidate-browser{display:grid;grid-template-columns:220px minmax(0,1fr);height:380px;border:1px solid #dce6e0;border-radius:8px;overflow:hidden}.candidate-list{overflow:auto;border-right:1px solid #e2e9e5;padding:8px}.candidate-list button{display:block;text-align:left;width:100%;border:0;background:white;border-radius:5px;padding:9px 12px;color:#365849}.candidate-list button.active{background:#eaf5ef}.candidate-list small{display:block;font-size:var(--ui-font-caption);color:var(--ui-text-muted)}.candidate-list b{font-size:var(--ui-font-caption);word-break:break-word}.candidate-detail{overflow:auto;padding:16px 22px;font-size:var(--ui-font-caption)}.candidate-detail h4{margin:4px 0 9px;font-size:var(--ui-font-caption)}.candidate-detail code{font-size:var(--ui-font-caption);color:var(--ui-text-muted);word-break:break-all}.candidate-detail dl{display:grid;grid-template-columns:135px minmax(0,1fr);line-height:1.8}.candidate-detail dt{color:var(--ui-text-muted);border-top:1px solid #edf1ee;padding:7px 0}.candidate-detail dd{margin:0;padding:7px;border-top:1px solid #edf1ee;white-space:pre-wrap;overflow-wrap:anywhere}.candidate-detail ul{padding-left:17px;font-size:var(--ui-font-caption);overflow-wrap:anywhere}.unresolved-box{background:#fff8ed;color:#795b26;padding:13px 18px;border-radius:6px;margin-top:15px;font-size:var(--ui-font-caption)}.unresolved-box ul{margin:7px 0 0;padding-left:18px}.publish-box{display:flex;gap:15px;margin:23px 0;padding:19px;background:#f4f8f6;border-radius:8px}.publish-box>div{flex:1;min-width:0}.acknowledge{font-size:var(--ui-font-caption);display:block;margin:12px 0}.publish-box textarea{display:block;width:100%;font:inherit;font-size:var(--ui-font-caption);padding:10px;border:1px solid #ccdad2;border-radius:6px;background:white}.hash-line{font-size:var(--ui-font-caption);color:var(--ui-text-muted);overflow-wrap:anywhere}.publish-button{background:#187d67;border:0;color:white;padding:10px 20px;border-radius:6px;font-size:var(--ui-font-caption)}.publish-button:disabled{opacity:.45;cursor:default}.publish-result{font-size:var(--ui-font-caption);color:#24795a}.publication-history article{padding:12px;border-bottom:1px solid #e5ece7}.publication-history article p{margin:6px 0}.publication-history code{font-size:var(--ui-font-caption);overflow-wrap:anywhere}@media(max-width:1050px){.knowledge-inputs{grid-template-columns:1fr}.knowledge-badge{display:none}.candidate-browser{grid-template-columns:150px minmax(0,1fr)}.candidate-detail dl{grid-template-columns:1fr}}
.unresolved-box{font-size:var(--ui-font-caption);line-height:1.8;color:#795b20}.mapping-editor,.knowledge-review .mapping-editor p{font-size:var(--ui-font-caption)}.mapping-row input,.mapping-row select,.mapping-row button{font-size:var(--ui-font-caption);min-height:42px}.mapping-row input,.mapping-row select{flex:1 1 180px}.candidate-list small{font-size:var(--ui-font-caption)}.candidate-list b{font-size:var(--ui-font-caption)}.candidate-detail{font-size:var(--ui-font-caption)}.candidate-detail ul{font-size:var(--ui-font-caption);line-height:1.8}.publish-box textarea,.publish-button,.acknowledge{font-size:var(--ui-font-caption)}.hash-line{font-size:var(--ui-font-caption)}@media(max-width:650px){.mapping-row{display:grid;grid-template-columns:minmax(0,1fr)}.mapping-row input,.mapping-row select{width:100%}}.knowledge-review{line-height:1.65}.knowledge-review :is(button,input,textarea,select,summary):focus-visible{outline:3px solid #147e70;outline-offset:3px}.knowledge-review summary{min-height:36px;display:list-item;align-content:center}.build-history-item{min-height:48px;line-height:1.65;overflow-wrap:anywhere;padding:12px 4px}.knowledge-tool-trace li{font-size:var(--ui-font-body);line-height:var(--ui-line-height)}.knowledge-tool-trace time{float:none;display:block;margin-top:4px;color:#4d685f}.knowledge-tool-trace p,.knowledge-tool-trace header span,.knowledge-tool-trace>small{color:#49665d}.knowledge-tool-trace li b{font-size:var(--ui-font-body)}.build-connection{padding:10px 12px;background:#e5f1ed;border-radius:6px;line-height:var(--ui-line-height)}.knowledge-review :is(p,code,small,label){overflow-wrap:anywhere}.knowledge-review textarea{resize:vertical;min-height:76px}.knowledge-review .file-button input{width:100%;max-width:100%;min-width:0}.knowledge-inputs article{min-width:0}.publication-history article{font-size:var(--ui-font-body);line-height:1.8}.knowledge-workspaces button{line-height:1.6}@media(max-width:650px){.publish-box{flex-direction:column}.publish-button{min-height:44px}.candidate-heading{flex-wrap:wrap;gap:8px}.knowledge-tool-trace{padding:14px}.meaning-builder{padding:16px}.knowledge-workspaces button{padding:12px}.knowledge-tool-trace header{flex-direction:column;gap:5px}}
.knowledge-workspaces small{font-size:var(--ui-font-caption)}.empty-review{padding:var(--ui-space-panel);border:1px solid #cbded8;border-radius:var(--ui-radius-card);background:#f4f9f7;font-size:var(--ui-font-body)}.empty-review button{min-height:var(--ui-control-height);margin-top:var(--ui-space-sm)}</style>


