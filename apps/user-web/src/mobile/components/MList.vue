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
  border: none;
  border-radius: var(--m-radius-xl);
  overflow: hidden;
  box-shadow: var(--m-shadow-xs);
}
</style>
