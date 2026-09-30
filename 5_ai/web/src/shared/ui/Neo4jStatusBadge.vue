<template>
  <div
    class="neo4j-status"
    :class="connected ? 'connected' : 'disconnected'"
    :title="connected ? 'Neo4j 연결됨' : 'Neo4j 연결 안됨'"
  >
    <span class="status-dot"></span>
    <span>Neo4j</span>
  </div>
</template>

<script setup>
defineProps({
  connected: {
    type: Boolean,
    required: true,
  },
})
</script>
