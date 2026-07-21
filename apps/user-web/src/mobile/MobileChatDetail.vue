<template>
  <div class="m-chat-detail-redirect" aria-hidden="true"></div>
</template>

<script setup>
import { onMounted } from 'vue'

const emit = defineEmits(['navigate', 'force-desktop', 'back'])

onMounted(() => {
  // @deprecated chat-detail 路由已废弃，聊天详情统一在 MobileMessages 内查看。
  // 正常情况下不会渲染本组件（mobileRouteState 已将 chat-detail 重定向到 messages）。
  // 此处作为兜底：若被渲染，立即重定向回消息列表。
  emit('navigate', 'messages')
})
</script>

<style scoped>
.m-chat-detail-redirect {
  display: none;
}
</style>
