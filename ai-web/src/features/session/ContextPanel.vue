<template>
  <CollapsiblePanel
    title="컨텍스트"
    :open="open"
    :visible="skills.length > 0 || refFiles.length > 0"
    @toggle="$emit('toggle')"
  >
    <div v-if="skills.length" class="ctx-section">
      <div class="ctx-label">스킬</div>
      <div v-for="skill in skills" :key="skill" class="ctx-item ctx-skill">
        <span class="ctx-icon">S</span>
        <span>{{ skill }}</span>
      </div>
    </div>
    <div v-if="refFiles.length" class="ctx-section">
      <div class="ctx-label">참조 파일</div>
      <div v-for="file in refFiles" :key="file" class="ctx-item ctx-ref">
        <span class="ctx-icon">F</span>
        <span>{{ file }}</span>
      </div>
    </div>
  </CollapsiblePanel>
</template>

<script setup>
import CollapsiblePanel from '../../shared/ui/CollapsiblePanel.vue'

defineProps({
  open: {
    type: Boolean,
    required: true,
  },
  refFiles: {
    type: Array,
    required: true,
  },
  skills: {
    type: Array,
    required: true,
  },
})

defineEmits(['toggle'])
</script>
