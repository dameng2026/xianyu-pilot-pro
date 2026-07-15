<template>
  <div class="page-content mb-5">
    <AdminDataState
      state="degraded"
      title="文章发布暂不可用"
      description="文章分类、详情、媒体上传和发布接口尚未接入真实内容服务。本页面不会保存、上传或发布任何内容，也不会访问第三方样例接口；生产菜单保持关闭。"
      :retryable="false"
    />
  </div>
</template>

<script setup lang="ts">
  import AdminDataState from '@/components/business/admin-data-state/index.vue'

  defineOptions({ name: 'ArticlePublish' })
</script>
