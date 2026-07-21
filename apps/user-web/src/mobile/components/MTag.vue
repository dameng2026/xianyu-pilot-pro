<template>
  <span class="m-tag" :class="tagClass">
    <slot />
  </span>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  type: { type: String, default: 'neutral' }, // success/warning/danger/info/neutral/outline
  size: { type: String, default: 'md' }, // sm/md
  count: { type: Boolean, default: false } // 数字徽标
})

const tagClass = computed(() => [
  `m-tag--${props.type}`,
  `m-tag--${props.size}`,
  { 'm-tag--count': props.count }
])
</script>

<style scoped>
.m-tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 2px var(--m-space-2);
  border-radius: var(--m-radius-pill);
  font-weight: var(--m-font-weight-medium);
  line-height: 1.4;
}

.m-tag--sm { font-size: var(--m-font-size-tiny); height: 20px; }
.m-tag--md { font-size: var(--m-font-size-caption); height: 24px; }

/* 类型 */
.m-tag--success { background: var(--m-color-success-bg); color: var(--m-color-success-text); }
.m-tag--warning { background: var(--m-color-warning-bg); color: var(--m-color-warning-text); }
.m-tag--danger { background: var(--m-color-danger-bg); color: var(--m-color-danger-text); }
.m-tag--info { background: var(--m-color-info-bg); color: var(--m-color-info-text); }
.m-tag--neutral { background: var(--m-color-bg-subtle); color: var(--m-color-text-secondary); }
.m-tag--outline { background: transparent; color: var(--m-color-text-secondary); border: 1px solid var(--m-color-border); }

/* 数字徽标 */
.m-tag--count {
  background: var(--m-color-danger);
  color: var(--m-color-text-inverse);
  min-width: 20px;
  height: 20px;
  padding: 0 6px;
  font-size: var(--m-font-size-tiny);
  font-weight: var(--m-font-weight-bold);
}
</style>
