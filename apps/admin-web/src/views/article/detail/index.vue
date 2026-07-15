<template>
  <div class="page-content mb-5">
    <AdminDataState
      state="degraded"
      title="文章详情暂不可用"
      description="真实文章详情接口尚未接入，样例内容与第三方数据源已移除。该页面不会展示无法验证来源的文章。"
      :retryable="false"
    />
  </div>
</template>

<script setup lang="ts">
  import AdminDataState from '@/components/business/admin-data-state/index.vue'

  defineOptions({ name: 'ArticleDetail' })
</script>
