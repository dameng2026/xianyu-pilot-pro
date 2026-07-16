<template>
  <div class="feature-unavailable-page">
    <EmptyState
      :variant="displayVariant"
      :icon="displayIcon"
      :title="displayTitle"
      :description="displayDescription"
    >
      <template v-if="showUpgradeAction" #actions>
        <button class="upgrade-btn" type="button" @click="goUpgrade">立即升级</button>
      </template>
    </EmptyState>
  </div>
</template>

<script setup>
import { computed } from 'vue'
import EmptyState from '../components/EmptyState.vue'

const props = defineProps({
  /** 拦截原因：disabled（暂未开放）| level（等级不足） */
  reason: { type: String, default: 'disabled' },
  /** 要求的等级：normal | vip | svp | svip */
  required: { type: String, default: '' },
  /** 被拦截的功能 key（可选，用于日志） */
  featureKey: { type: String, default: '' }
})

const emit = defineEmits(['navigate'])

const LEVEL_LABELS = {
  normal: '普通用户',
  vip: 'VIP',
  svp: 'SVP',
  svip: 'SVP'
}

const showUpgradeAction = computed(() => props.reason === 'level' && Boolean(props.required))

const displayVariant = computed(() => (props.reason === 'level' ? 'default' : 'dev'))
const displayIcon = computed(() => (props.reason === 'level' ? '🔒' : ''))
const displayTitle = computed(() => {
  if (props.reason === 'level') return '等级不足'
  return '暂未开放'
})
const displayDescription = computed(() => {
  if (props.reason === 'level') {
    const label = LEVEL_LABELS[props.required] || props.required || '更高等级'
    return `该功能需要 ${label} 等级才能使用，请升级后访问。`
  }
  return '该功能正在维护中，敬请期待。'
})

function goUpgrade() {
  emit('navigate', 'vip')
}
</script>

<style scoped>
.feature-unavailable-page {
  padding: 24px;
  display: flex;
  justify-content: center;
}
.feature-unavailable-page :deep(.empty-cta) {
  max-width: 560px;
  width: 100%;
}
.upgrade-btn {
  padding: 8px 20px;
  background: linear-gradient(135deg, #ffd54f, #ffa726);
  color: #5a3500;
  border: none;
  border-radius: 8px;
  font-weight: 600;
  font-size: 14px;
  cursor: pointer;
  transition: transform 0.15s ease, box-shadow 0.15s ease;
}
.upgrade-btn:hover {
  transform: translateY(-1px);
  box-shadow: 0 4px 12px rgba(255, 167, 38, 0.35);
}
</style>
