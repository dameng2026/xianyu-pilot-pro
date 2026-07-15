<template>
  <section class="legacy-account-vip-page">
    <EmptyState
      variant="dev"
      title="账号会员页已停用"
      description="旧页面曾展示静态账号、价格和权益，无法代表当前真实套餐。请前往会员中心，以后台返回的套餐与账号权益为准。"
    >
      <template #actions>
        <AppButton type="primary" @click="openVipCenter">前往会员中心</AppButton>
      </template>
    </EmptyState>
  </section>
</template>

<script setup>
import AppButton from '../components/AppButton.vue'
import EmptyState from '../components/EmptyState.vue'

const emit = defineEmits(['navigate'])

function openVipCenter() {
  emit('navigate', 'vip')
  window.dispatchEvent(new CustomEvent('xya-navigate', { detail: { route: 'vip' } }))
}
</script>

<style scoped>
.legacy-account-vip-page {
  max-width: 760px;
  margin: 36px auto;
}
</style>
