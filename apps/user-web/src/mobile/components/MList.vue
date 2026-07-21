<template>
  <div class="m-list" :class="{ 'm-list--compact': compact }">
    <slot />
  </div>
</template>

<script setup>
defineProps({
  compact: { type: Boolean, default: false }
})
</script>

<style scoped>
.m-list {
  background: var(--m-color-bg-card);
  border: 1px solid var(--m-color-border);
  border-radius: var(--m-radius-lg);
  overflow: hidden;
}
</style>
