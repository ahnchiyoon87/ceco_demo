<template>
  <main class="chat-main">
    <div class="chat-messages">
      <div v-if="messages.length === 0" class="welcome">
        <h1>Ontology Studio</h1>
        <div class="welcome-mode">{{ modeLabel }}</div>
        <p>{{ modeDescription }}</p>
        <div class="examples">
          <button
            v-for="example in examples"
            :key="example"
            class="example-btn"
            @click="$emit('send-example', example)"
          >
            {{ example }}
          </button>
        </div>
      </div>

      <template v-for="(msg, index) in messages" :key="index">
        <div v-if="msg.role === 'user'" class="msg msg-user">
          <div class="msg-bubble">
            <div class="msg-text">{{ msg.text }}</div>
            <div v-if="msg.buildBrief" class="msg-brief">
              <div class="msg-brief-intent">
                <strong>의도</strong>
                <span>{{ msg.buildBrief.intent }}</span>
              </div>
              <div class="msg-brief-questions">
                <strong>Golden Question</strong>
                <ul>
                  <li v-for="question in msg.buildBrief.goldenQuestions" :key="question">
                    {{ question }}
                  </li>
                </ul>
              </div>
            </div>
            <div v-if="msg.buildFeedback?.length" class="msg-brief">
              <div class="msg-brief-questions">
                <strong>개선 피드백</strong>
                <ul>
                  <li v-for="item in msg.buildFeedback" :key="item.question">
                    {{ item.question }}: {{ item.feedback || (item.verdict === 'correct' ? '정답 처리' : '수정 필요') }}
                  </li>
                </ul>
              </div>
            </div>
            <div v-if="msg.files && msg.files.length" class="msg-files">
              <span v-for="file in msg.files" :key="file" class="msg-file-chip">{{ file }}</span>
            </div>
          </div>
        </div>

        <div v-else-if="msg.role === 'assistant'" class="msg msg-assistant">
          <div class="msg-avatar">AI</div>
          <div class="msg-body">
            <div v-if="getToolGroups(msg).length" class="tool-activity">
              <div
                class="tool-activity-summary"
                @click="toggleToolPanel(index)"
              >
                <span
                  class="tool-activity-dot"
                  :class="hasRunningTools(msg) ? 'running' : 'done'"
                ></span>
                <span class="tool-activity-label">{{ getToolSummaryLabel(msg) }}</span>
                <span
                  class="tool-activity-chevron"
                  :class="{ open: isToolPanelOpen(index) }"
                >&#9656;</span>
              </div>
              <div v-show="isToolPanelOpen(index)" class="tool-activity-list">
                <div
                  v-for="(tool, ti) in getToolGroups(msg)"
                  :key="ti"
                  class="tool-activity-item"
                >
                  <div
                    class="tool-activity-header"
                    :class="{ 'tool-neo4j': isNeo4jTool(tool.name) }"
                  >
                    <span
                      class="tool-badge"
                      :class="{ 'badge-neo4j': isNeo4jTool(tool.name) }"
                    >
                      {{ isNeo4jTool(tool.name) ? 'NEO4J' : 'TOOL' }}
                    </span>
                    <code>{{ tool.name }}</code>
                    <span v-if="!tool.done" class="tool-running">실행 중...</span>
                    <span v-else class="tool-done-icon">&#10003;</span>
                  </div>
                  <div v-if="tool.description" class="tool-description">
                    {{ tool.description }}
                  </div>
                  <details v-if="hasToolArgs(tool)" class="tool-args-detail">
                    <summary>입력 보기</summary>
                    <pre v-if="tool.name === 'execute' && tool.args?.command" class="tool-code">{{ tool.args.command }}</pre>
                    <pre v-else>{{ JSON.stringify(tool.args, null, 2) }}</pre>
                  </details>
                  <details v-if="tool.result" class="tool-result-detail">
                    <summary>결과 보기</summary>
                    <pre>{{ tool.result }}</pre>
                  </details>
                </div>
              </div>
            </div>

            <div v-if="showPreprocessCard(msg)" class="preprocess-card">
              <div class="preprocess-title">문서 전처리</div>
              <div v-if="msg.preprocessState?.message || msg.statusMessage" class="preprocess-message">
                {{ msg.preprocessState?.message || msg.statusMessage }}
              </div>
              <div v-if="getPreprocessMeta(msg)" class="preprocess-meta">
                {{ getPreprocessMeta(msg) }}
              </div>
              <div
                v-if="msg.preprocessSummary?.documents?.length"
                class="preprocess-summary"
              >
                <div
                  v-for="doc in msg.preprocessSummary.documents"
                  :key="doc.documentId"
                  class="preprocess-summary-item"
                >
                  {{ doc.documentName }} · {{ doc.chunkCount }}개 청크 · OCR 캐시 {{ doc.ocrCachedPages?.length || 0 }}페이지
                </div>
              </div>
            </div>

            <MarkdownContent
              v-if="getTextContent(msg)"
              :content="getTextContent(msg)"
            />

            <div v-if="msg.files && msg.files.length" class="msg-output-files">
              <button
                v-for="file in msg.files"
                :key="file"
                class="btn-file-dl"
                @click="$emit('download', file)"
              >
                {{ file }}
              </button>
            </div>

            <GoldenQuestionReviewPanel
              v-if="msg.buildReport"
              :can-submit="canSubmitBuildFeedback(msg)"
              :is-streaming="isStreaming"
              :report="msg.buildReport"
              @set-verdict="(reviewIndex, verdict) => setBuildVerdict(msg, reviewIndex, verdict)"
              @submit-feedback="$emit('submit-build-feedback', msg)"
              @update-feedback="(reviewIndex, value) => updateBuildFeedback(msg, reviewIndex, value)"
            />
          </div>
        </div>
      </template>

      <div v-if="isStreaming" class="msg msg-assistant">
        <div class="msg-avatar">AI</div>
        <div class="msg-body"><span class="typing"><span /><span /><span /></span></div>
      </div>
    </div>

    <div
      class="chat-input-bar"
      :class="{ 'drag-active': inputDragOver }"
      @dragover.prevent="inputDragOver = true"
      @dragleave="inputDragOver = false"
      @drop.prevent="onInputDrop"
    >
      <div v-if="pendingFiles.length" class="input-pending-files">
        <span v-for="(f, i) in pendingFiles" :key="i" class="input-file-chip">
          {{ f.name }}
          <button class="input-file-remove" @click="pendingFiles.splice(i, 1)">&times;</button>
        </span>
      </div>
      <div class="input-wrapper">
        <button
          class="btn-attach"
          title="파일 첨부"
          :disabled="isStreaming"
          @click="$refs.chatFileInput.click()"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M21.44 11.05l-9.19 9.19a6 6 0 01-8.49-8.49l9.19-9.19a4 4 0 015.66 5.66l-9.2 9.19a2 2 0 01-2.83-2.83l8.49-8.48"/>
          </svg>
        </button>
        <input
          ref="chatFileInput"
          type="file"
          multiple
          hidden
          @change="onFileSelect"
        />
        <textarea
          v-model="inputText"
          rows="1"
          :placeholder="inputPlaceholder"
          :disabled="isStreaming"
          @keydown.enter.exact="onEnter"
          @paste="onPaste"
        />
        <button
          v-if="isStreaming"
          class="btn-stop"
          title="중단"
          @click="$emit('stop')"
        >
          &#9724;
        </button>
        <button
          v-else
          class="btn-send"
          :disabled="!canSend && !pendingFiles.length"
          @click="onSendWithFiles"
        >
          &#10148;
        </button>
      </div>
    </div>
  </main>
</template>

<script setup>
import { reactive, ref } from 'vue'
import GoldenQuestionReviewPanel from '../ontology/GoldenQuestionReviewPanel.vue'
import MarkdownContent from '../../shared/ui/MarkdownContent.vue'

const inputText = defineModel('inputText', {
  type: String,
  default: '',
})

const toolPanelOverrides = reactive(new Map())
const pendingFiles = ref([])
const inputDragOver = ref(false)
const chatFileInput = ref(null)

const props = defineProps({
  examples: {
    type: Array,
    required: true,
  },
  canSend: {
    type: Boolean,
    required: true,
  },
  canSubmitBuildFeedback: {
    type: Function,
    required: true,
  },
  inputPlaceholder: {
    type: String,
    required: true,
  },
  isNeo4jTool: {
    type: Function,
    required: true,
  },
  isStreaming: {
    type: Boolean,
    required: true,
  },
  messages: {
    type: Array,
    required: true,
  },
  modeDescription: {
    type: String,
    required: true,
  },
  modeLabel: {
    type: String,
    required: true,
  },
})

const emit = defineEmits(['download', 'send', 'send-example', 'stop', 'submit-build-feedback', 'upload'])

function setBuildVerdict(message, index, verdict) {
  const item = message?.buildReport?.goldenQuestions?.[index]
  if (!item) {
    return
  }
  item.verdict = item.verdict === verdict ? null : verdict
  if (item.verdict !== 'incorrect') {
    item.feedback = ''
  }
}

function updateBuildFeedback(message, index, value) {
  const item = message?.buildReport?.goldenQuestions?.[index]
  if (!item) {
    return
  }
  item.feedback = value
}

function getToolGroups(msg) {
  const groups = []
  for (const step of msg.steps) {
    if (step.type === 'tool_start') {
      groups.push({ name: step.name, args: step.args || null, description: step.description || '', done: step.done, result: null })
    } else if (step.type === 'tool_result') {
      for (let i = groups.length - 1; i >= 0; i--) {
        if (groups[i].name === step.name && !groups[i].result) {
          groups[i].result = step.content
          break
        }
      }
    }
  }
  return groups
}

function hasToolArgs(tool) {
  return tool.args && Object.keys(tool.args).length > 0
}

function formatToolArgsSummary(tool) {
  if (!tool.args || Object.keys(tool.args).length === 0) return ''
  if (tool.name === 'execute') {
    const cmd = tool.args.command || ''
    const firstLine = cmd.split('\n')[0].substring(0, 60)
    return firstLine + (cmd.length > 60 ? '...' : '')
  }
  if (tool.name === 'sandbox_ls') return tool.args.path || ''
  if (tool.name === 'sandbox_read') return tool.args.file_path || ''
  if (tool.name === 'batch_ingest') return tool.args.nodes_json?.substring(0, 50) || ''
  if (tool.name === 'schema_create_class') return tool.args.name || ''
  if (tool.name === 'schema_create_relationship_type') return tool.args.name || ''
  if (tool.name === 'entity_search') return `${tool.args.class_name || ''}`
  if (tool.name === 'neo4j_cypher' || tool.name === 'neo4j_cypher_readonly') {
    return (tool.args.query || '').substring(0, 60)
  }
  return ''
}

function getTextContent(msg) {
  return msg.steps
    .filter((s) => s.type === 'token')
    .map((s) => s.text)
    .join('')
}

function getPreprocessMeta(msg) {
  const state = msg.preprocessState
  if (!state) {
    return ''
  }

  const parts = []
  if (state.documentName) {
    parts.push(state.documentName)
  }
  if (state.pageCurrent && state.pageTotal) {
    parts.push(`${state.pageCurrent}/${state.pageTotal}페이지`)
  }
  if (typeof state.progress === 'number') {
    parts.push(`${state.progress}%`)
  }
  if (state.cacheHit) {
    parts.push('OCR 캐시 사용')
  }
  return parts.join(' · ')
}

function showPreprocessCard(msg) {
  return Boolean(
    msg.preprocessState ||
    msg.preprocessSummary ||
    (msg.mode === 'build' && msg.statusMessage && !getTextContent(msg))
  )
}

function hasRunningTools(msg) {
  return msg.steps.some((s) => s.type === 'tool_start' && !s.done)
}

function isLastAssistantMessage(msgIndex) {
  for (let i = props.messages.length - 1; i >= 0; i--) {
    if (props.messages[i].role === 'assistant') {
      return i === msgIndex
    }
  }
  return false
}

function isToolPanelOpen(msgIndex) {
  if (toolPanelOverrides.has(msgIndex)) {
    return toolPanelOverrides.get(msgIndex)
  }
  return props.isStreaming && isLastAssistantMessage(msgIndex)
}

function toggleToolPanel(msgIndex) {
  toolPanelOverrides.set(msgIndex, !isToolPanelOpen(msgIndex))
}

function getToolSummaryLabel(msg) {
  const groups = getToolGroups(msg)
  const running = groups.filter((g) => !g.done)
  if (running.length) {
    return `${running[running.length - 1].name} 실행 중...`
  }
  return `${groups.length}개 도구 사용됨`
}

function onEnter(event) {
  if (!event.shiftKey) {
    event.preventDefault()
    onSendWithFiles()
  }
}

function onFileSelect(event) {
  const files = event.target.files
  if (files?.length) {
    for (const f of files) pendingFiles.value.push(f)
  }
  event.target.value = ''
}

function onInputDrop(event) {
  inputDragOver.value = false
  const files = event.dataTransfer?.files
  if (files?.length) {
    for (const f of files) pendingFiles.value.push(f)
  }
}

function onPaste(event) {
  const items = event.clipboardData?.items
  if (!items) return
  for (const item of items) {
    if (item.kind === 'file') {
      const file = item.getAsFile()
      if (file) pendingFiles.value.push(file)
    }
  }
}

async function onSendWithFiles() {
  // Upload pending files first
  if (pendingFiles.value.length) {
    emit('upload', Array.from(pendingFiles.value))
    pendingFiles.value = []
  }
  if (props.canSend || inputText.value.trim()) {
    emit('send')
  }
}
</script>

<style scoped>
.preprocess-card {
  margin-bottom: 12px;
  padding: 12px 14px;
  border: 1px solid rgba(120, 120, 120, 0.18);
  border-radius: 12px;
  background: rgba(120, 120, 120, 0.06);
}

.preprocess-title {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.02em;
  text-transform: uppercase;
  opacity: 0.72;
}

.preprocess-message {
  margin-top: 6px;
  font-weight: 600;
}

.preprocess-meta {
  margin-top: 4px;
  font-size: 13px;
  opacity: 0.8;
}

.preprocess-summary {
  margin-top: 8px;
  display: grid;
  gap: 4px;
}

.preprocess-summary-item {
  font-size: 13px;
  opacity: 0.88;
}

/* --- Chat input file attachment --- */
.chat-input-bar.drag-active {
  outline: 2px dashed #018bff;
  outline-offset: -2px;
  background: rgba(1, 139, 255, 0.05);
}
.input-pending-files {
  display: flex;
  flex-wrap: wrap;
  gap: 4px;
  padding: 6px 12px 0;
}
.input-file-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  background: rgba(1, 139, 255, 0.15);
  color: var(--accent);
  font-size: 11px;
  padding: 2px 8px;
  border-radius: 4px;
}
.input-file-remove {
  background: none;
  border: none;
  color: var(--accent);
  cursor: pointer;
  font-size: 13px;
  padding: 0 2px;
  line-height: 1;
}
.input-file-remove:hover {
  color: #f85149;
}
.btn-attach {
  background: none;
  border: none;
  color: var(--text-muted);
  cursor: pointer;
  padding: 4px;
  border-radius: 4px;
  display: flex;
  align-items: center;
  flex-shrink: 0;
}
.btn-attach:hover:not(:disabled) {
  color: var(--text);
  background: rgba(255, 255, 255, 0.06);
}
.btn-attach:disabled {
  opacity: 0.3;
  cursor: default;
}
</style>
