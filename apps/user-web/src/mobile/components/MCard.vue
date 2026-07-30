<template>
  <div class="m-card" :class="cardClass">
    <div v-if="title || $slots.header || showAction" class="m-card-header">
      <slot name="header">
        <div class="m-card-title">{{ title }}</div>
        <p v-if="desc" class="m-card-desc">{{ desc }}</p>
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
  desc: { type: String, default: '' },
  actionText: { type: String, default: '' },
  showAction: { type: Boolean, default: false },
  variant: { type: String, default: 'default' },
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
  background: #ffffff;
  border: 1px solid #e7edf7;
  border-radius: 14px;
  padding: 18px;
  box-shadow: 0 1px 2px rgba(31, 53, 94, .04), 0 8px 24px rgba(31, 53, 94, .06);
}

.m-card--compact {
  padding: 12px;
}

.m-card--borderless {
  border: none;
  box-shadow: none;
  background: transparent;
  padding: 0;
}

.m-card--success {
  background: #e9fbf3;
  border-color: #c7f3df;
}

.m-card--warning {
  background: #fff5e6;
  border-color: #ffe1b0;
}

.m-card--danger {
  background: #fff0f1;
  border-color: #ffd6d6;
}

.m-card--info {
  background: #edf5ff;
  border-color: rgba(13, 107, 255, 0.2);
}

.m-card--clickable {
  cursor: pointer;
  transition: all 0.15s ease;
}

.m-card--clickable:active {
  transform: scale(0.98);
  background: #f8fbff;
}

.m-card-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 14px;
}

.m-card-title {
  font-size: 18px;
  font-weight: 800;
  color: #15213d;
  line-height: 1.2;
}

.m-card-desc {
  margin: 6px 0 0;
  font-size: 13px;
  color: #72809a;
  line-height: 1.4;
}

.m-card-action {
  font-size: 13px;
  color: #0d6bff;
  cursor: pointer;
  font-weight: 600;
  flex-shrink: 0;
  margin-left: 12px;
}

.m-card-action:active {
  opacity: 0.7;
}

.m-card-body {
  font-size: 14px;
  color: #44536f;
}
</style>
