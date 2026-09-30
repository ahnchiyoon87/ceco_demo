<template>
  <section class="golden-review-card">
    <div class="golden-review-header">
      <div>
        <h4>Golden Question 검수</h4>
        <p v-if="report.summary">{{ report.summary }}</p>
        <p v-else>이 구축 결과가 각 Golden Question에 답할 수 있는지 확인해 주세요.</p>
      </div>
      <span class="golden-review-chip">{{ report.goldenQuestions.length }}개 질문</span>
    </div>

    <div class="golden-review-list">
      <article
        v-for="(item, index) in report.goldenQuestions"
        :key="`${item.question}-${index}`"
        class="golden-review-item"
      >
        <div class="golden-review-question">{{ item.question }}</div>
        <div class="golden-review-answer">{{ item.answer || '에이전트가 답변 초안을 제공하지 못했습니다.' }}</div>
        <div class="golden-review-meta">
          <span class="golden-review-status">{{ formatStatus(item.status) }}</span>
          <span class="golden-review-confidence">{{ formatConfidence(item.confidence) }}</span>
        </div>
        <div class="golden-review-actions">
          <button
            class="btn-review-action"
            :class="{ active: item.verdict === 'correct' }"
            :disabled="isStreaming"
            @click="$emit('set-verdict', index, 'correct')"
          >
            맞다
          </button>
          <button
            class="btn-review-action danger"
            :class="{ active: item.verdict === 'incorrect' }"
            :disabled="isStreaming"
            @click="$emit('set-verdict', index, 'incorrect')"
          >
            틀리다
          </button>
        </div>
        <textarea
          v-if="item.verdict === 'incorrect'"
          :value="item.feedback"
          :disabled="isStreaming"
          rows="3"
          placeholder="무엇이 부족하거나 잘못되었는지 적어 주세요. 이 내용이 다음 개선 루프에 전달됩니다."
          @input="$emit('update-feedback', index, $event.target.value)"
        />
      </article>
    </div>

    <div class="golden-review-footer">
      <p v-if="report.nextAction" class="golden-review-next">{{ report.nextAction }}</p>
      <button class="btn-build-start" :disabled="!canSubmit || isStreaming" @click="$emit('submit-feedback')">
        피드백 반영 요청
      </button>
    </div>
  </section>
</template>

<script setup>
defineProps({
  canSubmit: {
    type: Boolean,
    required: true,
  },
  isStreaming: {
    type: Boolean,
    required: true,
  },
  report: {
    type: Object,
    required: true,
  },
})

defineEmits(['set-verdict', 'submit-feedback', 'update-feedback'])

function formatStatus(status) {
  if (status === 'partially_answerable') {
    return '부분적으로 답변 가능'
  }
  if (status === 'not_yet_answerable') {
    return '아직 답변 어려움'
  }
  return '답변 가능'
}

function formatConfidence(confidence) {
  if (confidence === 'high') {
    return '신뢰도 높음'
  }
  if (confidence === 'low') {
    return '신뢰도 낮음'
  }
  return '신뢰도 보통'
}
</script>
