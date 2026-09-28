<template>
  <div class="panel" v-if="visible">
    <div class="panel-header" @click="$emit('toggle')">
      <h3>{{ title }}</h3>
      <span class="chevron" :class="{ open }">&#9662;</span>
    </div>
    <div v-show="open" class="panel-body">
      <slot />
    </div>
  </div>
</template>

<script setup>
defineProps({
  open: {
    type: Boolean,
    required: true,
  },
  title: {
    type: String,
    required: true,
  },
  visible: {
    type: Boolean,
    default: true,
  },
})

defineEmits(['toggle'])
</script>
