<template>
  <div class="page-content mb-5">
    <AdminDataState
      state="degraded"
      title="留言管理暂不可用"
      description="留言查询、审核、回复和审计接口尚未接入，样例留言已移除。生产环境不会把演示数据当作用户留言。"
      :retryable="false"
    />
  </div>
</template>

<script setup lang="ts">
  import AdminDataState from '@/components/business/admin-data-state/index.vue'

  defineOptions({ name: 'ArticleComment' })
</script>
