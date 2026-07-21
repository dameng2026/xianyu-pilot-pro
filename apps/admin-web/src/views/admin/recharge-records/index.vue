<template>
  <div class="recharge-records-page">
    <!-- 顶部标题区 -->
    <ElCard shadow="never" class="toolbar-card">
      <div class="page-title-row">
        <div>
          <h2>用户充值记录</h2>
          <p>
            查询所有用户的 Token 充值记录。默认显示全部用户，可通过用户名/订单号搜索，或通过用户 ID 精确过滤单个用户；
            也可在「用户管理」中点击某用户的「充值记录」按钮直接跳转查看。
          </p>
        </div>
        <div class="actions">
          <ElButton :loading="loading" @click="loadList">刷新</ElButton>
        </div>
      </div>
    </ElCard>

    <!-- 概览统计卡片 -->
    <div class="summary-grid">
      <ElCard shadow="never">
        <div class="metric-label">累计充值笔数</div>
        <div class="metric-value">{{ formatNumber(summary.totalRecords) }}</div>
        <div class="metric-sub">{{ userIdFilter ? '当前用户' : '全部用户' }}</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">累计充值 Token</div>
        <div class="metric-value text-success">{{ formatNumber(summary.totalTokens) }}</div>
        <div class="metric-sub">≈ ¥{{ formatNumber((Number(summary.totalTokens) || 0) / 100) }}</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">今日充值笔数</div>
        <div class="metric-value">{{ formatNumber(summary.todayRecords) }}</div>
        <div class="metric-sub">今日 0 点至今</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">今日充值 Token</div>
        <div class="metric-value text-success">{{ formatNumber(summary.todayTokens) }}</div>
        <div class="metric-sub">≈ ¥{{ formatNumber((Number(summary.todayTokens) || 0) / 100) }}</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">本月充值 Token</div>
        <div class="metric-value text-success">{{ formatNumber(summary.monthTokens) }}</div>
        <div class="metric-sub">本月 1 日至今</div>
      </ElCard>
    </div>

    <!-- 当前过滤提示 -->
    <ElAlert v-if="userIdFilter" type="success" :closable="false" class="filter-alert" show-icon>
      <template #title>
        <span>
          已按用户过滤：用户 ID <b>{{ userIdFilter }}</b>
          <span v-if="usernameHint">（{{ usernameHint }}）</span>
          。<ElLink type="primary" :underline="false" @click="clearUserIdFilter">查看全部用户充值记录</ElLink>
          ｜
          <router-link :to="{ name: 'AdminAiUsage', query: { userId: userIdFilter } }" class="inline-link">
            查看该用户的 Token 消费记录
          </router-link>
        </span>
      </template>
    </ElAlert>

    <!-- 充值记录列表 -->
    <ElCard shadow="never" class="section-card">
      <template #header>
        <div class="table-header">
          <span>充值记录明细</span>
          <div class="actions small">
            <ElInput
              v-model="query.keyword"
              placeholder="用户名 / 订单号 / 备注"
              clearable
              style="width: 240px"
              @keyup.enter="onSearch"
              @clear="onSearch"
            />
            <ElInput
              v-model="userIdInput"
              placeholder="用户 ID 精确过滤"
              clearable
              style="width: 160px"
              @keyup.enter="onSearch"
              @clear="onSearch"
            />
            <ElInput
              v-model="query.source"
              placeholder="来源（如 payment）"
              clearable
              style="width: 180px"
              @keyup.enter="onSearch"
              @clear="onSearch"
            />
            <ElButton type="primary" @click="onSearch">查询</ElButton>
            <ElButton @click="onReset">重置</ElButton>
          </div>
        </div>
      </template>

      <AdminDataState v-if="listState === 'loading'" state="loading" title="正在读取充值记录" compact />
      <AdminDataState
        v-else-if="listState === 'error'"
        state="error"
        title="充值记录暂不可用"
        :description="listError"
        retry-text="重新加载"
        compact
        @retry="loadList"
      />
      <template v-else>
        <ElTable :data="list.records" border stripe>
          <template #empty><div class="empty-state">暂无充值记录</div></template>
          <ElTableColumn prop="id" label="ID" width="80" />
          <ElTableColumn label="用户" min-width="160">
            <template #default="{ row }">
              <div class="user-cell">
                <span class="user-name">{{ row.username || '—' }}</span>
                <span class="user-id">#{{ row.userId }}</span>
              </div>
            </template>
          </ElTableColumn>
          <ElTableColumn label="订单号" min-width="180">
            <template #default="{ row }">
              <span class="order-no">{{ row.orderNo || '—' }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="充值 Token" width="130">
            <template #default="{ row }">
              <span class="token-amount">+{{ formatNumber(row.tokenAmount) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="充值前余额" width="120">
            <template #default="{ row }">
              <span class="muted">{{ formatNumber(row.beforeBalance) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="充值后余额" width="120">
            <template #default="{ row }">
              <span class="num-text">{{ formatNumber(row.afterBalance) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="来源" width="110">
            <template #default="{ row }">
              <ElTag size="small" type="warning">{{ row.source || '—' }}</ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="备注" min-width="160" show-overflow-tooltip>
            <template #default="{ row }">{{ row.remark || '—' }}</template>
          </ElTableColumn>
          <ElTableColumn label="充值时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.createdTime) }}</template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="140" fixed="right">
            <template #default="{ row }">
              <router-link
                :to="{ name: 'AdminAiUsage', query: { userId: row.userId } }"
                class="inline-link"
              >
                <ElButton link type="primary" size="small">消费记录</ElButton>
              </router-link>
            </template>
          </ElTableColumn>
        </ElTable>
        <div class="pagination-row">
          <span class="muted">共 {{ list.total }} 条</span>
          <ElPagination
            v-model:current-page="query.current"
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
  import { computed, reactive, ref, watch } from 'vue'
  import { useRoute, useRouter } from 'vue-router'
  import { getRechargeRecordsPage, getRechargeRecordsSummary } from '@/api/recharge-records'
  import AdminDataState from '@/components/business/admin-data-state/index.vue'

  defineOptions({ name: 'AdminRechargeRecordsPage' })

  type ListState = 'loading' | 'ready' | 'error'

  const route = useRoute()
  const router = useRouter()

  const loading = ref(false)
  const listState = ref<ListState>('loading')
  const listError = ref('')
  const usernameHint = ref('')

  const list = reactive<any>({ records: [], total: 0 })
  const query = reactive<any>({
    current: 1,
    size: 20,
    keyword: '',
    source: ''
  })
  // 用户 ID 单独管理：来源可以是路由 query，也可以是搜索栏输入
  const userIdInput = ref<string>('')
  const summary = reactive<any>({
    totalRecords: 0,
    totalTokens: 0,
    todayRecords: 0,
    todayTokens: 0,
    monthTokens: 0
  })

  // 当前生效的 userId 过滤值（优先路由 query，否则取输入框）
  const userIdFilter = computed<number | null>(() => {
    // 路由 query 优先
    const fromRoute = route.query.userId
    if (fromRoute) {
      const n = Number(fromRoute)
      if (Number.isFinite(n) && n > 0) return n
    }
    // 否则取输入框
    const fromInput = Number(userIdInput.value)
    if (userIdInput.value && Number.isFinite(fromInput) && fromInput > 0) return fromInput
    return null
  })

  function formatNumber(value: any): string {
    const n = Number(value)
    if (!Number.isFinite(n)) return '0'
    return n.toLocaleString('zh-CN')
  }

  function formatDateTime(value: any): string {
    if (!value) return '—'
    const text = String(value).trim()
    if (!text || text === '-') return '—'
    // 兼容 ISO 字符串
    if (text.includes('T')) {
      const d = new Date(text)
      if (!isNaN(d.getTime())) {
        const pad = (n: number) => String(n).padStart(2, '0')
        return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}:${pad(d.getSeconds())}`
      }
    }
    return text.replace('T', ' ').replace(/\.\d+.*$/, '').slice(0, 19)
  }

  async function loadList() {
    loading.value = true
    listState.value = 'loading'
    listError.value = ''
    try {
      const params: any = { current: query.current, size: query.size }
      if (query.keyword) params.keyword = query.keyword
      if (query.source) params.source = query.source
      if (userIdFilter.value) params.userId = userIdFilter.value
      const data = await getRechargeRecordsPage(params)
      if (!data || !Array.isArray(data.records)) throw new Error('充值记录接口返回格式异常')
      Object.assign(list, data)
      // 提取首条记录的用户名作为过滤提示
      if (userIdFilter.value && data.records.length > 0) {
        usernameHint.value = data.records[0].username || ''
      } else if (userIdFilter.value) {
        usernameHint.value = ''
      }
      listState.value = 'ready'
      // 同步刷新汇总
      loadSummary()
    } catch (error: any) {
      listError.value = error?.message || '充值记录读取失败，请检查服务状态后重试。'
      listState.value = 'error'
    } finally {
      loading.value = false
    }
  }

  async function loadSummary() {
    try {
      const params: any = {}
      if (userIdFilter.value) params.userId = userIdFilter.value
      const data = await getRechargeRecordsSummary(params)
      Object.assign(summary, data || {})
    } catch (error: any) {
      // 汇总失败不阻塞列表，仅静默
      // eslint-disable-next-line no-console
      console.warn('充值记录汇总加载失败:', error?.message)
    }
  }

  // 将 userIdInput 同步到路由 query（让 URL 可分享），返回是否变更了路由
  function syncUserIdToRoute(): boolean {
    const currentRouteUserId = route.query.userId ? String(route.query.userId) : ''
    const inputVal = userIdInput.value || ''
    if (currentRouteUserId === inputVal) return false
    if (inputVal) {
      router.replace({ query: { ...route.query, userId: inputVal } })
    } else {
      const q = { ...route.query }
      delete q.userId
      router.replace({ query: q })
    }
    return true
  }

  function onSearch() {
    // 同步 userIdInput 到路由（让 URL 可分享）
    const routeChanged = syncUserIdToRoute()
    query.current = 1
    if (!routeChanged) {
      // 路由未变化（仅 keyword/source 变化），直接加载
      loadList()
    }
    // 若路由变化，watch 会触发 loadList
  }

  function onReset() {
    query.keyword = ''
    query.source = ''
    userIdInput.value = ''
    const routeChanged = syncUserIdToRoute()
    query.current = 1
    if (!routeChanged) {
      loadList()
    }
  }

  function clearUserIdFilter() {
    userIdInput.value = ''
    const routeChanged = syncUserIdToRoute()
    query.current = 1
    if (!routeChanged) {
      loadList()
    }
  }

  // 监听路由 query.userId 变化（从用户管理页跳转过来时触发）
  watch(
    () => route.query.userId,
    (val) => {
      userIdInput.value = val ? String(val) : ''
      query.current = 1
      loadList()
    },
    { immediate: true }
  )
</script>

<style scoped lang="scss">
.recharge-records-page {
  display: grid;
  gap: 18px;
}

.toolbar-card {
  border-radius: 18px;
}

.page-title-row {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
}

.page-title-row h2 {
  margin: 0 0 6px;
  font-size: 20px;
  font-weight: 700;
  color: #1f2937;
}

.page-title-row p {
  margin: 0;
  color: #6b7280;
  font-size: 13px;
  line-height: 1.6;
  max-width: 760px;
}

.actions {
  display: flex;
  gap: 8px;
  flex-shrink: 0;
}

.actions.small {
  flex-wrap: wrap;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 14px;
}

.summary-grid .el-card {
  border-radius: 14px;
  padding: 6px 4px;
}

.metric-label {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 8px;
}

.metric-value {
  font-size: 26px;
  font-weight: 800;
  color: #1f2937;
  line-height: 1.1;
  margin-bottom: 4px;
}

.metric-value.text-success {
  color: #16a34a;
}

.metric-sub {
  font-size: 12px;
  color: #9ca3af;
}

.filter-alert {
  border-radius: 12px;
}

.inline-link {
  color: #2563eb;
  text-decoration: none;
  margin: 0 2px;
}
.inline-link:hover {
  text-decoration: underline;
}

.section-card {
  border-radius: 18px;
}

.table-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  flex-wrap: wrap;
  font-weight: 600;
  color: #1f2937;
}

.empty-state {
  padding: 24px;
  color: #9ca3af;
  text-align: center;
}

.user-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.user-name {
  font-weight: 600;
  color: #1f2937;
}
.user-id {
  font-size: 11px;
  color: #9ca3af;
}

.order-no {
  font-family: 'JetBrains Mono', Consolas, Menlo, monospace;
  font-size: 12px;
  color: #4b5563;
  word-break: break-all;
}

.token-amount {
  font-weight: 700;
  color: #16a34a;
}

.num-text {
  font-weight: 600;
  color: #1f2937;
}

.muted {
  color: #9ca3af;
  font-size: 12px;
}

.pagination-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-top: 14px;
  flex-wrap: wrap;
}

@media (max-width: 768px) {
  .summary-grid {
    grid-template-columns: repeat(2, 1fr);
  }
  .page-title-row h2 {
    font-size: 18px;
  }
  .actions.small {
    width: 100%;
  }
}
</style>
