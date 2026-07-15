<template>
  <div class="page-content mb-5">
    <AdminDataState
      state="degraded"
      title="服务器管理暂不可用"
      description="尚未接入真实主机资产、资源监控和控制后端。为避免展示伪造指标或触发无效操作，开机、关机和重启能力已停用；请使用企业已授权的基础设施控制台。"
      :retryable="false"
    />
  </div>
</template>

<script setup lang="ts">
  import AdminDataState from '@/components/business/admin-data-state/index.vue'

  defineOptions({ name: 'SafeguardServer' })
</script>
