<template>
  <div v-if="state === 'loading'" class="admin-data-state admin-data-state--loading" role="status" aria-live="polite">
    <ElSkeleton :rows="compact ? 2 : 4" animated />
    <span class="sr-only">{{ title || '正在加载数据' }}</span>
  </div>

  <ElAlert
    v-else-if="state === 'degraded'"
    class="admin-data-state admin-data-state--degraded"
    role="alert"
    type="warning"
    show-icon
    :closable="false"
    :title="title || '部分数据暂不可用'"
    :description="description"
  >
    <template v-if="retryable" #default>
      <ElButton type="warning" plain size="small" @click="retry">{{ retryText }}</ElButton>
    </template>
  </ElAlert>

  <div
    v-else
    :class="['admin-data-state', `admin-data-state--${state}`, { 'is-compact': compact }]"
    :role="state === 'error' ? 'alert' : 'status'"
    aria-live="polite"
  >
    <ElIcon class="admin-data-state__icon">
      <WarningFilled v-if="state === 'error'" />
      <InfoFilled v-else />
    </ElIcon>
    <div class="admin-data-state__content">
      <strong>{{ title || defaultTitle }}</strong>
      <p v-if="description">{{ description }}</p>
    </div>
    <ElButton v-if="state === 'error' && retryable" type="primary" plain @click="retry">
      {{ retryText }}
    </ElButton>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue'
  import { InfoFilled, WarningFilled } from '@element-plus/icons-vue'

  export type AdminDataState = 'loading' | 'empty' | 'error' | 'degraded'

  const props = withDefaults(defineProps<{
    state: AdminDataState
    title?: string
    description?: string
    retryText?: string
    retryable?: boolean
    compact?: boolean
  }>(), {
    title: '',
    description: '',
    retryText: '重试',
    retryable: true,
    compact: false
  })

  const emit = defineEmits<{
    retry: []
  }>()

  const defaultTitle = computed(() => props.state === 'empty' ? '暂无数据' : '数据暂不可用')

  function retry() {
    emit('retry')
  }
</script>

<style scoped>
  .admin-data-state {
    display: flex;
    align-items: center;
    gap: 14px;
    min-height: 132px;
    border: 1px dashed var(--el-border-color);
    border-radius: 14px;
    background: var(--el-fill-color-extra-light);
    padding: 22px;
  }

  .admin-data-state--loading {
    display: block;
  }

  .admin-data-state--degraded {
    min-height: auto;
    border-style: solid;
  }

  .admin-data-state--error {
    border-color: var(--el-color-danger-light-5);
    background: var(--el-color-danger-light-9);
  }

  .admin-data-state.is-compact {
    min-height: 92px;
    padding: 16px;
  }

  .admin-data-state__icon {
    flex: none;
    color: var(--el-color-warning);
    font-size: 30px;
  }

  .admin-data-state--error .admin-data-state__icon {
    color: var(--el-color-danger);
  }

  .admin-data-state__content {
    min-width: 0;
    flex: 1;
  }

  .admin-data-state__content strong {
    color: var(--el-text-color-primary);
    font-size: 15px;
  }

  .admin-data-state__content p {
    margin: 6px 0 0;
    color: var(--el-text-color-secondary);
    font-size: 13px;
    line-height: 1.6;
  }

  .sr-only {
    position: absolute;
    width: 1px;
    height: 1px;
    overflow: hidden;
    clip: rect(0, 0, 0, 0);
    white-space: nowrap;
    clip-path: inset(50%);
  }

  @media (max-width: 640px) {
    .admin-data-state {
      align-items: flex-start;
      flex-direction: column;
    }
  }
</style>
