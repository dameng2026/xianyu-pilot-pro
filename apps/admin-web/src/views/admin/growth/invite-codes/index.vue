<template>
  <div class="growth-invite-codes-page">
    <!-- 顶部标题 -->
    <ElCard shadow="never" class="toolbar-card">
      <div class="page-title-row">
        <div>
          <h2>邀请码管理</h2>
          <p>查看所有用户创建的邀请码及其统计数据，包括绑定用户、拉新人数、累计收益等。</p>
        </div>
        <div class="actions">
          <ElButton :loading="loading" @click="loadList">刷新</ElButton>
        </div>
      </div>
    </ElCard>

    <!-- 邀请码列表 -->
    <ElCard shadow="never" class="section-card">
      <template #header>
        <div class="table-header">
          <span>邀请码列表</span>
          <div class="actions small">
            <ElInput
              v-model="query.keyword"
              placeholder="邀请码/用户名"
              clearable
              style="width: 220px"
              @keyup.enter="onSearch"
            />
            <ElButton @click="onSearch">查询</ElButton>
          </div>
        </div>
      </template>
      <AdminDataState v-if="listState === 'loading'" state="loading" title="正在读取邀请码" compact />
      <AdminDataState
        v-else-if="listState === 'error'"
        state="error"
        title="邀请码列表暂不可用"
        :description="listError"
        retry-text="重新加载"
        compact
        @retry="loadList"
      />
      <template v-else>
        <ElTable :data="list.records" border stripe height="540">
          <template #empty><div class="empty-state">暂无邀请码</div></template>
          <ElTableColumn prop="id" label="ID" width="70" />
          <ElTableColumn label="邀请码" width="180">
            <template #default="scope">
              <div class="code-cell">
                <b class="code-text">{{ scope.row.code }}</b>
                <ElButton link size="small" @click="copyCode(scope.row.code)">
                  <i class="ri-file-copy-line" />
                </ElButton>
              </div>
            </template>
          </ElTableColumn>
          <ElTableColumn label="所属用户" min-width="140">
            <template #default="scope">
              <div class="user-cell">
                <span>{{ scope.row.ownerNickname || scope.row.ownerUsername || `用户${scope.row.ownerId}` }}</span>
                <small class="muted">#{{ scope.row.ownerId }}</small>
              </div>
            </template>
          </ElTableColumn>
          <ElTableColumn label="渠道" width="120">
            <template #default="scope">
              <ElTag v-if="scope.row.channel" size="small" type="info">{{ scope.row.channel }}</ElTag>
              <span v-else class="muted">—</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="绑定用户" min-width="140">
            <template #default="scope">
              <div v-if="scope.row.boundUserId" class="user-cell">
                <span>{{ scope.row.boundNickname || scope.row.boundUsername || `用户${scope.row.boundUserId}` }}</span>
                <small class="muted">{{ scope.row.boundTime }}</small>
              </div>
              <span v-else class="muted">未绑定</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="拉新人数" width="100">
            <template #default="scope">
              <b>{{ scope.row.referralCount ?? 0 }}</b>
              <small class="muted">（有效 {{ scope.row.validReferralCount ?? 0 }}）</small>
            </template>
          </ElTableColumn>
          <ElTableColumn label="累计收益" width="120">
            <template #default="scope">
              <span class="text-success">¥{{ formatAmount(scope.row.totalCommission) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="Token 奖励" width="110">
            <template #default="scope">
              <b>{{ scope.row.totalTokenReward ?? 0 }}</b> 个
            </template>
          </ElTableColumn>
          <ElTableColumn label="状态" width="80">
            <template #default="scope">
              <ElTag :type="Number(scope.row.enabled) === 1 ? 'success' : 'info'" size="small">
                {{ Number(scope.row.enabled) === 1 ? '启用' : '禁用' }}
              </ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn prop="createdTime" label="创建时间" width="160" />
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
  import { ElMessage } from 'element-plus'
  import { getGrowthInviteCodesPage } from '@/api/growth'
  import AdminDataState from '@/components/business/admin-data-state/index.vue'

  defineOptions({ name: 'AdminGrowthInviteCodesPage' })

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

  async function loadList() {
    listState.value = 'loading'
    listError.value = ''
    loading.value = true
    try {
      const res = await getGrowthInviteCodesPage({
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

  async function copyCode(code: string) {
    try {
      await navigator.clipboard.writeText(code)
      ElMessage.success('已复制邀请码：' + code)
    } catch {
      ElMessage.warning('复制失败，请手动选择')
    }
  }

  onMounted(() => {
    loadList()
  })
</script>

<style scoped lang="scss">
  .growth-invite-codes-page {
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

  .code-cell {
    display: flex;
    align-items: center;
    gap: 4px;

    .code-text {
      font-family: 'JetBrains Mono', 'Courier New', monospace;
      font-size: 13px;
      letter-spacing: 0.5px;
    }
  }

  .user-cell {
    display: flex;
    flex-direction: column;

    small {
      font-size: 11px;
    }
  }

  .text-success {
    color: #10b981;
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
