<template>
  <!-- The only HTML sink for mobile icons; `getMobileIcon` only returns local allowlisted SVG. -->
  <!-- eslint-disable-next-line vue/no-v-html -->
  <span class="m-icon" :style="{ width: size + 'px', height: size + 'px' }" v-html="svgContent"></span>
</template>

<script setup>
import { computed } from 'vue'
import { getMobileIcon } from './MobileIcons.js'

const props = defineProps({
  name: { type: String, required: true },
  size: { type: Number, default: 24 }
})

const svgContent = computed(() => getMobileIcon(props.name))
</script>

<style scoped>
.m-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  flex-shrink: 0;
}
.m-icon :deep(svg) {
  width: 100%;
  height: 100%;
}
</style>
