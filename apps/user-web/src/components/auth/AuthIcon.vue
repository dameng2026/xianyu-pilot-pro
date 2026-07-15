<template>
  <!-- The only HTML sink for auth icons; `getAuthIcon` only returns local allowlisted SVG. -->
  <!-- eslint-disable-next-line vue/no-v-html -->
  <span aria-hidden="true" v-html="svg"></span>
</template>

<script setup>
import { computed } from 'vue'
import { getAuthIcon } from './authContent.js'

const props = defineProps({
  name: { type: String, required: true }
})

const svg = computed(() => getAuthIcon(props.name))
</script>
