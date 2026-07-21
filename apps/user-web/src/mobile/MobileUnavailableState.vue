<template>
  <div class="m-error" :class="{ 'm-error-compact': compact }">
    <div class="m-error-icon">
      <MIcon name="alertTriangle" :size="compact ? 48 : 64" :stroke-width="1.5" />
    </div>
    <div class="m-error-title">{{ title }}</div>
    <div v-if="description" class="m-error-desc">{{ description }}</div>
    <details v-if="details" class="m-error-details">
      <summary>详情</summary>
      <pre>{{ details }}</pre>
    </details>
    <button v-if="retryable" class="m-error-retry" @click="$emit('retry')">
      重新加载
    </button>
  </div>
</template>

<script setup>
import MIcon from './MIcon.vue'

defineProps({
  title: { type: String, default: '数据加载失败' },
  description: { type: String, default: '' },
  compact: { type: Boolean, default: false },
  retryable: { type: Boolean, default: true },
  details: { type: String, default: '' }
})

defineEmits(['retry'])
</script>

<style scoped>
.m-error {
  padding: var(--m-space-12) var(--m-space-6);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}
.m-error-compact {
  padding: var(--m-space-6) var(--m-space-4);
}

.m-error-icon {
  color: var(--m-color-warning);
  margin-bottom: var(--m-space-4);
}

.m-error-title {
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-secondary);
}

.m-error-desc {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  margin-top: var(--m-space-1);
  max-width: 80%;
}

.m-error-details {
  margin-top: var(--m-space-3);
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  max-width: 100%;
}

.m-error-details summary {
  cursor: pointer;
  color: var(--m-color-primary);
}

.m-error-details pre {
  margin-top: var(--m-space-2);
  text-align: left;
  white-space: pre-wrap;
  word-break: break-all;
  background: var(--m-color-bg-subtle);
  padding: var(--m-space-2);
  border-radius: var(--m-radius-md);
  font-family: var(--m-font-family-mono);
  font-size: var(--m-font-size-tiny);
}

.m-error-retry {
  margin-top: var(--m-space-4);
  padding: 8px var(--m-space-4);
  border: 1px solid var(--m-color-border);
  background: transparent;
  color: var(--m-color-text-primary);
  border-radius: var(--m-radius-md);
  font-size: var(--m-font-size-body-sm);
  cursor: pointer;
}

.m-error-retry:active {
  background: var(--m-color-bg-hover);
}
</style>
