<template>
  <AdminDataState
    state="degraded"
    title="评论功能暂不可用"
    description="评论查询、发布和回复接口尚未接入。当前不会在浏览器内伪造评论，也不会把本地状态冒充为发布成功。"
    :retryable="false"
    compact
  />
</template>

<script setup lang="ts">
  import AdminDataState from '@/components/business/admin-data-state/index.vue'

  defineOptions({ name: 'CommentWidget' })
</script>
