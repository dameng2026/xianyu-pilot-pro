<template>
  <div class="m-card" :class="cardClass">
    <div v-if="title || $slots.header || showAction" class="m-card-header">
      <slot name="header">
        <div class="m-card-title">{{ title }}</div>
      </slot>
      <div v-if="$slots.action || actionText" class="m-card-action" @click="$emit('action')">
        <slot name="action">{{ actionText }}</slot>
      </div>
    </div>
    <div class="m-card-body">
      <slot />
    </div>
  </div>
</template>

<script setup>
import { computed } from 'vue'

const props = defineProps({
  title: { type: String, default: '' },
  actionText: { type: String, default: '' },
  showAction: { type: Boolean, default: false },
  variant: { type: String, default: 'default' }, // default / compact / borderless / success / warning / danger / info
  clickable: { type: Boolean, default: false }
})

defineEmits(['action'])

const cardClass = computed(() => [
  `m-card--${props.variant}`,
  { 'm-card--clickable': props.clickable }
])
</script>

<style scoped>
.m-card {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-lg);
  padding: var(--m-space-3);
  box-shadow: var(--m-shadow-card);
}

.m-card--compact {
  padding: var(--m-space-2);
}

.m-card--borderless {
  border: none;
  box-shadow: none;
  background: transparent;
}

.m-card--success {
  background: var(--m-color-success-bg);
  border-color: var(--m-color-success-border);
}

.m-card--warning {
  background: var(--m-color-warning-bg);
  border-color: var(--m-color-warning-border);
}

.m-card--danger {
  background: var(--m-color-danger-bg);
  border-color: var(--m-color-danger-border);
}

.m-card--info {
  background: var(--m-color-info-bg);
  border-color: var(--m-color-info-border);
}

.m-card--clickable {
  cursor: pointer;
  transition: transform 0.15s;
}

.m-card--clickable:active {
  transform: scale(0.98);
}

.m-card-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--m-space-3);
}

.m-card-title {
  font-size: var(--m-font-size-h2);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
}

.m-card-action {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  cursor: pointer;
}
</style>
