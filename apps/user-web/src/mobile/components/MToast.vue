<template>
  <TransitionGroup name="m-toast" tag="div" class="m-toast-container">
    <div
      v-for="t in toasts"
      :key="t.id"
      class="m-toast"
      :class="`m-toast-${t.type}`"
      @click="remove(t.id)"
    >
      <MIcon :name="iconFor(t.type)" :size="18" class="m-toast-icon" />
      <span class="m-toast-text">{{ t.message }}</span>
    </div>
  </TransitionGroup>
</template>

<script setup>
import { toasts, remove } from '../toast.js'
import MIcon from '../MIcon.vue'

function iconFor(type) {
  const map = { success: 'checkCircle', error: 'xCircle', warning: 'alertCircle', info: 'info' }
  return map[type] || 'info'
}
</script>

<style scoped>
.m-toast-container {
  position: fixed;
  top: calc(env(safe-area-inset-top) + 60px);
  left: 50%;
  transform: translateX(-50%);
  z-index: 9999;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--m-space-2);
  pointer-events: none;
  width: max-content;
  max-width: calc(100vw - 32px);
}
.m-toast {
  display: inline-flex;
  align-items: center;
  gap: var(--m-space-2);
  padding: 10px var(--m-space-4);
  border-radius: var(--m-radius-lg);
  background: var(--m-color-bg-elevated);
  box-shadow: var(--m-shadow-xs);
  font-size: var(--m-font-size-body);
  font-weight: var(--m-font-weight-medium);
  color: var(--m-color-text-primary);
  pointer-events: auto;
  cursor: pointer;
  max-width: 100%;
  word-break: break-word;
}
.m-toast-icon { flex-shrink: 0; }
.m-toast-success .m-toast-icon { color: var(--m-color-success); }
.m-toast-error .m-toast-icon { color: var(--m-color-danger); }
.m-toast-warning .m-toast-icon { color: var(--m-color-warning); }
.m-toast-info .m-toast-icon { color: var(--m-color-info); }

.m-toast-enter-active,
.m-toast-leave-active {
  transition: all 0.3s ease;
}
.m-toast-enter-from {
  opacity: 0;
  transform: translateY(-12px);
}
.m-toast-leave-to {
  opacity: 0;
  transform: translateY(-8px);
}
</style>
