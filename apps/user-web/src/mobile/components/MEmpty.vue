<template>
  <div class="m-empty" :class="{ 'm-empty--inline': inline }">
    <div v-if="icon" class="m-empty-icon">
      <MIcon :name="icon" :size="64" :stroke-width="1.5" />
    </div>
    <div class="m-empty-title">{{ title }}</div>
    <div v-if="desc" class="m-empty-desc">{{ desc }}</div>
    <div v-if="$slots.default" class="m-empty-action">
      <slot />
    </div>
  </div>
</template>

<script setup>
import MIcon from '../MIcon.vue'

defineProps({
  icon: { type: String, default: 'box' },
  title: { type: String, required: true },
  desc: { type: String, default: '' },
  inline: { type: Boolean, default: false }
})
</script>

<style scoped>
.m-empty {
  padding: var(--m-space-12) var(--m-space-6);
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
}

.m-empty--inline {
  padding: var(--m-space-6);
}

.m-empty-icon {
  color: var(--m-color-text-disabled);
  margin-bottom: var(--m-space-4);
}

.m-empty-title {
  font-size: var(--m-font-size-h3);
  font-weight: var(--m-font-weight-semibold);
  color: var(--m-color-text-secondary);
}

.m-empty-desc {
  font-size: var(--m-font-size-caption);
  color: var(--m-color-text-tertiary);
  margin-top: var(--m-space-1);
}

.m-empty-action {
  margin-top: var(--m-space-4);
}
</style>
