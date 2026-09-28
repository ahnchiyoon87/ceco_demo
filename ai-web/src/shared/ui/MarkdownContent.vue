<template>
  <div class="markdown-body" v-html="rendered"></div>
</template>

<script setup>
import { computed } from 'vue'
import { marked } from 'marked'

marked.use({ breaks: true, gfm: true })

const props = defineProps({
  content: {
    type: String,
    default: '',
  },
})

const rendered = computed(() => {
  if (!props.content) {
    return ''
  }
  return marked.parse(props.content)
})
</script>
