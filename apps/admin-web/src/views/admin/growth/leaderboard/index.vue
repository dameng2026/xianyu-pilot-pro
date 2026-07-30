<template>
  <div class="growth-leaderboard-page">
    <!-- 顶部标题 -->
    <ElCard shadow="never" class="toolbar-card">
      <div class="page-title-row">
        <div>
          <h2>拉新排行榜</h2>
          <p>按累计拉新人数排名，可查看 TOP 50 的代理拉新情况与收益。</p>
        </div>
        <div class="actions">
          <ElInputNumber v-model="limit" :min="10" :max="200" :step="10" size="small" />
          <ElButton :loading="loading" @click="loadList">刷新</ElButton>
        </div>
      </div>
    </ElCard>

    <!-- 排行榜列表 -->
    <ElCard shadow="never" class="section-card">
      <AdminDataState v-if="listState === 'loading'" state="loading" title="正在读取排行榜" compact />
      <AdminDataState
        v-else-if="listState === 'error'"
        state="error"
        title="排行榜暂不可用"
        :description="listError"
        retry-text="重试"
        compact
        @retry="loadList"
      />
      <template v-else>
        <ElTable :data="list" border stripe height="600">
          <template #empty><div class="empty-state">暂无排行数据</div></template>
          <ElTableColumn label="排名" width="80" align="center">
            <template #default="scope">
              <span :class="['rank-badge', `rank-${scope.$index + 1}`]">{{ scope.$index + 1 }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="用户" min-width="160">
            <template #default="scope">
              <div class="user-cell">
                <span class="user-avatar" v-if="scope.row.avatar">
                  <img :src="scope.row.avatar" alt="" />
                </span>
                <div class="user-meta">
                  <div class="user-name">{{ scope.row.nickname || scope.row.username || `用户${scope.row.userId}` }}</div>
                  <small class="muted">#{{ scope.row.userId }}</small>
                </div>
              </div>
            </template>
          </ElTableColumn>
          <ElTableColumn label="代理等级" width="120">
            <template #default="scope">
              <ElTag v-if="scope.row.tierName" type="warning" size="small">{{ scope.row.tierName }}</ElTag>
              <span v-else class="muted">普通代理</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="拉新人数" width="120">
            <template #default="scope">
              <b>{{ scope.row.totalReferrals ?? 0 }}</b>
              <small class="muted">人</small>
            </template>
          </ElTableColumn>
          <ElTableColumn label="有效拉新" width="120">
            <template #default="scope">
              <b class="text-success">{{ scope.row.validReferrals ?? 0 }}</b>
              <small class="muted">人</small>
            </template>
          </ElTableColumn>
          <ElTableColumn label="累计收益" width="140">
            <template #default="scope">
              <span class="text-success">¥{{ formatAmount(scope.row.totalEarnings) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="Token 奖励" width="120">
            <template #default="scope">
              <b>{{ scope.row.totalTokenReward ?? 0 }}</b> 个
            </template>
          </ElTableColumn>
        </ElTable>
      </template>
    </ElCard>
  </div>
</template>

<script setup lang="ts">
  import { onMounted, ref, watch } from 'vue'
  import { getAdminGrowthLeaderboard } from '@/api/growth'
  import AdminDataState from '@/components/business/admin-data-state/index.vue'

  defineOptions({ name: 'AdminGrowthLeaderboardPage' })

  const loading = ref(false)
  const limit = ref(50)
  const listState = ref<'loading' | 'ready' | 'error'>('loading')
  const listError = ref('')
  const list = ref<any[]>([])

  function formatAmount(cent: any): string {
    const n = Number(cent)
    if (!Number.isFinite(n)) return '0.00'
    return (n / 100).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }

  async function loadList() {
    listState.value = 'loading'
    listError.value = ''
    loading.value = true
    try {
      list.value = await getAdminGrowthLeaderboard(limit.value)
      listState.value = 'ready'
    } catch (e: any) {
      listError.value = e?.message || '未知错误'
      listState.value = 'error'
    } finally {
      loading.value = false
    }
  }

  watch(limit, () => {
    loadList()
  })

  onMounted(() => {
    loadList()
  })
</script>

<style scoped lang="scss">
  .growth-leaderboard-page {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .toolbar-card {
    :deep(.el-card__body) {
      padding: 16px 20px;
    }
  }

  .page-title-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 12px;

    h2 {
      margin: 0 0 4px;
      font-size: 18px;
      font-weight: 600;
    }
    p {
      margin: 0;
      font-size: 13px;
      color: #6b7280;
    }
    .actions {
      display: flex;
      gap: 8px;
      align-items: center;
    }
  }

  .user-cell {
    display: flex;
    align-items: center;
    gap: 8px;

    .user-avatar {
      width: 32px;
      height: 32px;
      border-radius: 50%;
      overflow: hidden;
      flex-shrink: 0;
      img {
        width: 100%;
        height: 100%;
        object-fit: cover;
      }
    }
    .user-meta {
      display: flex;
      flex-direction: column;
    }
    .user-name {
      font-size: 13px;
    }
  }

  .rank-badge {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    width: 28px;
    height: 28px;
    border-radius: 50%;
    background: #f3f4f6;
    color: #6b7280;
    font-size: 13px;
    font-weight: 700;

    &.rank-1 {
      background: linear-gradient(135deg, #fde68a, #f59e0b);
      color: #fff;
      box-shadow: 0 2px 8px rgba(245, 158, 11, 0.3);
    }
    &.rank-2 {
      background: linear-gradient(135deg, #e5e7eb, #9ca3af);
      color: #fff;
      box-shadow: 0 2px 8px rgba(156, 163, 175, 0.3);
    }
    &.rank-3 {
      background: linear-gradient(135deg, #fed7aa, #fb923c);
      color: #fff;
      box-shadow: 0 2px 8px rgba(251, 146, 60, 0.3);
    }
  }

  .text-success {
    color: #10b981;
  }
  .muted {
    color: #9ca3af;
    font-size: 12px;
    margin-left: 4px;
  }

  .empty-state {
    text-align: center;
    color: #9ca3af;
    padding: 24px;
  }
</style>
