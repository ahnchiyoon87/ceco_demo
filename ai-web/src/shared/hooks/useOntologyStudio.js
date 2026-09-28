import { computed, nextTick, onMounted, onUnmounted, reactive, ref } from 'vue'

const API = import.meta.env.VITE_API_BASE || 'http://localhost:8000'
const DEFAULT_BUILD_PROMPT = '업로드된 문서를 바탕으로 Golden Question에 답할 수 있는 온톨로지를 구축해줘.'
const DEFAULT_REVIEW_PROMPT = '방금 검토 피드백을 반영해서 Golden Question에 더 잘 답할 수 있도록 온톨로지를 개선해줘.'

const NEO4J_TOOLS = [
  'neo4j_cypher',
  'neo4j_cypher_readonly',
  'schema_create_class',
  'schema_create_relationship_type',
  'schema_get',
  'entity_create',
  'entity_search',
  'relationship_create',
]

const MODES = {
  build: {
    key: 'build',
    label: '온톨로지 구축',
    description: '문서를 분석하고 스키마, 엔티티, 관계를 생성하는 작업 모드입니다.',
    inputPlaceholder: '추가 지시사항이 있으면 입력하세요. 비워두면 설정한 의도와 Golden Question 기준으로 바로 구축합니다.',
    allowsFiles: true,
    examples: [
      '업로드한 문서에서 엔티티를 추출해줘',
      '현재 스키마를 보여줘',
      '문서 내용을 바탕으로 관계 유형을 제안해줘',
    ],
  },
  answer: {
    key: 'answer',
    label: '질문 응답',
    description: '이미 구축된 온톨로지를 조회해 구체적인 질문에 답변하는 모드입니다.',
    inputPlaceholder: '구축된 온톨로지에 대한 질문을 입력하세요...',
    allowsFiles: false,
    examples: [
      '현재 그래프에 어떤 클래스와 관계가 정의되어 있어?',
      'Company 클래스 엔티티를 찾아줘',
      'Person과 Company 사이에 어떤 관계가 있는지 설명해줘',
    ],
  },
}

const MODE_KEYS = Object.keys(MODES)

function createBuildBrief() {
  return {
    intent: '',
    goldenQuestions: [''],
  }
}

function createModeState(targetMode) {
  return {
    draft: '',
    messages: [],
    todos: [],
    skills: [],
    refFiles: [],
    buildBrief: targetMode === 'build' ? createBuildBrief() : null,
  }
}

function normalizeGoldenQuestions(items = []) {
  return items.map((item) => item.trim()).filter(Boolean)
}

function createReviewItem(item) {
  return {
    question: item.question || '',
    answer: item.answer || '',
    status: item.status || 'answerable',
    confidence: item.confidence || 'medium',
    verdict: null,
    feedback: '',
  }
}

function createBuildReport(report) {
  return {
    intent: report.intent || '',
    summary: report.summary || '',
    nextAction: report.next_action || report.nextAction || '',
    goldenQuestions: Array.isArray(report.golden_questions)
      ? report.golden_questions.map(createReviewItem)
      : [],
  }
}

export function useOntologyStudio() {
  const mode = ref('build')
  const modeOptions = Object.values(MODES)
  const modeState = reactive({
    build: createModeState('build'),
    answer: createModeState('answer'),
  })
  const isStreaming = ref(false)
  const uploadedFiles = ref([])
  const outputFiles = ref([])
  const sessionId = ref('default')
  const sessions = ref([])
  const panelOpen = reactive({
    todos: true,
    context: true,
    files: true,
    schema: true,
  })
  const neo4jConnected = ref(false)
  const schema = ref({ classes: [], relationships: [] })
  const entityCounts = ref([])
  const graphData = ref({ nodes: [], edges: [] })
  const traversedNodeIds = ref([])
  const schemas = ref([])
  const selectedSchema = ref(null)
  const currentModeMeta = computed(() => MODES[mode.value])
  const inputText = computed({
    get: () => modeState[mode.value].draft,
    set: (value) => {
      modeState[mode.value].draft = value
    },
  })
  const messages = computed(() => modeState[mode.value].messages)
  const todos = computed(() => modeState[mode.value].todos)
  const skills = computed(() => modeState[mode.value].skills)
  const refFiles = computed(() => modeState[mode.value].refFiles)
  const examples = computed(() => currentModeMeta.value.examples)
  const showFilePanel = computed(() => currentModeMeta.value.allowsFiles)
  const buildSessions = computed(() => sessions.value.filter(s => s.mode !== 'answer'))
  const answerSessions = computed(() => sessions.value.filter(s => s.mode === 'answer'))
  const targetSchema = ref('')
  const newSchemaName = ref('')
  const buildBrief = computed(() => modeState.build.buildBrief)
  const buildIntent = computed({
    get: () => buildBrief.value.intent,
    set: (value) => {
      buildBrief.value.intent = value
    },
  })
  const buildGoldenQuestions = computed(() => buildBrief.value.goldenQuestions)
  const normalizedBuildGoldenQuestions = computed(() =>
    normalizeGoldenQuestions(buildBrief.value.goldenQuestions)
  )
  const isBuildBriefReady = computed(
    () =>
      Boolean(buildIntent.value.trim()) &&
      normalizedBuildGoldenQuestions.value.length > 0 &&
      uploadedFiles.value.length > 0
  )
  const canSend = computed(() => {
    if (isStreaming.value) {
      return false
    }
    if (mode.value === 'build') {
      return isBuildBriefReady.value
    }
    return Boolean(inputText.value.trim())
  })
  const effectiveInputPlaceholder = computed(() => {
    if (mode.value === 'build' && !isBuildBriefReady.value) {
      return '먼저 파일을 업로드하고, 구축 의도와 최소 1개의 Golden Question을 입력하세요...'
    }
    return currentModeMeta.value.inputPlaceholder
  })

  let neo4jInterval = null
  let activeEventSource = null

  function getModeState(targetMode = mode.value) {
    return modeState[targetMode]
  }

  function replaceItems(target, items) {
    target.splice(0, target.length, ...items)
  }

  function resetModeState(targetMode) {
    const state = getModeState(targetMode)
    state.draft = ''
    replaceItems(state.messages, [])
    replaceItems(state.todos, [])
    replaceItems(state.skills, [])
    replaceItems(state.refFiles, [])
    if (state.buildBrief) {
      state.buildBrief.intent = ''
      replaceItems(state.buildBrief.goldenQuestions, [''])
    }
  }

  function isNeo4jTool(name) {
    return NEO4J_TOOLS.includes(name)
  }

  function scrollBottom() {
    nextTick(() => {
      const chat = document.querySelector('.chat-messages')
      if (chat) {
        chat.scrollTop = chat.scrollHeight
      }
    })
  }

  function setMode(nextMode) {
    if (!MODES[nextMode] || isStreaming.value) {
      return
    }
    if (nextMode === mode.value) {
      // Same mode clicked again → start a fresh blank session locally
      // Persist current messages before clearing
      const currentState = getModeState(nextMode)
      if (currentState.messages.length > 0) {
        persistMessages(nextMode)
      }
      // Generate a local pending ID (will be created on first send)
      const pendingId = `pending_${Date.now()}`
      sessionId.value = pendingId
      for (const key of MODE_KEYS) {
        resetModeState(key)
      }
      uploadedFiles.value = []
      outputFiles.value = []
      traversedNodeIds.value = []
      return
    }
    mode.value = nextMode
    scrollBottom()
  }

  function setBuildGoldenQuestion(index, value) {
    if (buildBrief.value.goldenQuestions[index] === undefined) {
      return
    }
    buildBrief.value.goldenQuestions[index] = value
  }

  function addBuildGoldenQuestion() {
    buildBrief.value.goldenQuestions.push('')
  }

  function importBuildGoldenQuestions(questions) {
    const existing = buildBrief.value.goldenQuestions
    const hasOnlyEmptySlot = existing.length === 1 && !existing[0].trim()
    if (hasOnlyEmptySlot) {
      buildBrief.value.goldenQuestions = [...questions]
    } else {
      buildBrief.value.goldenQuestions.push(...questions)
    }
  }

  function removeBuildGoldenQuestion(index) {
    if (buildBrief.value.goldenQuestions.length === 1) {
      buildBrief.value.goldenQuestions[0] = ''
      return
    }
    buildBrief.value.goldenQuestions.splice(index, 1)
  }

  function createBuildContext(reviewFeedback = []) {
    const ctx = {
      intent: buildIntent.value.trim(),
      golden_questions: [...normalizedBuildGoldenQuestions.value],
      review_feedback: reviewFeedback,
    }
    // Include target schema info for the agent
    const schemaName = targetSchema.value || newSchemaName.value || ''
    if (schemaName) {
      ctx.target_schema = schemaName
    }
    return ctx
  }

  function replaceAssistantText(message, text) {
    const nextSteps = []
    let inserted = false
    for (const step of message.steps) {
      if (step.type === 'token') {
        if (!inserted && text.trim()) {
          nextSteps.push({ type: 'token', text })
          inserted = true
        }
        continue
      }
      nextSteps.push(step)
    }
    if (!inserted && text.trim()) {
      nextSteps.push({ type: 'token', text })
    }
    replaceItems(message.steps, nextSteps)
  }

  function updateAssistantPreprocessState(message, data = {}) {
    message.preprocessState = {
      ...(message.preprocessState || {}),
      ...data,
    }
  }

  function normalizeReportFeedback(message) {
    const report = message?.buildReport
    if (!report) {
      return []
    }

    return report.goldenQuestions
      .filter((item) => item.verdict)
      .map((item) => ({
        question: item.question,
        answer: item.answer,
        status: item.status,
        verdict: item.verdict,
        feedback: item.feedback.trim(),
      }))
  }

  function canSubmitBuildFeedback(message) {
    const reviewFeedback = normalizeReportFeedback(message)
    const incorrectItems = reviewFeedback.filter((item) => item.verdict === 'incorrect')
    return incorrectItems.length > 0 && incorrectItems.every((item) => item.feedback)
  }

  function persistMessages(targetMode = mode.value) {
    if (sessionId.value.startsWith('pending_')) return
    const state = getModeState(targetMode)
    // Deep clone to ensure nested objects (steps, args, buildReport) are serialized
    const serializable = JSON.parse(JSON.stringify(state.messages))
    fetch(
      `${API}/api/sessions/${encodeURIComponent(sessionId.value)}/messages?mode=${targetMode}`,
      {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(serializable),
      }
    ).catch(() => {})
  }

  async function loadSessionMessages(targetSessionId) {
    for (const m of MODE_KEYS) {
      try {
        const res = await fetch(
          `${API}/api/sessions/${encodeURIComponent(targetSessionId)}/messages?mode=${m}`
        )
        const data = await res.json()
        const state = getModeState(m)
        if (data.messages?.length) {
          replaceItems(state.messages, data.messages)
          // Restore buildBrief from the first user message that has one
          if (m === 'build' && state.buildBrief) {
            const briefMsg = data.messages.find((msg) => msg.buildBrief)
            if (briefMsg) {
              state.buildBrief.intent = briefMsg.buildBrief.intent || ''
              replaceItems(
                state.buildBrief.goldenQuestions,
                briefMsg.buildBrief.goldenQuestions?.length
                  ? briefMsg.buildBrief.goldenQuestions
                  : ['']
              )
            }
          }
          // Restore traversed node IDs from answer mode tool results
          if (m === 'answer') {
            traversedNodeIds.value = extractTraversedNodeIds(data.messages)
          }
        }
      } catch {
        // ignore
      }
    }
    scrollBottom()
  }

  function extractTraversedNodeIds(messages) {
    const ids = []
    for (const msg of messages) {
      if (msg.role !== 'assistant') continue
      for (const step of msg.steps || []) {
        if (step.type !== 'tool_result') continue
        try {
          const items = JSON.parse(step.content)
          const list = Array.isArray(items) ? items : [items]
          for (const item of list) {
            if (!item || typeof item !== 'object') continue
            // vector_search: node_id field
            if (item.node_id) ids.push(item.node_id)
            // entity_search / cypher: id field (element_id format "4:uuid:num")
            else if (item.id && typeof item.id === 'string' && item.id.includes(':')) ids.push(item.id)
            // nested node dicts in cypher results
            for (const val of Object.values(item)) {
              if (val && typeof val === 'object' && val.id && typeof val.id === 'string' && val.id.includes(':')) {
                ids.push(val.id)
              }
            }
          }
        } catch {
          // not JSON, skip
        }
      }
    }
    // dedupe preserving order
    return [...new Set(ids)]
  }

  function buildStreamUrl(prompt, currentMode, buildContext = null) {
    const url = new URL(`${API}/api/stream`)
    url.searchParams.set('prompt', prompt)
    url.searchParams.set('session_id', sessionId.value)
    url.searchParams.set('mode', currentMode)
    if (buildContext) {
      url.searchParams.set('build_context', JSON.stringify(buildContext))
    }
    return url.toString()
  }

  async function checkNeo4jStatus() {
    try {
      const res = await fetch(`${API}/api/neo4j/status`)
      const data = await res.json()
      neo4jConnected.value = data.status === 'connected'
    } catch {
      neo4jConnected.value = false
    }
  }

  async function refreshEntityCounts() {
    if (!schema.value.classes.length) {
      entityCounts.value = []
      return
    }

    try {
      const res = await fetch(`${API}/api/graph?limit=0`)
      const data = await res.json()
      const counts = {}
      for (const node of data.nodes || []) {
        for (const label of node.labels || []) {
          if (label !== '_Entity') {
            counts[label] = (counts[label] || 0) + 1
          }
        }
      }
      entityCounts.value = Object.entries(counts).map(([name, count]) => ({ name, count }))
    } catch {
      entityCounts.value = []
    }
  }

  async function fetchGraphData(className = '', limit = 200) {
    try {
      const params = new URLSearchParams()
      if (className) params.set('class_name', className)
      if (selectedSchema.value) params.set('schema_name', selectedSchema.value)
      params.set('limit', String(limit))
      const res = await fetch(`${API}/api/graph?${params}`)
      graphData.value = await res.json()
    } catch {
      graphData.value = { nodes: [], edges: [] }
    }
  }

  async function fetchSchemas() {
    try {
      const res = await fetch(`${API}/api/schemas`)
      const data = await res.json()
      schemas.value = data.schemas || []
    } catch {
      schemas.value = []
    }
  }

  async function selectSchema(schemaName) {
    selectedSchema.value = schemaName || null
    await fetchGraphData()
  }

  async function deleteSchemaEntities(schemaId) {
    try {
      await fetch(`${API}/api/schemas/${schemaId}/entities`, { method: 'DELETE' })
      await refreshSchema()
    } catch {
      // ignore
    }
  }

  async function rebuildSchema(schemaId) {
    try {
      await fetch(`${API}/api/schemas/${schemaId}/rebuild`, { method: 'POST' })
      await refreshSchema()
    } catch {
      // ignore
    }
  }

  async function refreshSchema() {
    try {
      const res = await fetch(`${API}/api/schema`)
      const data = await res.json()
      schema.value = {
        classes: data.classes || [],
        relationships: data.relationships || [],
      }
      await refreshEntityCounts()
      await fetchSchemas()
      await fetchGraphData()
    } catch {
      // ignore
    }
  }

  async function refreshFiles() {
    try {
      const res = await fetch(`${API}/api/files`)
      const data = await res.json()
      uploadedFiles.value = data.uploads || []
      outputFiles.value = data.output || []
    } catch {
      // ignore
    }
  }

  async function refreshAll() {
    await Promise.all([refreshFiles(), checkNeo4jStatus(), refreshSchema()])
  }

  async function uploadFiles(fileList) {
    if (!fileList?.length) {
      return []
    }

    const fd = new FormData()
    const names = []
    for (const file of fileList) {
      fd.append('files', file)
      names.push(file.name)
    }
    fd.append('session_id', sessionId.value)
    await fetch(`${API}/api/upload`, { method: 'POST', body: fd })
    await refreshFiles()
    return names
  }

  async function doUploadAndNotify(fileList) {
    if (!currentModeMeta.value.allowsFiles) {
      return
    }

    await ensureSessionOnServer()
    const names = await uploadFiles(fileList)
    const shouldNotifyInChat = mode.value !== 'build' || getModeState().messages.length > 0
    if (names.length && shouldNotifyInChat) {
      getModeState().messages.push({
        role: 'user',
        text: `파일 업로드: ${names.join(', ')}`,
        files: names,
      })
      scrollBottom()
    }
  }

  function downloadFile(name) {
    window.open(`${API}/api/download/${encodeURIComponent(name)}`, '_blank')
  }

  async function deleteUploadFile(name) {
    await fetch(`${API}/api/files/${encodeURIComponent(name)}`, { method: 'DELETE' })
    await refreshFiles()
  }

  async function saveClass({ name, original_name, description, properties, schema_name }) {
    await fetch(`${API}/api/schema/classes`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, original_name: original_name || '', description, properties, schema_name }),
    })
    await refreshSchema()
  }

  async function deleteClass(className) {
    await fetch(`${API}/api/schema/classes/${encodeURIComponent(className)}`, { method: 'DELETE' })
    await refreshSchema()
  }

  async function saveRelationship({ name, from_class, to_class, description, properties, schema_name }) {
    await fetch(`${API}/api/schema/relationships`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ name, from_class, to_class, description, properties, schema_name }),
    })
    await refreshSchema()
  }

  function selectTargetSchema(schemaName) {
    targetSchema.value = schemaName
    if (!schemaName) return
    // Load intent + golden questions from the selected schema
    const s = schemas.value.find(sc => sc.name === schemaName)
    if (s) {
      const brief = modeState.build.buildBrief
      if (s.intent) brief.intent = s.intent
      if (s.golden_questions?.length) {
        brief.goldenQuestions.splice(0, brief.goldenQuestions.length, ...s.golden_questions)
      }
    }
  }

  async function saveSchemaBrief(schemaName) {
    const s = schemas.value.find(sc => sc.name === schemaName)
    if (!s) return
    await fetch(`${API}/api/schemas/${encodeURIComponent(s.id)}/brief`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        intent: buildIntent.value.trim(),
        golden_questions: normalizedBuildGoldenQuestions.value,
      }),
    })
  }

  async function deleteRelationship(name, fromClass, toClass) {
    const params = new URLSearchParams({ from_class: fromClass, to_class: toClass })
    await fetch(`${API}/api/schema/relationships/${encodeURIComponent(name)}?${params}`, { method: 'DELETE' })
    await refreshSchema()
  }

  function autoUpdateSessionTitle(currentMode, prompt) {
    // Count total user messages across all modes
    const totalUserMsgs = MODE_KEYS.reduce(
      (sum, m) => sum + getModeState(m).messages.filter(msg => msg.role === 'user').length,
      0
    )
    // Only set title on the very first user message of the session
    if (totalUserMsgs === 1 && prompt) {
      const rawTitle = prompt.length > 30 ? prompt.slice(0, 30) + '...' : prompt
      const title = rawTitle
      const params = new URLSearchParams({ title })
      // Also update schema_name if build mode
      if (currentMode === 'build') {
        const schemaName = targetSchema.value || newSchemaName.value || ''
        if (schemaName) params.set('schema_name', schemaName)
      }
      fetch(
        `${API}/api/sessions/${encodeURIComponent(sessionId.value)}?${params}`,
        { method: 'PATCH' }
      ).then(() => fetchSessions()).catch(() => {})
    }
  }

  async function ensureSessionOnServer() {
    if (sessionId.value.startsWith('pending_')) {
      const currentMode = mode.value
      const schemaName = currentMode === 'build'
        ? (targetSchema.value || newSchemaName.value || '')
        : ''
      const params = new URLSearchParams({ title: '새 대화', mode: currentMode })
      if (schemaName) params.set('schema_name', schemaName)
      const res = await fetch(`${API}/api/sessions?${params}`, { method: 'POST' })
      const session = await res.json()
      sessionId.value = session.id
      await fetchSessions()
    }
  }

  function startStreamingRequest({ currentMode, prompt, userMessage, buildContext = null }) {
    const state = getModeState(currentMode)

    state.messages.push(userMessage)
    state.draft = ''
    traversedNodeIds.value = []
    scrollBottom()

    state.messages.push({ role: 'assistant', steps: [], files: [], mode: currentMode })
    isStreaming.value = true

    const getAiMsg = () => {
      const currentMessages = getModeState(currentMode).messages
      return currentMessages[currentMessages.length - 1]
    }

    let currentTokenIdx = -1
    const es = new EventSource(buildStreamUrl(prompt, currentMode, buildContext))
    activeEventSource = es

    es.addEventListener('token', (event) => {
      const data = JSON.parse(event.data)
      const aiMsg = getAiMsg()
      if (currentTokenIdx >= 0 && aiMsg.steps[currentTokenIdx]?.type === 'token') {
        aiMsg.steps[currentTokenIdx].text += data.text
      } else {
        currentTokenIdx = aiMsg.steps.length
        aiMsg.steps.push({ type: 'token', text: data.text })
      }
      scrollBottom()
    })

    es.addEventListener('tool_start', (event) => {
      const data = JSON.parse(event.data)
      currentTokenIdx = -1
      getAiMsg().steps.push({
        type: 'tool_start',
        name: data.name,
        args: data.args || {},
        description: data.description || '',
        done: false,
      })
      scrollBottom()
    })

    es.addEventListener('tool_result', (event) => {
      const data = JSON.parse(event.data)
      const aiMsg = getAiMsg()
      for (let index = aiMsg.steps.length - 1; index >= 0; index -= 1) {
        if (aiMsg.steps[index].type === 'tool_start' && !aiMsg.steps[index].done) {
          aiMsg.steps[index].done = true
          break
        }
      }
      aiMsg.steps.push({ type: 'tool_result', name: data.name, content: data.content })
      currentTokenIdx = -1
      scrollBottom()
    })

    es.addEventListener('neo4j_update', () => {
      refreshSchema()
    })

    es.addEventListener('schema_created', (event) => {
      const data = JSON.parse(event.data)
      const schemaName = data.schema_name
      if (schemaName) {
        selectedSchema.value = schemaName
        // Update session's schema_name on server
        if (!sessionId.value.startsWith('pending_')) {
          fetch(
            `${API}/api/sessions/${encodeURIComponent(sessionId.value)}?schema_name=${encodeURIComponent(schemaName)}`,
            { method: 'PATCH' }
          ).then(() => fetchSessions()).catch(() => {})
        }
      }
    })

    es.addEventListener('traversed_nodes', (event) => {
      const data = JSON.parse(event.data)
      const ids = data.node_ids || []
      if (ids.length) {
        traversedNodeIds.value = [...traversedNodeIds.value, ...ids]
      }
    })

    es.addEventListener('preprocess_progress', (event) => {
      const data = JSON.parse(event.data)
      const aiMsg = getAiMsg()
      updateAssistantPreprocessState(aiMsg, data)
      scrollBottom()
    })

    es.addEventListener('preprocess_complete', (event) => {
      const data = JSON.parse(event.data)
      const aiMsg = getAiMsg()
      aiMsg.preprocessSummary = data.summary || null
      updateAssistantPreprocessState(aiMsg, {
        completed: true,
        progress: 100,
      })
      scrollBottom()
    })

    es.addEventListener('todos', (event) => {
      const data = JSON.parse(event.data)
      replaceItems(getModeState(currentMode).todos, data.items || [])
    })

    es.addEventListener('skill_loaded', (event) => {
      const data = JSON.parse(event.data)
      const currentSkills = getModeState(currentMode).skills
      if (!currentSkills.includes(data.name)) {
        currentSkills.push(data.name)
      }
    })

    es.addEventListener('ref_file', (event) => {
      const data = JSON.parse(event.data)
      const currentRefFiles = getModeState(currentMode).refFiles
      if (!currentRefFiles.includes(data.name)) {
        currentRefFiles.push(data.name)
      }
    })

    es.addEventListener('status', (event) => {
      const data = JSON.parse(event.data)
      const aiMsg = getAiMsg()
      aiMsg.statusMessage = data.message || ''
      scrollBottom()
    })
    es.addEventListener('node_update', scrollBottom)

    es.addEventListener('done', (event) => {
      const data = JSON.parse(event.data)
      const aiMsg = getAiMsg()

      if (typeof data.text === 'string') {
        replaceAssistantText(aiMsg, data.text)
      }
      if (data.build_report) {
        aiMsg.buildReport = createBuildReport(data.build_report)
      }
      if (data.files?.length) {
        aiMsg.files = data.files
      }

      isStreaming.value = false
      activeEventSource = null
      es.close()
      persistMessages(currentMode)
      autoUpdateSessionTitle(currentMode, prompt)
      refreshAll()
      scrollBottom()
    })

    es.addEventListener('error_event', (event) => {
      const data = JSON.parse(event.data)
      getAiMsg().steps.push({ type: 'token', text: `\n오류: ${data.message}` })
      isStreaming.value = false
      activeEventSource = null
      es.close()
      scrollBottom()
    })

    es.onerror = () => {
      isStreaming.value = false
      activeEventSource = null
      es.close()
      scrollBottom()
    }
  }

  async function send(textOverride = null) {
    const currentMode = mode.value
    const state = getModeState(currentMode)
    const rawText = (textOverride ?? state.draft).trim()

    if (isStreaming.value) {
      return
    }

    // Lazily create session on server if pending
    await ensureSessionOnServer()

    // If there are already messages, this is a follow-up (e.g. "계속해")
    const hasExistingMessages = state.messages.length > 0
    const isFollowUp = currentMode === 'build' && hasExistingMessages

    if (currentMode === 'build' && !isFollowUp && !isBuildBriefReady.value) {
      return
    }

    const prompt = isFollowUp
      ? rawText
      : currentMode === 'build'
        ? rawText || DEFAULT_BUILD_PROMPT
        : rawText
    if (!prompt) {
      return
    }

    const userMessage = isFollowUp
      ? { role: 'user', text: prompt, mode: currentMode }
      : currentMode === 'build'
        ? {
            role: 'user',
            text: rawText || '구축 의도와 Golden Question을 기준으로 온톨로지 구축 시작',
            mode: currentMode,
            buildBrief: {
              intent: buildIntent.value.trim(),
              goldenQuestions: [...normalizedBuildGoldenQuestions.value],
            },
          }
        : {
            role: 'user',
            text: prompt,
            mode: currentMode,
          }

    // Save brief to schema when building (first message)
    if (currentMode === 'build' && !isFollowUp) {
      const schemaName = targetSchema.value || newSchemaName.value || ''
      if (schemaName) {
        saveSchemaBrief(schemaName).catch(() => {})
      }
    }

    startStreamingRequest({
      currentMode,
      prompt,
      userMessage,
      // Don't send build context for follow-up messages
      buildContext: currentMode === 'build' && !isFollowUp ? createBuildContext() : null,
    })
  }

  function stopStreaming() {
    if (!isStreaming.value || !activeEventSource) {
      return
    }
    activeEventSource.close()
    activeEventSource = null
    isStreaming.value = false

    // Mark any running tool as stopped
    const currentMessages = getModeState(mode.value).messages
    if (currentMessages.length > 0) {
      const lastMsg = currentMessages[currentMessages.length - 1]
      if (lastMsg.role === 'assistant') {
        lastMsg.steps.push({ type: 'token', text: '\n[중단됨] "계속해"를 입력하면 이어서 진행합니다.' })
      }
    }

    persistMessages(mode.value)
    scrollBottom()
  }

  async function submitBuildFeedback(message) {
    if (isStreaming.value || !canSubmitBuildFeedback(message)) {
      return
    }

    const reviewFeedback = normalizeReportFeedback(message)
    startStreamingRequest({
      currentMode: 'build',
      prompt: DEFAULT_REVIEW_PROMPT,
      userMessage: {
        role: 'user',
        text: 'Golden Question 검토 피드백 반영 요청',
        mode: 'build',
        buildFeedback: reviewFeedback,
      },
      buildContext: createBuildContext(reviewFeedback),
    })
  }

  async function resetSession() {
    await fetch(`${API}/api/session/reset?session_id=${encodeURIComponent(sessionId.value)}`, {
      method: 'POST',
    })
    uploadedFiles.value = []
    outputFiles.value = []
    traversedNodeIds.value = []
    for (const key of MODE_KEYS) {
      resetModeState(key)
    }
    await refreshSchema()
  }

  async function fetchSessions() {
    try {
      const res = await fetch(`${API}/api/sessions`)
      const data = await res.json()
      sessions.value = data.sessions || []
    } catch {
      sessions.value = []
    }
  }

  async function createNewSession(title = '') {
    try {
      const currentMode = mode.value
      const params = new URLSearchParams({ title: title || '새 대화', mode: currentMode })
      const res = await fetch(`${API}/api/sessions?${params}`, {
        method: 'POST',
      })
      const session = await res.json()
      sessionId.value = session.id
      for (const key of MODE_KEYS) {
        resetModeState(key)
      }
      uploadedFiles.value = []
      traversedNodeIds.value = []
      outputFiles.value = []
      await fetchSessions()
      await refreshAll()
      return session
    } catch {
      return null
    }
  }

  async function switchSession(targetSessionId) {
    if (targetSessionId === sessionId.value || isStreaming.value) {
      return
    }
    // Save current session messages before switching (skip pending sessions)
    if (!sessionId.value.startsWith('pending_')) {
      for (const m of MODE_KEYS) {
        if (getModeState(m).messages.length > 0) {
          persistMessages(m)
        }
      }
    }
    sessionId.value = targetSessionId
    for (const key of MODE_KEYS) {
      resetModeState(key)
    }
    uploadedFiles.value = []
    outputFiles.value = []
    traversedNodeIds.value = []
    // Switch mode to match the session's mode
    const session = sessions.value.find(s => s.id === targetSessionId)
    if (session?.mode && MODES[session.mode]) {
      mode.value = session.mode
    }
    // Auto-select associated schema for build sessions
    if (session?.schema_name) {
      selectedSchema.value = session.schema_name
    } else {
      selectedSchema.value = null
    }
    await loadSessionMessages(targetSessionId)
    await refreshAll()
  }

  async function deleteSession(targetSessionId) {
    try {
      await fetch(`${API}/api/sessions/${encodeURIComponent(targetSessionId)}`, {
        method: 'DELETE',
      })
      if (targetSessionId === sessionId.value) {
        sessionId.value = 'default'
        for (const key of MODE_KEYS) {
          resetModeState(key)
        }
        uploadedFiles.value = []
        outputFiles.value = []
        await refreshAll()
      }
      await fetchSessions()
    } catch {
      // ignore
    }
  }

  async function clearNeo4jAll() {
    const res = await fetch(`${API}/api/neo4j/clear-all`, { method: 'POST' })
    const data = await res.json()
    if (data.status === 'ok') {
      await refreshSchema()
    }
    return data
  }

  async function clearSandbox() {
    const res = await fetch(`${API}/api/sandbox/clear`, { method: 'POST' })
    const data = await res.json()
    if (data.status === 'ok') {
      await refreshFiles()
    }
    return data
  }

  onMounted(async () => {
    await fetchSessions()
    await loadSessionMessages(sessionId.value)
    await refreshAll()
    neo4jInterval = setInterval(checkNeo4jStatus, 30000)
  })

  onUnmounted(() => {
    if (neo4jInterval) {
      clearInterval(neo4jInterval)
    }
  })

  return {
    apiBase: API,
    addBuildGoldenQuestion,
    importBuildGoldenQuestions,
    buildGoldenQuestions,
    buildIntent,
    buildSessions,
    answerSessions,
    canSend,
    canSubmitBuildFeedback,
    clearNeo4jAll,
    clearSandbox,
    createNewSession,
    currentModeMeta,
    deleteSession,
    deleteClass,
    deleteRelationship,
    deleteUploadFile,
    doUploadAndNotify,
    downloadFile,
    effectiveInputPlaceholder,
    entityCounts,
    examples,
    fetchGraphData,
    fetchSessions,
    graphData,
    inputText,
    isBuildBriefReady,
    isNeo4jTool,
    isStreaming,
    messages,
    mode,
    modeOptions,
    neo4jConnected,
    outputFiles,
    panelOpen,
    refFiles,
    refreshAll,
    removeBuildGoldenQuestion,
    resetSession,
    saveClass,
    saveRelationship,
    saveSchemaBrief,
    selectTargetSchema,
    schema,
    schemas,
    selectedSchema,
    selectSchema,
    deleteSchemaEntities,
    rebuildSchema,
    send,
    sessionId,
    sessions,
    setBuildGoldenQuestion,
    setMode,
    showFilePanel,
    skills,
    stopStreaming,
    submitBuildFeedback,
    switchSession,
    targetSchema,
    newSchemaName,
    todos,
    traversedNodeIds,
    uploadedFiles,
  }
}
