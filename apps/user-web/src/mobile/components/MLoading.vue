<template>
  <!-- 全屏骨架屏 -->
  <div v-if="type === 'page'" class="m-skeleton-page">
    <div class="m-skeleton-block m-skeleton-hero"></div>
    <div class="m-skeleton-grid">
      <div class="m-skeleton-block m-skeleton-card"></div>
      <div class="m-skeleton-block m-skeleton-card"></div>
      <div class="m-skeleton-block m-skeleton-card"></div>
      <div class="m-skeleton-block m-skeleton-card"></div>
    </div>
    <div class="m-skeleton-block m-skeleton-list"></div>
    <div class="m-skeleton-block m-skeleton-list"></div>
  </div>

  <!-- 卡片骨架 -->
  <div v-else-if="type === 'card'" class="m-skeleton-card-wrap">
    <div class="m-skeleton-block m-skeleton-line-long"></div>
    <div class="m-skeleton-block m-skeleton-line-medium"></div>
    <div class="m-skeleton-block m-skeleton-line-short"></div>
  </div>

  <!-- 行内 spinner -->
  <div v-else class="m-spinner-wrap">
    <span class="m-spinner" :style="{ width: size + 'px', height: size + 'px' }"></span>
    <span v-if="text" class="m-spinner-text">{{ text }}</span>
  </div>
</template>

<script setup>
defineProps({
  type: { type: String, default: 'spinner' }, // page/card/spinner
  size: { type: Number, default: 14 },
  text: { type: String, default: '' }
})
</script>

<style scoped>
/* 骨架块通用 */
.m-skeleton-block {
  background: linear-gradient(
    90deg,
    var(--m-color-bg-subtle) 25%,
    var(--m-color-border-light) 37%,
    var(--m-color-bg-subtle) 63%
  );
  background-size: 400% 100%;
  animation: m-skeleton-shimmer 1.4s ease infinite;
  border-radius: var(--m-radius-sm);
}

@keyframes m-skeleton-shimmer {
  0% { background-position: 100% 50%; }
  100% { background-position: 0 50%; }
}

/* 全屏骨架 */
.m-skeleton-page {
  padding: var(--m-space-4);
}

.m-skeleton-hero {
  height: 100px;
  border-radius: var(--m-radius-lg);
  margin-bottom: var(--m-space-4);
}

.m-skeleton-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--m-space-2);
  margin-bottom: var(--m-space-4);
}

.m-skeleton-card {
  height: 72px;
  border-radius: var(--m-radius-lg);
}

.m-skeleton-list {
  height: 56px;
  margin-bottom: var(--m-space-2);
  border-radius: var(--m-radius-lg);
}

/* 卡片骨架 */
.m-skeleton-card-wrap {
  padding: var(--m-space-3);
}

.m-skeleton-line-long { height: 16px; width: 100%; margin-bottom: var(--m-space-2); }
.m-skeleton-line-medium { height: 14px; width: 70%; margin-bottom: var(--m-space-2); }
.m-skeleton-line-short { height: 12px; width: 40%; }

/* spinner */
.m-spinner-wrap {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-2);
}

.m-spinner {
  border: 2px solid var(--m-color-border);
  border-top-color: var(--m-color-primary);
  border-radius: 50%;
  animation: m-spinner-spin 0.8s linear infinite;
}

.m-spinner-text {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

@keyframes m-spinner-spin {
  to { transform: rotate(360deg); }
}
</style>
