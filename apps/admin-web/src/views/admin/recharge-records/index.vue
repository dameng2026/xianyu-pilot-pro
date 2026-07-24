<template>
  <div class="recharge-records-page">
    <!-- 顶部标题区 -->
    <ElCard shadow="never" class="toolbar-card">
      <div class="page-title-row">
        <div>
          <h2>用户充值记录</h2>
          <p>
            查询所有用户的充值记录（会员充值 + Token 充值）。默认显示全部用户，可通过用户名/订单号/套餐名搜索，或通过用户 ID 精确过滤；
            也可在「用户管理」中点击某用户的「充值记录」按钮直接跳转查看。
          </p>
        </div>
        <div class="actions">
          <ElButton :loading="loading" @click="loadList">刷新</ElButton>
        </div>
      </div>
    </ElCard>

    <!-- 今日收入模块 -->
    <ElCard shadow="never" class="today-card">
      <template #header>
        <div class="section-title">
          <span class="title-text">今日收入</span>
          <span class="title-sub">今日 0 点至今已支付成功的订单流水</span>
        </div>
      </template>
      <div class="today-grid">
        <div class="today-item today-total">
          <div class="today-label">今日合计</div>
          <div class="today-value">¥{{ formatAmount(todayRevenue.totalAmountCent) }}</div>
          <div class="today-sub">{{ formatNumber(todayRevenue.totalCount) }} 笔</div>
        </div>
        <div class="today-item">
          <div class="today-label">会员充值</div>
          <div class="today-value text-vip">¥{{ formatAmount(todayRevenue.vipAmountCent) }}</div>
          <div class="today-sub">{{ formatNumber(todayRevenue.vipCount) }} 笔</div>
        </div>
        <div class="today-item">
          <div class="today-label">Token 充值</div>
          <div class="today-value text-token">¥{{ formatAmount(todayRevenue.tokenAmountCent) }}</div>
          <div class="today-sub">{{ formatNumber(todayRevenue.tokenCount) }} 笔</div>
        </div>
      </div>
    </ElCard>

    <!-- 累计统计卡片 -->
    <div class="summary-grid">
      <ElCard shadow="never">
        <div class="metric-label">累计充值笔数</div>
        <div class="metric-value">{{ formatNumber(cumulative.totalRecords) }}</div>
        <div class="metric-sub">{{ userIdFilter ? '当前用户' : '全部用户' }}</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">累计充值金额</div>
        <div class="metric-value text-success">¥{{ formatAmount(cumulative.totalAmountCent) }}</div>
        <div class="metric-sub">会员 ¥{{ formatAmount(cumulative.vipTotalAmountCent) }} ｜ Token ¥{{ formatAmount(cumulative.tokenTotalAmountCent) }}</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">会员充值笔数</div>
        <div class="metric-value">{{ formatNumber(cumulative.vipTotalRecords) }}</div>
        <div class="metric-sub">¥{{ formatAmount(cumulative.vipTotalAmountCent) }}</div>
      </ElCard>
      <ElCard shadow="never">
        <div class="metric-label">Token 充值笔数</div>
        <div class="metric-value">{{ formatNumber(cumulative.tokenTotalRecords) }}</div>
        <div class="metric-sub">¥{{ formatAmount(cumulative.tokenTotalAmountCent) }} ｜ {{ formatNumber(cumulative.tokenTotalTokens) }} Token</div>
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
            <ElSelect
              v-model="query.orderType"
              placeholder="充值类型"
              clearable
              style="width: 140px"
              @change="onSearch"
            >
              <ElOption label="全部" value="" />
              <ElOption label="会员充值" value="vip" />
              <ElOption label="Token 充值" value="token" />
            </ElSelect>
            <ElInput
              v-model="query.keyword"
              placeholder="用户名 / 订单号 / 套餐名"
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
          <ElTableColumn label="类型" width="110">
            <template #default="{ row }">
              <ElTag size="small" :type="row.orderType === 'vip' ? 'danger' : 'success'">
                {{ row.recordTypeText || (row.orderType === 'vip' ? '会员充值' : 'Token 充值') }}
              </ElTag>
            </template>
          </ElTableColumn>
          <ElTableColumn label="用户" min-width="140">
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
          <ElTableColumn label="套餐 / 周期" min-width="160">
            <template #default="{ row }">
              <div class="plan-cell">
                <span class="plan-name">{{ row.planName || row.title || '—' }}</span>
                <ElTag v-if="row.periodText" size="small" type="info" effect="plain">{{ row.periodText }}</ElTag>
              </div>
            </template>
          </ElTableColumn>
          <ElTableColumn label="金额" width="120">
            <template #default="{ row }">
              <span class="amount-text">¥{{ formatYuan(row.amountYuan) }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="Token 数量" width="120">
            <template #default="{ row }">
              <span v-if="row.orderType === 'token'" class="token-amount">+{{ formatNumber(row.tokenAmount) }}</span>
              <span v-else class="muted">—</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="支付方式" width="110">
            <template #default="{ row }">
              <span>{{ row.paymentMethodText || '—' }}</span>
            </template>
          </ElTableColumn>
          <ElTableColumn label="绑定账号" width="140">
            <template #default="{ row }">
              <div class="target-cell">
                <span class="muted">{{ row.targetTypeText || '—' }}</span>
                <span v-if="row.targetId" class="user-id">#{{ row.targetId }}</span>
              </div>
            </template>
          </ElTableColumn>
          <ElTableColumn label="支付时间" width="170">
            <template #default="{ row }">{{ formatDateTime(row.paidTime || row.createdTime) }}</template>
          </ElTableColumn>
          <ElTableColumn label="操作" width="120" fixed="right">
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
  import {
    getUnifiedRechargeRecordsPage,
    getUnifiedRechargeRecordsSummary
  } from '@/api/recharge-records'
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
    orderType: ''
  })
  // 用户 ID 单独管理：来源可以是路由 query，也可以是搜索栏输入
  const userIdInput = ref<string>('')

  const todayRevenue = reactive<any>({
    totalCount: 0,
    totalAmountCent: 0,
    vipCount: 0,
    vipAmountCent: 0,
    tokenCount: 0,
    tokenAmountCent: 0
  })

  const cumulative = reactive<any>({
    totalRecords: 0,
    totalAmountCent: 0,
    vipTotalRecords: 0,
    vipTotalAmountCent: 0,
    tokenTotalRecords: 0,
    tokenTotalAmountCent: 0,
    tokenTotalTokens: 0
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

  /** 分（cent）转元并格式化 */
  function formatAmount(cent: any): string {
    const n = Number(cent)
    if (!Number.isFinite(n)) return '0.00'
    return (n / 100).toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
  }

  /** 元直接格式化 */
  function formatYuan(yuan: any): string {
    const n = Number(yuan)
    if (!Number.isFinite(n)) return '0.00'
    return n.toLocaleString('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 })
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
      if (query.orderType) params.orderType = query.orderType
      if (userIdFilter.value) params.userId = userIdFilter.value
      const data = await getUnifiedRechargeRecordsPage(params)
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
      const data = await getUnifiedRechargeRecordsSummary(params)
      const today = data?.todayRevenue || {}
      const cum = data?.cumulative || {}
      Object.assign(todayRevenue, {
        totalCount: Number(today.totalCount) || 0,
        totalAmountCent: Number(today.totalAmountCent) || 0,
        vipCount: Number(today.vipCount) || 0,
        vipAmountCent: Number(today.vipAmountCent) || 0,
        tokenCount: Number(today.tokenCount) || 0,
        tokenAmountCent: Number(today.tokenAmountCent) || 0
      })
      Object.assign(cumulative, {
        totalRecords: Number(cum.totalRecords) || 0,
        totalAmountCent: Number(cum.totalAmountCent) || 0,
        vipTotalRecords: Number(cum.vipTotalRecords) || 0,
        vipTotalAmountCent: Number(cum.vipTotalAmountCent) || 0,
        tokenTotalRecords: Number(cum.tokenTotalRecords) || 0,
        tokenTotalAmountCent: Number(cum.tokenTotalAmountCent) || 0,
        tokenTotalTokens: Number(cum.tokenTotalTokens) || 0
      })
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
      // 路由未变化（仅 keyword/orderType 变化），直接加载
      loadList()
    }
    // 若路由变化，watch 会触发 loadList
  }

  function onReset() {
    query.keyword = ''
    query.orderType = ''
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

/* 今日收入模块 */
.today-card {
  border-radius: 18px;
  background: linear-gradient(135deg, #fff 0%, #f0f9ff 100%);
}

.section-title {
  display: flex;
  align-items: baseline;
  gap: 10px;
}

.title-text {
  font-size: 16px;
  font-weight: 700;
  color: #1f2937;
}

.title-sub {
  font-size: 12px;
  color: #9ca3af;
}

.today-grid {
  display: grid;
  grid-template-columns: 1.4fr 1fr 1fr;
  gap: 14px;
}

.today-item {
  padding: 14px 16px;
  border-radius: 14px;
  background: #fff;
  border: 1px solid #f0f0f0;
}

.today-total {
  background: linear-gradient(135deg, #fff7ed 0%, #ffedd5 100%);
  border-color: #fed7aa;
}

.today-label {
  font-size: 13px;
  color: #6b7280;
  margin-bottom: 8px;
}

.today-value {
  font-size: 28px;
  font-weight: 800;
  color: #1f2937;
  line-height: 1.1;
  margin-bottom: 4px;
  letter-spacing: -0.5px;
}

.today-value.text-vip {
  color: #dc2626;
}

.today-value.text-token {
  color: #16a34a;
}

.today-sub {
  font-size: 12px;
  color: #9ca3af;
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

.plan-cell {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.plan-name {
  font-weight: 600;
  color: #1f2937;
  font-size: 13px;
}

.amount-text {
  font-weight: 700;
  color: #dc2626;
  font-family: 'JetBrains Mono', Consolas, Menlo, monospace;
}

.token-amount {
  font-weight: 700;
  color: #16a34a;
}

.target-cell {
  display: flex;
  flex-direction: column;
  gap: 2px;
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
  .today-grid {
    grid-template-columns: 1fr;
  }
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
