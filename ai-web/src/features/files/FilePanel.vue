<template>
  <div v-if="uploadedFiles.length || outputFiles.length" class="file-panel-section">
    <div class="file-panel-label" @click="open = !open">
      <span class="file-panel-toggle">{{ open ? '▾' : '▸' }}</span>
      파일 ({{ uploadedFiles.length + outputFiles.length }})
    </div>
    <div v-if="open" class="file-panel-list">
      <div v-for="file in uploadedFiles" :key="'u-' + file.name" class="file-panel-item">
        <span class="fi-icon fi-upload">U</span>
        <span class="file-name" :title="file.name">{{ file.name }}</span>
        <span class="file-size">{{ file.size }}</span>
        <button class="file-delete-btn" title="삭제" @click="$emit('delete-file', file.name)">&times;</button>
      </div>
      <div
        v-for="file in outputFiles"
        :key="'o-' + file.name"
        class="file-panel-item file-dl"
        @click="$emit('download', file.name)"
      >
        <span class="fi-icon fi-output">D</span>
        <span class="file-name" :title="file.name">{{ file.name }}</span>
        <span class="file-size">{{ file.size }}</span>
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref } from 'vue'

defineProps({
  outputFiles: {
    type: Array,
    required: true,
  },
  uploadedFiles: {
    type: Array,
    required: true,
  },
})

defineEmits(['delete-file', 'download'])

const open = ref(true)
</script>
