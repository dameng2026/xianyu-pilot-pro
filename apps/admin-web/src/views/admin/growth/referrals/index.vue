<template>
  <div class="growth-referrals-page">
    <!-- 顶部标题 -->
    <ElCard shadow="never" class="toolbar-card">
      <div class="page-title-row">
        <div>
          <h2>推荐关系</h2>
          <p>查看所有一级用户与二级用户的绑定关系，以及二级用户带来的分成收益与 Token 奖励。</p>
        </div>
        <div class="actions">
          <ElButton :loading="loading" @click="loadList">刷新</ElButton>
        </div>
      </div>
    </ElCard>

    <!-- 推荐关系列表 -->
    <ElCard shadow="never" class="section-card">
      <template #header>
        <div class="table-header">
          <span>推荐关系明细</span>
          <div class="actions small">
            <ElInput
              v-model="query.keyword"
              placeholder="用户名/邀请码"
              clearable
              style="width: 220px"
              @keyup.enter="onSearch"
            />
            <ElButton @click="onSearch">查询</ElButton>
          </div>
        </div>
      </template>
      <AdminDataState v-if="listState === 'loading'" state="loading" title="正在读取推荐关系" compact />
      <AdminDataState
        v-else-if="listState === 'error'"
        state="error"
        title="推荐关系列表暂不可用"
        :description="listError"
        retry-text="重新加载"
        compact
        @retry="loadList"
      />
      <template v-else>
        <ElTable :data="list.records" border stripe height="540">
          <template #empty><div class="empty-state">暂无推荐关系</div></template>
          <ElTableColumn prop="id" label="ID" width="70" />
          <ElTableColumn label="一级用户（邀请人）" min-width="160">
            <template #default="scope">
              <div class="user-cell">
                <span class="user-name">{{ scope.row.inviterNickname || scope.row.inviterUsername || `用户${scope.row.inviterId}` }}</span>
                <small class="muted">#{{ scope.row.inviterId }}</small>
              </div>
            </template>
          </ElTableColumn>
          <ElTableColumn label="代理等级" width="120">
            <template #default="scope">
              <ElTag v-if="scope.row.tierName" type="warning" size="small">{{ scope.row.tierName }}</ElTag>
              <span v-else class="muted">普通代理</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="二级用户（被邀请人）" min-width="160">
            <template #default="scope">
              <div class="user-cell">
                <span class="user-avatar" v-if="scope.row.inviteeAvatar">
                  <img :src="scope.row.inviteeAvatar" alt="" />
                </span>
                <div class="user-meta">
                  <span class="user-name">{{ scope.row.inviteeNickname || scope.row.inviteeUsername || `用户${scope.row.inviteeId}` }}</span>
                  <small class="muted">#{{ scope.row.inviteeId }}</small>
                </div>
              </div>
            </template>
          </ElTableColumn>
          <ElTableColumn label="邀请码" width="160">
            <template #default="scope">
              <span class="code-text">{{ scope.row.inviteCode || '—' }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="绑定时间" width="160">
            <template #default="scope">{{ scope.row.boundTime || '—' }}</template>
          </ElTableColumn>
          <ElTableColumn label="首单消费" width="120">
            <template #default="scope">
              <b v-if="scope.row.firstConsumeAmount" class="text-warning">¥{{ formatAmount(scope.row.firstConsumeAmount) }}</b>
              <span v-else class="muted">未消费</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="累计分成" width="120">
            <template #default="scope">
              <span class="text-success">¥{{ formatAmount(scope.row.totalCommission) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="Token 奖励" width="110">
            <template #default="scope">
              <b>{{ scope.row.totalTokenReward ?? 0 }}</b> 个
            </template>
          </ElTableColumn>
          <ElTableColumn label="状态" width="100">
            <template #default="scope">
              <ElTag :type="statusTagType(scope.row.status)" size="small">{{ scope.row.statusText || statusText(scope.row.status) }}</ElTag>
            </template>
          </ElTableColumn>
        </ElTable>
        <div class="pagination-row">
          <span class="muted">共 {{ list.total }} 条</span>
          <ElPagination
            v-model:current-page="query.page"
            v-model:page-size="query.size"
            layout="total, sizes, prev, pager, next, jumper"
            :total="list.total"
            :page-sizes="[10, 20, 50, 100]"
            @change="loadList"
          />
        </div>
      </template>
    </ElCard>
  </div>
</template>

<script setup lang="ts">
  import { onMounted, reactive, ref } from 'vue'
  import { getGrowthReferralsPage } from '@/api/growth'
  import AdminDataState from '@/components/business/admin-data-state/index.vue'

  defineOptions({ name: 'AdminGrowthReferralsPage' })

  const loading = ref(false)
  const listState = ref<'loading' | 'ready' | 'error'>('loading')
  const listError = ref('')
  const list = reactive<any>({ records: [], total: 0 })
  const query = reactive<any>({
    page: 1,
    size: 20,
    keyword: ''
  })

  function formatAmount(cent: any): string {
    const n = Number(cent)
    if (!Number.isFinite(n)) return '0.00'
    return (n / 100).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }

  function statusText(status?: string): string {
    switch (status) {
      case 'bound': return '已绑定'
      case 'first_consumed': return '已首单'
      case 'active': return '活跃'
      case 'inactive': return '不活跃'
      default: return status || '—'
    }
  }

  function statusTagType(status?: string) {
    switch (status) {
      case 'first_consumed': return 'success'
      case 'active': return 'success'
      case 'bound': return 'warning'
      case 'inactive': return 'info'
      default: return 'info'
    }
  }

  async function loadList() {
    listState.value = 'loading'
    listError.value = ''
    loading.value = true
    try {
      const res = await getGrowthReferralsPage({
        page: query.page,
        size: query.size,
        keyword: query.keyword || undefined
      })
      list.records = res.records
      list.total = res.total
      listState.value = 'ready'
    } catch (e: any) {
      listError.value = e?.message || '未知错误'
      listState.value = 'error'
    } finally {
      loading.value = false
    }
  }

  function onSearch() {
    query.page = 1
    loadList()
  }

  onMounted(() => {
    loadList()
  })
</script>

<style scoped lang="scss">
  .growth-referrals-page {
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
    }
  }

  .table-header {
    display: flex;
    justify-content: space-between;
    align-items: center;

    .actions.small {
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
      width: 26px;
      height: 26px;
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

  .code-text {
    font-family: 'JetBrains Mono', 'Courier New', monospace;
    font-size: 13px;
  }

  .text-success {
    color: #10b981;
  }
  .text-warning {
    color: #f59e0b;
  }
  .muted {
    color: #9ca3af;
    font-size: 12px;
  }

  .pagination-row {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-top: 12px;
  }

  .empty-state {
    text-align: center;
    color: #9ca3af;
    padding: 24px;
  }
</style>
