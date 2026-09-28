from pathlib import Path
p=Path(__file__).resolve().parents[1]/'ai-web/src/App.vue'
s=p.read_text(encoding='utf-8')
s=s.replace("import './manufacturing.css'", "import './manufacturing.css'\nimport SimulationControls from './features/operations/SimulationControls.vue'\nimport KnowledgeCoverage from './features/ontology/KnowledgeCoverage.vue'")
s=s.replace("const evidencePanel=ref(null)", "const detailTab=ref('review'), query=ref(''), statusFilter=ref('all')\nconst filteredIncidents=computed(()=>list.value.filter(x=>(statusFilter.value==='all'||x.status===statusFilter.value)&&[x.device,x.alarm?.tag,x.correlation_key,x.id].join(' ').toLowerCase().includes(query.value.toLowerCase())))\nconst evidencePanel=ref(null)")
s=s.replace("list.value.find(item=>item.id===selected.value?.id)","incidents.value.find(item=>item.id===selected.value?.id)")
s=s.replace("async function choose(item){", "async function choose(item){detailTab.value='review';")
s=s.replace("<template v-if=\"page==='scada'\"><ScadaLive />", "<template v-if=\"page==='scada'\"><SimulationControls @inspect=\"go('operations');refresh()\"/><ScadaLive />")
s=s.replace('운영 워크스페이스','이상 대응 · AI 검토').replace('알람 너머, 다음 행동까지.','이상 대응 현황').replace('설비의 맥락을 연결합니다.','설비 지식 스튜디오')
s=s.replace('반복 신호를 묶어 맥락을 확인합니다.</p><div class="incident-list">', '''최근 100건에서 검색합니다. 새 이상 발생 시 최신 사건을 선택하세요.</p><div class="case-filters"><label for="case-search">사건 검색</label><input id="case-search" v-model="query" type="search" placeholder="센서 · 설비 · 사건 ID"/><label for="case-status">처리 상태</label><select id="case-status" v-model="statusFilter"><option value="all">전체 상태</option><option v-for="(label,key) in statusLabels" :key="key" :value="key">{{label}}</option></select></div><div class="incident-list">''')
s=s.replace('v-for="item in list"','v-for="item in filteredIncidents"')
s=s.replace('v-if="!list.length" class="empty-state">접수된 사건이 없습니다.<br>SCADA 알람 수신을 기다리고 있습니다.', 'v-if="!filteredIncidents.length" class="empty-state">표시할 사건이 없습니다.<br>검색 조건 또는 알람 수신 상태를 확인하세요.')
start=s.index('<nav class="evidence-jumps"')
end=s.index('<div class="workflow-steps">',start)
s=s[:start]+'''<nav class="evidence-jumps" aria-label="사건 상세"><button :class="{active:detailTab==='review'}" @click="detailTab='review'">AI 분석 · 검토 · 결과</button><button :class="{active:detailTab==='evidence'}" @click="detailTab='evidence'">센서 · 매뉴얼 근거</button><button :class="{active:detailTab==='history'}" @click="detailTab='history'">전체 처리 이력</button></nav>'''+s[end:]
start=s.index('<div class="workflow-steps">')
end=s.index('<div v-if="busy"',start)
s=s[:start]+'''<p class="case-state" role="status"><span>선택한 사건</span><b>{{statusLabel(currentIncident?.status)}}</b><code>{{selected.id.slice(0,8)}}</code></p><div v-show="detailTab==='evidence'">'''+s[end:]
s=s.replace('<IncidentReview :incident-id=', '</div><IncidentReview v-show="detailTab===\'review\'" :incident-id=')
s=s.replace('<IncidentTimeline :incident-id=', '<IncidentTimeline v-if="detailTab===\'history\'" :incident-id=')
s=s.replace('<KnowledgeReview @published="loadGraph" />', '<KnowledgeCoverage :graph="graph" :loading="graphLoading" :error="graphError"/><KnowledgeReview @published="loadGraph" />')
p.write_text(s,encoding='utf-8')
