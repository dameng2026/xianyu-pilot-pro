<template>
  <div class="m-list-item" :class="{ 'm-list-item--no-arrow': !arrow }" @click="$emit('click')">
    <div v-if="$slots.icon" class="m-list-icon">
      <slot name="icon" />
    </div>
    <div class="m-list-content">
      <div class="m-list-title">{{ title }}</div>
      <div v-if="desc" class="m-list-desc">{{ desc }}</div>
    </div>
    <div v-if="$slots.extra || extra" class="m-list-extra">
      <slot name="extra">{{ extra }}</slot>
    </div>
    <div v-if="arrow" class="m-list-arrow">›</div>
  </div>
</template>

<script setup>
defineProps({
  title: { type: String, required: true },
  desc: { type: String, default: '' },
  extra: { type: String, default: '' },
  arrow: { type: Boolean, default: true }
})

defineEmits(['click'])
</script>

<style scoped>
.m-list-item {
  display: flex;
  align-items: center;
  gap: var(--m-space-3);
  padding: var(--m-space-3) var(--m-space-4);
  min-height: 56px;
  border-bottom: 1px solid var(--m-color-border-light);
  cursor: pointer;
  transition: background 0.15s;
}

.m-list-item:last-child {
  border-bottom: none;
}

.m-list-item:active {
  background: var(--m-color-bg-hover);
}

.m-list-icon {
  flex-shrink: 0;
  width: 36px;
  height: 36px;
  border-radius: var(--m-radius-md);
  background: var(--m-color-bg-subtle);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--m-color-text-secondary);
}

.m-list-content {
  flex: 1;
  min-width: 0;
}

.m-list-title {
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-primary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.m-list-desc {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  margin-top: 2px;
}

.m-list-extra {
  flex-shrink: 0;
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
}

.m-list-arrow {
  flex-shrink: 0;
  color: var(--m-color-text-disabled);
  font-size: 18px;
  line-height: 1;
}

.m-list-item--no-arrow .m-list-arrow {
  display: none;
}
</style>
