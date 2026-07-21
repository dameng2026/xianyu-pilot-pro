<template>
  <button
    class="m-btn"
    :class="btnClass"
    :disabled="disabled || loading"
    @click="handleClick"
  >
    <span v-if="loading" class="m-btn-loading"></span>
    <slot v-if="!loading" name="icon"></slot>
    <span class="m-btn-text"><slot /></span>
  </button>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  type: { type: String, default: 'secondary' }, // primary/secondary/outline/danger/text/pill
  size: { type: String, default: 'md' }, // sm/md/lg
  disabled: { type: Boolean, default: false },
  loading: { type: Boolean, default: false }
})

const emit = defineEmits(['click'])

const btnClass = computed(() => [
  `m-btn--${props.type}`,
  `m-btn--${props.size}`
])

function handleClick(e) {
  if (props.disabled || props.loading) return
  emit('click', e)
}
</script>

<style scoped>
.m-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: var(--m-space-2);
  border: none;
  cursor: pointer;
  font-family: inherit;
  transition: all 0.15s;
  white-space: nowrap;
}

/* 尺寸 */
.m-btn--sm { height: 32px; padding: 0 var(--m-space-3); font-size: var(--m-font-size-body-sm); font-weight: var(--m-font-weight-medium); }
.m-btn--md { height: 40px; padding: 0 var(--m-space-4); font-size: var(--m-font-size-body); font-weight: var(--m-font-weight-medium); }
.m-btn--lg { height: 44px; padding: 0 var(--m-space-5); font-size: var(--m-font-size-h3); font-weight: var(--m-font-weight-semibold); }

/* 类型 */
.m-btn--primary {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  border-radius: var(--m-radius-md);
}
.m-btn--primary:active { background: var(--m-color-primary-active); transform: scale(0.98); }

.m-btn--secondary {
  background: var(--m-color-bg-subtle);
  color: var(--m-color-text-primary);
  border-radius: var(--m-radius-md);
}
.m-btn--secondary:active { transform: scale(0.98); }

.m-btn--outline {
  background: transparent;
  color: var(--m-color-text-primary);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-md);
}
.m-btn--outline:active { background: var(--m-color-bg-hover); transform: scale(0.98); }

.m-btn--danger {
  background: var(--m-color-danger);
  color: var(--m-color-text-inverse);
  border-radius: var(--m-radius-md);
}
.m-btn--danger:active { transform: scale(0.98); }

.m-btn--text {
  background: transparent;
  color: var(--m-color-primary);
  padding: 0 var(--m-space-2);
}
.m-btn--text:active { opacity: 0.7; }

.m-btn--pill {
  background: var(--m-color-primary);
  color: var(--m-color-text-inverse);
  border-radius: var(--m-radius-pill);
}
.m-btn--pill:active { transform: scale(0.98); }

/* 状态 */
.m-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.m-btn-loading {
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: m-btn-spin 0.8s linear infinite;
}

@keyframes m-btn-spin {
  to { transform: rotate(360deg); }
}
</style>
