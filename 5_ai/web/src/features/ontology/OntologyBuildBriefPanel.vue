<template>
  <section class="build-brief-main">
    <div class="build-brief-content">
      <div class="build-brief-center">
        <div class="build-brief-welcome">
          <h1 class="build-brief-title">Ontology Studio</h1>
          <div class="welcome-mode">온톨로지 구축</div>
          <p class="build-brief-desc">
            구축 의도와 반드시 답해야 하는 Golden Question을 정의한 뒤, OCR -> 임베딩 -> 그래프 적재 -> 온톨로지 구축 순서로 시작하세요.
          </p>
        </div>

        <div class="build-brief-form">
          <div class="build-brief-field">
            <span>파일</span>
            <div
              class="build-upload-zone"
              :class="{ 'drag-active': dragOver }"
              @dragover.prevent="dragOver = true"
              @dragleave="dragOver = false"
              @drop.prevent="handleDrop"
              @click="docFileInput?.click()"
            >
              <input ref="docFileInput" type="file" hidden multiple @change="handleDocSelect" />
              <div v-if="!uploadedFiles.length" class="build-upload-placeholder">
                + 파일 업로드 (드래그 앤 드롭 가능)
              </div>
              <div v-else class="build-upload-file-list">
                <span v-for="f in uploadedFiles" :key="f.name" class="build-upload-chip">
                  {{ f.name }} <span class="build-upload-size">{{ f.size }}</span>
                </span>
                <span class="build-upload-add">+ 추가</span>
              </div>
            </div>
          </div>

          <div v-if="schemas.length" class="build-brief-field">
            <span>대상 스키마</span>
            <select
              :value="targetSchema"
              class="build-brief-select"
              :disabled="isStreaming"
              @change="$emit('update:targetSchema', $event.target.value)"
            >
              <option value="">새 스키마 생성</option>
              <option v-for="s in schemas" :key="s.id" :value="s.name">{{ s.name }} (추가 인제스천)</option>
            </select>
            <input
              v-if="!targetSchema"
              :value="newSchemaName"
              class="build-brief-input"
              :disabled="isStreaming"
              placeholder="새 스키마 이름 (예: 보험약관 스키마)"
              @input="$emit('update:newSchemaName', $event.target.value)"
            />
          </div>

          <label class="build-brief-field">
            <span>구축 의도</span>
            <textarea
              :value="intent"
              :disabled="isStreaming"
              rows="3"
              placeholder="예: 내부 감사 담당자가 문서의 핵심 개체와 관계를 빠르게 추적할 수 있도록 온톨로지를 만들고 싶습니다."
              @input="$emit('update:intent', $event.target.value)"
            />
          </label>

          <div class="build-brief-field">
            <div class="build-brief-field-header">
              <span>Golden Question</span>
              <div class="build-brief-field-actions">
                <button class="btn-inline-add" :disabled="isStreaming" @click="triggerFileUpload">
                  파일에서 불러오기
                </button>
                <button class="btn-inline-add" :disabled="isStreaming" @click="$emit('add-question')">
                  질문 추가
                </button>
              </div>
              <input
                ref="fileInputRef"
                type="file"
                accept=".txt,.csv,.tsv"
                hidden
                @change="onFileSelected"
              />
            </div>

            <div class="golden-question-list">
              <div
                v-for="(question, index) in goldenQuestions"
                :key="`golden-question-${index}`"
                class="golden-question-item"
              >
                <input
                  :value="question"
                  :disabled="isStreaming"
                  type="text"
                  :placeholder="`예: Golden Question ${index + 1}`"
                  @input="$emit('update:question', index, $event.target.value)"
                />
                <button
                  class="btn-inline-remove"
                  :disabled="isStreaming"
                  @click="$emit('remove-question', index)"
                >
                  삭제
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>

    <div class="build-brief-action-bar">
      <div class="build-brief-action-inner">
        <p v-if="!canStart" class="build-brief-hint">
          파일 1개 이상 업로드, 의도 1개, Golden Question 최소 1개를 입력하면 구축을 시작할 수 있습니다.
        </p>
        <button
          class="btn-build-start"
          :disabled="!canStart || isStreaming"
          @click="$emit('start-build')"
        >
          이 브리프로 구축 시작
        </button>
      </div>
    </div>
  </section>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  intent: {
    type: String,
    required: true,
  },
  goldenQuestions: {
    type: Array,
    required: true,
  },
  canStart: {
    type: Boolean,
    required: true,
  },
  isStreaming: {
    type: Boolean,
    required: true,
  },
  uploadedFiles: {
    type: Array,
    default: () => [],
  },
  schemas: {
    type: Array,
    default: () => [],
  },
  targetSchema: {
    type: String,
    default: '',
  },
  newSchemaName: {
    type: String,
    default: '',
  },
})

const emit = defineEmits([
  'add-question',
  'import-questions',
  'remove-question',
  'start-build',
  'update:intent',
  'update:question',
  'update:targetSchema',
  'update:newSchemaName',
  'upload',
])

const fileInputRef = ref(null)
const docFileInput = ref(null)
const dragOver = ref(false)

function handleDocSelect(event) {
  const files = event.target.files
  if (files?.length) {
    // Copy files before clearing input — FileList is a live reference
    const copied = Array.from(files)
    event.target.value = ''
    emit('upload', copied)
  } else {
    event.target.value = ''
  }
}

function handleDrop(event) {
  dragOver.value = false
  if (event.dataTransfer.files?.length) {
    emit('upload', event.dataTransfer.files)
  }
}

function triggerFileUpload() {
  fileInputRef.value?.click()
}

function onFileSelected(event) {
  const file = event.target.files?.[0]
  if (!file) return

  const reader = new FileReader()
  reader.onload = (e) => {
    const lines = e.target.result
      .split(/\r?\n/)
      .map((line) => line.trim())
      .filter(Boolean)
    if (lines.length > 0) {
      emit('import-questions', lines)
    }
  }
  reader.readAsText(file)
  event.target.value = ''
}
</script>
