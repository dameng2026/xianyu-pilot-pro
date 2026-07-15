<template>
  <div class="page-content mb-5">
    <AdminDataState
      state="degraded"
      title="文章管理暂不可用"
      description="尚未接入真实文章服务，样例文章及新增、编辑入口已移除，且该页面不会进入生产菜单。接入带权限校验和审计记录的内容服务后方可启用。"
      :retryable="false"
    />
  </div>
</template>

<script setup lang="ts">
  import AdminDataState from '@/components/business/admin-data-state/index.vue'

  defineOptions({ name: 'ArticleList' })
</script>
