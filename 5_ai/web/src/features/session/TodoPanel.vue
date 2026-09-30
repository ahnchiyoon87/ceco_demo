<template>
  <CollapsiblePanel
    title="진행 상황"
    :open="open"
    :visible="todos.length > 0"
    @toggle="$emit('toggle')"
  >
    <div
      v-for="(todo, index) in todos"
      :key="index"
      :class="['todo-item', { done: todo.status === 'completed', active: todo.status === 'in_progress' }]"
    >
      <span class="todo-check">
        <span v-if="todo.status === 'completed'" class="check-done">&#10003;</span>
        <span v-else-if="todo.status === 'in_progress'" class="check-active"></span>
        <span v-else class="check-pending"></span>
      </span>
      <span class="todo-text">{{ todo.content || todo.title || todo }}</span>
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
  todos: {
    type: Array,
    required: true,
  },
})

defineEmits(['toggle'])
</script>
